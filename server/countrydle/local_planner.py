"""Gemini-based planner for local Countrydle answering.

The planner does not answer the user's question. It validates and rewrites the
question, then returns a small execution plan that can be evaluated against the
local SQLite knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import sqlite3
from countrydle import local_answering
from countrydle.local_answering import LIST_RELATION_QUERIES
from countrydle.template_compiler import (
    _ENGLISH_COUNTRY_ALIASES, _norm, compile_entity_question, compile_template_plan,
)
from planner_protocol import (
    PLANNER_MAX_OUTPUT_TOKENS, PLANNER_OPERATORS, PLANNER_RULES, PLANNER_THINKING_BUDGET, PLANNER_VERSION,
    compile_planner_response, planner_response_schema,
)


APP_DIR = Path(__file__).resolve().parent
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_MODEL = "gemini-2.5-flash-lite"
# Countrydle-only prompt/generation revision; shared contracts/modes keep PLANNER_VERSION.
COUNTRYDLE_PROMPT_REVISION = "compact-v8-continent-borders-t1024"


SUPPORTED_RELATIONS = [
    "name",
    "continent",
    "geographic_area",
    "borders_country",
    "water_access",
    "marine_access",
    "is_island",
    "capital",
    "currency",
    "official_language",
    "membership",
    "population",
    "area",
    "coordinates.latitude",
    "coordinates.longitude",
    "major_rivers",
    "driving_side",
    "dominant_religion",
    "government_type",
    "flag_color",
    "flag_symbol",
    "historical_union",
    "hemisphere",
]

@dataclass(frozen=True)
class QuestionPlan:
    original_question: str
    valid: bool
    supported: bool
    improved_question: str | None
    explanation: str | None
    plan: dict | None
    fallback_reason: str | None = None


def load_dotenv_if_present() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_planner_prompt(question: str) -> str:
    meanings = {
        "name": "common/display country name; identity aliases resolve; official-name text/count is unsupported",
        "continent": "list of physical continental membership; membership tests use contains, never equals",
        "geographic_area": "stored broad regions/subregions, not unrepresented directional quadrants such as Northwestern Africa",
        "borders_country": "land-bordering countries",
        "water_access": "named coastal water bodies, including inland seas; contains(name) tests a known body, Ocean means ocean access only",
        "marine_access": "open-sea-connected coastline waters only; excludes inland/endorheic waters such as the Caspian Sea; landlocked is NOT exists(target_country.marine_access), not any/all",
        "is_island": "island-country boolean",
        "capital": "capital city in common English spelling (Warszawa→Warsaw); this is not a country-identity literal",
        "currency": "currency names/codes; prefer ISO 4217 codes for recognized currencies (e.g. yen→JPY), not shortened names",
        "official_language": "list of legally official/co-official languages, not spoken-prevalence data",
        "membership": "current organization memberships using their short codes (European Union→EU, North Atlantic Treaty Organization→NATO)",
        "population": "population in people",
        "area": "stored area in km²",
        "coordinates.latitude": "latitude in signed degrees",
        "coordinates.longitude": "longitude in signed degrees",
        "major_rivers": "recorded major rivers",
        "driving_side": "left/right driving side",
        "dominant_religion": "grouped dominant-religion category",
        "government_type": "broad stored government-form category",
        "flag_color": "colors present on flag",
        "flag_symbol": "symbols/designs present on flag",
        "historical_union": "past membership in named historical polities",
        "hemisphere": "hemispheres containing country territory",
    }
    relations = "\n".join(
        f"- {relation} ({'list' if relation in LIST_RELATION_QUERIES else 'scalar'}): "
        f"{meanings[relation]}"
        for relation in SUPPORTED_RELATIONS
    )
    return f"""
Plan a yes/no question for the hidden country; do not answer it. Recover the intended
proposition (translate Polish/other input to English); repair grammar/ordinary typos,
not missing meaning. Pronouns, "I/we/my country", and an explicitly named country
subject refer to the hidden target. Descriptive fragments and conventional region
adjectives can be yes/no questions. The game supplies the target.
A clear false or impossible proposition is still a valid yes/no question; never
classify it as nonsense merely because its answer would be false.

