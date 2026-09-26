import asyncio
import os
import time
from typing import List, Tuple
import httpx
from utils.ai_clients import generate_gemini_json

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, CountrydleDay, User
from qdrant.utils import get_fragments_matching_question
import qdrant
from schemas.country import DayCountryDisplay
from schemas.countrydle import QuestionCreate, QuestionEnhanced
from db.repositories.country import CountryRepository
from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import QuestionPlan, analyze_question_for_local_plan


GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"


FALLBACK_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string", "minLength": 1},
        "answer": {"type": ["boolean", "null"]},
    },
    "required": ["answer", "explanation"],
    "additionalProperties": False,
}


def gemini_json(
    system_prompt: str, user_prompt: str, max_output_tokens: int = 1024, *,
    evidence: dict | None = None, request_timeout: float = 60, max_attempts: int = 3,
    response_schema: dict | None = None, thinking_budget: int | None = None,
) -> dict:
    """Call Gemini through the shared connection pool, retaining fallback retry policy."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = (
        os.getenv("GEMINI_QUIZ_MODEL")
        or os.getenv("LOCAL_QUESTION_MODEL")
        or os.getenv("GEMINI_MODEL")
        or GEMINI_DEFAULT_MODEL
    )
    prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
    retryable_statuses = {429, 500, 502, 503, 504}
    for attempt in range(max_attempts):
        try:
            parsed = generate_gemini_json(
                prompt, model=model, api_key=api_key, max_output_tokens=max_output_tokens,
                timeout=request_timeout, evidence=evidence, response_schema=response_schema,
                thinking_budget=thinking_budget if model.startswith("gemini-2.5") else None,
            )
            break
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in retryable_statuses or attempt == max_attempts - 1:
                raise RuntimeError(f"Gemini HTTP error {status}") from exc
            time.sleep(2**attempt)
    else:
        raise RuntimeError("Gemini request failed")
    if evidence is not None:
        evidence.update(
            provider="gemini", model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0, max_output_tokens=max_output_tokens,
        )

    return parsed


async def enhance_question(question: str) -> QuestionEnhanced:
    system_prompt = """
You are an expert Question Analyzer for a geography guessing game. Your goal is to process user questions into a structured format that facilitates accurate information retrieval.

### Your Core Responsibilities:
1. **Semantic Analysis**: Understand the true intent behind the user's question, regardless of language or phrasing.
2. **Validation**: Determine if the input is a valid True/False question about a country's attributes (geography, politics, culture, etc.).
3. **Simplification**: Rewrite the question into a clear, atomic, and standardized English sentence with "the country" as the subject.
4. **Intent & Information Mapping**: Explicitly define what the question is trying to verify and what specific data points are needed to answer it.

### Guidelines:
- **Language Agnostic**: The user might ask in any language. Always translate the meaning to English for the `question` field.
- **Entity Reference**: The user may refer to the target country in various ways:
    - Talking about themselves: "Am I ...?", "Do I ...?", "Am I located in ...?"
    - Using "it/this/that": "Is it ...?", "Does it ...?", "Is this ...?"
    - Using "the country": "Is the country ...?", "Does the country ...?"
- **Subject Consistency**: The simplified question MUST start with or focus on "the country" (e.g., "Is the country...", "Does the country...").
- **Atomic Intent**: If a question is compound, focus on the primary query (e.g., "Is the country located in Eurasia?" -> "Is the country located in Europe or Asia?").
- **Required Info**: Be specific about the data needed (e.g., "List of bordering countries", "Official currency", "GDP per capita").
- **Identity Questions Are Allowed**: Direct yes/no identity checks and lists of
  candidate countries are valid uses of the question allowance. Do not reject
  them as guesses or cheating, or tell the player to use the guess field.
  They remain questions; the application handles limits and winning separately.

