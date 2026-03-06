import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Wojewodztwo, WojewodztwodleDay, User
from qdrant.utils import get_fragments_matching_question
import qdrant
from schemas.wojewodztwodle import (
    WojewodztwoQuestionCreate,
    WojewodztwoQuestionEnhanced,
)
from db.repositories.wojewodztwo import WojewodztwoRepository


async def enhance_question(question: str) -> WojewodztwoQuestionEnhanced:
    system_prompt = """
Jesteś ekspertem ds. analizy pytań w grze w zgadywanie polskich województw. Twoim celem jest przetworzenie pytań użytkowników na ustrukturyzowany format, który ułatwia dokładne wyszukiwanie informacji.

### Twoje główne obowiązki:
1. **Analiza semantyczna**: Zrozum prawdziwą intencję pytania użytkownika, niezależnie od języka czy sformułowania.
2. **Walidacja**: Określ, czy dane wejściowe są poprawnym pytaniem Tak/Nie dotyczącym atrybutów województwa (geografia, historia, symbole, itp.).
3. **Uproszczenie**: Przepisz pytanie na jasne, atomowe i standaryzowane zdanie w języku polskim, w którym "województwo" jest podmiotem.
4. **Mapowanie intencji i informacji**: Wyraźnie zdefiniuj, co pytanie próbuje zweryfikować i jakie konkretne punkty danych są potrzebne do odpowiedzi.

### Wytyczne:
- **Podmiot**: Uproszczone pytanie MUSI zaczynać się od słowa "województwo" lub skupiać się na nim (np. "Czy województwo...", "Czy w województwie...").
- **Atomowość**: Jeśli pytanie jest złożone, skup się na głównym zapytaniu.
- **Wymagane informacje**: Bądź precyzyjny co do potrzebnych danych (np. "Lista miast na prawach powiatu", "Sąsiednie województwa", "Powierzchnia").

### Format wyjściowy (Strict JSON):
{
  "question": "Uproszczone pytanie T/N po polsku",
  "intent": "Krótki opis tego, co jest sprawdzane",
  "required_info": "Konkretne punkty danych potrzebne z bazy danych",
  "valid": true,
  "explanation": null
}
-- LUB jeśli niepoprawne --
{
  "question": null,
  "intent": null,
  "required_info": null,
  "valid": false,
  "explanation": "Jasny powód, dla którego pytanie jest nieprawidłowe (np. to nie jest pytanie T/N, bełkot)"
}

### Przykłady:
User: "Czy graniczy z morzem?"
Output: {"question": "Czy województwo ma dostęp do Morza Bałtyckiego?", "intent": "Sprawdzanie dostępu do morza", "required_info": "Położenie geograficzne i granice morskie województwa", "valid": true, "explanation": null}

User: "Czy to małopolskie?"
Output: {"question": "Czy województwo to małopolskie?", "intent": "Sprawdzanie konkretnej nazwy województwa", "required_info": "Nazwa województwa", "valid": true, "explanation": null}

User: "Czy to małopolskie, śląskie czy opolskie?"
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "To jest pytanie wielokrotnego wyboru. Proszę zadać pojedyncze pytanie Tak/Nie."}

User: "Ile ma mieszkańców?"
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "To jest pytanie otwarte o liczbę, a nie pytanie Tak/Nie."}
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
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation") or ("Brak wyjaśnienia." if not answer_dict["valid"] else None),
    )



async def ask_question(
    question: WojewodztwoQuestionEnhanced,
    day_wojewodztwo: WojewodztwodleDay,
    user: User | None,
    session: AsyncSession,
) -> Tuple[WojewodztwoQuestionCreate, List[float]]:

    fragments, question_vector = await get_fragments_matching_question(
        question.question,
        "wojewodztwo_id",
        day_wojewodztwo.wojewodztwo_id,
        "wojewodztwa",
        session,
        limit=qdrant.WOJEWODZTWDLE_CONTEXT_LIMIT
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    wojewodztwo: Wojewodztwo = await WojewodztwoRepository(session).get(
        day_wojewodztwo.wojewodztwo_id
    )

    system_prompt = f"""
Jesteś 'Mistrzem Gry' w Wojewodztwodle. Twoim zadaniem jest odpowiedzieć na pytanie Tak/Nie dotyczące konkretnego polskiego województwa na podstawie dostarczonego kontekstu i Twojej wiedzy ogólnej.

### Docelowe województwo: {wojewodztwo.nazwa}
### Intencja pytania: {question.intent}
### Wymagane informacje: {question.required_info}

### Fragmenty kontekstu:
{context}

### Twoje instrukcje:
1. **Analiza kontekstu**: Szukaj konkretnych faktów w dostarczonym kontekście, które bezpośrednio potwierdzają lub zaprzeczają pytaniu.
2. **Wiedza ogólna**: Jeśli w kontekście brakuje konkretnego faktu, użyj swojej wiedzy wewnętrznej o geografii, historii i administracji Polski, aby udzielić dokładnej odpowiedzi.
3. **Niepewność**: Jeśli odpowiedzi nie można ustalić z wysoką pewnością, ustaw `answer` na `null`.
4. **Zasada sąsiedztwa**: Jeśli padnie pytanie, czy województwo sąsiaduje samo ze sobą, odpowiedź brzmi ZAWSZE `true`.
5. **Wyjaśnienie**: Napisz zwięzłe, rzeczowe wyjaśnienie w języku polskim, które logicznie prowadzi do odpowiedzi Tak/Nie/Null.

### Format wyjściowy (Strict JSON):
{{
    "explanation": "Zwięzłe uzasadnienie faktyczne.",
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
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "Brak wyjaśnienia.",
        context=context,
    )

    return question_create, question_vector
