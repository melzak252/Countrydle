"""Authoritative geographical water body hierarchy, parent basin mappings, and aliases.

Marginal seas, gulfs, and bays connect to oceanic drainage basins. When players
ask whether a country or state borders an ocean (e.g. "Does Nicaragua border the
Atlantic Ocean?", "Does Poland have access to the ocean?"), this hierarchy
provides the complete transitive parent resolution.
"""

from __future__ import annotations

import re
from typing import Any

# Direct parent relations (marginal sea/gulf/bay -> immediate parent sea or ocean)
DIRECT_WATER_BODY_PARENTS: dict[str, set[str]] = {
    # Mediterranean Basin
    "Adriatic Sea": {"Mediterranean Sea"},
    "Aegean Sea": {"Mediterranean Sea"},
    "Ionian Sea": {"Mediterranean Sea"},
    "Ligurian Sea": {"Mediterranean Sea"},
    "Tyrrhenian Sea": {"Mediterranean Sea"},
    "Sea of Crete": {"Mediterranean Sea"},
    "Black Sea": {"Mediterranean Sea"},
    "Sea of Azov": {"Black Sea"},
    "Mediterranean Sea": {"Atlantic Ocean"},

    # Atlantic Basin
    "Caribbean Sea": {"Atlantic Ocean"},
    "Gulf of Mexico": {"Atlantic Ocean"},
    "Gulf of Guinea": {"Atlantic Ocean"},
    "Baltic Sea": {"Atlantic Ocean"},
    "Morze Bałtyckie": {"Baltic Sea", "Atlantic Ocean"},
    "North Sea": {"Atlantic Ocean"},
    "Skagerrak": {"North Sea"},
    "Celtic Sea": {"Atlantic Ocean"},
    "Irish Sea": {"Atlantic Ocean"},
    "Norwegian Sea": {"Atlantic Ocean", "Arctic Ocean"},
    "Barents Sea": {"Arctic Ocean", "Atlantic Ocean"},

    # Pacific Basin
    "South China Sea": {"Pacific Ocean"},
    "Gulf of Thailand": {"South China Sea"},
    "East China Sea": {"Pacific Ocean"},
    "Yellow Sea": {"Pacific Ocean"},
    "Bohai Sea": {"Yellow Sea"},
    "Sea of Japan": {"Pacific Ocean"},
    "Sea of Okhotsk": {"Pacific Ocean"},
    "Philippine Sea": {"Pacific Ocean"},
    "Celebes Sea": {"Pacific Ocean"},
    "Sulu Sea": {"Pacific Ocean"},
    "Banda Sea": {"Pacific Ocean"},
    "Arafura Sea": {"Pacific Ocean", "Indian Ocean"},
    "Coral Sea": {"Pacific Ocean"},
    "Tasman Sea": {"Pacific Ocean"},
    "Bering Sea": {"Pacific Ocean"},
    "Gulf of Alaska": {"Pacific Ocean"},

    # Indian Ocean Basin
    "Arabian Sea": {"Indian Ocean"},
    "Red Sea": {"Indian Ocean"},
    "Gulf of Aqaba": {"Red Sea"},
    "Gulf of Aden": {"Arabian Sea"},
    "Persian Gulf": {"Arabian Sea"},
    "Gulf of Oman": {"Arabian Sea"},
    "Somali Sea": {"Indian Ocean"},
    "Bay of Bengal": {"Indian Ocean"},
    "Andaman Sea": {"Bay of Bengal"},
    "Timor Sea": {"Indian Ocean"},

    # Great Lakes (US States)
    "Lake Superior": {"Great Lakes"},
    "Lake Michigan": {"Great Lakes"},
    "Lake Huron": {"Great Lakes"},
    "Lake Erie": {"Great Lakes"},
    "Lake Ontario": {"Great Lakes"},

    # Oceans map to Ocean
    "Atlantic Ocean": {"Ocean"},
    "Pacific Ocean": {"Ocean"},
    "Indian Ocean": {"Ocean"},
    "Arctic Ocean": {"Ocean"},
    "Southern Ocean": {"Ocean"},
}

