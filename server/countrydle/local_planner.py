"""Gemini-based planner for local Countrydle answering.

The planner does not answer the user's question. It validates and rewrites the
question, then returns a small execution plan that can be evaluated against the
local SQLite knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import sqlite3
from countrydle import local_answering
from countrydle.local_answering import LIST_RELATION_QUERIES
from planner_protocol import (
    PLANNER_MAX_OUTPUT_TOKENS, PLANNER_OPERATORS, PLANNER_RULES, PLANNER_THINKING_BUDGET, PLANNER_VERSION,
    compile_planner_response, planner_response_schema,
)


APP_DIR = Path(__file__).resolve().parent
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_MODEL = "gemini-2.5-flash-lite"

SUPPORTED_RELATIONS = [
    "name",
    "continent",
    "geographic_area",
    "borders_country",
    "water_access",
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
    relations = "\n".join(
        f"- {relation} ({'list' if relation in LIST_RELATION_QUERIES else 'scalar'})"
        for relation in SUPPORTED_RELATIONS
    )
    return f"""
Build an execution plan for a geography guessing game. Do NOT answer the question.
The hidden country is the subject. In game questions, "I", "we", "my country",
and "it" refer to that country, not the player's physical location.

Make ONE routing decision in this order:
1. Recover the intended yes/no proposition, translating to English if needed.
   Repair grammar, not an absent relationship or unspecified polarity.
   Missing auxiliaries, question marks and ordinary typos do not change validity.
   Descriptive fragments and conventional region adjectives ask whether the
   target has that property; they do not need to be complete sentences.
2. If the proposition still lacks a relation, polarity or objective criterion,
   choose route="clarify", plan=null, and explain what the player must specify.
   Also clarify genuinely open-ended, unrelated or nonsensical requests.
3. Otherwise the question is valid. If the listed facts AND available operators
   express its EXACT proposition, choose route="local" with a plan. If either
   facts or operations are missing, choose route="fallback", plan=null, and
   identify the missing capability in fallback_reason.
   Missing local coverage can NEVER turn this valid question into clarification.
   Territory, history, culture, people and landmarks are all legitimate subjects.
Unqualified size ("big", "small", "large"), proximity ("near", "close"), fame,
beauty, popularity, importance, being "good", and vague frequency/amount
("often", "a lot") require an objective criterion.
Neither a known area/ranking nor an example attraction supplies the missing criterion.
Do not replace proximity with bordering, fame with existence, or a major role
with participation or sovereign-state status.
Traditional or typical food is not a substitute for an unspecified eating frequency.
An ending "or not?" after a single predicate asks for that predicate's yes/no
answer; it does NOT negate it. A genuine "or" joining two different predicates
retains both branches, and an explicit negation inside either branch is preserved.

Correct a typo only when the predicate and polarity are recoverable. Do not add
a missing spatial relation: "not on the prime meridian" specifies a relation,
but "not the prime meridian" does not establish on/near/east/west/crosses.
Mixed-language fragments do not license inventing such a relation.
Standalone compass directions need a reference point or region. A north/south
part of Earth, the world, or the planet supplies a global frame and means the
Northern/Southern Hemisphere; a bare direction does not supply that frame.

Supported local relations:
{relations}

Important rules:
- Treat the user's input as language-agnostic. If it is not English, translate
  the meaning to English before producing any output fields.
- The JSON output must be English-only: improved_question, explanation,
  fallback_reason, plan literal values, country names, regions, organizations,
  water bodies, currencies, and languages must use common English names.
  Exception: preserve country-identity abbreviations and misspellings verbatim
  in plan literals so the deterministic country resolver can check ambiguity.
- The hidden country must be represented as entity "target_country".
- Use common English names for countries and objects, NOT official long names.
  Good: "China", "United States", "Czech Republic", "Baltic Sea", "EU".
  Bad: "People's Republic of China", "United States of America".
- For informal or non-English input, normalize values to common English names.
  Examples: "Bałtyk" -> "Baltic Sea", "Niemcy" -> "Germany", "UE" -> "EU".
- Comparing two entities uses a predicate with both entity references in the flat node array.
  Example: "west of China" means compare target_country.coordinates.longitude
  with China.coordinates.longitude.