### Output Format (Strict JSON):
{
  "question": "Simplified English T/F question",
  "intent": "Detailed description of the user's intention and what they are trying to find out",
  "required_info": "Specific data points needed from the database",
  "valid": true,
  "explanation": null
}
-- OR if invalid --
{
  "question": null,
  "intent": null,
  "required_info": null,
  "valid": false,
  "explanation": "Clear reason why the question is invalid (e.g., not a T/F question, gibberish)"
}

### Examples:
User: "Czy graniczy z Niemcami?"
Output: {"question": "Does the country border Germany?", "intent": "The user wants to verify if the target country shares a physical land border with Germany.", "required_info": "List of countries that share a land border with the target country", "valid": true, "explanation": null}

User: "Is it Poland?"
Output: {"question": "Is the country Poland?", "intent": "The user wants to check whether the target country is Poland using a yes/no question.", "required_info": "The name of the country", "valid": true, "explanation": null}

User: "Is it Germany, Poland or France?"
Output: {"question": "Is the country one of the following: Germany, Poland, or France?", "intent": "The user is providing a list of countries and wants to know if the target country is one of them.", "required_info": "The name of the country", "valid": true, "explanation": null}

User: "Is it in Eurasia?"
Output: {"question": "Is the country located in Europe or Asia?", "intent": "The user is inquiring about the continental location of the country, specifically if it belongs to the combined landmass of Europe and Asia. This requires checking both Europe and Asia as potential continents.", "required_info": "The continent(s) where the country is located", "valid": true, "explanation": null}

User: "Tell me about the capital."
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "This is an open-ended request, not a True/False question."}
"""

    question_prompt = f"""User's Question: {question}"""

    answer_dict = await asyncio.to_thread(gemini_json, system_prompt, question_prompt, max_output_tokens=768)

    return QuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation")
        or ("No explanation provided." if not answer_dict["valid"] else None),
    )


def question_enhanced_from_plan(original_question: str, plan: QuestionPlan) -> QuestionEnhanced:
    """Preserve the question; planner coverage notes are not factual evidence."""
    return QuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question or original_question,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(
    original_question: str,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
    *,
    strict_errors: bool = False,
    evidence: dict | None = None,
) -> tuple[QuestionCreate | None, QuestionPlan]:
    """Run one Gemini validator/planner call and answer locally when possible."""
    country: Country = await CountryRepository(session).get(day_country.country_id)
    planner_kwargs = {"strict_errors": True, "use_cache": False} if strict_errors else {}
    if evidence is not None:
        planner_evidence = evidence.setdefault("planner", {})
        planner_kwargs["evidence"] = planner_evidence
        planner_started = time.perf_counter()
    try:
        planned_question = await asyncio.to_thread(
            analyze_question_for_local_plan, original_question, **planner_kwargs
        )
    finally:
        if evidence is not None:
            planner_evidence["duration_ms"] = (time.perf_counter() - planner_started) * 1000

    if not planned_question.valid:
        return QuestionCreate(
            user_id=user.id if user else None,
            day_id=day_country.id,
            original_question=original_question,
            valid=False,
            question=planned_question.improved_question,
            answer=None,
            explanation=planned_question.explanation or "This is not a valid yes/no country question.",
            intent="Gemini question analyzer validation failed",
            required_info=None,
            context="local_planner:invalid",
        ), planned_question

    if not planned_question.supported or not planned_question.plan:
        return None, planned_question

    if evidence is not None:
        local_started = time.perf_counter()
    try:
        local_answer = await asyncio.to_thread(
            execute_local_plan,
            planned_question.plan,
            country.name,
            planned_question.improved_question or original_question,
        )
    finally:
        if evidence is not None:
            evidence["local_duration_ms"] = (time.perf_counter() - local_started) * 1000
    if local_answer is None:
        return None, planned_question

    return QuestionCreate(
        user_id=user.id if user else None,
        day_id=day_country.id,
        original_question=original_question,
        valid=True,
        question=local_answer.question,
        answer=local_answer.answer,
        explanation=local_answer.explanation,
        intent=f"Local KB relation: {local_answer.relation}",
        required_info=local_answer.relation,
        context=f"local_kb:{local_answer.relation}",
    ), planned_question


