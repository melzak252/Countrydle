"""Domain alias tables and text/value normalization helpers for Countrydle."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from utils.water_hierarchy import (
    INLAND_WATER_BODIES,
    WATER_BODY_PARENT_MAP,
    expand_water_bodies,
    get_distinct_oceans,
    get_water_body_parents,
    is_marine_water_body,
    is_multi_ocean_question,
)
from countrydle.answering.country_aliases import (
    COUNTRY_NAME_SYNONYMS,
    POLISH_COUNTRY_ALIASES,
    _hyphenated_country_alias,
)
from countrydle.answering.geo_aliases import (
    CONTINENT_ALIASES,
    GEOGRAPHIC_AREA_ALIASES,
    GEOGRAPHIC_SUBREGION_PARENT_MAP,
    REGION_ALIASES,
    SUBREGION_ALIASES,
    expand_geographic_areas,
)

CURRENCY_ALIASES = {
    "us dollar": "united states dollar",
    "us dollars": "united states dollar",
    "usd": "united states dollar",
    "dollar": "united states dollar",
    "dolar": "united states dollar",
    "dolar amerykanski": "united states dollar",
    "dolarze": "united states dollar",
    "dolarach": "united states dollar",
    "euro": "euro",
    "eur": "euro",
    "polish zloty": "polish zloty",
    "zloty": "polish zloty",
    "pln": "polish zloty",
    "zlote": "polish zloty",
    "zlotych": "polish zloty",
    "pound": "british pound",
    "british pound": "british pound",
    "gbp": "british pound",
    "funt": "british pound",
}

HEMISPHERE_ALIASES = {
    "northern": "northern",
    "north": "northern",
    "polnocna": "northern",
    "polnocnej": "northern",
    "southern": "southern",
    "south": "southern",
    "poludniowa": "southern",
    "poludniowej": "southern",
    "eastern": "eastern",
    "east": "eastern",
    "wschodnia": "eastern",
    "wschodniej": "eastern",
    "western": "western",
    "west": "western",
    "zachodnia": "western",
    "zachodniej": "western",
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
    "sea of marmara": "Sea of Marmara",
    "marmara sea": "Sea of Marmara",
    "marmara": "Sea of Marmara",
    "morze marmara": "Sea of Marmara",
    "morza marmara": "Sea of Marmara",
    "morzem marmara": "Sea of Marmara",
    "morzu marmara": "Sea of Marmara",
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
    "us dollar": "United States dollar",
    "us dollars": "United States dollar",
    "usd": "United States dollar",
    "dollar": "United States dollar",
    "dollars": "United States dollar",
    "the dollar": "United States dollar",
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
    "rosyjski": "Russian",
    "po rosyjsku": "Russian",
    "ukrainski": "Ukrainian",
    "po ukrainsku": "Ukrainian",
    "katalonski": "Catalan",
    "po katalonsku": "Catalan",
    "baskijski": "Basque",
    "po baskijsku": "Basque",
    "galicyjski": "Galician",
    "irlandzki": "Irish",
    "szwedzki": "Swedish",
    "wloski": "Italian",
    "portugalski": "Portuguese",
    "chinski": "Chinese",
    "mandarynski": "Mandarin",
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
    "european union": "EU",
    "the european union": "EU",
    "unia europejska": "EU",
    "ue": "EU",
    "eu": "EU",
    "nato": "NATO",
    "onz": "UN",
    "un": "UN",
    "united nations": "UN",
    "the united nations": "UN",
    "narody zjednoczone": "UN",
    "g7": "G7",
    "the g7": "G7",
    "group of seven": "G7",
    "g20": "G20",
    "the g20": "G20",
    "group of twenty": "G20",
    "oecd": "OECD",
    "the oecd": "OECD",
    "ocde": "OECD",
    "wto": "WTO",
    "the wto": "WTO",
    "schengen": "Schengen",
    "schengen area": "Schengen",
    "schengen zone": "Schengen",
    "strefa schengen": "Schengen",
    "commonwealth": "Commonwealth",
    "commonwealth of nations": "Commonwealth",
    "african union": "AU",
    "the african union": "AU",
    "unia afrykanska": "AU",
    "asean": "ASEAN",
    "opec": "OPEC",
    "brics": "BRICS",
}

RELIGION_ALIASES = {
    "catholicism": "Catholic",
    "katolicyzm": "Catholic",
    "katolicka": "Catholic",
    "katolicki": "Catholic",
    "orthodoxy": "Orthodox",
    "prawoslawie": "Orthodox",
    "protestantism": "Protestant",
    "protestantyzm": "Protestant",
    "chrzescijanstwo": "Christianity",
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


def normalize(text: str, *, preserve_separators: bool = False) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    if preserve_separators:
        return text
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_value(value):
    if isinstance(value, str):
        return normalize(value)
    return value


def text_value(value) -> str | None:
    if value is None:
        return None
    return str(value)


def normalize_hemisphere(val: Any) -> str:
    cleaned = re.sub(r"\b(hemisphere|polkula|polkuli|polkule)\b", "", normalize_value(val)).strip()
    return HEMISPHERE_ALIASES.get(cleaned, cleaned)


def canonical_country_name(name: Any) -> str:
    clean = normalize(str(name or ""))
    mapped = COUNTRY_NAME_SYNONYMS.get(clean, clean)
    return normalize(mapped)


def contains_phrase(normalized_question: str, phrase: str) -> bool:
    phrase_norm = normalize(phrase)
    return bool(re.search(rf"(^|\s){re.escape(phrase_norm)}($|\s)", normalized_question))


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
    return (
        normalized_question.startswith(("czy ", "is ", "are ", "does ", "do ", "has ", "have ", "can ", "below ", "above ", "over ", "under "))
        or "?" in normalized_question
    )


def word_count(value: str) -> int:
    return len([part for part in re.split(r"\s+", value.strip()) if part])


def char_count(value: str) -> int:
    return len(re.sub(r"[\s\-\u2010\u2011]+", "", value))


__all__ = [
    "POLISH_COUNTRY_ALIASES",
    "COUNTRY_NAME_SYNONYMS",
    "_hyphenated_country_alias",
    "CONTINENT_ALIASES",
    "REGION_ALIASES",
    "SUBREGION_ALIASES",
    "GEOGRAPHIC_SUBREGION_PARENT_MAP",
    "GEOGRAPHIC_AREA_ALIASES",
    "expand_geographic_areas",
    "CURRENCY_ALIASES",
    "HEMISPHERE_ALIASES",
    "VALUE_ALIASES",
    "ORG_ALIASES",
    "RELIGION_ALIASES",
    "GOVERNMENT_TYPE_ALIASES",
    "WATER_BODY_PARENT_MAP",
    "INLAND_WATER_BODIES",
    "is_marine_water_body",
    "get_water_body_parents",
    "expand_water_bodies",
    "is_multi_ocean_question",
    "get_distinct_oceans",
    "normalize",
    "normalize_value",
    "text_value",
    "normalize_hemisphere",
    "canonical_country_name",
    "contains_phrase",
    "first_mentioned_value",
    "yes_no_question",
    "word_count",
    "char_count",
]
