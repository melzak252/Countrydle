"""English fast paths must account for the complete question's meaning."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sqlite3
import pytest

from countrydle import local_answering, local_planner, template_compiler, utils


@pytest.mark.parametrize("question, relation, value", [
    ("Is it Italy?", "name", "Italy"),
    ("Italy?", "name", "Italy"),
    ("Is it South Africa?", "name", "South Africa"),
    ("Is it in Europe?", "continent", "Europe"),
    ("Is it in Micronesia?", "geographic_area", "Micronesia"),
    ("Is it Micronesia?", "name", "Federated States of Micronesia"),
])
def test_entity_identity_and_location_are_distinct(question, relation, value):
    node, _ = template_compiler.compile_entity_question(question)
    assert node == {
        "operator": "equals" if relation == "name" else "contains",
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


@pytest.mark.parametrize("question", [
    "Is it in Italy?", "In Italy?", "Is the country in France?",
    "Is it in South Africa?", "Is it in Congo?", "America?", "Congo?",
    "Is it Italy and France?", "Is it not Italy?", "Is it entirely in Europe?",
    "Is it in Europe; is it an island?", "Is it Ⅰtaly?", "I\u0338taly?",
])
def test_entity_compiler_declines_containment_ambiguity_and_modifiers(question):
    assert template_compiler.compile_entity_question(question) is None


@pytest.mark.parametrize("question", [
    "Does it border Germany or France?", "Does it border Germany and Poland?",
    "Does it border Germany north of Austria?", "Is it an island in Europe?",
    "Is it entirely in the Northern Hemisphere?", "Is it mostly landlocked?",
    "Does it have a coastline only?", "Does it have access to the Baltic Sea in winter?",
    "Does it border Germany; does it border France?", "Is it an island not?",
    "Is it formerly an island?", "Does it border -Germany?",
    "Does it border Germany > France?", "Is it Ⅰsland?", "Is it an i\u0338sland?",
])
def test_templates_decline_unparsed_meaning(question):
    assert template_compiler.compile_template_plan(question) is None


@pytest.fixture
def offline_planner(monkeypatch):
    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def semantic_facts(tmp_path, monkeypatch):
    path = tmp_path / "country_facts.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE countries (
                id INTEGER PRIMARY KEY, app_country_name TEXT, official_name TEXT,
                is_island INTEGER
            );
            INSERT INTO countries VALUES
                (1, 'Italy', 'Italian Republic', 0),
                (2, 'Vatican City', 'Vatican City State', 0),
                (3, 'Kiribati', 'Republic of Kiribati', 1),
                (4, 'Federated States of Micronesia', 'Federated States of Micronesia', 1);
            CREATE TABLE country_water_access (country_id INTEGER, water_body TEXT);
            INSERT INTO country_water_access VALUES (1, 'Mediterranean Sea'), (3, 'Pacific Ocean');
            CREATE TABLE country_continents (country_id INTEGER, continent TEXT);
            INSERT INTO country_continents VALUES (1, 'Europe'), (2, 'Europe'), (3, 'Oceania');
            CREATE TABLE country_subregions (country_id INTEGER, subregion_name TEXT);
            INSERT INTO country_subregions VALUES (3, 'Micronesia'), (4, 'Micronesia');
            CREATE TABLE country_regions (country_id INTEGER, region_name TEXT);
            INSERT INTO country_regions VALUES (3, 'Oceania'), (4, 'Oceania');
            CREATE TABLE country_hemispheres (country_id INTEGER, hemisphere TEXT);
            INSERT INTO country_hemispheres VALUES
                (1, 'Northern'), (2, 'Northern'), (3, 'Northern'), (3, 'Southern');
        """)
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", path)