# Endorheic / inland water bodies that do NOT connect to the open world ocean
INLAND_WATER_BODIES: frozenset[str] = frozenset({
    "caspian sea", "aral sea", "dead sea",
    "morze kaspijskie", "morze aralskie", "morze martwe",
})

# Polish and English normalized aliases for water bodies
WATER_BODY_ALIASES: dict[str, str] = {
    # Oceans (English and Polish)
    "atlantic": "Atlantic Ocean",
    "atlantic ocean": "Atlantic Ocean",
    "atlantyk": "Atlantic Ocean",
    "atlantyku": "Atlantic Ocean",
    "atlantykiem": "Atlantic Ocean",
    "ocean atlantycki": "Atlantic Ocean",
    "oceanu atlantyckiego": "Atlantic Ocean",
    "oceanem atlantyckim": "Atlantic Ocean",
    "pacific": "Pacific Ocean",
    "pacific ocean": "Pacific Ocean",
    "pacyfik": "Pacific Ocean",
    "pacyfiku": "Pacific Ocean",
    "pacyfikiem": "Pacific Ocean",
    "ocean spokojny": "Pacific Ocean",
    "oceanu spokojnego": "Pacific Ocean",
    "oceanem spokojnym": "Pacific Ocean",
    "indian": "Indian Ocean",
    "indian ocean": "Indian Ocean",
    "ocean indyjski": "Indian Ocean",
    "oceanu indyjskiego": "Indian Ocean",
    "oceanem indyjskim": "Indian Ocean",
    "arctic": "Arctic Ocean",
    "arctic ocean": "Arctic Ocean",
    "ocean arktyczny": "Arctic Ocean",
    "oceanu arktycznego": "Arctic Ocean",
    "oceanem arktycznym": "Arctic Ocean",
    "southern ocean": "Southern Ocean",
    "ocean poludniowy": "Southern Ocean",
    "oceanu poludniowego": "Southern Ocean",
    "oceanem poludniowym": "Southern Ocean",
    "ocean": "Ocean",
    "oceanu": "Ocean",
    "oceanem": "Ocean",

    # Baltic
    "baltic": "Baltic Sea",
    "baltic sea": "Baltic Sea",
    "baltyk": "Baltic Sea",
    "baltyku": "Baltic Sea",
    "baltykiem": "Baltic Sea",
    "baltyckiego": "Baltic Sea",
    "morze baltyckie": "Baltic Sea",
    "morza baltyckiego": "Baltic Sea",
    "morzem baltyckim": "Baltic Sea",
    "morzu baltyckim": "Baltic Sea",

    # Mediterranean
    "mediterranean": "Mediterranean Sea",
    "mediterranean sea": "Mediterranean Sea",
    "srodziemne": "Mediterranean Sea",
    "srodziemnego": "Mediterranean Sea",
    "morze srodziemne": "Mediterranean Sea",
    "morza srodziemnego": "Mediterranean Sea",
    "morzem srodziemnym": "Mediterranean Sea",
    "morzu srodziemnym": "Mediterranean Sea",

    # Adriatic
    "adriatic": "Adriatic Sea",
    "adriatic sea": "Adriatic Sea",
    "adriatyk": "Adriatic Sea",
    "adriatyku": "Adriatic Sea",
    "adriatykiem": "Adriatic Sea",
    "morze adriatyckie": "Adriatic Sea",
    "morza adriatyckiego": "Adriatic Sea",
    "morzem adriatyckim": "Adriatic Sea",
    "morzu adriatyckim": "Adriatic Sea",

    # Black Sea
    "black sea": "Black Sea",
    "czarne": "Black Sea",
    "czarnego": "Black Sea",
    "morze czarne": "Black Sea",
    "morza czarnego": "Black Sea",
    "morzem czarnym": "Black Sea",
    "morzu czarnym": "Black Sea",

    # Red Sea
    "red sea": "Red Sea",
    "czerwone": "Red Sea",
    "czerwonego": "Red Sea",
    "morze czerwone": "Red Sea",
    "morza czerwonego": "Red Sea",
    "morzem czerwonym": "Red Sea",
    "morzu czerwonym": "Red Sea",

    # North Sea
    "north sea": "North Sea",
    "polnocne": "North Sea",
    "polnocnego": "North Sea",
    "morze polnocne": "North Sea",
    "morza polnocnego": "North Sea",
    "morzem polnocnym": "North Sea",
    "morzu polnocnym": "North Sea",

    # Caribbean
    "caribbean": "Caribbean Sea",
    "caribbean sea": "Caribbean Sea",
    "karaiby": "Caribbean Sea",
    "karaibskie": "Caribbean Sea",
    "morze karaibskie": "Caribbean Sea",
    "morza karaibskiego": "Caribbean Sea",
    "morzem karaibskim": "Caribbean Sea",
    # Gulf of Mexico
    "gulf of mexico": "Gulf of Mexico",
    "zatoka meksykanska": "Gulf of Mexico",
    "zatoki meksykanskiej": "Gulf of Mexico",
    "zatoke meksykanska": "Gulf of Mexico",

    # Persian Gulf
    "persian gulf": "Persian Gulf",
    "zatoka perska": "Persian Gulf",
    "zatoki perskiej": "Persian Gulf",
    "perska": "Persian Gulf",

    # South China Sea
    "south china sea": "South China Sea",
    "morze poludniowochinskie": "South China Sea",

    # Sea of Japan
    "sea of japan": "Sea of Japan",
    "morze japonskie": "Sea of Japan",

    # Sea of Okhotsk
    "sea of okhotsk": "Sea of Okhotsk",
    "morze ochockie": "Sea of Okhotsk",

    # Bering Sea
    "bering sea": "Bering Sea",
    "morze beringa": "Bering Sea",

    # Norwegian Sea
    "norwegian sea": "Norwegian Sea",
    "morze norweskie": "Norwegian Sea",

    # Barents Sea
    "barents sea": "Barents Sea",
    "morze barentsa": "Barents Sea",

    # Caspian Sea
    "caspian sea": "Caspian Sea",
    "morze kaspijskie": "Caspian Sea",

    # Great Lakes
    "great lakes": "Great Lakes",
    "wielkie jeziora": "Great Lakes",
    "wielkich jezior": "Great Lakes",
    "wielkimi jeziorami": "Great Lakes",

    # Generic Sea
    "morze": "Sea",
    "morza": "Sea",
    "morzem": "Sea",
    "morzu": "Sea",
    "sea": "Sea",
}