Decide in this order:
1. clarify + plan=null for unresolved relation/polarity/reference or criterion,
   open-ended, unrelated or nonsensical requests; explain what is missing.
2. Otherwise local + plan iff supported facts AND operators express every clause.
3. Otherwise fallback + plan=null for a clear objective question needing absent facts/
   operations; name the missing capability. Missing local coverage is never invalidity.
Official-name text/count predicates require fallback: official_name is absent.
Do not substitute common name for legal name. Official aliases remain valid for
country identity only ("Is it the Republic of Poland?", not its spelling properties).
Do not invent thresholds, comparisons, events, time periods, definitions or criteria.
Large/small/big, near, famous, beautiful, popular, important, good, often/a lot need
an objective criterion; known area, rank or participation does not supply one. Do not
substitute bordering for proximity, existence for fame, or participation/statehood for
an important role; typical food does not define eating frequency.
Preserve all clauses, qualifiers and polarity: a trailing "or not?" is not negation;
real A-or-B keeps both branches and internal negation. "Neither A nor B" is
not(or(A,B)). Resolve each positive predicate using the rules below, then negate it.
Territory, history, culture, people and landmarks are valid subjects; when clear but
not locally supported, use fallback.
Never weaken, drop, or add conditions.

Output JSON and all fields/literals in English; use common English names, not official
long names. Normalize translated names (Bałtyk→Baltic Sea, Niemcy→Germany, UE→EU).
Quoted text patterns for starts_with/ends_with/contains_text preserve exact original
characters, not translated meaning ("stan" stays "stan", never "state").
Exception: identity literals preserve the candidate's exact original abbreviation or
misspelling for deterministic resolution. Do not autocorrect an identity candidate;
even an unfamiliar proper name gets a local identity plan. Correctly spelled foreign
country names translate when unambiguous.
For example, "Are you Nigeri?" must preserve literal "Nigeri", never guess "Nigeria"
or "Niger"; deterministic identity resolution decides ambiguity.
Identity ("Is it Poland?", including multiple candidates) is valid; compare
target_country.name equals country name, OR
multiple candidates. A sea/city/line is not a country: require an explicit relation
and never invent one. "What country is it?" is open-ended.
An explicitly named country subject still asks about the hidden target's property,
not whether that named country itself has it.
Named comparison references remain named: the same country facts are available for
Poland, Germany, etc. Use both operand references, not fetched/invented literals:
{{"operator":"greater_than","left":{{"entity":"target_country","relation":"population"}},"right":{{"entity":"Poland","relation":"population"}}}}.
For "Does France have a population greater than Germany?", the subject still means
target_country: compare target_country.population > Germany.population. Never return
a constant France-vs-Germany comparison that ignores the hidden target.
Only country rows have these facts; a capital city's population is not country population.

Supported relations (list/scalar):
{relations}

Semantic mapping:
  longitude: west_of means target < reference; east_of means target > reference.
  latitude: north_of means target > reference; south_of means target < reference.
  Use north_of/south_of/west_of/east_of for geographic-direction predicates, including
  named-country references; plain numeric coordinate thresholds use numeric operators.
  Directional operands must use the relevant coordinates, never country-name text.
  Meridian/longitude references permit east/west, NOT north/south; latitude parallels
  permit north/south, NOT east/west. An incompatible axis ("south of Prime Meridian")
  requires clarify, never changing south to west or inventing a point on the line.
  Coordinates are signed degrees (west/south negative); point coordinates do not describe territorial extent.
- `hemisphere` describes territory, not a point. North/above the equator means contains
  Northern; south/below means Southern; crossing/on means both, joined with AND.
  East/west of Greenwich means contains Eastern/Western; crossing/on means both.
  "Entirely" in one hemisphere means contains that hemisphere AND NOT its opposite.
  Never use scalar coordinates for equator/prime-meridian sides or crossings. A bare
  compass direction needs a reference; "north/south part of Earth/world/planet" gives
  the global hemisphere frame. "Not the prime meridian" lacks a relation; "not on it"
  has one. Never turn nad równikiem ("above") into "on the equator".
