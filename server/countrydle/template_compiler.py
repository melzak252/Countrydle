"""Deterministic in-memory compiler for common single-intent geography questions."""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

from slot_template_engine import match_slot_template

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
_LOCATIVE_PREFIX = re.compile(r"^(?:is (?:it|the country) in|in)\s+(?:the\s+)?(.+)$")
_IDENTITY_PREFIX = re.compile(r"^(?:is (?:it|the country|this))\s+(?:the\s+)?(.+)$")
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
    return " ".join(_norm(question).split()).rstrip(" ?!.")


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
    continent = _ENTITY_CONTINENTS.get(entity)
    if continent is not None:
        return _node("contains", "continent", continent), f"Is the country in {continent}?"
    area = _ENTITY_AREAS.get(entity)
    union = _ENTITY_UNIONS.get(entity)
    if area is not None and union is None:
        return _node("contains", "geographic_area", area), f"Is the country in {area}?"
    if union is not None:
        return {
            "operator": "or",
            "conditions": [_node("contains", "continent", value) for value in union],
        }, f"Is the country in {'Eurasia' if union == ('Europe', 'Asia') else 'the Americas'}?"
    # Country containment has no local relation: let the model preserve that intent.
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


_POLISH_PREFIX = re.compile(r"^(?:czy|nad|pod|na|po|lezy|jest|ma|panstwo|kraj|graniczy)\b")
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
    if _POLISH_PREFIX.match(_norm(question).lstrip()):
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


