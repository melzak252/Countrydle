"""Populate/refresh country region label lists for Countrydle SQLite KB.

The base `build_country_facts_sqlite.py` script fills REST Countries scalar
columns and seeds list tables. This script derives additional commonly accepted
regional labels from local Wikipedia markdown without sending whole articles to
Gemini. It builds a compact evidence packet from the lead, geography/location
sections, and short keyword windows, then asks Gemini to select labels from an
allowed vocabulary and upserts them into `country_regions` / `country_subregions`.

Usage:
    python server/scripts/populate_country_region_facts.py

Examples:
    python server/scripts/populate_country_region_facts.py --sample --dry-run
    python server/scripts/populate_country_region_facts.py --country Poland --dry-run
    python server/scripts/populate_country_region_facts.py --replace-lists --limit 20
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
    "Germany",
    "Spain",
    "Japan",
    "United States",
    "Brazil",
    "Egypt",
    "Australia",
    "South Africa",
    "Canada",
]

BROAD_REGIONS = {
    "Africa",
    "Americas",
    "Asia",
    "Europe",
    "Oceania",
}

REGIONAL_LABEL_VOCAB = {
    # UN / REST Countries-style subregions.
    "Australia and New Zealand",
    "Caribbean",
    "Central America",
    "Central Asia",
    "Central Europe",
    "Eastern Africa",
    "Eastern Asia",
    "Eastern Europe",
    "Melanesia",
    "Micronesia",
    "Middle Africa",
    "North America",
    "Northern Africa",
    "Northern Europe",
    "Polynesia",
    "South America",
    "South-Eastern Asia",
    "Southeast Europe",
    "Southern Africa",
    "Southern Asia",
    "Southern Europe",
    "Western Africa",
    "Western Asia",
    "Western Europe",
    # Common cultural / geopolitical / physical-geography labels useful in game questions.
    "Arabian Peninsula",
    "Baltic states",
    "Balkans",
    "Benelux",
    "British Isles",
    "Caucasus",
    "Central Africa",
    "East Africa",
    "East Asia",
    "Horn of Africa",
    "Iberia",
    "Iberian Peninsula",
    "Indian subcontinent",
    "Levant",
    "Maghreb",
    "Mediterranean",
    "Middle East",
    "Nordic countries",
    "Oceania",
    "Polynesia",
    "Sahel",
    "Scandinavia",
    "South Asia",
    "Southeast Asia",
    "Transcaucasia",
    "West Africa",
}

SECTION_HEADING_PATTERN = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
REGION_KEYWORDS = sorted(
    {
        "region",
        "located",
        "situated",
        "lies",
        "peninsula",
        "balkan",
        "iberia",
        "iberian",
        "baltic",
        "caucasus",
        "levant",
        "maghreb",
        "sahel",
        "scandinavia",
        "nordic",
        "mediterranean",
        "middle east",
        "central europe",
        "eastern europe",
        "western europe",
        "southern europe",
        "northern europe",
        "southeast europe",
        "southwestern europe",
        "central and southeast europe",
        "horn of africa",
        "arabian peninsula",
        "indian subcontinent",
        "southeast asia",
        "central asia",
    }
    | {label.casefold() for label in BROAD_REGIONS | REGIONAL_LABEL_VOCAB},
    key=len,
    reverse=True,
)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'") )


def read_country_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def extract_lead(markdown: str) -> str:
    next_h2 = re.search(r"^##\s+", markdown, re.MULTILINE)
    return markdown[: next_h2.start()] if next_h2 else markdown


def iter_sections(markdown: str) -> list[tuple[str, int, str]]:
    matches = list(SECTION_HEADING_PATTERN.finditer(markdown))
    sections: list[tuple[str, int, str]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = normalize_text(match.group(2).strip("# "))
        start = match.end()
        end = len(markdown)
        for next_match in matches[index + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        sections.append((title, level, markdown[start:end].strip()))
    return sections


def extract_named_sections(markdown: str) -> list[tuple[str, str]]:
    wanted = re.compile(
        r"\b(geography|location|topography|climate|environment|borders|territory|physical geography)\b",
        re.IGNORECASE,
    )
    return [(title, body) for title, _level, body in iter_sections(markdown) if wanted.search(title)]


def compact_text(value: str, max_chars: int) -> str:
    normalized = re.sub(r"\n{3,}", "\n\n", value.strip())
    if len(normalized) <= max_chars:
        return normalized
    cut = normalized[:max_chars]
    sentence_end = max(cut.rfind(". "), cut.rfind("\n"))
    if sentence_end > max_chars * 0.65:
        cut = cut[: sentence_end + 1]
    return cut.rstrip() + " […]"


def keyword_windows(markdown: str, window: int = 420, max_windows: int = 10) -> list[str]:
    lowered = markdown.casefold()
    spans: list[tuple[int, int]] = []
    for keyword in REGION_KEYWORDS:
        start = 0
        while len(spans) < max_windows * 3:
            index = lowered.find(keyword, start)
            if index == -1:
                break
            spans.append((max(0, index - window), min(len(markdown), index + len(keyword) + window)))
            start = index + len(keyword)

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1] + 80:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    windows: list[str] = []
    for start, end in merged[:max_windows]:
        snippet = markdown[start:end].strip()
        snippet = re.sub(r"\n{3,}", "\n\n", snippet)
        windows.append(snippet)
    return windows


def build_evidence_packet(markdown: str) -> tuple[str, list[str]]:
    parts: list[str] = []
    section_names: list[str] = []

    lead = compact_text(extract_lead(markdown), 2400)
    if lead:
        parts.append(f"## Lead\n{lead}")

    for title, body in extract_named_sections(markdown)[:4]:
        section_names.append(title)
        parts.append(f"## Section: {title}\n{compact_text(body, 2600)}")

    windows = keyword_windows(markdown)
    if windows:
        parts.append("## Keyword windows\n" + "\n\n---\n\n".join(compact_text(window, 700) for window in windows))

    return compact_text("\n\n".join(parts), 9000), section_names


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
                payload_json = json.loads(response.read().decode("utf-8"))
            raw = payload_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return parse_gemini_json(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            if attempt == retries:
                raise RuntimeError(f"Gemini extraction failed after {retries} attempts: {exc}") from exc
            time.sleep(10 * attempt)

    raise RuntimeError("Gemini extraction failed")


def parse_gemini_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Gemini occasionally returns Windows-style or Markdown-escaped strings even
        # with JSON mode. Preserve valid escapes and neutralize invalid backslashes.
        repaired = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
        return json.loads(repaired)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def clean_region(value: object, allowed: set[str]) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = normalize_text(value)
    if not normalized:
        return None
    # normalize common variants observed in Wikipedia phrasing
    canonical = {
        "North American": "North America",
        "South American": "South America",
        "Central American": "Central America",
        "West Asia": "Western Asia",
        "East Asia": "Eastern Asia",
        "South-Eastern Asia": "South-Eastern Asia",
        "SE Asia": "South-Eastern Asia",
        "EU": "Europe",
    }.get(normalized, normalized)

    if canonical in allowed:
        return canonical

    # case-insensitive fallback for unexpected casing
    for allowed_value in allowed:
        if normalize_text(allowed_value).casefold() == canonical.casefold():
            return allowed_value

    return None


def clean_region_list(value: object, allowed: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        label = clean_region(item, allowed)
        if label and label not in seen:
            cleaned.append(label)
            seen.add(label)
    return cleaned


def get_allowed_values(connection: sqlite3.Connection) -> tuple[set[str], set[str]]:
    scalar_regions = {
        row[0]
        for row in connection.execute("SELECT DISTINCT region FROM countries WHERE region IS NOT NULL").fetchall()
        if row[0]
    }
    scalar_subregions = {
        row[0]
        for row in connection.execute("SELECT DISTINCT subregion FROM countries WHERE subregion IS NOT NULL").fetchall()
        if row[0]
    }
    list_regions = {
        row[0]
        for row in connection.execute("SELECT DISTINCT region_name FROM country_regions WHERE region_name IS NOT NULL").fetchall()
        if row[0]
    }
    list_subregions = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT subregion_name FROM country_subregions WHERE subregion_name IS NOT NULL"
        ).fetchall()
        if row[0]
    }
    return BROAD_REGIONS | scalar_regions | list_regions, REGIONAL_LABEL_VOCAB | scalar_subregions | list_subregions


def build_prompt(country_name: str, evidence_packet: str, allowed_regions: set[str], allowed_subregions: set[str]) -> str:
    return f"""
