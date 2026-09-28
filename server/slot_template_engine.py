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
US_STATES_MAP: dict[str, str] = {norm_text(s): s for s in _US_STATES}
# Polish inflections for popular states
US_STATES_MAP.update({
    "kalifornia": "California", "kalifornii": "California", "kalifornie": "California",
    "teksas": "Texas", "teksasu": "Texas", "teksasem": "Texas",
    "floryda": "Florida", "florydy": "Florida", "florydzie": "Florida",
    "alaska": "Alaska", "alaski": "Alaska", "alasce": "Alaska",
    "hawaje": "Hawaii", "hawajach": "Hawaii", "hawajow": "Hawaii",
    "nowy jork": "New York", "nowego jorku": "New York",
    "karolina polnocna": "North Carolina", "karoliny polnocnej": "North Carolina",
    "karolina poludniowa": "South Carolina", "karoliny poludniowej": "South Carolina",
    "dakota polnocna": "North Dakota", "dakota poludniowa": "South Dakota",
    "wirginia": "Virginia", "wirginii": "Virginia",
})
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
_SORTED_WATERS = sorted(WATER_BODIES_MAP.keys(), key=len, reverse=True)
_WATER_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in _SORTED_WATERS) + r")\b")

# 1.6 Driving Side
DRIVING_SIDE_MAP = {
    "left": "left", "left hand": "left", "left side": "left", "lewostronny": "left", "lewej": "left",
    "right": "right", "right hand": "right", "right side": "right", "prawostronny": "right", "prawej": "right",
}
_SORTED_SIDES = sorted(DRIVING_SIDE_MAP.keys(), key=len, reverse=True)
_SIDE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in _SORTED_SIDES) + r")\b")

# 1.7 International Organizations & Historical Unions
MEMBERSHIPS_MAP = {
    "eu": "EU", "ue": "EU", "european union": "EU", "unia europejska": "EU", "unii europejskiej": "EU",
    "nato": "NATO", "un": "UN", "onz": "UN",
}
_SORTED_MEMBERSHIPS = sorted(MEMBERSHIPS_MAP.keys(), key=len, reverse=True)
_MEMBERSHIP_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(m) for m in _SORTED_MEMBERSHIPS) + r")\b")

HISTORICAL_MAP = {
    "ussr": "USSR", "zsrr": "USSR", "soviet union": "USSR", "zwiazek radziecki": "USSR",
    "yugoslavia": "Yugoslavia", "jugoslawia": "Yugoslavia", "jugoslawii": "Yugoslavia",
    "czechoslovakia": "Czechoslovakia", "czechoslowacja": "Czechoslovakia", "czechoslowacji": "Czechoslovakia",
    "warsaw pact": "Warsaw Pact", "uklad warszawski": "Warsaw Pact",
    "british empire": "British Empire", "imperium brytyjskie": "British Empire",
    "spanish empire": "Spanish Empire", "imperium hiszpanskie": "Spanish Empire",
    "french empire": "French Empire", "imperium francuskie": "French Empire",
    "ottoman empire": "Ottoman Empire", "imperium osmanskie": "Ottoman Empire",
}
_SORTED_HISTORICAL = sorted(HISTORICAL_MAP.keys(), key=len, reverse=True)
_HISTORICAL_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(h) for h in _SORTED_HISTORICAL) + r")\b")


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
        if "[VOIVODESHIP]" not in q:
            def _sub_c(m):
                slots["COUNTRY"] = COUNTRIES_MAP[m.group(0)]
                return "[COUNTRY]"
            q = _COUNTRY_PATTERN.sub(_sub_c, q, count=1)
    elif mode in ("powiatdle", "powiat"):
        def _sub_c(m):
            slots["COUNTRY"] = COUNTRIES_MAP[m.group(0)]
            return "[COUNTRY]"
        q = _COUNTRY_PATTERN.sub(_sub_c, q, count=1)

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
    return ast, f"Czy województwo graniczy z {num} województwami?"


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
    return ast, f"Czy województwo ma {op.replace('_', ' ')} {num} sąsiadów?"


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
    return ast, f"Czy powiat graniczy z {num} powiatami?"


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
    return ast, f"Czy powiat graniczy z {op.replace('_', ' ')} {num} powiatami?"


# ------------------------------------------------------------------------------
# 3.2 Specific Water Bodies & Ocean Access
# ------------------------------------------------------------------------------

@register_skeleton(
    ["usstatedle", "us_statedle", "us_state"],
    [
        "does it have access to [WATER_BODY]",
        "does it have access to the [WATER_BODY]",
        "does it border [WATER_BODY]",
        "does it border the [WATER_BODY]",
        "does it touch [WATER_BODY]",
        "does it touch the [WATER_BODY]",
        "is it on [WATER_BODY]",
        "is it on the [WATER_BODY]",
        "is it located on [WATER_BODY]",
        "is it located on the [WATER_BODY]",
        "czy ma dostep do [WATER_BODY]",
        "czy ma dostep do oceanu [WATER_BODY]",
        "czy lezy nad [WATER_BODY]",
        "czy graniczy z [WATER_BODY]",
    ]
)
def _build_us_state_water_body(slots: dict[str, Any], mode: str):
    body = slots.get("WATER_BODY", "Atlantic Ocean")
    ast = {
        "operator": "contains_exact",
        "left": {"entity": "target_state", "relation": "water_access"},
        "right": {"value": body},
    }
    return ast, f"Does the state have access to the {body}?"


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
        {"operator": "exists", "left": {"entity": "target_country", "relation": "water_access"}},
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
        "czy ruch jest [SIDE]",
        "czy obowiazuje ruch [SIDE]",
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
        "is it in the [MEMBERSHIP]",
        "is it a member of [MEMBERSHIP]",
        "is it a member of the [MEMBERSHIP]",
        "is the country in the [MEMBERSHIP]",
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
        "czy nalezalo do [HISTORICAL]",
        "czy bylo czescia [HISTORICAL]",
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
    return ast, "Czy to miasto na prawach powiatu?"


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
    return ast, "Czy to powiat ziemski?"


# ==============================================================================
# 4. PUBLIC COMPILER DISPATCH
# ==============================================================================

def match_slot_template(raw_query: str, mode: str = "countrydle") -> Optional[Tuple[Any, str]]:
    """Match a query against the declarative slot-masked template registry.

    Returns:
        (ast, improved_question) if matched, otherwise None.
    """
    mode_clean = mode.lower().replace("-", "_")
    skeleton, slots = mask_query(raw_query, mode=mode_clean)
    
    # Try mode-specific skeleton lookup
    builder = _SKELETON_REGISTRY.get((mode_clean, skeleton))
    if not builder:
        # Fall back to generic mode aliases
        for alt_mode in ("countrydle", "usstatedle", "wojewodztwodle", "powiatdle"):
            builder = _SKELETON_REGISTRY.get((alt_mode, skeleton))
            if builder:
                break

    if builder:
        try:
            return builder(slots, mode_clean)
        except Exception:
            return None

    return None
