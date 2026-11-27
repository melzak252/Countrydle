import asyncio
import time
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CountydleDay, EnglishCounty, User
from db.repositories.english_county import EnglishCountyRepository
from local_kb_question import LocalModeConfig, QuestionPlan, ROOT_DIR, analyze_question, execute_plan
from schemas.countydle import EnglishCountyQuestionCreate, EnglishCountyQuestionEnhanced

LOCAL_CONFIG = LocalModeConfig(
    mode_name="Countydle",
    entity_label="English ceremonial county",
    target_entity="target_county",
    db_path=ROOT_DIR / "data" / "english_county_facts.sqlite",
    table="english_counties",
    name_column="name",
    scalar_relations={
        "name": "name",
        "county_town": "county_town",
        "region": "region",
        "is_coastal": "is_coastal",
        "is_metropolitan": "is_metropolitan",
        "population": "population",
        "area": "area_km2",
        "latitude": "latitude",
        "longitude": "longitude",
    },
    list_relations={
        "borders_county": ("english_county_borders_counties", "border_county_name"),
        "borders_country": ("english_county_borders_countries", "country_name"),
        "water_access": ("english_county_water_access", "water_body"),
        "major_rivers": ("english_county_major_rivers", "river_name"),
        "major_cities": ("english_county_major_cities", "city_name"),
        "regional_labels": ("english_county_regional_labels", "label"),
    },
    entity_list_relations=frozenset({"borders_county"}),
    supported_relations=[
        "name",
        "county_town",
        "region",
        "is_coastal",
        "is_metropolitan",
        "population",
        "area",
        "latitude",
        "longitude",
        "borders_county",
        "borders_country",
        "water_access",
        "major_rivers",
        "major_cities",
        "regional_labels",
    ],
    language="English or Polish",
    fk_column="county_id",
    mode_notes=(
        "- There are 48 ceremonial counties of England.\n"
        "- Official region values (scalar 'region'): 'North East', 'North West', "
        "'Yorkshire and the Humber', 'East Midlands', 'West Midlands', 'East of England', "
        "'London', 'South East', 'South West'.\n"
        "- For broad or informal regional labels such as 'Northern England', 'Midlands', "
        "'Southern England', 'Home Counties', 'West Country', 'East Anglia', 'Yorkshire', "
        "'Welsh Marches', 'Cotswolds', 'Lake District', 'Peak District', 'Thames Valley', "
        "prefer relation regional_labels.\n"
        "- Generic coastal/sea access ('is it coastal?', 'czy ma dostęp do morza?', 'is it landlocked?') "
        "uses is_coastal == 1 (or negated for landlocked). Specific seas/channels ('North Sea', "
        "'English Channel', 'Irish Sea', 'Bristol Channel', 'Celtic Sea', 'Atlantic Ocean', 'The Solent') "
        "use contains_exact on water_access.\n"
        "- For metropolitan counties (Greater Manchester, Merseyside, South Yorkshire, Tyne and Wear, "
        "West Midlands, West Yorkshire), use is_metropolitan == 1.\n"
        "- For borders_county, use canonical ceremonial county names (e.g. 'Durham' not 'County Durham', "
        "'East Riding of Yorkshire', 'City of London', 'Tyne and Wear').\n"
        "- For borders_country, valid values are 'Scotland' and 'Wales' (normalize Polish 'Szkocja' -> 'Scotland', 'Walia' -> 'Wales').\n"
        "- For major_rivers, omit 'River' (e.g. 'Thames', 'Severn', 'Trent', 'Mersey', 'Tyne', 'Great Ouse', 'Avon').\n"
        "- Relative cardinal directions comparing position to another county or county town "
        "(e.g. 'north of London', 'west of Oxfordshire') use north_of/south_of on latitude and west_of/east_of on longitude."
    ),
)


