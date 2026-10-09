import asyncio
import json
import logging
import os
import re
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

PRIMARY_MODEL = os.getenv("BLOG_GENERATOR_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("BLOG_FALLBACK_MODEL", "gemini-3.1-pro-preview")
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
            "water_access": ", ".join(water) if water else ("Island Nation" if row["is_island"] else "Landlocked"),
            "borders": ", ".join(borders) if borders else ("None (Island nation)" if row["is_island"] else "None"),
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
    water = facts.get("water_access", "")
    continent = facts.get("continent", "")
    borders = facts.get("borders", "")
    border_list = [b.strip() for b in borders.split(',') if b.strip() and b.strip() != 'None']

    if "landlocked" in water.lower():
        if "africa" in continent.lower():
            return f"There are only 16 landlocked nations in Africa. When your query confirms zero coastline, immediately ask about latitude (Equator) or borders with {border_list[0] if border_list else 'neighbors'} to isolate the target."
        elif "south america" in continent.lower():
            return "There are only two landlocked nations in South America: Bolivia and Paraguay. Asking about sea access immediately narrows your search to a 50/50 split."
        else:
            return f"When a nation is landlocked, eliminate all coastal states early and test regional anchors like {border_list[0] if border_list else 'bordering hubs'}."
    elif "none" in borders.lower() or "island" in borders.lower():
        return f"{country_name} has zero land borders. Once you confirm an island nation, test oceanic basins ({water}) or population thresholds to pinpoint the answer."
    else:
        first_border = border_list[0] if border_list else "a major neighbor"
        return f"Testing shared borders with {first_border} isolates the regional cluster immediately. Combine border queries with official languages to lock in {country_name}."


def extract_clean_curiosities(country_name: str, wiki_fragments: List[str], facts: Dict[str, Any]) -> List[Dict[str, str]]:
    sentences = []
    banned_words = [
        "redirects here", "see also", "main article", "from wikipedia",
        "coordinates:", "citation needed", "for the former", "for other uses",
        "human rights", "conflict"
    ]

    for frag in wiki_fragments:
        if frag.strip().startswith('|') or '--- | ---' in frag:
            continue

        cleaned = frag.replace(r'\[', '[').replace(r'\]', ']').replace(r'\(', '(').replace(r'\)', ')').replace(r'\_', '_').replace(r'\*', '*').replace(r'\-', '-')
        cleaned = re.sub(r'\[\d+\]', '', cleaned)
        cleaned = cleaned.replace('\\', '')
        # A warning after sentence punctuation still belongs to the preceding claim.
        # Move it inside that sentence before splitting, preserving unrelated sentences.
        cleaned = re.sub(
            rf"([.!?])\s*({_CITATION_NEEDED.pattern})",
            r" \2\1",
            cleaned,
            flags=re.IGNORECASE,
        )

        raw_sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        for s in raw_sentences:
            s = re.sub(r'\s+', ' ', s).strip()
            if len(s) >= 50 and len(s) <= 280 and s[0].isupper() and s[-1] in ('.', '!'):
                if not s.startswith(('#', '|', '-', '*', '•', '>', 'State in', 'Country in')):
                    if not _CITATION_NEEDED.search(s) and not any(bw in s.lower() for bw in banned_words):
                        if s not in sentences:
                            sentences.append(s)

    curiosities = []
    if len(sentences) >= 1:
        curiosities.append({
            "title": "Geographic Fact",
            "description": sentences[0]
        })
    if len(sentences) >= 2:
        curiosities.append({
            "title": "Cultural Heritage",
            "description": sentences[1]
        })

    if len(curiosities) < 1:
        curiosities.append({
            "title": "Geographic Profile",
            "description": f"{country_name} spans {facts.get('area_km2', 'an extensive territory')} in {facts.get('continent', 'its region')}, situated with {facts.get('water_access', 'its territorial borders')}."
        })
    if len(curiosities) < 2:
        borders = facts.get('borders', 'neighboring states')
        curiosities.append({
            "title": "Border Connections",
            "description": f"The country shares land borders with {borders}." if borders != "None" else f"{country_name} is an island nation surrounded by {facts.get('water_access', 'ocean basins')}."
        })
    return curiosities

def _call_gemini_api(model: str, prompt: str, api_key: str, timeout: int = 25) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    country_facts = get_country_sqlite_facts(country_name)
    if not api_key:
        logger.warning("No GEMINI_API_KEY found, falling back to deterministic template.")
        return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions)

    facts_summary = f"""
- Capital: {country_facts.get('capital', 'N/A')}
- Continent & Region: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- Population: {country_facts.get('population', 'N/A')}
- Land Area: {country_facts.get('area_km2', 'N/A')}
- Coastline / Water Access: {country_facts.get('water_access', 'N/A')}
- Neighboring Borders: {country_facts.get('borders', 'N/A')}
- Official Languages: {country_facts.get('languages', 'N/A')}
"""
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
Generate the daily blog recap for: {country_name} on {post_date.strftime('%B %d, %Y')}.

