import pathlib

import pytest

from countrydle import local_planner
from countrydle import local_answering
from countrydle.local_answering import LocalCountryFacts, execute_local_plan


_TEST_DIR = pathlib.Path(__file__).resolve().parent
_DATA_DIR = _TEST_DIR.parent / "data" if (_TEST_DIR.parent / "data").exists() else _TEST_DIR.parents[1] / "data"
DB_PATH = _DATA_DIR / "country_facts.sqlite"


pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="Countrydle local SQLite KB is missing")

# The application resolves the DB path differently depending on whether it runs
# from Docker or local development. These tests intentionally exercise the real
# repository KB generated under <repo>/data.
local_answering.DEFAULT_DB_PATH = DB_PATH


def contains_plan(relation: str, value: str) -> dict:
    return {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


def exists_plan(relation: str) -> dict:
    return {
        "operator": "exists",
        "left": {"entity": "target_country", "relation": relation},
    }


def scalar_plan(operator: str, relation: str, value) -> dict:
    return {
        "operator": operator,
        "left": {"entity": "target_country", "relation": relation},
        "right": {"value": value},
    }


def local_answer(plan: dict, country: str = "Poland"):
    return execute_local_plan(
        plan,
        country,
        "Test question?",
    )


@pytest.mark.parametrize("name,country", [
    ("Antigua", "Antigua and Barbuda"),
    ("Antugua", "Antigua and Barbuda"),
    ("Antigua & Barbdua", "Antigua and Barbuda"),
    ("St Kitis", "Saint Kitts and Nevis"),
    ("Saint Kitts", "Saint Kitts and Nevis"),
    ("Nigeira", "Nigeria"),
])
def test_country_identity_resolves_aliases_and_single_edit_typos(name, country):
    plan = scalar_plan("equals", "name", name)
    assert local_answer(plan, country).answer is True
    assert local_answer(plan, "Poland").answer is False


@pytest.mark.parametrize("name", ["Antzzq", "Nigeri", "Saint", "target_country", "item"])
def test_unresolved_country_identity_stays_unknown_under_negation(name):
    plan = scalar_plan("equals", "name", name)
    assert local_answer(plan, "Nigeria") is None
    assert local_answer({"operator": "not", "condition": plan}, "Nigeria") is None
    assert local_answer(contains_plan("borders_country", name), "Nigeria") is None


def test_name_compared_with_capital_remains_a_text_comparison():
    plan = {
        "operator": "equals",
        "left": {"entity": "target_country", "relation": "name"},
        "right": {"entity": "target_country", "relation": "capital"},
    }
    assert local_answer(plan, "Singapore").answer is True
    assert local_answer(plan, "Poland").answer is False


def test_resolved_border_name_preserves_the_self_border_rule():
    plan = contains_plan("borders_country", "St Kitis")
    assert local_answer(plan, "Saint Kitts and Nevis").answer is True
    assert local_answer(plan, "Dominica").answer is False


@pytest.mark.parametrize("name,country", [
    ("Dominica", "Dominica"),
    ("Dominican Republic", "Dominican Republic"),
    ("Dominika", "Dominica"),
    ("Dominikana", "Dominican Republic"),
    ("Niger", "Niger"),
    ("Nigeria", "Nigeria"),
    ("Guinea", "Guinea"),
    ("Guinea-Bissau", "Guinea-Bissau"),
    ("Equatorial Guinea", "Equatorial Guinea"),
    ("Papua New Guinea", "Papua New Guinea"),
])
def test_exact_country_identity_wins_over_similar_names(name, country):
    plan = scalar_plan("equals", "name", name)
    for target in ("Dominica", "Dominican Republic", "Niger", "Nigeria", "Guinea",
                   "Guinea-Bissau", "Equatorial Guinea", "Papua New Guinea"):
        assert local_answer(plan, target).answer is (target == country)


def test_planner_rejects_unresolved_identity_instead_of_sending_it_to_fallback(monkeypatch):
    from utils import ai_clients

    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setattr(ai_clients, "generate_gemini_json", lambda *args, **kwargs: {
        "route": "local",
        "plan": [scalar_plan("equals", "name", "Antzzq")],
    })
    plan = local_planner.analyze_question_for_local_plan("Are you Antzzq?", use_cache=False)
    assert plan.valid is False
    assert plan.supported is False
    assert plan.plan is None


@pytest.mark.parametrize("country,relation,value", [
    ("France", "continent", "Europe"),
    ("Costa Rica", "official_language", "Spanish"),
    ("Mali", "water_access", False),
])
def test_list_scalar_equality_abstains_instead_of_inventing_false(country, relation, value):
    plan = scalar_plan("equals", relation, value)
    assert local_answer(plan, country) is None
    assert local_answer({"operator": "not", "condition": plan}, country) is None


def test_unrepresented_historical_union_is_unknown_not_a_negative_fact():
    assert local_answer(contains_plan("historical_union", "Benelux"), "Netherlands") is None
    assert local_answer(contains_plan("historical_union", "USSR"), "Poland").answer is False


def test_current_membership_does_not_include_dissolved_unions():
    assert local_answer(contains_plan("membership", "USSR"), "Russia").answer is False
    assert local_answer(contains_plan("historical_union", "USSR"), "Russia").answer is True


def test_landlocked_negation_explains_actual_coastline_not_opposite_predicate():
    plan = {"operator": "not", "condition": exists_plan("water_access")}
    coastal = local_answer(plan, "Poland")
    inland = local_answer(plan, "Mali")
    assert coastal.answer is False
    assert "Baltic Sea" in coastal.explanation
    assert "completely landlocked" not in coastal.explanation
    assert inland.answer is True
    assert "landlocked" in inland.explanation


def test_island_false_literal_explanation_describes_fact_not_predicate_result():
    plan = scalar_plan("equals", "is_island", False)
    island = local_answer(plan, "Japan")
    mainland = local_answer(plan, "Poland")
    assert island.answer is False
    assert "is an island" in island.explanation
    assert "continental" not in island.explanation
    assert mainland.answer is True
    assert "not an island" in mainland.explanation


def test_named_reference_explanation_uses_evaluated_entity():
    plan = {"operator": "contains",
            "left": {"entity": "France", "relation": "continent"},
            "right": {"value": "Europe"}}
    result = local_answer(plan, "Japan")
    assert result.answer is True
    assert "France" in result.explanation
    assert "Japan" not in result.explanation


def test_inclusive_numeric_comparisons_keep_equality_and_direction():
    for operator, excluded_threshold in (("less_than_or_equal", 1.0), ("greater_than_or_equal", 1.5)):
        plan = {"operator": operator, "left": {"value": 1.25}, "right": {"value": 1.25}}
        result = local_answer(plan)
        assert result is not None
        assert result.answer is True
        plan["right"] = {"value": excluded_threshold}
        assert local_answer(plan).answer is False


def test_hyphen_predicate_distinguishes_names_and_dashes():
    plan = {"operator": "has_hyphen", "left": {"entity": "target_country", "relation": "name"}}
    result = local_answer(plan, "Guinea-Bissau")
    assert result is not None
    assert result.answer is True
    assert local_answer(plan, "Poland").answer is False
    assert local_answer({"operator": "has_hyphen", "left": {"value": "North–South"}}).answer is False


def test_negated_hyphen_name_explains_actual_name_pattern():
    result = local_answer(
        {
            "operator": "not",
            "condition": {
                "operator": "has_hyphen",
                "left": {"entity": "target_country", "relation": "name"},
            },
        },
        "Poland",
    )

    assert result.answer is True
    assert "does not contain a hyphen" in result.explanation


@pytest.mark.parametrize("operator,relation,value", [
    ("contains", "membership", "EU"),
    ("contains", "geographic_area", "Europe"),
    ("contains", "flag_color", "red"),
    ("equals", "name", "Poland"),
])
def test_negated_known_facts_do_not_explain_the_opposite_answer(operator, relation, value):
    result = local_answer({"operator": "not", "condition": scalar_plan(operator, relation, value)}, "Poland")
    assert result.answer is False
    assert not result.explanation.startswith("Yes")
    assert "Poland" in result.explanation
    assert value in result.explanation

def test_quantified_membership_explanations_use_bound_neighbor_facts():
    membership = {
        "operator": "contains",
        "left": {"entity": "item", "relation": "membership"},
        "right": {"value": "EU"},
    }
    borders = {"entity": "target_country", "relation": "borders_country"}
    any_eu_neighbor = {"operator": "any", "items": borders, "condition": membership}
    all_eu_neighbors = {"operator": "all", "items": borders, "condition": membership}

    positive = local_answer(any_eu_neighbor, "Poland")
    negative_any = local_answer(any_eu_neighbor, "Mongolia")
    negative_all = local_answer(all_eu_neighbors, "Poland")

    assert positive.answer is True
    assert any(neighbor in positive.explanation for neighbor in ("Germany", "Czech Republic", "Slovakia", "Lithuania"))
    assert "member of EU" in positive.explanation
    assert negative_any.answer is False
    assert "Russia" in negative_any.explanation and "China" in negative_any.explanation
    assert negative_all.answer is False
    assert "not a member of EU" in negative_all.explanation
    assert any(neighbor in negative_all.explanation for neighbor in ("Ukraine", "Belarus", "Russia"))


def test_literal_punctuation_is_not_an_empty_text_predicate():
    plan = scalar_plan("contains_text", "name", "-")
    assert local_answer(plan, "Poland").answer is False
    assert local_answer(plan, "Guinea-Bissau").answer is True


@pytest.mark.parametrize(
    ("country", "subregion"),
    [
        ("Poland", "Central Europe"),
        ("Poland", "Eastern Europe"),
        ("Lithuania", "Baltic states"),
        ("Lithuania", "Northern Europe"),
        ("Montenegro", "Balkans"),
        ("Montenegro", "Southern Europe"),
        ("Portugal", "Iberia"),
        ("Portugal", "Iberian Peninsula"),
        ("Portugal", "Mediterranean"),
        ("Croatia", "Balkans"),
        ("Croatia", "Central Europe"),
        ("Cambodia", "South-Eastern Asia"),
        ("Cambodia", "Southeast Asia"),
        ("United Arab Emirates", "Arabian Peninsula"),
        ("United Arab Emirates", "Middle East"),
        ("United Arab Emirates", "Western Asia"),
        ("Somalia", "Horn of Africa"),
    ],
)
def test_country_subregion_contains_expected_labels(country, subregion):
    answer = local_answer(contains_plan("subregion", subregion), country)

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "geographic_area"


@pytest.mark.parametrize(
    ("country", "subregion"),
    [
        ("Poland", "Balkans"),
        ("United Arab Emirates", "South-Eastern Asia"),
        ("Cambodia", "Middle East"),
        ("Somalia", "Arabian Peninsula"),
        ("India", "Western Asia"),
    ],
)
def test_country_subregion_rejects_wrong_labels(country, subregion):
    answer = local_answer(contains_plan("subregion", subregion), country)

    assert answer is not None
    assert answer.answer is False


@pytest.mark.parametrize(
    ("country", "region"),
    [
        ("Poland", "Europe"),
        ("Cambodia", "Asia"),
        ("United Arab Emirates", "Asia"),
        ("Australia", "Oceania"),
        ("Brazil", "Americas"),
    ],
)
def test_country_region_contains_expected_broad_regions(country, region):
    answer = local_answer(contains_plan("region", region), country)

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "geographic_area"


@pytest.mark.parametrize(
    ("country", "region"),
    [
        ("Mauritius", "East Africa"),
        ("Mauritius", "Eastern Africa"),
        ("Poland", "East Europe"),
        ("Japan", "East Asia"),
        ("Canada", "North America"),
        ("Brazil", "South America"),
    ],
)
def test_cardinal_region_names_match_canonical_geographic_areas(country, region):
    answer = local_answer(contains_plan("region", region), country)
    assert answer is not None
    assert answer.answer is True


def test_southern_africa_does_not_mean_south_africa_country():
    answer = local_answer(contains_plan("region", "Southern Africa"), "South Africa")
    assert answer is not None
    assert answer.answer is True
    assert local_answer(contains_plan("region", "South Africa"), "Namibia") is None


def test_geographic_area_does_not_drop_an_unrepresented_qualifier():
    assert local_answer(contains_plan("geographic_area", "coastal Europe"), "Austria") is None


def test_geographic_areas_use_the_exact_narrower_classification():
    assert local_answer(contains_plan("geographic_area", "Scandinavia"), "Finland").answer is False
    assert local_answer(contains_plan("geographic_area", "Middle East"), "Egypt").answer is True


def test_geographic_area_uses_complete_continental_coverage():
    assert local_answer(contains_plan("region", "North America"), "Jamaica").answer is True
    assert local_answer(contains_plan("region", "South America"), "Jamaica").answer is False


def test_generic_ocean_access_uses_named_direct_coastline():
    ocean_plan = contains_plan("water_access", "ocean")

    morocco = local_answer(ocean_plan, "Morocco")
    assert morocco is not None
    assert morocco.answer is True
    assert "Atlantic Ocean" in morocco.explanation
    assert "coastline access to: Ocean" not in morocco.explanation

    inland = local_answer(ocean_plan, "Czech Republic")
    assert inland is not None
    assert inland.answer is False
    assert "landlocked" in inland.explanation

    baltic = local_answer(contains_plan("water_access", "Atlantic Ocean"), "Poland")
    assert baltic is not None
    assert baltic.answer is False
    assert "Baltic Sea" in baltic.explanation


def test_oceania_and_polynesia_current_game_country_coverage():
    facts = LocalCountryFacts(db_path=DB_PATH)

    for country in ["Australia", "New Zealand", "Samoa", "Tonga", "Tuvalu", "Fiji"]:
        answer = facts.try_answer("Is the country in Oceania?", country)
        assert answer is not None, country
        assert answer.answer is True, country

    for country in ["New Zealand", "Samoa", "Tonga", "Tuvalu"]:
        answer = facts.try_answer("Is the country in Polynesia?", country)
        assert answer is not None, country
        assert answer.answer is True, country


@pytest.mark.parametrize(
    ("country", "question"),
    [
        ("Portugal", "Is the country Mediterranean?"),
        ("Portugal", "Is the country in the Iberian Peninsula?"),
        ("Croatia", "Is the country in the Balkans?"),
        ("Croatia", "Is the country in Central Europe?"),
        ("United Arab Emirates", "Is the country in the Middle East?"),
    ],
)
def test_direct_local_matcher_answers_new_regional_labels(country, question):
    facts = LocalCountryFacts(db_path=DB_PATH)

    answer = facts.try_answer(question, country)

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "geographic_area"


def test_direct_local_matcher_answers_grenada_caribbean_typo_question():
    facts = LocalCountryFacts(db_path=DB_PATH)

    answer = facts.try_answer("Is it Caribean country?", "Grenada")

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "geographic_area"


def test_planner_region_plan_for_caribbean_is_treated_as_geographic_area():
    plan = contains_plan("region", "Caribbean")

    answer = local_answer(plan, "Grenada")

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "geographic_area"


@pytest.mark.parametrize(
    ("country", "question", "relation"),
    [
        ("Poland", "Is the country Catholic?", "dominant_religion"),
        ("Turkey", "Is the dominant religion Islam?", "dominant_religion"),
        ("Japan", "Is the country religiously mixed?", "dominant_religion"),
        ("Israel", "Is the country Jewish?", "dominant_religion"),
        ("Greece", "Is the country Orthodox?", "dominant_religion"),
        ("Saudi Arabia", "Is the country an absolute monarchy?", "government_type"),
        ("Poland", "Is the country a parliamentary republic?", "government_type"),
        ("United Kingdom", "Is the country a monarchy?", "government_type"),
    ],
)
def test_direct_local_matcher_answers_religion_and_government(country, question, relation):
    facts = LocalCountryFacts(db_path=DB_PATH)

    answer = facts.try_answer(question, country)

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == relation


@pytest.mark.parametrize(
    ("country", "relation", "value", "expected"),
    [
        ("Poland", "dominant_religion", "Catholic", True),
        ("Poland", "dominant_religion", "Islam", False),
        ("Japan", "dominant_religion", "Mixed", True),
        ("Turkey", "government_type", "Republic", True),
        ("Saudi Arabia", "government_type", "Republic", False),
        ("United Kingdom", "government_type", "Monarchy", True),
    ],
)
def test_religion_and_government_plan_relations(country, relation, value, expected):
    answer = local_answer(scalar_plan("equals", relation, value), country)

    assert answer is not None
    assert answer.answer is expected
    assert answer.relation == relation


def test_continent_or_plan_handles_transcontinental_questions():
    plan = {
        "operator": "or",
        "conditions": [contains_plan("continent", "Europe"), contains_plan("continent", "Asia")],
    }

    answer = local_answer(plan, "Turkey")

    assert answer is not None
    assert answer.answer is True
    assert answer.relation == "continent"


def test_name_text_pattern_operators_are_evaluated_locally():
    ends_with_stan = {
        "operator": "ends_with",
        "left": {"entity": "target_country", "relation": "name"},
        "right": {"value": "stan"},
    }

    assert local_answer(ends_with_stan, "Afghanistan").answer is True
    assert local_answer(ends_with_stan, "Poland").answer is False


def test_self_bordering_rule_is_true_for_target_country_reference():
    answer = local_answer(contains_plan("borders_country", "Poland"), "Poland")

    assert answer is not None
    assert answer.answer is True


def test_exists_operator_for_known_list_relations():
    assert local_answer(exists_plan("water_access"), "Portugal").answer is True
    assert local_answer(exists_plan("subregion"), "Vatican City").answer is True


def test_unsupported_slavic_country_question_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    plan = local_planner.analyze_question_for_local_plan("Czy to państwo jest państwem słowiańskim?")

    assert plan.valid is True
    assert plan.supported is False
    assert plan.plan is None
    assert "GEMINI_API_KEY" in plan.fallback_reason


def test_slavic_country_is_not_accidentally_a_supported_local_relation():
    unsupported_relations = {
        "slavic_country",
        "cultural_group",
        "ethnolinguistic_group",
        "language_family",
        "ethnicity",
    }

    assert unsupported_relations.isdisjoint(set(local_planner.SUPPORTED_RELATIONS))

    answer = local_answer(contains_plan("slavic_country", "Slavic"), "Poland")
    assert answer is None


@pytest.mark.parametrize(
    ("country", "expected"),
    [
        ("Poland", True),
        ("Germany", True),
        ("Norway", True),
        ("Switzerland", False),
        ("Cuba", False),
    ],
)
def test_membership_or_plan_for_nato_or_eu(country, expected):
    plan = {
        "operator": "or",
        "conditions": [
            contains_plan("membership", "NATO"),
            contains_plan("membership", "EU"),
        ],
    }

    answer = local_answer(plan, country)

    assert answer is not None
    assert answer.answer is expected
    assert answer.relation == "membership"


@pytest.mark.parametrize(
    ("question_relation", "question_value"),
    [
        ("former_communist_country", "true"),
        ("communist_history", "true"),
        ("former_ussr_member", "true"),
        ("ussr_membership_history", "USSR"),
    ],
)
def test_historical_political_questions_are_not_local_sqlite_relations(question_relation, question_value):
    assert question_relation not in local_planner.SUPPORTED_RELATIONS
    assert local_answer(contains_plan(question_relation, question_value), "Poland") is None


@pytest.mark.parametrize(
        ("country", "expected"),
        [
            ("Poland", True),
            ("Vatican City", False),
            ("Germany", True),
    ],
)
def test_population_greater_than_one_million(country, expected):
    answer = local_answer(scalar_plan("greater_than", "population", 1_000_000), country)

    assert answer is not None
    assert answer.answer is expected


@pytest.mark.parametrize(
    ("country", "expected"),
    [
        ("Poland", False),
        ("Germany", True),
        ("Ukraine", True),
        ("Czech Republic", False),
        ("Russia", True),
    ],
)
def test_area_greater_than_poland(country, expected):
    plan = {
        "operator": "greater_than",
        "left": {"entity": "target_country", "relation": "area"},
        "right": {"entity": "Poland", "relation": "area"},
    }

    answer = local_answer(plan, country)

    assert answer is not None
    assert answer.answer is expected



@pytest.mark.parametrize(
    ("relation", "serbia_fact", "ukraine_fact"),
    [("area", "77,589", "603,550"), ("population", "6,567,783", "32,862,000")],
)
def test_country_scalar_comparison_explanation_includes_both_facts(
    relation, serbia_fact, ukraine_fact
):
    plan = {
        "operator": "greater_than",
        "left": {"entity": "target_country", "relation": relation},
        "right": {"entity": "Ukraine", "relation": relation},
    }

    answer = local_answer(plan, "Serbia")

    assert answer is not None
    assert answer.answer is False
    assert "Serbia" in answer.explanation
    assert serbia_fact in answer.explanation
    assert "Ukraine" in answer.explanation
    assert ukraine_fact in answer.explanation

@pytest.mark.parametrize(
    ("country", "operator", "expected"),
    [
        ("Kazakhstan", "west_of", True),
        ("Germany", "west_of", True),
        ("Japan", "west_of", False),
        ("Mongolia", "east_of", False),
        ("Japan", "east_of", True),
        ("Mongolia", "north_of", True),
        ("India", "south_of", True),
    ],
)
def test_coordinate_comparisons_against_china(country, operator, expected):
    relation = "coordinates.longitude" if operator in {"west_of", "east_of"} else "coordinates.latitude"
    plan = {
        "operator": operator,
        "left": {"entity": "target_country", "relation": relation},
        "right": {"entity": "China", "relation": relation},
    }

    answer = local_answer(plan, country)

    assert answer is not None
    assert answer.answer is expected


def test_bosnia_short_name_preserves_country_identity_and_borders():
    assert local_answer(contains_plan("borders_country", "Bosnia"), "Montenegro").answer is True
    assert local_answer(contains_plan("borders_country", "Bosnia"), "Poland").answer is False
    assert local_answer(
        {
            "operator": "equals",
            "left": {"entity": "target_country", "relation": "name"},
            "right": {"value": "Bośnią"},
        },
        "Bosnia and Herzegovina",
    ).answer is True


def test_named_cote_divoire_reference_resolves_for_directional_comparison():
    plan = {
        "operator": "west_of",
        "left": {"entity": "target_country", "relation": "coordinates.longitude"},
        "right": {"entity": "Côte d’Ivoire", "relation": "coordinates.longitude"},
    }

    result = local_answer(plan, "Guinea")

    assert result is not None
    assert result.answer is True
    assert "Ivory Coast" in result.explanation

    assert local_answer(contains_plan("borders_country", "Côte d’Ivoire"), "Guinea").answer is True


def test_every_simple_operator_is_evaluated_locally():
    cases = [
        ("equals", "capital", "Warsaw", "Poland", True),
        ("equals", "capital", "Berlin", "Poland", False),
        ("less_than", "population", 1_000_000, "Vatican City", True),
        ("starts_with", "name", "Po", "Poland", True),
        ("contains_text", "name", "land", "Poland", True),
        ("has_space", "name", None, "United Arab Emirates", True),
        ("word_count_equals", "name", 3, "United Arab Emirates", True),
        ("word_count_greater_than", "name", 2, "United Arab Emirates", True),
        ("word_count_less_than", "name", 2, "Poland", True),
        ("char_count_equals", "name", 6, "Poland", True),
        ("char_count_greater_than", "name", 10, "United Arab Emirates", True),
        ("char_count_less_than", "name", 7, "Poland", True),
    ]

    for operator, relation, value, country, expected in cases:
        plan = {
            "operator": operator,
            "left": {"entity": "target_country", "relation": relation},
        }
        if operator != "has_space":
            plan["right"] = {"value": value}

        answer = local_answer(plan, country)

        assert answer is not None, (operator, relation, country)
        assert answer.answer is expected, (operator, relation, country)


def test_conjunction_is_not_rewritten_as_a_letter_range():
    plan = {
        "operator": "and",
        "conditions": [
            scalar_plan("starts_with", "name", "A"),
            {"operator": "or", "conditions": [
                scalar_plan("starts_with", "name", "B"),
                scalar_plan("starts_with", "name", "M"),
            ]},
        ],
    }
    assert local_answer(plan, "Antigua and Barbuda").answer is False
    assert local_answer(plan, "Malta").answer is False


def test_unrepresented_directional_region_defers_instead_of_broadening():
    # Northern Africa does not establish membership in Northwestern Africa.
    plan = contains_plan("geographic_area", "Northwestern Africa")
    assert local_answer(plan, "Egypt") is None

def test_nested_boolean_not_any_and_all_operators():
    not_in_eu = {
        "operator": "not",
        "condition": contains_plan("membership", "EU"),
    }
    borders_nato_member = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "borders_country"},
        "condition": {
            "operator": "contains",
            "left": {"entity": "item", "relation": "membership"},
            "right": {"value": "NATO"},
        },
    }
    all_known_border_countries_are_not_islands = {
        "operator": "all",
        "items": {"entity": "target_country", "relation": "borders_country"},
        "condition": {
            "operator": "equals",
            "left": {"entity": "item", "relation": "is_island"},
            "right": {"value": 0},
        },
    }

    assert local_answer(not_in_eu, "Switzerland").answer is True
    assert local_answer(not_in_eu, "Poland").answer is False
    all_non_island = local_answer(all_known_border_countries_are_not_islands, "Mongolia")
    assert all_non_island.answer is True
    assert "Russia" in all_non_island.explanation
    assert "not an island" in all_non_island.explanation


