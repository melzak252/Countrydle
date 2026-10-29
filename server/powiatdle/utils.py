import asyncio
import time
import qdrant
from typing import List, Tuple
from utils.ai_clients import gemini_json

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Powiat, PowiatdleDay, User
from schemas.powiatdle import PowiatQuestionCreate, PowiatQuestionEnhanced
from db.repositories.powiatdle import PowiatRepository
from local_kb_question import LocalModeConfig, QuestionPlan, analyze_question, execute_plan, ROOT_DIR
from utils.explanation_sanitizer import sanitize_explanation_for_player

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
        "urban_rural_gmina_count": "urban_rural_gmina_count",
        "latitude": "latitude", "longitude": "longitude",
    },
    list_relations={
        "borders_powiat": ("powiat_borders_powiats", "border_powiat_name"),
        "borders_voivodeship": ("powiat_borders_voivodeships", "voivodeship"),
        "borders_country": ("powiat_borders_countries", "country_name"),
        "registration_plates": ("powiat_registration_plates", "plate_code"),
        "major_rivers": ("powiat_major_rivers", "river_name"),
        "major_roads": ("powiat_major_roads", "road_name"),
        "water_access": ("powiat_water_access", "water_name"),
        "landform_regions": ("powiat_landform_regions", "region_name"),
        "regional_labels": ("powiat_landform_regions", "region_name"),
        "historical_regions": ("powiat_historical_regions", "region_name"),
        "historical_partitions": ("powiat_historical_partitions", "partition_name"),
        "national_parks": ("powiat_national_parks", "park_name"),
        "major_lakes": ("powiat_lakes", "lake_name"),
        "lakes": ("powiat_lakes", "lake_name"),
        "unesco_sites": ("powiat_unesco_sites", "site_name"),
        "health_resorts": ("powiat_health_resorts", "resort_name"),
    },
    entity_list_relations=frozenset({"borders_powiat"}),
    supported_relations=[
        "name", "voivodeship", "is_city_county", "seat", "borders_powiat", "borders_voivodeship",
        "borders_country", "population", "area", "population_density", "urbanization", "registration_plates",
        "gmina_count", "urban_gmina_count", "rural_gmina_count", "urban_rural_gmina_count",
        "major_rivers", "major_roads", "water_access", "landform_regions", "regional_labels",
        "historical_regions", "historical_partitions", "latitude", "longitude",
        "national_parks", "major_lakes", "lakes", "unesco_sites", "health_resorts",
    ],
    mode_notes=(
        "Relative cardinal directions comparing position to another city or county (e.g. 'na zachód od Warszawy', "
        "'na wschód od Krakowa', 'na północ od Wrocławia', 'na południe od Poznania') are supported: use "
        "operator west_of / east_of comparing relation longitude, or north_of / south_of comparing relation latitude "
        "with the reference city/county name as right operand entity.\n"
        "Historical lands/regions (Małopolska, Wielkopolska, Śląsk, Mazowsze, Pomorze, Warmia, Mazury, Kujawy, Podlasie, Galicja) "
        "use contains_exact on relation historical_regions (or regional_labels).\n"
        "Historical partitions (Zabór rosyjski, Zabór pruski, Zabór austriacki, Ziemie Odzyskane) "
        "use contains_exact on relation historical_partitions.\n"
        "national_parks records national parks (e.g. 'Czy na terenie powiatu znajduje się park narodowy?' uses exists on national_parks; specific park uses contains_exact or contains_partial on national_parks).\n"
        "major_lakes / lakes records major lakes and reservoirs (e.g. Śniardwy, Mamry, Solina, Gopło, Hańcza, Morskie Oko; uses exists or contains_exact on major_lakes).\n"
        "unesco_sites records UNESCO World Heritage sites (e.g. 'Czy w powiecie znajduje się obiekt z listy UNESCO?' uses exists on unesco_sites; specific site uses contains_exact or contains_partial on unesco_sites).\n"
        "health_resorts records statutory spa towns / health resorts (uzdrowiska) (e.g. 'Czy w powiecie znajduje się uzdrowisko?' uses exists on health_resorts; specific resort uses contains_exact on health_resorts).\n"
        "water_access records direct coastline access to Morze Bałtyckie (Baltic Sea).\n"
        "When a question names a specific neighboring county, use contains_exact on borders_powiat "
        "with its canonical Polish nominative name, not an inflected phrase copied from the question. "
        "Land-county names retain the adjective and 'Powiat' prefix; never replace them with "
        "the seat's city name. City counties use the city name. If uncertain about the nominative, "
        "preserve the specified county adjective for the catalog's inflection resolver.\n"
        "A city and its surrounding land county are different entities. Preserve an explicit "
        "voivodeship qualifier for county names shared by multiple voivodeships; never guess one.\n"
        "When a question instead describes a neighbor's administrative type, use any over "
        "target_powiat.borders_powiat with a predicate on item.is_city_county "
        "(1 for a city with county rights, 0 for a land county). The target and its neighbor "
        "have independent classifications. exists(borders_powiat) only checks for ANY neighbor "
        "and cannot answer this. Neither target_powiat.is_city_county nor a self-border test "
        "can substitute for the neighbor's classification.\n"
        "Example for at least one neighboring LAND county (not a named county):\n"
        '{"route":"local","plan":['
        '{"operator":"equals","left":{"entity":"item","relation":"is_city_county"},"right":{"value":0}},'
        '{"operator":"any","items":{"entity":"target_powiat","relation":"borders_powiat"},"args":[0]}'
        "]}\n"
        "Use regional_labels for broad, historical, cultural, or physical-geography regions "
        "of a powiat, such as Mazowsze, Podlasie, Kujawy, Małopolska, Śląsk, Kaszuby, "
        "Roztocze, Polesie, or named mountain/upland/lowland/lake-district regions. "
        "The relation is list-valued, so use contains_exact/exists rather than equals.\n"
        "- For voivodeship and borders_voivodeship, use the canonical Polish voivodeship adjective name "
        "(Dolnośląskie, Kujawsko-Pomorskie, Lubelskie, Lubuskie, Łódzkie, Małopolskie, Mazowieckie, "
        "Opolskie, Podkarpackie, Podlaskie, Pomorskie, Śląskie, Świętokrzyskie, Warmińsko-Mazurskie, "
        "Wielkopolskie, Zachodniopomorskie).\n"
        "- For registration plate code length (e.g. 'Czy tablice mają 2 litery?', 'Czy tablice mają 3 litery?'), "
        "use operator char_count_equals with left relation registration_plates and right value 2 or 3.\n"
        "- Shorthand questions consisting only of a voivodeship name or adjective, with or without a question mark "
        "(e.g. 'mazowieckie?', 'lubuskie', 'warmińsko mazurskie?'), are valid yes/no questions asking whether the target "
        "powiat lies in that voivodeship (relation voivodeship equals the canonical voivodeship name).\n"
        "- When a question asks about a property of the voivodeship that the target powiat lies in "
        "(e.g. whether the voivodeship has the Vistula river, borders Germany, or has sea access), "
        "use entity 'target_voivodeship' with the corresponding relation (major_rivers, borders_country, "
        "borders_voivodeship, water_access, is_coastal, mountain_ranges)."
    ),
)