@pytest.mark.parametrize("question, target, expected", [
    ("Is it Italy?", "Italy", True),
    ("Is it Italy?", "Vatican City", False),
    ("Is it in Europe?", "Vatican City", True),
    ("Is it in Micronesia?", "Kiribati", True),
    ("Is it Micronesia?", "Kiribati", False),
    ("Is it landlocked?", "Vatican City", True),
    ("Is it landlocked?", "Italy", False),
    ("Does it have a coastline?", "Italy", True),
    ("Does it cross the equator?", "Kiribati", True),
    ("Does it straddle the equator?", "Italy", False),
])
def test_active_planner_answers_exact_predicates_offline(offline_planner, semantic_facts, question, target, expected):
    plan = local_planner.analyze_question_for_local_plan(question, use_cache=False, strict_errors=True)
    assert plan.valid and plan.supported
    answer = local_answering.execute_local_plan(plan.plan, target, plan.improved_question)
    assert answer.answer is expected


@pytest.mark.parametrize("question", [
    "Is it in Italy?", "In Italy?", "Is it in South Africa?",
    "Does it border Germany and France?", "Does it border Germany north of Austria?",
    "Is it entirely in the Northern Hemisphere?", "Is it an island in Europe?",
    "Czy leży w Europie?",  # No newly activated Polish fast path.
])
def test_active_planner_declines_complex_and_country_containment_queries(offline_planner, question):
    plan = local_planner.analyze_question_for_local_plan(question, use_cache=False)
    assert plan.valid and not plan.supported
    assert plan.plan is None
    assert plan.improved_question is None


@pytest.mark.parametrize("question, target, expected", [
    ("Is it landlocked?", "Vatican City", True),
    ("Is it landlocked?", "Italy", False),
    ("Does it have a coastline?", "Italy", True),
    ("Is it Italy?", "Italy", True),
])
def test_local_player_response_preserves_predicate_and_hides_target(
    monkeypatch, offline_planner, semantic_facts, question, target, expected,
):
    monkeypatch.setattr(utils.CountryRepository, "get", AsyncMock(return_value=SimpleNamespace(
        name=target, official_name="Italian Republic" if target == "Italy" else "Vatican City State",
    )))
    response, plan = asyncio.run(utils.analyze_and_answer_locally(
        question, SimpleNamespace(id=1, country_id=1), None, AsyncMock(),
    ))
    assert response.answer is expected
    assert target.casefold() not in response.explanation.casefold()
    assert response.question == plan.improved_question
    if "landlocked" in question:
        assert "landlocked" in response.question
        assert "not" == plan.plan["operator"]
    else:
        assert response.answer is True


def test_local_response_redacts_common_and_official_names(monkeypatch, offline_planner):
    monkeypatch.setattr(utils.CountryRepository, "get", AsyncMock(return_value=SimpleNamespace(
        name="Italy", official_name="Italian Republic",
    )))
    monkeypatch.setattr(utils, "execute_local_plan", lambda *args: local_answering.LocalAnswer(
        question="Does the country have a coastline?", answer=True, relation="water_access",
        explanation="Italy's coastline gives the Italian Republic access to the Mediterranean Sea.",
    ))
    response, _ = asyncio.run(utils.analyze_and_answer_locally(
        "Does it have a coastline?", SimpleNamespace(id=1, country_id=1), None, AsyncMock(),
    ))
    assert "Italy" not in response.explanation
    assert "Italian Republic" not in response.explanation
    assert "Mediterranean Sea" in response.explanation


def predicate_node(operator, relation, value=None):
    node = {"operator": operator, "left": {"entity": "target_country", "relation": relation}}
    if value is not None:
        node["right"] = {"value": value}
    return node