- Use contains for list membership and equals for scalar equality; exists means only
  some known value / true. List equals string/boolean is not membership/nonemptiness.
  `is_island` is scalar boolean. For self-bordering, test
  contains(target_country.borders_country, target_country.name); executor treats it true.
- `official_language` is legal official/co-official status, not prevalence. Specific
  named-language checks ("Do they speak French?" or official status) use contains;
  this does not establish how widely it is spoken. Usual/dominant-language prevalence,
  origins/families, and distinct "own language" identity need general knowledge (fallback),
  not exists(official_language) or a legal-status substitute. Preserve origin predicates.
  `dominant_religion` is grouped. Ordinary Christian/Christianity predicates ALWAYS
  mean Catholic OR Orthodox OR Protestant OR Christianity; a standalone equals
  Christianity loses the denominational categories and is wrong for this umbrella.
  Other categories: Islam, Judaism, Buddhism, Hinduism, Folk/Traditional religions,
  No religion, Mixed, Other; use Mixed for religiously mixed.
  Unlisted denominations/sects, state religion and population percentages are absent:
  fallback rather than using a related dominant-religion category.
- `government_type` supports Republic, Monarchy, Communist state, Theocracy, Military
  junta, Transitional government, Other. Democracy is not Republic; do not infer
  democracy from category. Constitutional vs absolute monarchy and finer classifications
  require fallback.
- `continent` exact values distinguish North America from South America. Eurasia =
  Europe OR Asia; unqualified America/Americas = North America OR South America, never
  silently USA. `geographic_area` is a list for user-facing broad and subregions
  (Africa, Americas, Asia, Europe, Oceania; e.g. Caribbean, Central Europe, Balkans,
  Middle East). Latin America / "Latin country" is cultural, not Americas: fallback.
  Preserve north/south/east/west qualifiers. "In Europe" is not "entirely in Europe";
  precise full territorial extent not in regional tags requires fallback.
  Cultural/ethnic/language-family labels (Slavic, Germanic, Romance, Celtic, Turkic,
  Arab, Francophone, Anglophone, Lusophone) are not geographic_area/official_language;
  fallback. Established shorthand remains valid; Nordic/Scandinavian is geographic.
  "Touch/border a continent or region" means any land-border country is in that
  continent/region: any(target_country.borders_country, contains(item.continent,
  continent)) or item.geographic_area for a region. Never replace this with the
  target's own continental/regional membership. Preserve negation and additional
  clauses. "In/part of a continent" still tests target_country.continent; proximity,
  maritime borders and territorial extent are different predicates.
  Spelling/grammar repairs and translation must preserve the relation verb:
  touch/border must never become in/belong/part of, even if the place is misspelled.
  A recognized cultural-country label such as Germanic is valid but unsupported:
  missing local cultural definitions/coverage alone means fallback, not clarify.
- Use `historical_union` only for past membership in USSR, Yugoslavia, Czechoslovakia,
  Gran Colombia, Austro-Hungarian Empire, Warsaw Pact, British Empire, Spanish Empire,
  French Empire, Portuguese Empire, Ottoman Empire. It covers only these; Eastern Bloc is not Warsaw
  Pact. PAST Soviet constituent republic/part-of questions use historical_union contains
  USSR, never government_type=Republic. `membership` is PRESENT membership even for
  dissolved organizations: "currently part of USSR" uses membership contains USSR,
  not historical_union and not missing coverage solely because it is dissolved.
  Past membership in active organizations, founding/creator/signatory status, accession
  dates/years, and unlisted historical groups require fallback. Never swap current and past.
- `flag_color` values red, white, blue, green, yellow, black, orange; `flag_symbol` values
  star, stars, cross, crescent, sun, stripes, circle, eagle, coat_of_arms. Use contains
  for asked color/design presence only; majority/proportion/layout/exclusive colors
  require fallback.
- Numeric operators preserve exact strict/inclusive thresholds: >/< are strict;
  at least/co najmniej is >=; at most/does not exceed/nie przekracza is <=.
  Name character counts ignore spaces and hyphens; use word_count_* or char_count_*.
  starts_with/ends_with test text edges; contains_text tests a substring.
  For starts-with letter ranges, OR one starts_with test per inclusive letter (never AND).
  Use has_space/has_hyphen for those characters (hyphen includes Unicode hyphens,
  not en/em dash; Polish łącznik); other text substrings use contains_text. Preserve
  quoted characters exactly ("-" differs from "–").
