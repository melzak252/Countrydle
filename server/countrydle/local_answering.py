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

COUNTRY_NAME_SYNONYMS = {
    "drc": "Democratic Republic of the Congo",
    "the drc": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "demokratyczna republika konga": "Democratic Republic of the Congo",
    "drk": "Democratic Republic of the Congo",
    "congo brazzaville": "Republic of the Congo",
    "congo republic": "Republic of the Congo",
    "republic of the congo": "Republic of the Congo",
    "republika konga": "Republic of the Congo",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    "timor-leste": "East Timor",
    "timor leste": "East Timor",
    "east timor": "East Timor",
    "gambia": "Gambia",
    "the gambia": "Gambia",
    "gambia the": "Gambia",
    "usa": "United States",
    "us": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "uae": "United Arab Emirates",
    "car": "Central African Republic",
}


def canonical_country_name(name: Any) -> str:
    clean = normalize(str(name or ""))
    mapped = COUNTRY_NAME_SYNONYMS.get(clean, clean)
    return normalize(mapped)


WATER_BODY_PARENT_MAP: dict[str, set[str]] = {
    "Adriatic Sea": {"Mediterranean Sea"},
    "Aegean Sea": {"Mediterranean Sea"},
    "Ionian Sea": {"Mediterranean Sea"},
    "Ligurian Sea": {"Mediterranean Sea"},
    "Tyrrhenian Sea": {"Mediterranean Sea"},
    "Sea of Crete": {"Mediterranean Sea"},
}

