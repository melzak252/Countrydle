"""Deterministic template compiler for Powiatdle, Wojewodztwodle, and US Statedle."""

from functools import lru_cache
import re
from typing import Any
import unicodedata

from polish_morphology import (
    canonicalize_pl_clause,
    expand_polish_phrase_forms,
    expand_polish_word_forms,
    norm_pl,
)
from slot_template_engine import (
    COUNTRIES_MAP,
    US_STATES_MAP,
    VOIVODESHIPS_MAP,
    build_us_state_water_plan,
    match_slot_template,
)



@lru_cache(maxsize=512)
def _resolve_unique_powiat(candidate: str) -> str | None:
    import sqlite3
    from local_kb_question import ROOT_DIR
    from powiat_names import resolve_powiat_name

    db_path = ROOT_DIR / "data" / "powiat_facts.sqlite"
    if not db_path.is_file():
        return None
    with sqlite3.connect(db_path) as conn:
        return resolve_powiat_name(conn, candidate)

@lru_cache(maxsize=1024)
def _norm(text: str) -> str:
    """Normalize Polish characters and accents, lowercase, strip punctuation."""
    folded = text.casefold().replace("ł", "l").replace("Ł", "l")
    normalized = unicodedata.normalize("NFKD", folded)
    cleaned = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# Neighboring countries of Poland with inflected forms
POLISH_NEIGHBOR_COUNTRIES = {
    "Niemcy": ("niemcy", "niemcami", "niemiec", "niemczech", "germany"),
    "Czechy": ("czechy", "czechami", "czech", "czechach", "czechia", "czech republic"),
    "Słowacja": ("slowacja", "slowacji", "slowacja", "slovakia"),
    "Ukraina": ("ukraina", "ukrainie", "ukrainy", "ukraine"),
    "Białoruś": ("bialorus", "bialorusia", "bialorusi", "belarus"),
    "Litwa": ("litwa", "litwie", "litwy", "lithuania"),
    "Rosja": ("rosja", "rosji", "obwodem krolewieckim", "obwodem kaliningradzkim", "krolewieckim", "kaliningradzkim", "russia"),
}

_NEIGHBOR_ENGLISH_NAMES = {
    "Niemcy": "Germany",
    "Czechy": "Czechia",
    "Słowacja": "Slovakia",
    "Ukraina": "Ukraine",
    "Białoruś": "Belarus",
    "Litwa": "Lithuania",
    "Rosja": "Russia",
}

# Major rivers in Poland
POLISH_MAJOR_RIVERS = {
    "Wisła": ("wisla", "wisly", "wisle", "vistula"),
    "Odra": ("odra", "odry", "odrze", "oder"),
    "Warta": ("warta", "warty", "warcie"),
    "Bug": ("bug", "bugu", "bugiem"),
    "Narew": ("narew", "narwi", "narwia"),
    "San": ("san", "sanu", "sanem"),
    "Noteć": ("notec", "noteci", "notecia"),
    "Pilica": ("pilica", "pilicy", "pilice"),
    "Bóbr": ("bobr", "bobra", "bobrem"),
    "Łyna": ("lyna", "lyny", "lynie"),
    "Drwęca": ("drweca", "drwecy", "drwece"),
}

_EXPANDED_POLISH_RIVERS: dict[str, str] = {}
for canonical, aliases in POLISH_MAJOR_RIVERS.items():
    _EXPANDED_POLISH_RIVERS[norm_pl(canonical)] = canonical
    for a in aliases:
        _EXPANDED_POLISH_RIVERS[norm_pl(a)] = canonical
        for f in expand_polish_word_forms(a):
            _EXPANDED_POLISH_RIVERS[f] = canonical

_EXPANDED_POLISH_NEIGHBORS: dict[str, str] = {}
for canonical, aliases in POLISH_NEIGHBOR_COUNTRIES.items():
    _EXPANDED_POLISH_NEIGHBORS[norm_pl(canonical)] = canonical
    for a in aliases:
        _EXPANDED_POLISH_NEIGHBORS[norm_pl(a)] = canonical
        for f in expand_polish_phrase_forms(a):
            _EXPANDED_POLISH_NEIGHBORS[f] = canonical


def _make_generic_slot_matcher(mapping: dict[str, Any], tag: str):
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


