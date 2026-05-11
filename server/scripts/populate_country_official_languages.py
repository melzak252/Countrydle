"""Populate Countrydle official-language facts from legal/encyclopedic sources.

The base Countrydle KB gets language data from REST Countries, but that API can
miss co-official languages (for example Albanian in North Macedonia). This
script augments ``country_languages`` with languages that are legally official
for the country.

Source priority:
1. Wikipedia markdown infobox rows named "Official language(s)" decide which
   languages are safe to add.
2. Wikidata P37 (official language), matched by ISO 3166-1 alpha-3 (P298), is
   used to fill language codes and can be enabled as a fallback for countries
   without a parseable Wikipedia row.

It intentionally does not use population percentages from Factbook. A widely
spoken language is not necessarily an official language.

Usage from repository root:
    python server/scripts/populate_country_official_languages.py --dry-run
    python server/scripts/populate_country_official_languages.py --country "North Macedonia"
    python server/scripts/populate_country_official_languages.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT_DIR / "data" / "country_facts.sqlite"
DEFAULT_COUNTRIES_CSV = ROOT_DIR / "data" / "countries.csv"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "Countrydle-dev/1.0 (official language data enrichment)"


@dataclass(frozen=True)
class CountryRow:
    id: int
    name: str
    cca3: str | None


@dataclass(frozen=True)
class LanguageFact:
    language_name: str
    language_code: str | None
    source: str


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def language_key(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return normalize_text(ascii_value).casefold()


def clean_wikipedia_cell(value: str) -> str:
    value = value.replace("\\", "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\[[^\]]*\]", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = value.replace("*", " ")
    return normalize_text(value)


def split_language_names(value: str) -> list[str]:
    value = re.split(r"languages? with special status", value, flags=re.IGNORECASE)[0]
    value = re.sub(r"\*\*\s*\d+\s+languages?\s*\*\*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\)\s*(?=[A-Z])", "),", value)
    value = re.sub(r"\b(?:and|or)\b", ",", value, flags=re.IGNORECASE)
    parts = re.split(r"[,;/•*]+", value)
    names: list[str] = []
    for part in parts:
        raw = part.casefold()
        if any(token in raw for token in ("none", "de facto", "de jure", "federal level")):
            continue
        name = clean_wikipedia_cell(part).strip(" .:-")
        name = name.strip("()[]{}")
        if not name:
            continue
        if any(token in name.casefold() for token in ("official", "language", "regional")):
            continue
        if len(name) > 60:
            continue
        names.append(name)
    return sorted(set(names), key=str.casefold)


def load_country_markdown_paths(countries_csv: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    with countries_csv.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            name = row.get("name", "").strip()
            md_file = row.get("md_file", "").strip()
            if name and md_file:
                paths[name.casefold()] = ROOT_DIR / md_file
    return paths


def fetch_country_rows(db_path: Path, only_country: str | None) -> list[CountryRow]:
    connection = sqlite3.connect(db_path)
    try:
        query = "SELECT id, app_country_name, cca3 FROM countries"
        params: tuple[str, ...] = ()
        if only_country:
            query += " WHERE app_country_name = ? OR cca3 = ?"
            params = (only_country, only_country.upper())
        query += " ORDER BY app_country_name"
        return [CountryRow(*row) for row in connection.execute(query, params)]
    finally:
        connection.close()


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_wikidata_official_languages(cca3_values: list[str], sleep_seconds: float) -> dict[str, list[LanguageFact]]:
    facts: dict[str, list[LanguageFact]] = {}
    cca3_values = sorted({value for value in cca3_values if value})
    for chunk in chunked(cca3_values, 40):
        values = " ".join(f'"{value}"' for value in chunk)
        query = f"""
        SELECT ?iso3 ?langLabel ?iso6391 ?iso6393 WHERE {{
          VALUES ?iso3 {{ {values} }}
          ?country wdt:P298 ?iso3 ;
                   wdt:P37 ?lang .
          OPTIONAL {{ ?lang wdt:P218 ?iso6391 . }}
          OPTIONAL {{ ?lang wdt:P220 ?iso6393 . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        url = f"{WIKIDATA_SPARQL_URL}?format=json&query={quote(query)}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for binding in payload.get("results", {}).get("bindings", []):
            cca3 = binding.get("iso3", {}).get("value")
            language_name = binding.get("langLabel", {}).get("value")
            language_code = (
                binding.get("iso6393", {}).get("value")
                or binding.get("iso6391", {}).get("value")
                or None
            )
            if cca3 and language_name:
                facts.setdefault(cca3, []).append(LanguageFact(language_name, language_code, "wikidata"))
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return {key: sorted(set(value), key=lambda fact: fact.language_name.casefold()) for key, value in facts.items()}


def parse_wikipedia_official_languages(markdown_path: Path) -> list[LanguageFact]:
    if not markdown_path.exists():
        return []
    lines = markdown_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[:140]:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = clean_wikipedia_cell(cells[0]).casefold()
        if not label.startswith("official") or "language" not in label:
            continue
        if "regional" in label:
            continue
        names = split_language_names(cells[1])
        return [LanguageFact(name, None, "wikipedia") for name in names]
    return []


def merge_wikipedia_names_with_wikidata_codes(
    wikipedia_facts: list[LanguageFact],
    wikidata_facts: list[LanguageFact],
) -> list[LanguageFact]:
    wikidata_by_name = {fact.language_name.casefold(): fact for fact in wikidata_facts}
    merged: list[LanguageFact] = []
    for fact in wikipedia_facts:
        canonical_fact = wikidata_by_name.get(fact.language_name.casefold())
        if not canonical_fact:
            parsed_name = fact.language_name.casefold()
            for wikidata_name, wikidata_fact in wikidata_by_name.items():
                if parsed_name.startswith(wikidata_name) or wikidata_name.startswith(parsed_name):
                    canonical_fact = wikidata_fact
                    break
        merged.append(
            LanguageFact(
                language_name=canonical_fact.language_name if canonical_fact else fact.language_name,
                language_code=(canonical_fact.language_code if canonical_fact else fact.language_code),
                source=fact.source,
            )
        )
    return sorted(set(merged), key=lambda item: item.language_name.casefold())


def existing_languages(connection: sqlite3.Connection, country_id: int) -> set[str]:
    rows = connection.execute(
        "SELECT language_name FROM country_languages WHERE country_id = ?",
        (country_id,),
    )
    return {language_key(row[0]) for row in rows}


def insert_language(connection: sqlite3.Connection, country_id: int, fact: LanguageFact) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO country_languages(country_id, language_code, language_name)
        VALUES (?, ?, ?)
        """,
        (country_id, fact.language_code, fact.language_name),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--countries-csv", type=Path, default=DEFAULT_COUNTRIES_CSV)
    parser.add_argument("--country", help="Limit to one app country name or CCA3 code")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing to SQLite")
    parser.add_argument(
        "--use-wikidata-fallback",
        action="store_true",
        help="Use raw Wikidata P37 when Wikipedia has no parseable official-language row",
    )
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between Wikidata requests")
    args = parser.parse_args()

    countries = fetch_country_rows(args.db, args.country)
    if not countries:
        print("No countries matched.")
        return 1

    markdown_paths = load_country_markdown_paths(args.countries_csv)
    wikidata = fetch_wikidata_official_languages(
        [country.cca3 for country in countries if country.cca3],
        sleep_seconds=args.sleep,
    )

    connection = sqlite3.connect(args.db)
    added = 0
    checked = 0
    try:
        for country in countries:
            checked += 1
            wikidata_facts = wikidata.get(country.cca3 or "", [])
            wikipedia_facts = parse_wikipedia_official_languages(markdown_paths.get(country.name.casefold(), Path()))
            if wikipedia_facts:
                facts = merge_wikipedia_names_with_wikidata_codes(wikipedia_facts, wikidata_facts)
            elif args.use_wikidata_fallback:
                facts = wikidata_facts
            else:
                facts = []
            if not facts:
                continue

            present = existing_languages(connection, country.id)
            missing = [fact for fact in facts if language_key(fact.language_name) not in present]
            if not missing:
                continue

            source_names = ", ".join(f"{fact.language_name} ({fact.source})" for fact in missing)
            print(f"{country.name}: add {source_names}")
            added += len(missing)
            if not args.dry_run:
                for fact in missing:
                    insert_language(connection, country.id, fact)
        if args.dry_run:
            connection.rollback()
        else:
            connection.commit()
    finally:
        connection.close()

    action = "would add" if args.dry_run else "added"
    print(f"Checked {checked} countries; {action} {added} official-language rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
