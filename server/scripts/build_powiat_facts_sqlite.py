"""Build local SQLite facts database for Powiatdle.

Administrative and descriptive facts come from local Wikipedia markdown.
County adjacency comes exclusively from the full-resolution PRG snapshot.
Use --refresh-borders to replace only county/province borders and their lookup
metadata, preserving all other facts, including manual edits.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = APP_DIR if (APP_DIR / "data").exists() else APP_DIR.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT = DATA_DIR / "powiat_facts.sqlite"
SCHEMA_PATH = APP_DIR / "powiatdle" / "local_kb" / "schema.sql"
DEFAULT_BORDERS = APP_DIR / "powiatdle" / "local_kb" / "borders.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from powiat_names import build_powiat_aliases


COUNTRY_ALIASES = {
    "niemc": "Niemcy",
    "czech": "Czechy",
    "słowac": "Słowacja",
    "slowac": "Słowacja",
    "ukrain": "Ukraina",
    "białor": "Białoruś",
    "bialor": "Białoruś",
    "litw": "Litwa",
    "rosj": "Rosja",
}

MANUAL_PLATES = {
    "Warszawa": ["WA", "WB", "WD", "WE", "WF", "WH", "WI", "WJ", "WK", "WN", "WT", "WU", "WW", "WX", "WY"],
}

RIVER_GAZETTEER = [
    "Wisła", "Odra", "Warta", "Bug", "Narew", "San", "Dunajec", "Poprad", "Raba", "Skawa",
    "Bóbr", "Nysa Kłodzka", "Nysa Łużycka", "Noteć", "Brda", "Drwęca", "Wieprz", "Pilica",
    "Bzura", "Prosna", "Nida", "Kamienna", "Czarna Nida", "Łyna", "Pasłęka", "Węgorapa",
    "Słupia", "Łeba", "Wda", "Radunia", "Rega", "Parsęta", "Ina", "Drawa", "Wisłok",
    "Wisłoka", "Biebrza", "Czarna Hańcza", "Przemsza", "Ner", "Obra", "Soła", "Biała",
    "Rudawa", "Prądnik", "Dłubnia", "Wilga", "Sanka", "Bystrzyca", "Wieprza", "Gwda",
    "Pisa", "Omulew", "Orzyc", "Liwiec", "Tanew", "Łabuńka", "Netta", "Supraśl", "Barycz",
]

LANDFORM_GAZETTEER = [
    "Beskid Śląski", "Beskid Żywiecki", "Beskid Mały", "Beskid Sądecki", "Beskid Niski",
    "Bieszczady", "Tatry", "Pieniny", "Gorce", "Sudety", "Karkonosze", "Góry Stołowe",
    "Góry Sowie", "Góry Opawskie", "Góry Świętokrzyskie", "Jura Krakowsko-Częstochowska",
    "Wyżyna Krakowsko-Częstochowska", "Wyżyna Lubelska", "Wyżyna Kielecka", "Wyżyna Śląska",
    "Wyżyna Małopolska", "Roztocze", "Polesie", "Podhale", "Kotlina Sandomierska",
    "Kotlina Oświęcimska", "Kotlina Kłodzka", "Nizina Śląska", "Nizina Mazowiecka",
    "Nizina Wielkopolska", "Nizina Podlaska", "Nizina Szczecińska", "Pojezierze Mazurskie",
    "Pojezierze Pomorskie", "Pojezierze Wielkopolskie", "Pojezierze Lubuskie", "Pojezierze Suwalskie",
    "Pobrzeże Gdańskie", "Pobrzeże Szczecińskie", "Pobrzeże Koszalińskie", "Żuławy Wiślane",
    "Kaszuby", "Kujawy", "Mazowsze", "Podlasie", "Wielkopolska", "Małopolska", "Śląsk",
]


@dataclass(frozen=True)
class PowiatRow:
    id: int
    name: str
    md_file: str


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace("\\-", "-").replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |\t\r\n")






def load_rows(csv_path: Path) -> list[PowiatRow]:
    rows: list[PowiatRow] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for idx, row in enumerate(csv.DictReader(f), start=1):
            rows.append(PowiatRow(idx, row["name"], row["md_file"]))
    return rows


def table_value(text: str, label: str) -> str | None:
    text = text.replace("\\-", "-")
    pattern = r"\|\s*" + re.escape(label) + r"[^|]*\|([^|]+)\|"
    m = re.search(pattern, text, flags=re.I)
    return clean_text(m.group(1)) if m else None


def parse_float_pl(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"([0-9][0-9\s]*)(?:,([0-9]+))?", value.replace("\xa0", " "))
    if not m:
        return None
    whole = m.group(1).replace(" ", "")
    frac = m.group(2) or ""
    return float(f"{whole}.{frac}" if frac else whole)


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def parse_population(value: str | None, area_km2: float | None) -> int | None:
    if not value:
        return None
    value = value.replace("\xa0", " ")
    if "os./km" not in value:
        return parse_int(value)

    before_density = value.split("os./km", 1)[0]
    digits = re.sub(r"[^0-9]", "", before_density)
    if not digits:
        return None
    if not area_km2:
        # City counties usually have 5-7 digit population at the start.
        return int(digits[:7]) if len(digits) >= 7 else int(digits[:6])

    best: tuple[float, int] | None = None
    for split in range(4, min(8, len(digits))):
        pop = int(digits[:split])
        rest = digits[split:]
        if pop < 10_000 or pop > 2_500_000 or not rest:
            continue
        density_actual = pop / area_km2
        possible_densities = [float(rest)]
        if len(rest) >= 2:
            possible_densities.append(float(rest) / 10)
        if len(rest) >= 3:
            possible_densities.append(float(rest) / 100)
        score = min(abs(density_actual - d) for d in possible_densities)
        if best is None or score < best[0]:
            best = (score, pop)
    return best[1] if best else parse_int(value)


def parse_plates(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted(set(re.findall(r"\b[A-ZŻŹŁŚĆŃÓ]{2,4}\b", value)))


def extract_section(text: str, heading_regex: str) -> str:
    m = re.search(heading_regex, text, flags=re.I | re.M)
    if not m:
        return ""
    level = len(m.group(1)) if m.lastindex else 2
    start = m.end()
    next_heading = re.search(r"^#{1," + str(level) + r"}\s+", text[start:], flags=re.M)
    return text[start : start + next_heading.start()] if next_heading else text[start:]






def extract_countries(text: str) -> list[str]:
    hay = text[:6000].lower().replace("\n", " ")
    found = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\s{2,}", hay):
        if not re.search(r"granic|granica|sąsiad|sasiad", sentence):
            continue
        for needle, country in COUNTRY_ALIASES.items():
            if needle in sentence:
                found.add(country)
    return sorted(found)


def extract_roads(text: str) -> list[str]:
    section = "\n".join(
        s for s in [
            extract_section(text, r"^(#{2,4})\s+Komunikacja\b.*$"),
            extract_section(text, r"^(#{2,4})\s+Transport\b.*$"),
            extract_section(text, r"^(#{2,4})\s+Drogi\b.*$"),
        ] if s
    ) or text[:5000]
    roads = set()
    for m in re.finditer(r"\bA\s*\d{1,2}\b|\bS\s*\d{1,2}\b", section):
        roads.add(re.sub(r"\s+", "", m.group(0).upper()))
    for m in re.finditer(r"(?:drogi? krajowe|DK)\s*:?\s*([0-9, ioraz\-–]+)", section, flags=re.I):
        for num in re.findall(r"\d{1,3}", m.group(1)):
            roads.add(f"DK{num}")
    for m in re.finditer(r"(?:drogi? wojewódzkie|DW)\s*:?\s*([0-9, ioraz\-–]+)", section, flags=re.I):
        for num in re.findall(r"\d{3}", m.group(1)):
            roads.add(f"DW{num}")
    return sorted(roads)


def extract_gazetteer(text: str, names: list[str]) -> list[str]:
    context = "\n".join([
        text[:3500],
        extract_section(text, r"^(#{2,4})\s+Geografia\b.*$"),
        extract_section(text, r"^(#{2,4})\s+Położenie\b.*$"),
        extract_section(text, r"^(#{2,4})\s+Środowisko naturalne\b.*$"),
        extract_section(text, r"^(#{2,4})\s+Rzeki\b.*$"),
    ])
    found = set()
    for name in names:
        if re.search(r"(?<![\wąćęłńóśźż])" + re.escape(name) + r"(?![\wąćęłńóśźż])", context, flags=re.I):
            found.add(name)
    return sorted(found)


def init_db(output_path: Path) -> sqlite3.Connection:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(output_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def insert_many(conn: sqlite3.Connection, table: str, powiat_id: int, column: str, values: list[str]) -> None:
    conn.executemany(
        f"INSERT OR IGNORE INTO {table} (powiat_id, {column}) VALUES (?, ?)",
        [(powiat_id, value) for value in values if value],
    )


def replace_border_facts(conn: sqlite3.Connection, borders_path: Path) -> dict[str, int]:
    snapshot = json.loads(borders_path.read_text(encoding="utf-8"))
    columns = ("id", "name", "voivodeship", "is_city_county", "terc")
    catalog = [
        dict(zip(columns, row))
        for row in conn.execute("SELECT id, name, voivodeship, is_city_county, terc FROM powiats")
    ]
    by_code = {}
    for row in catalog:
        terc = str(row["terc"] or "").strip()
        if not re.fullmatch(r"\d{4}(?:\d{3})?", terc):
            raise ValueError(f"Invalid county TERC: {row['name']}")
        code = terc[:4]
        if code in by_code:
            raise ValueError(f"Duplicate county TERYT: {code}")
        if not row["voivodeship"]:
            raise ValueError(f"Missing county voivodeship: {row['name']}")
        by_code[code] = row
    expected = snapshot["counties"]
    if (
        snapshot.get("schema_version") != 1
        or not by_code
        or len(expected) != len(set(expected))
        or set(expected) != by_code.keys()
    ):
        raise ValueError("Border snapshot and county catalog do not match")
    edges = set()
    for pair in snapshot["borders"]:
        if len(pair) != 2:
            raise ValueError(f"Invalid county border: {pair!r}")
        left, right = sorted(pair)
        if left == right or left not in by_code or right not in by_code or (left, right) in edges:
            raise ValueError(f"Unknown, duplicate or self border: {pair!r}")
        edges.add((left, right))
    if {code for edge in edges for code in edge} != by_code.keys():
        raise ValueError("Border snapshot leaves counties without verified neighbors")

    border_rows = []
    province_rows = set()
    for left, right in sorted(edges):
        for source, target in ((by_code[left], by_code[right]), (by_code[right], by_code[left])):
            border_rows.append((source["id"], target["name"]))
            if source["voivodeship"] != target["voivodeship"]:
                province_rows.add((source["id"], target["voivodeship"]))
    aliases = build_powiat_aliases(catalog)

    # Validate everything before changing an existing database. These two tables
    # also upgrade databases created before verified adjacency was introduced.
    with conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS powiat_name_aliases ("
            "alias TEXT NOT NULL, powiat_id INTEGER NOT NULL, PRIMARY KEY (alias, powiat_id), "
            "FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS powiat_border_coverage ("
            "powiat_id INTEGER PRIMARY KEY, "
            "FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)"
        )
        for table in (
            "powiat_borders_powiats", "powiat_borders_voivodeships",
            "powiat_name_aliases", "powiat_border_coverage",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany("INSERT INTO powiat_borders_powiats VALUES (?, ?)", border_rows)
        conn.executemany("INSERT INTO powiat_borders_voivodeships VALUES (?, ?)", sorted(province_rows))
        conn.executemany(
            "INSERT INTO powiat_name_aliases VALUES (?, ?)",
            [(alias, identifier) for alias, ids in sorted(aliases.items()) for identifier in sorted(ids)],
        )
        conn.executemany("INSERT INTO powiat_border_coverage VALUES (?)", [(row["id"],) for row in catalog])
    return {
        "counties": len(catalog),
        "directed_borders": len(border_rows),
        "province_borders": len(province_rows),
    }


def refresh_borders(output_path: Path, borders_path: Path = DEFAULT_BORDERS) -> dict[str, int]:
    conn = sqlite3.connect(output_path.resolve().as_uri() + "?mode=rw", uri=True)
    try:
        return replace_border_facts(conn, borders_path)
    finally:
        conn.close()


def build_database(output_path: Path, borders_path: Path = DEFAULT_BORDERS) -> None:
    rows = load_rows(DATA_DIR / "powiaty.csv")

    conn = init_db(output_path)
    cur = conn.cursor()
    for row in rows:
        md_path = ROOT_DIR / row.md_file.replace("\\", "/")
        text = md_path.read_text(encoding="utf-8")
        is_city = "miasto na prawach powiatu" in text[:800].lower()
        voivodeship = table_value(text, "Województwo") or ""
        area = parse_float_pl(table_value(text, "Powierzchnia"))
        population = parse_population(table_value(text, "Populacja"), area)
        density = parse_float_pl(table_value(text, "gęstość"))
        if density is None and population and area:
            density = round(population / area, 2)
        seat = table_value(text, "Siedziba") or (row.name if is_city else None)
        urbanization = parse_float_pl(table_value(text, "Urbanizacja"))
        urban_rural = parse_int(table_value(text, "Liczba gmin miejsko-wiejskich")) or 0
        rural = parse_int(table_value(text, "Liczba gmin wiejskich")) or 0
        urban = parse_int(table_value(text, "Liczba gmin miejskich")) or 0
        gmina_count = urban + rural + urban_rural if (urban or rural or urban_rural) else (1 if is_city else None)
        cur.execute(
            """
            INSERT INTO powiats (
                id, name, voivodeship, is_city_county, seat, terc, population, area_km2,
                population_density, urbanization_percent, gmina_count, urban_gmina_count,
                rural_gmina_count, urban_rural_gmina_count, md_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.id,
                row.name,
                voivodeship,
                1 if is_city else 0,
                seat,
                table_value(text, "TERC") or table_value(text, "TERC (TERYT)"),
                population,
                area,
                density,
                urbanization,
                gmina_count,
                urban,
                rural,
                urban_rural,
                row.md_file,
            ),
        )
        insert_many(conn, "powiat_borders_countries", row.id, "country_name", extract_countries(text))
        plates = parse_plates(table_value(text, "Tablice rejestracyjne")) or MANUAL_PLATES.get(row.name, [])
        insert_many(conn, "powiat_registration_plates", row.id, "plate_code", plates)
        insert_many(conn, "powiat_major_roads", row.id, "road_name", extract_roads(text))
        insert_many(conn, "powiat_major_rivers", row.id, "river_name", extract_gazetteer(text, RIVER_GAZETTEER))
        insert_many(conn, "powiat_landform_regions", row.id, "region_name", extract_gazetteer(text, LANDFORM_GAZETTEER))

    counts = replace_border_facts(conn, borders_path)
    conn.close()
    print(json.dumps({"output": str(output_path), **counts}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Powiatdle local facts SQLite database")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--borders", type=Path, default=DEFAULT_BORDERS)
    parser.add_argument("--refresh-borders", action="store_true", help="Preserve all non-border facts")
    args = parser.parse_args()
    if args.refresh_borders:
        print(json.dumps({"output": str(args.output), **refresh_borders(args.output, args.borders)}, ensure_ascii=False))
    else:
        build_database(args.output, args.borders)


if __name__ == "__main__":
    main()
