"""
Populate flag colors, symbols, and historical unions for all 195 countries in country_facts.sqlite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"

# Canonical color names: red, white, blue, green, yellow, black, orange
# Canonical symbols: star, stars, cross, crescent, sun, stripes, circle, eagle, coat_of_arms

FLAG_DATA = {
    "AFG": (["black", "red", "green", "white"], ["coat_of_arms", "stripes"]),
    "ALB": (["red", "black"], ["eagle"]),
    "DZA": (["green", "white", "red"], ["star", "crescent", "stripes"]),
    "AND": (["blue", "yellow", "red"], ["coat_of_arms", "stripes"]),
    "AGO": (["red", "black", "yellow"], ["star", "stripes"]),
    "ATG": (["red", "black", "blue", "white", "yellow"], ["sun"]),
    "ARG": (["blue", "white", "yellow"], ["sun", "stripes"]),
    "ARM": (["red", "blue", "orange"], ["stripes"]),
    "AUS": (["blue", "white", "red"], ["star", "stars", "cross"]),
    "AUT": (["red", "white"], ["stripes"]),
    "AZE": (["blue", "red", "green", "white"], ["star", "crescent", "stripes"]),
    "BHS": (["blue", "yellow", "black"], ["stripes"]),
    "BHR": (["red", "white"], ["stripes"]),
    "BGD": (["green", "red"], ["circle"]),
    "BRB": (["blue", "yellow", "black"], ["stripes"]),
    "BLR": (["red", "green", "white"], ["stripes"]),
    "BEL": (["black", "yellow", "red"], ["stripes"]),
    "BLZ": (["blue", "red", "white"], ["coat_of_arms", "stripes"]),
    "BEN": (["green", "yellow", "red"], ["stripes"]),
    "BTN": (["yellow", "orange", "white"], []),
    "BOL": (["red", "yellow", "green"], ["coat_of_arms", "stripes"]),
    "BIH": (["blue", "yellow", "white"], ["star", "stars"]),
    "BWA": (["blue", "black", "white"], ["stripes"]),
    "BRA": (["green", "yellow", "blue", "white"], ["star", "stars", "circle"]),
    "BRN": (["yellow", "white", "black", "red"], ["crescent", "coat_of_arms", "stripes"]),
    "BGR": (["white", "green", "red"], ["stripes"]),
    "BFA": (["red", "green", "yellow"], ["star", "stripes"]),
    "BDI": (["white", "red", "green"], ["star", "stars", "cross"]),
    "CPV": (["blue", "white", "red", "yellow"], ["star", "stars", "stripes"]),
    "KHM": (["blue", "red", "white"], ["stripes"]),
    "CMR": (["green", "red", "yellow"], ["star", "stripes"]),
    "CAN": (["red", "white"], ["stripes"]),
    "CAF": (["blue", "white", "green", "yellow", "red"], ["star", "stripes"]),
    "TCD": (["blue", "yellow", "red"], ["stripes"]),
    "CHL": (["blue", "white", "red"], ["star", "stripes"]),
    "CHN": (["red", "yellow"], ["star", "stars"]),
    "COL": (["yellow", "blue", "red"], ["stripes"]),
    "COM": (["yellow", "white", "red", "blue", "green"], ["star", "stars", "crescent", "stripes"]),
    "COG": (["green", "yellow", "red"], ["stripes"]),
    "COD": (["blue", "red", "yellow"], ["star", "stripes"]),
    "CRI": (["blue", "white", "red"], ["stripes"]),
    "CIV": (["orange", "white", "green"], ["stripes"]),
    "HRV": (["red", "white", "blue"], ["coat_of_arms", "stripes"]),
    "CUB": (["blue", "white", "red"], ["star", "stripes"]),
    "CYP": (["white", "orange", "green"], []),
    "CZE": (["white", "red", "blue"], ["stripes"]),
    "DNK": (["red", "white"], ["cross"]),
    "DJI": (["blue", "green", "white", "red"], ["star"]),
    "DMA": (["green", "yellow", "black", "white", "red"], ["star", "stars", "cross"]),
    "DOM": (["blue", "red", "white"], ["cross", "coat_of_arms"]),
    "ECU": (["yellow", "blue", "red"], ["coat_of_arms", "stripes"]),
    "EGY": (["red", "white", "black", "yellow"], ["eagle", "coat_of_arms", "stripes"]),
    "SLV": (["blue", "white"], ["coat_of_arms", "stripes"]),
    "GNQ": (["green", "white", "red", "blue"], ["coat_of_arms", "stripes"]),
    "ERI": (["green", "blue", "red", "yellow"], []),
    "EST": (["blue", "black", "white"], ["stripes"]),
    "SWZ": (["blue", "yellow", "red", "black", "white"], ["stripes"]),
    "ETH": (["green", "yellow", "red", "blue"], ["star", "stripes"]),
    "FJI": (["blue", "red", "white"], ["cross", "coat_of_arms"]),
    "FIN": (["white", "blue"], ["cross"]),
    "FRA": (["blue", "white", "red"], ["stripes"]),
    "GAB": (["green", "yellow", "blue"], ["stripes"]),
    "GMB": (["red", "blue", "green", "white"], ["stripes"]),
    "GEO": (["white", "red"], ["cross"]),
    "DEU": (["black", "red", "yellow"], ["stripes"]),
    "GHA": (["red", "yellow", "green", "black"], ["star", "stripes"]),
    "GRC": (["blue", "white"], ["cross", "stripes"]),
    "GRD": (["red", "yellow", "green"], ["star", "stars"]),
    "GTM": (["blue", "white"], ["coat_of_arms", "stripes"]),
    "GIN": (["red", "yellow", "green"], ["stripes"]),
    "GNB": (["red", "yellow", "green", "black"], ["star", "stripes"]),
    "GUY": (["green", "white", "yellow", "black", "red"], []),
    "HTI": (["blue", "red", "white"], ["coat_of_arms", "stripes"]),
    "HND": (["blue", "white"], ["star", "stars", "stripes"]),
    "HUN": (["red", "white", "green"], ["stripes"]),
    "ISL": (["blue", "white", "red"], ["cross"]),
    "IND": (["orange", "white", "green", "blue"], ["circle", "stripes"]),
    "IDN": (["red", "white"], ["stripes"]),
    "IRN": (["green", "white", "red"], ["crescent", "stripes"]),
    "IRQ": (["red", "white", "black", "green"], ["stripes"]),
    "IRL": (["green", "white", "orange"], ["stripes"]),
    "ISR": (["white", "blue"], ["star", "stripes"]),
    "ITA": (["green", "white", "red"], ["stripes"]),
    "JAM": (["green", "yellow", "black"], ["cross"]),
    "JPN": (["white", "red"], ["circle", "sun"]),
    "JOR": (["black", "white", "green", "red"], ["star", "stripes"]),
    "KAZ": (["blue", "yellow"], ["sun", "eagle"]),
    "KEN": (["black", "red", "green", "white"], ["stripes"]),
    "KIR": (["red", "blue", "white", "yellow"], ["sun", "stripes"]),
    "PRK": (["blue", "red", "white"], ["star", "stripes"]),
    "KOR": (["white", "red", "blue", "black"], ["circle"]),
    "KWT": (["green", "white", "red", "black"], ["stripes"]),
    "KGZ": (["red", "yellow"], ["sun"]),
    "LAO": (["red", "blue", "white"], ["circle", "stripes"]),
    "LVA": (["red", "white"], ["stripes"]),
    "LBN": (["red", "white", "green"], ["stripes"]),
    "LSO": (["blue", "white", "green", "black"], ["stripes"]),
    "LBR": (["red", "white", "blue"], ["star", "stripes"]),
    "LBY": (["red", "black", "green", "white"], ["star", "crescent", "stripes"]),
    "LIE": (["blue", "red", "yellow"], ["coat_of_arms", "stripes"]),
    "LTU": (["yellow", "green", "red"], ["stripes"]),
    "LUX": (["red", "white", "blue"], ["stripes"]),
    "MDG": (["white", "red", "green"], ["stripes"]),
    "MWI": (["black", "red", "green"], ["sun", "stripes"]),
    "MYS": (["red", "white", "blue", "yellow"], ["star", "crescent", "stripes"]),
    "MDV": (["red", "green", "white"], ["crescent"]),
    "MLI": (["green", "yellow", "red"], ["stripes"]),
    "MLT": (["white", "red"], ["cross", "stripes"]),
    "MHL": (["blue", "orange", "white"], ["star", "stripes"]),
    "MRT": (["green", "yellow", "red"], ["star", "crescent", "stripes"]),
    "MUS": (["red", "blue", "yellow", "green"], ["stripes"]),
    "MEX": (["green", "white", "red"], ["eagle", "coat_of_arms", "stripes"]),
    "FSM": (["blue", "white"], ["star", "stars"]),
    "MDA": (["blue", "yellow", "red"], ["eagle", "coat_of_arms", "stripes"]),
    "MCO": (["red", "white"], ["stripes"]),
    "MNG": (["red", "blue", "yellow"], ["sun", "stripes"]),
    "MNE": (["red", "yellow"], ["eagle", "coat_of_arms"]),
    "MAR": (["red", "green"], ["star"]),
    "MOZ": (["green", "black", "yellow", "white", "red"], ["star", "stripes"]),
    "MMR": (["yellow", "green", "red", "white"], ["star", "stripes"]),
    "NAM": (["blue", "red", "green", "white", "yellow"], ["sun", "stripes"]),
    "NRU": (["blue", "yellow", "white"], ["star", "stripes"]),
    "NPL": (["red", "blue", "white"], ["sun", "crescent"]),
    "NLD": (["red", "white", "blue"], ["stripes"]),
    "NZL": (["blue", "red", "white"], ["star", "stars", "cross"]),
    "NIC": (["blue", "white"], ["coat_of_arms", "stripes"]),
    "NER": (["orange", "white", "green"], ["circle", "stripes"]),
    "NGA": (["green", "white"], ["stripes"]),
    "MKD": (["red", "yellow"], ["sun"]),
    "NOR": (["red", "white", "blue"], ["cross"]),
    "OMN": (["white", "red", "green"], ["coat_of_arms", "stripes"]),
    "PAK": (["green", "white"], ["star", "crescent", "stripes"]),
    "PLW": (["blue", "yellow"], ["circle"]),
    "PAN": (["white", "red", "blue"], ["star", "stars"]),
    "PNG": (["black", "red", "yellow", "white"], ["star", "stars"]),
    "PRY": (["red", "white", "blue"], ["star", "coat_of_arms", "stripes"]),
    "PER": (["red", "white"], ["coat_of_arms", "stripes"]),
    "PHL": (["blue", "red", "white", "yellow"], ["star", "stars", "sun", "stripes"]),
    "POL": (["white", "red"], ["stripes"]),
    "PRT": (["green", "red", "yellow", "blue", "white"], ["coat_of_arms", "stripes"]),
    "QAT": (["white", "red"], ["stripes"]),
    "ROU": (["blue", "yellow", "red"], ["stripes"]),
    "RUS": (["white", "blue", "red"], ["stripes"]),
    "RWA": (["blue", "yellow", "green"], ["sun", "stripes"]),
    "KNA": (["green", "red", "black", "yellow", "white"], ["star", "stars", "stripes"]),
    "LCA": (["blue", "yellow", "black", "white"], []),
    "VCT": (["blue", "yellow", "green"], ["stripes"]),
    "WSM": (["red", "blue", "white"], ["star", "stars"]),
    "SMR": (["white", "blue"], ["coat_of_arms", "stripes"]),
    "STP": (["green", "yellow", "red", "black"], ["star", "stars", "stripes"]),
    "SAU": (["green", "white"], []),
    "SEN": (["green", "yellow", "red"], ["star", "stripes"]),
    "SRB": (["red", "blue", "white"], ["eagle", "coat_of_arms", "stripes"]),
    "SYC": (["blue", "yellow", "red", "white", "green"], ["stripes"]),
    "SLE": (["green", "white", "blue"], ["stripes"]),
    "SGP": (["red", "white"], ["star", "stars", "crescent", "stripes"]),
    "SVK": (["white", "blue", "red"], ["cross", "coat_of_arms", "stripes"]),
    "SVN": (["white", "blue", "red"], ["star", "stars", "coat_of_arms", "stripes"]),
    "SLB": (["blue", "green", "yellow", "white"], ["star", "stars", "stripes"]),
    "SOM": (["blue", "white"], ["star"]),
    "ZAF": (["black", "yellow", "green", "white", "red", "blue"], ["stripes"]),
    "SSD": (["black", "red", "green", "blue", "yellow", "white"], ["star", "stripes"]),
    "ESP": (["red", "yellow"], ["coat_of_arms", "stripes"]),
    "LKA": (["yellow", "green", "orange", "red"], ["stripes"]),
    "SDN": (["red", "white", "black", "green"], ["stripes"]),
    "SUR": (["green", "white", "red", "yellow"], ["star", "stripes"]),
    "SWE": (["blue", "yellow"], ["cross"]),
    "CHE": (["red", "white"], ["cross"]),
    "SYR": (["red", "white", "black", "green"], ["star", "stars", "stripes"]),
    "TWN": (["blue", "white", "red"], ["sun"]),
    "TJK": (["red", "white", "green", "yellow"], ["star", "stars", "stripes"]),
    "TZA": (["green", "black", "blue", "yellow"], ["stripes"]),
    "THA": (["red", "white", "blue"], ["stripes"]),
    "TLS": (["red", "yellow", "black", "white"], ["star"]),
    "TGO": (["green", "yellow", "red", "white"], ["star", "stripes"]),
    "TON": (["red", "white"], ["cross"]),
    "TTO": (["red", "black", "white"], ["stripes"]),
    "TUN": (["red", "white"], ["star", "crescent", "circle"]),
    "TUR": (["red", "white"], ["star", "crescent"]),
    "TKM": (["green", "red", "white", "yellow"], ["star", "stars", "crescent", "stripes"]),
    "TUV": (["blue", "red", "white", "yellow"], ["star", "stars", "cross"]),
    "UGA": (["black", "yellow", "red", "white"], ["circle", "stripes"]),
    "UKR": (["blue", "yellow"], ["stripes"]),
    "ARE": (["red", "green", "white", "black"], ["stripes"]),
    "GBR": (["red", "white", "blue"], ["cross"]),
    "USA": (["red", "white", "blue"], ["star", "stars", "stripes"]),
    "URY": (["white", "blue", "yellow"], ["sun", "stripes"]),
    "UZB": (["blue", "white", "green", "red"], ["star", "stars", "crescent", "stripes"]),
    "VUT": (["red", "green", "black", "yellow"], ["stripes"]),
    "VAT": (["yellow", "white"], ["cross", "coat_of_arms", "stripes"]),
    "VEN": (["yellow", "blue", "red", "white"], ["star", "stars", "stripes"]),
    "VNM": (["red", "yellow"], ["star"]),
    "YEM": (["red", "white", "black"], ["stripes"]),
    "ZMB": (["green", "red", "black", "orange"], ["eagle", "stripes"]),
    "ZWE": (["green", "yellow", "red", "black", "white"], ["star", "stripes"]),
}

# Historical blocs / former unions
HISTORICAL_UNIONS = {
    "USSR": [
        "RUS", "UKR", "BLR", "MDA", "GEO", "ARM", "AZE", "KAZ", "UZB", "TKM", "KGZ", "TJK", "EST", "LVA", "LTU"
    ],
    "Yugoslavia": [
        "SRB", "HRV", "BIH", "SVN", "MKD", "MNE"
    ],
    "Czechoslovakia": [
        "CZE", "SVK"
    ],
    "Gran Colombia": [
        "COL", "VEN", "ECU", "PAN"
    ],
    "Austro-Hungarian Empire": [
        "AUT", "HUN", "CZE", "SVK", "SVN", "HRV", "BIH"
    ],
    "Warsaw Pact": [
        "RUS", "UKR", "BLR", "POL", "CZE", "SVK", "HUN", "ROU", "BGR"
    ],
    "British Empire": [
        "GBR", "CAN", "AUS", "NZL", "IND", "PAK", "BGD", "ZAF", "NGA", "EGY", "KEN", "GHA",
        "JAM", "TTO", "GUY", "MYS", "SGP", "MMR", "LKA", "CYP", "MLT", "IRL", "ZMB", "ZWE",
        "UGA", "TZA", "MWI", "BWA", "FJI", "BRB", "BHS", "BLZ", "MDV", "MUS", "SYC", "KNA",
        "LCA", "VCT", "ATG", "DMA", "GRD", "SLB", "VUT", "WSM", "TON", "TUV", "KIR", "NRU", "PNG"
    ],
    "Spanish Empire": [
        "ESP", "MEX", "ARG", "COL", "PER", "CHL", "VEN", "ECU", "GTM", "CUB", "BOL", "DOM",
        "HND", "PRY", "SLV", "NIC", "CRI", "PAN", "URY", "GNQ", "PHL"
    ],
    "French Empire": [
        "FRA", "DZA", "MAR", "TUN", "SEN", "MLI", "GIN", "CIV", "BFA", "NER", "BEN", "TGO",
        "CMR", "TCD", "CAF", "COG", "GAB", "MDG", "DJI", "COM", "VNM", "LAO", "KHM", "HTI", "VUT"
    ],
    "Portuguese Empire": [
        "PRT", "BRA", "AGO", "MOZ", "GNB", "CPV", "STP", "TLS"
    ],
    "Ottoman Empire": [
        "TUR", "GRC", "BGR", "SRB", "BIH", "ALB", "MKD", "MNE", "EGY", "IRQ", "SYR", "LBN",
        "JOR", "ISR", "SAU", "YEM", "KWT", "LBY", "TUN", "DZA"
    ],
}


def main():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS country_flag_colors (
        country_id INTEGER NOT NULL,
        color TEXT NOT NULL,
        PRIMARY KEY (country_id, color),
        FOREIGN KEY (country_id) REFERENCES countries(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS country_flag_symbols (
        country_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        PRIMARY KEY (country_id, symbol),
        FOREIGN KEY (country_id) REFERENCES countries(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS country_historical_unions (
        country_id INTEGER NOT NULL,
        union_name TEXT NOT NULL,
        PRIMARY KEY (country_id, union_name),
        FOREIGN KEY (country_id) REFERENCES countries(id)
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_flag_colors ON country_flag_colors(color);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_flag_symbols ON country_flag_symbols(symbol);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historical_unions ON country_historical_unions(union_name);")

    # Clear previous entries to allow idempotent re-runs
    cursor.execute("DELETE FROM country_flag_colors;")
    cursor.execute("DELETE FROM country_flag_symbols;")
    cursor.execute("DELETE FROM country_historical_unions;")

    # 2. Map cca3 to country_id
    cca3_map = {}
    for cid, cca3, name in cursor.execute("SELECT id, cca3, app_country_name FROM countries"):
        cca3_map[cca3] = (cid, name)

    # 3. Populate Flag Data
    colors_count = 0
    symbols_count = 0
    for cca3, (colors, symbols) in FLAG_DATA.items():
        if cca3 not in cca3_map:
            continue
        cid, _ = cca3_map[cca3]
        for c in colors:
            cursor.execute("INSERT OR IGNORE INTO country_flag_colors(country_id, color) VALUES (?, ?)", (cid, c.lower()))
            colors_count += 1
        for s in symbols:
            cursor.execute("INSERT OR IGNORE INTO country_flag_symbols(country_id, symbol) VALUES (?, ?)", (cid, s.lower()))
            symbols_count += 1

    # 4. Populate Historical Unions
    unions_count = 0
    for union_name, cca3_list in HISTORICAL_UNIONS.items():
        for cca3 in cca3_list:
            if cca3 not in cca3_map:
                continue
            cid, _ = cca3_map[cca3]
            cursor.execute("INSERT OR IGNORE INTO country_historical_unions(country_id, union_name) VALUES (?, ?)", (cid, union_name))
            # Also insert into country_memberships so membership queries naturally find them
            cursor.execute("INSERT OR IGNORE INTO country_memberships(country_id, organization) VALUES (?, ?)", (cid, union_name))
            unions_count += 1

    conn.commit()
    print(f"Populated {colors_count} flag color rows across {len(FLAG_DATA)} countries.")
    print(f"Populated {symbols_count} flag symbol rows across {len(FLAG_DATA)} countries.")
    print(f"Populated {unions_count} historical union associations across {len(HISTORICAL_UNIONS)} unions.")
    conn.close()


if __name__ == "__main__":
    main()