VALUE_ALIASES = {
    "baltyk": "Baltic Sea",
    "morze baltyckie": "Baltic Sea",
    "morza baltyckiego": "Baltic Sea",
    "baltyckiego": "Baltic Sea",
    "baltykiem": "Baltic Sea",
    "baltyku": "Baltic Sea",
    "adriatyk": "Adriatic Sea",
    "adriatyku": "Adriatic Sea",
    "morze adriatyckie": "Adriatic Sea",
    "morza adriatyckiego": "Adriatic Sea",
    "morzem adriatyckim": "Adriatic Sea",
    "morzu adriatyckim": "Adriatic Sea",
    "srodziemne": "Mediterranean Sea",
    "srodziemnego": "Mediterranean Sea",
    "morze srodziemne": "Mediterranean Sea",
    "morza srodziemnego": "Mediterranean Sea",
    "morzem srodziemnym": "Mediterranean Sea",
    "morzu srodziemnym": "Mediterranean Sea",
    "czarne": "Black Sea",
    "czarnego": "Black Sea",
    "morze czarne": "Black Sea",
    "morza czarnego": "Black Sea",
    "morzem czarnym": "Black Sea",
    "morzu czarnym": "Black Sea",
    "czerwone": "Red Sea",
    "czerwonego": "Red Sea",
    "morze czerwone": "Red Sea",
    "morza czerwonego": "Red Sea",
    "morzem czerwonym": "Red Sea",
    "morzu czerwonym": "Red Sea",
    "polnocne": "North Sea",
    "polnocnego": "North Sea",
    "morze polnocne": "North Sea",
    "morza polnocnego": "North Sea",
    "morzem polnocnym": "North Sea",
    "morzu polnocnym": "North Sea",
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
    "czerwony": "red",
    "czerwona": "red",
    "czerwone": "red",
    "czerwonym": "red",
    "bialy": "white",
    "biały": "white",
    "biale": "white",
    "białe": "white",
    "biel": "white",
    "niebieski": "blue",
    "niebieska": "blue",
    "niebieskie": "blue",
    "błękitny": "blue",
    "blekitny": "blue",
    "zielony": "green",
    "zielona": "green",
    "zielone": "green",
    "żółty": "yellow",
    "zolty": "yellow",
    "żółta": "yellow",
    "zolta": "yellow",
    "czarny": "black",
    "czarna": "black",
    "czarne": "black",
    "pomarańczowy": "orange",
    "pomaranczowy": "orange",
    "gwiazda": "star",
    "gwiazdy": "star",
    "gwiazdę": "star",
    "gwiazde": "star",
    "krzyż": "cross",
    "krzyz": "cross",
    "półksiężyc": "crescent",
    "polksiezyc": "crescent",
    "słońce": "sun",
    "slonce": "sun",
    "pasy": "stripes",
    "paski": "stripes",
    "orzeł": "eagle",
    "orzel": "eagle",
    "godło": "coat_of_arms",
    "godlo": "coat_of_arms",
    "koło": "circle",
    "kolo": "circle",
    "zsrr": "USSR",
    "zwiazek radziecki": "USSR",
    "związek radziecki": "USSR",
    "jugoslawia": "Yugoslavia",
    "jugosławia": "Yugoslavia",
    "czechoslowacja": "Czechoslovakia",
    "czechosłowacja": "Czechoslovakia",
    "wielka kolumbia": "Gran Colombia",
    "uklad warszawski": "Warsaw Pact",
    "układ warszawski": "Warsaw Pact",
    "imperium brytyjskie": "British Empire",
    "kolonia brytyjska": "British Empire",
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


RELIGION_ALIASES = {
    "catholic": "Catholic",
    "roman catholic": "Catholic",
    "orthodox": "Orthodox",
    "protestant": "Protestant",
    "christian": "Christianity",
    "christianity": "Christianity",
    "islam": "Islam",
    "muslim": "Islam",
    "judaism": "Judaism",
    "jewish": "Judaism",
    "buddhism": "Buddhism",
    "buddhist": "Buddhism",
    "hinduism": "Hinduism",
    "hindu": "Hinduism",
    "folk religion": "Folk/Traditional religions",
    "traditional religion": "Folk/Traditional religions",
    "no religion": "No religion",
    "atheist": "No religion",
    "atheism": "No religion",
    "mixed": "Mixed",
}


GOVERNMENT_TYPE_ALIASES = {
    "republic": "Republic",
    "parliamentary republic": "Republic",
    "presidential republic": "Republic",
    "federal republic": "Republic",
    "democracy": "Republic",
    "parliamentary democracy": "Republic",
    "federation": "Republic",
    "federal": "Republic",
    "monarchy": "Monarchy",
    "constitutional monarchy": "Monarchy",
    "absolute monarchy": "Monarchy",
    "kingdom": "Monarchy",
    "emirate": "Monarchy",
    "sultanate": "Monarchy",
    "theocracy": "Theocracy",
    "communist": "Communist state",
    "communist state": "Communist state",
    "military junta": "Military junta",
    "junta": "Military junta",
    "transitional": "Transitional government",
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
    "caribean": "Caribbean",
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


GEOGRAPHIC_AREA_ALIASES = {
    **SUBREGION_ALIASES,
    **REGION_ALIASES,
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
    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
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
                self._answer_geographic_area,
                self._answer_subregion,
                self._answer_continent,
                self._answer_region,
                self._answer_water_access,
                self._answer_island,
                self._answer_capital,
                self._answer_currency,
                self._answer_language,
                self._answer_dominant_religion,
                self._answer_government_type,
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
        combined_aliases = {**POLISH_COUNTRY_ALIASES, **COUNTRY_NAME_SYNONYMS}
        return first_mentioned_value(q, names, combined_aliases)
    def _answer_border(self, conn, country, original, q):
        if not any(word in q for word in ("border", "borders", "neighbor", "neighbour", "granic", "sasiad")):
            return None
        target = self._target_country(conn, q)
        if not target:
            return None
        if target == country["app_country_name"] or canonical_country_name(target) == canonical_country_name(country["app_country_name"]):
            answer = True
        else:
            borders = {
                canonical_country_name(r[0])
                for r in conn.execute(
                    """
                    SELECT border_country_name FROM country_borders WHERE country_id=?
                    UNION
                    SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?
                    """,
                    (country["id"], country["id"]),
                )
            }
            answer = canonical_country_name(target) in borders
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

    def _answer_geographic_area(self, conn, country, original, q):
        region_values = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        subregion_values = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, [*region_values, *subregion_values], GEOGRAPHIC_AREA_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        country_areas = country_regions | country_subregions
        answer = any(normalize(area) == normalize(target) for area in country_areas)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Geographic areas for {country['app_country_name']}: {', '.join(sorted(country_areas))}.",
            relation="geographic_area",
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
        for w in list(waters):
            if w in WATER_BODY_PARENT_MAP:
                waters.update(WATER_BODY_PARENT_MAP[w])
        all_waters = [r[0] for r in conn.execute("SELECT DISTINCT water_body FROM country_water_access")]
        for w in list(all_waters):
            if w in WATER_BODY_PARENT_MAP:
                all_waters.extend(WATER_BODY_PARENT_MAP[w])
        all_waters = list(dict.fromkeys(all_waters))
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
        if not any(word in q for word in ("language", "jezyk", "speak", "mowi", "official language", "co-official", "coofficial")):
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

    def _answer_dominant_religion(self, conn, country, original, q):
        if not any(word in q for word in ("religion", "religious", "catholic", "orthodox", "protestant", "christian", "islam", "muslim", "jewish", "judaism", "buddhist", "buddhism", "hindu", "atheist")):
            return None
        target = first_mentioned_value(q, RELIGION_ALIASES.values(), RELIGION_ALIASES)
        if not target:
            return None
        religion = country["dominant_religion"]
        if not religion:
            return None
        answer = normalize(religion) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's dominant religion {target}?",
            answer=answer,
            explanation=f"The dominant religion category for {country['app_country_name']} is {religion}.",
            relation="dominant_religion",
        )

    def _answer_government_type(self, conn, country, original, q):
        if not any(word in q for word in ("government", "republic", "monarchy", "democracy", "federal", "theocracy", "communist", "dictatorship")):
            return None
        government_type = country["government_type"]
        if not government_type:
            return None
        target = first_mentioned_value(q, GOVERNMENT_TYPE_ALIASES.values(), GOVERNMENT_TYPE_ALIASES)
        if not target:
            return None
        answer = normalize(government_type) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's government type {target}?",
            answer=answer,
            explanation=f"The government type for {country['app_country_name']} is {government_type}.",
            relation="government_type",
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
    "government_type": "government_type",
    "dominant_religion": "dominant_religion",
    "coordinates.latitude": "latitude",
    "coordinates.longitude": "longitude",
    "latitude": "latitude",
    "longitude": "longitude",
}


LIST_RELATION_QUERIES = {
    "continent": "SELECT continent FROM country_continents WHERE country_id=?",
    "region": "SELECT region_name FROM country_regions WHERE country_id=?",
    "subregion": "SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "geographic_area": "SELECT region_name FROM country_regions WHERE country_id=? UNION SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "borders_country": "SELECT border_country_name FROM country_borders WHERE country_id=? UNION SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?",
    "water_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "currency": "SELECT currency_name FROM country_currencies WHERE country_id=? UNION SELECT currency_code FROM country_currencies WHERE country_id=? AND currency_code IS NOT NULL",
    "official_language": "SELECT language_name FROM country_languages WHERE country_id=?",
    "membership": "SELECT organization FROM country_memberships WHERE country_id=? UNION SELECT union_name FROM country_historical_unions WHERE country_id=?",
    "major_rivers": "SELECT river_name FROM country_major_rivers WHERE country_id=?",
    "flag_color": "SELECT color FROM country_flag_colors WHERE country_id=?",
    "flag_symbol": "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
    "historical_union": "SELECT union_name FROM country_historical_unions WHERE country_id=?",
}

def find_country(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    if name == "target_country" or name == "item":
        raise ValueError("Special entities must be resolved by caller")
    direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (name,)).fetchone()
    if direct:
        return direct
    wanted = normalize(name)
    alias = COUNTRY_NAME_SYNONYMS.get(wanted) or POLISH_COUNTRY_ALIASES.get(wanted)
    if alias:
        direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (alias,)).fetchone()
        if direct:
            return direct
    official = conn.execute("SELECT * FROM countries WHERE official_name=? COLLATE NOCASE", (name,)).fetchone()
    if official:
        return official
    for row in conn.execute("SELECT * FROM countries"):
        if normalize(row["app_country_name"]) == wanted or normalize(row["official_name"] or "") == wanted:
            return row
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
        params = (entity["id"],) * query.count("?")
        res = [row[0] for row in conn.execute(query, params) if row[0] is not None]
        if relation == "water_access":
            expanded = set(res)
            for w in res:
                if w in WATER_BODY_PARENT_MAP:
                    expanded.update(WATER_BODY_PARENT_MAP[w])
            return list(expanded)
        return res
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
            relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
            if relation == "borders_country":
                r_canon = canonical_country_name(right_norm)
                return any(canonical_country_name(normalize_value(value)) == r_canon for value in left)
            if relation == "geographic_area":
                if right_norm in {"northwestern africa", "northwest africa", "polnocno zachodnia afryka", "polnocno zachodniej afryce"}:
                    nw_areas = {"northern africa", "western africa", "west africa", "maghreb"}
                    return any(normalize_value(val) in nw_areas for val in left)
                if right_norm in {"northeastern africa", "northeast africa", "polnocno wschodnia afryka", "polnocno wschodniej afryce"}:
                    ne_areas = {"northern africa", "eastern africa", "east africa", "horn of africa"}
                    return any(normalize_value(val) in ne_areas for val in left)
                if right_norm in {"southwestern africa", "southwest africa", "poludniowo zachodnia afryka"}:
                    sw_areas = {"southern africa", "western africa", "middle africa"}
                    return any(normalize_value(val) in sw_areas for val in left)
                if right_norm in {"southeastern africa", "southeast africa", "poludniowo wschodnia afryka"}:
                    se_areas = {"southern africa", "eastern africa", "east africa"}
                    return any(normalize_value(val) in se_areas for val in left)
            return any(normalize_value(value) == right_norm for value in left)
        if operator == "equals":
            relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
            if relation in {"name", "borders_country"}:
                return canonical_country_name(left) == canonical_country_name(right)
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


