"""Populate water access and major rivers in the local Countrydle SQLite KB.

The base ``build_country_facts_sqlite.py`` script fills facts available from
REST Countries and Factbook. This script fills the two relation families that
need text extraction from local Wikipedia markdown files:

- ``country_water_access``
- ``country_major_rivers``

It reads each country's article lead plus Geography section from
``data/countries/*.md`` and asks Gemini for strict JSON. The prompt
intentionally stores only main direct water bodies, not small/local bays,
lagoons, straits, channels, ports, or lakes.

Usage from repository root:
    python server/scripts/populate_country_geography_facts.py

Useful test modes:
    python server/scripts/populate_country_geography_facts.py --sample
    python server/scripts/populate_country_geography_facts.py --country Poland --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_COUNTRIES_CSV = ROOT_DIR / "data" / "countries.csv"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"
DEFAULT_MODEL = "gemini-2.5-flash-lite"
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

SAMPLE_COUNTRIES = [
    "Poland",
    "Czech Republic",
    "Spain",
    "Japan",
    "Brazil",
    "Egypt",
    "Chad",
    "Australia",
    "Thailand",
    "Norway",
]

ALLOWED_SPECIAL_WATER_BODIES = {
    "Bay of Bengal",
    "Gulf of Aden",
    "Gulf of Aqaba",
    "Gulf of Guinea",
    "Gulf of Mexico",
    "Gulf of Oman",
    "Gulf of Thailand",
    "Persian Gulf",
}

WATER_BODY_ALIASES = {
    "North Atlantic Ocean": "Atlantic Ocean",
    "South Atlantic Ocean": "Atlantic Ocean",
    "South Pacific Ocean": "Pacific Ocean",
}

EXCLUDED_WATER_BODIES = {
    "Río de la Plata",
}

COUNTRY_WATER_ACCESS_REMOVALS = {
    # Moldova has river access via the Danube, but not direct sea coastline.
    "Moldova": {"Black Sea"},
}

MINOR_WATER_BODY_KEYWORDS = (
    "Bay",
    "Channel",
    "Gulf",
    "Passage",
    "Strait",
    "Lagoon",
)

RIVER_ALIASES = {
    "Mississippi River System": "Mississippi",
}

EXCLUDED_RIVERS = {
    "Amazon Rainforest",
    "Cuvelai-Etosha Basin",
}


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_country_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def extract_lead(markdown: str) -> str:
    next_h2 = re.search(r"^##\s+", markdown, re.MULTILINE)
    return markdown[: next_h2.start()] if next_h2 else markdown


def extract_geography_section(markdown: str) -> str | None:
    match = re.search(r"^(#{2,3})\s+Geography\b.*$", markdown, re.MULTILINE)
    if not match:
        return None

    level = len(match.group(1))
    start = match.end()
    next_heading = re.search(r"^#{2," + str(level) + r"}\s+", markdown[start:], re.MULTILINE)
    return markdown[start : start + next_heading.start()] if next_heading else markdown[start:]


def build_prompt(country_name: str, source_text: str) -> str:
    return f"""
You extract structured geography facts for a country guessing game.
Use ONLY the provided Wikipedia lead and Geography sections. Do not use outside knowledge.

Country: {country_name}

Return STRICT JSON only with this schema:
{{
  "water_access": ["main direct sea/ocean or globally significant gulf names"],
  "major_rivers": ["major river names that flow through or form borders of the country"],
  "notes": "short note about ambiguity or missing info, or null"
}}

Rules for water_access:
- Include only MAIN direct seas/oceans that the country directly borders or has a coastline on.
- Include a gulf only if it is a globally significant primary coastline water body, e.g. "Persian Gulf", "Gulf of Mexico", "Gulf of Thailand", "Gulf of Guinea".
- Do NOT include small/local bays, minor gulfs, lagoons, straits, channels, ports, lakes, reservoirs, or rivers.
- Do NOT infer parent water bodies unless the section directly names the main sea/ocean.
- If the country is landlocked, return an empty array.
- Examples of desired values: "Baltic Sea", "Mediterranean Sea", "Atlantic Ocean", "Pacific Ocean", "Indian Ocean", "Red Sea", "Black Sea", "Persian Gulf".

Rules for major_rivers:
- Include only notable/major rivers mentioned in the section.
- Include rivers that flow through the country or form its borders.
- Do not include canals, lakes, seas, watersheds, drainage basins, or tiny local streams unless clearly described as major/notable.
- Use common English names.

General rules:
- Prefer concise canonical English names.
- Remove duplicates.
- If none are found, use an empty array.

