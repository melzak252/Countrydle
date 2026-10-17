"""Deterministic in-memory compiler for common single-intent geography questions."""
from __future__ import annotations

from functools import lru_cache
from math import isfinite
import re
import unicodedata

from polish_morphology import canonicalize_pl_clause, expand_polish_phrase_forms, norm_pl

@lru_cache(maxsize=512)
def _norm(value: str) -> str:
    folded = value.casefold().replace("ł", "l")
    if folded.isascii():
        return folded
    normalized = unicodedata.normalize("NFKD", folded)
    return "".join(char for char in normalized if not unicodedata.combining(char))

_TARGET = {"entity": "target_country"}

def _node(operator: str, relation: str, value=None):
    result = {"operator": operator, "left": {**_TARGET, "relation": relation}}
    if value is not None:
        result["right"] = {"value": value}
    return result

@lru_cache(maxsize=32)
def _choice_pattern(items):
    aliases = {}
    for canonical, values in items:
        for alias in values:
            aliases[_norm(alias)] = canonical
    alternatives = sorted(aliases, key=len, reverse=True)
    expression = r"(?<![a-z])(?:" + "|".join(re.escape(alias) for alias in alternatives) + r")(?![a-z])"
    return re.compile(expression), aliases


def _choices(mapping, text):
    pattern, aliases = _choice_pattern(tuple((canonical, tuple(values)) for canonical, values in mapping.items()))
    found = pattern.findall(text)
    if not found:
        return None
    longest = max(found, key=len)
    values = {aliases[alias] for alias in found if len(alias) == len(longest)}
    return values.pop() if len(values) == 1 else None


CONTINENTS = {
    "Europe": ("Europe", "Europa", "Europie", "Europy"), "Asia": ("Asia", "Azja", "Azji"),
    "Africa": ("Africa", "Afryka", "Afryce", "Afryki"),
    "North America": ("North America", "Ameryka Północna", "Ameryce Północnej"),
    "South America": ("South America", "Ameryka Południowa", "Ameryce Południowej"),
    "Oceania": ("Oceania", "Oceanii"),
}
AREAS = {
    "Balkans": ("Balkans", "the Balkans"),
    "Baltic states": ("Baltic states", "the Baltic states", "the Baltics"),
    "Central Europe": ("Central Europe", "central part of europe", "middle part of europe"),
    "Eastern Europe": ("Eastern Europe", "eastern part of europe", "east part of europe", "east of europe"),
    "Western Europe": ("Western Europe", "western part of europe", "west part of europe", "west of europe"),
    "Northern Europe": ("Northern Europe", "northern part of europe", "north part of europe", "north of europe"),
    "Southern Europe": ("Southern Europe", "southern part of europe", "south part of europe", "south of europe"),
    "Scandinavia": ("Scandinavia",),
    "Iberia": ("Iberia", "Iberian Peninsula"),
    "Middle East": ("Middle East", "the Middle East", "Mid East", "Mideast", "Middle-East"),
    "Arabian Peninsula": ("Arabian Peninsula", "the Arabian Peninsula"),
    "Indochina": ("Indochina",),
    "Central Asia": ("Central Asia", "central part of asia", "middle part of asia"),
    "Southeast Asia": ("Southeast Asia", "South East Asia", "South-East Asia", "South-Eastern Asia", "South Eastern Asia", "Southeastern Asia", "southeastern part of asia", "south eastern part of asia"),
    "South Asia": ("South Asia", "Southern Asia", "southern part of asia", "south part of asia", "south of asia"),
    "East Asia": ("East Asia", "Eastern Asia", "eastern part of asia", "east part of asia", "east of asia"),
    "Western Asia": ("Western Asia", "West Asia", "western part of asia", "west part of asia", "west of asia"),
    "Northern Africa": ("Northern Africa", "North Africa", "northern part of africa", "north part of africa", "north of africa"),
    "Southern Africa": ("Southern Africa", "southern part of africa", "south part of africa", "south of africa"),
    "Western Africa": ("Western Africa", "West Africa", "western part of africa", "west part of africa", "west of africa"),
    "Eastern Africa": ("Eastern Africa", "East Africa", "eastern part of africa", "east part of africa", "east of africa"),
    "Middle Africa": ("Middle Africa", "Central Africa", "central part of africa", "middle part of africa"),
    "Horn of Africa": ("Horn of Africa", "the Horn of Africa"),
    "Maghreb": ("Maghreb", "the Maghreb"),
    "Sahel": ("Sahel", "the Sahel"),
    "Central America": ("Central America",),
    "Caribbean": ("Caribbean", "the Caribbean"),
}
MEMBERSHIPS = {
    "EU": ("EU", "UE", "European Union"), "NATO": ("NATO",), "UN": ("UN", "ONZ", "United Nations"),
    "Schengen": ("Schengen",), "Benelux": ("Benelux",), "African Union": ("African Union",),
    "ASEAN": ("ASEAN",), "Commonwealth": ("Commonwealth",), "G7": ("G7",), "G20": ("G20",), "OECD": ("OECD",),
}
HISTORICAL = {
    "USSR": ("USSR", "the USSR", "Soviet Union", "the Soviet Union"),
    "Yugoslavia": ("Yugoslavia",),
    "Warsaw Pact": ("Warsaw Pact", "the Warsaw Pact"),
    "Czechoslovakia": ("Czechoslovakia",),
    "Austro-Hungarian Empire": ("Austro-Hungarian Empire", "the Austro-Hungarian Empire", "Austria-Hungary", "Austro-Hungary"),
    "Ottoman Empire": ("Ottoman Empire", "the Ottoman Empire"),
    "British Empire": ("British Empire", "the British Empire"),
    "Spanish Empire": ("Spanish Empire", "the Spanish Empire"),
    "French Empire": ("French Empire", "the French Empire"),
    "Portuguese Empire": ("Portuguese Empire", "the Portuguese Empire"),
    "Gran Colombia": ("Gran Colombia",),
}
WATERS = {
    "Ocean": ("ocean",), "Sea": ("sea",), "Baltic Sea": ("Baltic Sea",),
    "Mediterranean Sea": ("Mediterranean Sea", "the Mediterranean"),
    "Black Sea": ("Black Sea",), "North Sea": ("North Sea",), "Red Sea": ("Red Sea",), "Caribbean Sea": ("Caribbean Sea",),
    "Sea of Marmara": ("Sea of Marmara", "Marmara Sea", "the Sea of Marmara", "the Marmara Sea"),
    "Indian Ocean": ("Indian Ocean",), "Atlantic Ocean": ("Atlantic Ocean",),
    "Pacific Ocean": ("Pacific Ocean",), "Arctic Ocean": ("Arctic Ocean",), "Adriatic Sea": ("Adriatic Sea",),
}

# Country names are canonicalized against the same 196-country facts catalog; common Polish inflections are explicit.
_COUNTRY_NAMES = "Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|Argentina|Armenia|Australia|Austria|Azerbaijan|Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|Bhutan|Bolivia|Bosnia and Herzegovina|Botswana|Brazil|Brunei|Bulgaria|Burkina Faso|Burundi|Cambodia|Cameroon|Canada|Cape Verde|Central African Republic|Chad|Chile|China|Colombia|Comoros|Costa Rica|Croatia|Cuba|Cyprus|Czech Republic|Democratic Republic of the Congo|Denmark|Djibouti|Dominica|Dominican Republic|East Timor|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|Eswatini|Ethiopia|Federated States of Micronesia|Fiji|Finland|France|Gabon|Gambia|Georgia|Germany|Ghana|Greece|Grenada|Guatemala|Guinea|Guinea-Bissau|Guyana|Haiti|Honduras|Hungary|Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|Italy|Ivory Coast|Jamaica|Japan|Jordan|Kazakhstan|Kenya|Kiribati|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|Lithuania|Luxembourg|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall Islands|Mauritania|Mauritius|Mexico|Moldova|Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|Namibia|Nauru|Nepal|Netherlands|New Zealand|Nicaragua|Niger|Nigeria|North Korea|North Macedonia|Norway|Oman|Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|Philippines|Poland|Portugal|Qatar|Republic of the Congo|Romania|Russia|Rwanda|Saint Kitts and Nevis|Saint Lucia|Saint Vincent and the Grenadines|Samoa|San Marino|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|South Korea|South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|Syria|São Tomé and Príncipe|Tajikistan|Tanzania|Thailand|Togo|Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|Uganda|Ukraine|United Arab Emirates|United Kingdom|United States|Uruguay|Uzbekistan|Vanuatu|Vatican City|Venezuela|Vietnam|Yemen|Zambia|Zimbabwe".split("|")
from countrydle.local_answering import (
    POLISH_COUNTRY_ALIASES, COUNTRY_NAME_SYNONYMS,
    CONTINENT_ALIASES, SUBREGION_ALIASES, REGION_ALIASES,
)

