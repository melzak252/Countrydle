import os
import json
from typing import List, Tuple
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
from local_kb_question import LocalModeConfig, QuestionPlan, analyze_question, execute_plan, ROOT_DIR


LOCAL_CONFIG = LocalModeConfig(
    mode_name="Wojewodztwodle",
    entity_label="polskie województwo",
    target_entity="target_voivodeship",
    db_path=ROOT_DIR / "data" / "voivodeship_facts.sqlite",
    table="voivodeships",
    name_column="name",
    scalar_relations={
        "name": "name", "seat": "seat", "macroregion": "macroregion", "is_coastal": "is_coastal",
        "population": "population", "area": "area_km2", "latitude": "latitude", "longitude": "longitude",
        "urbanization": "urbanization_percent", "powiat_count": "powiat_count", "city_count": "city_count",
        "city_count_with_powiat_rights": "city_count_with_powiat_rights",
    },
    list_relations={
        "borders_voivodeship": ("voivodeship_borders_voivodeships", "border_voivodeship_name"),
        "borders_country": ("voivodeship_borders_countries", "country_name"),
        "water_access": ("voivodeship_water_access", "water_body"),
        "major_rivers": ("voivodeship_major_rivers", "river_name"),
        "mountain_ranges": ("voivodeship_mountain_ranges", "range_name"),
        "historical_region": ("voivodeship_historical_regions", "region_name"),
        "landform_regions": ("voivodeship_landform_regions", "region_name"),
        "regional_labels": ("voivodeship_regional_labels", "label"),
    },
    supported_relations=[
        "name", "seat", "macroregion", "borders_voivodeship", "borders_country", "water_access",
        "is_coastal", "population", "area", "latitude", "longitude", "major_rivers", "mountain_ranges",
        "historical_region", "urbanization", "powiat_count", "city_count", "city_count_with_powiat_rights",
        "landform_regions", "regional_labels",
    ],
    mode_notes=(
        "For informal location labels such as 'zachodnia Polska', 'wschodnia Polska', "
        "'północna Polska', 'południowa Polska', 'centralna Polska', 'nadmorska Polska', "
        "or historical/common areas such as Śląsk, Małopolska, Pomorze, Mazury, Podlasie, "
        "prefer relation regional_labels. Use macroregion only for exact broad macroregion wording."
    ),
)


def question_enhanced_from_plan(original_question: str, plan: QuestionPlan) -> WojewodztwoQuestionEnhanced:
    return WojewodztwoQuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(question: str, day_wojewodztwo: WojewodztwodleDay, user: User | None, session: AsyncSession):
    wojewodztwo: Wojewodztwo = await WojewodztwoRepository(session).get(day_wojewodztwo.wojewodztwo_id)
    plan = analyze_question(question, LOCAL_CONFIG)
    if not plan.valid:
        return WojewodztwoQuestionCreate(
            user_id=user.id if user else None,
            day_id=day_wojewodztwo.id,
            original_question=question,
            question=plan.improved_question,
            valid=False,
            answer=None,
            explanation=plan.explanation or plan.fallback_reason or "Niepoprawne pytanie.",
            context="local_planner:invalid",
            intent=plan.explanation,
            required_info=plan.fallback_reason,
        ), plan
    try:
        answer = execute_plan(LOCAL_CONFIG, wojewodztwo.nazwa, plan)
    except Exception:
        return None, plan
    if answer is None:
        return None, plan
    return WojewodztwoQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_wojewodztwo.id,
        original_question=question,
        question=answer.question,
        valid=True,
        answer=answer.answer,
        explanation=answer.explanation,
        context="local_kb:" + ",".join(answer.relations),
        intent=plan.explanation,
        required_info=", ".join(answer.relations),
    ), plan


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
- **Odniesienie do encji**: Użytkownik może odnosić się do docelowego województwa na różne sposoby:
    - Mówiąc o sobie: "Czy jestem...?", "Czy leżę...?", "Czy mam...?"
    - Używając "ono/to": "Czy ono...", "Czy to...", "Czy jest ono..."
    - Używając "województwo": "Czy województwo...", "Czy w województwie..."
- **Atomowość**: Jeśli pytanie jest złożone, skup się na głównym zapytaniu.

- **Wymagane informacje**: Bądź precyzyjny co do potrzebnych danych (np. "Lista miast na prawach powiatu", "Sąsiednie województwa", "Powierzchnia").

### Format wyjściowy (Strict JSON):
{
  "question": "Uproszczone pytanie T/N po polsku",
  "intent": "Szczegółowy opis intencji użytkownika i tego, co próbuje on ustalić",
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
Output: {"question": "Czy województwo ma dostęp do Morza Bałtyckiego?", "intent": "Użytkownik chce zweryfikować, czy docelowe województwo jest położone nad Morzem Bałtyckim.", "required_info": "Położenie geograficzne i granice morskie województwa", "valid": true, "explanation": null}

User: "Czy to małopolskie?"
Output: {"question": "Czy województwo to małopolskie?", "intent": "Użytkownik próbuje bezpośrednio odgadnąć nazwę województwa, sprawdzając czy jest to województwo małopolskie.", "required_info": "Nazwa województwa", "valid": true, "explanation": null}

User: "Czy to małopolskie, śląskie czy opolskie?"
Output: {"question": "Czy województwo to jedno z wymienionych: małopolskie, śląskie lub opolskie?", "intent": "Użytkownik podaje listę potencjalnych nazw województw i chce wiedzieć, czy docelowe województwo znajduje się na tej liście.", "required_info": "Nazwa województwa", "valid": true, "explanation": null}

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
        temperature=0.0,
        seed=42,
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
4. **Zasada sąsiedztwa**: Jeśli padnie pytanie, czy województwo sąsiaduje z [X], a docelowym województwem JEST [X], odpowiedź brzmi ZAWSZE `true`. Traktuj województwo jako sąsiadujące samo ze sobą na potrzeby tej gry.
5. **Informacyjne Wyjaśnienia**: Napisz `explanation` jako informację o województwie, która odpowiada na pytanie i podaje szczegóły. Unikaj zaczynania od 'Tak' lub 'Nie' oraz prostego powtarzania odpowiedzi. Wyjaśnienie powinno być zdaniem informacyjnym o województwie, które uzasadnia odpowiedź Tak/Nie (np. zamiast 'Tak, województwo leży nad morzem', użyj 'Województwo {wojewodztwo.nazwa} jest położone w północnej części Polski i posiada szeroki dostęp do Morza Bałtyckiego.').
6. **Obsługa logicznego 'LUB' i list**: Jeśli pytanie zawiera słowo 'lub' lub podaje listę opcji (np. 'Czy to małopolskie lub śląskie?'), odpowiedź brzmi `true`, jeśli docelowe województwo pasuje do **przynajmniej jednej** z tych opcji.

7. **Perspektywa użytkownika**: Jeśli użytkownik odnosi się do siebie jako do województwa (np. "Czy jestem w północnej Polsce?"), powinieneś nadal odpowiadać o województwie w trzeciej osobie (np. "Województwo {wojewodztwo.nazwa} leży w północnej części Polski"), aby zachować rzeczowy i informacyjny ton.

### Format wyjściowy (Strict JSON):
{{
    "explanation": "Informacyjne stwierdzenie faktyczne o województwie.",
    "answer": true | false | null
}}
"""


    question_prompt = f"""Oryginalne pytanie użytkownika: {question.original_question}
Uproszczone pytanie: {question.question}"""


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
        temperature=0.0,
        seed=42,
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