def supported_english_bases():
    """Cover every whitelisted skeleton and finite water/hemisphere choice."""
    for subject in ("it", "the country"):
        for prefix in ("", "the country "):
            yield f"Does {subject} border {prefix}Germany", "border Germany", [
                predicate_node("contains", "borders_country", "Germany"),
            ]
        for suffix in ("", " country"):
            yield f"Is {subject} an island{suffix}", f"an island{suffix}", [
                predicate_node("equals", "is_island", True),
            ]
        for article in ("", "a "):
            yield f"Does {subject} have {article}coastline", "have a coastline", [
                predicate_node("exists", "water_access"),
            ]
        yield f"Is {subject} landlocked", "landlocked", [
            predicate_node("exists", "marine_access"), {"operator": "not", "args": [0]},
        ]
        for hemi in ("Northern", "Southern", "Eastern", "Western"):
            yield f"Is {subject} in the {hemi} Hemisphere", f"in the {hemi} Hemisphere", [
                predicate_node("contains", "hemisphere", hemi),
            ]
        for verb in ("cross", "straddle"):
            yield f"Does {subject} {verb} the equator", f"{verb} the equator", [
                predicate_node("contains", "hemisphere", "Northern"),
                predicate_node("contains", "hemisphere", "Southern"),
                {"operator": "and", "args": [0, 1]},
            ]
        for direction, hemi in (("north", "Northern"), ("south", "Southern")):
            yield f"Is {subject} {direction} of the equator", f"{direction} of the equator", [
                predicate_node("contains", "hemisphere", hemi),
            ]
        for water in (
            "Ocean", "Sea", "Baltic Sea", "Mediterranean Sea", "Black Sea", "North Sea",
            "Red Sea", "Caribbean Sea", "Indian Ocean", "Atlantic Ocean", "Pacific Ocean",
            "Arctic Ocean", "Adriatic Sea",
        ):
            expected = [predicate_node("contains", "water_access", water)]
            for verb in ("border", "have access to"):
                for article in ("", "the "):
                    yield f"Does {subject} {verb} {article}{water}", f"{verb} the {water}", expected
            yield f"Is {subject} on the {water}", f"on the {water}", expected
        yield f"Does {subject} have access to the Mediterranean", "have access to the Mediterranean", [
            predicate_node("contains", "water_access", "Mediterranean Sea"),
        ]
    for base, predicate, operator, relation, value in (
        ("is island", "an island", "equals", "is_island", True),
        ("has coast", "have a coastline", "exists", "water_access", None),
        ("has sea", "have a coastline", "exists", "water_access", None),
        ("is coastal", "coastal", "exists", "water_access", None),
        ("is it coastal", "coastal", "exists", "water_access", None),
        ("Italy", "Italy", "equals", "name", "Italy"),
        ("Is this Italy", "Italy", "equals", "name", "Italy"),
        ("Is it in Europe", "in Europe", "contains", "continent", "Europe"),
        ("In Europe", "in Europe", "contains", "continent", "Europe"),
        ("Is it in Micronesia", "in Micronesia", "contains", "geographic_area", "Micronesia"),
        ("Is it Micronesia", "Micronesia", "equals", "name", "Federated States of Micronesia"),
        ("Is it in Central Europe", "in Central Europe", "contains", "geographic_area", "Central Europe"),
    ):
        yield base, predicate, [predicate_node(operator, relation, value)]
    for entity, continents in (
        ("Eurasia", ("Europe", "Asia")), ("the Americas", ("North America", "South America")),
    ):
        yield f"Is it in {entity}", f"in {entity}", [{
            "operator": "or",
            "conditions": [predicate_node("contains", "continent", continent) for continent in continents],
        }]
    for relation in ("population", "area"):
        for comparison, operator in (("greater", "greater_than"), ("less", "less_than")):
            yield (
                f"Does France have a {relation} {comparison} than Germany",
                f"have a {relation} {comparison} than Germany",
                [{"operator": operator,
                  "left": {"entity": "target_country", "relation": relation},
                  "right": {"entity": "Germany", "relation": relation}}],
            )
    for direction, relation in (("north", "coordinates.latitude"), ("south", "coordinates.latitude"),
                                ("east", "coordinates.longitude"), ("west", "coordinates.longitude")):
        yield (
            f"Is the hidden country {direction} of France", f"{direction} of France",
            [{"operator": f"{direction}_of",
              "left": {"entity": "target_country", "relation": relation},
              "right": {"entity": "France", "relation": relation}}],
        )
    nodes = []
    groups = []
    for continent in ("Europe", "Asia", "Africa", "North America", "South America",
                      "Oceania", "Antarctica"):
        index = len(nodes)
        nodes.extend([
            predicate_node("contains", "continent", continent),
            {"operator": "contains", "left": {"entity": "France", "relation": "continent"},
             "right": {"value": continent}},
            {"operator": "and", "args": [index, index + 1]},
        ])
        groups.append(index + 2)
    nodes.append({"operator": "or", "args": groups})
    yield "Does it share a continent with France", "share a continent with France", nodes


