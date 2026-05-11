"""Build local SQLite facts database for US Statedle.

The script intentionally prefers deterministic sources:
- local Wikipedia markdown infoboxes in data/us_states/*.md
- Census region/division CSV
- simple state adjacency JSON
- curated static lists for Canada/Mexico borders and major highways

Water access, major rivers and mountain ranges are left empty here and should be
filled by a separate Geography-section extraction step, similarly to Countrydle.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT = DATA_DIR / "us_state_facts.sqlite"
SCHEMA_PATH = ROOT_DIR / "server" / "us_statedle" / "local_kb" / "schema.sql"

CENSUS_REGIONS_CSV_URL = (
    "https://raw.githubusercontent.com/cphalpert/census-regions/master/"
    "us%20census%20bureau%20regions%20and%20divisions.csv"
)
STATE_ADJACENCY_JSON_URL = (
    "https://gist.githubusercontent.com/neilb/ee60cd179d5eb17d1cb616cdeeda760f/"
    "raw/usa-state-data.json"
)


CANADA_BORDER_STATES = {
    "Alaska",
    "Washington",
    "Idaho",
    "Montana",
    "North Dakota",
    "Minnesota",
    "Michigan",
    "Ohio",
    "Pennsylvania",
    "New York",
    "Vermont",
    "New Hampshire",
    "Maine",
}

MEXICO_BORDER_STATES = {"California", "Arizona", "New Mexico", "Texas"}

OCEAN_OR_GULF_COASTAL_STATES = {
    "Alabama",
    "Alaska",
    "California",
    "Connecticut",
    "Delaware",
    "Florida",
    "Georgia",
    "Hawaii",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Mississippi",
    "New Hampshire",
    "New Jersey",
    "New York",
    "North Carolina",
    "Oregon",
    "Rhode Island",
    "South Carolina",
    "Texas",
    "Virginia",
    "Washington",
}

ADMISSION_ORDER_BY_STATE = {
    "Delaware": 1,
    "Pennsylvania": 2,
    "New Jersey": 3,
    "Georgia": 4,
    "Connecticut": 5,
    "Massachusetts": 6,
    "Maryland": 7,
    "South Carolina": 8,
    "New Hampshire": 9,
    "Virginia": 10,
    "New York": 11,
    "North Carolina": 12,
    "Rhode Island": 13,
    "Vermont": 14,
    "Kentucky": 15,
    "Tennessee": 16,
    "Ohio": 17,
    "Louisiana": 18,
    "Indiana": 19,
    "Mississippi": 20,
    "Illinois": 21,
    "Alabama": 22,
    "Maine": 23,
    "Missouri": 24,
    "Arkansas": 25,
    "Michigan": 26,
    "Florida": 27,
    "Texas": 28,
    "Iowa": 29,
    "Wisconsin": 30,
    "California": 31,
    "Minnesota": 32,
    "Oregon": 33,
    "Kansas": 34,
    "West Virginia": 35,
    "Nevada": 36,
    "Nebraska": 37,
    "Colorado": 38,
    "North Dakota": 39,
    "South Dakota": 40,
    "Montana": 41,
    "Washington": 42,
    "Idaho": 43,
    "Wyoming": 44,
    "Utah": 45,
    "Oklahoma": 46,
    "New Mexico": 47,
    "Arizona": 48,
    "Alaska": 49,
    "Hawaii": 50,
}

COORDINATE_OVERRIDES = {
    # Alaska crosses the antimeridian, so averaging the longitude range in the
    # infobox produces a meaningless positive value.
    "Alaska": (64.2008, -149.4937),
    # Iowa's infobox coordinate line is not consistently extracted in the local
    # markdown; use a standard approximate centroid.
    "Iowa": (42.0329, -93.5815),
}

CIVIL_WAR_SIDE_BY_STATE = {
    "Alabama": "Confederacy",
    "Alaska": "Territory / not a state yet",
    "Arizona": "Territory / not a state yet",
    "Arkansas": "Confederacy",
    "California": "Union",
    "Colorado": "Territory / not a state yet",
    "Connecticut": "Union",
    "Delaware": "Border state",
    "Florida": "Confederacy",
    "Georgia": "Confederacy",
    "Hawaii": "Territory / not a state yet",
    "Idaho": "Territory / not a state yet",
    "Illinois": "Union",
    "Indiana": "Union",
    "Iowa": "Union",
    "Kansas": "Union",
    "Kentucky": "Border state",
    "Louisiana": "Confederacy",
    "Maine": "Union",
    "Maryland": "Border state",
    "Massachusetts": "Union",
    "Michigan": "Union",
    "Minnesota": "Union",
    "Mississippi": "Confederacy",
    "Missouri": "Border state",
    "Montana": "Territory / not a state yet",
    "Nebraska": "Territory / not a state yet",
    "Nevada": "Union",
    "New Hampshire": "Union",
    "New Jersey": "Union",
    "New Mexico": "Territory / not a state yet",
    "New York": "Union",
    "North Carolina": "Confederacy",
    "North Dakota": "Territory / not a state yet",
    "Ohio": "Union",
    "Oklahoma": "Territory / not a state yet",
    "Oregon": "Union",
    "Pennsylvania": "Union",
    "Rhode Island": "Union",
    "South Carolina": "Confederacy",
    "South Dakota": "Territory / not a state yet",
    "Tennessee": "Confederacy",
    "Texas": "Confederacy",
    "Utah": "Territory / not a state yet",
    "Vermont": "Union",
    "Virginia": "Confederacy",
    "Washington": "Territory / not a state yet",
    "West Virginia": "Border state",
    "Wisconsin": "Union",
    "Wyoming": "Territory / not a state yet",
}


REGIONAL_LABELS_BY_STATE = {
    # Common coastal / water-facing labels.
    "Alabama": {"Gulf Coast", "Deep South", "Sun Belt"},
    "Alaska": {"Pacific Coast", "Arctic", "Non-contiguous US"},
    "Arizona": {"Southwest", "Four Corners", "Sun Belt", "Mountain West"},
    "Arkansas": {"Upper South", "Ozarks", "South Central US"},
    "California": {"West Coast", "Pacific Coast", "Southwest", "Sun Belt"},
    "Colorado": {"Mountain West", "Rocky Mountain States", "Four Corners", "Southwest", "Great Plains"},
    "Connecticut": {"East Coast", "New England"},
    "Delaware": {"East Coast", "Mid-Atlantic"},
    "Florida": {"East Coast", "Gulf Coast", "Deep South", "Sun Belt"},
    "Georgia": {"East Coast", "Deep South", "Sun Belt", "Appalachia"},
    "Hawaii": {"Pacific Coast", "Non-contiguous US"},
    "Idaho": {"Mountain West", "Rocky Mountain States", "Pacific Northwest"},
    "Illinois": {"Midwest", "Great Lakes", "Rust Belt"},
    "Indiana": {"Midwest", "Great Lakes", "Rust Belt"},
    "Iowa": {"Midwest", "Great Plains"},
    "Kansas": {"Midwest", "Great Plains"},
    "Kentucky": {"Upper South", "Appalachia", "South Central US"},
    "Louisiana": {"Gulf Coast", "Deep South", "Sun Belt", "South Central US"},
    "Maine": {"East Coast", "New England"},
    "Maryland": {"East Coast", "Mid-Atlantic", "Appalachia"},
    "Massachusetts": {"East Coast", "New England"},
    "Michigan": {"Midwest", "Great Lakes", "Rust Belt"},
    "Minnesota": {"Midwest", "Great Lakes", "Upper Midwest"},
    "Mississippi": {"Gulf Coast", "Deep South", "Sun Belt"},
    "Missouri": {"Midwest", "Upper South", "Ozarks", "South Central US", "Rust Belt"},
    "Montana": {"Mountain West", "Rocky Mountain States", "Great Plains"},
    "Nebraska": {"Midwest", "Great Plains"},
    "Nevada": {"Mountain West", "Southwest", "Sun Belt"},
    "New Hampshire": {"East Coast", "New England"},
    "New Jersey": {"East Coast", "Mid-Atlantic"},
    "New Mexico": {"Southwest", "Four Corners", "Sun Belt", "Mountain West", "Great Plains"},
    "New York": {"East Coast", "Mid-Atlantic", "Great Lakes", "Rust Belt"},
    "North Carolina": {"East Coast", "Upper South", "Sun Belt", "Appalachia"},
    "North Dakota": {"Midwest", "Great Plains", "Upper Midwest"},
    "Ohio": {"Midwest", "Great Lakes", "Rust Belt", "Appalachia"},
    "Oklahoma": {"South Central US", "Great Plains", "Sun Belt", "Southwest"},
    "Oregon": {"West Coast", "Pacific Coast", "Pacific Northwest"},
    "Pennsylvania": {"East Coast", "Mid-Atlantic", "Appalachia", "Great Lakes", "Rust Belt"},
    "Rhode Island": {"East Coast", "New England"},
    "South Carolina": {"East Coast", "Deep South", "Sun Belt", "Appalachia"},
    "South Dakota": {"Midwest", "Great Plains", "Upper Midwest"},
    "Tennessee": {"Upper South", "Appalachia", "South Central US", "Sun Belt"},
    "Texas": {"Gulf Coast", "South Central US", "Southwest", "Great Plains", "Sun Belt"},
    "Utah": {"Mountain West", "Rocky Mountain States", "Four Corners", "Southwest"},
    "Vermont": {"New England"},
    "Virginia": {"East Coast", "Mid-Atlantic", "Upper South", "Appalachia"},
    "Washington": {"West Coast", "Pacific Coast", "Pacific Northwest"},
    "West Virginia": {"Appalachia", "Upper South"},
    "Wisconsin": {"Midwest", "Great Lakes", "Upper Midwest", "Rust Belt"},
    "Wyoming": {"Mountain West", "Rocky Mountain States", "Great Plains"},
}


def regional_labels_for_state(state_name: str, region: str, division: str) -> set[str]:
    labels = {region, division}
    labels.update(REGIONAL_LABELS_BY_STATE.get(state_name, set()))
    return labels

# MVP list of commonly asked / recognizable highways. These are not meant to be
# a complete road inventory; they are stable quiz facts.
MAJOR_HIGHWAYS_BY_STATE = {
    "Alabama": {"I-10", "I-20", "I-22", "I-59", "I-65", "I-85"},
    "Alaska": set(),
    "Arizona": {"I-8", "I-10", "I-15", "I-17", "I-19", "I-40", "Route 66"},
    "Arkansas": {"I-30", "I-40", "I-49", "I-55", "I-57", "I-69"},
    "California": {"I-5", "I-8", "I-10", "I-15", "I-40", "I-80", "Route 66"},
    "Colorado": {"I-25", "I-70", "I-76"},
    "Connecticut": {"I-84", "I-91", "I-95"},
    "Delaware": {"I-95", "I-295", "I-495"},
    "Florida": {"I-4", "I-10", "I-75", "I-95"},
    "Georgia": {"I-16", "I-20", "I-24", "I-75", "I-85", "I-95"},
    "Hawaii": {"H-1", "H-2", "H-3"},
    "Idaho": {"I-15", "I-84", "I-86", "I-90"},
    "Illinois": {"I-24", "I-39", "I-55", "I-57", "I-64", "I-70", "I-72", "I-74", "I-80", "I-88", "I-90", "I-94", "Route 66"},
    "Indiana": {"I-64", "I-65", "I-69", "I-70", "I-74", "I-80", "I-90", "I-94"},
    "Iowa": {"I-29", "I-35", "I-74", "I-80"},
    "Kansas": {"I-35", "I-70", "I-135", "Route 66"},
    "Kentucky": {"I-24", "I-64", "I-65", "I-69", "I-71", "I-75"},
    "Louisiana": {"I-10", "I-12", "I-20", "I-49", "I-55", "I-59"},
    "Maine": {"I-95", "I-295"},
    "Maryland": {"I-68", "I-70", "I-81", "I-83", "I-95", "I-97"},
    "Massachusetts": {"I-84", "I-90", "I-91", "I-93", "I-95"},
    "Michigan": {"I-69", "I-75", "I-94", "I-96"},
    "Minnesota": {"I-35", "I-90", "I-94"},
    "Mississippi": {"I-10", "I-20", "I-22", "I-55", "I-59", "I-69"},
    "Missouri": {"I-29", "I-35", "I-44", "I-49", "I-55", "I-57", "I-64", "I-70", "Route 66"},
    "Montana": {"I-15", "I-90", "I-94"},
    "Nebraska": {"I-76", "I-80"},
    "Nevada": {"I-11", "I-15", "I-80"},
    "New Hampshire": {"I-89", "I-93", "I-95"},
    "New Jersey": {"I-76", "I-78", "I-80", "I-95", "I-287", "I-295"},
    "New Mexico": {"I-10", "I-25", "I-40", "Route 66"},
    "New York": {"I-78", "I-81", "I-84", "I-86", "I-87", "I-88", "I-90", "I-95"},
    "North Carolina": {"I-26", "I-40", "I-73", "I-74", "I-77", "I-85", "I-95"},
    "North Dakota": {"I-29", "I-94"},
    "Ohio": {"I-70", "I-71", "I-75", "I-76", "I-77", "I-80", "I-90"},
    "Oklahoma": {"I-35", "I-40", "I-44", "Route 66"},
    "Oregon": {"I-5", "I-84"},
    "Pennsylvania": {"I-70", "I-76", "I-78", "I-79", "I-80", "I-81", "I-83", "I-84", "I-90", "I-95"},
    "Rhode Island": {"I-95", "I-195", "I-295"},
    "South Carolina": {"I-20", "I-26", "I-77", "I-85", "I-95"},
    "South Dakota": {"I-29", "I-90"},
    "Tennessee": {"I-24", "I-26", "I-40", "I-55", "I-65", "I-75", "I-81"},
    "Texas": {"I-10", "I-14", "I-20", "I-27", "I-30", "I-35", "I-37", "I-40", "I-45", "I-69", "Route 66"},
    "Utah": {"I-15", "I-70", "I-80", "I-84"},
    "Vermont": {"I-89", "I-91", "I-93"},
    "Virginia": {"I-64", "I-66", "I-77", "I-81", "I-85", "I-95"},
    "Washington": {"I-5", "I-82", "I-90"},
    "West Virginia": {"I-64", "I-68", "I-70", "I-77", "I-79", "I-81"},
    "Wisconsin": {"I-39", "I-41", "I-43", "I-90", "I-94"},
    "Wyoming": {"I-25", "I-80", "I-90"},
}


@dataclass(frozen=True)
class USStateRow:
    name: str
    md_file: str


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def load_state_rows(csv_path: Path) -> list[USStateRow]:
    rows: list[USStateRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(USStateRow(name=row["name"], md_file=row["md_file"]))
    return rows


def clean_cell(text: str) -> str:
    text = text.replace("\\-", "-").replace("\\.", ".")
    text = text.replace("\xa0", " ")
    text = re.sub(r"Neutral (increase|decrease)\s+", "", text)
    text = re.sub(r"Increase\s+|Decrease\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_infobox(md_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in md_text.splitlines():
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        key = clean_cell(parts[0]).strip("• ")
        value = clean_cell(parts[1])
        if key and value and key not in {"---"}:
            values[key] = value
    return values


def first_key(info: dict[str, str], prefixes: tuple[str, ...]) -> str | None:
    for key, value in info.items():
        if any(key.startswith(prefix) for prefix in prefixes):
            return value
    return None


def parse_int(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"[0-9][0-9,]*", text)
    return int(match.group(0).replace(",", "")) if match else None


def parse_area_sq_mi(info: dict[str, str]) -> float | None:
    # The Total row after Area is usually stored as key "Total".
    area_text = info.get("Total")
    if not area_text:
        return None
    match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*sq\s*mi", area_text, re.I)
    if match:
        return float(match.group(1).replace(",", ""))
    return float(parse_int(area_text) or 0) or None


def parse_admission(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    year_match = re.search(r"\b(17|18|19|20)\d{2}\b", text)
    order_match = re.search(r"\((\d+)(?:st|nd|rd|th)\)", text)
    year = int(year_match.group(0)) if year_match else None
    order = int(order_match.group(1)) if order_match else None
    return year, order


def parse_nickname(info: dict[str, str], md_text: str) -> str | None:
    value = first_key(info, ("Nickname", "Nicknames"))
    if not value:
        for key in info:
            match = re.match(r"Nicknames?:\s*(.+)", key)
            if match:
                value = match.group(1)
                break
    if not value:
        match = re.search(r"^\|\s*Nicknames?:\s*([^|]+?)\s*\|", md_text, re.M)
        if match:
            value = clean_cell(match.group(1))
    if not value:
        return None
    value = re.sub(r"\s*\([^)]*\)", "", value)
    value = value.replace('"', "")
    return value.strip() or None


def dms_to_decimal(degrees: float, minutes: float, direction: str) -> float:
    value = degrees + minutes / 60.0
    return -value if direction in {"S", "W"} else value


def parse_coordinate_midpoint(text: str | None) -> float | None:
    if not text:
        return None
    normalized = text.replace("′", "'").replace("’", "'").replace("°", "°")
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s*°?\s*(?:(\d+(?:\.\d+)?)\s*['′])?\s*([NSEW])", re.I)
    values = []
    for deg, minutes, direction in pattern.findall(normalized):
        values.append(dms_to_decimal(float(deg), float(minutes or 0), direction.upper()))
    if values:
        return round(sum(values) / len(values), 4)
    return None


def load_regions() -> dict[str, tuple[str, str]]:
    text = fetch_text(CENSUS_REGIONS_CSV_URL)
    result: dict[str, tuple[str, str]] = {}
    for row in csv.DictReader(text.splitlines()):
        if row["State"] == "District of Columbia":
            continue
        result[row["State"]] = (row["Region"], row["Division"])
    return result


def load_adjacency() -> dict[str, dict]:
    return json.loads(fetch_text(STATE_ADJACENCY_JSON_URL))


def init_db(output_path: Path) -> sqlite3.Connection:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(output_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def insert_state_facts(output_path: Path, sample: bool = False) -> None:
    state_rows = load_state_rows(DATA_DIR / "us_states.csv")
    if sample:
        wanted = {"California", "Texas", "New York", "Florida", "Illinois", "Alaska", "Hawaii"}
        state_rows = [row for row in state_rows if row.name in wanted]

    regions = load_regions()
    adjacency = load_adjacency()
    code_by_name = {data["name"]: code for code, data in adjacency.items()}
    name_by_code = {code: data["name"] for code, data in adjacency.items()}

    conn = init_db(output_path)
    try:
        for idx, row in enumerate(state_rows, start=1):
            md_path = ROOT_DIR / row.md_file.replace("\\", "/")
            md_text = md_path.read_text(encoding="utf-8")
            info = parse_infobox(md_text)
            code = first_key(info, ("USPS abbreviation",)) or code_by_name.get(row.name)
            region, division = regions[row.name]
            admission_year, admission_order = parse_admission(first_key(info, ("Admitted to the Union",)))
            admission_order = admission_order or ADMISSION_ORDER_BY_STATE.get(row.name)
            latitude = parse_coordinate_midpoint(first_key(info, ("Latitude",)))
            longitude = parse_coordinate_midpoint(first_key(info, ("Longitude",)))
            if row.name in COORDINATE_OVERRIDES:
                latitude, longitude = COORDINATE_OVERRIDES[row.name]
            population = parse_int(first_key(info, ("Total",)))

            # Infobox has several "Total" keys in markdown extraction; population is safer from the
            # line immediately following Population if present. Fallback to regex over full article header.
            pop_match = re.search(r"\| Population[^\n]*\| \|\n\| •\s*Total \|([^|]+)\|", md_text)
            if pop_match:
                population = parse_int(clean_cell(pop_match.group(1)))

            area = parse_area_sq_mi(info)
            area_match = re.search(r"\| Area \| \|\n\| •\s*Total \|([^|]+)\|", md_text)
            if area_match:
                area = parse_area_sq_mi({"Total": clean_cell(area_match.group(1))})

            is_coastal = 1 if row.name in OCEAN_OR_GULF_COASTAL_STATES else 0

            conn.execute(
                """
                INSERT INTO us_states (
                    id, name, region, division, population, area_sq_mi,
                    latitude, longitude, is_coastal, admission_year, admission_order,
                    nickname, civil_war_side, md_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idx,
                    row.name,
                    region,
                    division,
                    population,
                    area,
                    latitude,
                    longitude,
                    is_coastal,
                    admission_year,
                    admission_order,
                    parse_nickname(info, md_text),
                    CIVIL_WAR_SIDE_BY_STATE[row.name],
                    row.md_file,
                ),
            )

            state_code = code_by_name[row.name]
            for border_code in adjacency[state_code].get("adjacent", []):
                border_name = name_by_code[border_code]
                if sample and border_name not in {r.name for r in state_rows}:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO us_state_borders_states VALUES (?, ?, ?)",
                    (idx, border_name, border_code),
                )

            if row.name in CANADA_BORDER_STATES:
                conn.execute("INSERT OR IGNORE INTO us_state_borders_countries VALUES (?, ?)", (idx, "Canada"))
            if row.name in MEXICO_BORDER_STATES:
                conn.execute("INSERT OR IGNORE INTO us_state_borders_countries VALUES (?, ?)", (idx, "Mexico"))

            for highway in sorted(MAJOR_HIGHWAYS_BY_STATE.get(row.name, set())):
                conn.execute("INSERT OR IGNORE INTO us_state_major_highways VALUES (?, ?)", (idx, highway))

            for label in sorted(regional_labels_for_state(row.name, region, division)):
                conn.execute("INSERT OR IGNORE INTO us_state_regional_labels VALUES (?, ?)", (idx, label))

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build US Statedle local facts SQLite database.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample", action="store_true", help="Build a small sample database.")
    args = parser.parse_args()

    insert_state_facts(args.output, sample=args.sample)
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
