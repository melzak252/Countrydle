"""Build local SQLite facts database for Wojewodztwodle.

Creates `data/voivodeship_facts.sqlite` from local markdown files plus small
curated maps for stable relations such as borders and broad regions.
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
DEFAULT_OUTPUT = DATA_DIR / "voivodeship_facts.sqlite"
SCHEMA_PATH = ROOT_DIR / "server" / "wojewodztwodle" / "local_kb" / "schema.sql"


MACROREGION_BY_VOIVODESHIP = {
    "Dolnośląskie": "południowy zachód",
    "Kujawsko-Pomorskie": "północne centrum",
    "Lubelskie": "wschód",
    "Lubuskie": "zachód",
    "Mazowieckie": "centrum",
    "Małopolskie": "południe",
    "Opolskie": "południowy zachód",
    "Podkarpackie": "południowy wschód",
    "Podlaskie": "północny wschód",
    "Pomorskie": "północ",
    "Warmińsko-Mazurskie": "północny wschód",
    "Wielkopolskie": "zachodnie centrum",
    "Zachodniopomorskie": "północny zachód",
    "Łódzkie": "centrum",
    "Śląskie": "południe",
    "Świętokrzyskie": "południowe centrum",
}

REGIONAL_LABELS_BY_VOIVODESHIP = {
    "Dolnośląskie": ["zachodnia Polska", "południowa Polska", "południowo-zachodnia Polska", "Dolny Śląsk", "Śląsk"],
    "Kujawsko-Pomorskie": ["północna Polska", "centralna Polska", "północno-centralna Polska", "Kujawy", "Pomorze"],
    "Lubelskie": ["wschodnia Polska", "południowo-wschodnia Polska", "Lubelszczyzna", "Polska wschodnia"],
    "Lubuskie": ["zachodnia Polska", "Polska zachodnia", "Ziemia lubuska"],
    "Mazowieckie": ["centralna Polska", "Mazowsze", "Polska centralna"],
    "Małopolskie": ["południowa Polska", "południowo-wschodnia Polska", "Małopolska", "Podhale"],
    "Opolskie": ["zachodnia Polska", "południowa Polska", "południowo-zachodnia Polska", "Śląsk", "Górny Śląsk"],
    "Podkarpackie": ["południowa Polska", "wschodnia Polska", "południowo-wschodnia Polska", "Podkarpacie", "Polska wschodnia"],
    "Podlaskie": ["północna Polska", "wschodnia Polska", "północno-wschodnia Polska", "Podlasie", "Polska wschodnia"],
    "Pomorskie": ["północna Polska", "nadmorska Polska", "Pomorze", "Kaszuby", "Wybrzeże Bałtyku"],
    "Warmińsko-Mazurskie": ["północna Polska", "wschodnia Polska", "północno-wschodnia Polska", "Warmia", "Mazury"],
    "Wielkopolskie": ["zachodnia Polska", "centralna Polska", "zachodnio-centralna Polska", "Wielkopolska"],
    "Zachodniopomorskie": ["północna Polska", "zachodnia Polska", "północno-zachodnia Polska", "nadmorska Polska", "Pomorze Zachodnie", "Wybrzeże Bałtyku"],
    "Łódzkie": ["centralna Polska", "Polska centralna", "Ziemia łódzka"],
    "Śląskie": ["południowa Polska", "południowo-zachodnia Polska", "Śląsk", "Górny Śląsk", "Zagłębie Dąbrowskie"],
    "Świętokrzyskie": ["centralna Polska", "południowa Polska", "południowo-centralna Polska", "Małopolska", "Ziemia świętokrzyska"],
}

CENTROID_BY_VOIVODESHIP = {
    "Dolnośląskie": (51.10, 16.40),
    "Kujawsko-Pomorskie": (53.00, 18.50),
    "Lubelskie": (51.25, 22.90),
    "Lubuskie": (52.10, 15.30),
    "Mazowieckie": (52.20, 21.00),
    "Małopolskie": (49.90, 20.10),
    "Opolskie": (50.70, 17.90),
    "Podkarpackie": (49.90, 22.00),
    "Podlaskie": (53.20, 23.20),
    "Pomorskie": (54.30, 18.20),
    "Warmińsko-Mazurskie": (53.80, 20.70),
    "Wielkopolskie": (52.30, 17.00),
    "Zachodniopomorskie": (53.60, 15.50),
    "Łódzkie": (51.60, 19.40),
    "Śląskie": (50.30, 19.00),
    "Świętokrzyskie": (50.80, 20.80),
}

BORDERS_VOIVODESHIPS = {
    "Dolnośląskie": ["Lubuskie", "Wielkopolskie", "Opolskie"],
    "Kujawsko-Pomorskie": ["Pomorskie", "Warmińsko-Mazurskie", "Mazowieckie", "Łódzkie", "Wielkopolskie"],
    "Lubelskie": ["Podlaskie", "Mazowieckie", "Świętokrzyskie", "Podkarpackie"],
    "Lubuskie": ["Zachodniopomorskie", "Wielkopolskie", "Dolnośląskie"],
    "Mazowieckie": ["Kujawsko-Pomorskie", "Warmińsko-Mazurskie", "Podlaskie", "Lubelskie", "Świętokrzyskie", "Łódzkie"],
    "Małopolskie": ["Śląskie", "Świętokrzyskie", "Podkarpackie"],
    "Opolskie": ["Dolnośląskie", "Wielkopolskie", "Łódzkie", "Śląskie"],
    "Podkarpackie": ["Małopolskie", "Świętokrzyskie", "Lubelskie"],
    "Podlaskie": ["Warmińsko-Mazurskie", "Mazowieckie", "Lubelskie"],
    "Pomorskie": ["Zachodniopomorskie", "Wielkopolskie", "Kujawsko-Pomorskie", "Warmińsko-Mazurskie"],
    "Warmińsko-Mazurskie": ["Pomorskie", "Kujawsko-Pomorskie", "Mazowieckie", "Podlaskie"],
    "Wielkopolskie": ["Zachodniopomorskie", "Pomorskie", "Kujawsko-Pomorskie", "Łódzkie", "Opolskie", "Dolnośląskie", "Lubuskie"],
    "Zachodniopomorskie": ["Pomorskie", "Wielkopolskie", "Lubuskie"],
    "Łódzkie": ["Wielkopolskie", "Kujawsko-Pomorskie", "Mazowieckie", "Świętokrzyskie", "Śląskie", "Opolskie"],
    "Śląskie": ["Opolskie", "Łódzkie", "Świętokrzyskie", "Małopolskie"],
    "Świętokrzyskie": ["Łódzkie", "Mazowieckie", "Lubelskie", "Podkarpackie", "Małopolskie", "Śląskie"],
}

BORDERS_COUNTRIES = {
    "Dolnośląskie": ["Czechy", "Niemcy"],
    "Lubuskie": ["Niemcy"],
    "Lubelskie": ["Białoruś", "Ukraina"],
    "Małopolskie": ["Słowacja"],
    "Opolskie": ["Czechy"],
    "Podkarpackie": ["Słowacja", "Ukraina"],
    "Podlaskie": ["Białoruś", "Litwa"],
    "Warmińsko-Mazurskie": ["Rosja"],
    "Zachodniopomorskie": ["Niemcy"],
    "Śląskie": ["Czechy", "Słowacja"],
}

WATER_ACCESS = {
    "Pomorskie": ["Morze Bałtyckie"],
    "Zachodniopomorskie": ["Morze Bałtyckie"],
}

MAJOR_RIVERS = {
    "Dolnośląskie": ["Odra", "Bóbr", "Nysa Kłodzka", "Bystrzyca"],
    "Kujawsko-Pomorskie": ["Wisła", "Brda", "Drwęca", "Noteć"],
    "Lubelskie": ["Wisła", "Bug", "Wieprz", "Tyśmienica"],
    "Lubuskie": ["Odra", "Warta", "Noteć", "Bóbr", "Nysa Łużycka"],
    "Mazowieckie": ["Wisła", "Bug", "Narew", "Pilica", "Bzura"],
    "Małopolskie": ["Wisła", "Dunajec", "Poprad", "Raba", "Skawa"],
    "Opolskie": ["Odra", "Nysa Kłodzka", "Mała Panew"],
    "Podkarpackie": ["Wisła", "San", "Wisłok", "Wisłoka"],
    "Podlaskie": ["Narew", "Bug", "Biebrza", "Czarna Hańcza"],
    "Pomorskie": ["Wisła", "Słupia", "Łeba", "Wda", "Radunia"],
    "Warmińsko-Mazurskie": ["Łyna", "Pasłęka", "Drwęca", "Węgorapa"],
    "Wielkopolskie": ["Warta", "Noteć", "Prosna", "Obra"],
    "Zachodniopomorskie": ["Odra", "Rega", "Parsęta", "Ina", "Drawa"],
    "Łódzkie": ["Warta", "Pilica", "Bzura", "Ner"],
    "Śląskie": ["Wisła", "Odra", "Warta", "Przemsza"],
    "Świętokrzyskie": ["Wisła", "Nida", "Kamienna", "Czarna Nida"],
}

MOUNTAIN_RANGES = {
    "Dolnośląskie": ["Sudety", "Karkonosze", "Góry Stołowe", "Góry Sowie"],
    "Małopolskie": ["Karpaty", "Tatry", "Beskidy", "Pieniny"],
    "Opolskie": ["Sudety", "Góry Opawskie"],
    "Podkarpackie": ["Karpaty", "Bieszczady", "Beskid Niski"],
    "Śląskie": ["Karpaty", "Beskidy", "Beskid Śląski", "Jura Krakowsko-Częstochowska"],
    "Świętokrzyskie": ["Góry Świętokrzyskie"],
}

HISTORICAL_REGIONS = {
    "Dolnośląskie": ["Dolny Śląsk", "Łużyce"],
    "Kujawsko-Pomorskie": ["Kujawy", "Pomorze", "Ziemia chełmińska", "Pałuki"],
    "Lubelskie": ["Lubelszczyzna", "Małopolska", "Polesie", "Podlasie"],
    "Lubuskie": ["Ziemia lubuska", "Dolny Śląsk", "Wielkopolska", "Łużyce"],
    "Mazowieckie": ["Mazowsze", "Podlasie", "Małopolska"],
    "Małopolskie": ["Małopolska", "Podhale", "Spisz", "Orawa"],
    "Opolskie": ["Śląsk", "Górny Śląsk"],
    "Podkarpackie": ["Małopolska", "Ruś Czerwona", "Podkarpacie"],
    "Podlaskie": ["Podlasie", "Suwalszczyzna"],
    "Pomorskie": ["Pomorze", "Kaszuby", "Kociewie", "Żuławy"],
    "Warmińsko-Mazurskie": ["Warmia", "Mazury", "Powiśle"],
    "Wielkopolskie": ["Wielkopolska", "Pałuki"],
    "Zachodniopomorskie": ["Pomorze Zachodnie"],
    "Łódzkie": ["Ziemia łęczycka", "Ziemia sieradzka", "Mazowsze", "Wielkopolska"],
    "Śląskie": ["Śląsk", "Górny Śląsk", "Zagłębie Dąbrowskie", "Małopolska"],
    "Świętokrzyskie": ["Małopolska", "Ziemia sandomierska"],
}

LANDFORM_REGIONS = {
    "Dolnośląskie": ["Sudety", "Przedgórze Sudeckie", "Nizina Śląska"],
    "Kujawsko-Pomorskie": ["Pojezierze Południowobałtyckie", "Pojezierze Chełmińsko-Dobrzyńskie", "Pradolina Toruńsko-Eberswaldzka", "Kujawy"],
    "Lubelskie": ["Wyżyna Lubelska", "Polesie Zachodnie", "Roztocze", "Nizina Południowopodlaska"],
    "Lubuskie": ["Pojezierze Lubuskie", "Pradolina Toruńsko-Eberswaldzka", "Wzniesienia Zielonogórskie", "Nizina Środkowopolska"],
    "Mazowieckie": ["Nizina Środkowomazowiecka", "Nizina Północnomazowiecka", "Nizina Południowopodlaska", "Wyżyna Małopolska"],
    "Małopolskie": ["Karpaty", "Tatry", "Beskidy", "Wyżyna Krakowsko-Częstochowska", "Kotlina Sandomierska"],
    "Opolskie": ["Nizina Śląska", "Wyżyna Śląska", "Sudety", "Góry Opawskie"],
    "Podkarpackie": ["Karpaty", "Bieszczady", "Beskid Niski", "Kotlina Sandomierska", "Pogórze Karpackie"],
    "Podlaskie": ["Nizina Północnopodlaska", "Pojezierze Litewskie", "Wysoczyzna Białostocka", "Kotlina Biebrzańska"],
    "Pomorskie": ["Pobrzeże Gdańskie", "Pojezierze Pomorskie", "Żuławy Wiślane", "Kaszuby"],
    "Warmińsko-Mazurskie": ["Pojezierze Mazurskie", "Pojezierze Iławskie", "Nizina Staropruska", "Wysoczyzna Elbląska"],
    "Wielkopolskie": ["Pojezierze Wielkopolskie", "Nizina Południowowielkopolska", "Pradolina Toruńsko-Eberswaldzka", "Wysoczyzna Kaliska"],
    "Zachodniopomorskie": ["Pobrzeże Szczecińskie", "Pobrzeże Koszalińskie", "Pojezierze Pomorskie", "Pojezierze Zachodniopomorskie"],
    "Łódzkie": ["Nizina Środkowopolska", "Wzniesienia Łódzkie", "Wysoczyzna Bełchatowska", "Wyżyna Przedborska"],
    "Śląskie": ["Wyżyna Śląska", "Jura Krakowsko-Częstochowska", "Beskid Śląski", "Kotlina Oświęcimska"],
    "Świętokrzyskie": ["Góry Świętokrzyskie", "Wyżyna Kielecka", "Niecka Nidziańska", "Wyżyna Sandomierska"],
}

CITY_COUNT_BY_VOIVODESHIP = {
    "Dolnośląskie": 93,
    "Kujawsko-Pomorskie": 56,
    "Lubelskie": 58,
    "Lubuskie": 44,
    "Mazowieckie": 111,
    "Małopolskie": 64,
    "Opolskie": 38,
    "Podkarpackie": 54,
    "Podlaskie": 40,
    "Pomorskie": 43,
    "Warmińsko-Mazurskie": 50,
    "Wielkopolskie": 116,
    "Zachodniopomorskie": 66,
    "Łódzkie": 60,
    "Śląskie": 75,
    "Świętokrzyskie": 51,
}


@dataclass(frozen=True)
class VoivodeshipRow:
    id: int
    name: str
    md_file: str


def clean_text(value: str) -> str:
    value = value.replace("\\-", "-").replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def parse_float_pl(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"([0-9][0-9\s]*)(?:,([0-9]+))?", value.replace("\xa0", " "))
    if not m:
        return None
    whole = m.group(1).replace(" ", "")
    frac = m.group(2) or ""
    return float(f"{whole}.{frac}" if frac else whole)


def table_value(text: str, label: str) -> str | None:
    pattern = r"\|\s*" + re.escape(label) + r"[^|]*\|([^|]+)\|"
    m = re.search(pattern, text)
    return clean_text(m.group(1)) if m else None


def parse_city_count(text: str) -> int | None:
    patterns = [
        r"w województwie [^\n.]* (?:jest|są|znajdują się)\s+(\d+)\s+miast",
        r"(?:jest|są|znajdują się)\s+(\d+)\s+miast",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return int(m.group(1))
    return None


def parse_powiat_count(text: str) -> int | None:
    m = re.search(r"Liczba powiatów\s*\|\s*(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"składa się z\s+(\d+)\s+powiat", text, re.I)
    return int(m.group(1)) if m else None


def parse_city_count_with_powiat_rights(text: str) -> int | None:
    m = re.search(r"Liczba miast na prawach powiatu\s*\|\s*(\d+)", text)
    return int(m.group(1)) if m else None


def load_rows(csv_path: Path) -> list[VoivodeshipRow]:
    rows: list[VoivodeshipRow] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for idx, row in enumerate(csv.DictReader(f), start=1):
            rows.append(VoivodeshipRow(idx, row["name"], row["md_file"]))
    return rows


def init_db(output_path: Path) -> sqlite3.Connection:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(output_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def insert_many(cur: sqlite3.Cursor, table: str, id_col: str, item_col: str, entity_id: int, values: list[str]) -> None:
    for value in sorted(set(values)):
        cur.execute(
            f"INSERT OR IGNORE INTO {table} ({id_col}, {item_col}) VALUES (?, ?)",
            (entity_id, value),
        )


def build(output_path: Path, csv_path: Path) -> None:
    rows = load_rows(csv_path)
    conn = init_db(output_path)
    cur = conn.cursor()

    for row in rows:
        md_path = ROOT_DIR / row.md_file.replace("\\", "/")
        text = md_path.read_text(encoding="utf-8")
        area = parse_float_pl(table_value(text, "Powierzchnia"))
        population = parse_int(table_value(text, "Populacja"))
        seat = table_value(text, "Siedziba wojewody i sejmiku") or table_value(text, "Siedziba wojewody")
        teryt = table_value(text, "TERYT")
        urbanization = parse_float_pl(table_value(text, "Urbanizacja"))
        powiat_count = parse_powiat_count(text)
        city_count = parse_city_count(text) or CITY_COUNT_BY_VOIVODESHIP[row.name]
        city_count_with_powiat_rights = parse_city_count_with_powiat_rights(text)
        latitude, longitude = CENTROID_BY_VOIVODESHIP[row.name]

        if area is None or population is None or not seat or not teryt:
            raise ValueError(f"Missing required parsed field for {row.name}")

        cur.execute(
            """
            INSERT INTO voivodeships (
                id, name, seat, teryt, macroregion, population, area_km2,
                latitude, longitude, is_coastal, urbanization_percent,
                powiat_count, city_count, city_count_with_powiat_rights, md_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.id,
                row.name,
                seat,
                teryt,
                MACROREGION_BY_VOIVODESHIP[row.name],
                population,
                area,
                latitude,
                longitude,
                1 if row.name in WATER_ACCESS else 0,
                urbanization,
                powiat_count,
                city_count,
                city_count_with_powiat_rights,
                row.md_file,
            ),
        )

        insert_many(cur, "voivodeship_borders_voivodeships", "voivodeship_id", "border_voivodeship_name", row.id, BORDERS_VOIVODESHIPS[row.name])
        insert_many(cur, "voivodeship_borders_countries", "voivodeship_id", "country_name", row.id, BORDERS_COUNTRIES.get(row.name, []))
        insert_many(cur, "voivodeship_water_access", "voivodeship_id", "water_body", row.id, WATER_ACCESS.get(row.name, []))
        insert_many(cur, "voivodeship_major_rivers", "voivodeship_id", "river_name", row.id, MAJOR_RIVERS[row.name])
        insert_many(cur, "voivodeship_mountain_ranges", "voivodeship_id", "range_name", row.id, MOUNTAIN_RANGES.get(row.name, []))
        insert_many(cur, "voivodeship_historical_regions", "voivodeship_id", "region_name", row.id, HISTORICAL_REGIONS[row.name])
        insert_many(cur, "voivodeship_landform_regions", "voivodeship_id", "region_name", row.id, LANDFORM_REGIONS[row.name])
        insert_many(cur, "voivodeship_regional_labels", "voivodeship_id", "label", row.id, REGIONAL_LABELS_BY_VOIVODESHIP[row.name])

    conn.commit()
    conn.close()
    print(f"Created {output_path} with {len(rows)} voivodeships")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build voivodeship facts SQLite database")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv", type=Path, default=DATA_DIR / "wojewodztwa.csv")
    args = parser.parse_args()
    build(args.output, args.csv)


if __name__ == "__main__":
    main()
