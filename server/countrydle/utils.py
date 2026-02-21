import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Country, CountrydleDay, User
from qdrant.utils import get_fragments_matching_question
from schemas.country import DayCountryDisplay
from schemas.countrydle import QuestionCreate, QuestionEnhanced
from db.repositories.country import CountryRepository


async def enhance_question(question: str) -> QuestionEnhanced:
    system_prompt = """
You are an AI assistant for a game where players guess a country by asking True/False questions. 
Your task is to:

1. Receive a user's question.
2. Retrieve the meaning of the user's question.
3. Determine if it is a valid True/False question about possible country.
4. Questions asking if the country is a specific country (e.g., "Is it Poland?") are VALID.
5. If It's valid then improve the question by make it more obvious about its intent.
6. If It's not valid then provide an explanation why the question is not valid.

Instructions:
- The player may refer to the selected country in various ways, including:
    - Talking about themselves or referring to being in the country: "Am I ...?", "Do I ...?" etc.
    - Using "it/this/that": "Is it ...?", "Does it ...?", "Is this ...?", "Is that ...?" etc.
    - Using "the country": "Is the country ...?", "Does the country ...?", "Is that country ...?" etc.
    - Using "here" or "there": "is here ...?", "is there ...?", etc.
    - Using short forms: "in ...?", "is ...?" etc.
    - In different languages.
- Always respond in English.
- The improved question should always use the "the country" version of the question.

### Output Format
Answer with JSON format and nothing else. 
Use the specific format:
{
  "question": "Improved question if question is valid",
  "explanation": "Explanation if question is not valid",    
  "valid": true | false
}

### Examples
User's Question: Is it in Europe?
Output: 
{
  "question": "Is the country located in Europe?",
  "valid": true
}

User's Question: in Europe
Output: 
{
  "question": "Is the country located in Europe?",
  "valid": true
}

User's Question: Tell me about its history
Output:
{
  "explanation": "This is not a True/False question.",
  "valid": false
}

User's Question: Is it seychelles?
{
  "question": "Is the country Seychelles?",
  "valid": true,
}

User's Question: Is this island/s country
{
  "question": "Is the country an island nation?",
  "valid": true
}

User's Question: "asdfghjkl"
{
  "explanation": "The input is gibberish and not a valid True/False question.",
  "valid": false
}
"""

    question_prompt = f"""User's Question: {question}"""

    prompts = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question_prompt},
    ]
    model = os.getenv("QUIZ_MODEL")

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=prompts,
        response_format={"type": "json_object"},
    )

    answer = response.choices[0].message.content

    try:
        answer_dict: dict = json.loads(answer)
    except json.JSONDecodeError:
        print(answer)
        raise

    return QuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        explanation=answer_dict.get("explanation", None),
    )


async def ask_question(
    question: QuestionEnhanced,
    day_country: CountrydleDay,
    user: User,
    session: AsyncSession,
) -> QuestionCreate:

    fragments, question_vector = await get_fragments_matching_question(
        question.question, "country_id", day_country.country_id, "countries", session
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    country: Country = await CountryRepository(session).get(day_country.country_id)

    system_prompt = f"""
You are an AI assistant in a game where players try to guess a country by asking True/False questions. 
Your task is to:
1. Receive a valid True/False question from the player.
2. Use the provided country and context to answer the question accurately.

Instructions:
- Base your answers primarily on the provided context. If the context does not contain enough information, use your general knowledge to provide the most accurate answer possible.
- If you cannot determine the answer even with general knowledge, set "answer" to null.
- Incorporate any relevant details from the provided context about the country into your explanations.
- If the question asks whether the country is a neighbor of itself or shares boreder with itself, answer "true".
- For any questions about events or information from April 2024 onwards, set "answer" to null.
- Explanations should be provided before the answer.
- Answer should be consistent with the explanation.

### Country to Guess: {country.name}
### Context: 
[...]
{context}
[...]

### Output Format
You are answering the question with your best knowledge.
Answer with JSON forma and nothing else. Use the specific format:
{{
    "explanation": "Your explanation for your answer."
    "answer": true | false | null,
}}
### 

### Examples of answers
Country: France. Question: Is your country known for its wines?
{{
    "explanation": "France is known for its Bordeaux, Champagne and many more!"
    "answer": true,
}}
Country: China. Question: Am I in Europe?
{{
    "explanation": "China is located in Asia.",
    "answer": false
}}
Country: Brazil. Question: Is the country's average annual rainfall over 2000 millimeters?
{{
    "explanation": "The question is too vague to answer correctly.",
    "answer": null
}}

Country: Germany. Question: Is the country a neighbor of Germany?
{{
    "explanation": "A country is always considered to be a neighbor of itself.",
    "answer": true
}}

Country: Japan. Question: Has the country hosted the 2025 World Expo?
{{
  "explanation": "I cannot provide information about events occurring after April 2024.",
  "answer": null
}}
"""
    question_prompt = f"""Question: {question.question}"""

    prompts = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question_prompt},
    ]
    model = os.getenv("QUIZ_MODEL")

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=prompts,
        response_format={"type": "json_object"},
    )

    answer = response.choices[0].message.content

    try:
        answer_dict = json.loads(answer)
    except json.JSONDecodeError:
        print(answer)
        raise

    question_create = QuestionCreate(
        user_id=user.id,
        day_id=day_country.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict["answer"],
        explanation=answer_dict["explanation"],
        context=context,
    )

    return question_create, question_vector


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

    prompts = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": guess_prompt},
    ]
    model = os.getenv("QUIZ_MODEL")

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=prompts,
        response_format={"type": "json_object"},
    )

    answer = response.choices[0].message.content

    try:
        answer_dict = json.loads(answer)
    except json.JSONDecodeError:
        print(answer)
        raise

    return answer_dict