_CANONICAL_COUNTRIES = {_norm(name): name for name in _COUNTRY_NAMES}
_CANONICAL_COUNTRIES.update({_norm(k): v for k, v in COUNTRY_NAME_SYNONYMS.items()})
_POLISH_COUNTRIES = {_norm(alias): name for alias, name in POLISH_COUNTRY_ALIASES.items()}
_COUNTRY_ALIASES = {**_CANONICAL_COUNTRIES, **_POLISH_COUNTRIES}
# The synonym catalog is bilingual; exclude its Polish-only spellings, not
# shared names/abbreviations such as Antigua, DRC, UK, USA and São Tomé.
_POLISH_ONLY_SYNONYMS = frozenset({
    "bosni", "bosnie", "bosnia i hercegowina",
    "demokratyczna republika konga", "drk", "republika konga",
})
_ENGLISH_COUNTRY_ALIASES = {
    alias: country for alias, country in _CANONICAL_COUNTRIES.items()
    if alias not in _POLISH_ONLY_SYNONYMS
}
_COUNTRY_PATTERN = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(alias) for alias in sorted(_COUNTRY_ALIASES, key=len, reverse=True)) + r")(?![a-z])"
)

_ENTITY_CONTINENTS = {_norm(value): value for value in CONTINENT_ALIASES.values()}
_ENTITY_AREAS = {
    _norm(alias): value for alias, value in (SUBREGION_ALIASES | REGION_ALIASES).items()
}
_ENTITY_AREAS.update({
    _norm(alias): canonical for canonical, aliases in AREAS.items() for alias in aliases
})
_ENTITY_UNIONS = {
    "eurasia": ("Europe", "Asia"),
    "americas": ("North America", "South America"),
}
_TARGET_SUBJECT_PREFIX = re.compile(
    r"^(is|does) (?:this country|the hidden country|hidden country) "
)
_LOCATIVE_PREFIX = re.compile(r"^(?:is (?:it|the country) in|in)\s+(?:the\s+)?(.+)$")
_IDENTITY_PREFIX = re.compile(r"^(?:is (?:it|the country|this)|it is|it's|it\s+is|this is)\s+(?:the\s+)?(.+)$", re.IGNORECASE)
_BARE_PREFIX = re.compile(r"^(?:the\s+)?(.+)$")
_AMBIGUOUS_ENTITIES = frozenset({"america", "ameryka", "ameryce", "congo", "kongo"})
_ENTITY_ACCENTS = frozenset(
    "\u0300\u0301\u0302\u0303\u0304\u0306\u0307\u0308\u030a\u030b\u030c"
    "\u031b\u0323\u0327\u0328"
)


def _normalized_english_question(question: str) -> str | None:
    if not isinstance(question, str):
        return None
    if not question.isascii():
        # Folding accents is safe; numeric letters and semantic overlays are not.
        if any(unicodedata.category(char) == "Nl" for char in question):
            return None
        if any(
            unicodedata.category(char).startswith("M") and char not in _ENTITY_ACCENTS
            for char in unicodedata.normalize("NFKD", question)
        ):
            return None
    text = " ".join(_norm(question).split()).rstrip(" ?!.")
    return _TARGET_SUBJECT_PREFIX.sub(r"\1 it ", text)


def compile_entity_question(question: str) -> tuple[dict, str] | None:
    """Resolve a whole English entity question without confusing location and identity."""
    text = _normalized_english_question(question)
    if not text:
        return None
    locative = _LOCATIVE_PREFIX.fullmatch(text)
    match = locative or _IDENTITY_PREFIX.fullmatch(text) or _BARE_PREFIX.fullmatch(text)
    if match is None:
        return None
    entity = match.group(1)
    if entity in _AMBIGUOUS_ENTITIES:
        return None
    if not locative:
        country = _ENGLISH_COUNTRY_ALIASES.get(entity)
        if country is not None:
            return _node("equals", "name", country), f"Is the country {country}?"
    union = _ENTITY_UNIONS.get(entity)
    if union is not None:
        return {
            "operator": "or",
            "conditions": [_node("contains", "continent", value) for value in union],
        }, f"Is the country in {'Eurasia' if union == ('Europe', 'Asia') else 'the Americas'}?"
    continent = _ENTITY_CONTINENTS.get(entity)
    if continent is not None:
        return _node("contains", "continent", continent), f"Is the country in {continent}?"
    area = _ENTITY_AREAS.get(entity)
    if area is not None:
        return _node("contains", "geographic_area", area), f"Is the country in {area}?"
    return None


def _clean_country_input(text: str) -> str:
    cleaned = re.sub(r"\bst\.\s*", "saint ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bst\s+", "saint ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<=\b[a-zA-Z])\.(?=[a-zA-Z](\.|\b))", "", cleaned).rstrip(".")
    return cleaned.strip()


def _country(text: str):
    raw = _norm(text.strip())
    cleaned = _norm(_clean_country_input(text))
    return (
        _POLISH_COUNTRIES.get(raw)
        or _CANONICAL_COUNTRIES.get(raw)
        or _POLISH_COUNTRIES.get(cleaned)
        or _CANONICAL_COUNTRIES.get(cleaned)
    )


def _country_in(text: str):
    match = _COUNTRY_PATTERN.search(text)
    if match is None:
        return None
    return _COUNTRY_ALIASES[match.group(0)]


def _direction(operator: str, country: str):
    relation = "coordinates.latitude" if operator in ("north_of", "south_of") else "coordinates.longitude"
    return {"operator": operator, "left": {**_TARGET, "relation": relation}, "right": {"entity": country, "relation": relation}}

def _parse_number_literal(text: str) -> float | int | None:
    m_dec = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(mld|miliard\w*|billion\w*|mln|milion\w*|million\w*|tys\w*|thousand\w*|k\b|m\b|b\b)", text)
    m_full = re.search(r"\b(\d{1,3}(?:[ ,]\d{3})+|\d+)\b(?:\s*(mld|miliard\w*|billion\w*|mln|milion\w*|million\w*|tys\w*|thousand\w*|k\b|m\b|b\b))?", text)
    m = m_dec if m_dec else m_full
    if not m:
        return None
    val_str, unit = m.groups()
    val_cleaned = val_str.replace(" ", "").replace(",", "") if not (unit and "," in val_str and len(val_str.split(",")[1]) != 3) else val_str.replace(",", ".")
    try:
        val = float(val_cleaned)
    except ValueError:
        return None
    mult = 1
    if unit:
        u = unit.lower()
        if any(u.startswith(p) for p in ("mld", "miliard", "billion", "b")):
            mult = 1_000_000_000
        elif any(u.startswith(p) for p in ("mln", "milion", "million", "m")):
            mult = 1_000_000
        elif any(u.startswith(p) for p in ("tys", "thousand", "k")):
            mult = 1_000
    res = val * mult
    return int(res) if res.is_integer() else res


_POLISH_DIACRITICS = frozenset("ąćęłńóśźż")
_POLISH_PREFIX = re.compile(
    r"^(?:czy|nad|pod|na|po|w|we|z|ze|od|lezy|jest|ma|posiada|znajduje|"
    r"graniczy|sasiaduje|nalezy|nalezal|nalezala|nalezalo|byl|byla|bylo|"
    r"ten|to|ta|kraj|panstwo|wyspa|wyspiarskie|srodladowe|ruch|jezyk|jezykiem|"
    r"flaga|fladze|populacja|powierzchnia|stolica)\b"
)
_POLISH_BARE_ENTITIES = frozenset(
    norm_pl(name)
    for name in (
        *POLISH_COUNTRY_ALIASES.keys(),
        "Europa", "Azja", "Afryka", "Ameryka Północna", "Ameryka Południowa", "Oceania",
        "Eurasia", "Eurazja", "Ameryki",
        "Bałkany", "Kraje Bałtyckie", "Europa Środkowa", "Europa Wschodnia",
        "Europa Zachodnia", "Europa Północna", "Europa Południowa", "Skandynawia",
        "Półwysep Iberyjski", "Bliski Wschód", "Półwysep Arabski", "Indochiny",
    )
)