- Coordinates use signed degrees: latitude is positive north and negative south;
  longitude is positive east and negative west. The Western Hemisphere has
  negative longitude, not positive longitude. Point coordinates do not establish
  the full territorial extent of a country.
- If a clear question can be answered only with external facts, return route="fallback"
  and plan=null. Local coverage does not determine whether the question is meaningful.
- Direct identity questions are valid and supported, including "Is it Poland?",
  "Czy to Polska?", and questions naming several candidate countries. Players
  may use their question allowance to check identity; do not reject these as
  guesses, cheating, or requests to reveal the answer, and do not redirect them
  to the guess field. The application, not the planner, enforces game limits.
  Identity must compare countries with countries. A sea, city, or geographic line
  is not a country candidate. Such a feature needs an explicit relationship
  (contains the city, borders the sea, lies on the line); do not invent that
  relationship or answer a nonsensical country-versus-feature identity comparison.
- For identity checks, compare target_country.name with the common English
  country name using "equals". For multiple candidates, combine those checks
  with "or"; preserve negation with "not" and other logical conditions.
  Example: "Is it Poland?" -> {{"operator": "equals",
  "left": {{"entity": "target_country", "relation": "name"}},
  "right": {{"value": "Poland"}}}}.
  For an abbreviated or misspelled country candidate, copy its original spelling
  into the identity literal; do NOT expand it or autocorrect it in the plan.
  The deterministic resolver handles aliases and unique spelling corrections.
  Translate correctly spelled foreign country names when unambiguous.
  Never replace an already valid country name with a similar country's name.
  For an identity question containing a candidate proper name, emit a local
  identity plan even if you do not recognize the spelling. Name recognition,
  uniqueness and rejection belong to the deterministic resolver, not the model.
  Do not reject a candidate merely because its spelling is unfamiliar.
  Open-ended requests such as "What country is it?" remain invalid.
- Use official_language for official, co-official, and otherwise legally
  recognized official country languages.
  Legal status does not establish how often a language is spoken. Questions about
  what people usually, predominantly, or widely speak require usage/prevalence
  evidence and must use fallback rather than substituting official_language.
  A main/dominant national language has an ordinary demographic meaning and is
  a valid general-knowledge predicate; do not demand an exact percentage merely
  because that prevalence is absent from SQLite. Language origins/families
  likewise require fallback, not rejection or an invented list of official languages.
  When regional origin modifies a country's main language, preserve both:
  a principal national language originating in that region. Do not rewrite it
  as a ranking of languages inside the region or demand an unspecified ranking.
- Use dominant_religion for the country's grouped dominant religion category.
  Allowed values are: Catholic, Orthodox, Protestant, Christianity, Islam,
  Judaism, Buddhism, Hinduism, Folk/Traditional religions, No religion, Mixed,
  Other. Use Mixed when the question asks whether the country is religiously mixed.
- Use government_type only for the stored broad government-form categories:
  Republic, Monarchy, Communist state, Theocracy, Military junta, Transitional
  government, Other. Democracy is NOT a synonym for Republic; constitutional
  monarchies can be democracies. Detailed political classifications absent from
  these broad categories must use fallback, not a substitute category.
- Do not invent unsupported relation names.
- Self-bordering rule: if the user asks whether the hidden country borders or
  neighbors itself / the same country, create a borders_country contains plan
  comparing against target_country.name; the executor treats this as true.

{PLANNER_RULES.replace("TARGET", "target_country")}

Allowed plan operators:
- "contains": left list relation contains right literal value
- "exists": left list/scalar relation has at least one known value / is true
- "equals": left scalar relation equals right literal value
  A list compared with equals to a string or boolean is NOT a membership/emptiness
  test and cannot be executed. Even a single official language or continent is a list.
  For a list use contains to test membership, or exists to test nonemptiness.
- A landlocked country has NO sea/ocean access: emit exists(water_access) followed
  by not referencing that node. Do not compare water_access with true/false.
- For an island country use equals(is_island, true). Sharing a land border on an
  island does not make a country continental.