def answer_prompts(
    question: QuestionEnhanced, entity_name: str, context: str,
) -> tuple[str, str]:
    """Build the shared daily and explicit-target answer instructions."""
    system_prompt = f"""
You are the 'Game Master' for Countrydle. Your task is to answer a True/False question about a specific country based on provided context and your general knowledge.

### Target Country: {entity_name}

### Context Fragments:
{context}

1. **Analyze the Context**: Evaluate the exact predicate asked, using evidence that directly confirms or denies it. If retrieval is silent or irrelevant, use reliable general knowledge when available; do not abstain solely because a fact is absent from the fragments.
2. **Compute the Predicate**: Resolve the requested entity, property, quantifier, comparison, and any arithmetic exactly. Use the resulting fact to select `true` or `false`, and ensure the explanation directly supports that same answer. Never let an explanation that establishes one result accompany the opposite boolean.
3. **Preserve Geographic Scope**: Interpret quantifiers, qualifiers, and negation literally. An unqualified question about whether a country is in a region normally asks whether any of its territory lies there; “partly” or “any part” requires some territory there; “entirely,” “fully,” or “only” requires all of its territory there; “mostly” or “majority” requires more than half using the measure asked about. Apply negation exactly. Never let the general transcontinental rule override a more specific qualifier.
4. **Handle Uncertainty**: If the exact answer cannot be determined with high confidence from reliable evidence or stable general knowledge, set `answer` to `null`. Use established broad counts and historical membership when they answer the question, even if retrieval is irrelevant. Null is only for genuinely undetermined facts, not facts omitted from context.
5. **Special Rule (Self-Bordering)**: If the unnegated question asks whether the country borders/neighbors [X], and the target country IS [X], the answer is `true`. Treat a country as bordering itself for this game, while respecting explicit negation.
6. **Temporal Questions**: Answer the period the question asks about. Do not impose an arbitrary date cutoff. If asked about a current fact and you cannot establish it reliably, abstain with `null`.
7. **Focused Explanations**: Give only a concise fact directly relevant to the question that supports the answer. Do not add unrelated facts or claims about current officeholders unless they are needed to answer the question; avoid asserting that a potentially stale fact is current.
8. **Handle Logical 'OR' and Lists**: Treat 'or' as inclusive, so an unnegated question is true if any branch is true. Apply negation and the exact qualifiers in each branch; do not let this rule override them.
9. **User Perspective**: If the user refers to themselves as the country (e.g., "Am I in Europe?"), answer about the country in the third person.
### Output Format (Strict JSON):
{{
    "explanation": "One concise fact directly relevant to the question, or a brief reason the answer is uncertain.",
    "answer": true | false | null
}}
For a well-defined historical question, use available historical knowledge rather than abstaining solely because of its date.
"""

    question_prompt = f"""User's Original Question: {question.original_question}
Simplified Question: {question.question}"""
    return system_prompt, question_prompt


def answer_question_for_entity(
    question: QuestionEnhanced, entity_name: str, context: str, *,
    evidence: dict | None = None, request_timeout: float | None = None,
) -> dict:
    """Run the normal answer model for an explicit target, without daily state."""
    system_prompt, question_prompt = answer_prompts(question, entity_name, context)

    answer_dict = gemini_json(
        system_prompt, question_prompt, max_output_tokens=2048, evidence=evidence,
        request_timeout=60 if request_timeout is None else request_timeout,
        max_attempts=3 if request_timeout is None else 1,
        response_schema=FALLBACK_ANSWER_SCHEMA, thinking_budget=1024,
    )
    if not isinstance(answer_dict, dict):
        raise ValueError("Gemini answer must be a JSON object")
    if "answer" not in answer_dict:
        raise ValueError("Gemini answer is missing the answer field")
    answer = answer_dict["answer"]
    if answer is not None and type(answer) is not bool:
        raise ValueError("Gemini answer must be true, false, or null")
    if answer_dict.keys() - {"answer", "explanation"}:
        raise ValueError("Gemini answer contains unexpected fields")
    explanation = answer_dict.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Gemini answer must include a non-empty explanation")
    return answer_dict


