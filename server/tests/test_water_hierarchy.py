"""Tests for water body hierarchy, parent ocean/sea resolution, and explanation formatting."""

import pytest
import sqlite3
from pathlib import Path

from countrydle.local_answering import (
    execute_local_plan,
    try_answer_locally,
    LocalCountryFacts,
    DEFAULT_DB_PATH,
)
from local_kb_question import execute_plan as execute_mode_plan, QuestionPlan
from us_statedle.utils import LOCAL_CONFIG as US_STATE_CONFIG
from wojewodztwodle.utils import LOCAL_CONFIG as VOIVODESHIP_CONFIG
from powiatdle.utils import LOCAL_CONFIG as POWIAT_CONFIG
from utils.water_hierarchy import (
    WATER_BODY_PARENT_MAP,
    get_water_body_parents,
    expand_water_bodies,
    is_marine_water_body,
    canonicalize_water_body,
)


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


def make_us_plan(water: str) -> QuestionPlan:
    return QuestionPlan(
        valid=True,
        supported=True,
        explanation="",
        original_question=f"Does the state have access to {water}?",
        improved_question=f"Does the state have access to {water}?",
        plan={
            "operator": "contains",
            "left": {"entity": "target_state", "relation": "water_access"},
            "right": {"value": water},
        },
    )


# ---------------------------------------------------------------------------
# Unit tests on water_hierarchy module
# ---------------------------------------------------------------------------

def test_water_hierarchy_transitive_atlantic_basin():
    # Direct ocean
    assert "Ocean" in get_water_body_parents("Atlantic Ocean")

    # Marginal seas in Atlantic basin
    assert "Atlantic Ocean" in get_water_body_parents("Caribbean Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Gulf of Mexico")
    assert "Atlantic Ocean" in get_water_body_parents("Baltic Sea")
    assert "Atlantic Ocean" in get_water_body_parents("North Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Mediterranean Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Celtic Sea")

    # Sub-seas of Mediterranean
    assert "Mediterranean Sea" in get_water_body_parents("Adriatic Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Adriatic Sea")
    assert "Mediterranean Sea" in get_water_body_parents("Aegean Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Aegean Sea")
    assert "Mediterranean Sea" in get_water_body_parents("Black Sea")
    assert "Atlantic Ocean" in get_water_body_parents("Black Sea")

    # Sub-sea of Black Sea
    assert "Black Sea" in get_water_body_parents("Sea of Azov")
    assert "Mediterranean Sea" in get_water_body_parents("Sea of Azov")
    assert "Atlantic Ocean" in get_water_body_parents("Sea of Azov")


def test_water_hierarchy_transitive_pacific_basin():
    assert "Ocean" in get_water_body_parents("Pacific Ocean")
    assert "Pacific Ocean" in get_water_body_parents("South China Sea")
    assert "South China Sea" in get_water_body_parents("Gulf of Thailand")
    assert "Pacific Ocean" in get_water_body_parents("Gulf of Thailand")
    assert "Pacific Ocean" in get_water_body_parents("East China Sea")
    assert "Pacific Ocean" in get_water_body_parents("Yellow Sea")
    assert "Yellow Sea" in get_water_body_parents("Bohai Sea")
    assert "Pacific Ocean" in get_water_body_parents("Bohai Sea")
    assert "Pacific Ocean" in get_water_body_parents("Sea of Japan")
    assert "Pacific Ocean" in get_water_body_parents("Sea of Okhotsk")
    assert "Pacific Ocean" in get_water_body_parents("Philippine Sea")
    assert "Pacific Ocean" in get_water_body_parents("Coral Sea")
    assert "Pacific Ocean" in get_water_body_parents("Tasman Sea")
    assert "Pacific Ocean" in get_water_body_parents("Bering Sea")
    assert "Pacific Ocean" in get_water_body_parents("Gulf of Alaska")


def test_water_hierarchy_transitive_indian_basin():
    assert "Ocean" in get_water_body_parents("Indian Ocean")
    assert "Indian Ocean" in get_water_body_parents("Red Sea")
    assert "Red Sea" in get_water_body_parents("Gulf of Aqaba")
    assert "Indian Ocean" in get_water_body_parents("Gulf of Aqaba")
    assert "Indian Ocean" in get_water_body_parents("Persian Gulf")
    assert "Arabian Sea" in get_water_body_parents("Persian Gulf")
    assert "Indian Ocean" in get_water_body_parents("Arabian Sea")
    assert "Indian Ocean" in get_water_body_parents("Bay of Bengal")
    assert "Bay of Bengal" in get_water_body_parents("Andaman Sea")
    assert "Indian Ocean" in get_water_body_parents("Andaman Sea")