- "greater_than": strict numeric comparison >
- "less_than": strict numeric comparison <
- "greater_than_or_equal": inclusive numeric comparison >=
- "less_than_or_equal": inclusive numeric comparison <=
- "west_of": left longitude < right longitude
- "east_of": left longitude > right longitude
- "north_of": left latitude > right latitude
- "south_of": left latitude < right latitude
- "any": any item from a list relation satisfies a nested condition
- "all": all items from a list relation satisfy a nested condition
- "or": at least one referenced predicate is true
- "and": every referenced predicate is true
- "not": negates its one referenced predicate
- "starts_with": left text starts with right literal text
- "ends_with": left text ends with right literal text
- "contains_text": left text contains right literal text
- "has_space": left text contains a space
- "has_hyphen": left text contains a hyphen (łącznik), not an en/em dash; no right operand
- "word_count_equals", "word_count_greater_than", "word_count_less_than"
- "char_count_equals", "char_count_greater_than", "char_count_less_than"

Super-region rules:
- Eurasia is not a stored continent value. Represent it as Europe OR Asia.
- The Americas is not a stored continent value. Represent it as North America OR South America.
- Do not use literal values "Eurasia" or "Americas" with the continent relation.
- For a geographic location question, unqualified "America" denotes the Americas
  (North America OR South America). Do not reject this conventional regional name
  as ambiguous or silently narrow it to the United States.
- The "geographic_area" relation combines broad regions and specific subregions.
  Use it for user-facing area questions such as "in Europe", "in the Americas",
  "in the Caribbean", "in Central Europe", "in the Balkans", or "in the Middle East".
  It is list-valued; use contains/exists, not equals. Broad stored values include
  "Africa", "Americas", "Asia", "Europe", and "Oceania". Specific stored values
  include examples such as "Caribbean", "Southern Africa", "Western Asia",
  "Central Europe", "South-Eastern Asia", "Baltic states", "Balkans", "Iberia",
  "Iberian Peninsula", and "Mediterranean".
- Preserve geographic qualifiers exactly. North America and South America are
  different continents; use continent contains the EXACT one asked about, not
  the broader geographic_area "Americas". Likewise do not drop north/south/east/west.
- Latin America is not equivalent to the Americas. Its cultural classification
  is not stored locally; use route="fallback", never replace it with "Americas".
- Distinguish "in Europe" (any European territory) from "entirely/fully/only in
  Europe". The latter is NOT a contains test. Precise territorial extent and
  hemisphere-crossing boundaries are not represented by a country point or a
  broad regional tag: use route="fallback" when that detail is required.
- The largest/smallest country in a group, ordinal rankings, continent-wide counts,
  and arbitrary historical periods require fallback. There is no global-country
  collection, ranking operator, or historical timeline in the plan language.
  Do not invent independent nodes or guess a comparison country as a shortcut.

Ethnic, linguistic group, and cultural family rules:
- Do NOT substitute geographic_area or official_language for ethnic/cultural or
  language-family categories such as Slavic, Germanic, Romance, Celtic, Turkic,
  Arab, Francophone, Anglophone, or Lusophone.
- Established regional/cultural labels remain valid in shorthand. In this
  geography game, "Latin country" denotes Latin America, not literal use of Latin.
  A regional label such as Nordic or Scandinavian is geographic, not automatically ethnic.
- When the exact requested category is not represented locally, return route="fallback",
  plan=null, with a fallback_reason naming the missing category.
  Do not reject a familiar category merely because its classification needs general knowledge.
Alphabet and Letter Range rules:
- When the user asks if the country name starts with a letter within an alphabet range (e.g. "from A to M", "between N and Z", "first half of the alphabet"):
  Use operator "or" with "starts_with" for EACH letter in the range (inclusive).
  NEVER combine single-letter starts_with conditions with "and".

Flag and historical union rules:
- Use "flag_color" for questions about colors on the national flag. Allowed values:
  "red", "white", "blue", "green", "yellow", "black", "orange".
  Use contains (e.g. {{"operator": "contains", "left": {{"entity": "target_country", "relation": "flag_color"}}, "right": {{"value": "red"}}}}).
