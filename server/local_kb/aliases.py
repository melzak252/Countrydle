"""Entity, region, water, and partition normalization and alias lookup helpers."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Any

from .models import LocalModeConfig


_REGIONAL_DISPLAY = {
    "centrum": "central", "południe": "south", "północ": "north",
    "wschód": "east", "zachód": "west",
    "południowe centrum": "south central", "północne centrum": "north central",
    "zachodnie centrum": "west central", "południowy wschód": "southeast",
    "południowy zachód": "southwest", "północny wschód": "northeast",
    "północny zachód": "northwest",
    "polska centralna": "central Poland", "centralna polska": "central Poland",
    "polska wschodnia": "eastern Poland", "wschodnia polska": "eastern Poland",
    "polska zachodnia": "western Poland", "zachodnia polska": "western Poland",
    "południowa polska": "southern Poland", "północna polska": "northern Poland",
    "południowo-centralna polska": "south-central Poland",
    "południowo-wschodnia polska": "southeastern Poland",
    "południowo-zachodnia polska": "southwestern Poland",
    "północno-centralna polska": "north-central Poland",
    "północno-wschodnia polska": "northeastern Poland",
    "północno-zachodnia polska": "northwestern Poland",
    "zachodnio-centralna polska": "west-central Poland",
    "nadmorska polska": "coastal Poland", "wybrzeże bałtyku": "Baltic coast",
    "zabór austriacki": "Austrian partition", "zabór pruski": "Prussian partition",
    "zabór rosyjski": "Russian partition", "ziemie odzyskane": "Recovered Territories",
    "morze bałtyckie": "Baltic Sea",
}

POLISH_CITY_ALIASES = {
    "warsaw": "Warszawa",
    "cracow": "Kraków",
    "krakow": "Kraków",
    "lodz": "Łódź",
    "wroclaw": "Wrocław",
    "poznan": "Poznań",
    "gdansk": "Gdańsk",
    "szczecin": "Szczecin",
    "bialystok": "Białystok",
    "rzeszow": "Rzeszów",
    "torun": "Toruń",
    "zielona gora": "Zielona Góra",
    "gorzow wielkopolski": "Gorzów Wielkopolski",
}

POLISH_REGION_ALIASES = {
    "lesser poland": "Małopolska",
    "greater poland": "Wielkopolska",
    "silesia": "Śląsk",
    "lower silesia": "Dolny Śląsk",
    "upper silesia": "Górny Śląsk",
    "masovia": "Mazowsze",
    "mazovia": "Mazowsze",
    "pomerania": "Pomorze",
    "western pomerania": "Pomorze Zachodnie",
    "west pomerania": "Pomorze Zachodnie",
    "gdansk pomerania": "Pomorze Gdańskie",
    "masuria": "Mazury",
    "warmia": "Warmia",
    "podlachia": "Podlasie",
    "podlasie": "Podlasie",
    "kuyavia": "Kujawy",
    "galicia": "Galicja",
    "carpathians": "Karpaty",
    "carpathian mountains": "Karpaty",
    "sudetes": "Sudety",
    "sudeten": "Sudety",
    "beskids": "Beskidy",
    "bieszczady mountains": "Bieszczady",
    "tatras": "Tatry",
    "tatra mountains": "Tatry",
    "kashubia": "Kaszuby",
    "holy cross mountains": "Góry Świętokrzyskie",
}

POLISH_HISTORICAL_PARTITION_ALIASES = {
    "congress poland": "Zabór rosyjski",
    "kongresowka": "Zabór rosyjski",
    "krolestwo polskie": "Zabór rosyjski",
    "kingdom of poland": "Zabór rosyjski",
    "krolestwo kongresowe": "Zabór rosyjski",
    "russian partition": "Zabór rosyjski",
    "prussian partition": "Zabór pruski",
    "austrian partition": "Zabór austriacki",
    "recovered territories": "Ziemie Odzyskane",
}

POLISH_NEIGHBORING_COUNTRIES_ALIASES: dict[str, str] = {
    "slovakia": "Słowacja",
    "slowacja": "Słowacja",
    "słowacja": "Słowacja",
    "czech republic": "Czechy",
    "czechia": "Czechy",
    "czechy": "Czechy",
    "germany": "Niemcy",
    "niemcy": "Niemcy",
    "ukraine": "Ukraina",
    "ukraina": "Ukraina",
    "belarus": "Białoruś",
    "bialorus": "Białoruś",
    "białoruś": "Białoruś",
    "lithuania": "Litwa",
    "litwa": "Litwa",
    "russia": "Rosja",
    "rosja": "Rosja",
}

POLISH_RIVER_ALIASES: dict[str, str] = {
    "vistula": "Wisła",
    "vistula river": "Wisła",
    "river vistula": "Wisła",
    "wisla": "Wisła",
    "wisly": "Wisła",
    "wisle": "Wisła",
    "wisłę": "Wisła",
    "wisły": "Wisła",
    "wiśle": "Wisła",
    "wisłą": "Wisła",
    "oder": "Odra",
    "oder river": "Odra",
    "river oder": "Odra",
    "odra": "Odra",
    "odry": "Odra",
    "odrze": "Odra",
    "odrę": "Odra",
    "odrą": "Odra",
}

ENGLISH_COUNTY_ALIASES: dict[str, str] = {
    "county durham": "Durham",
    "east riding": "East Riding of Yorkshire",
    "yorkshire east riding": "East Riding of Yorkshire",
    "london city": "City of London",
    "county of herefordshire": "Herefordshire",
    "tyne & wear": "Tyne and Wear",
    "londyn": "Greater London",
    "kornwalia": "Cornwall",
}

UK_NEIGHBORING_COUNTRIES_ALIASES: dict[str, str] = {
    "scotland": "Scotland",
    "szkocja": "Scotland",
    "wales": "Wales",
    "walia": "Wales",
}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def fold_polish(value: Any) -> str:
    text = norm(value).replace("ł", "l")
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def text_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _resolve_english_county_alias(value: Any) -> Any:
    if isinstance(value, str):
        return ENGLISH_COUNTY_ALIASES.get(norm(value), value)
    return value


def _canonical_us_region(value: Any) -> Any:
    """Canonicalize a spelling alias, not a different regional category."""
    if isinstance(value, str) and re.fullmatch(r"north[\s\-\u2010-\u2015]*east", value.strip(), re.I):
        return "Northeast"
    return value


def is_self_reference(value: Any, row: sqlite3.Row, config: LocalModeConfig) -> bool:
    if value is None:
        return False
    value_norm = norm(value)
    target_norm = norm(row[config.name_column])
    return value_norm == target_norm or value_norm in {
        "itself",
        "it self",
        "same state",
        "same entity",
        "self",
        "samym soba",
        "samym sobą",
        "sobą",
        "soba",
    }