def test_mixed_sqlite_and_unsupported_and_condition_falls_back_when_sqlite_part_is_true():
    plan = {
        "operator": "and",
        "conditions": [
            contains_plan("borders_country", "Germany"),
            contains_plan("slavic_country", "Slavic"),
        ],
    }

    answer = local_answer(plan, "Poland")

    assert answer is None


def test_mixed_sqlite_and_unsupported_or_condition_falls_back_when_sqlite_part_is_false():
    plan = {
        "operator": "or",
        "conditions": [
            contains_plan("borders_country", "Portugal"),
            contains_plan("slavic_country", "Slavic"),
        ],
    }

    answer = local_answer(plan, "Poland")
    assert answer is None


def test_mixed_conditions_can_still_answer_when_sqlite_logic_is_decisive():
    decisive_and_false = {
        "operator": "and",
        "conditions": [
            contains_plan("borders_country", "Portugal"),
            contains_plan("slavic_country", "Slavic"),
        ],
    }
    decisive_or_true = {
        "operator": "or",
        "conditions": [
            contains_plan("borders_country", "Germany"),
            contains_plan("slavic_country", "Slavic"),
        ],
    }

    assert local_answer(decisive_and_false, "Poland").answer is False
    assert local_answer(decisive_or_true, "Poland").answer is True


