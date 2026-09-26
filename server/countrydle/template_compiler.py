"""Deterministic in-memory compiler for common single-intent geography questions."""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

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
    "Balkans": ("Balkans", "Bałkany", "Bałkanach", "Bałkanów"), "Middle East": ("Middle East", "Bliski Wschód", "Bliskim Wschodzie"),
    "Scandinavia": ("Scandinavia", "Skandynawia", "Skandynawii"), "Caribbean": ("Caribbean", "Karaiby", "Karaibach"),
    "Baltic states": ("Baltic states", "państwa bałtyckie", "krajach bałtyckich"), "Central Europe": ("Central Europe", "Europa Środkowa", "Europie Środkowej"),
    "Eastern Europe": ("Eastern Europe", "Eastern Europe", "Europa Wschodnia", "Europie Wschodniej"), "Western Europe": ("Western Europe", "Europa Zachodnia", "Europie Zachodniej"),
    "Northern Europe": ("Northern Europe", "Europa Północna", "Europie Północnej"), "Southern Europe": ("Southern Europe", "Europa Południowa", "Europie Południowej"),
    "Maghreb": ("Maghreb",), "Sahel": ("Sahel",), "Horn of Africa": ("Horn of Africa", "Róg Afryki"),
    "Arabian Peninsula": ("Arabian Peninsula", "Półwysep Arabski"), "Indochina": ("Indochina", "Indochiny"),
    "Central Asia": ("Central Asia", "Azja Środkowa", "Azji Środkowej"), "Southeast Asia": ("Southeast Asia", "Azja Południowo-Wschodnia"),
    "South Asia": ("South Asia", "Azja Południowa"), "East Asia": ("East Asia", "Azja Wschodnia"),
}
MEMBERSHIPS = {
    "EU": ("EU", "UE", "European Union", "Unia Europejska"), "NATO": ("NATO",), "UN": ("UN", "ONZ", "United Nations", "Narody Zjednoczone"),
    "Schengen": ("Schengen", "Strefa Schengen"), "Benelux": ("Benelux",), "African Union": ("African Union", "Unia Afrykańska"),
    "ASEAN": ("ASEAN",), "Commonwealth": ("Commonwealth", "Wspólnota Narodów"), "G7": ("G7",), "G20": ("G20",), "OECD": ("OECD",),
}
HISTORICAL = {
    "USSR": ("USSR", "ZSRR", "Soviet Union", "Związek Radziecki"), "Yugoslavia": ("Yugoslavia", "Jugosławia", "Jugosławii"),
    "Warsaw Pact": ("Warsaw Pact", "Układ Warszawski"), "Czechoslovakia": ("Czechoslovakia", "Czechosłowacja", "Czechosłowacji"),
    "Austro-Hungarian Empire": ("Austro-Hungarian Empire", "Austro-Węgry", "Monarchia Austro-Węgierska"),
    "Ottoman Empire": ("Ottoman Empire", "Imperium Osmańskie"), "British Empire": ("British Empire", "Imperium Brytyjskie"),
    "Spanish Empire": ("Spanish Empire", "Imperium Hiszpańskie"), "French Empire": ("French Empire", "Imperium Francuskie"),
    "Portuguese Empire": ("Portuguese Empire", "Imperium Portugalskie"),
}
WATERS = {
    "Ocean": ("ocean", "oceanem", "oceanu"), "Sea": ("sea", "morze", "morzem"), "Baltic Sea": ("Baltic Sea", "Bałtyk", "Bałtyku", "Morze Bałtyckie"),
    "Mediterranean Sea": ("Mediterranean Sea", "Morze Śródziemne"), "Black Sea": ("Black Sea", "Morze Czarne", "Morza Czarnego"),
    "North Sea": ("North Sea", "Morze Północne"), "Red Sea": ("Red Sea", "Morze Czerwone"), "Caribbean Sea": ("Caribbean Sea", "Morze Karaibskie"),
    "Indian Ocean": ("Indian Ocean", "Ocean Indyjski"), "Atlantic Ocean": ("Atlantic Ocean", "Ocean Atlantycki"),
    "Pacific Ocean": ("Pacific Ocean", "Ocean Spokojny"), "Arctic Ocean": ("Arctic Ocean", "Ocean Arktyczny"), "Adriatic Sea": ("Adriatic Sea", "Morze Adriatyckie"),
}