- any/all quantify a list and test the bound item predicate; any already requires a
  matching item, so do not add exists for that same list. For "borders an EU member",
  test item.membership contains EU, then any over target_country.borders_country.
  A target predicate and item predicate are distinct.
  Item country facts need country-valued items (border countries or literal country
  names). Water bodies, languages and flag values are not country rows: do not query
  item.water_access/item.membership on them; use direct contains/exists instead.
  For shared continent membership, OR one AND pair per physical continent:
  contains(target_country.continent, C) AND contains(reference_country.continent, C).
  Never bind continent-name strings as country rows or use contains(list, another list).
- Largest/smallest in a group, rankings, continent-wide counts, arbitrary historical
  periods, flag percentages and exact territory extent are unsupported; fallback.
Do not invent relation names or substitute a related fact for a missing one.

{PLANNER_RULES.replace("TARGET", "target_country")}

Return strict compact JSON only, required fields route and plan. Local omits explanation
and fallback_reason. Add improved_question only for translation/clarification. Clarify
with a short explanation of the missing predicate/reference/criterion; fallback with
a short missing-facts reason. Examples:

Polish: "Czy graniczy z krajem należącym do UE?" (not merely has an EU border fact):
{{"route":"local","improved_question":"Does the country border an EU member?","plan":[
  {{"operator":"contains","left":{{"entity":"item","relation":"membership"}},"right":{{"value":"EU"}}}},
  {{"operator":"any","items":{{"entity":"target_country","relation":"borders_country"}},"args":[0]}}
]}}

"Does it touch Asia?" means a land neighbor is in Asia, NOT target membership:
{{"route":"local","plan":[
  {{"operator":"contains","left":{{"entity":"item","relation":"continent"}},"right":{{"value":"Asia"}}}},
  {{"operator":"any","items":{{"entity":"target_country","relation":"borders_country"}},"args":[0]}}
]}}

"Does it cross the equator?" means both hemispheres, not a point latitude:
{{"route":"local","plan":[
  {{"operator":"contains","left":{{"entity":"target_country","relation":"hemisphere"}},"right":{{"value":"Northern"}}}},
  {{"operator":"contains","left":{{"entity":"target_country","relation":"hemisphere"}},"right":{{"value":"Southern"}}}},
  {{"operator":"and","args":[0,1]}}
]}}

"Is Christianity the dominant religion?" uses ALL four Christian categories:
{{"route":"local","plan":[
  {{"operator":"equals","left":{{"entity":"target_country","relation":"dominant_religion"}},"right":{{"value":"Catholic"}}}},
  {{"operator":"equals","left":{{"entity":"target_country","relation":"dominant_religion"}},"right":{{"value":"Orthodox"}}}},
  {{"operator":"equals","left":{{"entity":"target_country","relation":"dominant_religion"}},"right":{{"value":"Protestant"}}}},
  {{"operator":"equals","left":{{"entity":"target_country","relation":"dominant_religion"}},"right":{{"value":"Christianity"}}}},
  {{"operator":"or","args":[0,1,2,3]}}
]}}

"Is it an island or does it border the Baltic Sea, but not both?" is XOR; duplicate
the predicates rather than reusing nodes:
{{"route":"local","plan":[
  {{"operator":"equals","left":{{"entity":"target_country","relation":"is_island"}},"right":{{"value":true}}}},
  {{"operator":"contains","left":{{"entity":"target_country","relation":"water_access"}},"right":{{"value":"Baltic Sea"}}}},
  {{"operator":"or","args":[0,1]}},
  {{"operator":"equals","left":{{"entity":"target_country","relation":"is_island"}},"right":{{"value":true}}}},
  {{"operator":"contains","left":{{"entity":"target_country","relation":"water_access"}},"right":{{"value":"Baltic Sea"}}}},
  {{"operator":"and","args":[3,4]}},
  {{"operator":"not","args":[5]}},
  {{"operator":"and","args":[2,6]}}
]}}