@pytest.mark.parametrize(
    "invalid_plan",
    [
        {},
        {"operator": "and", "conditions": []},
        {"operator": "contains", "left": {"entity": "target_country", "relation": "membership"}},
        {"operator": "greater_than", "left": {"entity": "target_country", "relation": "population"}, "right": {"value": "many"}},
        {"operator": "made_up_operator", "left": {"entity": "target_country", "relation": "population"}, "right": {"value": 1}},
    ],
)
def test_invalid_or_nonsense_local_plans_do_not_produce_answers(invalid_plan):
    assert local_answer(invalid_plan, "Poland") is None


@pytest.mark.parametrize(
    ("country", "water_body"),
    [
        ("Bosnia and Herzegovina", "Adriatic Sea"),
        ("Bosnia and Herzegovina", "Mediterranean Sea"),
        ("Croatia", "Adriatic Sea"),
        ("Croatia", "Mediterranean Sea"),
        ("Montenegro", "Adriatic Sea"),
        ("Montenegro", "Mediterranean Sea"),
        ("Slovenia", "Adriatic Sea"),
        ("Slovenia", "Mediterranean Sea"),
        ("Albania", "Mediterranean Sea"),
        ("Italy", "Mediterranean Sea"),
        ("Greece", "Mediterranean Sea"),
    ],
)
def test_bosnia_and_adriatic_countries_have_mediterranean_water_access(country, water_body):
    plan = contains_plan("water_access", water_body)
    ans = execute_local_plan(plan, country, f"Does the country have access to {water_body}?")
    assert ans is not None
    assert ans.answer is True
    assert water_body in ans.explanation