def _is_polish_question(question: str) -> bool:
    if not isinstance(question, str) or not question.strip():
        return False
    if set(question.casefold()) & _POLISH_DIACRITICS:
        return True
    norm = norm_pl(question)
    if _POLISH_PREFIX.match(norm):
        return True
    if norm in _POLISH_BARE_ENTITIES:
        return True
    return False
_UNHANDLED_ENGLISH = re.compile(
    r"\b(?:and|or|not|never|neither|nor|but|except|without|ever|former|formerly|past)\b|[<>-]"
)
_WATER_ALIASES = {
    _norm(alias).removeprefix("the "): canonical
    for canonical, aliases in WATERS.items() for alias in aliases
}

_ENGLISH_TARGET_SUBJECTS = frozenset({
    "it", "the country", "this country", "the hidden country", "hidden country",
})
_COUNTRY_COMPARISON_OPERATORS = {
    "greater": "greater_than", "larger": "greater_than", "higher": "greater_than",
    "less": "less_than", "smaller": "less_than", "lower": "less_than",
}
_SHARED_CONTINENTS = (*CONTINENTS, "Antarctica")
_ENGLISH_CONTINENTS = {continent.casefold(): continent for continent in _SHARED_CONTINENTS}

_LITERAL_COMPARISONS = {
    "greater than": "greater_than", "more than": "greater_than",
    "larger than": "greater_than", "higher than": "greater_than",
    "over": "greater_than", "above": "greater_than",
    "less than": "less_than", "fewer than": "less_than",
    "smaller than": "less_than", "lower than": "less_than",
    "under": "less_than", "below": "less_than",
    "at least": "greater_than_or_equal", "at most": "less_than_or_equal",
    "equal to": "equals", "exactly": "equals",
}
_NUMBER_SCALE_EXPONENTS = {"thousand": 3, "k": 3, "million": 6, "m": 6, "billion": 9, "b": 9}
_LITERAL_COMPARISON_PATTERN = "|".join(_LITERAL_COMPARISONS)
_NUMERIC_FACT_QUESTION = re.compile(
    r"(?:does (?:it|the country) have (?:an? )?|is (?:its|the) )"
    r"(?P<relation>population|area) "
    rf"(?P<comparison>{_LITERAL_COMPARISON_PATTERN}) "
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?: ?(?P<scale>thousand|million|billion|k|m|b))?"
    r"(?: ?(?P<unit>people|inhabitants|km2|sq km|square kilometres|square kilometers))?"
)
_POPULATION_PEOPLE_QUESTION = re.compile(
    r"(?:does (?:it|the country) have )"
    rf"(?P<comparison>{_LITERAL_COMPARISON_PATTERN}) "
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?: ?(?P<scale>thousand|million|billion|k|m|b))? "
    r"(?P<unit>inhabitants|people|citizens)"
)
_NAME_PATTERN_QUESTION = re.compile(
    r"^(?:does (?:(?:it|the country)(?:['\u2019]s)?|its|the)(?: name)? )"
    r"(?P<op>end with|end in|contain|start with) "
    r"[\"'\u201c\u201d]?-?(?P<val>[a-zA-Z]+)[\"'\u201c\u201d]?$",
    re.IGNORECASE,
)
_CAPITAL_TEXT = r"(?:its|the|(?:the|this) country['\u2019]s) capital(?: name)?"
_CAPITAL_LENGTH_QUESTION = re.compile(
    rf"is {_CAPITAL_TEXT} (?P<comparison>longer than|shorter than) "
    r"(?P<number>\d+) letters?"
)
_CAPITAL_LETTERS_QUESTION = re.compile(
    rf"does {_CAPITAL_TEXT} have (?P<comparison>{_LITERAL_COMPARISON_PATTERN}) "
    r"(?P<number>\d+) letters?"
)


def _english_number(number: str, scale: str | None) -> int | float | None:
    whole, _, fraction = number.replace(",", "").partition(".")
    coefficient = int(whole + fraction)
    exponent = _NUMBER_SCALE_EXPONENTS.get(scale, 0)
    power = len(fraction) - exponent
    try:
        if power <= 0:
            value = coefficient * 10 ** -power
        else:
            divisor = 10 ** power
            quotient, remainder = divmod(coefficient, divisor)
            value = quotient if remainder == 0 else coefficient / divisor
        return value if isfinite(value) else None
    except OverflowError:
        return None


def _compile_english_numeric_question(question: str) -> tuple[list[dict], str] | None:
    match = _NUMERIC_FACT_QUESTION.fullmatch(question)
    if match is not None:
        relation, unit = match["relation"], match["unit"]
        if unit is not None and (unit in {"people", "inhabitants"}) != (relation == "population"):
            return None
        value = _english_number(match["number"], match["scale"])
        if value is None:
            return None
        operator = _LITERAL_COMPARISONS[match["comparison"]]
        suffix = " km²" if relation == "area" else ""
        return [_node(operator, relation, value)], (
            f"Is the country's {relation} {match['comparison']} {value:,}{suffix}?"
        )
    match_people = _POPULATION_PEOPLE_QUESTION.fullmatch(question)
    if match_people is not None:
        value = _english_number(match_people["number"], match_people["scale"])
        if value is not None:
            operator = _LITERAL_COMPARISONS[match_people["comparison"]]
            return [_node(operator, "population", value)], (
                f"Is the country's population {match_people['comparison']} {value:,}?"
            )
    match_name = _NAME_PATTERN_QUESTION.fullmatch(question)
    if match_name is not None:
        op_raw = match_name["op"]
        val = match_name["val"]
        if op_raw in {"end with", "end in"}:
            op = "ends_with"
            desc = f"Does the country name end with “{val}”?"
        elif op_raw == "start with":
            op = "starts_with"
            desc = f"Does the country name start with “{val}”?"
        else:
            op = "contains_text"
            desc = f"Does the country name contain “{val}”?"
        return [_node(op, "name", val)], desc
    match = _CAPITAL_LENGTH_QUESTION.fullmatch(question) or _CAPITAL_LETTERS_QUESTION.fullmatch(question)
    if match is None:
        return None
    comparison = match["comparison"]
    if comparison == "longer than":
        comparison = "greater than"
    elif comparison == "shorter than":
        comparison = "less than"
    operator, value = _LITERAL_COMPARISONS[comparison], int(match["number"])
    if operator in {"greater_than_or_equal", "less_than_or_equal"}:
        opposite = "less_than" if operator == "greater_than_or_equal" else "greater_than"
        nodes = [_node(f"char_count_{opposite}", "capital", value), {"operator": "not", "args": [0]}]
    else:
        nodes = [_node(f"char_count_{operator}", "capital", value)]
    return nodes, f"Does the capital name have {comparison} {value} letters?"


def _english_reference_country(match: re.Match | None) -> str | None:
    if match is None:
        return None
    subject = match["subject"]
    if subject not in _ENGLISH_TARGET_SUBJECTS and (
        subject in _AMBIGUOUS_ENTITIES or subject not in _ENGLISH_COUNTRY_ALIASES
    ):
        return None
    reference = match["country"]
    return None if reference in _AMBIGUOUS_ENTITIES else _ENGLISH_COUNTRY_ALIASES.get(reference)


_SUBJECT_AUXILIARY = re.compile(
    r"^\s*(?P<verb>does|do|did|is|are|was|were|has|have|had|can|could|will|would|should|must|may|might|"
    r"can['\u2019]t|cannot|won['\u2019]t)(?:n['\u2019]t)?\s+", re.IGNORECASE,
)
_COUNTRY_ALIAS_WORD_LIMIT = max(len(alias.split()) for alias in _ENGLISH_COUNTRY_ALIASES)
_COPULAR_COUNTRY_PREDICATES = frozenset({
    "a", "an", "the", "in", "on", "at", "from", "north", "south", "east", "west",
    "larger", "smaller", "bigger", "greater", "less", "more", "lower", "higher",
    "coastal", "landlocked", "located", "situated", "surrounded", "bordered",
    "connected", "known", "called", "governed", "controlled", "divided",
})
_VERBAL_COUNTRY_PREDICATES = frozenset({
    "have", "had", "been", "be", "border", "share", "belong", "contain", "speak",
    "use", "lie", "include", "cross", "straddle", "start", "end", "exist", "rank",
    "consist", "host", "join", "joined", "win", "produce", "export", "import",
    "touch", "neighbor", "neighbour", "recognize", "maintain", "follow", "possess",
    "allow", "require", "rely", "support", "drive", "make", "hold", "participate",
    "occupy", "extend", "stretch", "adjoin", "surround", "face",
})
_COUNTRY_PREDICATE_MODIFIERS = frozenset({
    "not", "never", "ever", "only", "entirely", "completely", "fully", "mostly",
    "partly", "currently", "formerly", "previously", "already", "still", "once",
})


