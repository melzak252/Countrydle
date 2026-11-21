import asyncio
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from pydantic import ValidationError
from schemas.blog import BlogPostUpdate, BlogSourceLink
from db.models.blog import DailyBlogPost
from db.models.fragment import CountryFragment
from db.models.countrydle import CountrydleDay, CountrydleQuestion

logger = logging.getLogger(__name__)

PRIMARY_MODEL = os.getenv("BLOG_GENERATOR_MODEL", "gemini-2.5-flash-lite")
FALLBACK_MODEL = os.getenv("BLOG_FALLBACK_MODEL", "gemini-2.5-flash")
_CITATION_NEEDED = re.compile(r"\[\s*citation\s*needed\s*\]", re.IGNORECASE)


def generate_slug(post_date: date, country_name: str) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", country_name.strip().lower()).strip("-")
    return f"{post_date.isoformat()}-{clean_name}"

def deduplicate_border_names(borders: List[str]) -> List[str]:
    """Deduplicate canonical country names and aliases for human display."""
    canonical_aliases = {
        "dr congo": "Democratic Republic of the Congo",
        "democratic republic of the congo": "Democratic Republic of the Congo",
        "czech republic": "Czechia",
        "czechia": "Czechia",
        "usa": "United States",
        "united states": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
    }
    seen = set()
    result = []
    for b in borders:
        clean = b.strip()
        canonical = canonical_aliases.get(clean.lower(), clean)
        canon_key = canonical.lower()
        if canon_key not in seen:
            seen.add(canon_key)
            result.append(canonical)
    return sorted(result)