def normalize_geographic_area_plan(conn: sqlite3.Connection, node: dict | None) -> dict | None:
    """Treat region and subregion planner output as one geographic-area layer."""
    if not isinstance(node, dict):
        return node

    normalized = dict(node)

    for key in ("left", "right", "items"):
        ref = normalized.get(key)
        if isinstance(ref, dict):
            normalized[key] = dict(ref)
            if ref.get("relation") in {"region", "subregion"}:
                normalized[key]["relation"] = "geographic_area"

    left = normalized.get("left")
    right = normalized.get("right")
    if (
        isinstance(left, dict)
        and left.get("relation") == "geographic_area"
        and isinstance(right, dict)
        and isinstance(right.get("value"), str)
    ):
        value = right["value"]
        area_values = {
            r[0]
            for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")
        } | {
            r[0]
            for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")
        }
        canonical_area = first_mentioned_value(normalize(value), area_values, GEOGRAPHIC_AREA_ALIASES)
        if canonical_area:
            direction_words = {
                "north", "northern", "northwest", "northwestern", "northeast", "northeastern",
                "south", "southern", "southwest", "southwestern", "southeast", "southeastern",
                "east", "eastern", "west", "western", "central"
            }
            val_words = set(normalize(value).split())
            if canonical_area in {"Africa", "Europe", "Asia", "Americas", "Oceania"} and (val_words & direction_words):
                pass
            else:
                right["value"] = canonical_area
        else:
            # If right["value"] is not a recognized geographic area in the database
            # (e.g. cultural or ethnic family like "Slavic", "Germanic", etc.),
            # this plan cannot be truthfully evaluated against local geographic_area tables.
            return None
    if isinstance(normalized.get("condition"), dict):
        normalized["condition"] = normalize_geographic_area_plan(conn, normalized["condition"])
    if isinstance(normalized.get("conditions"), list):
        normalized["conditions"] = [
            normalize_geographic_area_plan(conn, condition)
            if isinstance(condition, dict)
            else condition
            for condition in normalized["conditions"]
        ]
    return normalized