def _bind_named_country_subject(question: str | None) -> str | None:
    """Bind an exact leading English country subject without changing its predicate."""
    if question is None or (auxiliary := _SUBJECT_AUXILIARY.match(question)) is None:
        return question
    start = auxiliary.end()
    country_start = start
    article = re.match(r"the\s+", question[start:], re.IGNORECASE)
    if article is not None:
        country_start += article.end()
    country_end = None
    for index, token in enumerate(re.finditer(r"\S+", question[country_start:])):
        if index >= _COUNTRY_ALIAS_WORD_LIMIT:
            break
        candidate = " ".join(_norm(question[country_start:country_start + token.end()]).split())
        if candidate in _ENGLISH_COUNTRY_ALIASES and candidate not in _AMBIGUOUS_ENTITIES:
            country_end = country_start + token.end()
    if country_end is None:
        return question
    rest = question[country_end:]
    following = re.match(r"\s+(\w+)", rest)
    predicates = (
        _COPULAR_COUNTRY_PREDICATES if _norm(auxiliary["verb"]) in {"is", "are", "was", "were"}
        else _VERBAL_COUNTRY_PREDICATES
    )
    if following is None:
        return question
    first = _norm(following[1])
    if first not in predicates and first not in _COUNTRY_PREDICATE_MODIFIERS:
        return question
    return question[:start] + "the country" + rest


def compile_template_plan(
    question: str, *, english_only: bool = False,
) -> tuple[list[dict], str] | None:
    """Compile fully covered English skeletons; retain the separate Polish path."""
    if not isinstance(question, str) or not question.strip():
        return None
    # The active planner must not newly activate legacy Polish compilation.
    if _is_polish_question(question):
        return None if english_only else _compile_polish_template_plan(question)
    q = _normalized_english_question(question)
    if not q:
        return None
    entity = compile_entity_question(question)
    if entity is not None:
        node, wording = entity
        return [node], wording
    continent_border = re.fullmatch(
        r"does (?P<subject>[a-z0-9 '\u2019&.]+?) (?P<negative>not )?"
        r"(?:touch|border) (?:the (?:continent of )?)?(?P<continent>[a-z ]+)",
        _bind_named_country_subject(q),
    )
    if continent_border is not None and continent_border["subject"] in _ENGLISH_TARGET_SUBJECTS:
        continent = _ENGLISH_CONTINENTS.get(continent_border["continent"])
        if continent is not None:
            nodes = [
                {"operator": "contains", "left": {"entity": "item", "relation": "continent"},
                 "right": {"value": continent}},
                {"operator": "any", "items": {**_TARGET, "relation": "borders_country"}, "args": [0]},
            ]
            negative = continent_border["negative"] is not None
            if negative:
                nodes.append({"operator": "not", "args": [1]})
            return nodes, f"Does the country {'not ' if negative else ''}have a land border with a country in {continent}?"
    numeric = _compile_english_numeric_question(q)
    if numeric is not None:
        return numeric
    if _UNHANDLED_ENGLISH.search(q):
        return None
    comparison = re.fullmatch(
        r"does (?P<subject>[a-z0-9 '\u2019&.]+) have (?:a )?"
        r"(?P<relation>population|area) (?P<comparison>greater|larger|higher|less|smaller|lower) "
        r"than (?P<country>[a-z0-9 '\u2019&.]+)", q,
    )
    country = _english_reference_country(comparison)
    if country is not None:
        relation = comparison["relation"]
        operator = _COUNTRY_COMPARISON_OPERATORS[comparison["comparison"]]
        return [{
            "operator": operator,
            "left": {**_TARGET, "relation": relation},
            "right": {"entity": country, "relation": relation},
        }], f"Does the country have a {relation} {comparison['comparison']} than {country}?"
    direction = re.fullmatch(
        r"is (?P<subject>[a-z0-9 '\u2019&.]+) (?:(?:farther|further) )?"
        r"(?P<direction>north|south|east|west) (?:of|than) (?P<country>[a-z0-9 '\u2019&.]+)", q,
    )
    country = _english_reference_country(direction)
    if country is not None:
        compass = direction["direction"]
        return [_direction(f"{compass}_of", country)], f"Is the country {compass} of {country}?"
    shared = re.fullmatch(
        r"does (?P<subject>[a-z0-9 '\u2019&.]+) "
        r"(?:share (?:a|any) continent with|have (?:a|any) continent in common with) "
        r"(?P<country>[a-z0-9 '\u2019&.]+)", q,
    )
    country = _english_reference_country(shared)
    if country is not None:
        # List intersection uses supported predicates, never continent-valued country items.
        nodes, branches = [], []
        for continent in _SHARED_CONTINENTS:
            first = len(nodes)
            nodes.extend([
                _node("contains", "continent", continent),
                {"operator": "contains", "left": {"entity": country, "relation": "continent"},
                 "right": {"value": continent}},
                {"operator": "and", "args": [first, first + 1]},
            ])
            branches.append(first + 2)
        nodes.append({"operator": "or", "args": branches})
        return nodes, f"Does the country share a continent with {country}?"
    border = re.fullmatch(
        r"does (?:it|the country) border (?:the country\s+)?(?P<country>[a-z0-9 '\u2019&.-]+)", q,
    )
    if border is not None:
        reference = border["country"]
        if reference in _AMBIGUOUS_ENTITIES:
            return None
        country = _ENGLISH_COUNTRY_ALIASES.get(reference)
        if country is not None:
            return [_node("contains", "borders_country", country)], f"Does the country border {country}?"
    if re.fullmatch(r"(?:is (?:it|the country) an island(?: country)?|is island)", q):
        return [_node("equals", "is_island", True)], "Is the country an island country?"
    if re.fullmatch(
        r"(?:does (?:it|the country) have (?:a )?coastline|has coast|has sea|is (?:it )?coastal)", q,
    ):
        return [_node("exists", "water_access")], "Does the country have a coastline?"
    if re.fullmatch(r"is (?:it|the country) landlocked", q):
        return [_node("exists", "marine_access"), {"operator": "not", "args": [0]}], "Is the country landlocked?"
    hemisphere = re.fullmatch(
        r"is (?:it|the country) in the (?P<hemi>northern|southern|eastern|western) hemisphere", q,
    )
    if hemisphere is not None:
        hemi = hemisphere["hemi"].capitalize()
        return [_node("contains", "hemisphere", hemi)], f"Is the country in the {hemi} Hemisphere?"
    if re.fullmatch(r"does (?:it|the country) (?:cross|straddle) the equator", q):
        return [
            _node("contains", "hemisphere", "Northern"),
            _node("contains", "hemisphere", "Southern"),
            {"operator": "and", "args": [0, 1]},
        ], "Does the country cross the equator?"
    equator = re.fullmatch(r"is (?:it|the country) (?P<direction>north|south) of the equator", q)
    if equator is not None:
        direction = equator["direction"]
        hemi = "Northern" if direction == "north" else "Southern"
        return [_node("contains", "hemisphere", hemi)], f"Is the country {direction} of the equator?"
    water = re.fullmatch(
        r"(?:does (?:it|the country) (?:border|have access to) (?:the )?(?P<water>[a-z\s]+)"
        r"|is (?:it|the country) on the (?P<water2>[a-z\s]+))", q,
    )
    if water is not None:
        value = _WATER_ALIASES.get(water["water"] or water["water2"])
        if value is not None:
            return [_node("contains", "water_access", value)], f"Does the country have access to the {value}?"
    return None


def _expand_slot_map(base_map: dict[str, Any], reversible: bool = False) -> dict[str, Any]:
    expanded: dict[str, Any] = {}
    for phrase, val in base_map.items():
        expanded[norm_pl(phrase)] = val
        for f in expand_polish_phrase_forms(phrase, reversible=reversible):
            expanded[f] = val
    return expanded