def test_inland_water_bodies_classification():
    assert is_marine_water_body("Caspian Sea") is False
    assert is_marine_water_body("Aral Sea") is False
    assert is_marine_water_body("Dead Sea") is False
    assert is_marine_water_body("Baltic Sea") is True
    assert is_marine_water_body("Mediterranean Sea") is True
    assert "Ocean" not in get_water_body_parents("Caspian Sea")


# ---------------------------------------------------------------------------
# Countrydle game integration tests (Report #23 & global countries)
# ---------------------------------------------------------------------------

def test_nicaragua_touches_both_atlantic_and_pacific_report_23():
    # Report 23 reproduction: player asked if Nicaragua touches both Atlantic and Pacific
    plan = {
        "operator": "and",
        "conditions": [
            {"operator": "contains", "left": {"entity": "target_country", "relation": "water_access"}, "right": {"value": "Atlantic Ocean"}},
            {"operator": "contains", "left": {"entity": "target_country", "relation": "water_access"}, "right": {"value": "Pacific Ocean"}}
        ]
    }
    ans = execute_local_plan(plan, "Nicaragua", "Does the country border both the Atlantic and Pacific Oceans?")
    assert ans is not None
    assert ans.answer is True
    assert "Atlantic Ocean" in ans.explanation
    assert "Caribbean Sea" in ans.explanation
    assert "Pacific Ocean" in ans.explanation


def test_panama_and_colombia_touch_both_atlantic_and_pacific():
    for country in ("Panama", "Colombia", "Costa Rica"):
        plan_atl = contains_plan("water_access", "Atlantic Ocean")
        plan_pac = contains_plan("water_access", "Pacific Ocean")
        assert execute_local_plan(plan_atl, country, "").answer is True, country
        assert execute_local_plan(plan_pac, country, "").answer is True, country


def test_single_ocean_countries_do_not_falsely_match_other_oceans():
    # Brazil has Atlantic access, not Pacific
    assert execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Brazil", "").answer is True
    assert execute_local_plan(contains_plan("water_access", "Pacific Ocean"), "Brazil", "").answer is False

    # Chile has Pacific access, not Atlantic
    assert execute_local_plan(contains_plan("water_access", "Pacific Ocean"), "Chile", "").answer is True
    assert execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Chile", "").answer is False

    # India has Indian Ocean access, not Atlantic or Pacific
    assert execute_local_plan(contains_plan("water_access", "Indian Ocean"), "India", "").answer is True
    assert execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "India", "").answer is False


def test_marginal_sea_countries_inherit_parent_ocean():
    # Poland: Baltic Sea -> Atlantic Ocean
    ans_pl = execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Poland", "")
    assert ans_pl.answer is True
    assert "via the Baltic Sea" in ans_pl.explanation

    # Croatia: Adriatic Sea -> Mediterranean Sea -> Atlantic Ocean
    ans_hr_med = execute_local_plan(contains_plan("water_access", "Mediterranean Sea"), "Croatia", "")
    assert ans_hr_med.answer is True
    ans_hr_atl = execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Croatia", "")
    assert ans_hr_atl.answer is True
    assert "via the Adriatic Sea" in ans_hr_atl.explanation

    # Egypt: Mediterranean Sea (Atlantic) + Red Sea (Indian)
    assert execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Egypt", "").answer is True
    assert execute_local_plan(contains_plan("water_access", "Indian Ocean"), "Egypt", "").answer is True

    # Saudi Arabia: Red Sea + Persian Gulf -> Indian Ocean
    ans_sa = execute_local_plan(contains_plan("water_access", "Indian Ocean"), "Saudi Arabia", "")
    assert ans_sa.answer is True

    # Vietnam: South China Sea + Gulf of Thailand -> Pacific Ocean
    ans_vn = execute_local_plan(contains_plan("water_access", "Pacific Ocean"), "Vietnam", "")
    assert ans_vn.answer is True