def question_enhanced_from_plan(original_question: str, plan: QuestionPlan) -> PowiatQuestionEnhanced:
    return PowiatQuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question or original_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(
    question: str, day_powiat: PowiatdleDay, user: User | None, session: AsyncSession,
    *, strict_errors: bool = False, evidence: dict | None = None,
):
    powiat: Powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
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
        plan = await asyncio.to_thread(analyze_question, question, LOCAL_CONFIG, **planner_kwargs)
    finally:
        if evidence is not None:
            planner_evidence["duration_ms"] = (time.perf_counter() - planner_started) * 1000
    if not plan.valid:
        return PowiatQuestionCreate(
            user_id=user.id if user else None,
            day_id=day_powiat.id,
            original_question=question,
            question=plan.improved_question,
            valid=False,
            answer=None,
            explanation=plan.explanation or plan.fallback_reason or "Invalid question.",
            context="local_planner:invalid",
            intent=plan.explanation,
            required_info=plan.fallback_reason,
        ), plan
    if strict_errors and plan.supported and plan.plan and not LOCAL_CONFIG.db_path.is_file():
        raise RuntimeError("Local facts are unavailable")
    if evidence is not None:
        local_started = time.perf_counter()
    try:
        answer = await asyncio.to_thread(execute_plan, LOCAL_CONFIG, powiat.nazwa, plan)
    except Exception:
        if strict_errors:
            raise
        return None, plan
    finally:
        if evidence is not None:
            evidence["local_duration_ms"] = (time.perf_counter() - local_started) * 1000
    if answer is None:
        return None, plan
    target_names: set[str] = set()
    if not (answer.relations == ["name"] and answer.answer is True):
        target_names.add(powiat.nazwa)
        if powiat.nazwa.startswith("Powiat "):
            target_names.add(powiat.nazwa.replace("Powiat ", "", 1).strip())
    clean_exp = sanitize_explanation_for_player(answer.explanation, target_names, "this county")
    return PowiatQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_powiat.id,
        original_question=question,
        question=answer.question,
        valid=True,
        answer=answer.answer,
        explanation=clean_exp,
        context="local_kb:" + ",".join(answer.relations),
        intent=plan.explanation,
        required_info=", ".join(answer.relations),
    ), plan


