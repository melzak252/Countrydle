import asyncio
import json
import logging
import os
import re
import urllib.request
from datetime import date
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
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found, falling back to deterministic template.")
        return _generate_fallback_template(country_name, wiki_fragments, post_date)

    prompt = f"""You are the lead geography editor and viral trivia writer for Countrydle (a daily geography deduction game).
Yesterday's secret target country was {country_name} on {post_date.strftime('%B %d, %Y')}.

Here are verified excerpts directly from its Wikipedia page:
---
{"---".join(wiki_fragments[:6])}
---

Write an engaging, authoritative, and educational recap article for Countrydle players and geography enthusiasts.
Format the output as a valid JSON object with the exact keys:
{{
  "title": "A compelling, viral-worthy headline (e.g. 'Yesterday's Countrydle: Uncovering the Wonders of {country_name}')",
  "subtitle": "An engaging 1-sentence teaser summarizing what makes {country_name} unique",
  "reading_time_minutes": 2,
  "summary": "2-3 sentence overview of yesterday's game and the country's global significance",
  "fast_facts": {{
    "continent": "Continent name",
    "capital": "Capital city",
    "water_access": "Maritime ocean or Landlocked",
    "notable_feature": "Key geographic feature"
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
  "content_markdown": "Full educational article in Markdown format with ## headings, bullet points, engaging prose explaining the history, nature, and deduction strategy, concluding with an encouraging invitation to play today's game."
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

    return _generate_fallback_template(country_name, wiki_fragments, post_date)


def _generate_fallback_template(
    country_name: str, wiki_fragments: List[str], post_date: date
) -> Dict[str, Any]:
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
            "title": f"Did You Know?",
            "description": f"{country_name} was yesterday's featured country on Countrydle."
        })

    return {
        "title": f"Countrydle Daily Recap: Exploring {country_name}",
        "subtitle": f"Yesterday's mystery location revealed: discovering the geography, culture, and trivia of {country_name}.",
        "reading_time_minutes": 2,
        "summary": f"On {post_date.strftime('%B %d, %Y')}, Countrydle players tackled the challenge of deducing {country_name}. Explore its geography, historical heritage, and key trivia facts.",
        "fast_facts": {
            "country": country_name,
            "status": "Sovereign Nation",
        },
        "fun_facts": facts,
        "deduction_masterclass": {
            "step_1": "Test hemisphere and continent boundaries to narrow down the quadrant.",
            "step_2": "Inquire about oceanic coastline and neighboring sovereign states.",
            "winning_clue": f"Confirm demographic thresholds and capital city attributes for {country_name}."
        },
        "content_markdown": f"""## Yesterday's Mystery Country: {country_name}

Every day at midnight UTC, Countrydle challenges players to deduce a secret nation using spatial elimination. Yesterday's target was **{country_name}**!

### Key Wikipedia Facts
{chr(10).join([f"- **{f['title']}**: {f['description']}" for f in facts])}

### Optimal Deduction Strategy
1. **Macro Triangulation**: Start with hemisphere checks (Northern vs Southern Hemisphere) to immediately divide the world's nations.
2. **Coastline Checks**: Determine whether {country_name} has maritime sea access or is landlocked.
3. **Neighbor Frontiers**: Ask about key hub borders to zero in on the exact territory.

---
*Think you can deduce today's secret location in fewer guesses? Jump into [Countrydle](/) and put your geography knowledge to the test!*"""
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

    # 2. Generate content via Gemini 3.1 Pro (with fallback)
    payload = await generate_blog_content_ai(country.name, fragments, post_date)

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