_POLISH_BASE_HEMISPHERES = {
    "półkula północna": "Northern",
    "półkula południowa": "Southern",
    "półkula wschodnia": "Eastern",
    "półkula zachodnia": "Western",
}
_POLISH_HEMISPHERES = _expand_slot_map(_POLISH_BASE_HEMISPHERES)

_POLISH_BASE_CONTINENTS = {
    "Europa": "Europe",
    "Azja": "Asia",
    "Afryka": "Africa",
    "Ameryka Północna": "North America",
    "Ameryka Południowa": "South America",
    "Oceania": "Oceania",
}
_POLISH_CONTINENTS = _expand_slot_map(_POLISH_BASE_CONTINENTS)

_POLISH_BASE_UNIONS = {
    "Eurazja": ("Europe", "Asia"),
    "Ameryki": ("North America", "South America"),
}
_POLISH_UNIONS = _expand_slot_map(_POLISH_BASE_UNIONS)

_POLISH_BASE_REGIONS = {
    "Bałkany": "Balkans",
    "Kraj bałtycki": "Baltic states",
    "Kraje bałtyckie": "Baltic states",
    "Skandynawia": "Scandinavia",
    "Półwysep Iberyjski": "Iberia",
    "Iberia": "Iberia",
    "Bliski Wschód": "Middle East",
    "Półwysep Arabski": "Arabian Peninsula",
    "Indochiny": "Indochina",
    "Ameryka Środkowa": "Central America",
    "Karaiby": "Caribbean",
    "Maghreb": "Maghreb",
    "Sahel": "Sahel",
    "Róg Afryki": "Horn of Africa",
    "Europa Środkowa": "Central Europe",
    "Środkowa Europa": "Central Europe",
    "Europa Wschodnia": "Eastern Europe",
    "Wschodnia Europa": "Eastern Europe",
    "Europa Zachodnia": "Western Europe",
    "Zachodnia Europa": "Western Europe",
    "Europa Północna": "Northern Europe",
    "Północna Europa": "Northern Europe",
    "Europa Południowa": "Southern Europe",
    "Południowa Europa": "Southern Europe",
    "Azja Środkowa": "Central Asia",
    "Środkowa Azja": "Central Asia",
    "Azja Południowo-Wschodnia": "Southeast Asia",
    "Południowo-Wschodnia Azja": "Southeast Asia",
    "azja poludniowy wschodni": "Southeast Asia",
    "azja poludniowo wschodni": "Southeast Asia",
    "poludniowy wschodni azja": "Southeast Asia",
    "poludniowo wschodnia azja": "Southeast Asia",
    "azji poludniowo wschodniej": "Southeast Asia",
    "Azja Południowa": "South Asia",
    "Południowa Azja": "South Asia",
    "Azja Wschodnia": "East Asia",
    "Wschodnia Azja": "East Asia",
    "Azja Zachodnia": "Western Asia",
    "Zachodnia Azja": "Western Asia",
    "Afryka Północna": "Northern Africa",
    "Północna Afryka": "Northern Africa",
    "Afryka Południowa": "Southern Africa",
    "Południowa Afryka": "Southern Africa",
    "Afryka Zachodnia": "Western Africa",
    "Zachodnia Afryka": "Western Africa",
    "Afryka Wschodnia": "Eastern Africa",
    "Wschodnia Afryka": "Eastern Africa",
    "Afryka Środkowa": "Middle Africa",
    "Środkowa Afryka": "Middle Africa",
}
_POLISH_REGIONS = _expand_slot_map(_POLISH_BASE_REGIONS)

_POLISH_BASE_WATERS = {
    "Ocean Atlantycki": "Atlantic Ocean",
    "Atlantyk": "Atlantic Ocean",
    "Ocean Spokojny": "Pacific Ocean",
    "Pacyfik": "Pacific Ocean",
    "Ocean Arktyczny": "Arctic Ocean",
    "Ocean Indyjski": "Indian Ocean",
    "Ocean Południowy": "Southern Ocean",
    "Morze Bałtyckie": "Baltic Sea",
    "morze bałtycki": "Baltic Sea",
    "Bałtyk": "Baltic Sea",
    "Morze Śródziemne": "Mediterranean Sea",
    "morze śródziemny": "Mediterranean Sea",
    "Morze Czarne": "Black Sea",
    "morze czarny": "Black Sea",
    "Morze Północne": "North Sea",
    "morze północny": "North Sea",
    "Morze Czerwone": "Red Sea",
    "morze czerwony": "Red Sea",
    "Morze Karaibskie": "Caribbean Sea",
    "morze karaibski": "Caribbean Sea",
    "Morze Adriatyckie": "Adriatic Sea",
    "morze adriatycki": "Adriatic Sea",
    "Adriatyk": "Adriatic Sea",
    "Morze Marmara": "Sea of Marmara",
    "ocean atlantycki": "Atlantic Ocean",
    "ocean spokojny": "Pacific Ocean",
    "ocean arktyczny": "Arctic Ocean",
    "ocean indyjski": "Indian Ocean",
    "ocean południowy": "Southern Ocean",
}
_POLISH_WATERS = _expand_slot_map(_POLISH_BASE_WATERS, reversible=True)

_POLISH_BASE_MEMBERSHIPS = {
    "UE": "EU",
    "Unia Europejska": "EU",
    "NATO": "NATO",
    "ONZ": "UN",
    "Schengen": "Schengen",
    "Beneluks": "Benelux",
    "Benelux": "Benelux",
    "Unia Afrykańska": "African Union",
    "ASEAN": "ASEAN",
    "Commonwealth": "Commonwealth",
    "G7": "G7",
    "G20": "G20",
    "OECD": "OECD",
}
_POLISH_MEMBERSHIPS = _expand_slot_map(_POLISH_BASE_MEMBERSHIPS)

_POLISH_BASE_HISTORICAL = {
    "ZSRR": "USSR",
    "Związek Radziecki": "USSR",
    "Związek Sowiecki": "USSR",
    "Jugosławia": "Yugoslavia",
    "Układ Warszawski": "Warsaw Pact",
    "Pakt Warszawski": "Warsaw Pact",
    "Czechosłowacja": "Czechoslovakia",
    "Austro-Węgry": "Austro-Hungarian Empire",
    "austro wegry": "Austro-Hungarian Empire",
    "austro wegier": "Austro-Hungarian Empire",
    "austro wegrami": "Austro-Hungarian Empire",
    "Cesarstwo Austro-Węgierskie": "Austro-Hungarian Empire",
    "cesarstwo austro wegierski": "Austro-Hungarian Empire",
    "cesarstwa austro wegierskiego": "Austro-Hungarian Empire",
    "cesarstwo austro wegierskiego": "Austro-Hungarian Empire",
    "Imperium Osmańskie": "Ottoman Empire",
    "Imperium Brytyjskie": "British Empire",
    "Imperium Hiszpańskie": "Spanish Empire",
    "Imperium Francuskie": "French Empire",
    "Imperium Portugalskie": "Portuguese Empire",
    "Wielka Kolumbia": "Gran Colombia",
}
_POLISH_HISTORICAL = _expand_slot_map(_POLISH_BASE_HISTORICAL)

_POLISH_BASE_LANGUAGES = {
    "angielski": "English",
    "polski": "Polish",
    "hiszpański": "Spanish",
    "francuski": "French",
    "niemiecki": "German",
    "arabski": "Arabic",
    "rosyjski": "Russian",
    "portugalski": "Portuguese",
    "chiński": "Chinese",
    "włoski": "Italian",
    "japoński": "Japanese",
    "niderlandzki": "Dutch",
    "holenderski": "Dutch",
    "grecki": "Greek",
    "turecki": "Turkish",
    "suahili": "Swahili",
    "swahili": "Swahili",
}
_POLISH_LANGUAGES = _expand_slot_map(_POLISH_BASE_LANGUAGES)

_POLISH_BASE_COLORS = {
    "czerwony": "red",
    "biały": "white",
    "niebieski": "blue",
    "zielony": "green",
    "żółty": "yellow",
    "czarny": "black",
    "pomarańczowy": "orange",
}
_POLISH_COLORS = _expand_slot_map(_POLISH_BASE_COLORS)

_POLISH_BASE_SYMBOLS = {
    "gwiazda": "star",
    "krzyż": "cross",
    "półksiężyc": "crescent",
    "słońce": "sun",
    "pasy": "stripes",
    "koło": "circle",
    "orzeł": "eagle",
    "herb": "coat_of_arms",
}
_POLISH_SYMBOLS = _expand_slot_map(_POLISH_BASE_SYMBOLS)

