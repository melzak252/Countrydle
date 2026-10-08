import asyncio
import time
from typing import List, Tuple
import qdrant
from utils.ai_clients import gemini_json

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, CountrydleDay, User
from schemas.country import DayCountryDisplay
from schemas.countrydle import QuestionCreate, QuestionEnhanced
from db.repositories.country import CountryRepository
from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import QuestionPlan, analyze_question_for_local_plan
from countrydle.template_compiler import _bind_named_country_subject


from utils.explanation_sanitizer import sanitize_explanation_for_player



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
    """Plan the complete question and answer locally when its predicate is supported."""
    country: Country = await CountryRepository(session).get(day_country.country_id)
    if hasattr(session, "commit") and callable(session.commit):
        commit_res = session.commit()
        if asyncio.iscoroutine(commit_res):
            await commit_res
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
        explanation=sanitize_explanation_for_player(
            local_answer.explanation,
            entity_names=[name for name in (country.name, country.official_name) if name],
        ),
        intent=f"Local KB relation: {local_answer.relation}",
        required_info=local_answer.relation,
        context=f"local_kb:{local_answer.relation}",
        fact_provenance=local_answer.fact_provenance,
    ), planned_question


def answer_prompts(
    question: QuestionEnhanced, entity_name: str, context: str,
) -> tuple[str, str]:
    """Build the shared daily and explicit-target answer instructions."""
    system_prompt = f"""
You are the 'Game Master' for Countrydle. Evaluate the exact True/False proposition using the entity-binding rules first, then the provided context and reliable general knowledge.

### Hidden Target Country: {entity_name}

### Entity Binding (resolve before looking up or comparing facts)
- Pronouns and user references to themselves as the country denote the hidden target.
- Exact leading country-name subjects have already been replaced with "the country" in the question data. Evaluate that subject using {entity_name}'s facts, not another country's facts mentioned in the context.
- Country names in explicit property phrases and comparison/object references are LITERAL, not placeholders. A named country's population, area, capital or other property belongs to that named country; never substitute {entity_name}'s property merely because a hidden target is supplied.
- A country-name SUBJECT elsewhere in a compound question still denotes the hidden target. Do not confuse a named property/reference with a country-name subject. Apply these role distinctions before computing the answer.
- Quoted text remains literal. Preserve the requested relationship, qualifiers, negation and date after resolving entities.

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
9. **User Perspective**: Answer about the country in the third person, applying the entity bindings above rather than substituting the hidden target for every named reference.
10. **STRICT SECRECY (NO SPOILERS)**:
    - The player is trying to guess the hidden country. You must NEVER state, name, or reveal the target country's name ({entity_name}) in the explanation, whether the answer is true, false, or null!
    - Always refer to the target as "the country" or "this country" (e.g. "The country is located on the mainland...", NOT "{entity_name} is located on the mainland...").
    - NEVER reference internal context fragments or retrieval (e.g. NEVER write "The provided text mentions...", "Context fragments show...").
11. **Common Sense Geographic Reasoning (Thresholds & Composition)**:
    - "Majority", "most", or "większość" means more than 50% (> 50%) of the land area.
    - Apply geographic common sense:
      - Continental mainland nations (such as Vietnam, France, Canada, Greece) have the overwhelming majority of their territory on the continental mainland. Coastal islands make up only a tiny fraction (< 5% to 20%), so questions asking if most or a majority (> 50%) of the territory is islands are unequivocally FALSE. Do NOT abstain with null!
      - Archipelagos and island nations (such as Indonesia, Japan, Philippines, UK) have > 50% of their territory on islands; answer TRUE.
      - Do NOT return null merely because context fragments omit exact square-kilometer surface area percentages. If geographic common sense clearly establishes whether a country is continental vs island-dominated, answer true or false with a concise fact.
12. **Linguistic Identity ("Their own language" / "Własny język")**:
    - For questions asking whether the country has or speaks "their own language" (or "własny język"):
      - Answer TRUE if the country has an official or primary national language unique to or primarily named after its nation/people (e.g. Polish in Poland, French in France, Vietnamese in Vietnam, Japanese in Japan, German in Germany, Spanish in Spain, Italian in Italy).
      - Answer FALSE if the country primarily speaks a shared or borrowed language originating elsewhere (e.g. English in the United States, Australia, Canada, New Zealand; Spanish in Mexico, Argentina, Colombia; Portuguese in Brazil; German in Austria).
### Output Format (Strict JSON):
{{
    "explanation": "One concise fact directly relevant to the question, or a brief reason the answer is uncertain.",
    "answer": true | false | null
}}
For a well-defined historical question, use available historical knowledge rather than abstaining solely because of its date.
"""

    original = _bind_named_country_subject(question.original_question)
    simplified = _bind_named_country_subject(question.question)
    question_prompt = f"""User's Question (country subjects bound to the hidden target): {original}
Suggested Rewrite (do not drop the original proposition's modifiers): {simplified}"""
    return system_prompt, question_prompt


def answer_question_for_entity(
    question: QuestionEnhanced, entity_name: str, context: str, *,
    evidence: dict | None = None, request_timeout: float | None = None,
    model: str | None = None, deadline: float | None = None,
) -> dict:
    """Run the normal answer model for an explicit target, without daily state."""
    system_prompt, question_prompt = answer_prompts(question, entity_name, context)
    from utils.fallback_answers import get_answer
    answer_dict = get_answer(
        system_prompt, question_prompt, evidence=evidence,
        request_timeout=request_timeout, deadline=deadline, model=model,
    )
    answer_dict["explanation"] = sanitize_explanation_for_player(
        answer_dict["explanation"], {entity_name}, "the country"
    )
    return answer_dict


async def ask_question(
    question: QuestionEnhanced,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
    *,
    evidence: dict | None = None,
    use_cache: bool = True,
) -> Tuple[QuestionCreate, List[float]]:
    country: Country = await CountryRepository(session).get(day_country.country_id)
    if hasattr(session, "commit") and callable(session.commit):
        commit_res = session.commit()
        if asyncio.iscoroutine(commit_res):
            await commit_res
    from utils.fallback import retrieve_and_answer
    answer_dict, context, question_vector = await retrieve_and_answer(
        question, country.name,
        cache_scope=("countrydle", day_country.country_id) if use_cache else None,
        filter_key="country_id", filter_value=day_country.country_id,
        collection_name="countries", context_limit=qdrant.COUNTRYDLE_CONTEXT_LIMIT,
        session=session, answerer=answer_question_for_entity,
        prompt_builder=answer_prompts, evidence=evidence,
        game_date=getattr(day_country, "date", None),
    )
    question_create = QuestionCreate(
        user_id=user.id if user else None,
        day_id=day_country.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict["answer"],
        explanation=sanitize_explanation_for_player(
            answer_dict["explanation"],
            {country.name, getattr(country, "official_name", None)} if getattr(country, "official_name", None) else {country.name},
            "the country",
        ),
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
