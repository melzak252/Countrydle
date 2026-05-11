import os
import json
from typing import List, Tuple
from openai import OpenAI

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Powiat, PowiatdleDay, User
from qdrant.utils import get_fragments_matching_question
import qdrant
from schemas.powiatdle import PowiatQuestionCreate, PowiatQuestionEnhanced
from db.repositories.powiatdle import PowiatRepository
from local_kb_question import LocalModeConfig, QuestionPlan, analyze_question, execute_plan, ROOT_DIR


LOCAL_CONFIG = LocalModeConfig(
    mode_name="Powiatdle",
    entity_label="polski powiat lub miasto na prawach powiatu",
    target_entity="target_powiat",
    db_path=ROOT_DIR / "data" / "powiat_facts.sqlite",
    table="powiats",
    name_column="name",
    scalar_relations={
        "name": "name", "voivodeship": "voivodeship", "is_city_county": "is_city_county", "seat": "seat",
        "population": "population", "area": "area_km2", "population_density": "population_density",
        "urbanization": "urbanization_percent", "gmina_count": "gmina_count",
        "urban_gmina_count": "urban_gmina_count", "rural_gmina_count": "rural_gmina_count",
        "urban_rural_gmina_count": "urban_rural_gmina_count",
    },
    list_relations={
        "borders_powiat": ("powiat_borders_powiats", "border_powiat_name"),
        "borders_voivodeship": ("powiat_borders_voivodeships", "voivodeship"),
        "borders_country": ("powiat_borders_countries", "country_name"),
        "registration_plates": ("powiat_registration_plates", "plate_code"),
        "major_rivers": ("powiat_major_rivers", "river_name"),
        "major_roads": ("powiat_major_roads", "road_name"),
        "landform_regions": ("powiat_landform_regions", "region_name"),
        "regional_labels": ("powiat_landform_regions", "region_name"),
    },
    supported_relations=[
        "name", "voivodeship", "is_city_county", "seat", "borders_powiat", "borders_voivodeship",
        "borders_country", "population", "area", "population_density", "urbanization", "registration_plates",
        "gmina_count", "urban_gmina_count", "rural_gmina_count", "urban_rural_gmina_count",
        "major_rivers", "major_roads", "landform_regions", "regional_labels",
    ],
    mode_notes=(
        "Use regional_labels for broad, historical, cultural, or physical-geography regions "
        "of a powiat, such as Mazowsze, Podlasie, Kujawy, Małopolska, Śląsk, Kaszuby, "
        "Roztocze, Polesie, or named mountain/upland/lowland/lake-district regions. "
        "The relation is list-valued, so use contains/exists rather than equals."
    ),
)


def question_enhanced_from_plan(original_question: str, plan: QuestionPlan) -> PowiatQuestionEnhanced:
    return PowiatQuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(question: str, day_powiat: PowiatdleDay, user: User | None, session: AsyncSession):
    powiat: Powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    plan = analyze_question(question, LOCAL_CONFIG)
    if not plan.valid:
        return PowiatQuestionCreate(
            user_id=user.id if user else None,
            day_id=day_powiat.id,
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
        answer = execute_plan(LOCAL_CONFIG, powiat.nazwa, plan)
    except Exception:
        return None, plan
    if answer is None:
        return None, plan
    return PowiatQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_powiat.id,
        original_question=question,
        question=answer.question,
        valid=True,
        answer=answer.answer,
        explanation=answer.explanation,
        context="local_kb:" + ",".join(answer.relations),
        intent=plan.explanation,
        required_info=", ".join(answer.relations),
    ), plan


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
- **Odniesienie do encji**: Użytkownik może odnosić się do docelowego powiatu na różne sposoby:
    - Mówiąc o sobie: "Czy jestem...?", "Czy leżę...?", "Czy mam...?"
    - Używając "on/to": "Czy on...", "Czy to...", "Czy jest on..."
    - Używając "powiat": "Czy powiat...", "Czy w powiecie..."
- **Atomowość**: Jeśli pytanie jest złożone, skup się na głównym zapytaniu.

- **Wymagane informacje**: Bądź precyzyjny co do potrzebnych danych (np. "Lista powiatów sąsiadujących", "Nazwa województwa", "Liczba ludności").

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
User: "Czy leży w małopolskim?"
Output: {"question": "Czy powiat znajduje się w województwie małopolskim?", "intent": "Użytkownik chce zweryfikować przynależność administracyjną powiatu do konkretnego województwa (małopolskiego).", "required_info": "Nazwa województwa, w którym leży powiat", "valid": true, "explanation": null}

User: "Czy to powiat krakowski?"
Output: {"question": "Czy powiat to powiat krakowski?", "intent": "Użytkownik próbuje bezpośrednio odgadnąć nazwę powiatu, sprawdzając czy jest to powiat krakowski.", "required_info": "Nazwa powiatu", "valid": true, "explanation": null}

User: "Czy to powiat krakowski, wielicki czy poznański?"
Output: {"question": "Czy powiat to jeden z wymienionych: krakowski, wielicki lub poznański?", "intent": "Użytkownik podaje listę potencjalnych nazw powiatów i chce wiedzieć, czy docelowy powiat znajduje się na tej liście.", "required_info": "Nazwa powiatu", "valid": true, "explanation": null}

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
        temperature=0.0,
        seed=42,
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
4. **Zasada sąsiedztwa**: Jeśli padnie pytanie, czy powiat sąsiaduje z [X], a docelowym powiatem JEST [X], odpowiedź brzmi ZAWSZE `true`. Traktuj powiat jako sąsiadujący sam ze sobą na potrzeby tej gry.
5. **Informacyjne Wyjaśnienia**: Napisz `explanation` jako informację o powiecie, która odpowiada na pytanie i podaje szczegóły. Unikaj zaczynania od 'Tak' lub 'Nie' oraz prostego powtarzania odpowiedzi. Wyjaśnienie powinno być zdaniem informacyjnym o powiecie, które uzasadnia odpowiedź Tak/Nie (np. zamiast 'Tak, powiat leży w małopolskim', użyj 'Powiat {powiat.nazwa} znajduje się w województwie małopolskim, w południowej części kraju.').
6. **Obsługa logicznego 'LUB' i list**: Jeśli pytanie zawiera słowo 'lub' lub podaje listę opcji (np. 'Czy to powiat krakowski lub wielicki?'), odpowiedź brzmi `true`, jeśli docelowy powiat pasuje do **przynajmniej jednej** z tych opcji.

7. **Perspektywa użytkownika**: Jeśli użytkownik odnosi się do siebie jako do powiatu (np. "Czy jestem w małopolskim?"), powinieneś nadal odpowiadać o powiecie w trzeciej osobie (np. "Powiat {powiat.nazwa} leży w województwie małopolskim"), aby zachować rzeczowy i informacyjny ton.

### Format wyjściowy (Strict JSON):
{{
    "explanation": "Informacyjne stwierdzenie faktyczne o powiecie.",
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