ENGLISH_BASES = list(supported_english_bases())


@pytest.mark.parametrize("base, predicate, expected", ENGLISH_BASES, ids=[row[0] for row in ENGLISH_BASES])
def test_unmodified_english_skeletons_have_exact_operator_coverage(base, predicate, expected):
    nodes, _ = template_compiler.compile_template_plan(f"{base}?")
    assert nodes == expected


def semantic_perturbations(base, predicate):
    yield f"{base} and does it border France?"
    yield f"{base} or Germany?"
    yield f"{base} as well as Spain?"
    yield f"Either {base} or is it an island?"
    yield f"{base} or not?"
    yield f"Is it not {predicate}?"
    yield f"{base} not?"
    yield f"Doesn't it {predicate}?"
    for qualifier in ("only", "entirely", "mostly", "all"):
        yield f"{base} {qualifier}?"
    yield f"Was it {predicate} in 1990?"
    yield f"Was {base} ever?"
    yield f"Formerly {base}?"
    yield f"Does the country that borders Canada {predicate}?"
    yield f"{base}; does it border France?"
    yield f"{base}. Also Spain?"
    for connective in ("never", "neither", "nor", "but", "except", "without"):
        yield f"{base} {connective} France?"
    for comparator in ("<", ">", "<=", ">=", "-"):
        yield f"{base} {comparator} 5?"


PERTURBED_QUESTIONS = [
    question for base, predicate, _ in ENGLISH_BASES
    for question in semantic_perturbations(base, predicate)
]


@pytest.mark.parametrize("question", PERTURBED_QUESTIONS)
def test_semantic_perturbations_never_compile_partial_predicates(question):
    assert template_compiler.compile_entity_question(question) is None
    assert template_compiler.compile_template_plan(question) is None


@pytest.mark.parametrize("question, bound", [
    ("Was France an EU member in 2010?", "Was the country an EU member in 2010?"),
    ("Does France have more inhabitants than Germany?", "Does the country have more inhabitants than Germany?"),
    ("Does France border France?", "Does the country border France?"),
    ("Doesn't France border Germany or Poland?", "Doesn't the country border Germany or Poland?"),
    ("Is the UK entirely in the Northern Hemisphere?", "Is the country entirely in the Northern Hemisphere?"),
    ("Does South Africa have a larger area than South Sudan?", "Does the country have a larger area than South Sudan?"),
    ("Was Côte d'Ivoire a member of the EU in 2010?", "Was the country a member of the EU in 2010?"),
    ("Does France have 'France' in its name?", "Does the country have 'France' in its name?"),
])
def test_fallback_subject_binding_preserves_references_and_complete_predicate(question, bound):
    # These strings specify entity roles and retained logic, not display formatting.
    assert template_compiler._bind_named_country_subject(question) == bound


@pytest.mark.parametrize("question", [
    "Is the population of France greater than the population of Germany?",
    "Is France's population greater than Germany's?",
    "Is the US dollar an official currency in El Salvador?",
    "Is the China Sea connected to the Pacific Ocean?",
    "Is 'France' part of its name?",
    "Is it France?",
    "France?",
    "Czy Francja ma więcej mieszkańców niż Niemcy?",
])
def test_fallback_subject_binding_does_not_rebind_literals_or_other_language(question):
    assert template_compiler._bind_named_country_subject(question) == question


@pytest.mark.parametrize("question", [
    "Is the Jordan River in Asia?",
    "Is the Panama Canal in North America?",
    "Is the Canada goose native to Europe?",
])
def test_fallback_subject_binding_keeps_named_feature_and_species_subjects_literal(question):
    assert template_compiler._bind_named_country_subject(question) == question