def get_country_sqlite_facts(country_name: str) -> Dict[str, Any]:
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data" if (base / "data").exists() else base.parent / "data"
    facts_db = data_dir / "country_facts.sqlite"
    if not facts_db.exists():
        return {}
    try:
        conn = sqlite3.connect(f"{facts_db.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM countries WHERE app_country_name = ? LIMIT 1", (country_name,)).fetchone()
        if not row:
            conn.close()
            return {}
        c_id = row["id"]
        raw_borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id = ?", (c_id,)).fetchall()]
        borders = deduplicate_border_names(raw_borders)
        water = [r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id = ?", (c_id,)).fetchall()]
        languages = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id = ?", (c_id,)).fetchall()]
        continents = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id = ?", (c_id,)).fetchall()]
        conn.close()
        return {
            "capital": row["capital"] or "N/A",
            "population": f"{row['population']:,}" if row["population"] else "N/A",
            "area_km2": f"{int(row['area_km2']):,} km²" if row["area_km2"] else "N/A",
            "continent": ", ".join(continents) or row["region"] or "N/A",
            "region": row["subregion"] or row["region"] or "N/A",
            "water_access": ", ".join(water) if water else "N/A",
            "borders": ", ".join(borders) if borders else "N/A",
            "languages": ", ".join(languages) if languages else "N/A",
            "driving_side": row["driving_side"] or "Right",
        }
    except Exception:
        return {}

def get_deduction_steps(country_name: str, actual_questions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    # This is a recap of logged play, not a hypothetical solution walkthrough.
    steps = []
    if actual_questions:
        seen = set()
        for q in actual_questions:
            q_clean = q['question'].strip()
            if country_name.lower() in q_clean.lower():
                continue
            if q_clean not in seen and len(steps) < 4:
                seen.add(q_clean)
                steps.append({
                    "step": len(steps) + 1,
                    "question": q["question"],
                    "answer": q["answer"],
                    "explanation": q["explanation"],
                })

    return steps


def get_curator_pro_tip(country_name: str, facts: Dict[str, Any]) -> str:
    return "Questions about region, borders, and access to water can help narrow the candidates."

def _call_gemini_api(model: str, prompt: str, api_key: str, timeout: int = 25) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "generativelanguage.googleapis.com":
        raise ValueError("Invalid Gemini API URL")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        }
    })
    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw_text = res["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)


def _validate_generated_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the same editable-content contract as an editor before accepting output."""
    editable = {field: payload[field] for field in BlogPostUpdate.model_fields if field in payload}
    validated = BlogPostUpdate.model_validate(editable)
    return {**payload, **validated.model_dump(mode="json", exclude_unset=True)}


async def generate_blog_content_ai(
    country_name: str,
    wiki_fragments: List[str],
    post_date: date,
    actual_questions: Optional[List[Dict[str, Any]]] = None,
    player_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    country_facts = get_country_sqlite_facts(country_name)
    if not api_key:
        logger.warning("No GEMINI_API_KEY found, falling back to deterministic template.")
        return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions, player_summary)

    facts_summary = f"""
- Capital: {country_facts.get('capital', 'N/A')}
- Continent & Region: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- Population: {country_facts.get('population', 'N/A')}
- Land Area: {country_facts.get('area_km2', 'N/A')}
- Coastline / Water Access: {country_facts.get('water_access', 'N/A')}
- Neighboring Borders: {country_facts.get('borders', 'N/A')}
- Driving Side: {country_facts.get('driving_side', 'N/A')}
- Languages in dataset (not necessarily official): {country_facts.get('languages', 'N/A')}
"""
    telemetry_summary = "No player telemetry recorded for this date yet."
    if player_summary and player_summary.get("total_players", 0) > 0:
        pitfalls = ", ".join(
            f"{p['guess']} ({p['count']}x)" for p in (player_summary.get("pitfalls") or [])[:4]
        ) or "None"
        telemetry_summary = (
            f"Challengers: {player_summary['total_players']} | "
            f"Solved: {player_summary.get('winners_count', 0)} ({player_summary.get('win_rate_pct', 0)}%) | "
            f"Avg questions to win: {player_summary.get('avg_questions_won', 0)} | "
            f"Top wrong guesses: {pitfalls}"
        )

    clean_frags = []
    for frag in wiki_fragments:
        cleaned = frag.replace(r'\[', '[').replace(r'\]', ']').replace(r'\(', '(').replace(r'\)', ')').replace(r'\_', '_').replace(r'\*', '*').replace(r'\-', '-')
        cleaned = re.sub(r'\[\d+\]', '', cleaned)
        cleaned = cleaned.replace('\\', '').strip()
        if cleaned.startswith('|') and '---' in cleaned and len(cleaned) < 300:
            continue
        if len(cleaned) > 80:
            clean_frags.append(cleaned[:1000])

    wiki_context = "\n\n".join(clean_frags[:15]) if clean_frags else "No additional Wikipedia context available."

    prompt = f"""You are the lead geography editor and game analyst for Countrydle.
Write a crisp, entertaining, zero-fluff daily recap for {country_name} ({post_date.strftime('%B %d, %Y')}).

Stored country data (not independently verified):
{facts_summary}

How players performed on this puzzle:
{telemetry_summary}

Wikipedia Context Excerpts:
{wiki_context}

Source excerpts can contain unresolved [citation needed] warnings. Do not use claims
marked with that warning as facts, and do not imply they have been independently verified.

STYLE RULES (ANTI-SLOP):
- Write like a sharp puzzle columnist, NOT generic AI travel prose.
- BANNED clichés: "nestled in", "rich tapestry", "vibrant mosaic", "testament to", "delve into", "in conclusion", "land of contrasts".
- Use concrete numbers, borders, seas, and player misguesses.

TASK — Return a single raw JSON object with:
1. "title": Punchy headline (e.g. "{country_name}: [Sharp Hook or Puzzle Twist]").
2. "subtitle": 1 crisp sentence teasing what made {country_name} tricky or fun to deduce.
3. "summary": 2 sentences summarizing the puzzle and how players handled it.
4. "editorial_body": 2 tight, engaging paragraphs:
   - Paragraph 1: How players fared (cite the win rate, avg questions, or wrong-guess traps if telemetry exists; otherwise explain the sharpest deduction path).
   - Paragraph 2: The geographic profile (terrain, borders, coastline, or neighbors that separate {country_name} from look-alikes).
5. "fun_facts": EXACTLY 2 surprising, self-contained curiosities about {country_name}'s geography, culture, or history.
   - "title": 2–4 word hook.
   - "description": 1–2 crisp sentences naming {country_name} directly (no dangling pronouns).
6. "trivia_quiz": 1 quick multiple-choice question about {country_name}.
   - CRITICAL: Must test a DIFFERENT fact from both items in "fun_facts" (do not repeat or paraphrase them).
   - "question": Clear question string.
   - "correct_answer": Exact correct answer.
   - "incorrect_distractor": Believable, plausible wrong answer.
   - "explanation": 1 concise sentence explaining why.

Return ONLY the raw JSON object.
"""

    loop = asyncio.get_running_loop()
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        try:
            logger.info(f"Calling Gemini model {model_name} for blog post ({country_name})...")
            res = await loop.run_in_executor(None, _call_gemini_api, model_name, prompt, api_key, 35)
            if not isinstance(res, dict) or not res.get("fun_facts"):
                raise ValueError("Provider output must include substantive fun facts")
            payload = _assemble_blog_post_payload(country_name, country_facts, res, post_date, actual_questions, player_summary)
            payload.update(_generation_provenance(wiki_fragments, ai_assisted=True))
            payload = _validate_generated_payload(payload)
            logger.info(f"Successfully generated blog content using {model_name} for {country_name}")
            return payload
        except Exception as e:
            logger.warning(f"Model {model_name} failed for {country_name}: {e}")

    logger.warning(f"All AI models failed for {country_name}, using deterministic template.")
    return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions, player_summary)


def _build_fallback_facts_and_quiz(
    country_name: str,
    country_facts: Dict[str, Any],
) -> tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
    """Build 2 grounded fun facts and 1 non-overlapping quiz question from SQLite facts."""
    facts: List[Dict[str, str]] = []
    capital = country_facts.get("capital")
    borders = country_facts.get("borders")
    water = country_facts.get("water_access")
    driving = country_facts.get("driving_side")
    area = country_facts.get("area_km2")
    pop = country_facts.get("population")
    region = country_facts.get("region") or country_facts.get("continent")

    # Quiz focuses on Capital (if available) or Driving Side so fun_facts cover different traits.
    quiz: Optional[Dict[str, str]] = None
    if capital and capital != "N/A":
        distractors = {
            "Tokyo": "Osaka",
            "Brasília": "Rio de Janeiro",
            "Rabat": "Casablanca",
            "Pristina": "Prizren",
            "Canberra": "Sydney",
            "Ottawa": "Toronto",
            "Bern": "Zurich",
        }
        wrong = distractors.get(capital, f"{country_name} City" if capital != f"{country_name} City" else "Port Harbor")
        quiz = {
            "question": f"Which city serves as the capital of {country_name}?",
            "correct_answer": capital,
            "incorrect_distractor": wrong,
            "explanation": f"{capital} is the recorded capital of {country_name}.",
        }
    elif driving in {"Left", "Right"}:
        other_side = "Right" if driving == "Left" else "Left"
        quiz = {
            "question": f"Which side of the road do drivers use in {country_name}?",
            "correct_answer": f"{driving} side",
            "incorrect_distractor": f"{other_side} side",
            "explanation": f"Traffic in {country_name} drives on the {driving.lower()} side.",
        }

    if borders and borders != "N/A" and borders != "None":
        border_list = [b.strip() for b in borders.split(",") if b.strip()]
        facts.append({
            "title": "Border Footprint",
            "description": f"{country_name} shares land borders with {len(border_list)} neighbor{'s' if len(border_list) != 1 else ''}: {', '.join(border_list[:5])}{'…' if len(border_list) > 5 else ''}.",
        })
    elif water and water != "N/A":
        facts.append({
            "title": "Island & Sea Access",
            "description": f"{country_name} has no land borders and connects directly to {water}.",
        })

    if driving in {"Left", "Right"} and (not quiz or "side" not in quiz["question"]):
        facts.append({
            "title": "Road Rules",
            "description": f"Vehicles in {country_name} drive on the {driving.lower()} side of the road.",
        })
    elif area and area != "N/A" and pop and pop != "N/A":
        facts.append({
            "title": "Scale on the Map",
            "description": f"{country_name} spans {area} with a recorded population of {pop}.",
        })

    if len(facts) < 2 and region and region != "N/A":
        facts.append({
            "title": "Regional Placement",
            "description": f"On the world map, {country_name} sits within {region}.",
        })

    return facts[:2], quiz


def _assemble_blog_post_payload(
    country_name: str,
    country_facts: Dict[str, Any],
    ai_data: Dict[str, Any],
    post_date: date,
    actual_questions: Optional[List[Dict[str, Any]]] = None,
    player_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    steps = get_deduction_steps(country_name, actual_questions)
    pro_tip = get_curator_pro_tip(country_name, country_facts)
    fallback_facts, fallback_quiz = _build_fallback_facts_and_quiz(country_name, country_facts)
    fun_facts = (ai_data.get("fun_facts") or fallback_facts)[:2]
    if ai_data.get("editorial_body"):
        markdown = ai_data["editorial_body"].strip()
    else:
        from utils.water_hierarchy import is_marine_water_body
        region_str = country_facts.get("region") or country_facts.get("continent") or "the world"
        capital_str = country_facts.get("capital")
        cap_phrase = f" with its capital at {capital_str}" if capital_str and capital_str != "N/A" else ""
        water_str = country_facts.get("water_access")
        borders_str = country_facts.get("borders")
        geo_parts = []
        if water_str and water_str != "N/A":
            water_items = [w.strip() for w in water_str.split(",") if w.strip()]
            marine = [w for w in water_items if is_marine_water_body(w)]
            inland = [w for w in water_items if not is_marine_water_body(w)]
            if marine:
                geo_parts.append(f"maritime coastal access along the {', '.join(marine)}")
            if inland:
                geo_parts.append(f"shoreline along inland water ({', '.join(inland)})")
        if borders_str and borders_str != "N/A" and borders_str != "None":
            geo_parts.append(f"land borders with {borders_str}")
        geo_phrase = f" Key recorded geographical features include {'; '.join(geo_parts)}." if geo_parts else ""
        perf_line = ""
        if player_summary and player_summary.get("total_players", 0) > 0:
            perf_line = (
                f"\n\n## How Players Handled It\n\n"
                f"{player_summary['total_players']} challengers tackled {country_name}, "
                f"with {player_summary.get('win_rate_pct', 0)}% solving it in an average of "
                f"{player_summary.get('avg_questions_won', 0)} questions."
            )
        markdown = f"## Geographic Profile\n\n{country_name} is situated in {region_str}{cap_phrase}.{geo_phrase}{perf_line}"

    deduction_masterclass = {
        "steps": steps,
        "pro_tip": pro_tip,
    }
    # An omitted quiz is legitimate; a present invalid quiz must never be dropped.
    if "trivia_quiz" in ai_data:
        deduction_masterclass["quiz"] = ai_data["trivia_quiz"]
    elif fallback_quiz is not None:
        deduction_masterclass["quiz"] = fallback_quiz

    title = ai_data.get("title") or f"Countrydle Solution: {country_name}"
    subtitle = ai_data.get("subtitle") or f"Deduction breakdown, 2 fast facts & quick quiz for {country_name}."
    summary = ai_data.get("summary") or f"Yesterday's Countrydle mystery country was {country_name}."

    return {
        "title": title,
        "subtitle": subtitle,
        "reading_time_minutes": 2,
        "summary": summary,
        "fast_facts": {
            "capital": country_facts.get("capital", "N/A"),
            "continent": country_facts.get("continent", "N/A"),
            "region": country_facts.get("region", "N/A"),
            "population": country_facts.get("population", "N/A"),
            "area": country_facts.get("area_km2", "N/A"),
            "coastline": country_facts.get("water_access", "N/A"),
            "borders": country_facts.get("borders", "N/A"),
            "languages": country_facts.get("languages", "N/A"),
        },
        "fun_facts": fun_facts,
        "deduction_masterclass": deduction_masterclass,
        "content_markdown": markdown,
    }


def _generation_provenance(wiki_fragments: List[str], *, ai_assisted: bool) -> Dict[str, Any]:
    origin = "AI-assisted recap" if ai_assisted else "Automatically assembled template recap"
    note = (
        f"{origin} using stored country facts"
        + (" and local article excerpts without retained source URLs" if ai_assisted else "")
        + ". No external source pages were fetched for this recap. No human editorial review was recorded during generation."
    )
    if any(
        _CITATION_NEEDED.search(fragment.replace("\\", ""))
        or "citation needed" in fragment.lower()
        for fragment in wiki_fragments
    ):
        note += " Retrieved excerpts include unresolved [citation needed] warnings."
        if not ai_assisted:
            note += " No excerpt claims were included in the template."
        note += " Warning-bearing claims must not be treated as verified without checking their evidence."
    return {"source_links": [], "editorial_note": note, "ai_assisted": ai_assisted}


def _used_question_sources(
    questions: List[Dict[str, Any]], steps: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Retain cited stored evidence only for questions included in this recap."""
    used = {(step["question"], step["answer"], step["explanation"]) for step in steps}
    sources = []
    seen = set()
    for question in questions:
        if (question["question"], question["answer"], question["explanation"]) not in used:
            continue
        for evidence in question.get("fact_provenance") or []:
            if not isinstance(evidence, dict):
                continue
            provenance = evidence.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("status") != "cited":
                continue
            citation, url = provenance.get("citation"), provenance.get("source_url")
            if not isinstance(citation, str) or not citation.strip() or not isinstance(url, str):
                continue
            try:
                source = BlogSourceLink(label=citation.strip()[:200], url=url)
            except ValidationError:
                continue
            if source.url not in seen:
                seen.add(source.url)
                sources.append(source.model_dump())
                if len(sources) == 20:
                    return sources
    return sources


def _generate_fallback_template(
    country_name: str, 
    wiki_fragments: List[str], 
    post_date: date,
    actual_questions: Optional[List[Dict[str, Any]]] = None,
    player_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    country_facts = get_country_sqlite_facts(country_name)
    payload = _assemble_blog_post_payload(country_name, country_facts, {}, post_date, actual_questions, player_summary)
    payload.update(_generation_provenance(wiki_fragments, ai_assisted=False))
    return _validate_generated_payload(payload)


async def create_daily_blog_post(
    engine: AsyncEngine,
    country_id: int,
    country_name: str,
    post_date: date,
) -> DailyBlogPost:
    """Build an unsaved recap from scalar inputs using an owned read session.

    Callers must finish their discovery transaction before invoking generation;
    no caller session or ORM instance is retained across provider I/O.
    """
    async with AsyncSession(bind=engine) as input_session:
        res = await input_session.execute(
            select(CountryFragment.text)
            .where(CountryFragment.country_id == country_id)
            .limit(25)
        )
        fragments = list(res.scalars().all())
        day_id = await input_session.scalar(
            select(CountrydleDay.id).where(CountrydleDay.date == post_date)
        )

        actual_questions: List[Dict[str, Any]] = []
        if day_id is not None:
            q_res = await input_session.execute(
                select(
                    CountrydleQuestion.question, CountrydleQuestion.answer,
                    CountrydleQuestion.explanation, CountrydleQuestion.fact_provenance,
                )
                .where(CountrydleQuestion.day_id == day_id, CountrydleQuestion.valid.is_(True))
                .order_by(CountrydleQuestion.id.asc())
                .limit(15)
            )
            for q in q_res.all():
                actual_questions.append({
                    "question": q.question or "",
                    "answer": "YES" if q.answer is True else "NO" if q.answer is False else "UNKNOWN",
                    "explanation": q.explanation or "",
                    "fact_provenance": q.fact_provenance or [],
                })

        player_summary: Optional[Dict[str, Any]] = None
        if day_id is not None:
            from db.models.countrydle import CountrydleGuess
            from db.repositories.participation import ParticipationRepository
            from sqlalchemy import func
            stats = await ParticipationRepository(input_session).get_stats(post_date, mode="countrydle")
            pitfalls_rows = (await input_session.execute(
                select(CountrydleGuess.guess, func.count(CountrydleGuess.id).label("cnt"))
                .where(CountrydleGuess.day_id == day_id, CountrydleGuess.answer.is_(False))
                .group_by(CountrydleGuess.guess)
                .order_by(func.count(CountrydleGuess.id).desc())
                .limit(4)
            )).all()
            player_summary = {
                **stats,
                "pitfalls": [{"guess": r.guess, "count": int(r.cnt)} for r in pitfalls_rows],
            }

    # 3. Generate content via Gemini (with questions log, player stats, and anti-slop rules)
    payload = await generate_blog_content_ai(country_name, fragments, post_date, actual_questions, player_summary)
    steps = (payload.get("deduction_masterclass") or {}).get("steps") or []
    payload["source_links"] = _used_question_sources(actual_questions, steps)
    if payload["source_links"]:
        payload["editorial_note"] += (
            " Listed links are citations attached to the stored question evidence used "
            "in this recap, not source pages fetched again during generation."
        )

    # Sources and provenance are assembled after provider validation; validate them too.
    payload = _validate_generated_payload(payload)
    slug = generate_slug(post_date, country_name)

    post = DailyBlogPost(
        date=post_date,
        country_id=country_id,
        slug=slug,
        title=payload["title"],
        subtitle=payload["subtitle"],
        reading_time_minutes=payload.get("reading_time_minutes", 2),
        summary=payload.get("summary", ""),
        fast_facts=payload.get("fast_facts"),
        fun_facts=payload.get("fun_facts", []),
        deduction_masterclass=payload.get("deduction_masterclass"),
        content_markdown=payload.get("content_markdown", ""),
        source_links=payload["source_links"],
        editorial_note=payload["editorial_note"],
        ai_assisted=payload["ai_assisted"],
        reviewed_by_id=None,
        reviewed_at=None,
    )

    return post
