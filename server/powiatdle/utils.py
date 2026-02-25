import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Powiat, PowiatdleDay, User
from qdrant.utils import get_fragments_matching_question
from schemas.powiatdle import PowiatQuestionCreate, PowiatQuestionEnhanced
from db.repositories.powiatdle import PowiatRepository


async def enhance_question(question: str) -> PowiatQuestionEnhanced:
    system_prompt = """
Jesteś asystentem AI w grze, w której gracze odgadują polski powiat, zadając pytania Tak/Nie.
Twoim zadaniem jest:

1. Otrzymanie pytania użytkownika.
2. Zrozumienie znaczenia pytania użytkownika.
3. Określenie, czy jest to poprawne pytanie Tak/Nie dotyczące możliwego polskiego powiatu.
4. Pytania o to, czy powiat jest konkretnym powiatem (np. "Czy to powiat krakowski?") są POPRAWNE.
5. Jeśli pytanie jest poprawne, ulepsz je, aby jego intencja była bardziej oczywista.
6. Jeśli pytanie nie jest poprawne, podaj wyjaśnienie, dlaczego nie jest ono poprawne.

Instrukcje:
- Gracz może odnosić się do wybranego powiatu na różne sposoby, w tym:
    - Mówiąc o sobie lub odnosząc się do bycia w powiecie: "Czy jestem ...?", "Czy mieszkam ...?" itp.
    - Używając "to/ten/tamten": "Czy to ...?", "Czy ten powiat ...?" itp.
    - Używając "powiat": "Czy powiat ...?", "Czy ten powiat ...?" itp.
    - Używając "tu" lub "tam": "czy tu jest ...?", "czy tam jest ...?" itp.
    - W różnych językach (głównie polskim lub angielskim).
- Zawsze odpowiadaj w języku polskim.
- Ulepszone pytanie musi zawsze mieć "powiat" jako podmiot zdania (np. "Czy powiat znajduje się na południu?").
- Sprawdź, czy pytanie ma sens i czy jest poprawnym zapytaniem o polski powiat.

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
  "question": "Czy powiat znajduje się na południu?",
  "valid": true
}

Pytanie użytkownika: Czy to powiat krakowski?
Wyjście:
{
  "question": "Czy powiat to powiat krakowski?",
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

    return PowiatQuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        explanation=answer_dict.get("explanation", None),
    )


async def ask_question(
    question: PowiatQuestionEnhanced,
    day_powiat: PowiatdleDay,
    user: User | None,
    session: AsyncSession,
) -> PowiatQuestionCreate:

    fragments, question_vector = await get_fragments_matching_question(
        question.question, "powiat_id", day_powiat.powiat_id, "powiaty", session
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    powiat: Powiat = await PowiatRepository(session).get(day_powiat.powiat_id)

    system_prompt = f"""
Jesteś asystentem AI w grze, w której gracze próbują odgadnąć polski powiat, zadając pytania Tak/Nie.
Twoim zadaniem jest:
1. Otrzymanie poprawnego pytania Tak/Nie od gracza.
2. Użycie podanego powiatu i kontekstu, aby dokładnie odpowiedzieć na pytanie.

Instrukcje:
- Opieraj swoje odpowiedzi głównie na dostarczonym kontekście. Jeśli kontekst nie zawiera wystarczających informacji, użyj swojej wiedzy ogólnej, aby udzielić jak najdokładniejszej odpowiedzi.
- Jeśli nie możesz ustalić odpowiedzi nawet przy użyciu wiedzy ogólnej, ustaw "answer" na null.
- Uwzględnij wszelkie istotne szczegóły z dostarczonego kontekstu dotyczące powiatu w swoich wyjaśnieniach.
- Jeśli pytanie dotyczy tego, czy powiat sąsiaduje z [X], a powiatem DO ODGADNIĘCIA JEST [X], odpowiedz "true". Traktuj powiat jako sąsiadujący sam ze sobą na potrzeby tej gry.
- Wyjaśnienia powinny być podane przed odpowiedzią.
- Odpowiedź powinna być spójna z wyjaśnieniem.
- Zawsze odpowiadaj w języku polskim.

### Powiat do odgadnięcia: {powiat.nazwa}
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

    question_create = PowiatQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_powiat.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict["answer"],
        explanation=answer_dict["explanation"],
        context=context,
    )

    return question_create, question_vector