Wikipedia lead and Geography sections:
---
{source_text}
---
""".strip()


def call_gemini(prompt: str, model: str, api_key: str, retries: int = 3) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    url = GEMINI_URL_TEMPLATE.format(model=model, key=api_key)

    for attempt in range(1, retries + 1):
        request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
            raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return json.loads(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            if attempt == retries:
                raise RuntimeError(f"Gemini extraction failed after {retries} attempts: {exc}") from exc
            time.sleep(10 * attempt)

    raise RuntimeError("Gemini extraction failed")


def clean_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key not in seen:
            cleaned.append(normalized)
            seen.add(key)
    return cleaned


def clean_rivers(values: object) -> list[str]:
    rivers = clean_values(values)
    cleaned = []
    seen = set()
    for river in rivers:
        river = re.sub(r"\s+Rivers?$", "", river, flags=re.IGNORECASE).strip()
        river = RIVER_ALIASES.get(river, river)
        if river in EXCLUDED_RIVERS:
            continue
        key = river.casefold()
        if key not in seen:
            cleaned.append(river)
            seen.add(key)
    return cleaned


def clean_water_access(country_name: str, values: object) -> list[str]:
    water_bodies = clean_values(values)
    cleaned = []
    seen = set()
    for water_body in water_bodies:
        water_body = WATER_BODY_ALIASES.get(water_body, water_body)
        if water_body in EXCLUDED_WATER_BODIES:
            continue
        if water_body in COUNTRY_WATER_ACCESS_REMOVALS.get(country_name, set()):
            continue
        if water_body in ALLOWED_SPECIAL_WATER_BODIES:
            key = water_body.casefold()
            if key not in seen:
                cleaned.append(water_body)
                seen.add(key)
            continue
        if any(keyword in water_body for keyword in MINOR_WATER_BODY_KEYWORDS):
            continue
        key = water_body.casefold()
        if key not in seen:
            cleaned.append(water_body)
            seen.add(key)
    return cleaned


def get_country_id(connection: sqlite3.Connection, country_name: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM countries WHERE app_country_name = ?",
        (country_name,),
    ).fetchone()
    return int(row[0]) if row else None


def replace_geography_facts(
    connection: sqlite3.Connection,
    country_id: int,
    water_access: list[str],
    major_rivers: list[str],
) -> None:
    connection.execute("DELETE FROM country_water_access WHERE country_id = ?", (country_id,))
    connection.execute("DELETE FROM country_major_rivers WHERE country_id = ?", (country_id,))

    for water_body in water_access:
        connection.execute(
            "INSERT OR IGNORE INTO country_water_access(country_id, water_body) VALUES (?, ?)",
            (country_id, water_body),
        )
    for river_name in major_rivers:
        connection.execute(
            "INSERT OR IGNORE INTO country_major_rivers(country_id, river_name) VALUES (?, ?)",
            (country_id, river_name),
        )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--countries-csv", type=Path, default=DEFAULT_COUNTRIES_CSV)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--country", action="append", help="Only process selected country name; can be repeated")
    parser.add_argument("--sample", action="store_true", help="Process a fixed sample of countries")
    parser.add_argument("--limit", type=int, help="Process at most N countries after filtering")
    parser.add_argument("--dry-run", action="store_true", help="Print extraction results without writing SQLite")
    parser.add_argument("--sleep", type=float, default=6.0, help="Seconds to sleep between API calls")
    args = parser.parse_args()

    load_dotenv(ROOT_DIR / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY missing")
        return 1

    rows = read_country_rows(args.countries_csv)
    selected = set(args.country or [])
    if args.sample:
        selected.update(SAMPLE_COUNTRIES)
    if selected:
        rows = [row for row in rows if row["name"] in selected]
    if args.limit is not None:
        rows = rows[: args.limit]

    connection = None if args.dry_run else sqlite3.connect(args.db)
    if connection is not None:
        connection.execute("PRAGMA foreign_keys = ON")

    processed = 0
    missing_sections: list[str] = []
    missing_db: list[str] = []
    failures: list[tuple[str, str]] = []

    try:
        for row in rows:
            country_name = row["name"].strip()
            md_path = ROOT_DIR / row["md_file"]
            markdown = md_path.read_text(encoding="utf-8")
            geography = extract_geography_section(markdown)
            if not geography:
                missing_sections.append(country_name)
                continue
            source_text = f"# Lead\n{extract_lead(markdown)}\n\n# Geography\n{geography}"

            try:
                result = call_gemini(build_prompt(country_name, source_text), args.model, api_key)
            except RuntimeError as exc:
                failures.append((country_name, str(exc)))
                continue

            water_access = clean_water_access(country_name, result.get("water_access"))
            major_rivers = clean_rivers(result.get("major_rivers"))
            notes = result.get("notes")

            print(f"{country_name}: water={water_access}; rivers={major_rivers}; notes={notes}")

            if connection is not None:
                country_id = get_country_id(connection, country_name)
                if country_id is None:
                    missing_db.append(country_name)
                    continue
                replace_geography_facts(connection, country_id, water_access, major_rivers)
                connection.commit()

            processed += 1
            if args.sleep:
                time.sleep(args.sleep)
    finally:
        if connection is not None:
            connection.close()

    print(f"Processed countries: {processed}")
    if missing_sections:
        print("Missing Geography sections:")
        for country_name in missing_sections:
            print(f"- {country_name}")
    if missing_db:
        print("Missing countries in SQLite:")
        for country_name in missing_db:
            print(f"- {country_name}")
    if failures:
        print("Failures:")
        for country_name, error in failures:
            print(f"- {country_name}: {error}")

    return 1 if failures or missing_db else 0


if __name__ == "__main__":
    sys.exit(main())
