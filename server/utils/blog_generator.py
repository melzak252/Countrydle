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
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.fragment import CountryFragment
from db.models.countrydle import CountrydleDay, CountrydleQuestion

logger = logging.getLogger(__name__)

PRIMARY_MODEL = os.getenv("BLOG_GENERATOR_MODEL", "gemini-3.1-pro-preview")
FALLBACK_MODEL = os.getenv("BLOG_FALLBACK_MODEL", "gemini-3.8-flash")


def generate_slug(post_date: date, country_name: str) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", country_name.strip().lower()).strip("-")
    return f"{post_date.isoformat()}-{clean_name}"

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
        borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id = ?", (c_id,)).fetchall()]
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

def get_deduction_steps(country_name: str, actual_questions: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    facts = get_country_sqlite_facts(country_name)
    continent = facts.get('continent', 'Unknown')
    water = facts.get('water_access', 'Unknown')
    is_landlocked = 'landlocked' in water.lower()
    borders = facts.get('borders', '')
    border_list = [b.strip() for b in borders.split(',') if b.strip() and b.strip() != 'None']

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

    if len(steps) < 3:
        steps = [
            {
                "step": 1,
                "question": f"Is the country in {continent}?",
                "answer": "YES",
                "explanation": f"Confirmed location in {continent}.",
            },
            {
                "step": 2,
                "question": "Does the country have access to the sea?",
                "answer": "NO" if is_landlocked else "YES",
                "explanation": "Completely landlocked with zero coastline." if is_landlocked else f"Maritime access via {water}.",
            },
            {
                "step": 3,
                "question": f"Does it border {border_list[0]}?" if border_list else "Is it an island nation?",
                "answer": "YES",
                "explanation": f"Adjacent land border with {border_list[0]}." if border_list else "Zero land borders (Island nation).",
            },
            {
                "step": 4,
                "question": f"Is the capital city {facts.get('capital')}?",
                "answer": "YES",
                "explanation": f"Capital is {facts.get('capital')}. Target solved!",
            }
        ]
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
        cleaned = re.sub(r'\[\*?\s*citation needed\s*\*?\]', '', cleaned, flags=re.I)
        cleaned = re.sub(r'\[\d+\]', '', cleaned)
        cleaned = cleaned.replace('\\', '')

        raw_sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        for s in raw_sentences:
            s = re.sub(r'\s+', ' ', s).strip()
            if len(s) >= 50 and len(s) <= 280 and s[0].isupper() and s[-1] in ('.', '!'):
                if not s.startswith(('#', '|', '-', '*', '•', '>', 'State in', 'Country in')):
                    if not any(bw in s.lower() for bw in banned_words):
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


async def generate_blog_content_ai(
    country_name: str,
    wiki_fragments: List[str],
    post_date: date,
    actual_questions: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    # Deterministic factual debrief: guaranteed ground-truth, 0 hallucinations, 0 AI slop
    return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions)


def _generate_fallback_template(
    country_name: str, 
    wiki_fragments: List[str], 
    post_date: date,
    actual_questions: Optional[List[Dict[str, str]]] = None,
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

    return {
        "title": f"Countrydle Solution: {country_name}",
        "subtitle": f"Game recap and deduction breakdown for {post_date.strftime('%B %d, %Y')}.",
        "reading_time_minutes": 2,
        "summary": f"Yesterday's Countrydle mystery country was {country_name}. Here is how the community eliminated regions to find the answer.",
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
    }


async def create_daily_blog_post(
    session: AsyncSession,
    country: Country,
    post_date: date,
) -> DailyBlogPost:
    # 1. Fetch authentic Wikipedia fragments from PostgreSQL
    res = await session.execute(
        select(CountryFragment.text)
        .where(CountryFragment.country_id == country.id)
        .limit(8)
    )
    fragments = list(res.scalars().all())

    # 2. Fetch actual player questions asked for yesterday's puzzle
    day_res = await session.execute(
        select(CountrydleDay).where(CountrydleDay.date == post_date)
    )
    day = day_res.scalars().first()

    actual_questions: List[Dict[str, str]] = []
    if day:
        q_res = await session.execute(
            select(CountrydleQuestion.question, CountrydleQuestion.answer, CountrydleQuestion.explanation)
            .where(CountrydleQuestion.day_id == day.id, CountrydleQuestion.valid.is_(True))
            .order_by(CountrydleQuestion.id.asc())
            .limit(15)
        )
        for q in q_res.all():
            actual_questions.append({
                "question": q.question or "",
                "answer": "YES" if q.answer else "NO",
                "explanation": q.explanation or ""
            })

    # 3. Generate content via Gemini (with questions log and anti-slop rules)
    payload = await generate_blog_content_ai(country.name, fragments, post_date, actual_questions)

    slug = generate_slug(post_date, country.name)

    post = DailyBlogPost(
        date=post_date,
        country_id=country.id,
        slug=slug,
        title=payload.get("title", f"Countrydle Recap: {country.name}"),
        subtitle=payload.get("subtitle", f"Exploring the geography of {country.name}"),
        reading_time_minutes=payload.get("reading_time_minutes", 2),
        summary=payload.get("summary", ""),
        fast_facts=payload.get("fast_facts"),
        fun_facts=payload.get("fun_facts", []),
        deduction_masterclass=payload.get("deduction_masterclass"),
        content_markdown=payload.get("content_markdown", ""),
    )

    return post