async def enhance_question(question: str) -> PowiatQuestionEnhanced:
    system_prompt = """
You analyze questions for a game about Polish counties. Understand Polish and English
input identically. Determine whether it is a valid yes/no question about a county,
including direct identity questions and inclusive lists of possible identities.
Interpret first-person and pronoun references as referring to the target county.
Rewrite the main question clearly in English with the county as its subject, and
describe the user's intent and the specific facts needed to answer it in English.
Preserve the meaning and names. For invalid or open-ended input, explain why in English.

Return strict JSON with question, intent, required_info, valid and explanation.
For valid input, explanation is null. For invalid input, question, intent and
required_info are null, valid is false and explanation is a concise reason.

User: "Czy leży w małopolskim?"
Output: {"question": "Is the county in Małopolskie voivodeship?", "intent": "Check the county's administrative location.", "required_info": "County's voivodeship", "valid": true, "explanation": null}
User: "Powiedz mi coś o nim."
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "This is an open-ended request, not a yes/no question."}
"""

    question_prompt = f"""User's Question: {question}"""

    answer_dict = await asyncio.to_thread(gemini_json, system_prompt, question_prompt, max_output_tokens=768)
    return PowiatQuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation") or ("No explanation provided." if not answer_dict["valid"] else None),
    )



