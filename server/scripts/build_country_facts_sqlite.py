"""Build a local SQLite knowledge base for Countrydle facts.

This script creates ``data/country_facts.sqlite`` from the existing
``data/countries.csv`` list and the free REST Countries API.

It intentionally leaves relation families that need curation (`water_access`,
`major_rivers`) empty for now. The old OpenAI + Qdrant flow should be used
whenever this local DB does not contain the requested relation/data.

Usage from repository root:
    python server/scripts/build_country_facts_sqlite.py

Optional:
    python server/scripts/build_country_facts_sqlite.py --sample
    python server/scripts/build_country_facts_sqlite.py --output data/country_facts.sqlite
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_COUNTRIES_CSV = ROOT_DIR / "data" / "countries.csv"
DEFAULT_OUTPUT = ROOT_DIR / "data" / "country_facts.sqlite"
SCHEMA_PATH = ROOT_DIR / "server" / "countrydle" / "local_kb" / "schema.sql"
REST_COUNTRIES_URLS = [
    "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,capital,continents,region,subregion,latlng,borders,currencies",
    "https://restcountries.com/v3.1/all?fields=name,cca3,languages,population,area,landlocked,car,unMember",
]
FACTBOOK_TREE_URL = "https://api.github.com/repos/factbook/factbook.json/git/trees/master?recursive=1"
FACTBOOK_RAW_BASE_URL = "https://raw.githubusercontent.com/factbook/factbook.json/master/"

SAMPLE_COUNTRIES = {
    "Poland",
    "Germany",
    "France",
    "Spain",
    "Italy",
    "United Kingdom",
    "Japan",
    "United States",
    "Brazil",
}

EU_MEMBERS = {
    "AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD",
    "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE",
}

NATO_MEMBERS = {
    "ALB", "BEL", "BGR", "CAN", "HRV", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "ISL", "ITA", "LVA", "LTU", "LUX", "MNE", "NLD",
    "MKD", "NOR", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "TUR",
    "GBR", "USA",
}

SCHENGEN_MEMBERS = {
    "AUT", "BEL", "BGR", "HRV", "CZE", "DNK", "EST", "FIN", "FRA", "DEU",
    "GRC", "HUN", "ISL", "ITA", "LVA", "LIE", "LTU", "LUX", "MLT", "NLD",
    "NOR", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "CHE",
}


COUNTRY_ADDITIONAL_SUBREGIONS = {
    "Poland": {"Eastern Europe"},
    "Lithuania": {"Eastern Europe", "Baltic states"},
    "Montenegro": {"Balkans", "Southern Europe"},
    "Portugal": {"Iberia", "Iberian Peninsula"},
}

COUNTRY_ADDITIONAL_OFFICIAL_LANGUAGES = {
    "MKD": [("sqi", "Albanian")],
}

COUNTRY_GOVERNMENT_TYPE_OVERRIDES = {
    "Palestine": "Republic",
}

COUNTRY_DOMINANT_RELIGION_OVERRIDES = {
    "Palestine": "Islam",
    "Saint Kitts and Nevis": "Protestant",
}

OECD_MEMBERS = {
    "AUS", "AUT", "BEL", "CAN", "CHL", "COL", "CRI", "CZE", "DNK", "EST",
    "FIN", "FRA", "DEU", "GRC", "HUN", "ISL", "IRL", "ISR", "ITA", "JPN",
    "KOR", "LVA", "LTU", "LUX", "MEX", "NLD", "NZL", "NOR", "POL", "PRT",
    "SVK", "SVN", "ESP", "SWE", "CHE", "TUR", "GBR", "USA",
}

G7_MEMBERS = {"CAN", "FRA", "DEU", "ITA", "JPN", "GBR", "USA"}
G20_MEMBERS = {
    "ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA",
    "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF", "TUR", "GBR", "USA",
}

COUNTRY_NAME_ALIASES = {
    "Bahamas": "The Bahamas",
    "Cape Verde": "Cabo Verde",
    "Czechia": "Czech Republic",
    "Democratic Republic of the Congo": "DR Congo",
    "East Timor": "Timor-Leste",
    "Gambia The": "Gambia",
    "Ivory Coast": "Côte d'Ivoire",
    "Republic of the Congo": "Republic of the Congo",
    "Russia": "Russia",
    "South Korea": "South Korea",
    "Syria": "Syria",
    "Turkey": "Türkiye",
    "United States": "United States",
    "Vatican City": "Vatican City",
}

FACTBOOK_NAME_ALIASES = {
    "Bahamas": "The Bahamas",
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "Democratic Republic of the Congo": "Congo, Democratic Republic of the",
    "Gambia The": "The Gambia",
    "Republic of the Congo": "Congo, Republic of the",
    "Ivory Coast": "Côte d'Ivoire",
    "Myanmar": "Burma",
    "São Tomé and Príncipe": "Sao Tome and Principe",
    "United States": "United States of America",
    "Vatican City": "Holy See (Vatican City)",
}

FACTBOOK_ORGANIZATION_ALIASES = {
    "C": "Commonwealth",
    "CE": "Council of Europe",
    "Schengen Convention": "Schengen",
    "G-7": "G7",
    "G-20": "G20",
    "LAS": "Arab League",
    "EU": "EU",
    "NATO": "NATO",
    "OECD": "OECD",
    "UN": "UN",
    "WTO": "WTO",
}

FACTBOOK_MEMBERSHIP_EXCLUDED_QUALIFIERS = {
    "accession candidate",
    "associate",
    "candidate",
    "compliant country",
    "cooperating state",
    "correspondent",
    "de facto member",
    "dialogue",
    "excluded from formal participation",
    "implementing country",
    "national committees",
    "ngos",
    "observer",
    "partner",
    "pending member",
    "regional",
    "signatory",
    "subbureau",
    "subscriber",
    "suspended",
    "temporary",
}

# These high-value game relations are maintained by explicit up-to-date lists
# below, because the Factbook organization field can include stale entries
# (for example the United Kingdom still appears with EU in the source).
STATIC_MEMBERSHIP_ORGANIZATIONS = {"EU", "NATO", "Schengen", "OECD", "G7", "G20"}

RELIGION_GROUP_PATTERNS = [
    ("No religion", ("no religion", "none", "unaffiliated", "atheist", "agnostic", "nonreligious")),
    ("Catholic", ("catholic",)),
    ("Orthodox", ("orthodox",)),
    (
        "Protestant",
        (
            "protestant",
            "evangelical",
            "anglican",
            "baptist",
            "lutheran",
            "methodist",
            "pentecostal",
            "presbyterian",
            "reformed",
            "adventist",
        ),
    ),
    ("Islam", ("muslim", "islam", "sunni", "shia", "shi'a", "ibadi")),
    ("Judaism", ("jewish", "judaism")),
    ("Buddhism", ("buddhist", "buddhism")),
    ("Hinduism", ("hindu", "hinduism")),
    ("Folk/Traditional religions", ("folk", "traditional", "animist", "indigenous")),
    ("Christianity", ("christian", "apostolic", "mormon", "jehovah", "latter day saint")),
]

RELIGION_ALIASES = {
    "islam": "Islam",
    "muslim": "Islam",
    "catholic": "Catholic",
    "roman catholic": "Catholic",
    "orthodox": "Orthodox",
    "protestant": "Protestant",
    "christian": "Christianity",
    "christianity": "Christianity",
    "jewish": "Judaism",
    "judaism": "Judaism",
    "buddhist": "Buddhism",
    "buddhism": "Buddhism",
    "hindu": "Hinduism",
    "hinduism": "Hinduism",
    "atheist": "No religion",
    "atheism": "No religion",
    "no religion": "No religion",
    "unaffiliated": "No religion",
    "mixed": "Mixed",
}

MIXED_RELIGION_MIN_SHARE = 35.0
MIXED_RELIGION_CLOSE_MARGIN = 15.0

# REST Countries sometimes returns borders with dependent territories or
# disputed territories instead of the sovereign country we want to use in the
# local game KB.
BORDER_TERRITORY_ALIASES = {
    "ESH": ("Morocco", "MAR"),  # Western Sahara
    "GIB": ("United Kingdom", "GBR"),  # Gibraltar
    "GUF": ("France", "FRA"),  # French Guiana
    "HKG": ("China", "CHN"),  # Hong Kong
    "MAC": ("China", "CHN"),  # Macau
}


def normalize_name(value: str) -> str:
    return value.strip().casefold()


def read_app_countries(path: Path, sample: bool) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    names = [row["name"].strip() for row in rows]
    if sample:
        names = [name for name in names if name in SAMPLE_COUNTRIES]
    return names


def fetch_rest_countries() -> list[dict]:
    """Fetch and merge REST Countries data.

    The API currently rejects very long `fields=` lists, so the data is fetched
    in two small requests and merged by `cca3`.
    """
    merged: dict[str, dict] = {}
    for url in REST_COUNTRIES_URLS:
        with urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for country in payload:
            cca3 = country.get("cca3")
            if not cca3:
                continue
            merged.setdefault(cca3, {}).update(country)
    return list(merged.values())


def fetch_factbook_profiles() -> dict[str, dict]:
    """Fetch Factbook JSON profiles and index them by country names.

    Factbook uses CIA/GEC file codes, so matching by country names is simpler
    and robust enough for this build-time script.
    """
    with urlopen(FACTBOOK_TREE_URL, timeout=60) as response:
        tree = json.loads(response.read().decode("utf-8"))

    json_paths = [
        item["path"]
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and item.get("path", "").endswith(".json") and "/" in item.get("path", "")
    ]

    index: dict[str, dict] = {}
    for path in json_paths:
        with urlopen(FACTBOOK_RAW_BASE_URL + path, timeout=60) as response:
            profile = json.loads(response.read().decode("utf-8"))

        country_name = ((profile.get("Government") or {}).get("Country name") or {})
        names = [
            (country_name.get("conventional short form") or {}).get("text"),
            (country_name.get("conventional long form") or {}).get("text"),
            (country_name.get("local short form") or {}).get("text"),
            (country_name.get("local long form") or {}).get("text"),
        ]
        profile["_factbook_path"] = path
        for name in names:
            if name:
                index[normalize_name(html.unescape(name))] = profile
    return index


def build_country_index(rest_countries: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for country in rest_countries:
        names = country.get("name") or {}
        candidates = [
            names.get("common"),
            names.get("official"),
            *((names.get("nativeName") or {}).get(code, {}).get("common") for code in (names.get("nativeName") or {})),
            *((names.get("nativeName") or {}).get(code, {}).get("official") for code in (names.get("nativeName") or {})),
        ]
        for candidate in candidates:
            if candidate:
                index[normalize_name(candidate)] = country
    return index


def find_rest_country(app_name: str, index: dict[str, dict]) -> dict | None:
    candidates = [app_name, COUNTRY_NAME_ALIASES.get(app_name, "")]
    for candidate in candidates:
        if candidate and normalize_name(candidate) in index:
            return index[normalize_name(candidate)]
    return None


def find_factbook_profile(app_name: str, rest_country: dict, index: dict[str, dict]) -> dict | None:
    names = rest_country.get("name") or {}
    candidates = [
        app_name,
        FACTBOOK_NAME_ALIASES.get(app_name, ""),
        names.get("common"),
        names.get("official"),
        FACTBOOK_NAME_ALIASES.get(names.get("common", ""), ""),
    ]
    for candidate in candidates:
        if candidate and normalize_name(candidate) in index:
            return index[normalize_name(candidate)]
    return None


def parse_factbook_memberships(profile: dict | None) -> list[str]:
    if not profile:
        return []

    text = (
        ((profile.get("Government") or {}).get("International organization participation") or {}).get("text")
        or ""
    )
    memberships: list[str] = []
    for raw_item in text.split(","):
        item = raw_item.strip()
        if not item:
            continue

        qualifier_matches = [match.casefold() for match in re.findall(r"\(([^)]*)\)", item)]
        if any(excluded in qualifier for qualifier in qualifier_matches for excluded in FACTBOOK_MEMBERSHIP_EXCLUDED_QUALIFIERS):
            continue

        organization = re.sub(r"\s*\([^)]*\)", "", item).strip()
        organization = FACTBOOK_ORGANIZATION_ALIASES.get(organization, organization)
        if organization in STATIC_MEMBERSHIP_ORGANIZATIONS:
            continue
        if organization:
            memberships.append(organization)
    return sorted(set(memberships))


def group_government_type(raw_text: str | None) -> str | None:
    if not raw_text:
        return None
    text = html.unescape(raw_text).casefold()
    if any(word in text for word in ("communist", "communist party", "marxist")):
        return "Communist state"
    if any(word in text for word in ("theocracy", "ecclesiastical")):
        return "Theocracy"
    if any(word in text for word in ("military junta", "military regime")):
        return "Military junta"
    if any(word in text for word in ("monarchy", "emirate", "sultanate", "commonwealth realm", "kingdom")):
        return "Monarchy"
    if any(word in text for word in ("republic", "federation", "parliamentary democracy", "presidential", "semi-presidential")):
        return "Republic"
    if "transitional" in text:
        return "Transitional government"
    return "Other"


def parse_factbook_government_type(profile: dict | None) -> str | None:
    if not profile:
        return None
    text = ((profile.get("Government") or {}).get("Government type") or {}).get("text")
    return group_government_type(text)


def religion_group(raw_label: str) -> str | None:
    original = html.unescape(raw_label).casefold()
    label = re.sub(r"\([^)]*\)", " ", original)
    label = re.sub(r"[^a-z0-9' ]+", " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    searchable = f"{label} {original}"
    if not label or label in {"other", "unspecified", "not stated", "refused to answer"}:
        return None
    for group, patterns in RELIGION_GROUP_PATTERNS:
        if any(pattern in searchable for pattern in patterns):
            return group
    return "Other"


def parse_factbook_dominant_religion(profile: dict | None) -> str | None:
    if not profile:
        return None
    text = ((profile.get("People and Society") or {}).get("Religions") or {}).get("text") or ""
    if not text:
        return None

    scores: dict[str, float] = {}
    for match in re.finditer(r"([^,;:]+?)\s+(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?%", html.unescape(text)):
        label, percent_text, range_end_text = match.groups()
        group = religion_group(label)
        if not group:
            continue
        percent = float(percent_text)
        if range_end_text:
            percent = (percent + float(range_end_text)) / 2
        scores[group] = scores.get(group, 0.0) + percent

    if not scores:
        lowered = text.casefold()
        for alias, group in RELIGION_ALIASES.items():
            if alias in lowered:
                return group
        return None

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_group, top_score = ranked[0]
    if top_group == "Other":
        leading_context = html.unescape(text).split("%", 1)[0]
        contextual_group = religion_group(leading_context)
        if contextual_group and contextual_group != "Other":
            top_group = contextual_group
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score < MIXED_RELIGION_MIN_SHARE or (top_score < 50.0 and top_score - second_score < MIXED_RELIGION_CLOSE_MARGIN):
        return "Mixed"
    return top_group


def init_db(output: Path) -> sqlite3.Connection:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    connection = sqlite3.connect(output)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def insert_country(
    connection: sqlite3.Connection,
    app_name: str,
    country: dict,
    cca3_to_name: dict[str, str],
    factbook_profile: dict | None,
) -> None:
    names = country.get("name") or {}
    latlng = country.get("latlng") or [None, None]
    car = country.get("car") or {}
    cca3 = country.get("cca3")
    government_type = COUNTRY_GOVERNMENT_TYPE_OVERRIDES.get(
        app_name,
        parse_factbook_government_type(factbook_profile),
    )
    dominant_religion = COUNTRY_DOMINANT_RELIGION_OVERRIDES.get(
        app_name,
        parse_factbook_dominant_religion(factbook_profile),
    )

    cursor = connection.execute(
        """
        INSERT INTO countries (
            app_country_name, official_name, cca2, cca3, region, subregion, capital,
            population, area_km2, latitude, longitude, is_island, driving_side,
            government_type, dominant_religion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            app_name,
            names.get("official"),
            country.get("cca2"),
            cca3,
            country.get("region"),
            country.get("subregion"),
            (country.get("capital") or [None])[0],
            country.get("population"),
            country.get("area"),
            latlng[0] if len(latlng) > 0 else None,
            latlng[1] if len(latlng) > 1 else None,
            1 if country.get("landlocked") is False and not country.get("borders") else 0,
            car.get("side"),
            government_type,
            dominant_religion,
        ),
    )
    country_id = cursor.lastrowid

    region = country.get("region")
    if region:
        connection.execute(
            "INSERT OR IGNORE INTO country_regions(country_id, region_name) VALUES (?, ?)",
            (country_id, region),
        )

    subregions = set()
    if country.get("subregion"):
        subregions.add(country["subregion"])
    subregions.update(COUNTRY_ADDITIONAL_SUBREGIONS.get(app_name, set()))
    for subregion in sorted(subregions):
        connection.execute(
            "INSERT OR IGNORE INTO country_subregions(country_id, subregion_name) VALUES (?, ?)",
            (country_id, subregion),
        )

    for continent in country.get("continents") or []:
        connection.execute(
            "INSERT OR IGNORE INTO country_continents(country_id, continent) VALUES (?, ?)",
            (country_id, continent),
        )

    for border_cca3 in country.get("borders") or []:
        border_name, normalized_border_cca3 = BORDER_TERRITORY_ALIASES.get(
            border_cca3,
            (cca3_to_name.get(border_cca3, border_cca3), border_cca3),
        )
        if normalized_border_cca3 == cca3:
            continue
        connection.execute(
            """
            INSERT OR IGNORE INTO country_borders(country_id, border_country_name, border_cca3)
            VALUES (?, ?, ?)
            """,
            (country_id, border_name, normalized_border_cca3),
        )

    for code, currency in (country.get("currencies") or {}).items():
        connection.execute(
            """
            INSERT OR IGNORE INTO country_currencies(country_id, currency_code, currency_name, currency_symbol)
            VALUES (?, ?, ?, ?)
            """,
            (country_id, code, currency.get("name"), currency.get("symbol")),
        )

    for code, language in (country.get("languages") or {}).items():
        connection.execute(
            """
            INSERT OR IGNORE INTO country_languages(country_id, language_code, language_name)
            VALUES (?, ?, ?)
            """,
            (country_id, code, language),
        )

    for code, language in COUNTRY_ADDITIONAL_OFFICIAL_LANGUAGES.get(cca3, []):
        connection.execute(
            """
            INSERT OR IGNORE INTO country_languages(country_id, language_code, language_name)
            VALUES (?, ?, ?)
            """,
            (country_id, code, language),
        )

    memberships = parse_factbook_memberships(factbook_profile)
    if country.get("unMember"):
        memberships.append("UN")
    if cca3 in EU_MEMBERS:
        memberships.append("EU")
    if cca3 in NATO_MEMBERS:
        memberships.append("NATO")
    if cca3 in SCHENGEN_MEMBERS:
        memberships.append("Schengen")
    if cca3 in OECD_MEMBERS:
        memberships.append("OECD")
    if cca3 in G7_MEMBERS:
        memberships.append("G7")
    if cca3 in G20_MEMBERS:
        memberships.append("G20")

    for organization in memberships:
        connection.execute(
            "INSERT OR IGNORE INTO country_memberships(country_id, organization) VALUES (?, ?)",
            (country_id, organization),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--countries-csv", type=Path, default=DEFAULT_COUNTRIES_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample", action="store_true", help="Populate only a small test set of countries")
    args = parser.parse_args()

    app_countries = read_app_countries(args.countries_csv, args.sample)
    rest_countries = fetch_rest_countries()
    factbook_index = fetch_factbook_profiles()
    index = build_country_index(rest_countries)
    cca3_to_name = {
        country.get("cca3"): (country.get("name") or {}).get("common", country.get("cca3"))
        for country in rest_countries
        if country.get("cca3")
    }

    connection = init_db(args.output)
    missing = []
    missing_factbook = []
    inserted = 0
    try:
        for app_name in app_countries:
            country = find_rest_country(app_name, index)
            if not country:
                missing.append(app_name)
                continue
            factbook_profile = find_factbook_profile(app_name, country, factbook_index)
            if not factbook_profile:
                missing_factbook.append(app_name)
            insert_country(connection, app_name, country, cca3_to_name, factbook_profile)
            inserted += 1
        connection.commit()
    finally:
        connection.close()

    print(f"Created SQLite KB: {args.output}")
    print(f"Inserted countries: {inserted}")
    if missing:
        print("Missing countries from REST Countries mapping:")
        for name in missing:
            print(f"- {name}")
    if missing_factbook:
        print("Missing countries from Factbook mapping:")
        for name in missing_factbook:
            print(f"- {name}")
    return 0 if inserted else 1


if __name__ == "__main__":
    sys.exit(main())
