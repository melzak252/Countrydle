import asyncio
import time
import qdrant
from typing import List, Tuple
from utils.ai_clients import gemini_json

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Wojewodztwo, WojewodztwodleDay, User
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
        "major_roads": ("voivodeship_major_roads", "road_name"),
        "mountain_ranges": ("voivodeship_mountain_ranges", "range_name"),
        "historical_region": ("voivodeship_historical_regions", "region_name"),
        "landform_regions": ("voivodeship_landform_regions", "region_name"),
        "regional_labels": ("voivodeship_regional_labels", "label"),
    },
    entity_list_relations=frozenset({"borders_voivodeship"}),
    supported_relations=[
        "name", "seat", "macroregion", "borders_voivodeship", "borders_country", "water_access",
        "is_coastal", "population", "area", "latitude", "longitude", "major_rivers", "mountain_ranges",
        "historical_region", "urbanization", "powiat_count", "city_count", "city_count_with_powiat_rights",
        "landform_regions", "regional_labels", "major_roads",
    ],
    mode_notes=(
        "- For motorways (autostrady) and expressways (drogi ekspresowe), use contains_exact or contains_text on major_roads with code e.g. A1, A2, A4, S3, S5, S7, S8, S19.\n"
        "- Relative cardinal directions comparing position to another voivodeship, city, or capital (e.g. 'na zachód od Mazowsza / Warszawy', 'na południe od Warszawy') are supported: use operator west_of / east_of on longitude and north_of / south_of on latitude with the reference entity.\n"
        "- For borders_voivodeship, use the canonical Polish voivodeship adjective name: "
        "Dolnośląskie, Kujawsko-Pomorskie, Lubelskie, Lubuskie, Łódzkie, Małopolskie, "
        "Mazowieckie, Opolskie, Podkarpackie, Podlaskie, Pomorskie, Śląskie, "
        "Świętokrzyskie, Warmińsko-Mazurskie, Wielkopolskie, Zachodniopomorskie. "
        "Never use city names (like Łódź, Kraków, Warszawa) for borders_voivodeship.\n"
        "- For informal location labels such as 'zachodnia Polska', 'wschodnia Polska', "
        "'północna Polska', 'południowa Polska', 'centralna Polska', 'nadmorska Polska', "
        "or historical/common areas such as Śląsk, Małopolska, Pomorze, Mazury, Podlasie, "
        "prefer relation regional_labels. Use macroregion only for exact broad macroregion wording."
    ),
)