def _build_powiat_verified_facts_block(entity_name: str) -> str:
    import sqlite3
    from local_kb_question import get_entity_row, _get_parent_voivodeship_relation

    if not LOCAL_CONFIG.db_path.is_file():
        return ""
    try:
        with sqlite3.connect(LOCAL_CONFIG.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = get_entity_row(conn, LOCAL_CONFIG, entity_name)
            if row is None:
                return ""
            voiv = _get_parent_voivodeship_relation(row, "name") or row["voivodeship"]
            powiat_rivers = [
                r[0]
                for r in conn.execute(
                    "SELECT river_name FROM powiat_major_rivers WHERE powiat_id = ?",
                    (row["id"],),
                ).fetchall()
            ]
            voiv_rivers = _get_parent_voivodeship_relation(row, "major_rivers") or []
            voiv_countries = _get_parent_voivodeship_relation(row, "borders_country") or []
            voiv_neighbors = _get_parent_voivodeship_relation(row, "borders_voivodeship") or []
            lines = [
                f"- Target county's voivodeship: {voiv}",
                f"- County seat: {row['seat']}",
                f"- Major rivers flowing through the county: {', '.join(powiat_rivers) if powiat_rivers else 'none listed'}",
            ]
            if voiv_rivers:
                lines.append(
                    f"- Major rivers of {voiv} voivodeship (complete list): {', '.join(voiv_rivers)} (other major rivers not listed do NOT flow through {voiv} voivodeship)"
                )
            if voiv_neighbors:
                lines.append(f"- Voivodeships neighboring {voiv}: {', '.join(voiv_neighbors)}")
            lines.append(
                f"- Countries neighboring {voiv} voivodeship: {', '.join(voiv_countries) if voiv_countries else 'none (does not border a foreign country)'}"
            )
            return "\n### Verified database facts (always take precedence over general knowledge):\n" + "\n".join(lines) + "\n"
    except Exception:
        return ""


def answer_prompts(
    question: PowiatQuestionEnhanced, entity_name: str, context: str,
) -> tuple[str, str]:
    """Build the shared daily and explicit-target answer instructions."""
    verified_facts = _build_powiat_verified_facts_block(entity_name)
    system_prompt = f"""
You are the game master for Powiatdle. Answer the yes/no question about the
specified Polish county using the supplied context and your general knowledge.
Interpret Polish and English questions identically. Write the explanation in English.

Target county: {entity_name}
Question intent: {question.intent}
Required information: {question.required_info}
{verified_facts}
Context:
{context}

Find facts that confirm or contradict the proposition; use general knowledge of
Polish geography and administration when context lacks a fact. If the answer cannot
be determined with high confidence, set answer to null. For this game a county
borders itself. Treat "or" and lists as inclusive: any matching option is enough.
Answer about the county in the third person, even for first-person questions.
Provide an informative factual explanation supporting the answer, rather than
starting with yes or no or simply repeating it.

Return strict JSON: {{"explanation": "Informative factual statement in English.", "answer": true | false | null}}
"""


    question_prompt = f"""Original user question: {question.original_question}
Simplified question: {question.question}"""
    return system_prompt, question_prompt


def answer_question_for_entity(
    question: PowiatQuestionEnhanced, entity_name: str, context: str, *,
    evidence: dict | None = None, request_timeout: float | None = None,
    model: str | None = None, deadline: float | None = None,
) -> dict:
    """Run the normal answer model for an explicit target, without daily state."""
    system_prompt, question_prompt = answer_prompts(question, entity_name, context)
    from utils.fallback_answers import get_answer
    return get_answer(
        system_prompt, question_prompt, evidence=evidence,
        request_timeout=request_timeout, deadline=deadline, model=model,
    )


async def ask_question(
    question: PowiatQuestionEnhanced,
    day_powiat: PowiatdleDay,
    user: User | None,
    session: AsyncSession,
    *,
    evidence: dict | None = None,
    use_cache: bool = True,
) -> Tuple[PowiatQuestionCreate, List[float]]:
    powiat: Powiat = await PowiatRepository(session).get(day_powiat.powiat_id)
    if hasattr(session, "commit") and callable(session.commit):
        commit_res = session.commit()
        if asyncio.iscoroutine(commit_res):
            await commit_res
    from utils.fallback import retrieve_and_answer
    answer_dict, context, question_vector = await retrieve_and_answer(
        question, powiat.nazwa,
        cache_scope=("powiatdle", day_powiat.powiat_id) if use_cache else None,
        filter_key="powiat_id", filter_value=day_powiat.powiat_id,
        collection_name="powiaty", context_limit=qdrant.POWIATDLE_CONTEXT_LIMIT,
        session=session, answerer=answer_question_for_entity,
        prompt_builder=answer_prompts, evidence=evidence,
        game_date=getattr(day_powiat, "date", None),
    )
    question_create = PowiatQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_powiat.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=sanitize_explanation_for_player(
            answer_dict.get("explanation") or "No explanation provided.",
            {powiat.nazwa, powiat.nazwa.replace("Powiat ", "", 1).strip()} if powiat.nazwa.startswith("Powiat ") else {powiat.nazwa},
            "this county",
        ),
        context=context,
    )
    return question_create, question_vector