_MATCH_VOJ = _make_generic_slot_matcher(VOIVODESHIPS_MAP, "[VOJ]")
_MATCH_RIVER = _make_generic_slot_matcher(_EXPANDED_POLISH_RIVERS, "[RIVER]")
_MATCH_NEIGHBOR = _make_generic_slot_matcher(_EXPANDED_POLISH_NEIGHBORS, "[COUNTRY]")
_MATCH_US_STATE = _make_generic_slot_matcher(US_STATES_MAP, "[STATE]")
_MATCH_US_COUNTRY = _make_generic_slot_matcher(COUNTRIES_MAP, "[COUNTRY]")


def check_generic_open_ended_question(question: str) -> str | None:
    """Identify open-ended questions and return clarification message."""
    norm_q = _norm(question)
    open_ended = (
        r"\b(jaka jest|jaki jest|jakie jest|jaki to|jakie to|co to za|stolica|wojewodztwo|powiat)\b",
        r"\b(what is|which state|which county|what county|what capital)\b",
    )
    for pattern in open_ended:
        if re.search(pattern, norm_q):
            words = norm_q.split()
            if len(words) <= 5 and any(p in norm_q for p in ("jaka", "jaki", "jakie", "co to", "what", "which")):
                return "Please ask a yes/no question rather than an open-ended question."
    return None