# Country names are canonicalized against the same 196-country facts catalog; common Polish inflections are explicit.
_COUNTRY_NAMES = "Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|Argentina|Armenia|Australia|Austria|Azerbaijan|Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|Bhutan|Bolivia|Bosnia and Herzegovina|Botswana|Brazil|Brunei|Bulgaria|Burkina Faso|Burundi|Cambodia|Cameroon|Canada|Cape Verde|Central African Republic|Chad|Chile|China|Colombia|Comoros|Costa Rica|Croatia|Cuba|Cyprus|Czech Republic|Democratic Republic of the Congo|Denmark|Djibouti|Dominica|Dominican Republic|East Timor|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|Eswatini|Ethiopia|Federated States of Micronesia|Fiji|Finland|France|Gabon|Gambia|Georgia|Germany|Ghana|Greece|Grenada|Guatemala|Guinea|Guinea-Bissau|Guyana|Haiti|Honduras|Hungary|Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|Italy|Ivory Coast|Jamaica|Japan|Jordan|Kazakhstan|Kenya|Kiribati|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|Lithuania|Luxembourg|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall Islands|Mauritania|Mauritius|Mexico|Moldova|Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|Namibia|Nauru|Nepal|Netherlands|New Zealand|Nicaragua|Niger|Nigeria|North Korea|North Macedonia|Norway|Oman|Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|Philippines|Poland|Portugal|Qatar|Republic of the Congo|Romania|Russia|Rwanda|Saint Kitts and Nevis|Saint Lucia|Saint Vincent and the Grenadines|Samoa|San Marino|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|South Korea|South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|Syria|São Tomé and Príncipe|Tajikistan|Tanzania|Thailand|Togo|Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|Uganda|Ukraine|United Arab Emirates|United Kingdom|United States|Uruguay|Uzbekistan|Vanuatu|Vatican City|Venezuela|Vietnam|Yemen|Zambia|Zimbabwe".split("|")
_POLISH_COUNTRIES = {
    "polska": "Poland", "polsce": "Poland", "polski": "Poland", "polską": "Poland", "niemcy": "Germany", "niemcami": "Germany", "niemiec": "Germany", "niemczech": "Germany",
    "francja": "France", "francji": "France", "włochy": "Italy", "włoch": "Italy", "hiszpania": "Spain", "hiszpanii": "Spain", "czechy": "Czech Republic", "czechami": "Czech Republic",
    "słowacja": "Slovakia", "słowacji": "Slovakia", "ukraina": "Ukraine", "ukrainy": "Ukraine", "białoruś": "Belarus", "białorusi": "Belarus", "litwa": "Lithuania", "litwy": "Lithuania",
    "rosja": "Russia", "rosji": "Russia", "dania": "Denmark", "danii": "Denmark", "szwecja": "Sweden", "szwecji": "Sweden", "norwegia": "Norway", "norwegii": "Norway",
    "finlandia": "Finland", "finlandii": "Finland", "holandia": "Netherlands", "holandii": "Netherlands", "niderlandy": "Netherlands", "belgia": "Belgium", "belgii": "Belgium",
    "luksemburg": "Luxembourg", "austria": "Austria", "austrii": "Austria", "szwajcaria": "Switzerland", "szwajcarii": "Switzerland", "portugalia": "Portugal", "portugalii": "Portugal",
    "grecja": "Greece", "grecji": "Greece", "turcja": "Turkey", "turcji": "Turkey", "chiny": "China", "chin": "China", "indie": "India", "indii": "India", "japonia": "Japan", "japonii": "Japan",
    "meksyk": "Mexico", "meksyku": "Mexico", "kanada": "Canada", "kanady": "Canada", "brazylia": "Brazil", "argentyna": "Argentina", "egipt": "Egypt", "egiptu": "Egypt", "izrael": "Israel", "iran": "Iran", "iranu": "Iran", "irak": "Iraq", "iraku": "Iraq",
    "wielka brytania": "United Kingdom", "wielkiej brytanii": "United Kingdom", "stany zjednoczone": "United States", "usa": "United States", "korea południowa": "South Korea",
}
_POLISH_COUNTRIES.update({
    "francją": "France", "włochami": "Italy", "hiszpanią": "Spain", "ukrainą": "Ukraine",
    "białorusią": "Belarus", "litwą": "Lithuania", "rosją": "Russia", "danią": "Denmark",
    "szwecją": "Sweden", "norwegią": "Norway", "finlandią": "Finland", "holandią": "Netherlands",
    "belgią": "Belgium", "austrią": "Austria", "szwajcarią": "Switzerland", "portugalią": "Portugal",
    "grecją": "Greece", "turcją": "Turkey", "chinami": "China", "indiami": "India", "japonią": "Japan",
    "meksykiem": "Mexico", "kanadą": "Canada", "brazylią": "Brazil", "argentyną": "Argentina",
    "egiptem": "Egypt", "izraelem": "Israel",
})
_POLISH_COUNTRIES = {_norm(alias): name for alias, name in _POLISH_COUNTRIES.items()}
_CANONICAL_COUNTRIES = {_norm(name): name for name in _COUNTRY_NAMES}
_CANONICAL_COUNTRIES["czechia"] = "Czech Republic"
_COUNTRY_ALIASES = {**_CANONICAL_COUNTRIES, **{_norm(alias): name for alias, name in _POLISH_COUNTRIES.items()}}
_COUNTRY_PATTERN = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(alias) for alias in sorted(_COUNTRY_ALIASES, key=len, reverse=True)) + r")(?![a-z])"
)