_AMBIGUOUS_COUNTRY_LEMMAS = frozenset({
    "ameryka", "ameryce", "ameryki", "kongo", "konga", "nigerie", "nigeriem",
})

def _build_polish_country_lemma_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for alias, canonical in POLISH_COUNTRY_ALIASES.items():
        n = norm_pl(alias)
        if n not in _AMBIGUOUS_COUNTRY_LEMMAS:
            mapping[n] = canonical
        for form in expand_polish_phrase_forms(alias, reversible=False):
            if form not in _AMBIGUOUS_COUNTRY_LEMMAS:
                mapping[form] = canonical
    for name in _CANONICAL_COUNTRIES.values():
        n = norm_pl(name)
        if n not in _AMBIGUOUS_COUNTRY_LEMMAS:
            mapping[n] = name
        for form in expand_polish_phrase_forms(name, reversible=False):
            if form not in _AMBIGUOUS_COUNTRY_LEMMAS:
                mapping[form] = name
    for k, v in COUNTRY_NAME_SYNONYMS.items():
        n = norm_pl(k)
        if n not in _AMBIGUOUS_COUNTRY_LEMMAS:
            mapping[n] = v
    return mapping

_POLISH_COUNTRY_LEMMAS = _build_polish_country_lemma_map()

_POLISH_DIRECTION_CONTINENT_AREAS: dict[tuple[str, str], str] = {
    ("polnocny", "Europe"): "Northern Europe",
    ("poludniowy", "Europe"): "Southern Europe",
    ("wschodni", "Europe"): "Eastern Europe",
    ("zachodni", "Europe"): "Western Europe",
    ("srodkowy", "Europe"): "Central Europe",
    ("polnocny", "Africa"): "Northern Africa",
    ("poludniowy", "Africa"): "Southern Africa",
    ("wschodni", "Africa"): "Eastern Africa",
    ("zachodni", "Africa"): "Western Africa",
    ("srodkowy", "Africa"): "Middle Africa",
    ("wschodni", "Asia"): "East Asia",
    ("poludniowy", "Asia"): "South Asia",
    ("zachodni", "Asia"): "Western Asia",
    ("srodkowy", "Asia"): "Central Asia",
}


def _extract_single_polish_number(norm_q: str) -> tuple[str, float | int | None] | None:
    # Standardize area unit representations while keeping bare km distinct
    norm_q = re.sub(r"\bkilometrow kwadratowych\b", "km2", norm_q)
    norm_q = re.sub(r"\bkm\s*2\b", "km2", norm_q)

    number_pattern = re.compile(
        r"\b\d+(?:[.,]\d+)?(?:\s*(?:mld|miliard\w*|billion\w*|mln|milion\w*|million\w*|tys\w*|thousand\w*|k\b|m\b|b\b))?\b"
    )
    matches = list(number_pattern.finditer(norm_q))
    if len(matches) > 1:
        return None
    if len(matches) == 1:
        m = matches[0]
        val = _parse_number_literal(m.group(0))
        if val is None:
            return None
        q_with_num = norm_q[:m.start()] + "[NUM]" + norm_q[m.end():]
        q_with_num = re.sub(r"\s+", " ", q_with_num).strip()
        return q_with_num, val
    return norm_q, None


def _make_slot_matcher(mapping: dict[str, Any], tag: str):
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    if not sorted_keys:
        return lambda clause: (clause, None)
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in sorted_keys) + r")\b")

    def substitute(clause: str) -> tuple[str, Any | None] | None:
        matches = list(pattern.finditer(clause))
        if len(matches) > 1:
            return None
        if len(matches) == 1:
            m = matches[0]
            val = mapping[m.group(0)]
            new_clause = clause[:m.start()] + tag + clause[m.end():]
            new_clause = re.sub(r"\s+", " ", new_clause).strip()
            return new_clause, val
        return clause, None

    return substitute


_MATCH_REGION = _make_slot_matcher(_POLISH_REGIONS, "[REGION]")
_MATCH_UNION = _make_slot_matcher(_POLISH_UNIONS, "[UNION]")
_MATCH_CONT = _make_slot_matcher(_POLISH_CONTINENTS, "[CONT]")
_MATCH_WATER = _make_slot_matcher(_POLISH_WATERS, "[WATER]")
_MATCH_HEMI = _make_slot_matcher(_POLISH_HEMISPHERES, "[HEMI]")
_MATCH_MEM = _make_slot_matcher(_POLISH_MEMBERSHIPS, "[MEM]")
_MATCH_HIST = _make_slot_matcher(_POLISH_HISTORICAL, "[HIST]")
_MATCH_LANG = _make_slot_matcher(_POLISH_LANGUAGES, "[LANG]")
_MATCH_COLOR = _make_slot_matcher(_POLISH_COLORS, "[COLOR]")
_MATCH_SYMBOL = _make_slot_matcher(_POLISH_SYMBOLS, "[SYMBOL]")
_MATCH_COUNTRY = _make_slot_matcher(_POLISH_COUNTRY_LEMMAS, "[COUNTRY]")


def _substitute_polish_slots(clause: str) -> tuple[str, dict[str, Any]] | None:
    slots: dict[str, Any] = {}

    res = _MATCH_REGION(clause)
    if res is None:
        return None
    clause, slots["REGION"] = res

    res = _MATCH_UNION(clause)
    if res is None:
        return None
    clause, slots["UNION"] = res

    res = _MATCH_CONT(clause)
    if res is None:
        return None
    clause, slots["CONT"] = res

    res = _MATCH_WATER(clause)
    if res is None:
        return None
    clause, slots["WATER"] = res

    res = _MATCH_HEMI(clause)
    if res is None:
        return None
    clause, slots["HEMI"] = res

    res = _MATCH_MEM(clause)
    if res is None:
        return None
    clause, slots["MEM"] = res

    res = _MATCH_HIST(clause)
    if res is None:
        return None
    clause, slots["HIST"] = res

    if any(k in clause for k in ("jezyk", "urzedowy")):
        res = _MATCH_LANG(clause)
        if res is None:
            return None
        clause, slots["LANG"] = res
    else:
        slots["LANG"] = None

    if any(k in clause for k in ("flaga", "kolor")):
        res = _MATCH_COLOR(clause)
        if res is None:
            return None
        clause, slots["COLOR"] = res
    else:
        slots["COLOR"] = None

    if any(k in clause for k in ("flaga", "symbol", "herb")):
        res = _MATCH_SYMBOL(clause)
        if res is None:
            return None
        clause, slots["SYMBOL"] = res
    else:
        slots["SYMBOL"] = None

    res = _MATCH_COUNTRY(clause)
    if res is None:
        return None
    clause, slots["COUNTRY"] = res

    return clause, slots