def question_enhanced_from_plan(original_question: str, plan: QuestionPlan) -> WojewodztwoQuestionEnhanced:
    return WojewodztwoQuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question or original_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(
    question: str, day_wojewodztwo: WojewodztwodleDay, user: User | None, session: AsyncSession,
    *, strict_errors: bool = False, evidence: dict | None = None,
):
    wojewodztwo: Wojewodztwo = await WojewodztwoRepository(session).get(day_wojewodztwo.wojewodztwo_id)
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
        return WojewodztwoQuestionCreate(
            user_id=user.id if user else None,
            day_id=day_wojewodztwo.id,
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
        answer = await asyncio.to_thread(execute_plan, LOCAL_CONFIG, wojewodztwo.nazwa, plan)
    except Exception:
        if strict_errors:
            raise
        return None, plan
    finally:
        if evidence is not None:
            evidence["local_duration_ms"] = (time.perf_counter() - local_started) * 1000
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
You analyze questions for a game about Polish voivodeships. Understand Polish and
English input identically. Determine whether it is a valid yes/no question about
a voivodeship, including direct identity questions and inclusive lists of possible
identities. Interpret first-person and pronoun references as the target voivodeship.
Rewrite the main question clearly in English with the voivodeship as its subject,
and describe the user's intent and the specific facts needed to answer it in English.
Preserve the meaning and names. For invalid or open-ended input, explain why in English.

Return strict JSON with question, intent, required_info, valid and explanation.
For valid input, explanation is null. For invalid input, question, intent and
required_info are null, valid is false and explanation is a concise reason.

User: "Czy graniczy z morzem?"
Output: {"question": "Does the voivodeship have access to the Baltic Sea?", "intent": "Check whether the voivodeship is on the Baltic Sea.", "required_info": "Geographic location and maritime borders", "valid": true, "explanation": null}
User: "Ile ma mieszkańców?"
Output: {"question": null, "intent": null, "required_info": null, "valid": false, "explanation": "This is an open-ended question, not a yes/no question."}
"""

    question_prompt = f"""User's Question: {question}"""

    answer_dict = await asyncio.to_thread(gemini_json, system_prompt, question_prompt, max_output_tokens=768)
    return WojewodztwoQuestionEnhanced(
        original_question=question,
        valid=answer_dict["valid"],
        question=answer_dict.get("question", None),
        intent=answer_dict.get("intent", None),
        required_info=answer_dict.get("required_info", None),
        explanation=answer_dict.get("explanation") or ("No explanation provided." if not answer_dict["valid"] else None),
    )



def answer_prompts(
    question: WojewodztwoQuestionEnhanced, entity_name: str, context: str,
) -> tuple[str, str]:
    """Build the shared daily and explicit-target answer instructions."""
    system_prompt = f"""
You are the game master for Wojewodztwodle. Answer the yes/no question about the
specified Polish voivodeship using the supplied context and your general knowledge.
Interpret Polish and English questions identically. Write the explanation in English.

Target voivodeship: {entity_name}
Question intent: {question.intent}
Required information: {question.required_info}
Context:
{context}

Find facts that confirm or contradict the proposition; use general knowledge of
Polish geography, history and administration when context lacks a fact. If the
answer cannot be determined with high confidence, set answer to null. For this game
a voivodeship borders itself. Treat "or" and lists as inclusive: any matching option
is enough. Answer about the voivodeship in the third person, even for first-person
questions. Provide an informative factual explanation supporting the answer,
rather than starting with yes or no or simply repeating it.

Return strict JSON: {{"explanation": "Informative factual statement in English.", "answer": true | false | null}}
"""


    question_prompt = f"""Original user question: {question.original_question}
Simplified question: {question.question}"""
    return system_prompt, question_prompt


def answer_question_for_entity(
    question: WojewodztwoQuestionEnhanced, entity_name: str, context: str, *,
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
    question: WojewodztwoQuestionEnhanced,
    day_wojewodztwo: WojewodztwodleDay,
    user: User | None,
    session: AsyncSession,
    *,
    evidence: dict | None = None,
    use_cache: bool = True,
) -> Tuple[WojewodztwoQuestionCreate, List[float]]:
    wojewodztwo: Wojewodztwo = await WojewodztwoRepository(session).get(
        day_wojewodztwo.wojewodztwo_id
    )
    if hasattr(session, "commit") and callable(session.commit):
        commit_res = session.commit()
        if asyncio.iscoroutine(commit_res):
            await commit_res
    from utils.fallback import retrieve_and_answer
    answer_dict, context, question_vector = await retrieve_and_answer(
        question, wojewodztwo.nazwa,
        cache_scope=("wojewodztwodle", day_wojewodztwo.wojewodztwo_id) if use_cache else None,
        filter_key="wojewodztwo_id", filter_value=day_wojewodztwo.wojewodztwo_id,
        collection_name="wojewodztwa", context_limit=qdrant.WOJEWODZTWDLE_CONTEXT_LIMIT,
        session=session, answerer=answer_question_for_entity,
        prompt_builder=answer_prompts, evidence=evidence,
        game_date=getattr(day_wojewodztwo, "date", None),
    )
    question_create = WojewodztwoQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_wojewodztwo.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "No explanation provided.",
        context=context,
    )
    return question_create, question_vector
