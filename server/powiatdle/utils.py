import os
import json
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Powiat, PowiatdleDay, User
from qdrant.utils import get_fragments_matching_question
import qdrant
from schemas.powiatdle import PowiatQuestionCreate, PowiatQuestionEnhanced
from db.repositories.powiatdle import PowiatRepository


async def enhance_question(question: str) -> PowiatQuestionEnhanced:
    system_prompt = """
Jesteś ekspertem ds. analizy pytań w grze w zgadywanie polskich powiatów. Twoim celem jest przetworzenie pytań użytkowników na ustrukturyzowany format, który ułatwia dokładne wyszukiwanie informacji.

### Twoje główne obowiązki:
1. **Analiza semantyczna**: Zrozum prawdziwą intencję pytania użytkownika, niezależnie od języka (polski/angielski) czy sformułowania.
2. **Walidacja**: Określ, czy dane wejściowe są poprawnym pytaniem Tak/Nie dotyczącym atrybutów powiatu (geografia, przynależność do województwa, symbole, itp.).
3. **Uproszczenie**: Przepisz pytanie na jasne, atomowe i standaryzowane zdanie w języku polskim, w którym "powiat" jest podmiotem.
4. **Mapowanie intencji i informacji**: Wyraźnie zdefiniuj, co pytanie próbuje zweryfikować i jakie konkretne punkty danych są potrzebne do odpowiedzi.

### Wytyczne:
- **Podmiot**: Uproszczone pytanie MUSI zaczynać się od słowa "powiat" lub skupiać się na nim (np. "Czy powiat...", "Czy w powiecie...").
- **Atomowość**: Jeśli pytanie jest złożone, skup się na głównym zapytaniu.
- **Wymagane informacje**: Bądź precyzyjny co do potrzebnych danych (np. "Lista powiatów sąsiadujących", "Nazwa województwa", "Liczba ludności").

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
User: "Czy leży w małopolskim?"
Output: {"question": "Czy powiat znajduje się w województwie małopolskim?", "intent": "Sprawdzanie przynależności administracyjnej", "required_info": "Nazwa województwa, w którym leży powiat", "valid": true, "explanation": null}

User: "Czy to powiat krakowski?"
Output: {"question": "Czy powiat to powiat krakowski?", "intent": "Sprawdzanie konkretnej nazwy powiatu", "required_info": "Nazwa powiatu", "valid": true, "explanation": null}

User: "Czy to powiat krakowski, wielicki czy poznański?"
Output: {"question": "Czy powiat to jeden z wymienionych: krakowski, wielicki lub poznański?", "intent": "Sprawdzanie nazwy powiatu względem listy", "required_info": "Nazwa powiatu", "valid": true, "explanation": null}

User: "Powiedz mi coś o nim."
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "To jest prośba otwarta, a nie pytanie Tak/Nie."}
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
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation") or ("Brak wyjaśnienia." if not answer_dict["valid"] else None),
    )



async def ask_question(
    question: PowiatQuestionEnhanced,
    day_powiat: PowiatdleDay,
    user: User | None,
    session: AsyncSession,
) -> Tuple[PowiatQuestionCreate, List[float]]:

    fragments, question_vector = await get_fragments_matching_question(
        question.question, "powiat_id", day_powiat.powiat_id, "powiaty", session, limit=qdrant.POWIATDLE_CONTEXT_LIMIT
    )
    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments)
    powiat: Powiat = await PowiatRepository(session).get(day_powiat.powiat_id)

    system_prompt = f"""
Jesteś 'Mistrzem Gry' w Powiatdle. Twoim zadaniem jest odpowiedzieć na pytanie Tak/Nie dotyczące konkretnego polskiego powiatu na podstawie dostarczonego kontekstu i Twojej wiedzy ogólnej.

### Docelowy powiat: {powiat.nazwa}
### Intencja pytania: {question.intent}
### Wymagane informacje: {question.required_info}

### Fragmenty kontekstu:
{context}

### Twoje instrukcje:
1. **Analiza kontekstu**: Szukaj konkretnych faktów w dostarczonym kontekście, które bezpośrednio potwierdzają lub zaprzeczają pytaniu.
2. **Wiedza ogólna**: Jeśli w kontekście brakuje konkretnego faktu, użyj swojej wiedzy wewnętrznej o geografii i administracji Polski, aby udzielić dokładnej odpowiedzi.
3. **Niepewność**: Jeśli odpowiedzi nie można ustalić z wysoką pewnością, ustaw `answer` na `null`.
4. **Zasada sąsiedztwa**: Jeśli padnie pytanie, czy powiat sąsiaduje sam ze sobą, odpowiedź brzmi ZAWSZE `true`.
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

    question_create = PowiatQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_powiat.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "Brak wyjaśnienia.",
        context=context,
    )

    return question_create, question_vector
