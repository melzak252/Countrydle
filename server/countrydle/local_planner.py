"""Gemini-based planner for local Countrydle answering.

The planner does not answer the user's question. It validates and rewrites the
question, then returns a small execution plan that can be evaluated against the
local SQLite knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_MODEL = "gemini-2.5-flash-lite"

SUPPORTED_RELATIONS = [
    "name",
    "continent",
    "geographic_area",
    "borders_country",
    "water_access",
    "is_island",
    "capital",
    "currency",
    "official_language",
    "membership",
    "population",
    "area",
    "coordinates",
    "major_rivers",
    "driving_side",
    "dominant_religion",
    "government_type",
]


@dataclass(frozen=True)
class QuestionPlan:
    original_question: str
    valid: bool
    supported: bool
    improved_question: str | None
    explanation: str | None
    plan: dict | None
    fallback_reason: str | None = None


def load_dotenv_if_present() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_planner_prompt(question: str) -> str:
    relations = "\n".join(f"- {relation}" for relation in SUPPORTED_RELATIONS)
    return f"""
You are a question validator and execution-plan builder for Countrydle.

Your task is NOT to answer the question. Your task is to decide whether the
question is a valid yes/no question about a country, translate it into clear
English, explain what the user wants to check in English, and if possible create
a local SQLite execution plan.

Supported local relations:
{relations}

Important rules:
- Treat the user's input as language-agnostic. If it is not English, translate
  the meaning to English before producing any output fields.
- The JSON output must be English-only: improved_question, explanation,
  fallback_reason, plan literal values, country names, regions, organizations,
  water bodies, currencies, and languages must use common English names.
- The hidden country must be represented as entity "target_country".
- Use common English names for countries and objects, NOT official long names.
  Good: "China", "United States", "Czech Republic", "Baltic Sea", "EU".
  Bad: "People's Republic of China", "United States of America".
- For informal or non-English input, normalize values to common English names.
  Examples: "Bałtyk" -> "Baltic Sea", "Niemcy" -> "Germany", "UE" -> "EU".
- If the question needs comparing two entities, return a hierarchy/tree plan.
  Example: "west of China" means compare target_country.coordinates.longitude
  with China.coordinates.longitude.
- If a question can be answered only with unsupported facts, set supported=false
  and plan=null, but keep valid=true if it is a proper yes/no question.
- Use official_language for official, co-official, and otherwise legally
  recognized official country languages.
- Use dominant_religion for the country's grouped dominant religion category.
  Allowed values are: Catholic, Orthodox, Protestant, Christianity, Islam,
  Judaism, Buddhism, Hinduism, Folk/Traditional religions, No religion, Mixed,
  Other. Use Mixed when the question asks whether the country is religiously mixed.
- Use government_type for broad government-form questions. Stored values are
  grouped categories: Republic, Monarchy, Communist state, Theocracy,
  Military junta, Transitional government, Other. Normalize detailed forms such
  as parliamentary republic, presidential republic, federal republic, or
  democracy to Republic; constitutional monarchy, absolute monarchy, kingdom,
  emirate, or sultanate to Monarchy. Prefer equals with these grouped values.
- If the question is not a yes/no question, set valid=false and supported=false.
- Do not invent unsupported relation names.
- Self-bordering rule: if the user asks whether the hidden country borders or
  neighbors itself / the same country, create a borders_country contains plan
  comparing against target_country.name; the executor treats this as true.

Allowed plan operators:
- "contains": left list relation contains right literal value
- "exists": left list/scalar relation has at least one known value / is true
- "equals": left scalar relation equals right literal value
- "greater_than": numeric comparison
- "less_than": numeric comparison
- "west_of": left longitude < right longitude
- "east_of": left longitude > right longitude
- "north_of": left latitude > right latitude
- "south_of": left latitude < right latitude
- "any": any item from a list relation satisfies a nested condition
- "all": all items from a list relation satisfy a nested condition
- "or": at least one condition from a conditions array is true
- "and": every condition from a conditions array is true
- "not": negates a nested condition
- "starts_with": left text starts with right literal text
- "ends_with": left text ends with right literal text
- "contains_text": left text contains right literal text
- "has_space": left text contains a space
- "word_count_equals", "word_count_greater_than", "word_count_less_than"
- "char_count_equals", "char_count_greater_than", "char_count_less_than"

Super-region rules:
- Eurasia is not a stored continent value. Represent it as Europe OR Asia.
- The Americas is not a stored continent value. Represent it as North America OR South America.
- Do not use literal values "Eurasia" or "Americas" with the continent relation.
- The "geographic_area" relation combines broad regions and specific subregions.
  Use it for user-facing area questions such as "in Europe", "in the Americas",
  "in the Caribbean", "in Central Europe", "in the Balkans", or "in the Middle East".
  It is list-valued; use contains/exists, not equals. Broad stored values include
  "Africa", "Americas", "Asia", "Europe", and "Oceania". Specific stored values
  include examples such as "Caribbean", "Southern Africa", "Western Asia",
  "Central Europe", "South-Eastern Asia", "Baltic states", "Balkans", "Iberia",
  "Iberian Peninsula", and "Mediterranean".