def _match_polish_canonical_skeletons(
    clause: str,
    slots: dict[str, Any],
    num: float | int | None,
) -> tuple[list[dict], str] | None:
    # 1. Identity
    if re.fullmatch(r"(?:byc )?\[COUNTRY\]", clause):
        country = slots.get("COUNTRY")
        if country:
            return [_node("equals", "name", country)], f"Is the country {country}?"

    # 2. Continent
    if re.fullmatch(r"(?:(?:lezec|byc) (?:w|na) |w |na )?\[CONT\]", clause):
        cont = slots.get("CONT")
        if cont:
            return [_node("contains", "continent", cont)], f"Is the country in {cont}?"

    # 3. Continent union
    if re.fullmatch(r"(?:(?:lezec|byc) (?:w|na) |w |na )?\[UNION\]", clause):
        union = slots.get("UNION")
        if union:
            ast = [
                _node("contains", "continent", union[0]),
                _node("contains", "continent", union[1]),
                {"operator": "or", "args": [0, 1]},
            ]
            wording = f"Is the country in {'Eurasia' if union == ('Europe', 'Asia') else 'the Americas'}?"
            return ast, wording

    # 4. Geographic area / subregion
    if re.fullmatch(r"(?:(?:lezec|byc) (?:w|na) |w |na )?\[REGION\]", clause):
        reg = slots.get("REGION")
        if reg:
            return [_node("contains", "geographic_area", reg)], f"Is the country in {reg}?"

    m_dir_cont = re.fullmatch(r"(?:(?:lezec|byc) (?:w|na) |w |na )?(?P<dir>polnocny|poludniowy|wschodni|zachodni|srodkowy) czesc \[CONT\]", clause)
    if m_dir_cont:
        cont = slots.get("CONT")
        dir_word = m_dir_cont.group("dir")
        area = _POLISH_DIRECTION_CONTINENT_AREAS.get((dir_word, cont))
        if area and area in AREAS:
            return [_node("contains", "geographic_area", area)], f"Is the country in {area}?"
        return None

    # 5. Hemisphere
    if re.fullmatch(r"(?:(?:lezec|byc) )?(?:calkowicie |w calosci |tylko )na \[HEMI\]", clause):
        hemi = slots.get("HEMI")
        if hemi:
            opposite = {"Northern": "Southern", "Southern": "Northern", "Eastern": "Western", "Western": "Eastern"}[hemi]
            ast = [
                _node("contains", "hemisphere", hemi),
                _node("contains", "hemisphere", opposite),
                {"operator": "not", "args": [1]},
                {"operator": "and", "args": [0, 2]},
            ]
            return ast, f"Is the country entirely in the {hemi} Hemisphere?"

    if re.fullmatch(r"(?:(?:lezec|byc) na |na )?\[HEMI\]", clause):
        hemi = slots.get("HEMI")
        if hemi:
            return [_node("contains", "hemisphere", hemi)], f"Is the country in the {hemi} Hemisphere?"

    # 6. Equator & Prime Meridian
    if re.fullmatch(r"(?:przecinac rownik|(?:lezec|byc) na rownik|na rownik)", clause):
        ast = [
            _node("contains", "hemisphere", "Northern"),
            _node("contains", "hemisphere", "Southern"),
            {"operator": "and", "args": [0, 1]},
        ]
        return ast, "Does the country cross the equator?"

    if re.fullmatch(r"(?:(?:lezec|byc) )?(?:na polnoc od rownik|nad rownik|powyzej rownik)", clause):
        return [_node("contains", "hemisphere", "Northern")], "Is the country north of the equator?"

    if re.fullmatch(r"(?:(?:lezec|byc) )?(?:na poludnie od rownik|pod rownik|ponizej rownik)", clause):
        return [_node("contains", "hemisphere", "Southern")], "Is the country south of the equator?"

    if re.fullmatch(r"(?:przecinac poludnik (?:greenwich|zerowy)|(?:lezec|byc) na poludnik (?:greenwich|zerowy)|na poludnik (?:greenwich|zerowy))", clause):
        ast = [
            _node("contains", "hemisphere", "Eastern"),
            _node("contains", "hemisphere", "Western"),
            {"operator": "and", "args": [0, 1]},
        ]
        return ast, "Does the country cross the prime meridian?"

    if re.fullmatch(r"(?:(?:lezec|byc) )?na wschod od (?:poludnik )?(?:greenwich|zerowy)", clause):
        return [_node("contains", "hemisphere", "Eastern")], "Is the country east of the prime meridian?"

    if re.fullmatch(r"(?:(?:lezec|byc) )?na zachod od (?:poludnik )?(?:greenwich|zerowy)", clause):
        return [_node("contains", "hemisphere", "Western")], "Is the country west of the prime meridian?"

    # 7. Country borders
    if re.fullmatch(r"(?:graniczyc z \[COUNTRY\]|z \[COUNTRY\] graniczyc|\[COUNTRY\] graniczyc)", clause):
        country = slots.get("COUNTRY")
        if country:
            return [_node("contains", "borders_country", country)], f"Does the country border {country}?"

    # 8. Relative directions
    m_dir = re.fullmatch(r"(?:(?:lezec|byc) )?(?:na (?P<dir>polnoc|poludnie|wschod|zachod|lewo|prawo) od|po (?P<side>lewy|prawy) strona od|(?P<rel>nad|pod|powyzej|ponizej|wyzej niz|nizej niz)) \[COUNTRY\]", clause)
    if m_dir:
        country = slots.get("COUNTRY")
        if country:
            d = m_dir.group("dir") or m_dir.group("rel") or m_dir.group("side")
            if d in ("polnoc", "nad", "powyzej", "wyzej niz"):
                op = "north_of"
            elif d in ("poludnie", "pod", "ponizej", "nizej niz"):
                op = "south_of"
            elif d in ("wschod", "prawo", "prawy"):
                op = "east_of"
            else:
                op = "west_of"
            return [_direction(op, country)], f"Is the country {op[:-3]} of {country}?"

    m_diag = re.fullmatch(r"(?:(?:lezec|byc) )?na (?P<d1>polnocny|poludniowy) (?P<d2>wschod|zachod) od \[COUNTRY\]", clause)
    if m_diag:
        country = slots.get("COUNTRY")
        if country:
            d1 = m_diag.group("d1")
            d2 = m_diag.group("d2")
            d1_op = "north_of" if d1 == "polnocny" else "south_of"
            d2_op = "east_of" if d2 == "wschod" else "west_of"
            ast = [
                _direction(d1_op, country),
                _direction(d2_op, country),
                {"operator": "and", "args": [0, 1]},
            ]
            d1_lbl = "north" if d1 == "polnocny" else "south"
            d2_lbl = "east" if d2 == "wschod" else "west"
            return ast, f"Is the country {d1_lbl}-{d2_lbl} of {country}?"

    # 9. Coastline, ocean, named water body, landlocked, island
    if re.fullmatch(r"(?:miec dostep do morze(?: lub ocean)?|miec wybrzeze|(?:lezec|byc) nad morze|graniczyc z morze|(?:byc )?nadmorski)", clause):
        return [_node("exists", "water_access")], "Does the country have access to the sea?"

    if re.fullmatch(r"(?:miec dostep do ocean|(?:lezec|byc) nad ocean|graniczyc z ocean)", clause):
        return [_node("contains", "water_access", "Ocean")], "Does the country have access to the ocean?"

    if re.fullmatch(r"(?:miec dostep do (?:ocean )?\[WATER\]|(?:lezec|byc) nad \[WATER\]|graniczyc z \[WATER\])", clause):
        water = slots.get("WATER")
        if water:
            return [_node("contains", "water_access", water)], f"Does the country have access to the {water}?"

    if re.fullmatch(r"(?:(?:byc )?srodladowy|brak dostep do morze|nie miec dostep do morze)", clause):
        return [_node("exists", "marine_access"), {"operator": "not", "args": [0]}], "Is the country landlocked?"

    if re.fullmatch(r"(?:(?:byc )?(?:wyspa|wyspiarski)|archipelag)", clause):
        return [_node("equals", "is_island", True)], "Is the country an island?"

    # 10. Population & area numeric and country comparisons
    m_num_pop = re.fullmatch(
        r"(?:miec (?P<op>ponad|powyzej|wiecej niz|ponizej|mniej niz|co najmniej|co najwyzej) \[NUM\] mieszkaniec"
        r"|populacja (?:byc )?(?P<op2>wiekszy niz|mniejszy niz|ponad|powyzej|ponizej|co najmniej|co najwyzej) \[NUM\](?: mieszkaniec)?"
        r"|miec populacja (?P<op3>wiekszy niz|mniejszy niz|ponad|powyzej|ponizej) \[NUM\](?: mieszkaniec)?)",
        clause,
    )
    if m_num_pop and num is not None:
        op_str = m_num_pop.group("op") or m_num_pop.group("op2") or m_num_pop.group("op3")
        op = "greater_than" if any(k in op_str for k in ("wiecej", "wiekszy", "ponad", "powyzej", "co najmniej")) else "less_than"
        ast = [{
            "operator": op,
            "left": {**_TARGET, "relation": "population"},
            "right": {"value": num},
        }]
        return ast, f"Is the population {op.replace('_', ' ')} {num}?"

    m_country_pop = re.fullmatch(
        r"(?:miec (?P<op>wiecej|mniej) mieszkaniec (?:niz|od) \[COUNTRY\]"
        r"|miec (?P<op2>wiekszy|mniejszy) populacja (?:niz|od) \[COUNTRY\]"
        r"|populacja (?:byc )?(?P<op3>wiekszy|mniejszy) (?:niz|od) \[COUNTRY\])",
        clause,
    )
    if m_country_pop:
        country = slots.get("COUNTRY")
        if country:
            op_str = m_country_pop.group("op") or m_country_pop.group("op2") or m_country_pop.group("op3")
            op = "greater_than" if any(k in op_str for k in ("wiecej", "wiekszy")) else "less_than"
            ast = [{
                "operator": op,
                "left": {**_TARGET, "relation": "population"},
                "right": {"entity": country, "relation": "population"},
            }]
            return ast, f"Is the population of the country {op.replace('_', ' ')} that of {country}?"

    m_num_area = re.fullmatch(
        r"(?:powierzchnia (?:byc )?(?P<op>wiekszy niz|mniejszy niz|ponad|powyzej|ponizej|co najmniej|co najwyzej) \[NUM\] km2"
        r"|miec powierzchnia (?P<op2>wiekszy niz|mniejszy niz|ponad|powyzej|ponizej) \[NUM\] km2"
        r"|miec (?P<op3>ponad|powyzej|wiecej niz|ponizej|mniej niz) \[NUM\] km2(?: powierzchnia)?)",
        clause,
    )
    if m_num_area and num is not None:
        op_str = m_num_area.group("op") or m_num_area.group("op2") or m_num_area.group("op3")
        op = "greater_than" if any(k in op_str for k in ("wiecej", "wiekszy", "ponad", "powyzej", "co najmniej")) else "less_than"
        ast = [{
            "operator": op,
            "left": {**_TARGET, "relation": "area"},
            "right": {"value": num},
        }]
        return ast, f"Is the area {op.replace('_', ' ')} {num}?"

    m_country_area = re.fullmatch(
        r"(?:byc (?P<op>wiekszy|mniejszy) (?:niz|od) \[COUNTRY\]"
        r"|(?:miec )?powierzchnia (?:byc )?(?P<op2>wiekszy|mniejszy) (?:niz|od) \[COUNTRY\]"
        r"|byc (?P<op3>wiekszy|mniejszy) powierzchnia (?:niz|od) \[COUNTRY\])",
        clause,
    )
    if m_country_area:
        country = slots.get("COUNTRY")
        if country:
            op_str = m_country_area.group("op") or m_country_area.group("op2") or m_country_area.group("op3")
            op = "greater_than" if "wiekszy" in op_str else "less_than"
            ast = [{
                "operator": op,
                "left": {**_TARGET, "relation": "area"},
                "right": {"entity": country, "relation": "area"},
            }]
            return ast, f"Is the area of the country {op.replace('_', ' ')} that of {country}?"

    # 11. Driving side, government, membership, historical union, language, flag, hyphen, words
    m_side = re.fullmatch(r"(?:byc )?ruch (?:byc )?(?P<side>lewostronny|prawostronny)", clause)
    if m_side:
        side = "left" if m_side.group("side") == "lewostronny" else "right"
        return [_node("equals", "driving_side", side)], f"Does the country drive on the {side}?"

    m_gov = re.fullmatch(r"(?:byc )?(?P<gov>monarchia|republika)", clause)
    if m_gov:
        gov = "Monarchy" if m_gov.group("gov") == "monarchia" else "Republic"
        return [_node("equals", "government_type", gov)], f"Is the country a {gov.lower()}?"

    if re.fullmatch(r"(?:nalezec do \[MEM\]|byc (?:w|czlonkiem) \[MEM\])", clause):
        mem = slots.get("MEM")
        if mem:
            return [_node("contains", "membership", mem)], f"Is the country in {mem}?"

    if re.fullmatch(r"(?:nalezec_past do \[HIST\]|bylo_past (?:w|czesc) \[HIST\])", clause):
        hist = slots.get("HIST")
        if hist:
            return [_node("contains", "historical_union", hist)], f"Was the country historically part of {hist}?"

    if re.fullmatch(r"(?:jezyk urzedowy (?:byc|to) \[LANG\]|\[LANG\] (?:byc|to) jezyk urzedowy|miec \[LANG\] jako jezyk urzedowy)", clause):
        lang = slots.get("LANG")
        if lang:
            return [_node("contains", "official_language", lang)], f"Is {lang} an official language?"

    m_color = re.fullmatch(r"(?:miec (?:kolor )?\[COLOR\](?: kolor)? na flaga|na flaga byc (?:kolor )?\[COLOR\]|flaga miec (?:kolor )?\[COLOR\](?: kolor)?|flaga byc \[COLOR\])", clause)
    if m_color:
        color = slots.get("COLOR")
        if color:
            return [_node("contains", "flag_color", color)], f"Does the country's flag contain {color}?"

    m_symbol = re.fullmatch(r"(?:miec \[SYMBOL\] na flaga|na flaga byc \[SYMBOL\]|flaga miec \[SYMBOL\])", clause)
    if m_symbol:
        symbol = slots.get("SYMBOL")
        if symbol:
            return [_node("contains", "flag_symbol", symbol)], f"Does the country's flag contain {symbol}?"

    if re.fullmatch(r"(?:nazwa miec myslnik|miec myslnik w nazwa)", clause):
        return [_node("has_hyphen", "name")], "Does the country name have a hyphen?"

    if re.fullmatch(r"(?:nazwa byc dwuczlonowy|byc dwuczlonowy)", clause):
        return [{"operator": "word_count_equals", "left": {**_TARGET, "relation": "name"}, "right": {"value": 2}}], "Does the country name have 2 words?"

    return None