def _compile_polish_template_plan(question: str) -> tuple[list[dict], str] | None:
    """Existing Polish behavior, intentionally outside the English cutover."""
    if not isinstance(question, str) or not question.strip():
        return None
    if "/" in question or "\\" in question:
        return None
    slot_res = match_slot_template(question, "countrydle")
    if slot_res is not None:
        return slot_res
    q = _norm(question)
    diagonal = re.search(r"\b(north[- ]west|north[- ]east|south[- ]west|south[- ]east|northwest|northeast|southwest|southeast)\b", q)
    logical = re.search(r"\b(and|or|i|lub|neither|nor|ani|not|brak)\b", q)
    if logical:
        country_match = _COUNTRY_PATTERN.search(q)
        if country_match is None or any(
            match.start() < country_match.start() or match.end() > country_match.end()
            for match in re.finditer(r"\b(and|or|i|lub|neither|nor|ani|not|brak)\b", q)
        ):
            return None
    if any(term in q for term in ("sea level", "poziom morza", "poziomu morza", "away from", "daleko od")):
        return None
    location = re.search(r"\b(?:in|w)\s+(?:the\s+)?", q)
    if location and _COUNTRY_PATTERN.match(q, location.end()):
        return None
    if any(term in q for term in ("border", "borders", "neighbor", "neighbour", "graniczy", "granic")):
        country = _country_in(q)
        if country:
            return [_node("contains", "borders_country", country)], f"Does the country border {country}?"

    if diagonal:
        country = _country_in(q)
        if country:
            directions = diagonal.group(1).replace("-", " ").replace("northwest", "north west").replace("northeast", "north east").replace("southwest", "south west").replace("southeast", "south east").split()
            ast = [_direction({"north": "north_of", "south": "south_of", "west": "west_of", "east": "east_of"}[d], country) for d in directions]
            ast.append({"operator": "and", "args": [0, 1]})
            return ast, f"Is the country {directions[0]}-{directions[1]} of {country}?"

    is_pop = any(term in q for term in ("population", "inhabitants", "people")) or bool(re.search(r"\bpop\b", q))
    is_area = any(term in q for term in ("area", "sq km", "km2", "km 2", "square km", "square kilometer")) or bool(re.search(r"\bkm\b", q))
    is_greater = any(term in q for term in (
        "greater", "larger", "bigger", "more than", "more people", "more inhabitants", "more ",
        "over", "above", "exceed", "exceeds"
    ))
    is_less = any(term in q for term in (
        "less", "smaller", "fewer", "under", "below"
    ))
    if is_pop and (is_greater or is_less):
        op = "greater_than" if is_greater else "less_than"
        country = _country_in(q)
        if country:
            return [{
                "operator": op,
                "left": {**_TARGET, "relation": "population"},
                "right": {"entity": country, "relation": "population"},
            }], f"Is the population of the country {op.replace('_', ' ')} that of {country}?"
        num = _parse_number_literal(q)
        if num is not None:
            return [{
                "operator": op,
                "left": {**_TARGET, "relation": "population"},
                "right": {"value": num},
            }], f"Is the population {op.replace('_', ' ')} {num}?"

    if is_area and (is_greater or is_less):
        op = "greater_than" if is_greater else "less_than"
        country = _country_in(q)
        if country:
            return [{
                "operator": op,
                "left": {**_TARGET, "relation": "area"},
                "right": {"entity": country, "relation": "area"},
            }], f"Is the area of the country {op.replace('_', ' ')} that of {country}?"
        num = _parse_number_literal(q)
        if num is not None:
            return [{
                "operator": op,
                "left": {**_TARGET, "relation": "area"},
                "right": {"value": num},
            }], f"Is the area {op.replace('_', ' ')} {num}?"

    if not is_pop and (is_greater or is_less):
        country = _country_in(q)
        if country and any(term in q for term in ("bigger", "larger", "smaller", "wiekszy", "mniejszy", "wieksza", "mniejsza")):
            op = "greater_than" if is_greater else "less_than"
            return [{
                "operator": op,
                "left": {**_TARGET, "relation": "area"},
                "right": {"entity": country, "relation": "area"},
            }], f"Is the area of the country {op.replace('_', ' ')} that of {country}?"

    identity = re.search(r"\b(?:is it|is this|czy to|czy jest to|is|it)\s+([a-z0-9 '\u2019&.-]+?)\s*[?!.]*$", q)
    if identity:
        candidate = identity.group(1).strip()
        if not candidate.startswith(("in ", "a ", "an ")):
            check_name = candidate[4:].strip() if candidate.startswith("the ") else candidate
            country = _country(check_name) or _country(candidate)
            if country:
                return [_node("equals", "name", country)], f"Is the country {country}?"

    is_entirely = any(term in q for term in ("entirely", "completely", "fully", "calkowicie", "w calosci", "tylko na polkuli", "only in the"))
    hemi_mapping = (
        (("northern hemisphere", "north hemisphere", "polkuli polnocnej", "polkula polnocna"), "Northern", "Southern"),
        (("southern hemisphere", "south hemisphere", "polkuli poludniowej", "polkula poludniowa"), "Southern", "Northern"),
        (("eastern hemisphere", "east hemisphere", "polkuli wschodniej", "polkula wschodnia"), "Eastern", "Western"),
        (("western hemisphere", "west hemisphere", "polkuli zachodniej", "polkula zachodnia"), "Western", "Eastern"),
    )
    for phrases, target_hemi, opposite_hemi in hemi_mapping:
        if any(phrase in q for phrase in phrases):
            if is_entirely:
                ast = [
                    _node("contains", "hemisphere", target_hemi),
                    _node("contains", "hemisphere", opposite_hemi),
                    {"operator": "not", "args": [1]},
                    {"operator": "and", "args": [0, 2]},
                ]
                return ast, f"Is the country entirely in the {target_hemi} Hemisphere?"
            else:
                return [_node("contains", "hemisphere", target_hemi)], f"Is the country in the {target_hemi} Hemisphere?"

    equator_crossing_phrases = (
        "cross the equator", "crosses the equator", "crossing the equator",
        "crosses equator", "cross equator",
        "on the equator", "on equator",
        "straddle the equator", "straddles the equator",
        "przecina rownik", "przecina ten rownik", "lezy na rowniku", "na rowniku",
    )
    if any(phrase in q for phrase in equator_crossing_phrases):
        ast = [
            _node("contains", "hemisphere", "Northern"),
            _node("contains", "hemisphere", "Southern"),
            {"operator": "and", "args": [0, 1]},
        ]
        return ast, "Does the country cross the equator?"

    equator_rules = (
        (
            (
                "north of the equator", "north of equator", "north to the equator", "north to equator",
                "above the equator", "above equator",
                "nad rownikiem", "powyzej rownika", "na polnoc od rownika",
            ),
            "Northern",
            "north of the equator",
        ),
        (
            (
                "south of the equator", "south of equator", "south to the equator", "south to equator",
                "below the equator", "below equator",
                "pod rownikiem", "ponizej rownika", "na poludnie od rownika",
            ),
            "Southern",
            "south of the equator",
        ),
    )
    for phrases, hemi, wording in equator_rules:
        if any(phrase in q for phrase in phrases):
            return [_node("contains", "hemisphere", hemi)], f"Is the country {wording}?"

    prime_meridian_crossing_phrases = (
        "cross the prime meridian", "crosses the prime meridian", "crossing the prime meridian",
        "cross the greenwich meridian", "crosses the greenwich meridian",
        "cross the greenwich line", "crosses the greenwich line",
        "on the prime meridian", "on the greenwich meridian", "on the greenwich line",
        "przecina poludnik greenwich", "przecina poludnik zerowy",
        "lezy na poludniku greenwich", "lezy na poludniku zerowym",
        "na poludniku greenwich", "na poludniku zerowym",
    )
    if any(phrase in q for phrase in prime_meridian_crossing_phrases):
        ast = [
            _node("contains", "hemisphere", "Eastern"),
            _node("contains", "hemisphere", "Western"),
            {"operator": "and", "args": [0, 1]},
        ]
        return ast, "Does the country cross the prime meridian?"

    prime_meridian_rules = (
        (
            (
                "east of the prime meridian", "east of prime meridian", "east to the prime meridian", "east to prime meridian",
                "east of greenwich", "east to greenwich",
                "na wschod od poludnika greenwich", "na wschod od poludnika zerowego", "na wschod od greenwich",
            ),
            "Eastern",
            "east of the prime meridian",
        ),
        (
            (
                "west of the prime meridian", "west of prime meridian", "west to the prime meridian", "west to prime meridian",
                "west of greenwich", "west to greenwich",
                "na zachod od poludnika greenwich", "na zachod od poludnika zerowego", "na zachod od greenwich",
            ),
            "Western",
            "west of the prime meridian",
        ),
    )
    for phrases, hemi, wording in prime_meridian_rules:
        if any(phrase in q for phrase in phrases):
            return [_node("contains", "hemisphere", hemi)], f"Is the country {wording}?"
    direction_phrases = (
        ("north_of", ("north of", "north to", "above")),
        ("south_of", ("south of", "south to", "below")),
        ("west_of", ("west of", "west to", "to the left of", "left of", "left to")),
        ("east_of", ("east of", "east to", "to the right of", "right of", "right to")),
    )
    for operator, phrases in direction_phrases:
        if any(phrase in q for phrase in phrases):
            country = _country_in(q)
            return ([_direction(operator, country)], f"Is the country {operator[:-3]} of {country}?") if country else None

    if re.search(r"\b(landlocked|inland|srodladow\w*|no coastline|no access to (?:the )?(?:sea|ocean)|brak dostepu do morza|nie ma dostepu do morza)\b", q):
        return [_node("exists", "marine_access"), {"operator": "not", "args": [0]}], "Is the country landlocked?"
    if any(x in q for x in ("island", "wyspa", "wyspiarsk")) and not any(term in q for term in ("share", "shares", "dziel", "border", "borders", "sasied")):
        return [_node("equals", "is_island", True)], "Is the country an island?"
    is_directional_coast = bool(re.search(r"\b(west\w*|east\w*|north\w*|south\w*|zachod\w*|wschod\w*|polnoc\w*|poludn\w*)\b.*?\b(coast|coastline|wybrzez\w*)\b", q))
    water_body = _choices(WATERS, q) if not is_directional_coast else None
    if not is_directional_coast:
        if any(x in q for x in ("coastline", "coast", "access to sea", "access sea", "access to the sea", "has sea", "have sea", "has coast", "have coast", "dostep do morza")):
            if water_body and water_body != "Sea":
                return [_node("contains", "water_access", water_body)], f"Does the country have access to the {water_body}?"
            after_sea = re.search(r"\b(?:morza|morze|sea)\s+([a-z]+)", q)
            if after_sea and after_sea.group(1) not in {"and", "or", "i", "lub", "oceanu", "ocean"}:
                return None
            return [_node("exists", "water_access")], "Does the country have access to the sea?"
        if any(x in q for x in ("has ocean", "have ocean", "access ocean", "access to ocean", "access to the ocean")):
            return [_node("contains", "water_access", "Ocean")], "Does the country have access to the ocean?"

    for relation, choices in (("geographic_area", AREAS), ("continent", CONTINENTS), ("membership", MEMBERSHIPS), ("historical_union", HISTORICAL)):
        if relation == "continent":
            if re.search(r"\b(north\w*|south\w*|east\w*|west\w*|central\w*|middle\w*|polnoc\w*|poludn\w*|wschod\w*|zachod\w*|srodk\w*|centraln\w*)\b", q):
                if not any(continent in q for continent in ("north america", "south america", "ameryka polnocna", "ameryce polnocnej", "ameryka poludniowa", "ameryce poludniowej")):
                    continue
        value = _choices(choices, q)
        if value and any(x in q for x in (
            "in ", " in the ", "in the", "lezy", "nalezy", "nalezal", "nalezala", "nalezaly", "nalezalo",
            "part of", "member", "join", "joined", "belong", "belongs", "czlonkiem", " w ", "na ", "kraj", "panstwo", "z ",
            "czescia", "czesc", "sklad", "wchodzil", "wchodzila", "wchodzilo",
            "on te ", "on the ", "part of ",
        )):
            if relation == "membership":
                if any(x in q for x in ("founding", "founder", "zaloz", "założ", "original", "pierwotn", "when", "kiedy", "accession", "akcesj")):
                    continue
                if re.search(r"\b(19\d\d|20\d\d)\b", q):
                    continue
            wording = f"Was the country historically part of {value}?" if relation == "historical_union" else f"Is the country in {value}?"
            return [_node("contains", relation, value)], wording
    if water_body and water_body != "Sea" and not is_directional_coast and any(x in q for x in ("access", "coast", "border", "dostep", "wybrze", "ma ")):
        return [_node("contains", "water_access", water_body)], f"Does the country have access to the {water_body}?"


    if any(x in q for x in ("left-driving", "drive on the left", "drive on left", "drive left", "drives left", "drives on left", "left drive", "left side of the road")):
        return [_node("equals", "driving_side", "left")], "Does the country drive on the left?"
    if any(x in q for x in ("right-driving", "drive on the right", "drive on right", "drive right", "drives right", "drives on right", "right drive", "right side of the road")):
        return [_node("equals", "driving_side", "right")], "Does the country drive on the right?"
    if any(x in q for x in ("monarchy", "monarch", "monarchia")) and not any(m in q for m in ("absolute", "absolutn", "constitutional", "konstytucyjn")):
        return [_node("equals", "government_type", "Monarchy")], "Is the country a monarchy?"
    if any(x in q for x in ("republic", "republika")):
        return [_node("equals", "government_type", "Republic")], "Is the country a republic?"

    if "flag" in q or "flaga" in q or "fladze" in q:
        colors = {"red": ("red", "czerwony", "czerwona", "czerwone"), "white": ("white", "biały", "biała", "białe"), "blue": ("blue", "niebieski", "niebieska"), "green": ("green", "zielony", "zielona"), "yellow": ("yellow", "żółty", "żółta"), "black": ("black", "czarny", "czarna"), "orange": ("orange", "pomarańczowy", "pomarańczowa")}
        value = _choices(colors, q)
        relation = "flag_color"
        if value is None:
            symbols = {"star": ("star", "stars", "gwiazda", "gwiazdę", "gwiazdy"), "cross": ("cross", "krzyż"), "crescent": ("crescent", "półksiężyc"), "sun": ("sun", "słońce"), "stripes": ("stripes", "pasy"), "circle": ("circle", "koło"), "eagle": ("eagle", "orzeł"), "coat_of_arms": ("coat of arms", "herb")}
            value = _choices(symbols, q)
            relation = "flag_symbol"
        return ([_node("contains", relation, value)], f"Does the country's flag contain {value}?") if value else None

    if any(x in q for x in ("official language", "official languages", "jezyk urzedowy", "jezykiem urzedowym", "language", "speak", "speaks", "jezyk")):
        languages = {"English": ("english", "angielski", "angielskim"), "Polish": ("polish", "polski", "polskim"), "Spanish": ("spanish", "hiszpański", "hiszpańskim"), "French": ("french", "francuski", "francuskim"), "German": ("german", "niemiecki", "niemieckim"), "Arabic": ("arabic", "arabski", "arabskim"), "Russian": ("russian", "rosyjski", "rosyjskim"), "Portuguese": ("portuguese", "portugalski", "portugalskim"), "Chinese": ("chinese", "chiński", "chińskim"), "Italian": ("italian", "włoski", "włoskim"), "Japanese": ("japanese", "japoński", "japońskim"), "Dutch": ("dutch", "niderlandzki", "holenderski"), "Greek": ("greek", "grecki", "greckim"), "Turkish": ("turkish", "turecki", "tureckim"), "Swahili": ("swahili",)}
        language = _choices(languages, q)
        return ([_node("contains", "official_language", language)], f"Is {language} an official language?") if language else None
    return None

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