- Use "flag_symbol" for questions about symbols or designs on the flag. Allowed values:
  "star", "stars", "cross", "crescent", "sun", "stripes", "circle", "eagle", "coat_of_arms".
  Use contains (e.g. {{"operator": "contains", "left": {{"entity": "target_country", "relation": "flag_symbol"}}, "right": {{"value": "star"}}}}).
- Use "historical_union" for PAST membership in the listed historical states,
  empires or unions. A dissolved organization's name does not by itself make
  a present-tense question historical.
  Allowed values: "USSR", "Yugoslavia", "Czechoslovakia", "Gran Colombia", "Austro-Hungarian Empire",
  "Warsaw Pact", "British Empire", "Spanish Empire", "French Empire", "Portuguese Empire", "Ottoman Empire".
  Use contains (e.g. {{"operator": "contains", "left": {{"entity": "target_country", "relation": "historical_union"}}, "right": {{"value": "USSR"}}}}).
- historical_union covers ONLY the named dissolved polities above. Absence of an
  unlisted union is missing coverage, not evidence of non-membership.
  Broader historical classifications such as the Eastern Bloc are not synonyms
  for one named treaty organization such as the Warsaw Pact; use fallback.
- Use membership for PRESENT membership, including a question about a dissolved
  organization. Never use past membership as evidence of current membership.
  "Currently belongs to" and "was part of" are different predicates, regardless
  of whether the organization still exists.
  A past-tense question about an active organization needs historical membership
  knowledge: use fallback unless the actual historical predicate is represented.
- Flag colors/symbols are presence lists, not surface-area percentages. Questions
  about a majority color, proportions, layout or exclusive colors require fallback.
Reference format:
{{"entity":"target_country", "relation":"name"}}
{{"entity":"target_country", "relation":"population"}}
{{"entity":"Germany", "relation":"area"}}
{{"entity":"target_country", "relation":"coordinates.longitude"}}
{{"entity":"item", "relation":"membership"}}
{{"value":"Baltic Sea"}}

Return compact STRICT JSON only. Required fields: route, plan.
Add improved_question only when translation or clarification is necessary.
For route="local", omit explanation and fallback_reason: the executor explains the facts.
For questions needing clarification, return route="clarify", plan=null and a short explanation.
The explanation must identify the missing predicate, reference, or criterion;
do not claim that an entire subject (such as landmarks) is an invalid question type.
For clear questions needing external facts, return route="fallback", plan=null and a short fallback_reason.
{{"route": "local", "plan": [{{...}}]}}

Examples:
User: Czy jest na zachód od Chin?
{{"route":"local","improved_question":"Is the country west of China?","plan":[
  {{"operator":"west_of","left":{{"entity":"target_country","relation":"coordinates.longitude"}},"right":{{"entity":"China","relation":"coordinates.longitude"}}}}
]}}

User: Czy graniczy z krajem należącym do UE?
{{"route":"local","improved_question":"Does the country border an EU member?","plan":[
  {{"operator":"contains","left":{{"entity":"item","relation":"membership"}},"right":{{"value":"EU"}}}},
  {{"operator":"any","items":{{"entity":"target_country","relation":"borders_country"}},"args":[0]}}
]}}

User: Czy leży w Eurazji?
{{"route":"local","improved_question":"Is the country in Eurasia?","plan":[
  {{"operator":"contains","left":{{"entity":"target_country","relation":"continent"}},"right":{{"value":"Europe"}}}},
  {{"operator":"contains","left":{{"entity":"target_country","relation":"continent"}},"right":{{"value":"Asia"}}}},
  {{"operator":"or","args":[0,1]}}
]}}

User: north america
{{"route":"local","improved_question":"Is the country in North America?","plan":[
  {{"operator":"contains","left":{{"entity":"target_country","relation":"continent"}},"right":{{"value":"North America"}}}}
]}}

User: Does it have an ocean coastline?
{{"route":"local","plan":[
  {{"operator":"contains","left":{{"entity":"target_country","relation":"water_access"}},"right":{{"value":"Ocean"}}}}
]}}

User: Does it have no coastline?
{{"route":"local","plan":[
  {{"operator":"exists","left":{{"entity":"target_country","relation":"water_access"}}}},
  {{"operator":"not","args":[0]}}
]}}