def question_enhanced_from_plan(
    original_question: str, plan: QuestionPlan
) -> EnglishCountyQuestionEnhanced:
    return EnglishCountyQuestionEnhanced(
        original_question=original_question,
        valid=plan.valid,
        question=plan.improved_question or original_question,
        intent=plan.explanation,
        required_info=plan.fallback_reason,
        explanation=plan.explanation if not plan.valid else None,
    )


async def analyze_and_answer_locally(
    question: str,
    day_county: CountydleDay,
    user: User | None,
    session: AsyncSession,
    *,
    strict_errors: bool = False,
    evidence: dict | None = None,
):
    county: EnglishCounty = await EnglishCountyRepository(session).get(day_county.county_id)
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
        return EnglishCountyQuestionCreate(
            user_id=user.id if user else None,
            day_id=day_county.id,
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
        answer = await asyncio.to_thread(execute_plan, LOCAL_CONFIG, county.name, plan)
    except Exception:
        if strict_errors:
            raise
        return None, plan
    finally:
        if evidence is not None:
            evidence["local_duration_ms"] = (time.perf_counter() - local_started) * 1000
    if answer is None:
        return None, plan
    return EnglishCountyQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_county.id,
        original_question=question,
        question=answer.question,
        valid=True,
        answer=answer.answer,
        explanation=answer.explanation,
        context="local_kb:" + ",".join(answer.relations),
        intent=plan.explanation,
        required_info=", ".join(answer.relations),
    ), plan


def answer_prompts(
    question: EnglishCountyQuestionEnhanced, entity_name: str, context: str
) -> tuple[str, str]:
    system_prompt = f"""
You are the game master for Countydle (English Ceremonial Counties). Answer the yes/no question
about the specified English ceremonial county using the supplied context and your general knowledge
of English geography, history, and administration. Interpret Polish and English questions identically.
Write the explanation in English.

Target county: {entity_name}
Question intent: {question.intent}
Required information: {question.required_info}
Context:
{context}

Find facts that confirm or contradict the proposition. If the answer cannot be determined with high
confidence, set answer to null. For this game a county borders itself. Treat "or" and lists as
inclusive: any matching option is enough. Answer about the county in the third person. Provide an
informative factual explanation supporting the answer rather than starting with yes or no.

Return strict JSON: {{"explanation": "Informative factual statement in English.", "answer": true | false | null}}
"""
    question_prompt = f"""Original user question: {question.original_question}
Simplified question: {question.question}"""
    return system_prompt, question_prompt


def answer_question_for_entity(
    question: EnglishCountyQuestionEnhanced,
    entity_name: str,
    context: str,
    *,
    evidence: dict | None = None,
    request_timeout: float | None = None,
    model: str | None = None,
    deadline: float | None = None,
) -> dict:
    system_prompt, question_prompt = answer_prompts(question, entity_name, context)
    from utils.fallback_answers import get_answer

    return get_answer(
        system_prompt,
        question_prompt,
        evidence=evidence,
        request_timeout=request_timeout,
        deadline=deadline,
        model=model,
    )


async def ask_question(
    question: EnglishCountyQuestionEnhanced,
    day_county: CountydleDay,
    user: User | None,
    session: AsyncSession,
    *,
    evidence: dict | None = None,
    use_cache: bool = True,
) -> Tuple[EnglishCountyQuestionCreate, List[float]]:
    county: EnglishCounty = await EnglishCountyRepository(session).get(day_county.county_id)
    if hasattr(session, "commit") and callable(session.commit):
        commit_res = session.commit()
        if asyncio.iscoroutine(commit_res):
            await commit_res
    answer_dict = await asyncio.to_thread(
        answer_question_for_entity,
        question,
        county.name,
        "",
        evidence=evidence,
    )
    question_create = EnglishCountyQuestionCreate(
        user_id=user.id if user else None,
        day_id=day_county.id,
        original_question=question.original_question,
        valid=question.valid,
        question=question.question,
        answer=answer_dict.get("answer"),
        explanation=answer_dict.get("explanation") or "No explanation provided.",
        context="fallback:general_knowledge",
    )
    return question_create, []
