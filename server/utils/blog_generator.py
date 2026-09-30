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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found, falling back to deterministic template.")
        return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions)
    country_facts = get_country_sqlite_facts(country_name)
    facts_summary = f"""
- Capital: {country_facts.get('capital', 'N/A')}
- Continent & Region: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- Population: {country_facts.get('population', 'N/A')}
- Land Area: {country_facts.get('area_km2', 'N/A')}
- Coastline / Water Access: {country_facts.get('water_access', 'N/A')}
- Neighboring Borders: {country_facts.get('borders', 'N/A')}
- Official Languages: {country_facts.get('languages', 'N/A')}
"""

    if actual_questions:
        q_log = "\n".join([f"- [{q['answer']}] \"{q['question']}\" -> Outcome: {q['explanation']}" for q in actual_questions[:10]])
    else:
        q_log = f"- [YES] \"Is the country in {country_facts.get('continent', 'the continent')}?\"\n- [{ 'YES' if 'Landlocked' not in country_facts.get('water_access', '') else 'NO'}] \"Does it have maritime sea access?\"\n- [YES] \"Does it border its regional neighbors?\""

    prompt = f"""You are the lead geography editor and game analyst for Countrydle (a daily geography deduction game).
Yesterday's secret target country was {country_name} on {post_date.strftime('%B %d, %Y')}.

Verified Geographic Identity Facts:
{facts_summary}

Actual Questions Asked by Players in Yesterday's Game:
{q_log}

Authentic Wikipedia Excerpts:
---
{"---".join(wiki_fragments[:6])}
---

ANTI-AI-SLOP & AUTHENTICITY RULES (STRICT):
1. FORBIDDEN CLICHÉS (NEVER USE ANY OF THESE UNDER ANY CIRCUMSTANCES):
   - "Nestled in..."
   - "A tapestry of..."
   - "Boasts a rich..."
   - "Vibrant culture / vibrant nation"
   - "Whether you're a seasoned traveler or an armchair explorer"
   - "In conclusion..."
   - "Embark on a journey"
   - "Beacon of..."
   - "Steeped in history"
2. VOICE & TONE:
   - Analytical, concise, factual, and crisp—like a seasoned match analyst reviewing a game.
   - Use active voice, short paragraphs (2-3 sentences max).
   - Use real numbers, real border names, and reference the ACTUAL questions asked by players from the log above.
3. STRUCTURE OF 'content_markdown':
   ## Yesterday's Mystery Country: {country_name}
   [Direct 2-sentence intro confirming the secret country and community difficulty]

   ### 📌 Main Facts at a Glance
   - 🏛️ **Capital**: {country_facts.get('capital', 'N/A')}
   - 🌍 **Continent & Region**: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
   - 👥 **Population**: {country_facts.get('population', 'N/A')}
   - 📏 **Land Area**: {country_facts.get('area_km2', 'N/A')}
   - 🌊 **Coastline & Water Access**: {country_facts.get('water_access', 'N/A')}
   - 🗺️ **Neighboring Borders**: {country_facts.get('borders', 'N/A')}
   - 🗣️ **Official Languages**: {country_facts.get('languages', 'N/A')}

   ### 🎮 The Deduction Breakdown (Real Player Questions)
   [Analyze the actual questions from the log above: what was the first macro move, what ruled out the closest rivals, and what was the winning clue that clinched the game]

   ### 🌿 Geography & Natural Landscape
   [1-2 crisp, informative paragraphs on the terrain, river basins, or mountain systems]

   ### 💡 Did You Know?
   > **[Authentic fact title from Wiki fragments]**: [Detailed, accurate explanation]

   ### 🎯 Countrydle Pro Deduction Tip
   > **Pro Tip**: [A practical tactical tip for identifying this country in future games]

Format the output as a valid JSON object with the exact keys:
{{
  "title": "A compelling headline (e.g. 'Yesterday's Countrydle: Uncovering {country_name}')",
  "subtitle": "An engaging 1-sentence teaser summarizing what made yesterday's puzzle unique",
  "reading_time_minutes": 2,
  "summary": "2-3 sentence overview of yesterday's game and the country's geographic identity",
  "fast_facts": {{
    "capital": "{country_facts.get('capital', 'N/A')}",
    "continent": "{country_facts.get('continent', 'N/A')}",
    "population": "{country_facts.get('population', 'N/A')}",
    "area": "{country_facts.get('area_km2', 'N/A')}",
    "coastline": "{country_facts.get('water_access', 'N/A')}",
    "borders": "{country_facts.get('borders', 'N/A')}",
    "languages": "{country_facts.get('languages', 'N/A')}"
  }},
  "fun_facts": [
    {{"title": "Intriguing Fact 1 Title", "description": "Fascinating narrative explanation using the provided Wikipedia context."}},
    {{"title": "Intriguing Fact 2 Title", "description": "Fascinating narrative explanation."}},
    {{"title": "Intriguing Fact 3 Title", "description": "Fascinating narrative explanation."}}
  ],
  "deduction_masterclass": {{
    "step_1": "How smart players eliminate hemispheres or continents early",
    "step_2": "The decisive border or maritime question that isolated the region",
    "winning_clue": "The final signature characteristic that locked in the correct guess"
  }},
  "content_markdown": "Markdown following the structure above without any AI clichés."
}}
Return only valid JSON."""

    # Try Primary Model (gemini-3.1-pro-preview)
    try:
        logger.info(f"Generating daily blog post with primary model {PRIMARY_MODEL} for {country_name}...")
        result = await asyncio.to_thread(_call_gemini_api, PRIMARY_MODEL, prompt, api_key, 30)
        return result
    except Exception as e:
        logger.warning(f"Primary model {PRIMARY_MODEL} failed: {e}. Trying fallback model {FALLBACK_MODEL}...")

    # Try Fallback Model (gemini-3.8-flash)
    try:
        result = await asyncio.to_thread(_call_gemini_api, FALLBACK_MODEL, prompt, api_key, 20)
        return result
    except Exception as e:
        logger.error(f"Fallback model {FALLBACK_MODEL} failed: {e}. Generating deterministic fallback.")

    return _generate_fallback_template(country_name, wiki_fragments, post_date, actual_questions)