User: Were the 2004 Summer Olympics held in this country?
{{"route":"fallback","plan":null,"fallback_reason":"The local relations do not store event venues."}}
The event and year are precise. Missing event data means unsupported, NOT invalid.

User: Did it have an important role in the Cold War?
{{"route":"clarify","plan":null,"explanation":"Please define a measurable criterion for an important role, or ask about a specific event or alliance."}}
Participation in a historical event does not establish its importance.

User: Are its mountains beautiful?
{{"route":"clarify","plan":null,"explanation":"Please specify an objective criterion for beauty."}}

User: Is its area large?
{{"route":"clarify","plan":null,"explanation":"Please specify an area threshold or comparison country."}}
These are invalid because their criteria are undefined, not because local facts are missing.

User: Is it near Finland?
{{"route":"clarify","plan":null,"explanation":"Please specify a distance threshold or ask about a shared border."}}

User: Does it speak an Asian main language?
{{"fallback_reason":"Principal national language usage and language origin require general knowledge.","route":"fallback","plan":null}}
This asks about the origin of a main language used by the country, not a ranking of languages.

User: it it isn't the meridian
{{"explanation":"Please specify the relationship to the meridian: on, near, east, west, or crossing it.","route":"clarify","plan":null}}
Removing a repeated verb is harmless, but inserting a spatial relationship changes the predicate.

Before returning JSON, verify that the rewrite and plan preserve the intended
original proposition, including its polarity, qualifiers and logical conditions.
The plan must answer that proposition, not its opposite or a weaker substitute.
Do not reject a recovered yes/no proposition because of its original grammar,
pronouns, or missing local facts; only unresolved meaning requires clarification.

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


def analyze_question_for_local_plan(
    question: str, *, use_cache: bool = True, strict_errors: bool = False,
    evidence: dict | None = None,
) -> QuestionPlan:
    from utils.plan_cache import plan_cache
    from utils.ai_clients import generate_gemini_json

    load_dotenv_if_present()
    model = os.getenv("LOCAL_QUESTION_MODEL") or os.getenv("GEMINI_QUESTION_MODEL") or DEFAULT_MODEL
    version = f"{PLANNER_VERSION}:{model}"
    from countrydle.template_compiler import check_open_ended_question, compile_template_plan
    clarify_msg = check_open_ended_question(question)
    if clarify_msg is not None:
        plan = QuestionPlan(
            original_question=question,
            valid=False,
            supported=False,
            improved_question=None,
            explanation=clarify_msg,
            plan=None,
        )
        if use_cache:
            plan_cache.set("countrydle", question, plan, version=version)
        if evidence is not None:
            evidence.update(provider="template_clarify", model=None, contract_version=PLANNER_VERSION, cache_hit=False)
        return plan
    deterministic = compile_template_plan(question)
    if deterministic is not None:
        ast, improved = deterministic
        plan = QuestionPlan(
            original_question=question,
            valid=True,
            supported=True,
            improved_question=improved,
            explanation="Deterministic template match.",
            plan=ast,
        )
        if use_cache:
            plan_cache.set("countrydle", question, plan, version=version)
        if evidence is not None:
            evidence.update(provider="template", model=None, contract_version=PLANNER_VERSION, cache_hit=False)
        return plan
    cached = plan_cache.get("countrydle", question, version=version) if use_cache else None
    if evidence is not None:
        evidence.update(provider="gemini", model=model, contract_version=PLANNER_VERSION, cache_hit=cached is not None)
    if cached is not None:
        return replace(cached, original_question=question)
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
    ast = compile_planner_response(
        parsed, relations=relations, operators=operators, target_entity="target_country",
        allow_named_entities=True,
    )
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

    plan = QuestionPlan(
        original_question=question,
        valid=parsed["route"] != "clarify",
        supported=parsed["route"] == "local",
        improved_question=parsed.get("improved_question"),
        explanation=parsed.get("explanation"),
        plan=ast,
        fallback_reason=parsed.get("fallback_reason"),
    )
    if use_cache:
        plan_cache.set("countrydle", question, plan, version=version)
    return plan