def compile_powiatdle_template(question: str) -> tuple[dict[str, Any], str] | None:
    """Match high-frequency Powiatdle player questions into canonical AST."""
    norm_q = norm_pl(question)
    m_voiv_river_pl = re.fullmatch(
        r"(?:czy )?(?:przez )?wojewodztw(?:o|ie)(?: w ktorym (?:lezy|znajduje sie|jest)(?: ten powiat| powiat)?)? "
        r"(?:przeplywa|plynie|ma|posiada)(?: rzek[ae])? (?P<river>[a-z]+)"
        r"|(?:czy )?(?:rzeka )?(?P<river2>[a-z]+) (?:przeplywa|plynie) przez wojewodztwo w ktorym (?:lezy|znajduje sie|jest)(?: ten powiat| powiat)?",
        norm_q,
    )
    if m_voiv_river_pl:
        raw_r = m_voiv_river_pl.group("river") or m_voiv_river_pl.group("river2")
        r_name = _EXPANDED_POLISH_RIVERS.get(raw_r)
        if r_name:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "major_rivers"}, "right": {"value": r_name}},
                f"Does {r_name} flow through the voivodeship containing the county?",
            )

    norm_en_early = _norm(question)
    m_voiv_river_en = re.fullmatch(
        r"(?:does|is) (?:the )?(?:voivodeship|voidvoship|voivodship|province) (?:that |which |where )?(?:it|the county|this county) (?:lies|is|is located)(?: in)? "
        r"(?:have|contain) (?:the )?(?P<river>[a-z ]+?)(?: river)?(?: in it)?"
        r"|does (?:the )?(?P<river2>[a-z ]+?)(?: river)? flow through (?:the )?(?:voivodeship|voidvoship|voivodship|province) (?:that |which |where )?(?:it|the county|this county) (?:lies|is|is located)(?: in)?",
        norm_en_early,
    )
    if m_voiv_river_en:
        raw_r = (m_voiv_river_en.group("river") or m_voiv_river_en.group("river2") or "").strip()
        r_name = _EXPANDED_POLISH_RIVERS.get(raw_r)
        if r_name:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "major_rivers"}, "right": {"value": r_name}},
                f"Does {r_name} flow through the voivodeship containing the county?",
            )

    m_identity_en = re.fullmatch(
        r"is (?:it|this|the county) (?:(?P<p1>[a-z -]+?) (?:powiat|county)|(?:powiat|county) (?P<p2>[a-z -]+))",
        norm_en_early,
    )
    if m_identity_en:
        raw_p = (m_identity_en.group("p1") or m_identity_en.group("p2") or "").strip()
        if raw_p not in {"ziemski", "grodzki", "land", "city", "a land", "a city"}:
            resolved_p = _resolve_unique_powiat(raw_p)
            if resolved_p:
                return (
                    {"operator": "equals", "left": {"entity": "target_powiat", "relation": "name"}, "right": {"value": resolved_p}},
                    f"Is this {resolved_p}?",
                )

    m_identity_pl = re.fullmatch(
        r"(?:czy )?(?:to |ten powiat to )?(?:jest )?(?:powiat (?P<p1>[a-z -]+)|(?P<p2>[a-z -]+) powiat)",
        norm_q,
    )
    if m_identity_pl:
        raw_p = (m_identity_pl.group("p1") or m_identity_pl.group("p2") or "").strip()
        if raw_p not in {"ziemski", "grodzki"}:
            resolved_p = _resolve_unique_powiat(raw_p)
            if resolved_p:
                return (
                    {"operator": "equals", "left": {"entity": "target_powiat", "relation": "name"}, "right": {"value": resolved_p}},
                    f"Is this {resolved_p}?",
                )

    clause = canonicalize_pl_clause(question, target_nouns=("powiat",))
    if not clause:
        return None
    # Substitute slots (reject if multiple of same type)
    res = _MATCH_RIVER(clause)
    if res is None:
        return None
    clause, river = res

    res = _MATCH_NEIGHBOR(clause)
    if res is None:
        return None
    clause, country = res

    res = _MATCH_VOJ(clause)
    if res is None:
        return None
    clause, voj = res

    # 1. City county
    if re.fullmatch(r"(?:byc )?(?:miasto na prawach|grodzki)", clause):
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 1}},
            "Is the county a city county?",
        )

    # Land county
    if re.fullmatch(r"(?:byc )?(?:powiat )?ziemski", clause):
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 0}},
            "Is the county a land county?",
        )

    # 2. Registration plates length
    m_plate = re.fullmatch(
        r"(?:tablica (?:rejestracyjny )?miec (?P<n>2|3) litera"
        r"|miec (?P<n2>dwuliterowy|trzyliterowy) tablica(?: rejestracyjny)?"
        r"|tablica (?:byc )?(?P<n3>dwuliterowy|trzyliterowy))",
        clause,
    )
    if m_plate:
        n_val = 2 if (m_plate.group("n") == "2" or m_plate.group("n2") == "dwuliterowy" or m_plate.group("n3") == "dwuliterowy") else 3
        return (
            {"operator": "char_count_equals", "left": {"entity": "target_powiat", "relation": "registration_plates"}, "right": {"value": n_val}},
            f"Do the county's registration plates have {n_val} letters?",
        )

    # 3. Sea access
    if re.fullmatch(r"(?:miec dostep do morze|graniczyc z morze|(?:lezec|byc) nad morze|miec dostep do baltyk|(?:lezec|byc) nad baltyk)", clause):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "water_access"}},
            "Does the county have access to the sea?",
        )

    # 4. Major rivers
    if re.fullmatch(r"(?:plynac \[RIVER\]|\[RIVER\] plynac|(?:lezec|byc) nad (?:rzeka )?\[RIVER\])", clause):
        if river:
            return (
                {"operator": "contains_text", "left": {"entity": "target_powiat", "relation": "major_rivers"}, "right": {"value": river}},
                f"Does {river} flow through the county?",
            )

    # 5. International borders
    if re.fullmatch(r"graniczyc z (?:inny |obcy )?(?:panstwo|kraj)", clause):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_country"}},
            "Does the county border a foreign country?",
        )

    if re.fullmatch(r"graniczyc z inny wojewodztwo", clause):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_voivodeship"}},
            "Does the county border another voivodeship?",
        )

    if re.fullmatch(r"(?:graniczyc z \[COUNTRY\]|z \[COUNTRY\] graniczyc)", clause):
        if country:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_powiat", "relation": "borders_country"}, "right": {"value": country}},
                f"Does the county border {_NEIGHBOR_ENGLISH_NAMES.get(country, country)}?",
            )

    # 6. Voivodeship borders
    if re.fullmatch(r"(?:graniczyc z (?:wojewodztwo )?\[VOJ\]|z (?:wojewodztwo )?\[VOJ\] graniczyc)", clause):
        if voj:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_powiat", "relation": "borders_voivodeship"}, "right": {"value": voj}},
                f"Does the county border {voj} voivodeship?",
            )

    # 7. Lies in voivodeship
    if re.fullmatch(r"(?:(?:lezec|byc) w (?:wojewodztwo )?\[VOJ\]|w (?:wojewodztwo )?\[VOJ\]|\[VOJ\])", clause):
        if voj:
            return (
                {"operator": "equals", "left": {"entity": "target_powiat", "relation": "voivodeship"}, "right": {"value": voj}},
                f"Is the county in {voj} voivodeship?",
            )

    # 8. English Powiatdle checks
    norm_en = _norm(question)
    if re.fullmatch(r"is (?:it|the county) a city (?:county|with county rights)", norm_en):
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 1}},
            "Is the county a city county?",
        )
    if re.fullmatch(r"is (?:it|the county) a land county", norm_en):
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 0}},
            "Is the county a land county?",
        )
    m_plate_en = re.fullmatch(
        r"(?:do (?:its|the county) (?:registration )?plates have (?P<n>2|3) letters"
        r"|does (?:it|the county) have (?P<n2>2|3)[ -]letter (?:registration )?plates)",
        norm_en,
    )
    if m_plate_en:
        n_val = int(m_plate_en.group("n") or m_plate_en.group("n2"))
        return (
            {"operator": "char_count_equals", "left": {"entity": "target_powiat", "relation": "registration_plates"}, "right": {"value": n_val}},
            f"Do the county's registration plates have {n_val} letters?",
        )
    if re.fullmatch(r"(?:does (?:it|the county) have (?:access to (?:the )?sea|a coastline)|is (?:it|the county) coastal)", norm_en):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "water_access"}},
            "Does the county have access to the sea?",
        )
    if re.fullmatch(r"does (?:it|the county) border (?:a )?(?:foreign |neighboring )?country", norm_en):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_country"}},
            "Does the county border a foreign country?",
        )
    if re.fullmatch(r"does (?:it|the county) border another voivodeship", norm_en):
        return (
            {"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_voivodeship"}},
            "Does the county border another voivodeship?",
        )
    m_border_en = re.fullmatch(r"does (?:it|the county) border (?P<country>[a-z ]+)", norm_en)
    if m_border_en:
        c_name = _EXPANDED_POLISH_NEIGHBORS.get(m_border_en.group("country"))
        if c_name:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_powiat", "relation": "borders_country"}, "right": {"value": c_name}},
                f"Does the county border {_NEIGHBOR_ENGLISH_NAMES.get(c_name, c_name)}?",
            )
    m_river_en = re.fullmatch(r"does (?:the )?(?P<river>[a-z ]+?)(?: river)? flow through (?:it|the county)", norm_en)
    if m_river_en:
        r_name = _EXPANDED_POLISH_RIVERS.get(m_river_en.group("river"))
        if r_name:
            return (
                {"operator": "contains_text", "left": {"entity": "target_powiat", "relation": "major_rivers"}, "right": {"value": r_name}},
                f"Does {r_name} flow through the county?",
            )
    return None


