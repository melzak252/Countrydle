import os
import json
import time
from typing import List, Tuple
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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


def gemini_json(system_prompt: str, user_prompt: str, max_output_tokens: int = 1024) -> dict:
    """Call Gemini and return a strict JSON object.

    Used for the Countrydle fallback pipeline so we can move away from OpenAI
    while keeping the old two-step enhance/answer architecture as fallback.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = (
        os.getenv("GEMINI_QUIZ_MODEL")
        or os.getenv("LOCAL_QUESTION_MODEL")
        or os.getenv("GEMINI_MODEL")
        or GEMINI_DEFAULT_MODEL
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: RuntimeError | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                break
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Gemini HTTP error {exc.code}: {body[:500]}")
            if exc.code not in retryable_statuses or attempt == 2:
                raise last_error from exc
            time.sleep(2**attempt)
    else:
        raise last_error or RuntimeError("Gemini request failed")

    answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        print(answer)
        raise
    if not isinstance(parsed, dict):
        raise ValueError("Gemini returned JSON that is not an object")
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
Output: {"question": "Is the country Poland?", "intent": "The user is making a direct guess to see if the target country is Poland.", "required_info": "The name of the country", "valid": true, "explanation": null}

User: "Is it Germany, Poland or France?"
Output: {"question": "Is the country one of the following: Germany, Poland, or France?", "intent": "The user is providing a list of countries and wants to know if the target country is one of them.", "required_info": "The name of the country", "valid": true, "explanation": null}

User: "Is it in Eurasia?"
Output: {"question": "Is the country located in Europe or Asia?", "intent": "The user is inquiring about the continental location of the country, specifically if it belongs to the combined landmass of Europe and Asia. This requires checking both Europe and Asia as potential continents.", "required_info": "The continent(s) where the country is located", "valid": true, "explanation": null}

User: "Tell me about the capital."
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "This is an open-ended request, not a True/False question."}
"""

    question_prompt = f"""User's Question: {question}"""

    answer_dict = gemini_json(system_prompt, question_prompt, max_output_tokens=768)

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
    """Reuse the single local analyzer/planner output as the fallback enhanced question."""
    return QuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question or original_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason
        or "More context is needed to answer this question confidently.",
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(
    original_question: str,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
) -> tuple[QuestionCreate | None, QuestionPlan]:
    """Run one Gemini validator/planner call and answer locally when possible."""
    country: Country = await CountryRepository(session).get(day_country.country_id)
    planned_question = analyze_question_for_local_plan(original_question)

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

    local_answer = execute_local_plan(
        planned_question.plan,
        country.name,
        planned_question.improved_question or original_question,
        planned_question.explanation,
    )
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


async def ask_question(
    question: QuestionEnhanced,
    day_country: CountrydleDay,
    user: User | None,
    session: AsyncSession,
) -> Tuple[QuestionCreate, List[float]]:

    fragments, question_vector = await get_fragments_matching_question(
        question.question,
        "country_id",
        day_country.country_id,
        "countries",
        session,
        limit=qdrant.COUNTRYDLE_CONTEXT_LIMIT,
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    country: Country = await CountryRepository(session).get(day_country.country_id)

    system_prompt = f"""
You are the 'Game Master' for Countrydle. Your task is to answer a True/False question about a specific country based on provided context and your general knowledge.

### Target Country: {country.name}
### Question Intent: {question.intent}
### Required Information: {question.required_info}

### Context Fragments:
{context}

### Your Instructions:
1. **Analyze the Context**: Look for specific facts in the provided context that directly confirm or deny the question.
2. **Use General Knowledge**: If the context is missing the specific fact, use your internal knowledge to provide an accurate answer.
3. **Handle Super-regions (e.g., Eurasia)**: If the question asks about a large landmass or super-region (like Eurasia, The Americas, Oceania), and the country is located in any part of that region (e.g., Europe or Asia for Eurasia), the answer must be `true`.
4. **Transcontinental Logic**: For countries spanning multiple continents (e.g., Turkey, Russia, Egypt, Kazakhstan), if the question asks if they are in either of those continents, the answer is `true`.
5. **Handle Uncertainty**: If the answer cannot be determined with high confidence, set `answer` to `null`.
6. **Special Rule (Self-Bordering)**: If asked if the country borders/neighbors [X], and the target country IS [X], the answer is ALWAYS `true`. Treat a country as bordering itself for the purpose of this game.
7. **Temporal Cutoff**: For any events or data from April 2024 onwards, set `answer` to `null`.
8. **Informative Explanations**: Write the `explanation` as factual information about the country that answers the question and provides details. Avoid starting with 'Yes' or 'No' or simply repeating the answer. The explanation should be an informative statement about the country that justifies the True/False answer (e.g., instead of 'Yes, it is in Europe', use '{country.name} is a country located in Southeastern Europe, bordering the Black Sea.').
9. **Handle Logical 'OR' and Lists**: If a question contains 'or' or provides a list of options (e.g., 'Is it in Europe or Asia?', 'Is it Poland, Germany, or France?'), the answer is `true` if the target country matches **at least one** of those options. Do not answer `false` just because it doesn't match all of them.

10. **User Perspective**: If the user refers to themselves as the country (e.g., "Am I in Europe?"), you should still answer about the country in the third person (e.g., "{country.name} is in Europe") to maintain a factual and informative tone.

### Output Format (Strict JSON):
{{
    "explanation": "Informative factual statement about the country.",
    "answer": true | false | null
}}
"""

    question_prompt = f"""User's Original Question: {question.original_question}
Simplified Question: {question.question}"""

    answer_dict = gemini_json(system_prompt, question_prompt, max_output_tokens=768)

    question_create = QuestionCreate(
        user_id=user.id if user else None,
        day_id=day_country.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "No explanation provided.",
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
    relation, so callers can fall back to the existing OpenAI + Qdrant flow.
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

    answer_dict = gemini_json(system_prompt, guess_prompt, max_output_tokens=128)

    return answer_dict
