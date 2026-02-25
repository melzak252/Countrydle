import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Wojewodztwo, WojewodztwodleDay, User
from qdrant.utils import get_fragments_matching_question
from schemas.wojewodztwodle import (
    WojewodztwoQuestionCreate,
    WojewodztwoQuestionEnhanced,
)
from db.repositories.wojewodztwo import WojewodztwoRepository


async def enhance_question(question: str) -> WojewodztwoQuestionEnhanced:
    system_prompt = """
Jesteś asystentem AI w grze, w której gracze odgadują polskie województwo, zadając pytania Tak/Nie.
Twoim zadaniem jest:

1. Otrzymanie pytania użytkownika.
2. Zrozumienie znaczenia pytania użytkownika.
3. Określenie, czy jest to poprawne pytanie Tak/Nie dotyczące możliwego polskiego województwa.
4. Pytania o to, czy województwo jest konkretnym województwem (np. "Czy to Małopolskie?") są POPRAWNE.
5. Jeśli pytanie jest poprawne, ulepsz je, aby jego intencja była bardziej oczywista.
6. Jeśli pytanie nie jest poprawne, podaj wyjaśnienie, dlaczego nie jest ono poprawne.

Instrukcje:
- Gracz może odnosić się do wybranego województwa na różne sposoby, w tym:
    - Mówiąc o sobie lub odnosząc się do bycia w województwie: "Czy jestem ...?", "Czy mieszkam ...?" itp.
    - Używając "to/ten/tamten": "Czy to ...?", "Czy to województwo ...?" itp.
    - Używając "województwo": "Czy województwo ...?", "Czy to województwo ...?" itp.
    - Używając "tu" lub "tam": "czy tu jest ...?", "czy tam jest ...?" itp.
    - W różnych językach (głównie polskim lub angielskim).
- Zawsze odpowiadaj w języku polskim.
- Ulepszone pytanie musi zawsze mieć "województwo" jako podmiot zdania (np. "Czy województwo znajduje się na południu?").
- Sprawdź, czy pytanie ma sens i czy jest poprawnym zapytaniem o polskie województwo.

### Format wyjściowy
Odpowiedz w formacie JSON i niczym więcej.
Użyj określonego formatu:
{
  "question": "Ulepszone pytanie, jeśli jest poprawne",
  "explanation": "Wyjaśnienie, jeśli pytanie nie jest poprawne",
  "valid": true | false
}

### Przykłady
Pytanie użytkownika: Czy jest na południu?
Wyjście:
{
  "question": "Czy województwo znajduje się na południu?",
  "valid": true
}

Pytanie użytkownika: Czy to Małopolskie?
Wyjście:
{
  "question": "Czy województwo to Małopolskie?",
  "valid": true
}

Pytanie użytkownika: Opowiedz mi o jego historii
Wyjście:
{
  "explanation": "To nie jest pytanie typu Tak/Nie.",
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

    return WojewodztwoQuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        explanation=answer_dict.get("explanation", None),
    )


async def ask_question(
    question: WojewodztwoQuestionEnhanced,
    day_wojewodztwo: WojewodztwodleDay,
    user: User | None,
    session: AsyncSession,
) -> WojewodztwoQuestionCreate:

    fragments, question_vector = await get_fragments_matching_question(
        question.question,
        "wojewodztwo_id",
        day_wojewodztwo.wojewodztwo_id,
        "wojewodztwa",
        session,
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    wojewodztwo: Wojewodztwo = await WojewodztwoRepository(session).get(
        day_wojewodztwo.wojewodztwo_id
    )

    system_prompt = f"""
Jesteś asystentem AI w grze, w której gracze próbują odgadnąć polskie województwo, zadając pytania Tak/Nie.
Twoim zadaniem jest:
1. Otrzymanie poprawnego pytania Tak/Nie od gracza.
2. Użycie podanego województwa i kontekstu, aby dokładnie odpowiedzieć na pytanie.

Instrukcje:
- Opieraj swoje odpowiedzi głównie na dostarczonym kontekście. Jeśli kontekst nie zawiera wystarczających informacji, użyj swojej wiedzy ogólnej, aby udzielić jak najdokładniejszej odpowiedzi.
- Jeśli nie możesz ustalić odpowiedzi nawet przy użyciu wiedzy ogólnej, ustaw "answer" na null.
- Uwzględnij wszelkie istotne szczegóły z dostarczonego kontekstu dotyczące województwa w swoich wyjaśnieniach.
- Jeśli pytanie dotyczy tego, czy województwo sąsiaduje z [X], a województwem DO ODGADNIĘCIA JEST [X], odpowiedz "true". Traktuj województwo jako sąsiadujące same ze sobą na potrzeby tej gry.
- Wyjaśnienia powinny być podane przed odpowiedzią.
- Odpowiedź powinna być spójna z wyjaśnieniem.
- Zawsze odpowiadaj w języku polskim.

### Województwo do odgadnięcia: {wojewodztwo.nazwa}
### Kontekst: 
[...]
{context}
[...]

### Format wyjściowy
Odpowiedz w formacie JSON i niczym więcej. Użyj określonego formatu:
{{
    "explanation": "Twoje wyjaśnienie odpowiedzi.",
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

    question_create = WojewodztwoQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_wojewodztwo.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict["answer"],
        explanation=answer_dict["explanation"],
        context=context,
    )

    return question_create, question_vector