def generate_factual_explanation(
    conn: sqlite3.Connection,
    country: sqlite3.Row,
    plan: dict,
    answer: bool,
    improved_question: str,
    planner_explanation: str | None = None,
    original_question: str | None = None,
) -> str:
    name = country["app_country_name"]
    node = plan if isinstance(plan, dict) else {}
    op = node.get("operator")
    left = node.get("left")
    right = node.get("right")
    rel = None
    target_val = None
    if isinstance(left, dict) and "relation" in left:
        rel = left["relation"]
    if isinstance(right, dict) and "value" in right:
        target_val = right["value"]
    elif isinstance(right, (str, int, float)):
        target_val = right

    if rel == "borders_country" and target_val:
        borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id=?", (country["id"],))]
        if answer:
            return f"{name} shares a land border with {target_val}."
        else:
            b_str = ", ".join(sorted(set(borders))) if borders else "none (island nation)"
            return f"{name} does not border {target_val}. Its land borders are: {b_str}."

    if rel == "water_access":
        db_waters = sorted(set(r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))))
        all_waters = set(db_waters)
        for w in db_waters:
            if w in WATER_BODY_PARENT_MAP:
                all_waters.update(WATER_BODY_PARENT_MAP[w])
        all_waters_sorted = sorted(all_waters)
        w_str = ", ".join(all_waters_sorted) if all_waters_sorted else ""

        if target_val:
            via_sub = [w for w in db_waters if w in WATER_BODY_PARENT_MAP and target_val in WATER_BODY_PARENT_MAP[w]]
            via_str = f" (via the {', '.join(via_sub)})"
            if answer:
                sub_note = via_str if via_sub and target_val not in db_waters else ""
                return f"{name} has direct coastline access to: {target_val}{sub_note}."
            else:
                if all_waters_sorted:
                    return f"{name} does not have direct coastline access to: {target_val}. Its coastline access: {w_str}."
                else:
                    return f"{name} is completely landlocked with no direct coastline to any sea or ocean (no access to: {target_val})."
        else:
            if answer:
                return f"{name} has direct coastline access to: {w_str}."
            else:
                return f"{name} is completely landlocked with no direct coastline."

    if rel == "is_island":
        if answer:
            return f"{name} is an island nation."
        else:
            borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id=?", (country["id"],))]
            b_str = f" It shares land borders with: {', '.join(sorted(set(borders)))}." if borders else ""
            return f"{name} is a continental country, not an island.{b_str}"

    if rel == "continent":
        conts = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))]
        c_str = ", ".join(conts)
        if answer:
            return f"{name} is located in {c_str}."
        else:
            return f"{name} is not located in {target_val or 'that continent'}; it is in {c_str}."

    if rel in ("geographic_area", "region", "subregion") and target_val:
        subregs = [r[0] for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))]
        regs = [r[0] for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))]
        all_areas = sorted(set(subregs + regs))
        areas_str = ", ".join(all_areas)
        if answer:
            return f"Yes, {name} is located in {target_val}."
        else:
            return f"No, {name} is not located in {target_val}. Its geographic regions are: {areas_str}."

    if rel == "currency":
        curr_rows = conn.execute("SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],)).fetchall()
        currs_str = ", ".join(f"{r[0]} ({r[1]})" if r[1] else r[0] for r in curr_rows) if curr_rows else "no data"
        if answer:
            return f"The official currency of {name} is: {currs_str}."
        else:
            return f"The currency of {name} is not {target_val}. Official currency: {currs_str}."

    if rel == "official_language":
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        langs_str = ", ".join(langs) if langs else "no data"
        if answer:
            return f"An official language of {name} is: {target_val} (official language(s): {langs_str})."
        else:
            return f"{target_val} is not an official language of {name}. Official language(s): {langs_str}."

    if rel == "major_rivers":
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))]
        riv_str = ", ".join(rivers) if rivers else "no major rivers recorded"
        if answer:
            return f"The river {target_val} flows through {name}."
        else:
            return f"The river {target_val} does not flow through {name}. Major rivers include: {riv_str}."

    if rel in ("historical_union", "membership") and target_val:
        if rel == "membership":
            if answer:
                return f"Yes, {name} is or was a member of {target_val}."
            else:
                return f"No, {name} is not a member of {target_val}."
        else:
            if answer:
                return f"Yes, {name} was historically part of {target_val}."
            else:
                return f"No, {name} was not part of {target_val}."

    if rel == "flag_color" and target_val:
        colors = [r[0] for r in conn.execute("SELECT color FROM country_flag_colors WHERE country_id=?", (country["id"],))]
        c_str = ", ".join(colors)
        if answer:
            return f"Yes, the flag of {name} includes the color {target_val}. Flag colors: {c_str}."
        else:
            return f"No, the flag of {name} does not include {target_val}. Flag colors: {c_str}."

    if rel == "flag_symbol" and target_val:
        symbols = [r[0] for r in conn.execute("SELECT symbol FROM country_flag_symbols WHERE country_id=?", (country["id"],))]
        s_str = ", ".join(symbols) if symbols else "none (plain stripes/colors)"
        if answer:
            return f"Yes, the flag of {name} features: {target_val}."
        else:
            return f"No, the flag of {name} does not feature {target_val}. Elements on flag: {s_str}."

    if rel == "driving_side":
        side_en = "left" if country["driving_side"] == "left" else "right"
        return f"Traffic in {name} drives on the {side_en} side."

    if rel == "capital":
        cap = country["capital"]
        if target_val and not answer:
            return f"The capital of {name} is {cap}, not {target_val}."
        return f"The capital of {name} is {cap}."

    if rel == "population":
        pop = country["population"]
        if target_val and op in ("greater_than", "less_than"):
            try:
                val_num = float(target_val)
                comp_en = "more" if pop > val_num else "fewer"
                return f"{name} has a population of approximately {pop:,} ({comp_en} than {int(val_num):,})."
            except (ValueError, TypeError):
                pass
        return f"{name} has a population of approximately {pop:,}."

    if rel in ("area_km2", "area"):
        area = country["area_km2"]
        if target_val and op in ("greater_than", "less_than"):
            try:
                val_num = float(target_val)
                comp_en = "larger" if area > val_num else "smaller"
                return f"The area of {name} is approximately {area:,.0f} km² (it is {comp_en} than {val_num:,.0f} km²)."
            except (ValueError, TypeError):
                pass
        return f"The area of {name} is approximately {area:,.0f} km²."

    if rel == "dominant_religion":
        relig = country["dominant_religion"]
        if target_val and not answer:
            return f"The dominant religion in {name} is {relig}, not {target_val}."
        return f"The dominant religion in {name} is {relig}."

    if rel == "government_type":
        gov = country["government_type"]
        if target_val and not answer:
            return f"The government type of {name} is {gov}, not {target_val}."
        return f"The government type of {name} is {gov}."

    if op in ("north_of", "south_of", "east_of", "west_of"):
        other_entity_name = None
        if isinstance(right, dict):
            other_entity_name = right.get("entity")
        other_country = find_country(conn, other_entity_name) if other_entity_name else None
        c_lat = country["latitude"]
        c_lon = country["longitude"]
        if other_country:
            o_name = other_country["app_country_name"]
            o_lat = other_country["latitude"]
            o_lon = other_country["longitude"]
            if op in ("north_of", "south_of"):
                actual_dir_en = "north" if c_lat > o_lat else "south"
                lat_card = "N" if c_lat >= 0 else "S"
                o_lat_card = "N" if o_lat >= 0 else "S"
                return f"{name} ({abs(c_lat):.1f}°{lat_card}) is located {actual_dir_en} of {o_name} ({abs(o_lat):.1f}°{o_lat_card})."
            if op in ("east_of", "west_of"):
                actual_dir_en = "east" if c_lon > o_lon else "west"
                lon_card = "E" if c_lon >= 0 else "W"
                o_lon_card = "E" if o_lon >= 0 else "W"
                return f"{name} ({abs(c_lon):.1f}°{lon_card}) is located {actual_dir_en} of {o_name} ({abs(o_lon):.1f}°{o_lon_card})."

    left_rel = left.get("relation") if isinstance(left, dict) else rel
    if left_rel == "name":
        if op == "has_space":
            return f"The name {name} {'contains' if answer else 'does not contain'} a space."
        if op and op.startswith("word_count"):
            wc = word_count(name)
            return f"The name {name} consists of {wc} {'words' if wc != 1 else 'word'}."
        if op and op.startswith("char_count"):
            cc = char_count(name)
            return f"The name {name} has {cc} letters."
        if op == "ends_with" and target_val:
            last_let = name[-1].upper()
            val_u = str(target_val).upper()
            if answer:
                return f"The name {name} ends with the letter '{val_u}'."
            else:
                return f"The name {name} ends with the letter '{last_let}', not '{val_u}'."

    # Handle starts_with single letter questions
    if rel == "name" and op == "starts_with" and target_val:
        first_letter = name[0].upper()
        val_u = str(target_val).upper()
        if answer:
            return f"The name {name} starts with the letter '{val_u}'."
        else:
            return f"The name {name} starts with the letter '{first_letter}', not '{val_u}'."

    # Handle OR of starts_with (letter ranges)
    if op == "or":
        conds = plan.get("conditions", [])
        if conds and all(isinstance(c, dict) and c.get("operator") == "starts_with" for c in conds):
            letters = [str(c.get("right", {}).get("value") or "").strip().upper() for c in conds if isinstance(c.get("right"), dict)]
            first_letter = name[0].upper()
            if len(letters) > 1:
                letters_sorted = sorted(set(letters))
                first_let = letters_sorted[0]
                last_let = letters_sorted[-1]
                range_str = f"{first_let}–{last_let}" if len(letters_sorted) > 2 else ", ".join(letters_sorted)
                if answer:
                    return f"The name {name} starts with '{first_letter}' (within the range {range_str})."
                else:
                    return f"The name {name} starts with '{first_letter}' (outside the range {range_str})."

    # Informative fallback
    prefix = "Yes" if answer else "No"
    if planner_explanation:
        return f"{prefix} - {planner_explanation.rstrip('.')} for {name}."

    parts = []
    conts = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))]
    if conts:
        parts.append(f"located in {', '.join(conts)}")
    if country["capital"]:
        parts.append(f"capital: {country['capital']}")
    if country["population"]:
        parts.append(f"population: {country['population']:,}")
    summary = ", ".join(parts)
    if summary:
        return f"{prefix} ({name} is {summary})."
    return f"{prefix} for {name}."