def _compile_polish_template_plan(question: str) -> tuple[list[dict], str] | None:
    """Compile Polish natural language questions via whole-sentence canonical skeletons."""
    if not isinstance(question, str) or not question.strip():
        return None
    if "/" in question or "\\" in question:
        return None

    norm_q = norm_pl(question)

    # Step 3a: Check re.fullmatch for Polish name-pattern queries
    m_name = re.fullmatch(
        r"(?:czy )?(?:nazwa (?:tego )?(?:kraju|panstwa) |(?:ten |to )?(?:kraj|panstwo) |nazwa )?"
        r"(?P<op>konczy sie na|zaczyna sie (?:od|na)|ma w nazwie|zawiera(?: w nazwie)?)"
        r"(?: liter[eay]| sylab[eay]| koncowk[eai])? [\"'\u201c\u201d]?-?(?P<val>[a-z]+)[\"'\u201c\u201d]?",
        norm_q,
    )
    if m_name is not None:
        op_raw = m_name.group("op")
        val = m_name.group("val")
        if "konczy" in op_raw:
            op = "ends_with"
            desc = f"Does the country name end with “{val}”?"
        elif "zaczyna" in op_raw:
            op = "starts_with"
            desc = f"Does the country name start with “{val}”?"
        else:
            op = "contains_text"
            desc = f"Does the country name contain “{val}”?"
        return [_node(op, "name", val)], desc

    # Step 3b: Check match_slot_template
    from slot_template_engine import match_slot_template
    slot_res = match_slot_template(question, "countrydle")
    if slot_res is not None:
        return slot_res

    # Step 3c & 3d: Canonicalize clause then extract at most one numeric literal ([NUM])
    clause = canonicalize_pl_clause(norm_q, target_nouns=("kraj", "panstwo"))
    if not clause:
        return None

    num_res = _extract_single_polish_number(clause)
    if num_res is None:
        return None
    clause, extracted_num = num_res

    # Step 3e: Substitute single slots
    slot_res = _substitute_polish_slots(clause)
    if slot_res is None:
        return None
    clause, extracted_slots = slot_res

    # Step 3f: Match canonicalized clause against exact whole-sentence skeletons
    return _match_polish_canonical_skeletons(clause, extracted_slots, extracted_num)

def check_open_ended_question(question: str) -> str | None:
    """Detect open-ended questions about supported attributes that require a yes/no rephrasing."""
    if not isinstance(question, str) or not question.strip():
        return None
    q = _norm(question)
    if (
        re.search(r"\b(?:which|what)\s+side\b.*\b(?:drive|road|car|traffic|street)\b", q)
        or re.search(r"\b(?:drive|road|car|traffic|street)\b.*\b(?:which|what)\s+side\b", q)
        or re.search(r"\b(?:which|what)\s+side\s+do\s+they\s+drive\b", q)
    ):
        return "Please ask a yes/no question about the driving side, for example: 'Does it drive on the right?' or 'Does it drive on the left?'."
    if re.search(r"\bpo\s+kt[oó]rej\s+stronie\b", q) and any(
        term in q for term in ("drog", "ulic", "jezd", "jech", "ruch", "samochod")
    ):
        return "Proszę zadać pytanie rozstrzygnięcia (Tak/Nie) o stronę ruchu, np. 'Czy ruch jest prawostronny?' lub 'Czy ruch jest lewostronny?'."
    return None