def _generate_fallback_template(
    country_name: str, 
    wiki_fragments: List[str], 
    post_date: date,
    actual_questions: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    country_facts = get_country_sqlite_facts(country_name)
    facts = []
    for i, frag in enumerate(wiki_fragments[:3]):
        snippet = frag.strip().split("\n")[0]
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        facts.append({
            "title": f"Fascinating Fact #{i + 1}",
            "description": snippet or f"An official Wikipedia excerpt detailing {country_name}'s cultural and geographic heritage."
        })

    while len(facts) < 3:
        facts.append({
            "title": "Did You Know?",
            "description": f"{country_name} was yesterday's featured country on Countrydle."
        })

    pro_tip = f"When deducing {country_name}, check whether it borders {country_facts.get('borders', 'its neighbors')} or has access to {country_facts.get('water_access', 'the sea')}. This immediately narrows the global search space down to single-digit candidates!"
    if actual_questions:
        q_section = "### 🎮 The Deduction Breakdown (Real Player Questions)\n"
        q_section += "Yesterday's solvers tackled the puzzle with these pivotal questions:\n"
        for q in actual_questions[:5]:
            badge = "✅ YES" if q["answer"] == "YES" else "❌ NO"
            q_section += f"- **{badge}** \"{q['question']}\": {q['explanation']}\n"
    else:
        q_section = f"""### 🎮 The Deduction Breakdown (Optimal Strategy)
1. **Macro Triangulation**: Start by verifying {country_facts.get('continent', 'the continent')} and hemisphere orientation.
2. **Maritime Check**: Confirming whether {country_name} has coastline access ({country_facts.get('water_access', 'coastlines')}) eliminates non-coastal candidates.
3. **Border Anchors**: Querying adjacent borders ({country_facts.get('borders', 'neighboring nations')}) isolates {country_name}."""

    markdown = f"""## Yesterday's Mystery Country: {country_name}

Every day at midnight UTC, Countrydle challenges players to deduce a secret nation using spatial elimination. Yesterday's target was **{country_name}**!

### 📌 Main Facts at a Glance
- 🏛️ **Capital**: {country_facts.get('capital', 'N/A')}
- 🌍 **Continent & Region**: {country_facts.get('continent', 'N/A')} ({country_facts.get('region', 'N/A')})
- 👥 **Population**: {country_facts.get('population', 'N/A')}
- 📏 **Land Area**: {country_facts.get('area_km2', 'N/A')}
- 🌊 **Coastline & Water Access**: {country_facts.get('water_access', 'N/A')}
- 🗺️ **Neighboring Borders**: {country_facts.get('borders', 'N/A')}
- 🗣️ **Official Languages**: {country_facts.get('languages', 'N/A')}

{q_section}
### 🌿 Geography & Landscape
{country_name} is located in {country_facts.get('continent', 'the world')}, encompassing {country_facts.get('area_km2', 'an extensive territory')}. Its unique physical terrain features diverse biomes and important transportation and river corridors.

### 💡 Did You Know?
> **{facts[0]['title']}**: {facts[0]['description']}

### 🏛️ Fascinating Curiosities from Wikipedia
{chr(10).join([f"- **{f['title']}**: {f['description']}" for f in facts[1:]])}

### 🎯 Countrydle Pro Deduction Tip
> **Pro Tip**: {pro_tip}
---
*Ready to test your geography skills today? Jump into [Countrydle](/) and see if you can solve today's daily puzzle!*"""

    return {
        "title": f"Yesterday's Countrydle: Uncovering the Wonders of {country_name}",
        "subtitle": f"Yesterday's mystery location revealed: discovering the geography, culture, and trivia of {country_name}.",
        "reading_time_minutes": 2,
        "summary": f"On {post_date.strftime('%B %d, %Y')}, Countrydle players tackled the challenge of deducing {country_name}. Explore its geography, historical heritage, and key trivia facts.",
        "fast_facts": {
            "capital": country_facts.get("capital", "N/A"),
            "continent": country_facts.get("continent", "N/A"),
            "population": country_facts.get("population", "N/A"),
            "area": country_facts.get("area_km2", "N/A"),
            "coastline": country_facts.get("water_access", "N/A"),
            "borders": country_facts.get("borders", "N/A"),
            "languages": country_facts.get("languages", "N/A"),
        },
        "fun_facts": facts,
        "deduction_masterclass": {
            "step_1": f"Start with hemisphere and continent checks to isolate {country_facts.get('continent', 'the region')}.",
            "step_2": f"Ask about maritime access: {country_facts.get('water_access', 'coastlines')} isolates the candidates.",
            "winning_clue": f"Confirm border neighbors ({country_facts.get('borders', 'adjacent nations')}) to lock in {country_name}."
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