def compile_wojewodztwodle_template(question: str) -> tuple[dict[str, Any], str] | None:
    """Match high-frequency Województwodle player questions into canonical AST."""
    clause = canonicalize_pl_clause(question, target_nouns=("wojewodztwo", "region"))
    if not clause:
        return None

    res = _MATCH_RIVER(clause)
    if res is None:
        return None
    clause, river = res

    res = _MATCH_NEIGHBOR(clause)
    if res is None:
        return None
    clause, country = res

    res = _MATCH_VOJ(clause)
    if res is None:
        return None
    clause, voj = res

    # 1. Sea access
    if re.fullmatch(r"(?:miec dostep do morze|graniczyc z morze|(?:lezec|byc) nad morze|miec wybrzeze|miec dostep do baltyk|(?:lezec|byc) nad baltyk)", clause):
        return (
            {"operator": "equals", "left": {"entity": "target_voivodeship", "relation": "is_coastal"}, "right": {"value": True}},
            "Does the voivodeship have access to the sea?",
        )

    # 2. International borders
    if re.fullmatch(r"graniczyc z (?:inny |obcy )?(?:panstwo|kraj)", clause):
        return (
            {"operator": "exists", "left": {"entity": "target_voivodeship", "relation": "borders_country"}},
            "Does the voivodeship border a foreign country?",
        )

    if re.fullmatch(r"(?:graniczyc z \[COUNTRY\]|z \[COUNTRY\] graniczyc)", clause):
        if country:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_country"}, "right": {"value": country}},
                f"Does the voivodeship border {_NEIGHBOR_ENGLISH_NAMES.get(country, country)}?",
            )

    # 3. Neighboring voivodeship
    if re.fullmatch(r"(?:graniczyc z (?:wojewodztwo )?\[VOJ\]|z (?:wojewodztwo )?\[VOJ\] graniczyc)", clause):
        if voj:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_voivodeship"}, "right": {"value": voj}},
                f"Does the voivodeship border {voj} voivodeship?",
            )

    # 4. Major rivers
    if re.fullmatch(r"(?:plynac \[RIVER\]|\[RIVER\] plynac|(?:lezec|byc) nad (?:rzeka )?\[RIVER\])", clause):
        if river:
            return (
                {"operator": "contains_text", "left": {"entity": "target_voivodeship", "relation": "major_rivers"}, "right": {"value": river}},
                f"Does {river} flow through the voivodeship?",
            )

    # 5. English Województwodle checks
    norm_en = _norm(question)
    if re.fullmatch(r"(?:does (?:it|the voivodeship) have (?:access to (?:the )?sea|a coastline)|is (?:it|the voivodeship) coastal)", norm_en):
        return (
            {"operator": "equals", "left": {"entity": "target_voivodeship", "relation": "is_coastal"}, "right": {"value": True}},
            "Does the voivodeship have access to the sea?",
        )
    if re.fullmatch(r"does (?:it|the voivodeship) border (?:a )?(?:foreign |neighboring )?country", norm_en):
        return (
            {"operator": "exists", "left": {"entity": "target_voivodeship", "relation": "borders_country"}},
            "Does the voivodeship border a foreign country?",
        )
    m_border_en = re.fullmatch(r"does (?:it|the voivodeship) border (?P<country>[a-z ]+)", norm_en)
    if m_border_en:
        c_name = _EXPANDED_POLISH_NEIGHBORS.get(m_border_en.group("country"))
        if c_name:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_country"}, "right": {"value": c_name}},
                f"Does the voivodeship border {_NEIGHBOR_ENGLISH_NAMES.get(c_name, c_name)}?",
            )
    m_river_en = re.fullmatch(r"does (?:the )?(?P<river>[a-z ]+?)(?: river)? flow through (?:it|the voivodeship)", norm_en)
    if m_river_en:
        r_name = _EXPANDED_POLISH_RIVERS.get(m_river_en.group("river"))
        if r_name:
            return (
                {"operator": "contains_text", "left": {"entity": "target_voivodeship", "relation": "major_rivers"}, "right": {"value": r_name}},
                f"Does {r_name} flow through the voivodeship?",
            )
    return None