def test_water_access_exists_for_bosnia_and_explains_coastline():
    plan = exists_plan("water_access")
    ans_pl = execute_local_plan(
        plan,
        "Bosnia and Herzegovina",
        "Does the country have access to a sea or ocean?",
    )
    assert ans_pl is not None
    assert ans_pl.answer is True
    assert "Adriatic Sea" in ans_pl.explanation


def test_water_access_explains_actual_coastline_when_different_sea_queried():
    # Poland has Baltic Sea, not Mediterranean Sea. Must NOT say landlocked!
    plan = contains_plan("water_access", "Mediterranean Sea")
    ans_pl = execute_local_plan(
        plan,
        "Poland",
        "Does the country have access to the Mediterranean Sea?",
    )
    assert ans_pl is not None
    assert ans_pl.answer is False
    assert "Baltic Sea" in ans_pl.explanation
    assert "landlocked" not in ans_pl.explanation



def test_truly_landlocked_countries_state_landlocked():
    plan = exists_plan("water_access")
    ans = execute_local_plan(
        plan,
        "Czech Republic",
        "Does it have sea access?",
    )
    assert ans is not None
    assert ans.answer is False
    assert "is completely landlocked" in ans.explanation


def test_informative_explanations_for_currency_language_area_coords_capital():
    # Currency (False)
    curr_plan = contains_plan("currency", "Euro")
    ans_curr = execute_local_plan(
        curr_plan, "Poland", "Is the currency Euro?"
    )
    assert ans_curr is not None
    assert ans_curr.answer is False
    assert "Polish złoty" in ans_curr.explanation


    # Official Language (False)
    lang_plan = contains_plan("official_language", "Spanish")
    ans_lang = execute_local_plan(
        lang_plan, "Brazil", "Is Spanish an official language?"
    )
    assert ans_lang is not None
    assert ans_lang.answer is False
    assert "Portuguese" in ans_lang.explanation

    # Capital (False)
    cap_plan = scalar_plan("equals", "capital", "Krakow")
    ans_cap = execute_local_plan(
        cap_plan, "Poland", "Is the capital Krakow?"
    )
    assert ans_cap is not None
    assert ans_cap.answer is False
    assert "Warsaw" in ans_cap.explanation
    assert "Krakow" in ans_cap.explanation

    # Coordinates (north_of)
    coords_plan = {
        "operator": "north_of",
        "left": {"entity": "target_country", "relation": "coordinates.latitude"},
        "right": {"entity": "Italy", "relation": "coordinates.latitude"},
    }
    ans_coords = execute_local_plan(
        coords_plan, "Poland", "Is the country north of Italy?"
    )
    assert ans_coords is not None
    assert ans_coords.answer is True
    assert "52.0°N" in ans_coords.explanation
