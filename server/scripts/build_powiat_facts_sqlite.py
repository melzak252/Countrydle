"""Build local SQLite facts database for Powiatdle.

Creates `data/powiat_facts.sqlite` from local markdown files. This is an MVP
builder: scalar administrative fields are parsed from infoboxes, while borders,
roads, rivers and landform regions are extracted with conservative regexes and
gazetteers from local Wikipedia markdown.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT = DATA_DIR / "powiat_facts.sqlite"
SCHEMA_PATH = ROOT_DIR / "server" / "powiatdle" / "local_kb" / "schema.sql"


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


def normalize_name(value: str) -> str:
    value = clean_text(value) or ""
    value = re.sub(r"\s*\([^)]*\)", "", value)
    value = re.sub(r"^(powiat|miasto)\s+", "", value, flags=re.I)
    return value.strip().lower()


def genitive_variants(powiat_name: str) -> set[str]:
    base = re.sub(r"^Powiat\s+", "", powiat_name).strip().lower()
    variants = {base}
    for suffix in ("ski", "cki", "dzki"):
        if base.endswith(suffix):
            variants.add(base[:-1] + "ego")
    if base.endswith("ki"):
        variants.add(base[:-1] + "ego")
    if base.endswith("y"):
        variants.add(base[:-1] + "ego")
    return variants


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


def choose_candidate(candidates: list[str], prefer_voivodeship: str, voivodeship_by_name: dict[str, str]) -> str | None:
    if not candidates:
        return None
    for candidate in candidates:
        if voivodeship_by_name.get(candidate) == prefer_voivodeship:
            return candidate
    if len(candidates) > 1:
        # Ambiguous county names exist in several voivodeships (e.g. bielski,
        # nowodworski, średzki). If the source text does not disambiguate and
        # none is in the same voivodeship, skip instead of creating a false edge.
        return None
    return candidates[0]


def extract_neighbors(
    text: str,
    name_by_norm: dict[str, list[str]],
    genitive_by_norm: dict[str, list[str]],
    prefer_voivodeship: str,
    voivodeship_by_name: dict[str, str],
    include_prose: bool = False,
) -> list[str]:
    section = extract_section(text, r"^(#{2,4})\s+Sąsiednie powiaty\b.*$")
    neighbors: set[str] = set()
    for line in section.splitlines() if section else []:
        if not line.lstrip().startswith("*"):
            continue
        item = re.sub(r"^\s*\*\s*", "", line)
        item = re.sub(r"\([^)]*\)", "", item)
        item = clean_text(item) or ""
        candidate = choose_candidate(name_by_norm.get(normalize_name(item), []), prefer_voivodeship, voivodeship_by_name)
        if candidate:
            neighbors.add(candidate)
            continue
        # Try after removing adjectives like "powiat" already handled.
        words = re.sub(r"\b(miasto na prawach powiatu|powiat)\b", "", item, flags=re.I)
        candidate = choose_candidate(name_by_norm.get(normalize_name(words), []), prefer_voivodeship, voivodeship_by_name)
        if candidate:
            neighbors.add(candidate)
    if not include_prose:
        return sorted(neighbors)

    # City-county pages often describe neighboring powiats in prose, e.g.
    # "powiatów sąsiadujących z Krakowem: krakowskiego, wielickiego...".
    prose = text[:7000].lower().replace("\n", " ")
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        if "powiat" not in sentence or not re.search(r"sąsiad|sasiad|granic", sentence):
            continue
        for variant, canonical in genitive_by_norm.items():
            if re.search(r"(?<![\wąćęłńóśźż])" + re.escape(variant) + r"(?![\wąćęłńóśźż])", sentence, flags=re.I):
                candidate = choose_candidate(canonical, prefer_voivodeship, voivodeship_by_name)
                if candidate:
                    neighbors.add(candidate)
    return sorted(neighbors)


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


def build_database(output_path: Path) -> None:
    rows = load_rows(DATA_DIR / "powiaty.csv")
    name_by_norm: dict[str, list[str]] = {}
    for row in rows:
        name_by_norm.setdefault(normalize_name(row.name), []).append(row.name)
    genitive_by_norm: dict[str, list[str]] = {}
    for row in rows:
        if row.name.startswith("Powiat "):
            for variant in genitive_variants(row.name):
                genitive_by_norm.setdefault(variant, []).append(row.name)

    conn = init_db(output_path)
    cur = conn.cursor()
    voivodeship_by_name: dict[str, str] = {}
    neighbors_by_name: dict[str, list[str]] = {}

    for row in rows:
        md_path = ROOT_DIR / row.md_file.replace("\\", "/")
        text = md_path.read_text(encoding="utf-8")
        voivodeship_by_name[row.name] = table_value(text, "Województwo") or ""

    parsed_payloads = []
    for row in rows:
        md_path = ROOT_DIR / row.md_file.replace("\\", "/")
        text = md_path.read_text(encoding="utf-8")
        is_city = "miasto na prawach powiatu" in text[:800].lower()
        voivodeship = voivodeship_by_name[row.name]
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
        neighbors = [
            n
            for n in extract_neighbors(
                text,
                name_by_norm,
                genitive_by_norm,
                voivodeship,
                voivodeship_by_name,
                include_prose=is_city,
            )
            if n != row.name
        ]
        neighbors_by_name[row.name] = neighbors
        parsed_payloads.append((row, text, is_city, voivodeship, seat, area, population, density, urbanization, gmina_count, urban, rural, urban_rural))

    for payload in parsed_payloads:
        row, text, is_city, voivodeship, seat, area, population, density, urbanization, gmina_count, urban, rural, urban_rural = payload
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
        neighbors = neighbors_by_name[row.name]
        insert_many(conn, "powiat_borders_powiats", row.id, "border_powiat_name", neighbors)
        border_voivodeships = sorted({voivodeship_by_name[n] for n in neighbors if voivodeship_by_name.get(n) and voivodeship_by_name[n] != voivodeship})
        insert_many(conn, "powiat_borders_voivodeships", row.id, "voivodeship", border_voivodeships)
        insert_many(conn, "powiat_borders_countries", row.id, "country_name", extract_countries(text))
        plates = parse_plates(table_value(text, "Tablice rejestracyjne")) or MANUAL_PLATES.get(row.name, [])
        insert_many(conn, "powiat_registration_plates", row.id, "plate_code", plates)
        insert_many(conn, "powiat_major_roads", row.id, "road_name", extract_roads(text))
        insert_many(conn, "powiat_major_rivers", row.id, "river_name", extract_gazetteer(text, RIVER_GAZETTEER))
        insert_many(conn, "powiat_landform_regions", row.id, "region_name", extract_gazetteer(text, LANDFORM_GAZETTEER))

    conn.commit()
    conn.close()
    print(f"Created {output_path} with {len(rows)} powiats")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Powiatdle local facts SQLite database")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_database(args.output)


if __name__ == "__main__":
    main()
