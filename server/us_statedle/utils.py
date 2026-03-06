import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import USState, USStatedleDay, User
from qdrant.utils import get_fragments_matching_question
import qdrant
from schemas.us_statedle import USStateQuestionCreate, USStateQuestionEnhanced
from db.repositories.us_state import USStateRepository


async def enhance_question(question: str) -> USStateQuestionEnhanced:
    system_prompt = """
You are an AI assistant for a game where players guess a US State by asking True/False questions. 
Your task is to:

1. Receive a user's question.
2. Retrieve the meaning of the user's question.
3. Determine if it is a valid True/False question about a possible US State.
4. Questions asking if the state is a specific state (e.g., "Is it Pennsylvania?") are VALID.
5. If it's valid, then:
    - Simplify the question to its most basic form while keeping the user's meaning.
    - Define the "intent" of the question (e.g., "Checking geographic location", "Checking state history").
    - List the "required_info" needed to answer this question (e.g., "The region where the state is located", "List of bordering states").
6. If it's not valid, then provide an explanation why the question is not valid.

Instructions:
- The player may refer to the selected state in various ways, including:
    - Talking about themselves or referring to being in the state: "Am I ...?", "Do I ...?" etc.
    - Using "it/this/that": "Is it ...?", "Does it ...?", "Is this ...?", "Is that ...?" etc.
    - Using "the state": "Is the state ...?", "Does the state ...?", etc.
    - Using "here" or "there": "is here ...?", "is there ...?", etc.
    - Using short forms: "in ...?", "is ...?" etc.
    - In different languages (e.g., Polish, Spanish, French).
- Always respond in English.
- The improved question must always have "the state" as the subject of the sentence.
- Check if the question makes sense and is a valid query about a US state.

### Output Format
Answer with JSON format and nothing else. 
Use the specific format:
{
  "question": "Simplified question if valid",
  "intent": "Intent of the question if valid",
  "required_info": "Information needed to answer if valid",
  "explanation": "Explanation if question is not valid",    
  "valid": true | false
}

### Examples
User's Question: Is it in the South?
Output: 
{
  "question": "Is the state located in the South?",
  "intent": "Checking geographic location",
  "required_info": "The region where the state is located",
  "valid": true
}

User's Question: Is it Pennsylvania?
Output: 
{
  "question": "Is the state Pennsylvania?",
  "intent": "Checking specific state name",
  "required_info": "The name of the state",
  "valid": true
}

User's Question: Is it California, Texas or Florida?
Output: {"question": "Is the state one of the following: California, Texas, or Florida?", "intent": "Checking against a list of specific states", "required_info": "The name of the state", "valid": true, "explanation": null}

User's Question: Tell me about its history
Output:
{
  "explanation": "This is not a True/False question.",
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

    return USStateQuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation") or ("No explanation provided." if not answer_dict["valid"] else None),
    )



async def ask_question(
    question: USStateQuestionEnhanced,
    day_state: USStatedleDay,
    user: User | None,
    session: AsyncSession,
) -> Tuple[USStateQuestionCreate, List[float]]:


    fragments, question_vector = await get_fragments_matching_question(
        question.question, "us_state_id", day_state.us_state_id, "us_states", session, limit=qdrant.US_STATEDLE_CONTEXT_LIMIT
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    state: USState = await USStateRepository(session).get(day_state.us_state_id)

    system_prompt = f"""
You are an AI assistant in a game where players try to guess a US State by asking True/False questions. 
Your task is to:
1. Receive a valid True/False question from the player.
2. Use the provided state and context to answer the question accurately.

Instructions:
- Base your answers primarily on the provided context. If the context does not contain enough information, use your general knowledge to provide the most accurate answer possible.
- If you cannot determine the answer even with general knowledge, set "answer" to null.
- Incorporate any relevant details from the provided context about the state into your explanations.
- If the question asks if the state borders/neighbors [X], and the secret state IS [X], answer "true". Treat a state as bordering itself for the purpose of this game.
- Explanations should be provided before the answer.
- Answer should be consistent with the explanation.

### State to Guess: {state.name}
### Question Intent: {question.intent}
### Required Information: {question.required_info}
### Context: 
[...]
{context}
[...]

### Output Format
Answer with JSON format and nothing else. Use the specific format:
{{
    "explanation": "Your explanation for your answer.",
    "answer": true | false | null
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

    question_create = USStateQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_state.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "No explanation provided.",
        context=context,
    )

    return question_create, question_vector