def _country(text: str):
    value = _norm(text.strip())
    return _POLISH_COUNTRIES.get(value) or _CANONICAL_COUNTRIES.get(value)


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


def compile_template_plan(question: str) -> tuple[list[dict], str] | None:
    """Compile a recognized question to ``(AST, improved English question)``."""
    if not isinstance(question, str) or not question.strip():
        return None
    q = _norm(question)
    diagonal = re.search(r"\b(north[- ]west|north[- ]east|south[- ]west|south[- ]east|northwest|northeast|southwest|southeast)\b", q)
    logical = re.search(r"\b(and|or|i|lub)\b", q)
    if logical:
        country_match = _COUNTRY_PATTERN.search(q)
        if country_match is None or any(
            match.start() < country_match.start() or match.end() > country_match.end()
            for match in re.finditer(r"\b(and|or|i|lub)\b", q)
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
        if not country:
            return None
        directions = diagonal.group(1).replace("-", " ").replace("northwest", "north west").replace("northeast", "north east").replace("southwest", "south west").replace("southeast", "south east").split()
        ast = [_direction({"north": "north_of", "south": "south_of", "west": "west_of", "east": "east_of"}[d], country) for d in directions]
        ast.append({"operator": "and", "args": [0, 1]})
        return ast, f"Is the country {directions[0]}-{directions[1]} of {country}?"

    is_pop = any(term in q for term in ("population", "populacj", "inhabitants", "mieszkanc", "ludnosc", "people", "ludzi")) or bool(re.search(r"\bpop\b", q))
    is_area = any(term in q for term in ("area", "powierzchni", "sq km", "km2", "km 2", "square km", "square kilometer", "kilometrow")) or bool(re.search(r"\bkm\b", q))
    is_greater = any(term in q for term in (
        "greater", "larger", "bigger", "more than", "more people", "more inhabitants", "more ",
        "over", "above", "exceed", "exceeds", "wieksz", "wiecej", "ponad", "powyzej", "przekracza"
    ))
    is_less = any(term in q for term in (
        "less", "smaller", "fewer", "under", "below", "mniejsz", "mniej", "ponizej"
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

    identity = re.search(r"\b(?:is it|is this|czy to|czy jest to|is|it)\s+([a-z -]+?)\s*[?!.]*$", q)
    if identity:
        candidate = identity.group(1).strip()
        if not candidate.startswith(("in ", "a ", "an ", "the ")):
            country = _country(candidate)
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

    equator_prime_rules = (
        (("north of the equator", "north of equator", "north to the equator", "north to equator", "na polnoc od rownika"), "greater_than", "coordinates.latitude", "north of the equator"),
        (("south of the equator", "south of equator", "south to the equator", "south to equator", "na poludnie od rownika"), "less_than", "coordinates.latitude", "south of the equator"),
        (("east of the prime meridian", "east of prime meridian", "east to the prime meridian", "east to prime meridian", "na wschod od poludnika greenwicha", "na wschod od poludnika zerowego"), "greater_than", "coordinates.longitude", "east of the prime meridian"),
        (("west of the prime meridian", "west of prime meridian", "west to the prime meridian", "west to prime meridian", "na zachod od poludnika greenwicha", "na zachod od poludnika zerowego", "poludnika greenwich"), "less_than", "coordinates.longitude", "west of the prime meridian"),
    )
    for phrases, op, relation, wording in equator_prime_rules:
        if any(phrase in q for phrase in phrases):
            return [_node(op, relation, 0)], f"Is the country {wording}?"
    direction_phrases = (
        ("north_of", ("north of", "north to", "above", "powyzej", "na polnoc od", "na polnoc do")),
        ("south_of", ("south of", "south to", "below", "ponizej", "na poludnie od", "na poludnie do")),
        ("west_of", ("west of", "west to", "to the left of", "left of", "left to", "na zachod od", "na lewo od", "na zachod do")),
        ("east_of", ("east of", "east to", "to the right of", "right of", "right to", "na wschod od", "na prawo od", "na wschod do")),
    )
    for operator, phrases in direction_phrases:
        if any(phrase in q for phrase in phrases):
            country = _country_in(q)
            return ([_direction(operator, country)], f"Is the country {operator[:-3]} of {country}?") if country else None

    if re.search(r"\b(landlocked|inland|srodladow\w*|no coastline|no access to (?:the )?(?:sea|ocean)|brak dostepu do morza|nie ma dostepu do morza)\b", q):
        return [_node("exists", "water_access"), {"operator": "not", "args": [0]}], "Is the country landlocked?"
    if any(x in q for x in ("island", "wyspa", "wyspiarsk")):
        return [_node("equals", "is_island", True)], "Is the country an island?"
    water_body = _choices(WATERS, q)
    if any(x in q for x in ("coastline", "coast", "access to sea", "access sea", "access to the sea", "has sea", "have sea", "has coast", "have coast", "dostep do morza", "linia brzegowa", "linie brzegowa")):
        if water_body and water_body != "Sea":
            return [_node("contains", "water_access", water_body)], f"Does the country have access to the {water_body}?"
        return [_node("exists", "water_access")], "Does the country have access to the sea?"
    if any(x in q for x in ("has ocean", "have ocean", "access ocean", "access to ocean", "access to the ocean")):
        return [_node("contains", "water_access", "Ocean")], "Does the country have access to the ocean?"

    for relation, choices in (("continent", CONTINENTS), ("geographic_area", AREAS), ("membership", MEMBERSHIPS), ("historical_union", HISTORICAL)):
        value = _choices(choices, q)
        if value and any(x in q for x in ("in ", " in the ", "in the", "lezy", "nalezy", "nalezalo", "part of", "member", "join", "joined", "belong", "belongs", "czlonkiem", " w ", "na ")):
            return [_node("contains", relation, value)], f"Is the country in {value}?"
    if water_body and water_body != "Sea" and any(x in q for x in ("access", "coast", "border", "dostep", "wybrze", "ma ")):
        return [_node("contains", "water_access", water_body)], f"Does the country have access to the {water_body}?"


    if any(x in q for x in ("left-driving", "drive on the left", "drive on left", "drive left", "drives left", "drives on left", "left drive", "left side of the road", "ruch lewostronny", "lewostronny")):
        return [_node("equals", "driving_side", "left")], "Does the country drive on the left?"
    if any(x in q for x in ("right-driving", "drive on the right", "drive on right", "drive right", "drives right", "drives on right", "right drive", "right side of the road", "ruch prawostronny", "prawostronny", "prawej stronie")):
        return [_node("equals", "driving_side", "right")], "Does the country drive on the right?"
    if any(x in q for x in ("monarchy", "monarch", "monarchia")):
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
        term in q for term in ("drog", "ulic", "jezd", "jech", "ruch", "samochod", "sie", "jest")
    ):
        return "Proszę zadać pytanie rozstrzygnięcia (Tak/Nie) o stronę ruchu, np. 'Czy ruch jest prawostronny?' lub 'Czy ruch jest lewostronny?'."
    return None