Verified Ground Truth Facts:
{facts_summary}

Wikipedia Context Excerpts:
{wiki_context}

Source excerpts can contain unresolved [citation needed] warnings. Do not use claims
marked with that warning as facts, and do not imply they have been independently verified.
No human editorial review has taken place.

TASK:
Generate a JSON object with:
1. "title": Catchy, exciting headline (e.g. "Countrydle Solution: {country_name} — [Evocative Description]").
2. "subtitle": Engaging 1-sentence teaser summarizing the country's unique deduction identity.
3. "summary": 2-3 sentence overview of the country and its daily deduction challenge.
4. "fun_facts": Exactly 2 or 3 fascinating, grammatically complete, polished curiosities about culture, geography, or history.
   Each curiosity MUST have:
   - "title": Catchy 2-4 word theme (e.g. "Alpine Wonderland", "Cradle of Classical Music", "Culinary Traditions").
   - "description": 1-2 polished, self-contained sentences. NEVER start with dangling pronouns like "This left..." or "On 11 November, the emperor...". Always clearly name {country_name} or the specific subject.
5. "trivia_quiz":
   A fun trivia question for players.
   CRITICAL RULE: The quiz question and answer MUST NOT simply repeat or copy any of the fun facts provided in "fun_facts"! It must test a different piece of cultural, historical, or geographic knowledge about {country_name}.
   - "question": Specific question string.
   - "correct_answer": Correct answer string.
   - "incorrect_distractor": Believable false answer string.
   - "explanation": 1 concise sentence explaining the correct answer.

Return ONLY the raw JSON object.
"""

    loop = asyncio.get_running_loop()
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        try:
            logger.info(f"Calling Gemini model {model_name} for blog post ({country_name})...")
            res = await loop.run_in_executor(None, _call_gemini_api, model_name, prompt, api_key, 35)
            if not isinstance(res, dict) or not res.get("fun_facts"):
                raise ValueError("Provider output must include substantive fun facts")
            payload = _assemble_blog_post_payload(country_name, country_facts, res, post_date, actual_questions)
            payload.update(_generation_provenance(wiki_fragments, ai_assisted=True))
            payload = _validate_generated_payload(payload)
            logger.info(f"Successfully generated blog content using {model_name} for {country_name}")
            return payload
        except Exception as e:
            logger.warning(f"Model {model_name} failed for {country_name}: {e}")

    logger.warning(f"All AI models failed for {country_name}, using deterministic template.")
    return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions)


def _assemble_blog_post_payload(
    country_name: str,
    country_facts: Dict[str, Any],
    ai_data: Dict[str, Any],
    post_date: date,
    actual_questions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    steps = get_deduction_steps(country_name, actual_questions)
    pro_tip = get_curator_pro_tip(country_name, country_facts)

    step_lines = "\n".join([
        f"{s['step']}. **[{s['answer']}] \"{s['question']}\"** — {s['explanation']}"
        for s in steps
    ])

    fun_facts = ai_data.get("fun_facts") or []
    curiosity_lines = "\n".join([
        f"- **{c['title']}**: {c['description']}"
        for c in fun_facts
    ])

    markdown = f"""## Yesterday's Solution: {country_name}

