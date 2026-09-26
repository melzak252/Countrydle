"""Canonical voivodeship name resolution and inflection mapping."""
from __future__ import annotations

import re
import unicodedata

CANONICAL_VOIVODESHIPS = (
    "Dolnośląskie",
    "Kujawsko-Pomorskie",
    "Lubelskie",
    "Lubuskie",
    "Łódzkie",
    "Małopolskie",
    "Mazowieckie",
    "Opolskie",
    "Podkarpackie",
    "Podlaskie",
    "Pomorskie",
    "Śląskie",
    "Świętokrzyskie",
    "Warmińsko-Mazurskie",
    "Wielkopolskie",
    "Zachodniopomorskie",
)

def _norm(text: str) -> str:
    folded = text.casefold().replace("ł", "l")
    normalized = unicodedata.normalize("NFKD", folded)
    cleaned = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = re.sub(r"^(?:wojewodztwo|wojewodztwem|wojewodztwa|wojewodztwie|woj\.?)\s+", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

# Base alias mapping for all 16 voivodeships (including inflected forms and capitals/seats)
_RAW_ALIASES: dict[str, list[str]] = {
    "Dolnośląskie": [
        "dolnośląskie", "dolnoslaskie", "dolnośląskim", "dolnoslaskim", "dolnośląskiego", "dolnoslaskiego",
        "dolnośląska", "dolnoslaska", "dolnośląską", "dolnoslaska", "wrocław", "wroclaw", "wrocławia", "wrocławiu", "dolny śląsk", "dolny slask",
    ],
    "Kujawsko-Pomorskie": [
        "kujawsko-pomorskie", "kujawsko pomorskie", "kujawsko-pomorskim", "kujawsko pomorskim", "kujawsko-pomorskiego",
        "kujawy", "kujawach", "kujaw", "bydgoszcz", "bydgoszczy", "toruń", "torun", "torunia", "toruniu",
    ],
    "Lubelskie": [
        "lubelskie", "lubelskim", "lubelskiego", "lubelska", "lubelską", "lublin", "lublina", "lublinie",
    ],
    "Lubuskie": [
        "lubuskie", "lubuskim", "lubuskiego", "lubuska", "lubuską", "zielona góra", "zielona gora", "zielonej góry", "zielonej gory",
        "gorzów", "gorzow", "gorzowa", "gorzowie", "gorzów wielkopolski", "gorzow wielkopolski",
    ],
    "Łódzkie": [
        "łódzkie", "lodzkie", "łódzkim", "lodzkim", "łódzkiego", "lodzkiego", "łódzka", "lodzka", "łódzką", "lodzka",
        "łódź", "lodz", "łodzi", "lodzi", "łodzią", "lodzia",
    ],
    "Małopolskie": [
        "małopolskie", "malopolskie", "małopolskim", "malopolskim", "małopolskiego", "malopolskiego",
        "małopolska", "malopolska", "małopolskę", "malopolske", "małopolsce", "kraków", "krakow", "krakowa", "krakowie", "krakowem",
    ],
    "Mazowieckie": [
        "mazowieckie", "mazowieckim", "mazowieckiego", "mazowiecka", "mazowiecką",
        "mazowsze", "mazowszu", "warszawa", "warszawy", "warszawie", "warszawą",
    ],
    "Opolskie": [
        "opolskie", "opolskim", "opolskiego", "opolska", "opolską", "opole", "opola", "opolu", "opolem",
    ],
    "Podkarpackie": [
        "podkarpackie", "podkarpackim", "podkarpackiego", "podkarpacka", "podkarpacką",
        "podkarpacie", "podkarpaciu", "rzeszów", "rzeszow", "rzeszowa", "rzeszowie", "rzeszowem",
    ],
    "Podlaskie": [
        "podlaskie", "podlaskim", "podlaskiego", "podlaska", "podlaską",
        "podlasie", "podlasiu", "białystok", "bialystok", "białegostoku", "bialegostoku", "białymstoku", "bialymstoku",
    ],
    "Pomorskie": [
        "pomorskie", "pomorskim", "pomorskiego", "pomorska", "pomorską",
        "pomorze", "pomorzu", "gdańsk", "gdansk", "gdańska", "gdansku", "gdańskiem", "gdanskiem", "trójmiasto", "trojmiasto",
    ],
    "Śląskie": [
        "śląskie", "slaskie", "śląskim", "slaskim", "śląskiego", "slaskiego", "śląska", "slaska", "śląską", "slaska",
        "śląsk", "slask", "śląsku", "slasku", "katowice", "katowic", "katowicach", "katowicami",
    ],
    "Świętokrzyskie": [
        "świętokrzyskie", "swietokrzyskie", "świętokrzyskim", "swietokrzyskim", "świętokrzyskiego", "swietokrzyskiego",
        "kielce", "kielc", "kielcach", "kielcami",
    ],
    "Warmińsko-Mazurskie": [
        "warmińsko-mazurskie", "warminsko-mazurskie", "warmińsko mazurskie", "warminsko mazurskie",
        "warmińsko-mazurskim", "warminsko-mazurskim", "warmińsko-mazurskiego", "warminsko-mazurskiego",
        "warmia", "warmii", "mazury", "mazurach", "mazur", "olsztyn", "olsztyna", "olsztynie", "olsztynem",
    ],
    "Wielkopolskie": [
        "wielkopolskie", "wielkopolskim", "wielkopolskiego", "wielkopolska", "wielkopolskę", "wielkopolsce",
        "poznań", "poznan", "poznania", "poznaniu", "poznaniem",
    ],
    "Zachodniopomorskie": [
        "zachodniopomorskie", "zachodniopomorskim", "zachodniopomorskiego", "zachodnio-pomorskie", "zachodnio-pomorskim",
        "szczecin", "szczecina", "szczecinie", "szczecinem", "koszalin", "koszalina",
    ],
}

VOIVODESHIP_ALIASES: dict[str, str] = {}
for canonical, aliases in _RAW_ALIASES.items():
    VOIVODESHIP_ALIASES[_norm(canonical)] = canonical
    for alias in aliases:
        VOIVODESHIP_ALIASES[_norm(alias)] = canonical


def resolve_voivodeship_name(value: object) -> str | None:
    """Resolve an inflected name, abbreviation, or capital city to a canonical voivodeship."""
    if not isinstance(value, str):
        return None
    cleaned = _norm(value)
    if not cleaned:
        return None
    return VOIVODESHIP_ALIASES.get(cleaned)