def normalize_letter_range_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        return plan

    op = plan.get("operator")
    conditions = plan.get("conditions")

    if isinstance(conditions, list):
        plan["conditions"] = [normalize_letter_range_plan(c) for c in conditions]

    # Detect impossible AND of starts_with conditions:
    # e.g. AND [ starts_with(A), OR [ starts_with(B)... ] ]
    if op == "and" and isinstance(conditions, list) and len(conditions) == 2:
        c1, c2 = conditions[0], conditions[1]
        sw_node = None
        or_node = None
        if c1.get("operator") == "starts_with" and c2.get("operator") == "or":
            sw_node, or_node = c1, c2
        elif c2.get("operator") == "starts_with" and c1.get("operator") == "or":
            sw_node, or_node = c2, c1

        if sw_node and or_node:
            sub_conds = or_node.get("conditions", [])
            if sub_conds and all(isinstance(sc, dict) and sc.get("operator") == "starts_with" for sc in sub_conds):
                return {
                    "operator": "or",
                    "conditions": [sw_node] + sub_conds,
                }

    return plan

def execute_local_plan(
    plan: dict,
    country_name: str,
    improved_question: str,
    planner_explanation: str | None = None,
    original_question: str | None = None,
) -> LocalAnswer | None:
    if not DEFAULT_DB_PATH.exists():
        return None
    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        country = find_country(conn, country_name)
        if country is None:
            return None
        plan = normalize_geographic_area_plan(conn, plan) or plan
        plan = normalize_letter_range_plan(plan) or plan
        answer = evaluate_plan_node(conn, plan, country)
        if answer is None:
            return None
        relations = sorted(plan_relations(plan)) or ["local_plan"]
        explanation = generate_factual_explanation(
            conn, country, plan, answer, improved_question, planner_explanation, original_question=original_question
        )
        return LocalAnswer(
            question=improved_question,
            answer=answer,
            explanation=explanation,
            relation="+".join(relations),
        )