### The Deduction Path
{step_lines}

### Quick Facts
- **Capital**: {country_facts.get('capital', 'N/A')}
- **Region**: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- **Population**: {country_facts.get('population', 'N/A')}
- **Land Area**: {country_facts.get('area_km2', 'N/A')} ({country_facts.get('water_access', 'N/A')})
- **Bordering Neighbors**: {country_facts.get('borders', 'N/A')}
- **Official Languages**: {country_facts.get('languages', 'N/A')}

### Two Things Worth Knowing
{curiosity_lines}

### Curator's Pro Tip
> {pro_tip}"""

    deduction_masterclass = {
        "steps": steps,
        "pro_tip": pro_tip,
    }
    # An omitted quiz is legitimate; a present invalid quiz must never be dropped.
    if "trivia_quiz" in ai_data:
        deduction_masterclass["quiz"] = ai_data["trivia_quiz"]

    title = ai_data.get("title") or f"Countrydle Solution: {country_name}"
    subtitle = ai_data.get("subtitle") or f"Game recap and deduction breakdown for {post_date.strftime('%B %d, %Y')}."
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
        f"{origin} using stored country facts and retrieved local article excerpts. "
        "The article excerpts do not retain original source URLs; no external source "
        "pages were fetched for this recap. No human editorial review was recorded during generation."
    )
    if any(
        _CITATION_NEEDED.search(fragment.replace("\\", ""))
        or "citation needed" in fragment.lower()
        for fragment in wiki_fragments
    ):
        note += " Retrieved excerpts include unresolved [citation needed] warnings."
        if not ai_assisted:
            note += " Claims carrying those warnings were excluded from the template."
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
) -> Dict[str, Any]:
    country_facts = get_country_sqlite_facts(country_name)
    steps = get_deduction_steps(country_name, actual_questions)
    pro_tip = get_curator_pro_tip(country_name, country_facts)
    curiosities = extract_clean_curiosities(country_name, wiki_fragments, country_facts)

    step_lines = "\n".join([
        f"{s['step']}. **[{s['answer']}] \"{s['question']}\"** — {s['explanation']}"
        for s in steps
    ])

    curiosity_lines = "\n".join([
        f"- **{c['title']}**: {c['description']}"
        for c in curiosities
    ])

    markdown = f"""## Yesterday's Solution: {country_name}

### The Deduction Path
{step_lines}

### Quick Facts
- **Capital**: {country_facts.get('capital', 'N/A')}
- **Region**: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- **Population**: {country_facts.get('population', 'N/A')}
- **Land Area**: {country_facts.get('area_km2', 'N/A')} ({country_facts.get('water_access', 'N/A')})
- **Bordering Neighbors**: {country_facts.get('borders', 'N/A')}
- **Official Languages**: {country_facts.get('languages', 'N/A')}

### Two Things Worth Knowing
{curiosity_lines}

### Curator's Pro Tip
> {pro_tip}"""

    return _validate_generated_payload({
        "title": f"Countrydle Solution: {country_name}",
        "subtitle": f"Game recap and deduction breakdown for {post_date.strftime('%B %d, %Y')}.",
        "reading_time_minutes": 2,
        "summary": f"The Countrydle mystery country for {post_date.isoformat()} was {country_name}. This recap combines stored geographic facts with available question history.",
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
        "fun_facts": curiosities,
        "deduction_masterclass": {
            "steps": steps,
            "pro_tip": pro_tip,
        },
        "content_markdown": markdown,
        **_generation_provenance(wiki_fragments, ai_assisted=False),
    })


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

    # 3. Generate content via Gemini (with questions log and anti-slop rules)
    payload = await generate_blog_content_ai(country_name, fragments, post_date, actual_questions)
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