def _norm(text: str) -> str:
    """Normalize text by lowering, stripping diacritics and non-alphanumeric chars."""
    t = text.lower()
    mapping = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    }
    for k, v in mapping.items():
        t = t.replace(k, v)
    t = re.sub(r"[^\w\s-]", "", t)
    return " ".join(t.split())


def _build_transitive_hierarchy(direct_map: dict[str, set[str]]) -> dict[str, set[str]]:
    """Compute the full transitive closure of parent water bodies."""
    full_map: dict[str, set[str]] = {}
    for body in direct_map:
        parents: set[str] = set()
        queue = list(direct_map[body])
        while queue:
            p = queue.pop(0)
            if p not in parents:
                parents.add(p)
                if p in direct_map:
                    queue.extend(direct_map[p] - parents)

        # Marine classification
        norm_b = _norm(body)
        if norm_b not in INLAND_WATER_BODIES and not body.startswith("Lake "):
            if "Ocean" not in body:
                parents.add("Sea")
            # If any parent is an ocean, the body also inherits Ocean
            if any("Ocean" in p for p in parents) or "Ocean" in body:
                parents.add("Ocean")
        full_map[body] = parents
    return full_map


# Complete transitive closure mapping: water_body -> set of all parent bodies
WATER_BODY_PARENT_MAP: dict[str, set[str]] = _build_transitive_hierarchy(DIRECT_WATER_BODY_PARENTS)

