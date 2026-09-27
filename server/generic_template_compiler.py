"""Deterministic template compiler for Powiatdle, Wojewodztwodle, and US Statedle.

Compiles high-frequency player question patterns into canonical AST plans in < 5ms,
bypassing LLM planner calls and eliminating API costs and latency.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from voivodeship_names import resolve_voivodeship_name, CANONICAL_VOIVODESHIPS


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
    "Słowacja": ("slowacja", "slowacja", "slowacja", "slowacja", "slowacji", "slowacja", "slovakia"),
    "Ukraina": ("ukraina", "ukraina", "ukrainie", "ukrainy", "ukraine"),
    "Białoruś": ("bialorus", "bialorusia", "bialorusi", "belarus"),
    "Litwa": ("litwa", "litwa", "litwie", "litwy", "lithuania"),
    "Rosja": ("rosja", "rosja", "rosji", "rosja", "obwodem krolewieckim", "obwodem kaliningradzkim", "krolewieckim", "kaliningradzkim", "russia"),
}

# Major rivers in Poland
POLISH_MAJOR_RIVERS = {
    "Wisła": ("wisla", "wisly", "wisle", "wisla", "vistula"),
    "Odra": ("odra", "odry", "odrze", "odra", "oder"),
    "Warta": ("warta", "warty", "warcie", "warta"),
    "Bug": ("bug", "bugu", "bugiem"),
    "Narew": ("narew", "narwi", "narwia"),
    "San": ("san", "sanu", "sanem"),
    "Noteć": ("notec", "noteci", "notecia"),
    "Pilica": ("pilica", "pilicy", "pilice"),
    "Bóbr": ("bobr", "bobra", "bobrem"),
    "Łyna": ("lyna", "lyny", "lynie"),
    "Drwęca": ("drweca", "drwecy", "drwece"),
}


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
    norm_q = _norm(question)
    words = norm_q.split()
    if re.search(r"\b(?:nie\s+(?:ma|graniczy|lezy|jest|plynie|przeplywa|posiada)|not\b|ani\b|bez\b|brak\b)", norm_q) and not re.search(r"\bpowiat(?:em)? ziemski(?:m)?\b", norm_q):
        return None
    if re.search(r"\b(?:oraz)\b", norm_q):
        return None
    # 1. City with county rights (is_city_county == 1)
    if re.search(r"\bmiasto na prawach powiatu\b", norm_q) or re.search(r"\bmiastem na prawach powiatu\b", norm_q):
        if any(neg in norm_q for neg in ("nie jest", "nie ")):
            pass # let complex negation pass to planner
        elif "powiat ziemski" not in norm_q:
            return (
                {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 1}},
                "Czy powiat jest miastem na prawach powiatu?",
            )

    # Powiat ziemski (is_city_county == 0)
    if re.search(r"\bpowiat(?:em)? ziemski(?:m)?\b", norm_q):
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "is_city_county"}, "right": {"value": 0}},
            "Czy powiat jest powiatem ziemskim?",
        )

    # 2. Registration plates length (char_count_equals on registration_plates)
    plate_kw = any(k in norm_q for k in ("tablic", "rejestrac", "wyroznik"))
    if plate_kw or any(k in norm_q for k in ("dwuliterow", "trzyliterow")):
        if re.search(r"\b(?:2|dwie|dwu)\s*(?:litery|liter|literowe|literowy)?\b", norm_q) and ("2" in norm_q or "dwuliterow" in norm_q or "dwie litery" in norm_q):
            return (
                {"operator": "char_count_equals", "left": {"entity": "target_powiat", "relation": "registration_plates"}, "right": {"value": 2}},
                "Czy tablice rejestracyjne powiatu mają 2 litery?",
            )
        if re.search(r"\b(?:3|trzy|trzy)\s*(?:litery|liter|literowe|literowy)?\b", norm_q) and ("3" in norm_q or "trzyliterow" in norm_q or "trzy litery" in norm_q):
            return (
                {"operator": "char_count_equals", "left": {"entity": "target_powiat", "relation": "registration_plates"}, "right": {"value": 3}},
                "Czy tablice rejestracyjne powiatu mają 3 litery?",
            )

    # 3. Sea access (water_access exists)
    if any(k in norm_q for k in ("morzem", "morza", "baltyk", "baltykiem")):
        if any(k in norm_q for k in ("graniczy", "dostep", "lezy nad", "jest nad", "znajduje sie nad")):
            return (
                {"operator": "exists", "left": {"entity": "target_powiat", "relation": "water_access"}},
                "Czy powiat ma dostęp do morza?",
            )

    # 4. Major rivers (major_rivers contains_text)
    for river_canonical, aliases in POLISH_MAJOR_RIVERS.items():
        if any(alias in words or f" {alias} " in f" {norm_q} " for alias in aliases):
            if any(k in norm_q for k in ("plynie", "przeplywa", "lezy nad", "rzeka", "rzeki")):
                return (
                    {"operator": "contains_text", "left": {"entity": "target_powiat", "relation": "major_rivers"}, "right": {"value": river_canonical}},
                    f"Czy przez powiat przepływa {river_canonical}?",
                )

    # 5. International borders (borders_country exists / contains_exact)
    is_border_q = any(k in norm_q for k in ("graniczy", "granice", "granica", "sasiaduje"))
    if is_border_q and any(k in norm_q for k in ("panstwem", "krajem", "zagranica", "obcym")):
        # Generic foreign border
        if not any(c in norm_q for aliases in POLISH_NEIGHBOR_COUNTRIES.values() for c in aliases):
            return (
                {"operator": "exists", "left": {"entity": "target_powiat", "relation": "borders_country"}},
                "Czy powiat graniczy z obcym państwem?",
            )

    for country_canonical, aliases in POLISH_NEIGHBOR_COUNTRIES.items():
        if any(alias in words or f" {alias} " in f" {norm_q} " for alias in aliases):
            if is_border_q:
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_powiat", "relation": "borders_country"}, "right": {"value": country_canonical}},
                    f"Czy powiat graniczy z: {country_canonical}?",
                )

    # 6. Voivodeship: Shorthand or explicit location/bordering
    # Check if a voivodeship is explicitly named
    matched_voivodeship = None
    for word in words:
        resolved = resolve_voivodeship_name(word)
        if resolved:
            matched_voivodeship = resolved
            break

    if matched_voivodeship is None:
        for canonical in CANONICAL_VOIVODESHIPS:
            res = resolve_voivodeship_name(norm_q)
            if res == canonical:
                matched_voivodeship = canonical
                break
            c_norm = _norm(canonical)
            if c_norm in norm_q:
                matched_voivodeship = canonical
                break
    if matched_voivodeship:
        # Is it a question about BORDERING the voivodeship?
        if is_border_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_powiat", "relation": "borders_voivodeship"}, "right": {"value": matched_voivodeship}},
                f"Czy powiat graniczy z województwem {matched_voivodeship}?",
            )
        # Otherwise it is asking if the powiat LIES IN the voivodeship
        return (
            {"operator": "equals", "left": {"entity": "target_powiat", "relation": "voivodeship"}, "right": {"value": matched_voivodeship}},
            f"Czy powiat leży w województwie {matched_voivodeship}?",
        )

    return None


def compile_wojewodztwodle_template(question: str) -> tuple[dict[str, Any], str] | None:
    """Match high-frequency Województwodle player questions into canonical AST."""
    norm_q = _norm(question)
    words = norm_q.split()
    if re.search(r"\b(?:nie\s+(?:ma|graniczy|lezy|jest|plynie|przeplywa|posiada)|not\b|ani\b|bez\b|brak\b)", norm_q):
        return None
    if re.search(r"\b(?:oraz)\b", norm_q):
        return None
    is_border_q = any(k in norm_q for k in ("graniczy", "granice", "granica", "sasiaduje"))

    # 1. Sea access (is_coastal == True)
    if any(k in norm_q for k in ("morzem", "morza", "baltyk", "baltykiem")):
        if any(k in norm_q for k in ("graniczy", "dostep", "lezy nad", "jest nad", "linia brzegowa")):
            return (
                {"operator": "equals", "left": {"entity": "target_voivodeship", "relation": "is_coastal"}, "right": {"value": True}},
                "Czy województwo ma dostęp do morza?",
            )

    # 2. International borders (borders_country exists / contains_exact)
    if is_border_q and any(k in norm_q for k in ("panstwem", "krajem", "zagranica", "obcym", "innego panstwa")):
        if not any(c in norm_q for aliases in POLISH_NEIGHBOR_COUNTRIES.values() for c in aliases):
            return (
                {"operator": "exists", "left": {"entity": "target_voivodeship", "relation": "borders_country"}},
                "Czy województwo graniczy z obcym państwem?",
            )

    for country_canonical, aliases in POLISH_NEIGHBOR_COUNTRIES.items():
        if any(alias in words or f" {alias} " in f" {norm_q} " for alias in aliases):
            if is_border_q:
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_country"}, "right": {"value": country_canonical}},
                    f"Czy województwo graniczy z: {country_canonical}?",
                )

    # 3. Neighboring voivodeship (borders_voivodeship contains_exact)
    if is_border_q:
        for word in words:
            resolved = resolve_voivodeship_name(word)
            if resolved:
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_voivodeship"}, "right": {"value": resolved}},
                    f"Czy województwo graniczy z województwem {resolved}?",
                )
        for canonical in CANONICAL_VOIVODESHIPS:
            c_norm = _norm(canonical)
            if c_norm in norm_q:
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_voivodeship", "relation": "borders_voivodeship"}, "right": {"value": canonical}},
                    f"Czy województwo graniczy z województwem {canonical}?",
                )

    # 4. Major rivers (major_rivers contains_text)
    for river_canonical, aliases in POLISH_MAJOR_RIVERS.items():
        if any(alias in words or f" {alias} " in f" {norm_q} " for alias in aliases):
            if any(k in norm_q for k in ("plynie", "przeplywa", "lezy nad", "rzeka", "rzeki")):
                return (
                    {"operator": "contains_text", "left": {"entity": "target_voivodeship", "relation": "major_rivers"}, "right": {"value": river_canonical}},
                    f"Czy przez województwo przepływa {river_canonical}?",
                )

    return None


def compile_us_statedle_template(question: str) -> tuple[dict[str, Any], str] | None:
    """Match high-frequency US Statedle player questions into canonical AST."""
    norm_q = _norm(question)
    if re.search(r"\b(?:not|nie|never|neither|nor)\b", norm_q):
        return None
    if re.search(r"\b(?:and|oraz)\b", norm_q):
        return None
    is_border_q = any(k in norm_q for k in ("border", "borders", "touch", "touches", "graniczy", "granica"))
    # 1. Foreign borders (Canada, Mexico)
    if is_border_q:
        if "canada" in norm_q or "kanad" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "borders_country"}, "right": {"value": "Canada"}},
                "Does the state border Canada?",
            )
        if "mexico" in norm_q or "meksyk" in norm_q:
            # Distinguish from Gulf of Mexico
            if "gulf" not in norm_q and "zatok" not in norm_q:
                return (
                    {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "borders_country"}, "right": {"value": "Mexico"}},
                    "Does the state border Mexico?",
                )

    # 2. Coastal state (is_coastal == True)
    if any(k in norm_q for k in ("coastal", "coast", "ocean", "oceanu", "morza", "morze", "wybrzez", "linia brzegowa")):
        # Check specific bodies first
        if "atlantic" in norm_q or "atlantyck" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "water_access"}, "right": {"value": "Atlantic Ocean"}},
                "Does the state have access to the Atlantic Ocean?",
            )
        if "pacific" in norm_q or "spokojn" in norm_q or "pacyfik" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "water_access"}, "right": {"value": "Pacific Ocean"}},
                "Does the state have access to the Pacific Ocean?",
            )
        if "gulf" in norm_q or "zatok" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "water_access"}, "right": {"value": "Gulf of Mexico"}},
                "Does the state have access to the Gulf of Mexico?",
            )
        # Check regional labels (East Coast, West Coast, Gulf Coast, Great Lakes)
        if "east coast" in norm_q or "wschodnie wybrzez" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "East Coast"}},
                "Is the state located on the East Coast?",
            )
        if "west coast" in norm_q or "zachodnie wybrzez" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "West Coast"}},
                "Is the state located on the West Coast?",
            )
        if "great lakes" in norm_q or "wielkie jezior" in norm_q:
            return (
                {"operator": "contains_exact", "left": {"entity": "target_state", "relation": "regional_labels"}, "right": {"value": "Great Lakes"}},
                "Is the state located in the Great Lakes region?",
            )
        # Generic ocean / coastal access
        if any(k in norm_q for k in ("ocean", "coastal", "dostep do morza", "dostep do oceanu", "graniczy z oceanem")):
            return (
                {"operator": "equals", "left": {"entity": "target_state", "relation": "is_coastal"}, "right": {"value": True}},
                "Does the state border an ocean?",
            )

    # 3. Original 13 colonies
    if "13" in norm_q and any(k in norm_q for k in ("colon", "kolon")):
        return (
            {"operator": "less_than_or_equal", "left": {"entity": "target_state", "relation": "admission_order"}, "right": {"value": 13}},
            "Was the state one of the original 13 colonies?",
        )

    # 4. Civil War side
    if any(k in norm_q for k in ("civil war", "wojna secesyjn", "wojny secesyjn")):
        if any(k in norm_q for k in ("confederat", "konfederac", "south", "poludni")):
            return (
                {"operator": "equals", "left": {"entity": "target_state", "relation": "civil_war_side"}, "right": {"value": "Confederacy"}},
                "Did the state fight for the Confederacy during the Civil War?",
            )
        if any(k in norm_q for k in ("union", "unia", "unij", "north", "polnoc")):
            return (
                {"operator": "equals", "left": {"entity": "target_state", "relation": "civil_war_side"}, "right": {"value": "Union"}},
                "Did the state fight for the Union during the Civil War?",
            )

    return None


def compile_generic_template_plan(question: str, mode_name: str) -> tuple[dict[str, Any], str] | None:
    """Entry point dispatching to mode-specific template compiler."""
    norm_mode = mode_name.lower().strip()
    if norm_mode == "powiatdle":
        return compile_powiatdle_template(question)
    elif norm_mode == "wojewodztwodle":
        return compile_wojewodztwodle_template(question)
    elif norm_mode == "usstatedle":
        return compile_us_statedle_template(question)
    return None
