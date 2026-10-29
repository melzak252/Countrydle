"""Slot-masking and skeleton-hashing deterministic template engine.

Instead of running long chains of fragile sequential regular expressions, this engine:
1. Normalizes input and extracts recognized entity slots ([COUNTRY], [STATE], [WATER_BODY], [NUMBER], [COMP_OP], etc.).
2. Replaces slots to produce a normalized sentence skeleton (e.g. "does it border [NUMBER] countries").
3. Performs an O(1) hash map lookup against pre-compiled AST templates.
4. Injects extracted slot values into the AST parameters.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from countrydle.local_answering import (
    COUNTRY_NAME_SYNONYMS,
    POLISH_COUNTRY_ALIASES,
)
from polish_morphology import (
    expand_polish_phrase_forms,
    expand_polish_word_forms,
)


def norm_text(text: str) -> str:
    """Case-folded, diacritic-free, alphanumeric text with single spaces."""
    folded = text.casefold().replace("ł", "l")
    normalized = unicodedata.normalize("NFKD", folded)
    clean = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    clean = re.sub(r"[^\w\s]", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


# ==============================================================================
# 1. SLOT DICTIONARIES
# ==============================================================================

# 1.1 Comparison Operators
COMP_OPS_MAP: dict[str, str] = {
    "more than": "greater_than",
    "fewer than": "less_than",
    "less than": "less_than",
    "at least": "greater_than_or_equal",
    "at most": "less_than_or_equal",
    "wiecej niz": "greater_than",
    "mniej niz": "less_than",
    "co najmniej": "greater_than_or_equal",
    "przynajmniej": "greater_than_or_equal",
    "nie wiecej niz": "less_than_or_equal",
    "co najwyzej": "less_than_or_equal",
    "ponad": "greater_than",
    "over": "greater_than",
}
_SORTED_COMP_OPS = sorted(COMP_OPS_MAP.keys(), key=len, reverse=True)
_COMP_OP_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in _SORTED_COMP_OPS) + r")\b")

# 1.2 Countries (196 canonical + English synonyms + Polish aliases)
_BASE_COUNTRY_NAMES = (
    "Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|Argentina|Armenia|Australia|Austria|"
    "Azerbaijan|Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|Bhutan|Bolivia|"
    "Bosnia and Herzegovina|Botswana|Brazil|Brunei|Bulgaria|Burkina Faso|Burundi|Cambodia|Cameroon|"
    "Canada|Cape Verde|Central African Republic|Chad|Chile|China|Colombia|Comoros|Costa Rica|Croatia|"
    "Cuba|Cyprus|Czech Republic|Democratic Republic of the Congo|Denmark|Djibouti|Dominica|"
    "Dominican Republic|East Timor|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|Eswatini|"
    "Ethiopia|Federated States of Micronesia|Fiji|Finland|France|Gabon|Gambia|Georgia|Germany|Ghana|"
    "Greece|Grenada|Guatemala|Guinea|Guinea-Bissau|Guyana|Haiti|Honduras|Hungary|Iceland|India|"
    "Indonesia|Iran|Iraq|Ireland|Israel|Italy|Ivory Coast|Jamaica|Japan|Jordan|Kazakhstan|Kenya|"
    "Kiribati|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|"
    "Lithuania|Luxembourg|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall Islands|Mauritania|"
    "Mauritius|Mexico|Moldova|Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|Namibia|Nauru|"
    "Nepal|Netherlands|New Zealand|Nicaragua|Niger|Nigeria|North Korea|North Macedonia|Norway|Oman|"
    "Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|Philippines|Poland|Portugal|Qatar|"
    "Republic of the Congo|Romania|Russia|Rwanda|Saint Kitts and Nevis|Saint Lucia|"
    "Saint Vincent and the Grenadines|Samoa|San Marino|Saudi Arabia|Senegal|Serbia|Seychelles|"
    "Sierra Leone|Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|South Korea|"
    "South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|Syria|São Tomé and Príncipe|"
    "Tajikistan|Tanzania|Thailand|Togo|Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|"
    "Uganda|Ukraine|United Arab Emirates|United Kingdom|United States|Uruguay|Uzbekistan|Vanuatu|"
    "Vatican City|Venezuela|Vietnam|Yemen|Zambia|Zimbabwe"
).split("|")

COUNTRIES_MAP: dict[str, str] = {}
for name in _BASE_COUNTRY_NAMES:
    COUNTRIES_MAP[norm_text(name)] = name
for k, v in COUNTRY_NAME_SYNONYMS.items():
    COUNTRIES_MAP[norm_text(k)] = v
for k, v in POLISH_COUNTRY_ALIASES.items():
    COUNTRIES_MAP[norm_text(k)] = v
    for form in expand_polish_phrase_forms(k, reversible=False):
        if form not in {"ameryka", "ameryce", "ameryki", "kongo", "konga", "nigerie", "nigeriem"}:
            COUNTRIES_MAP[norm_text(form)] = v
_SORTED_COUNTRIES = sorted(COUNTRIES_MAP.keys(), key=len, reverse=True)
_COUNTRY_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in _SORTED_COUNTRIES) + r")\b")

# 1.3 US States
_US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
]
US_STATES_MAP: dict[str, str] = {}
for s in _US_STATES:
    US_STATES_MAP[norm_text(s)] = s
    for form in expand_polish_phrase_forms(s, reversible=True):
        US_STATES_MAP[norm_text(form)] = s

_BASE_POLISH_US_STATES = {
    "Kalifornia": "California",
    "Teksas": "Texas",
    "Floryda": "Florida",
    "Alaska": "Alaska",
    "Hawaje": "Hawaii",
    "Nowy Jork": "New York",
    "Nowy Meksyk": "New Mexico",
    "Karolina Północna": "North Carolina",
    "Karolina Południowa": "South Carolina",
    "Dakota Północna": "North Dakota",
    "Dakota Południowa": "South Dakota",
    "Wirginia": "Virginia",
    "Wirginia Zachodnia": "West Virginia",
    "Pensylwania": "Pennsylvania",
    "Kolorado": "Colorado",
    "Luizjana": "Louisiana",
    "Waszyngton": "Washington",
}
for pl_name, canonical in _BASE_POLISH_US_STATES.items():
    US_STATES_MAP[norm_text(pl_name)] = canonical
    for form in expand_polish_phrase_forms(pl_name, reversible=True):
        US_STATES_MAP[norm_text(form)] = canonical
_SORTED_US_STATES = sorted(US_STATES_MAP.keys(), key=len, reverse=True)
_US_STATE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in _SORTED_US_STATES) + r")\b")

# 1.4 Polish Voivodeships
_VOIVODESHIPS = [
    "Dolnośląskie", "Kujawsko-Pomorskie", "Lubelskie", "Lubuskie", "Łódzkie", "Małopolskie",
    "Mazowieckie", "Opolskie", "Podkarpackie", "Podlaskie", "Pomorskie", "Śląskie",
    "Świętokrzyskie", "Warmińsko-Mazurskie", "Wielkopolskie", "Zachodniopomorskie"
]
VOIVODESHIPS_MAP: dict[str, str] = {}
for v in _VOIVODESHIPS:
    VOIVODESHIPS_MAP[norm_text(v)] = v
    for form in expand_polish_word_forms(v):
        VOIVODESHIPS_MAP[norm_text(form)] = v
    # Adjective/inflections
    stem = norm_text(v)
    if stem.endswith("ie"):
        base = stem[:-2]
        for suffix in ("im", "iego", "iem", "a"):
            VOIVODESHIPS_MAP[base + suffix] = v

_SORTED_VOIVODESHIPS = sorted(VOIVODESHIPS_MAP.keys(), key=len, reverse=True)
_VOIVODESHIP_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in _SORTED_VOIVODESHIPS) + r")\b")

# 1.5 Water Bodies
WATER_BODIES_MAP: dict[str, str] = {
    # Atlantic Ocean & typos
    "atlantic ocean": "Atlantic Ocean", "atlantic": "Atlantic Ocean",
    "antlantic ocean": "Atlantic Ocean", "antlantic": "Atlantic Ocean",
    "atlantik": "Atlantic Ocean", "atlantycki": "Atlantic Ocean", "atlantyckiego": "Atlantic Ocean",
    "atlantyckim": "Atlantic Ocean", "atlantyk": "Atlantic Ocean", "atlantykiem": "Atlantic Ocean",
    "antlantyk": "Atlantic Ocean", "antlantykiem": "Atlantic Ocean", "antlantyckiego": "Atlantic Ocean",
    # Pacific Ocean
    "pacific ocean": "Pacific Ocean", "pacific": "Pacific Ocean",
    "pacyfik": "Pacific Ocean", "pacyfikiem": "Pacific Ocean", "pacyfiku": "Pacific Ocean",
    "spokojny": "Pacific Ocean", "ocean spokojny": "Pacific Ocean",
    # Arctic Ocean
    "arctic ocean": "Arctic Ocean", "arctic": "Arctic Ocean",
    "arktyczny": "Arctic Ocean", "ocean arktyczny": "Arctic Ocean", "arktyk": "Arctic Ocean",
    # Indian Ocean
    "indian ocean": "Indian Ocean", "indian": "Indian Ocean",
    "indyjski": "Indian Ocean", "ocean indyjski": "Indian Ocean",
    # Southern Ocean
    "southern ocean": "Southern Ocean", "antarktyczny": "Southern Ocean",
    # Seas & Gulfs
    "baltic sea": "Baltic Sea", "baltic": "Baltic Sea", "baltyk": "Baltic Sea", "baltyku": "Baltic Sea", "baltykiem": "Baltic Sea",
    "mediterranean sea": "Mediterranean Sea", "mediterranean": "Mediterranean Sea", "morze srodziemne": "Mediterranean Sea",
    "black sea": "Black Sea", "morze czarne": "Black Sea",
    "north sea": "North Sea", "morze polnocne": "North Sea",
    "red sea": "Red Sea", "morze czerwone": "Red Sea",
    "caribbean sea": "Caribbean Sea", "morze karaibskie": "Caribbean Sea",
    "gulf of mexico": "Gulf of Mexico", "gulf": "Gulf of Mexico", "zatoka meksykanska": "Gulf of Mexico",
    "great lakes": "Great Lakes", "wielkie jeziora": "Great Lakes",
}
_BASE_POLISH_WATER_BODIES = {
    "Ocean Atlantycki": "Atlantic Ocean",
    "Ocean Spokojny": "Pacific Ocean",
    "Ocean Arktyczny": "Arctic Ocean",
    "Ocean Indyjski": "Indian Ocean",
    "Ocean Południowy": "Southern Ocean",
    "Morze Bałtyckie": "Baltic Sea",
    "Morze Śródziemne": "Mediterranean Sea",
    "Morze Czarne": "Black Sea",
    "Morze Północne": "North Sea",
    "Morze Czerwone": "Red Sea",
    "Morze Karaibskie": "Caribbean Sea",
    "Zatoka Meksykańska": "Gulf of Mexico",
    "Wielkie Jeziora": "Great Lakes",
    "Bałtyk": "Baltic Sea",
    "Atlantyk": "Atlantic Ocean",
    "Pacyfik": "Pacific Ocean",
}
for pl_name, canonical in _BASE_POLISH_WATER_BODIES.items():
    WATER_BODIES_MAP[norm_text(pl_name)] = canonical
    for form in expand_polish_phrase_forms(pl_name, reversible=True):
        WATER_BODIES_MAP[norm_text(form)] = canonical
_SORTED_WATERS = sorted(WATER_BODIES_MAP.keys(), key=len, reverse=True)
_WATER_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in _SORTED_WATERS) + r")\b")

# 1.6 Driving Side
DRIVING_SIDE_MAP = {
    "left": "left", "left hand": "left", "left side": "left",
    "right": "right", "right hand": "right", "right side": "right",
}
_SORTED_SIDES = sorted(DRIVING_SIDE_MAP.keys(), key=len, reverse=True)
_SIDE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in _SORTED_SIDES) + r")\b")

# 1.7 International Organizations & Historical Unions
MEMBERSHIPS_MAP = {
    "eu": "EU", "european union": "EU",
    "nato": "NATO", "un": "UN", "united nations": "UN",
    "schengen": "Schengen", "benelux": "Benelux",
    "african union": "African Union", "asean": "ASEAN",
    "commonwealth": "Commonwealth", "g7": "G7", "g20": "G20", "oecd": "OECD",
}
_SORTED_MEMBERSHIPS = sorted(MEMBERSHIPS_MAP.keys(), key=len, reverse=True)
_MEMBERSHIP_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(m) for m in _SORTED_MEMBERSHIPS) + r")\b")

HISTORICAL_MAP = {
    "ussr": "USSR", "soviet union": "USSR",
    "yugoslavia": "Yugoslavia",
    "czechoslovakia": "Czechoslovakia",
    "warsaw pact": "Warsaw Pact",
    "british empire": "British Empire",
    "spanish empire": "Spanish Empire",
    "french empire": "French Empire",
    "ottoman empire": "Ottoman Empire",
    "austro hungarian empire": "Austro-Hungarian Empire",
    "austria hungary": "Austro-Hungarian Empire",
    "gran colombia": "Gran Colombia",
}
_SORTED_HISTORICAL = sorted(HISTORICAL_MAP.keys(), key=len, reverse=True)
_HISTORICAL_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(h) for h in _SORTED_HISTORICAL) + r")\b")

# 1.8 Official Languages
LANGUAGES_MAP: dict[str, str] = {
    "english": "English", "spanish": "Spanish", "french": "French", "german": "German",
    "arabic": "Arabic", "russian": "Russian", "portuguese": "Portuguese", "chinese": "Chinese",
    "italian": "Italian", "japanese": "Japanese", "dutch": "Dutch", "greek": "Greek",
    "turkish": "Turkish", "swahili": "Swahili", "polish": "Polish",
}
_SORTED_LANGUAGES = sorted(LANGUAGES_MAP.keys(), key=len, reverse=True)
_LANGUAGE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(lang) for lang in _SORTED_LANGUAGES) + r")\b")

# 1.9 Flag Colors
FLAG_COLORS_MAP: dict[str, str] = {
    "red": "red", "white": "white", "blue": "blue", "green": "green",
    "yellow": "yellow", "black": "black", "orange": "orange",
}
_SORTED_FLAG_COLORS = sorted(FLAG_COLORS_MAP.keys(), key=len, reverse=True)
_FLAG_COLOR_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in _SORTED_FLAG_COLORS) + r")\b")

# 1.10 Flag Symbols
FLAG_SYMBOLS_MAP: dict[str, str] = {
    "star": "star", "stars": "star", "cross": "cross", "crescent": "crescent",
    "crescent moon": "crescent", "moon": "crescent",
    "sun": "sun", "stripes": "stripes", "stripe": "stripes", "circle": "circle", "eagle": "eagle",
    "coat of arms": "coat_of_arms", "coat_of_arms": "coat_of_arms",
    "polksiezyc": "crescent", "półksiężyc": "crescent", "ksiezyc": "crescent", "księżyc": "crescent",
    "gwiazda": "star", "gwiazdy": "stars", "gwiazdka": "star", "gwiazdki": "stars",
    "krzyz": "cross", "krzyż": "cross",
    "slonce": "sun", "słońce": "sun",
    "pasy": "stripes", "paski": "stripes",
    "kolo": "circle", "koło": "circle",
    "orzel": "eagle", "orzeł": "eagle",
    "herb": "coat_of_arms", "godlo": "coat_of_arms", "godło": "coat_of_arms",
}
_SORTED_FLAG_SYMBOLS = sorted(FLAG_SYMBOLS_MAP.keys(), key=len, reverse=True)
_FLAG_SYMBOL_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in _SORTED_FLAG_SYMBOLS) + r")\b")


# ==============================================================================
# 2. MASKING ENGINE
# ==============================================================================

def mask_query(raw_query: str, mode: str = "countrydle") -> tuple[str, dict[str, Any]]:
    """Mask recognized slots into [SLOT] tags and return (masked_skeleton, slots_dict)."""
    q = norm_text(raw_query)
    slots: dict[str, Any] = {}

    # Comparison Operator
    def _sub_comp_op(m):
        slots["COMP_OP"] = COMP_OPS_MAP[m.group(0)]
        return "[COMP_OP]"
    q = _COMP_OP_PATTERN.sub(_sub_comp_op, q, count=1)

    # Number
    def _sub_num(m):
        slots["NUMBER"] = int(m.group(0))
        return "[NUMBER]"
    q = re.sub(r"\b\d+\b", _sub_num, q, count=1)

    # Water Body
    def _sub_water(m):
        slots["WATER_BODY"] = WATER_BODIES_MAP[m.group(0)]
        return "[WATER_BODY]"
    q = _WATER_PATTERN.sub(_sub_water, q, count=1)

    # Historical Union
    def _sub_hist(m):
        slots["HISTORICAL"] = HISTORICAL_MAP[m.group(0)]
        return "[HISTORICAL]"
    q = _HISTORICAL_PATTERN.sub(_sub_hist, q, count=1)

    # Membership
    def _sub_mem(m):
        slots["MEMBERSHIP"] = MEMBERSHIPS_MAP[m.group(0)]
        return "[MEMBERSHIP]"
    q = _MEMBERSHIP_PATTERN.sub(_sub_mem, q, count=1)

    # Driving Side
    def _sub_side(m):
        slots["SIDE"] = DRIVING_SIDE_MAP[m.group(0)]
        return "[SIDE]"
    q = _SIDE_PATTERN.sub(_sub_side, q, count=1)

    # Official Language (only if language or official in q)
    if "language" in q or "official" in q:
        def _sub_lang(m):
            slots["LANGUAGE"] = LANGUAGES_MAP[m.group(0)]
            return "[LANGUAGE]"
        q = _LANGUAGE_PATTERN.sub(_sub_lang, q, count=1)

    # Flag Colors & Symbols (only if flag in q)
    if "flag" in q:
        def _sub_color(m):
            slots["COLOR"] = FLAG_COLORS_MAP[m.group(0)]
            return "[COLOR]"
        q = _FLAG_COLOR_PATTERN.sub(_sub_color, q, count=1)

        def _sub_symbol(m):
            slots["SYMBOL"] = FLAG_SYMBOLS_MAP[m.group(0)]
            return "[SYMBOL]"
        q = _FLAG_SYMBOL_PATTERN.sub(_sub_symbol, q, count=1)

    # Mode-specific Entity matching
    if mode in ("countrydle", "world", "continental"):
        def _sub_country(m):
            slots["COUNTRY"] = COUNTRIES_MAP[m.group(0)]
            return "[COUNTRY]"
        q = _COUNTRY_PATTERN.sub(_sub_country, q, count=1)
    elif mode in ("usstatedle", "us_statedle", "us_state"):
        # Match US State first, then Country (for Canada/Mexico borders)
        def _sub_state(m):
            slots["STATE"] = US_STATES_MAP[m.group(0)]
            return "[STATE]"
        q = _US_STATE_PATTERN.sub(_sub_state, q, count=1)
        if "[STATE]" not in q:
            def _sub_c(m):
                slots["COUNTRY"] = COUNTRIES_MAP[m.group(0)]
                return "[COUNTRY]"
            q = _COUNTRY_PATTERN.sub(_sub_c, q, count=1)
    elif mode in ("wojewodztwodle", "wojewodztwo"):
        def _sub_voj(m):
            slots["VOIVODESHIP"] = VOIVODESHIPS_MAP[m.group(0)]
            return "[VOIVODESHIP]"
        q = _VOIVODESHIP_PATTERN.sub(_sub_voj, q, count=1)
    elif mode in ("powiatdle", "powiat"):
        pass
    q = re.sub(r"\s+", " ", q).strip()
    return q, slots


# ==============================================================================
# 3. SKELETON REGISTRY (O(1) STATIC DICTIONARY LOOKUP)
# ==============================================================================

TemplateBuilder = Callable[[dict[str, Any], str], Optional[Tuple[Any, str]]]

# Global registry: (mode, skeleton) -> TemplateBuilder
_SKELETON_REGISTRY: dict[tuple[str, str], TemplateBuilder] = {}


def register_skeleton(modes: list[str], skeletons: list[str]):
    """Decorator registering declarative skeletons to a template generator."""
    def decorator(fn: TemplateBuilder):
        for m in modes:
            for s in skeletons:
                _SKELETON_REGISTRY[(m, s)] = fn
        return fn
    return decorator


# ------------------------------------------------------------------------------
# 3.1 Borders Count & Comparison Skeletons
# ------------------------------------------------------------------------------

@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does it border [NUMBER] countries",
        "does it border [NUMBER] country",
        "does it have [NUMBER] neighbors",
        "does it have [NUMBER] neighbor",
        "does it have [NUMBER] bordering countries",
        "does the country border [NUMBER] countries",
        "does the country have [NUMBER] neighbors",
        "czy ma [NUMBER] sasiadow",
        "czy ma [NUMBER] sasiada",
        "czy graniczy z [NUMBER] panstwami",
        "czy graniczy z [NUMBER] panstwem",
        "czy to panstwo ma [NUMBER] sasiadow",
        "czy to panstwo graniczy z [NUMBER] panstwami",
    ]
)
def _build_country_border_count_eq(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    ast = [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "borders_country"}, "right": {"value": num}}
    ]
    return ast, f"Does the country have {num} neighbors?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does it border [COMP_OP] [NUMBER] countries",
        "does it have [COMP_OP] [NUMBER] neighbors",
        "does it have [COMP_OP] [NUMBER] bordering countries",
        "does the country border [COMP_OP] [NUMBER] countries",
        "does the country have [COMP_OP] [NUMBER] neighbors",
        "czy ma [COMP_OP] [NUMBER] sasiadow",
        "czy graniczy z [COMP_OP] [NUMBER] panstwami",
        "czy to panstwo ma [COMP_OP] [NUMBER] sasiadow",
        "czy to panstwo graniczy z [COMP_OP] [NUMBER] panstwami",
    ]
)
def _build_country_border_count_comp(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    op = slots.get("COMP_OP", "greater_than")
    ast = [
        {"operator": op, "left": {"entity": "target_country", "relation": "borders_country"}, "right": {"value": num}}
    ]
    op_label = "more than" if op == "greater_than" else "fewer than" if op == "less_than" else "at least"
    return ast, f"Does the country have {op_label} {num} neighbors?"


@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it border [NUMBER] states",
        "does it border [NUMBER] state",
        "does it have [NUMBER] neighbors",
        "does it have [NUMBER] neighboring states",
        "does the state border [NUMBER] states",
        "does the state have [NUMBER] neighbors",
        "czy graniczy z [NUMBER] stanami",
        "czy ma [NUMBER] sasiadow",
    ]
)
def _build_us_state_border_count_eq(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    ast = {
        "operator": "equals",
        "left": {"entity": "target_state", "relation": "borders_state"},
        "right": {"value": num},
    }
    return ast, f"Does the state border {num} states?"


@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it border [COMP_OP] [NUMBER] states",
        "does it have [COMP_OP] [NUMBER] neighbors",
        "does it have [COMP_OP] [NUMBER] neighboring states",
        "czy graniczy z [COMP_OP] [NUMBER] stanami",
        "czy ma [COMP_OP] [NUMBER] sasiadow",
    ]
)
def _build_us_state_border_count_comp(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    op = slots.get("COMP_OP", "greater_than")
    ast = {
        "operator": op,
        "left": {"entity": "target_state", "relation": "borders_state"},
        "right": {"value": num},
    }
    op_label = "more than" if op == "greater_than" else "fewer than" if op == "less_than" else "at least"
    return ast, f"Does the state border {op_label} {num} states?"

@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it border [STATE]",
        "does it border the state of [STATE]",
        "does the state border [STATE]",
        "does the state border the state of [STATE]",
        "is it next to [STATE]",
        "czy graniczy ze stanem [STATE]",
        "czy graniczy ze [STATE]",
        "czy graniczy z [STATE]",
        "czy ten stan graniczy z [STATE]",
        "czy ten stan graniczy ze stanem [STATE]",
    ],
)
def _build_us_state_border_state(slots: dict[str, Any], mode: str):
    state = slots.get("STATE", "Texas")
    ast = {
        "operator": "contains_exact",
        "left": {"entity": "target_state", "relation": "borders_state"},
        "right": {"value": state},
    }
    return ast, f"Does the state border {state}?"


@register_skeleton(
    ["wojewodztwodle", "wojewodztwo"],
    [
        "czy graniczy z [NUMBER] wojewodztwami",
        "czy graniczy z [NUMBER] wojewodztwem",
        "czy ma [NUMBER] sasiadow",
        "czy to wojewodztwo ma [NUMBER] sasiadow",
        "does it border [NUMBER] voivodeships",
        "does it have [NUMBER] neighbors",
    ]
)
def _build_wojewodztwo_border_count_eq(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    ast = {
        "operator": "equals",
        "left": {"entity": "target_voivodeship", "relation": "borders_voivodeship"},
        "right": {"value": num},
    }
    return ast, f"Does the voivodeship border {num} voivodeships?"


@register_skeleton(
    ["wojewodztwodle", "wojewodztwo"],
    [
        "czy graniczy z [COMP_OP] [NUMBER] wojewodztwami",
        "czy ma [COMP_OP] [NUMBER] sasiadow",
        "czy to wojewodztwo ma [COMP_OP] [NUMBER] sasiadow",
        "does it border [COMP_OP] [NUMBER] voivodeships",
        "does it have [COMP_OP] [NUMBER] neighbors",
    ]
)
def _build_wojewodztwo_border_count_comp(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    op = slots.get("COMP_OP", "greater_than")
    ast = {
        "operator": op,
        "left": {"entity": "target_voivodeship", "relation": "borders_voivodeship"},
        "right": {"value": num},
    }
    return ast, f"Does the voivodeship have {op.replace('_', ' ')} {num} neighbors?"


@register_skeleton(
    ["powiatdle", "powiat"],
    [
        "czy graniczy z [NUMBER] powiatami",
        "czy graniczy z [NUMBER] powiatem",
        "czy ma [NUMBER] sasiadow",
        "czy ma [NUMBER] sasiada",
        "does it border [NUMBER] counties",
        "does it border [NUMBER] county",
        "does it have [NUMBER] neighbors",
        "does it have [NUMBER] neighbor",
    ]
)
def _build_powiat_border_count_eq(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    ast = {
        "operator": "equals",
        "left": {"entity": "target_powiat", "relation": "borders_powiat"},
        "right": {"value": num},
    }
    return ast, f"Does the county border {num} counties?"


@register_skeleton(
    ["powiatdle", "powiat"],
    [
        "czy graniczy z [COMP_OP] [NUMBER] powiatami",
        "czy graniczy z [COMP_OP] [NUMBER] powiatem",
        "czy ma [COMP_OP] [NUMBER] sasiadow",
        "czy ma [COMP_OP] [NUMBER] sasiada",
        "does it border [COMP_OP] [NUMBER] counties",
        "does it have [COMP_OP] [NUMBER] neighbors",
    ]
)
def _build_powiat_border_count_comp(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 0)
    op = slots.get("COMP_OP", "greater_than")
    ast = {
        "operator": op,
        "left": {"entity": "target_powiat", "relation": "borders_powiat"},
        "right": {"value": num},
    }
    return ast, f"Does the county border {op.replace('_', ' ')} {num} counties?"


# ------------------------------------------------------------------------------
# 3.2 Specific Water Bodies & Ocean Access
# ------------------------------------------------------------------------------

def build_us_state_water_plan(body: str, *, direct: bool) -> tuple[dict[str, Any], str]:
    """Keep parent-ocean access distinct from direct named-water coastline."""
    predicate = {
        "operator": "contains_exact",
        "left": {"entity": "target_state", "relation": "water_access"},
        "right": {"value": body},
    }
    if not direct and body == "Atlantic Ocean":
        predicate = {
            "operator": "or",
            "conditions": [
                predicate,
                {
                    "operator": "contains_exact",
                    "left": {"entity": "target_state", "relation": "water_access"},
                    "right": {"value": "Gulf of Mexico"},
                },
            ],
        }
    wording = "border" if direct else "have access to"
    return predicate, f"Does the state {wording} the {body}?"


@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it have access to [WATER_BODY]",
        "does it have access to the [WATER_BODY]",
        "does the state have access to [WATER_BODY]",
        "does the state have access to the [WATER_BODY]",
        "czy ma dostep do [WATER_BODY]",
        "czy ma dostep do oceanu [WATER_BODY]",
    ],
)
def _build_us_state_water_access(slots: dict[str, Any], mode: str):
    return build_us_state_water_plan(slots["WATER_BODY"], direct=False)


@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it border [WATER_BODY]",
        "does it border the [WATER_BODY]",
        "does it touch [WATER_BODY]",
        "does it touch the [WATER_BODY]",
        "does the state border [WATER_BODY]",
        "does the state border the [WATER_BODY]",
        "does it have a direct coastline on [WATER_BODY]",
        "does it have a direct coastline on the [WATER_BODY]",
        "does the state have a direct coastline on [WATER_BODY]",
        "does the state have a direct coastline on the [WATER_BODY]",
        "is it on [WATER_BODY]",
        "is it on the [WATER_BODY]",
        "is it located on [WATER_BODY]",
        "is it located on the [WATER_BODY]",
        "czy lezy nad [WATER_BODY]",
        "czy graniczy z [WATER_BODY]",
    ]
)
def _build_us_state_water_body(slots: dict[str, Any], mode: str):
    return build_us_state_water_plan(slots["WATER_BODY"], direct=True)


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does it have access to [WATER_BODY]",
        "does it have access to the [WATER_BODY]",
        "does it border [WATER_BODY]",
        "does it border the [WATER_BODY]",
        "does the country have access to [WATER_BODY]",
        "does the country have access to the [WATER_BODY]",
        "does the country border [WATER_BODY]",
        "does the country border the [WATER_BODY]",
        "czy ma dostep do [WATER_BODY]",
        "czy ma dostep do oceanu [WATER_BODY]",
        "czy ten kraj ma dostep do oceanu [WATER_BODY]",
        "czy lezy nad [WATER_BODY]",
        "czy graniczy z [WATER_BODY]",
        "czy to panstwo ma dostep do [WATER_BODY]",
    ]
)
def _build_country_water_body(slots: dict[str, Any], mode: str):
    body = slots.get("WATER_BODY", "Atlantic Ocean")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "water_access"}, "right": {"value": body}}
    ]
    return ast, f"Does the country have access to the {body}?"


# ------------------------------------------------------------------------------
# 3.3 Zero-Slot Core Templates
# ------------------------------------------------------------------------------

@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is it landlocked",
        "is the country landlocked",
        "czy jest srodladowe",
        "czy to kraj srodladowy",
        "czy panstwo jest srodladowe",
        "brak dostepu do morza",
    ]
)
def _build_country_landlocked(slots: dict[str, Any], mode: str):
    ast = [
        {"operator": "exists", "left": {"entity": "target_country", "relation": "marine_access"}},
        {"operator": "not", "args": [0]},
    ]
    return ast, "Is the country landlocked?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is it an island",
        "is the country an island",
        "czy to wyspa",
        "czy jest wyspa",
        "czy panstwo to wyspa",
    ]
)
def _build_country_island(slots: dict[str, Any], mode: str):
    ast = [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "is_island"}, "right": {"value": True}}
    ]
    return ast, "Is the country an island?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does it drive on the [SIDE]",
        "does it have [SIDE] hand traffic",
        "does the country drive on the [SIDE]",
        "does it drive [SIDE]",
        "does the country drive [SIDE]",
        "is it [SIDE] driving",
        "is it a [SIDE] driving country",
    ]
)
def _build_country_driving_side(slots: dict[str, Any], mode: str):
    side = slots.get("SIDE", "left")
    ast = [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "driving_side"}, "right": {"value": side}}
    ]
    return ast, f"Does the country drive on the {side}?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is it a monarchy",
        "is the country a monarchy",
    ],
)
def _build_country_monarchy(slots: dict[str, Any], mode: str):
    ast = [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "government_type"}, "right": {"value": "Monarchy"}}
    ]
    return ast, "Is the country a monarchy?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is it a republic",
        "is the country a republic",
    ],
)
def _build_country_republic(slots: dict[str, Any], mode: str):
    ast = [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "government_type"}, "right": {"value": "Republic"}}
    ]
    return ast, "Is the country a republic?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is [LANGUAGE] an official language",
        "is [LANGUAGE] an official language of the country",
        "is [LANGUAGE] the official language",
        "does it have [LANGUAGE] as an official language",
        "does the country have [LANGUAGE] as an official language",
    ],
)
def _build_country_language(slots: dict[str, Any], mode: str):
    lang = slots.get("LANGUAGE", "English")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "official_language"}, "right": {"value": lang}}
    ]
    return ast, f"Is {lang} an official language?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does its flag contain [COLOR]",
        "does the flag contain [COLOR]",
        "does its flag have [COLOR]",
        "does the flag have [COLOR]",
        "is there [COLOR] on its flag",
        "is [COLOR] on its flag",
    ],
)
def _build_country_flag_color(slots: dict[str, Any], mode: str):
    color = slots.get("COLOR", "red")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "flag_color"}, "right": {"value": color}}
    ]
    return ast, f"Does the country's flag contain {color}?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does its flag contain a [SYMBOL]",
        "does its flag contain [SYMBOL]",
        "does the flag contain a [SYMBOL]",
        "does the flag contain [SYMBOL]",
        "does its flag have a [SYMBOL]",
        "does its flag have [SYMBOL]",
        "does the flag have a [SYMBOL]",
        "does the flag have [SYMBOL]",
        "does it have a [SYMBOL] in a flag",
        "does it have a [SYMBOL] in the flag",
        "does it have a [SYMBOL] in its flag",
        "does it have a [SYMBOL] on its flag",
        "does it have a [SYMBOL] on the flag",
        "does it have a [SYMBOL] on flag",
        "does it have a [SYMBOL] in flag",
        "does it have [SYMBOL] on its flag",
        "does it have [SYMBOL] in its flag",
        "does the country have a [SYMBOL] on its flag",
        "does the country have a [SYMBOL] in its flag",
        "does the country have a [SYMBOL] on the flag",
        "does the country have a [SYMBOL] in a flag",
        "is there a [SYMBOL] on its flag",
        "is there a [SYMBOL] on the flag",
        "is there a [SYMBOL] in its flag",
        "is there a [SYMBOL] in the flag",
        "is there a [SYMBOL] on flag",
        "is there a [SYMBOL] in flag",
        "czy na fladze jest [SYMBOL]",
        "czy w fladze jest [SYMBOL]",
        "czy flaga ma [SYMBOL]",
        "czy flaga posiada [SYMBOL]",
    ],
)
def _build_country_flag_symbol(slots: dict[str, Any], mode: str):
    symbol = slots.get("SYMBOL", "star")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "flag_symbol"}, "right": {"value": symbol}}
    ]
    return ast, f"Does the country's flag contain {symbol}?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does the country name have a hyphen",
        "does its name have a hyphen",
        "does the name have a hyphen",
    ],
)
def _build_country_name_hyphen(slots: dict[str, Any], mode: str):
    ast = [
        {"operator": "has_hyphen", "left": {"entity": "target_country", "relation": "name"}}
    ]
    return ast, "Does the country name have a hyphen?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "does the country name have [NUMBER] words",
        "does its name have [NUMBER] words",
        "does the name have [NUMBER] words",
        "is the country name [NUMBER] words",
        "is its name [NUMBER] words",
    ],
)
def _build_country_name_words(slots: dict[str, Any], mode: str):
    num = slots.get("NUMBER", 2)
    ast = [
        {"operator": "word_count_equals", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": num}}
    ]
    return ast, f"Does the country name have {num} words?"

@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "is it in [MEMBERSHIP]",
        "is it in the [MEMBERSHIP]",
        "is it a member of [MEMBERSHIP]",
        "is it a member of the [MEMBERSHIP]",
        "is the country in [MEMBERSHIP]",
        "is the country in the [MEMBERSHIP]",
        "is the country a member of [MEMBERSHIP]",
        "is the country a member of the [MEMBERSHIP]",
        "does it belong to [MEMBERSHIP]",
        "does it belong to the [MEMBERSHIP]",
        "does the country belong to [MEMBERSHIP]",
        "does the country belong to the [MEMBERSHIP]",
        "czy nalezy do [MEMBERSHIP]",
        "czy to panstwo nalezy do [MEMBERSHIP]",
    ]
)
def _build_country_membership(slots: dict[str, Any], mode: str):
    org = slots.get("MEMBERSHIP", "EU")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "membership"}, "right": {"value": org}}
    ]
    return ast, f"Is the country in {org}?"


@register_skeleton(
    ["countrydle", "world", "continental"],
    [
        "was it part of [HISTORICAL]",
        "was it part of the [HISTORICAL]",
        "was it in the [HISTORICAL]",
        "was the country part of the [HISTORICAL]",
    ]
)
def _build_country_historical(slots: dict[str, Any], mode: str):
    union = slots.get("HISTORICAL", "USSR")
    ast = [
        {"operator": "contains", "left": {"entity": "target_country", "relation": "historical_union"}, "right": {"value": union}}
    ]
    return ast, f"Was the country part of {union}?"


@register_skeleton(
    ["powiatdle", "powiat"],
    [
        "czy to miasto na prawach powiatu",
        "czy jest to miasto na prawach powiatu",
        "czy to powiat grodzki",
        "czy jest to powiat grodzki",
    ]
)
def _build_powiat_city_county(slots: dict[str, Any], mode: str):
    ast = {
        "operator": "equals",
        "left": {"entity": "target_powiat", "relation": "is_city_county"},
        "right": {"value": 1},
    }
    return ast, "Is this a city county?"


@register_skeleton(
    ["powiatdle", "powiat"],
    [
        "czy to powiat ziemski",
        "czy jest to powiat ziemski",
    ]
)
def _build_powiat_land_county(slots: dict[str, Any], mode: str):
    ast = {
        "operator": "equals",
        "left": {"entity": "target_powiat", "relation": "is_city_county"},
        "right": {"value": 0},
    }
    return ast, "Is this a land county?"


# ==============================================================================
# 4. PUBLIC COMPILER DISPATCH
# ==============================================================================

_MODE_CANONICAL = {
    "countrydle": "countrydle",
    "world": "countrydle",
    "continental": "countrydle",
    "usstatedle": "usstatedle",
    "us_statedle": "usstatedle",
    "us_state": "usstatedle",
    "wojewodztwodle": "wojewodztwodle",
    "wojewodztwo": "wojewodztwodle",
    "powiatdle": "powiatdle",
    "powiat": "powiatdle",
}


def match_slot_template(raw_query: str, mode: str = "countrydle") -> Optional[Tuple[Any, str]]:
    """Match a query against the declarative slot-masked template registry.

    Returns:
        (ast, improved_question) if matched, otherwise None.
    """
    mode_clean = mode.lower().replace("-", "_")
    canon_mode = _MODE_CANONICAL.get(mode_clean, mode_clean)
    skeleton, slots = mask_query(raw_query, mode=canon_mode)

    builder = _SKELETON_REGISTRY.get((canon_mode, skeleton))
    if builder:
        try:
            return builder(slots, canon_mode)
        except Exception:
            return None

    return None