def compile_us_statedle_template(question: str) -> tuple[dict[str, Any], str] | None:
    """Match high-frequency US Statedle player questions into canonical AST."""
    norm_q = _norm(question)

    # Guard: negations and complex conjunctions
    if re.search(r"\b(?:not|nie|never|neither|nor|no|without|bez|brak)\b|\b\w+n t\b", norm_q):
        return None
    if re.search(
        r"\b(?:and|or|but|if|unless|except|when|while|where|that|which|whose|whether|whereas|"
        r"with|having|although|despite|until|provided|assuming|only|all|both|either|oraz|i|lub|albo|ale|jesli|jezeli|chyba|jednak)\b",
        norm_q,
    ):
        return None

    # Northeast region
    if re.fullmatch(r"is (?:it|the state) (?:located )?in (?:the )?north(?:[ -]?east)(?: region)?", norm_q):
        return (
            {"operator": "equals", "left": {"entity": "target_state", "relation": "region"}, "right": {"value": "Northeast"}},
            "Is the state in the Northeast?",
        )

    # Water bodies (re.fullmatch water plans)
    _ATLANTIC_PATTERNS = (
        "atlantic", "atlantyck", "atlantyk", "antlantic", "atlantik",
        "atlanitc", "atlanic", "atlntic", "atlatnic", "antlantyk", "antlantyck",
    )
    _PACIFIC_PATTERNS = ("pacific", "spokojn", "pacyfik", "pacifik", "pacyfic")
    _ARCTIC_PATTERNS = ("arctic", "arktyczn", "arktyk", "arktic")
    _INDIAN_PATTERNS = ("indian", "indyjsk")
    _SOUTHERN_PATTERNS = ("southern", "antarktyczn")
    _GULF_PATTERNS = ("gulf", "zatok")
    _COASTAL_TRIGGERS = (
        "coastal", "coast", "ocean", "oceanu", "morza", "morze", "wybrzez", "linia brzegowa", "nadmorsk",
        *_ATLANTIC_PATTERNS, *_PACIFIC_PATTERNS, *_ARCTIC_PATTERNS, *_INDIAN_PATTERNS, *_SOUTHERN_PATTERNS, *_GULF_PATTERNS,
    )
    is_border_q = any(k in norm_q for k in ("border", "borders", "touch", "touches", "graniczy", "granica"))
    if any(k in norm_q for k in _COASTAL_TRIGGERS):
        direct = (
            is_border_q
            or bool(re.search(r"\b(?:direct|directly|coast|coastline|shore|beach)\b|bezposredn|wybrzez|brzeg", norm_q))
            or not bool(re.search(r"\baccess\b|dostep", norm_q))
        )
        for patterns, body in (
            (_ATLANTIC_PATTERNS, "Atlantic Ocean"),
            (_PACIFIC_PATTERNS, "Pacific Ocean"),
            (_ARCTIC_PATTERNS, "Arctic Ocean"),
            (_INDIAN_PATTERNS, "Indian Ocean"),
            (_SOUTHERN_PATTERNS, "Southern Ocean"),
            (_GULF_PATTERNS, "Gulf of Mexico"),
        ):
            if any(k in norm_q for k in patterns):
                body_pattern = (
                    r"(?:gulf of mexico|zatok[ai] meksykansk[a-z]*)"
                    if body == "Gulf of Mexico"
                    else "(?:" + "|".join(re.escape(k) + r"[a-z]*" for k in patterns) + r")(?: ocean)?"
                )
                english = (
                    r"(?:does (?:it|the state) (?:have (?:direct |a direct )?"
                    r"(?:access to|coastline on|coast on|shoreline on)|(?:directly )?(?:border|touch))"
                    r"|is (?:it|the state) (?:located )?(?:on|along|by)) (?:the )?"
                )
                polish = (
                    r"czy (?:(?:ten )?stan )?(?:ma (?:bezposredni )?dostep do|"
                    r"(?:bezposrednio )?graniczy z|lezy nad|jest nad|znajduje sie nad) "
                    r"(?:oceanu |oceanem )?"
                )
                if not re.fullmatch("(?:" + english + "|" + polish + ")" + body_pattern, norm_q):
                    return None
                return build_us_state_water_plan(body, direct=direct)

        if re.fullmatch(r"(?:is (?:it|the state) (?:located )?on (?:the )?east coast|czy (?:ten stan )?lezy na wschodnim wybrzezu)", norm_q):
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "East Coast"}},
                "Is the state located on the East Coast?",
            )
        if re.fullmatch(r"(?:is (?:it|the state) (?:located )?on (?:the )?west coast|czy (?:ten stan )?lezy na zachodnim wybrzezu)", norm_q):
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "West Coast"}},
                "Is the state located on the West Coast?",
            )
        if re.fullmatch(r"(?:is (?:it|the state) (?:located )?in (?:the )?great lakes region|czy (?:ten stan )?lezy w regionie wielkich jezior)", norm_q):
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "Great Lakes"}},
                "Is the state located in the Great Lakes region?",
            )

        # Generic ocean / coastal access
        if re.fullmatch(
            r"(?:does (?:it|the state) border an ocean|is (?:it|the state) coastal|"
            r"czy (?:ten stan )?(?:ma dostep do (?:morza|oceanu)|graniczy z oceanem|jest nadmorski))",
            norm_q,
        ):
            return (
                {"operator": "equals", "left": {"entity": "target_state", "relation": "is_coastal"}, "right": {"value": True}},
                "Does the state border an ocean?",
            )

    # Whole-sentence Polish canonical skeleton checks
    clause = canonicalize_pl_clause(question, target_nouns=("stan",))
    if clause:
        res = _MATCH_US_STATE(clause)
        if res is not None:
            clause_st, state = res
            if state and re.fullmatch(r"(?:graniczyc z (?:stan )?\[STATE\]|z (?:stan )?\[STATE\] graniczyc)", clause_st):
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "borders_state"}, "right": {"value": state}},
                    f"Does the state border {state}?",
                )

        res_c = _MATCH_US_COUNTRY(clause)
        if res_c is not None:
            clause_c, country = res_c
            if country and re.fullmatch(r"(?:graniczyc z \[COUNTRY\]|z \[COUNTRY\] graniczyc)", clause_c):
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "borders_country"}, "right": {"value": country}},
                    f"Does the state border {country}?",
                )

        if re.fullmatch(r"graniczyc z (?:inny |obcy )?(?:panstwo|kraj)", clause):
            return (
                {"operator": "exists", "left": {"entity": "target_state", "relation": "borders_country"}},
                "Does the state border a foreign country?",
            )

        if re.fullmatch(r"(?:nazwa byc dwuczlonowy|byc dwuczlonowy)", clause):
            return (
                {"operator": "word_count_equals", "left": {"entity": "target_state", "relation": "name"}, "right": {"value": 2}},
                "Does the state name have 2 words?",
            )

        # 13 Colonies
        if re.fullmatch(r"(?:byc )?(?:1 z )?13 (?:pierwotny )?kolonia", clause):
            return (
                {"operator": "less_than_or_equal", "left": {"entity": "target_state", "relation": "admission_order"}, "right": {"value": 13}},
                "Was the state one of the original 13 colonies?",
            )

        # Civil War
        m_cw_pl = re.fullmatch(r"(?:walczyc po strona (?P<side>konfederacja|unia) w wojna secesyjny|byc w (?P<side2>konfederacja|unia) w wojna secesyjny)", clause)
        if m_cw_pl:
            s_raw = m_cw_pl.group("side") or m_cw_pl.group("side2")
            side = "Confederacy" if "konfederac" in s_raw else "Union"
            return (
                {"operator": "equals", "left": {"entity": "target_state", "relation": "civil_war_side"}, "right": {"value": side}},
                f"Did the state fight for the {side} during the Civil War?",
            )

    # English whole-sentence checks
    m_en_border_country = re.fullmatch(r"does (?:it|the state) border (?P<country>canada|mexico)", norm_q)
    if m_en_border_country:
        country_name = "Canada" if m_en_border_country.group("country") == "canada" else "Mexico"
        return (
            {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "borders_country"}, "right": {"value": country_name}},
            f"Does the state border {country_name}?",
        )

    # English 13 colonies
    if re.fullmatch(r"was (?:it|the state) one of the (?:original )?13 colonies", norm_q):
        return (
            {"operator": "less_than_or_equal", "left": {"entity": "target_state", "relation": "admission_order"}, "right": {"value": 13}},
            "Was the state one of the original 13 colonies?",
        )

    # English Civil war
    m_cw_en = re.fullmatch(
        r"(?:did (?:it|the state) fight for the (?P<side>confederacy|union) during the civil war"
        r"|was (?:it|the state) part of the (?P<side2>confederacy|union))",
        norm_q,
    )
    if m_cw_en:
        s_raw = m_cw_en.group("side") or m_cw_en.group("side2")
        side = "Confederacy" if s_raw == "confederacy" else "Union"
        return (
            {"operator": "equals", "left": {"entity": "target_state", "relation": "civil_war_side"}, "right": {"value": side}},
            f"Did the state fight for the {side} during the Civil War?",
        )

    return None


@lru_cache(maxsize=1024)
def compile_generic_template_plan(question: str, mode_name: str) -> tuple[dict[str, Any], str] | None:
    """Entry point dispatching to mode-specific template compiler."""
    if not isinstance(question, str) or not question.strip():
        return None
    if "/" in question or "\\" in question:
        return None
    slot_res = match_slot_template(question, mode_name)
    if slot_res is not None:
        return slot_res

    norm_mode = mode_name.lower().strip()
    if norm_mode in ("powiatdle", "powiat"):
        return compile_powiatdle_template(question)
    elif norm_mode in ("wojewodztwodle", "wojewodztwo"):
        return compile_wojewodztwodle_template(question)
    elif norm_mode in ("usstatedle", "us_statedle", "us_state"):
        return compile_us_statedle_template(question)
    return None