You extract structured geography facts for a country guessing game.
Use ONLY the compact evidence packet from local Wikipedia markdown.

Country: {country_name}

Return STRICT JSON only with this schema:
{{
  "regions": ["zero or more allowed broad region names"],
  "subregions": ["zero or more allowed regional label names"],
  "evidence": {{"Label": "short quote or phrase from the packet"}},
  "notes": "short note about ambiguity or missing data, or null"
}}

Allowed region names:
{', '.join(sorted(allowed_regions))}

Allowed subregion names:
{', '.join(sorted(allowed_subregions))}

Rules:
- Use only values from the allowed lists. If nothing is confidently present in text,
  return an empty array for that field.
- Prefer direct, commonly accepted geographic/geopolitical labels.
- Include multiple labels when the evidence supports them (for example Portugal can be
  Southern Europe, Iberia, and Iberian Peninsula; Croatia can be Central Europe and
  Southeast Europe if both are explicit).
- Do not infer obscure labels from neighbors alone. Do not invent labels outside the
  allowed lists.
- Keep labels in English exactly as allowed.
- Keep evidence short and quote-like.

Evidence packet:
---
{evidence_packet}
---
""".strip()


def ensure_list_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS country_regions (
            country_id INTEGER NOT NULL,
            region_name TEXT NOT NULL,
            PRIMARY KEY (country_id, region_name),
            FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS country_subregions (
            country_id INTEGER NOT NULL,
            subregion_name TEXT NOT NULL,
            PRIMARY KEY (country_id, subregion_name),
            FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_country_regions_name ON country_regions(region_name)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_country_subregions_name ON country_subregions(subregion_name)")


def upsert_region_lists(
    connection: sqlite3.Connection,
    country_id: int,
    regions: list[str],
    subregions: list[str],
    *,
    replace_lists: bool,
) -> None:
    if replace_lists:
        connection.execute("DELETE FROM country_regions WHERE country_id = ?", (country_id,))
        connection.execute("DELETE FROM country_subregions WHERE country_id = ?", (country_id,))

    for region in regions:
        connection.execute(
            "INSERT OR IGNORE INTO country_regions(country_id, region_name) VALUES (?, ?)",
            (country_id, region),
        )
    for subregion in subregions:
        connection.execute(
            "INSERT OR IGNORE INTO country_subregions(country_id, subregion_name) VALUES (?, ?)",
            (country_id, subregion),
        )

    scalar_region = regions[0] if regions else None
    scalar_subregion = subregions[0] if subregions else None
    if scalar_region or scalar_subregion:
        connection.execute(
            """
            UPDATE countries
            SET region = COALESCE(?, region),
                subregion = COALESCE(?, subregion),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (scalar_region, scalar_subregion, country_id),
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
    parser.add_argument("--sleep", type=float, default=2.5, help="Seconds to sleep between API calls")
    parser.add_argument(
        "--replace-lists",
        action="store_true",
        help="Replace existing region/subregion list rows for each processed country instead of appending",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Deprecated alias for --replace-lists",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print extraction results without writing SQLite")
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

    connection = sqlite3.connect(args.db)
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_list_tables(connection)
    replace_lists = bool(args.replace_lists or args.overwrite)

    regions, subregions = get_allowed_values(connection)

    processed = 0
    missing_sections: list[str] = []
    missing_db: list[str] = []
    failures: list[tuple[str, str]] = []

    try:
        for row in rows:
            country_name = row["name"].strip()
            md_path = ROOT_DIR / row["md_file"]
            if not md_path.exists():
                failures.append((country_name, f"Missing markdown file: {md_path}"))
                continue

            markdown = md_path.read_text(encoding="utf-8")
            evidence_packet, section_names = build_evidence_packet(markdown)
            if not evidence_packet:
                missing_sections.append(country_name)
                continue

            try:
                result = call_gemini(build_prompt(country_name, evidence_packet, regions, subregions), args.model, api_key)
            except RuntimeError as exc:
                failures.append((country_name, str(exc)))
                continue

            region_values = clean_region_list(result.get("regions"), regions)
            subregion_values = clean_region_list(result.get("subregions"), subregions)
            evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
            notes = result.get("notes")
            print(
                f"{country_name}: regions={region_values}; subregions={subregion_values}; "
                f"sections={section_names}; evidence={evidence}; notes={notes}"
            )

            country = connection.execute("SELECT id FROM countries WHERE app_country_name = ?", (country_name,)).fetchone()
            if country is None:
                missing_db.append(country_name)
                continue

            country_id = country[0]
            if not args.dry_run:
                upsert_region_lists(
                    connection,
                    country_id,
                    region_values,
                    subregion_values,
                    replace_lists=replace_lists,
                )
                connection.commit()

            processed += 1
            if args.sleep:
                time.sleep(args.sleep)
    finally:
        connection.close()

    print(f"Processed countries: {processed}")
    if missing_sections:
        print("Missing evidence packets:")
        for name in missing_sections:
            print(f"- {name}")
    if missing_db:
        print("Missing countries in SQLite:")
        for name in missing_db:
            print(f"- {name}")
    if failures:
        print("Failures:")
        for name, error in failures:
            print(f"- {name}: {error}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
