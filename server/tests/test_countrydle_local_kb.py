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
        "Test planner explanation.",
    )


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


def test_letter_range_normalization_and_answering():
    contradictory_and_plan = {
        "operator": "and",
        "conditions": [
            {"operator": "starts_with", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "A"}},
            {
                "operator": "or",
                "conditions": [
                    {"operator": "starts_with", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "B"}},
                    {"operator": "starts_with", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "M"}},
                ]
            }
        ]
    }
    ans = local_answer(contradictory_and_plan, "Antigua and Barbuda")
    assert ans is not None
    assert ans.answer is True
    assert "starts with 'A'" in ans.explanation

    ans_poland = local_answer(contradictory_and_plan, "Poland")
    assert ans_poland is not None
    assert ans_poland.answer is False


def test_directional_african_quadrants():
    nw_plan = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "geographic_area"},
        "right": {"value": "Northwestern Africa"},
    }
    # Kenya is in East Africa, NOT Northwestern Africa
    ans_kenya = local_answer(nw_plan, "Kenya")
    assert ans_kenya is not None
    assert ans_kenya.answer is False
    assert "East Africa" in ans_kenya.explanation

    # Morocco is in Northwestern Africa
    ans_morocco = local_answer(nw_plan, "Morocco")
    assert ans_morocco is not None
    assert ans_morocco.answer is True

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
    assert local_answer(borders_nato_member, "Poland").answer is True
    assert local_answer(all_known_border_countries_are_not_islands, "Mongolia").answer is True


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
        original_question="Czy ma dostęp do morza/oceanu?",
    )
    assert ans_pl is not None
    assert ans_pl.answer is True
    assert "dostęp do morza" in ans_pl.explanation
    assert "Adriatic Sea" in ans_pl.explanation


def test_water_access_explains_actual_coastline_when_different_sea_queried():
    # Poland has Baltic Sea, not Mediterranean Sea. Must NOT say landlocked!
    plan = contains_plan("water_access", "Mediterranean Sea")
    ans_pl = execute_local_plan(
        plan,
        "Poland",
        "Does the country have access to the Mediterranean Sea?",
        original_question="Czy ma dostęp do Morza Śródziemnego?",
    )
    assert ans_pl is not None
    assert ans_pl.answer is False
    assert "nie ma bezpośredniego dostępu do: Mediterranean Sea" in ans_pl.explanation
    assert "Baltic Sea" in ans_pl.explanation
    assert "śródlądowym" not in ans_pl.explanation

    ans_en = execute_local_plan(
        plan,
        "Poland",
        "Does the country have access to the Mediterranean Sea?",
        original_question="Does it have access to the Mediterranean Sea?",
    )
    assert ans_en is not None
    assert ans_en.answer is False
    assert "does not have direct coastline access to: Mediterranean Sea" in ans_en.explanation
    assert "Baltic Sea" in ans_en.explanation
    assert "completely landlocked" not in ans_en.explanation


def test_truly_landlocked_countries_state_landlocked():
    plan = exists_plan("water_access")
    ans = execute_local_plan(
        plan,
        "Czech Republic",
        "Does it have sea access?",
        original_question="Czy ma dostęp do morza?",
    )
    assert ans is not None
    assert ans.answer is False
    assert "jest krajem śródlądowym" in ans.explanation


def test_informative_explanations_for_currency_language_area_coords_capital():
    # Currency (False)
    curr_plan = contains_plan("currency", "Euro")
    ans_curr = execute_local_plan(
        curr_plan, "Poland", "Is the currency Euro?", original_question="Czy walutą jest Euro?"
    )
    assert ans_curr is not None
    assert ans_curr.answer is False
    assert "Walutą w Poland nie jest Euro" in ans_curr.explanation
    assert "Polish złoty" in ans_curr.explanation

    # Currency (True)
    ans_curr_de = execute_local_plan(
        curr_plan, "Germany", "Is the currency Euro?", original_question="Czy walutą jest Euro?"
    )
    assert ans_curr_de is not None
    assert ans_curr_de.answer is True
    assert "Oficjalną walutą w Germany jest" in ans_curr_de.explanation

    # Official Language (False)
    lang_plan = contains_plan("official_language", "Spanish")
    ans_lang = execute_local_plan(
        lang_plan, "Brazil", "Is Spanish an official language?", original_question="Czy językiem jest hiszpański?"
    )
    assert ans_lang is not None
    assert ans_lang.answer is False
    assert "Portuguese" in ans_lang.explanation

    # Capital (False)
    cap_plan = scalar_plan("equals", "capital", "Krakow")
    ans_cap = execute_local_plan(
        cap_plan, "Poland", "Is the capital Krakow?", original_question="Czy stolicą jest Kraków?"
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
        coords_plan, "Poland", "Is the country north of Italy?", original_question="Czy leży na północ od Włoch?"
    )
    assert ans_coords is not None
    assert ans_coords.answer is True
    assert "leży na północ od Italy" in ans_coords.explanation
    assert "52.0°N" in ans_coords.explanation
