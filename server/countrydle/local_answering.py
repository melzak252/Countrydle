"""Local SQLite-based answering for Countrydle questions.

This module is intentionally conservative: it only answers questions that can be
mapped with high confidence to one of the local knowledge-base relations. When a
question is unsupported or ambiguous, callers should fall back to the old
OpenAI + Qdrant pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Iterable


APP_DIR = Path(__file__).resolve().parent
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"


@dataclass(frozen=True)
class LocalAnswer:
    question: str
    answer: bool | None
    explanation: str
    relation: str


POLISH_COUNTRY_ALIASES = {
    "niemcy": "Germany",
    "niemcami": "Germany",
    "niemiec": "Germany",
    "polska": "Poland",
    "polsce": "Poland",
    "polske": "Poland",
    "francja": "France",
    "francji": "France",
    "hiszpania": "Spain",
    "hiszpanii": "Spain",
    "wlochy": "Italy",
    "wlochami": "Italy",
    "czechy": "Czech Republic",
    "czechami": "Czech Republic",
    "slowacja": "Slovakia",
    "slowacja": "Slovakia",
    "ukraina": "Ukraine",
    "ukraina": "Ukraine",
    "rosja": "Russia",
    "rosja": "Russia",
    "usa": "United States",
    "stany zjednoczone": "United States",
    "wielka brytania": "United Kingdom",
    "uk": "United Kingdom",
}


VALUE_ALIASES = {
    "baltyk": "Baltic Sea",
    "morze baltyckie": "Baltic Sea",
    "morza baltyckiego": "Baltic Sea",
    "baltyckiego": "Baltic Sea",
    "srodziemne": "Mediterranean Sea",
    "morze srodziemne": "Mediterranean Sea",
    "czarne": "Black Sea",
    "morze czarne": "Black Sea",
    "czerwone": "Red Sea",
    "morze czerwone": "Red Sea",
    "polnocne": "North Sea",
    "morze polnocne": "North Sea",
    "atlantyk": "Atlantic Ocean",
    "ocean atlantycki": "Atlantic Ocean",
    "pacyfik": "Pacific Ocean",
    "ocean spokojny": "Pacific Ocean",
    "ocean indyjski": "Indian Ocean",
    "wisla": "Vistula",
    "wisle": "Vistula",
    "odra": "Oder",
    "odrze": "Oder",
    "dunaj": "Danube",
    "ren": "Rhine",
    "nil": "Nile",
    "amazonka": "Amazon",
    "euro": "Euro",
    "dolar": "United States dollar",
    "dolar amerykanski": "United States dollar",
    "zloty": "Polish złoty",
    "polski": "Polish",
    "po polsku": "Polish",
    "polsku": "Polish",
    "angielski": "English",
    "niemiecki": "German",
    "francuski": "French",
    "hiszpanski": "Spanish",
    "arabski": "Arabic",
}


ORG_ALIASES = {
    "unia europejska": "EU",
    "ue": "EU",
    "eu": "EU",
    "nato": "NATO",
    "onz": "UN",
    "un": "UN",
    "narody zjednoczone": "UN",
    "g7": "G7",
    "g20": "G20",
    "oecd": "OECD",
    "ocde": "OECD",
    "wto": "WTO",
    "schengen": "Schengen",
    "strefa schengen": "Schengen",
    "commonwealth": "Commonwealth",
    "african union": "AU",
    "unia afrykanska": "AU",
    "asean": "ASEAN",
    "opec": "OPEC",
    "brics": "BRICS",
}


CONTINENT_ALIASES = {
    "europa": "Europe",
    "europie": "Europe",
    "europe": "Europe",
    "azja": "Asia",
    "azji": "Asia",
    "asia": "Asia",
    "afryka": "Africa",
    "afryce": "Africa",
    "africa": "Africa",
    "ameryka polnocna": "North America",
    "ameryce polnocnej": "North America",
    "north america": "North America",
    "ameryka poludniowa": "South America",
    "ameryce poludniowej": "South America",
    "south america": "South America",
    "oceania": "Oceania",
    "oceania": "Oceania",
    "antarktyda": "Antarctica",
    "antarctica": "Antarctica",
}


REGION_ALIASES = {
    "europe": "Europe",
    "asia": "Asia",
    "africa": "Africa",
    "americas": "Americas",
    "north america": "Americas",
    "south america": "Americas",
    "oceania": "Oceania",
}


SUBREGION_ALIASES = {
    "central europe": "Central Europe",
    "eastern europe": "Eastern Europe",
    "western europe": "Western Europe",
    "northern europe": "Northern Europe",
    "southern europe": "Southern Europe",
    "southeast europe": "Southeast Europe",
    "eastern asia": "Eastern Asia",
    "western asia": "Western Asia",
    "southern asia": "Southern Asia",
    "southeast asia": "South-Eastern Asia",
    "south eastern asia": "South-Eastern Asia",
    "south-eastern asia": "South-Eastern Asia",
    "central asia": "Central Asia",
    "caribbean": "Caribbean",
    "central america": "Central America",
    "north america": "North America",
    "south america": "South America",
    "middle east": "Western Asia",
    "scandinavia": "Northern Europe",
    "baltic states": "Baltic states",
    "baltics": "Baltic states",
    "balkans": "Balkans",
    "iberia": "Iberia",
    "iberian peninsula": "Iberian Peninsula",
    "mediterranean": "Mediterranean",
    "eastern africa": "Eastern Africa",
    "middle africa": "Middle Africa",
    "northern africa": "Northern Africa",
    "southern africa": "Southern Africa",
    "western africa": "Western Africa",
    "melanesia": "Melanesia",
    "micronesia": "Micronesia",
    "polynesia": "Polynesia",
    "australia and new zealand": "Australia and New Zealand",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(normalized_question: str, phrase: str) -> bool:
    phrase_norm = normalize(phrase)
    return bool(re.search(rf"(^|\s){re.escape(phrase_norm)}($|\s)", normalized_question))


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def first_mentioned_value(
    normalized_question: str,
    values: Iterable[str],
    aliases: dict[str, str] | None = None,
) -> str | None:
    aliases = aliases or {}
    for alias, canonical in aliases.items():
        if contains_phrase(normalized_question, alias):
            return canonical
    candidates = sorted(set(values), key=len, reverse=True)
    for value in candidates:
        if value and contains_phrase(normalized_question, value):
            return value
    return None


def yes_no_question(normalized_question: str) -> bool:
    return normalized_question.startswith(("czy ", "is ", "are ", "does ", "do ", "has ", "have ", "can ")) or "?" in normalized_question


class LocalCountryFacts:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def try_answer(self, original_question: str, country_name: str) -> LocalAnswer | None:
        if not self.db_path.exists():
            return None

        q = normalize(original_question)
        if not yes_no_question(q):
            return None


        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            country = conn.execute(
                "SELECT * FROM countries WHERE app_country_name = ?", (country_name,)
            ).fetchone()
            if country is None:
                return None

            handlers = (
                self._answer_border,
                self._answer_subregion,
                self._answer_continent,
                self._answer_region,
                self._answer_water_access,
                self._answer_island,
                self._answer_capital,
                self._answer_currency,
                self._answer_language,
                self._answer_membership,
                self._answer_population_or_area,
                self._answer_coordinates,
                self._answer_river,
                self._answer_driving_side,
            )
            for handler in handlers:
                answer = handler(conn, country, original_question, q)
                if answer is not None:
                    return answer
        return None

    def _target_country(self, conn: sqlite3.Connection, q: str) -> str | None:
        names = [r[0] for r in conn.execute("SELECT app_country_name FROM countries")]
        return first_mentioned_value(q, names, POLISH_COUNTRY_ALIASES)

    def _answer_border(self, conn, country, original, q):
        if not any(word in q for word in ("border", "borders", "neighbor", "neighbour", "granic", "sasiad")):
            return None
        target = self._target_country(conn, q)
        if not target:
            return None
        if target == country["app_country_name"]:
            answer = True
        else:
            borders = {r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id=?", (country["id"],))}
            answer = target in borders
        return LocalAnswer(
            question=f"Does the country border {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} {'borders' if answer else 'does not border'} {target}.",
            relation="borders_country",
        )

    def _answer_continent(self, conn, country, original, q):
        if not any(
            word in q
            for word in (
                "continent",
                "kontynent",
                "europ",
                "europe",
                "azj",
                "asia",
                "afryk",
                "africa",
                "america",
                "americ",
                "oceani",
                "oceania",
            )
        ):
            return None
        target = first_mentioned_value(q, CONTINENT_ALIASES.values(), CONTINENT_ALIASES)
        if not target:
            return None
        continents = {r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))}
        answer = target in continents
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} is listed under these continents: {', '.join(sorted(continents))}.",
            relation="continent",
        )

    def _answer_region(self, conn, country, original, q):
        if "subregion" in q:
            return None
        regions = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        target = first_mentioned_value(q, regions, REGION_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        answer = any(normalize(region) == normalize(target) for region in country_regions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Regions for {country['app_country_name']}: {', '.join(sorted(country_regions))}.",
            relation="region",
        )

    def _answer_subregion(self, conn, country, original, q):
        subregions = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, subregions, SUBREGION_ALIASES)
        if not target:
            return None
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        answer = any(normalize(subregion) == normalize(target) for subregion in country_subregions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Subregions for {country['app_country_name']}: {', '.join(sorted(country_subregions))}.",
            relation="subregion",
        )

    def _answer_water_access(self, conn, country, original, q):
        if not any(word in q for word in ("sea", "ocean", "morze", "ocean", "dostep", "coast", "coastline", "wybrzez", "nad ")):
            return None
        waters = {r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))}
        all_waters = [r[0] for r in conn.execute("SELECT DISTINCT water_body FROM country_water_access")]
        target = first_mentioned_value(q, all_waters, VALUE_ALIASES)
        if target:
            answer = target in waters
            explanation = f"{country['app_country_name']} {'has' if answer else 'does not have'} direct access to {target}."
        elif any(word in q for word in ("sea access", "dostep do morza", "dostep do wod", "coast", "coastline", "wybrzez")):
            answer = bool(waters)
            explanation = f"Main water bodies for {country['app_country_name']}: {', '.join(sorted(waters)) if waters else 'none'}."
        else:
            return None
        return LocalAnswer(
            question=f"Does the country have direct access to {target or 'a sea/ocean'}?",
            answer=answer,
            explanation=explanation,
            relation="water_access",
        )

    def _answer_island(self, conn, country, original, q):
        if not any(word in q for word in ("island", "wyspa", "wyspiars")):
            return None
        answer = bool(country["is_island"])
        return LocalAnswer(
            question="Is the country an island country?",
            answer=answer,
            explanation=f"{country['app_country_name']} is {'marked' if answer else 'not marked'} as an island country.",
            relation="is_island",
        )

    def _answer_capital(self, conn, country, original, q):
        if not any(word in q for word in ("capital", "stolic")):
            return None
        capitals = [r[0] for r in conn.execute("SELECT DISTINCT capital FROM countries WHERE capital IS NOT NULL")]
        capital_aliases = {"warszawa": "Warsaw", "praga": "Prague", "wieden": "Vienna", "rzym": "Rome", "londyn": "London", "paryz": "Paris"}
        target = first_mentioned_value(q, capitals, capital_aliases)
        if not target:
            return None
        answer = normalize(country["capital"] or "") == normalize(target)
        return LocalAnswer(
            question=f"Is the capital {target}?",
            answer=answer,
            explanation=f"The capital of {country['app_country_name']} is {country['capital']}.",
            relation="capital",
        )

    def _answer_currency(self, conn, country, original, q):
        if not any(word in q for word in ("currency", "walut", "euro", "dollar", "dolar", "zlot")):
            return None
        currencies = rows(conn, "SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],))
        all_values = [r[0] for r in conn.execute("SELECT DISTINCT currency_name FROM country_currencies")] + [r[0] for r in conn.execute("SELECT DISTINCT currency_code FROM country_currencies WHERE currency_code IS NOT NULL")]
        target = first_mentioned_value(q, all_values, VALUE_ALIASES)
        if not target:
            return None
        target_norm = normalize(target)
        answer = any(normalize(r["currency_name"]) == target_norm or normalize(r["currency_code"] or "") == target_norm for r in currencies)
        names = ", ".join(r["currency_name"] for r in currencies)
        return LocalAnswer(
            question=f"Does the country use {target}?",
            answer=answer,
            explanation=f"The currency for {country['app_country_name']} is: {names}.",
            relation="currency",
        )

    def _answer_language(self, conn, country, original, q):
        if not any(word in q for word in ("language", "jezyk", "speak", "mowi", "official language")):
            return None
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        all_langs = [r[0] for r in conn.execute("SELECT DISTINCT language_name FROM country_languages")]
        target = first_mentioned_value(q, all_langs, VALUE_ALIASES)
        if not target:
            return None
        answer = normalize(target) in {normalize(x) for x in langs}
        return LocalAnswer(
            question=f"Is {target} an official language?",
            answer=answer,
            explanation=f"Official languages for {country['app_country_name']}: {', '.join(langs)}.",
            relation="official_language",
        )

    def _answer_membership(self, conn, country, original, q):
        orgs = [r[0] for r in conn.execute("SELECT DISTINCT organization FROM country_memberships")]
        target = first_mentioned_value(q, orgs, ORG_ALIASES)
        if not target:
            return None
        if not any(word in q for word in ("member", "nalezy", "czlon", "w ", "in ", "belongs", "part of")):
            return None
        memberships = {r[0] for r in conn.execute("SELECT organization FROM country_memberships WHERE country_id=?", (country["id"],))}
        answer = target in memberships
        return LocalAnswer(
            question=f"Is the country a member of {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} {'is' if answer else 'is not'} a member of {target}.",
            relation="membership",
        )

    def _answer_population_or_area(self, conn, country, original, q):
        relation = None
        field = None
        unit = None
        if any(word in q for word in ("population", "ludnosc", "mieszkanc")):
            relation, field, unit = "population", "population", "people"
        elif any(word in q for word in ("area", "powierzch", "larger", "bigger", "wieksz")):
            relation, field, unit = "area", "area_km2", "km²"
        else:
            return None

        comparator = None
        if any(word in q for word in ("more", "greater", "larger", "bigger", "wiecej", "wieksz", "ponad", "above")):
            comparator = "gt"
        elif any(word in q for word in ("less", "smaller", "mniej", "mniejsz", "ponizej", "below")):
            comparator = "lt"
        if not comparator:
            return None

        target_country = self._target_country(conn, q)
        target_value = None
        target_label = None
        if target_country and target_country != country["app_country_name"]:
            row = conn.execute(f"SELECT {field} FROM countries WHERE app_country_name=?", (target_country,)).fetchone()
            if row and row[0] is not None:
                target_value = row[0]
                target_label = target_country
        else:
            number_match = re.search(r"(\d+(?:[\s,.]\d+)*)\s*(million|mln|m|tys|thousand|k)?", q)
            if number_match:
                raw = re.sub(r"[\s,]", "", number_match.group(1))
                target_value = float(raw)
                suffix = number_match.group(2) or ""
                if suffix in {"million", "mln", "m"}:
                    target_value *= 1_000_000
                elif suffix in {"tys", "thousand", "k"}:
                    target_value *= 1_000
                target_label = f"{target_value:g} {unit}"
        if target_value is None:
            return None
        value = country[field]
        answer = value > target_value if comparator == "gt" else value < target_value
        sign = "more than" if comparator == "gt" else "less than"
        return LocalAnswer(
            question=f"Does the country have {sign} {target_label}?",
            answer=answer,
            explanation=f"{country['app_country_name']} has {value:g} {unit}; comparison: {sign} {target_label}.",
            relation=relation,
        )

    def _answer_coordinates(self, conn, country, original, q):
        if not any(word in q for word in ("hemisphere", "polkul", "equator", "rownik", "greenwich", "latitude", "longitude")):
            return None
        lat = country["latitude"]
        lon = country["longitude"]
        if any(word in q for word in ("northern", "polnocn", "north of equator", "na polnoc od rownika")):
            answer = lat > 0
            target = "Northern Hemisphere"
        elif any(word in q for word in ("southern", "poludn", "south of equator", "na poludnie od rownika")):
            answer = lat < 0
            target = "Southern Hemisphere"
        elif any(word in q for word in ("eastern", "wschodn")):
            answer = lon > 0
            target = "Eastern Hemisphere"
        elif any(word in q for word in ("western", "zachodn")):
            answer = lon < 0
            target = "Western Hemisphere"
        else:
            return None
        return LocalAnswer(
            question=f"Is the country in the {target}?",
            answer=answer,
            explanation=f"The coordinates for {country['app_country_name']} are approximately {lat:g}, {lon:g}.",
            relation="coordinates",
        )

    def _answer_river(self, conn, country, original, q):
        if not any(word in q for word in ("river", "rzeka", "rzek")):
            return None
        rivers = {r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))}
        all_rivers = [r[0] for r in conn.execute("SELECT DISTINCT river_name FROM country_major_rivers")]
        target = first_mentioned_value(q, all_rivers, VALUE_ALIASES)
        if not target:
            return None
        answer = target in rivers
        return LocalAnswer(
            question=f"Does the country have the {target} river?",
            answer=answer,
            explanation=f"Major rivers for {country['app_country_name']}: {', '.join(sorted(rivers)) if rivers else 'none in the local database'}.",
            relation="major_rivers",
        )

    def _answer_driving_side(self, conn, country, original, q):
        if not any(word in q for word in ("drive", "driving", "ruch", "lewostron", "prawostron", "left side", "right side")):
            return None
        if any(word in q for word in ("left", "lew")):
            target = "left"
        elif any(word in q for word in ("right", "praw")):
            target = "right"
        else:
            return None
        answer = normalize(country["driving_side"] or "") == target
        return LocalAnswer(
            question=f"Does traffic drive on the {target}?",
            answer=answer,
            explanation=f"Traffic in {country['app_country_name']} drives on the {country['driving_side']}.",
            relation="driving_side",
        )


def try_answer_locally(question: str, country_name: str) -> LocalAnswer | None:
    return LocalCountryFacts().try_answer(question, country_name)


SCALAR_RELATION_FIELDS = {
    "name": "app_country_name",
    "capital": "capital",
    "population": "population",
    "area": "area_km2",
    "area_km2": "area_km2",
    "is_island": "is_island",
    "driving_side": "driving_side",
    "coordinates.latitude": "latitude",
    "coordinates.longitude": "longitude",
    "latitude": "latitude",
    "longitude": "longitude",
}


LIST_RELATION_QUERIES = {
    "continent": "SELECT continent FROM country_continents WHERE country_id=?",
    "region": "SELECT region_name FROM country_regions WHERE country_id=?",
    "subregion": "SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "borders_country": "SELECT border_country_name FROM country_borders WHERE country_id=?",
    "water_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "currency": "SELECT currency_name FROM country_currencies WHERE country_id=? UNION SELECT currency_code FROM country_currencies WHERE country_id=? AND currency_code IS NOT NULL",
    "official_language": "SELECT language_name FROM country_languages WHERE country_id=?",
    "membership": "SELECT organization FROM country_memberships WHERE country_id=?",
    "major_rivers": "SELECT river_name FROM country_major_rivers WHERE country_id=?",
}


def find_country(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    if name == "target_country" or name == "item":
        raise ValueError("Special entities must be resolved by caller")
    direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (name,)).fetchone()
    if direct:
        return direct
    wanted = normalize(name)
    for row in conn.execute("SELECT * FROM countries"):
        if normalize(row["app_country_name"]) == wanted:
            return row
    alias = POLISH_COUNTRY_ALIASES.get(wanted)
    if alias:
        return conn.execute("SELECT * FROM countries WHERE app_country_name=?", (alias,)).fetchone()
    return None


def resolve_entity(
    conn: sqlite3.Connection,
    entity: str,
    target_country: sqlite3.Row,
    item_value: str | None = None,
) -> sqlite3.Row | None:
    if entity == "target_country":
        return target_country
    if entity == "item":
        return find_country(conn, item_value or "")
    return find_country(conn, entity)


def resolve_ref(
    conn: sqlite3.Connection,
    ref: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
):
    if not isinstance(ref, dict):
        return None
    if "value" in ref:
        return ref["value"]
    entity_name = ref.get("entity")
    relation = ref.get("relation")
    if not entity_name or not relation:
        return None
    entity = resolve_entity(conn, entity_name, target_country, item_value)
    if entity is None:
        return None
    if relation in SCALAR_RELATION_FIELDS:
        return entity[SCALAR_RELATION_FIELDS[relation]]
    if relation in LIST_RELATION_QUERIES:
        query = LIST_RELATION_QUERIES[relation]
        params = (entity["id"], entity["id"]) if relation == "currency" else (entity["id"],)
        return [row[0] for row in conn.execute(query, params) if row[0] is not None]
    return None


def normalize_value(value):
    if isinstance(value, str):
        return normalize(value)
    return value


def text_value(value) -> str | None:
    if value is None:
        return None
    return str(value)


def is_self_country_reference(value, target_country: sqlite3.Row) -> bool:
    if value is None:
        return False
    value_norm = normalize(value)
    target_norm = normalize(target_country["app_country_name"])
    return value_norm == target_norm or value_norm in {
        "itself",
        "it self",
        "same country",
        "same entity",
        "self",
        "samym soba",
        "samym sobą",
        "sobą",
        "soba",
    }


def word_count(value: str) -> int:
    return len([part for part in re.split(r"\s+", value.strip()) if part])


def char_count(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def evaluate_plan_node(
    conn: sqlite3.Connection,
    node: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
) -> bool | None:
    if not isinstance(node, dict):
        return None
    operator = node.get("operator")

    if operator == "not":
        result = evaluate_plan_node(conn, node.get("condition"), target_country, item_value)
        return None if result is None else not result

    if operator in {"and", "or"}:
        conditions = node.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            return None
        results = [evaluate_plan_node(conn, condition, target_country, item_value) for condition in conditions]
        if operator == "or":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    if operator == "exists":
        value = resolve_ref(conn, node.get("left", {}), target_country, item_value)
        if value is None:
            return None
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    if operator in {
        "contains",
        "equals",
        "greater_than",
        "less_than",
        "west_of",
        "east_of",
        "north_of",
        "south_of",
        "starts_with",
        "ends_with",
        "contains_text",
        "has_space",
        "word_count_equals",
        "word_count_greater_than",
        "word_count_less_than",
        "char_count_equals",
        "char_count_greater_than",
        "char_count_less_than",
    }:
        left = resolve_ref(conn, node.get("left", {}), target_country, item_value)
        right = resolve_ref(conn, node.get("right", {}), target_country, item_value)
        if left is None or (operator != "has_space" and right is None):
            return None
        left_ref = node.get("left", {})
        if (
            operator in {"contains", "equals"}
            and isinstance(left_ref, dict)
            and str(left_ref.get("relation") or "").startswith("borders_")
            and is_self_country_reference(right, target_country)
        ):
            return True
        if operator == "contains":
            if not isinstance(left, list):
                return None
            right_norm = normalize_value(right)
            return any(normalize_value(value) == right_norm for value in left)
        if operator == "equals":
            return normalize_value(left) == normalize_value(right)
        if operator in {"starts_with", "ends_with", "contains_text", "has_space"}:
            left_text = normalize(text_value(left) or "")
            right_text = normalize(text_value(right) or "")
            if operator == "starts_with":
                return left_text.startswith(right_text)
            if operator == "ends_with":
                return left_text.endswith(right_text)
            if operator == "contains_text":
                return right_text in left_text
            if operator == "has_space":
                return " " in (text_value(left) or "").strip()
        if operator.startswith("word_count_"):
            left_num = word_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "word_count_equals":
                return left_num == right_num
            if operator == "word_count_greater_than":
                return left_num > right_num
            if operator == "word_count_less_than":
                return left_num < right_num
        if operator.startswith("char_count_"):
            left_num = char_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "char_count_equals":
                return left_num == right_num
            if operator == "char_count_greater_than":
                return left_num > right_num
            if operator == "char_count_less_than":
                return left_num < right_num
        try:
            left_num = float(left)
            right_num = float(right)
        except (TypeError, ValueError):
            return None
        if operator in {"greater_than", "east_of", "north_of"}:
            return left_num > right_num
        if operator in {"less_than", "west_of", "south_of"}:
            return left_num < right_num

    if operator in {"any", "all"}:
        items = resolve_ref(conn, node.get("items", {}), target_country, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return None
        results = [evaluate_plan_node(conn, condition, target_country, str(item)) for item in items]
        if operator == "any":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    return None


def plan_relations(node: dict | None) -> set[str]:
    found: set[str] = set()
    if not isinstance(node, dict):
        return found
    for key in ("left", "right", "items"):
        ref = node.get(key)
        if isinstance(ref, dict) and isinstance(ref.get("relation"), str):
            found.add(ref["relation"].split(".")[0])
    found |= plan_relations(node.get("condition"))
    for condition in node.get("conditions", []) if isinstance(node.get("conditions"), list) else []:
        found |= plan_relations(condition)
    return found


def execute_local_plan(
    plan: dict,
    country_name: str,
    improved_question: str,
    planner_explanation: str | None = None,
) -> LocalAnswer | None:
    if not DEFAULT_DB_PATH.exists():
        return None
    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        country = find_country(conn, country_name)
        if country is None:
            return None
        answer = evaluate_plan_node(conn, plan, country)
        if answer is None:
            return None
        relations = sorted(plan_relations(plan)) or ["local_plan"]
        explanation = planner_explanation or "Question answered from the local Countrydle knowledge base."
        explanation = f"{explanation} The result was checked locally in SQLite for {country['app_country_name']}."
        return LocalAnswer(
            question=improved_question,
            answer=answer,
            explanation=explanation,
            relation="+".join(relations),
        )