Reference format:
{{"entity":"target_country", "relation":"name"}}
{{"entity":"target_country", "relation":"population"}}
{{"entity":"Germany", "relation":"area"}}
{{"entity":"target_country", "relation":"coordinates.longitude"}}
{{"entity":"item", "relation":"membership"}}
{{"value":"Baltic Sea"}}

Return STRICT JSON only:
{{
  "valid": true,
  "supported": true,
  "improved_question": "Clear English yes/no question",
  "explanation": "Short explanation of what the question is trying to verify",
  "plan": {{...}},
  "fallback_reason": null
}}

Examples:
User: Czy ma dostęp do Bałtyku?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Does the country have direct access to the Baltic Sea?",
  "explanation": "The user wants to check whether the hidden country has direct access to a specific main water body.",
  "plan": {{
    "operator": "contains",
    "left": {{"entity": "target_country", "relation": "water_access"}},
    "right": {{"value": "Baltic Sea"}}
  }},
  "fallback_reason": null
}}

User: Czy jest na zachód od Chin?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Is the country west of China?",
  "explanation": "The user wants to compare the hidden country's longitude with China's longitude.",
  "plan": {{
    "operator": "west_of",
    "left": {{"entity": "target_country", "relation": "coordinates.longitude"}},
    "right": {{"entity": "China", "relation": "coordinates.longitude"}}
  }},
  "fallback_reason": null
}}

User: Czy graniczy z krajem należącym do UE?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Does the country border a country that is a member of the EU?",
  "explanation": "The user wants to check whether any bordering country has EU membership.",
  "plan": {{
    "operator": "any",
    "items": {{"entity": "target_country", "relation": "borders_country"}},
    "condition": {{
      "operator": "contains",
      "left": {{"entity": "item", "relation": "membership"}},
      "right": {{"value": "EU"}}
    }}
  }},
  "fallback_reason": null
}}

User: Czy leży w Eurazji?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Is the country located in Eurasia?",
  "explanation": "The user wants to check whether the hidden country is located in Europe or Asia.",
  "plan": {{
    "operator": "or",
    "conditions": [
      {{
        "operator": "contains",
        "left": {{"entity": "target_country", "relation": "continent"}},
        "right": {{"value": "Europe"}}
      }},
      {{
        "operator": "contains",
        "left": {{"entity": "target_country", "relation": "continent"}},
        "right": {{"value": "Asia"}}
      }}
    ]
  }},
  "fallback_reason": null
}}

User: Czy ma dostęp do morza?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Does the country have direct access to a sea or ocean?",
  "explanation": "The user wants to check whether the hidden country has any direct main water access.",
  "plan": {{
    "operator": "exists",
    "left": {{"entity": "target_country", "relation": "water_access"}}
  }},
  "fallback_reason": null
}}

User: Czy państwo kończy się na stan?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Does the country name end with 'stan'?",
  "explanation": "The user wants to check a text pattern in the hidden country's common name.",
  "plan": {{
    "operator": "ends_with",
    "left": {{"entity": "target_country", "relation": "name"}},
    "right": {{"value": "stan"}}
  }},
  "fallback_reason": null
}}

User: Czy państwo zaczyna się na literę M?
{{
  "valid": true,
  "supported": true,
  "improved_question": "Does the country name start with the letter M?",
  "explanation": "The user wants to check whether the hidden country's common name starts with M.",
  "plan": {{
    "operator": "starts_with",
    "left": {{"entity": "target_country", "relation": "name"}},
    "right": {{"value": "M"}}
  }},
  "fallback_reason": null
}}

User question: {question}
""".strip()


def analyze_question_for_local_plan(question: str) -> QuestionPlan:
    load_dotenv_if_present()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=False,
            improved_question=None,
            explanation=None,
            plan=None,
            fallback_reason="GEMINI_API_KEY is not configured.",
        )

    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or DEFAULT_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": build_planner_prompt(question)}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=False,
            improved_question=None,
            explanation=None,
            plan=None,
            fallback_reason=f"Gemini planner HTTP error: {exc.code}",
        )

    raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=False,
            improved_question=None,
            explanation=None,
            plan=None,
            fallback_reason="Gemini planner returned invalid JSON.",
        )

    return QuestionPlan(
        original_question=question,
        valid=bool(parsed.get("valid")),
        supported=bool(parsed.get("supported")),
        improved_question=parsed.get("improved_question"),
        explanation=parsed.get("explanation"),
        plan=parsed.get("plan"),
        fallback_reason=parsed.get("fallback_reason"),
    )