"Was it a founding EU member?" is valid but absent locally; "Is it important?" lacks
a criterion. Route the first fallback, the second clarify.

Final wire check: the plan is a TREE, not a DAG. Every non-root node is referenced
exactly once. Duplicate repeated predicates in separate branches; never reuse indices,
including for XOR. Identity typos AND quoted text patterns preserve original spelling.
Use children-before-parent order: node i may reference only earlier child indices.
In contains → not → any, nodes 0,1,2 use not.args=[0], any.args=[1], never [2].

User question: {question}
""".strip()


def _country_name_literals(node):
    if isinstance(node, list):
        for child in node:
            yield from _country_name_literals(child)
    elif isinstance(node, dict):
        left, right = node.get("left", {}), node.get("right", {})
        for reference, literal in ((left, right), (right, left)):
            relation = reference.get("relation")
            if node.get("operator") == "equals" and relation == "name" and "value" in literal:
                yield literal["value"]
        for child in node.values():
            yield from _country_name_literals(child)


_COUNTRY_LIST_RELATIONS = frozenset(LIST_RELATION_QUERIES) | {"region", "subregion"}
_DIRECTION_AXES = {
    "north_of": "coordinates.latitude", "south_of": "coordinates.latitude",
    "east_of": "coordinates.longitude", "west_of": "coordinates.longitude",
}


def _validate_country_plan(plan: dict, question: str) -> None:
    """Reject semantically impossible references before advertising local coverage."""
    def visit(node: dict, country_item: bool = False) -> bool:
        target = False
        for field in ("left", "right", "items"):
            operand = node.get(field, {})
            entity = operand.get("entity")
            target |= entity == "target_country"
            if entity == "item" and not country_item:
                raise ValueError("Item country facts require country-valued items")
        operator = node["operator"]
        if operator in _DIRECTION_AXES:
            axis = _DIRECTION_AXES[operator]
            for field in ("left", "right"):
                operand = node[field]
                if "entity" in operand:
                    if operand["relation"] != axis:
                        raise ValueError(f"{operator} requires {axis} operands")
                elif type(operand.get("value")) not in (int, float):
                    raise ValueError("Direction thresholds must be numeric")
        if operator == "contains":
            left, right = node["left"], node["right"]
            if left.get("relation") not in _COUNTRY_LIST_RELATIONS and not isinstance(left.get("value"), list):
                raise ValueError("contains requires a list on the left")
            if right.get("relation") in _COUNTRY_LIST_RELATIONS or isinstance(right.get("value"), list):
                raise ValueError("contains tests one value, not list intersection")
        if operator in {"any", "all"}:
            items = node["items"]
            literal = items.get("value")
            bound_countries = items.get("relation") == "borders_country" or (
                isinstance(literal, list) and all(
                    isinstance(value, str) and _norm(value) in _ENGLISH_COUNTRY_ALIASES
                    for value in literal
                )
            )
            target |= visit(node["condition"], bound_countries)
        elif operator == "not":
            target |= visit(node["condition"], country_item)
        elif operator in {"and", "or"}:
            for child in node["conditions"]:
                target |= visit(child, country_item)
        return target

    has_target = visit(plan)
    normalized = " ".join(_norm(question).split())
    hidden_subject = re.search(
        r"\b(?:it|its|itself|(?:(?:the|this|hidden|my|our|your) )country)\b", normalized,
    )
    subject = re.match(r"(?:is|are|was|were|does|do|did|can|will|would) (.+)", normalized)
    named_subject = subject is not None and any(
        subject[1] == alias or subject[1].startswith(alias + " ")
        for alias in _ENGLISH_COUNTRY_ALIASES
    )
    # Named objects/references remain literal; only subjects bind to the hidden target.
    if not has_target and (hidden_subject or named_subject):
        raise ValueError("A hidden-country subject must depend on the hidden target")


def analyze_question_for_local_plan(
    question: str, *, use_cache: bool = True, strict_errors: bool = False,
    evidence: dict | None = None,
) -> QuestionPlan:
    if evidence is not None:
        evidence.setdefault("attempts", [])
        evidence.setdefault("provider_attempts", len(evidence["attempts"]))
    template = None
    entity = compile_entity_question(question)
    if entity is not None:
        ast, improved_question = entity
    else:
        template = compile_template_plan(question, english_only=True)
        if template is not None:
            nodes, improved_question = template
            ast = compile_planner_response(
                {"route": "local", "plan": nodes},
                relations=set(SUPPORTED_RELATIONS), operators=PLANNER_OPERATORS | {"any", "all"},
                target_entity="target_country", allow_named_entities=True,
            )
    if entity is not None or template is not None:
        ast = local_answering.normalize_continent_unions(ast)
        if evidence is not None:
            evidence.update(
                provider="template", contract_version="countrydle-strict-v2", cache_hit=False,
            )
        return QuestionPlan(
            original_question=question, valid=True, supported=True,
            improved_question=improved_question, explanation=None, plan=ast,
        )

    from utils.plan_cache import plan_cache
    from utils.ai_clients import generate_gemini_json

    load_dotenv_if_present()
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or DEFAULT_MODEL
    # Cache/evidence identity combines shared contract, this mode's prompt, and model.
    version = f"{PLANNER_VERSION}:countrydle:{COUNTRYDLE_PROMPT_REVISION}:{model}"
    cached = plan_cache.get("countrydle", question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(provider="gemini", model=model, contract_version=version, cache_hit=cached is not None)
        evidence.setdefault("attempts", [])
        evidence.setdefault("provider_attempts", 0)
    if cached is not None:
        return replace(cached, original_question=question)
    from utils.water_hierarchy import is_multi_ocean_question, build_multi_ocean_plan
    if is_multi_ocean_question(question):
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=True,
            improved_question="Does the country have access to two or more oceans?",
            explanation=None,
            plan=build_multi_ocean_plan("target_country"),
        )
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        if strict_errors:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        return QuestionPlan(
            original_question=question,
            valid=True,
            supported=False,
            improved_question=None,
            explanation=None,
            plan=None,
            fallback_reason="GEMINI_API_KEY is not configured.",
        )

    prompt = build_planner_prompt(question)
    if evidence is not None:
        evidence.update(prompt=prompt, temperature=0, max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS)
    relations = set(SUPPORTED_RELATIONS) | {"coordinates.latitude", "coordinates.longitude", "region", "subregion"}
    operators = PLANNER_OPERATORS | {"any", "all"}
    schema = planner_response_schema(
        relations=relations, operators=operators, target_entity="target_country",
        allow_named_entities=True,
    )
    parsed = generate_gemini_json(
        prompt, model=model, api_key=api_key, max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
        timeout=30, evidence=evidence, response_schema=schema,
        thinking_budget=PLANNER_THINKING_BUDGET if model.startswith("gemini-2.5-flash-lite") else None,
    )
    try:
        ast = compile_planner_response(
            parsed, relations=relations, operators=operators, target_entity="target_country",
        allow_named_entities=True,
    )
        if ast is not None:
            ast = local_answering.normalize_continent_unions(ast)
            _validate_country_plan(ast, question)
    except Exception as exc:
        ast = None
        parsed = {
            "route": "fallback",
            "fallback_reason": f"Plan compilation failed: {exc}",
        }
    names = tuple(_country_name_literals(ast))
    if names and local_answering.DEFAULT_DB_PATH.exists():
        with sqlite3.connect(local_answering.DEFAULT_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            for name in names:
                if local_answering.find_country(conn, name) is None:
                    parsed = {
                        "route": "clarify",
                        "explanation": f"Please clarify which country you mean by {name!r}.",
                    }
                    ast = None
                    break
    # A paraphrase cannot silently remove the user's explicit logical grouping.
    improved_question = (
        question if "(" in question or ")" in question else parsed.get("improved_question")
    )

    plan = QuestionPlan(
        original_question=question,
        valid=parsed["route"] != "clarify",
        supported=parsed["route"] == "local",
        improved_question=improved_question,
        explanation=parsed.get("explanation"),
        plan=ast,
        fallback_reason=parsed.get("fallback_reason"),
    )
    if use_cache:
        plan_cache.set("countrydle", question, plan, version=version)
    return plan