def test_landlocked_countries_stay_false_for_all_oceans_and_seas():
    for country in ("Czech Republic", "Austria", "Hungary", "Switzerland", "Mali", "Niger", "Bolivia"):
        assert execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), country, "").answer is False
        assert execute_local_plan(contains_plan("water_access", "Ocean"), country, "").answer is False
        assert execute_local_plan(contains_plan("water_access", "Sea"), country, "").answer is False
        assert execute_local_plan(exists_plan("water_access"), country, "").answer is False


def test_caspian_sea_endorheic_inland_water_is_not_ocean():
    # Kazakhstan borders Caspian Sea: has water_access and Sea, but NOT Ocean or Atlantic
    ans_caspian = execute_local_plan(contains_plan("water_access", "Caspian Sea"), "Kazakhstan", "")
    assert ans_caspian.answer is True

    ans_ocean = execute_local_plan(contains_plan("water_access", "Ocean"), "Kazakhstan", "")
    assert ans_ocean.answer is False

    ans_atl = execute_local_plan(contains_plan("water_access", "Atlantic Ocean"), "Kazakhstan", "")
    assert ans_atl.answer is False


# ---------------------------------------------------------------------------
# US States mode integration tests (Report #20)
# ---------------------------------------------------------------------------

def test_us_states_gulf_of_mexico_inherits_atlantic_report_20():
    # Report 20: Gulf of Mexico states should have Atlantic Ocean access
    for state in ("Texas", "Louisiana", "Mississippi", "Alabama"):
        ans = execute_mode_plan(US_STATE_CONFIG, state, make_us_plan("Atlantic Ocean"))
        assert ans is not None
        assert ans.answer is True, f"{state} should have Atlantic Ocean access via Gulf of Mexico"
        assert "via the Gulf of Mexico" in ans.explanation

    # Florida borders both directly and via Gulf of Mexico
    ans_fl = execute_mode_plan(US_STATE_CONFIG, "Florida", make_us_plan("Atlantic Ocean"))
    assert ans_fl.answer is True

    # California has Pacific access, not Atlantic
    ans_ca_pac = execute_mode_plan(US_STATE_CONFIG, "California", make_us_plan("Pacific Ocean"))
    assert ans_ca_pac.answer is True
    ans_ca_atl = execute_mode_plan(US_STATE_CONFIG, "California", make_us_plan("Atlantic Ocean"))
    assert ans_ca_atl.answer is False

    # Kansas is completely inland
    ans_ks = execute_mode_plan(US_STATE_CONFIG, "Kansas", make_us_plan("Atlantic Ocean"))
    assert ans_ks.answer is False


# ---------------------------------------------------------------------------
# Polish Voivodeships & Powiaty integration tests
# ---------------------------------------------------------------------------

def test_voivodeship_water_access_baltic():
    plan_baltic = QuestionPlan(
        valid=True, supported=True, explanation="",
        original_question="Czy województwo ma dostęp do Morza Bałtyckiego?",
        improved_question="Czy województwo ma dostęp do Morza Bałtyckiego?",
        plan={
            "operator": "contains",
            "left": {"entity": "target_voivodeship", "relation": "water_access"},
            "right": {"value": "Morze Bałtyckie"},
        },
    )
    ans_pom = execute_mode_plan(VOIVODESHIP_CONFIG, "Pomorskie", plan_baltic)
    assert ans_pom.answer is True

    ans_maz = execute_mode_plan(VOIVODESHIP_CONFIG, "Mazowieckie", plan_baltic)
    assert ans_maz.answer is False


def test_powiat_water_access_baltic():
    plan_baltic = QuestionPlan(
        valid=True, supported=True, explanation="",
        original_question="Czy powiat ma dostęp do morza?",
        improved_question="Czy powiat ma dostęp do morza?",
        plan={"operator": "exists", "left": {"entity": "target_powiat", "relation": "water_access"}},
    )
    ans_puck = execute_mode_plan(POWIAT_CONFIG, "Powiat pucki", plan_baltic)
    assert ans_puck.answer is True

    ans_krk = execute_mode_plan(POWIAT_CONFIG, "Powiat krakowski", plan_baltic)
    assert ans_krk.answer is False