async def ask_question(
    question: QuestionEnhanced,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
    *,
    evidence: dict | None = None,
) -> Tuple[QuestionCreate, List[float]]:

    fragments = []
    question_vector = []
    if evidence is not None:
        retrieval_started = time.perf_counter()
    try:
        fragments, question_vector = await get_fragments_matching_question(
            question.question,
            "country_id",
            day_country.country_id,
            "countries",
            session,
            limit=qdrant.COUNTRYDLE_CONTEXT_LIMIT,
        )
    except Exception as exc:
        print(f"Warning: Vector retrieval failed ({exc}); answering directly with Gemini general knowledge.")
    finally:
        if evidence is not None:
            evidence["retrieval_duration_ms"] = (time.perf_counter() - retrieval_started) * 1000

    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments) if fragments else ""
    country: Country = await CountryRepository(session).get(day_country.country_id)
    answer_kwargs = {}
    if evidence is not None:
        fallback_evidence = evidence.setdefault("fallback", {})
        answer_kwargs["evidence"] = fallback_evidence
        fallback_started = time.perf_counter()
    try:
        answer_dict = await asyncio.to_thread(
            answer_question_for_entity, question, country.name, context, **answer_kwargs
        )
    finally:
        if evidence is not None:
            fallback_evidence["duration_ms"] = (time.perf_counter() - fallback_started) * 1000

    question_create = QuestionCreate(
        user_id=user.id if user else None,
        day_id=day_country.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict["answer"],
        explanation=answer_dict["explanation"],
        context=context,
    )

    return question_create, question_vector


async def ask_question_locally(
    original_question: str,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
) -> QuestionCreate | None:
    """Try to answer a Countrydle question from the local SQLite KB.

    Returns None when the question cannot be mapped confidently to a local
    relation, so callers can fall back to the existing Gemini + Qdrant flow.
    """
    local_question, _planned_question = await analyze_and_answer_locally(
        original_question=original_question,
        day_country=day_country,
        user=user,
        session=session,
    )
    return local_question


async def give_guess(
    guess: str, daily_country: DayCountryDisplay, user: User, session: AsyncSession
):
    country: Country = await CountryRepository(session).get(daily_country.country_id)

    system_prompt = f"""
    You are the game master for a country guessing game. The player will guess a country, and you must determine if the guess is correct.

    Answering Guidelines:
        - true: If the player correctly guessed the country, including casual or abbreviated names (e.g., USA, Holland, Pol).
        - false: If the player's guess does not match the country.
        - null: If the guess is unclear or confusing.
    
    Answer guess True or False if you are fully confident of the answer.
    Answer guess NA if guess is confusing you.

    Country to Guess: {country.name} ({country.official_name})

    ### Task: 
    Use your best knowledge to determine if the player's guess is correct. Respond only in JSON format as follows:
    {{
        "answer": true | false | null,
    }}
    ### 
    
    ### Examples
    Country: Poland. Guess: Polska
    {{
        "answer": true
    }}
    
    Country: France. Guess: Franc
    {{
        "answer": true
    }}
    
    Country: United States of America. Guess: USA 
    {{
        "answer": true
    }}
    
    Country: Germany. Guess: Austria
    {{
        "answer": false
    }}
    
    Country: Australia. Guess: Austria
    {{
        "answer": false
    }}
    
    Country: France. Guess: Germany or France
    {{
        "answer": null
    }} # False because player tried to cheat. He can ask one guess at a time.
    """

    guess_prompt = f"Guess: {guess}"

    answer_dict = await asyncio.to_thread(gemini_json, system_prompt, guess_prompt, max_output_tokens=128)

    return answer_dict