# Normalized lookup map: normalized_name -> set of canonical parent names
NORMALIZED_WATER_PARENT_MAP: dict[str, set[str]] = {
    _norm(body): parents for body, parents in WATER_BODY_PARENT_MAP.items()
}


def get_water_body_parents(water_body: str) -> set[str]:
    """Get all transitive parent water bodies for a given water body name."""
    if water_body in WATER_BODY_PARENT_MAP:
        return WATER_BODY_PARENT_MAP[water_body]
    normalized = _norm(water_body)
    canonical = WATER_BODY_ALIASES.get(normalized)
    if canonical and canonical in WATER_BODY_PARENT_MAP:
        return WATER_BODY_PARENT_MAP[canonical]
    return NORMALIZED_WATER_PARENT_MAP.get(normalized, set())


def expand_water_bodies(water_bodies: set[str] | list[str]) -> set[str]:
    """Expand a collection of direct water bodies with all transitive parents."""
    expanded = set(water_bodies)
    for w in list(water_bodies):
        parents = get_water_body_parents(w)
        expanded.update(parents)
    return expanded


def is_marine_water_body(water_body: str) -> bool:
    """Check whether a named water body gives a coastline connected to the open world ocean."""
    return _norm(water_body) not in INLAND_WATER_BODIES


def canonicalize_water_body(query_str: str) -> str | None:
    """Find a mentioned water body from a question or string, returning canonical English name."""
    norm_q = _norm(query_str)
    for alias, canonical in sorted(WATER_BODY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", norm_q):
            return canonical
    for canonical in sorted(WATER_BODY_PARENT_MAP.keys(), key=lambda x: len(x), reverse=True):
        if _norm(canonical) in norm_q:
            return canonical
    return None
WORLD_OCEANS: frozenset[str] = frozenset({
    "Atlantic Ocean", "Pacific Ocean", "Indian Ocean", "Arctic Ocean", "Southern Ocean",
})

MULTI_OCEAN_PATTERNS: tuple[str, ...] = (
    r"\b(?:two|2|multiple|more than one)\s+oceans?\b",
    r"\b(?:dw(?:a|och|óch|oma|e))\s+ocean(?:y|ow|ów|ami)?\b",
    r"\bwi[eę]cej\s+ni[zż]\s+jedn(?:ego|ym)\s+ocean(?:u|em)?\b",
    r"\b(?:oba|obu|obydwa|obydwu|obydwoma)\s+ocean(?:y|ow|ów|ami)?\b",
    r"\bboth\s+oceans?\b",
)


def is_multi_ocean_question(question: str) -> bool:
    """Check whether a question asks whether an entity has access to two or multiple oceans."""
    return any(re.search(pattern, question, re.I) for pattern in MULTI_OCEAN_PATTERNS)


def get_distinct_oceans(water_bodies: set[str] | list[str]) -> set[str]:
    """Get the set of distinct open world oceans a location has direct or indirect access to."""
    oceans: set[str] = set()
    for w in water_bodies:
        if not is_marine_water_body(w):
            continue
        if w in WORLD_OCEANS:
            oceans.add(w)
        for p in get_water_body_parents(w):
            if p in WORLD_OCEANS:
                oceans.add(p)
    return oceans


def build_multi_ocean_plan(target_entity: str = "target_country") -> dict:
    """Build a tree-form AST checking whether target_entity has access to 2 or more oceans."""
    oceans = ["Atlantic Ocean", "Pacific Ocean", "Indian Ocean", "Arctic Ocean"]
    pairs = []
    for i in range(len(oceans)):
        for j in range(i + 1, len(oceans)):
            pairs.append({
                "operator": "and",
                "conditions": [
                    {"operator": "contains", "left": {"entity": target_entity, "relation": "water_access"}, "right": {"value": oceans[i]}},
                    {"operator": "contains", "left": {"entity": target_entity, "relation": "water_access"}, "right": {"value": oceans[j]}},
                ]
            })
    return {"operator": "or", "conditions": pairs}
