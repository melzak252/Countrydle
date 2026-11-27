"""Tests for geographic bot auto-coloring (map_highlight) in regional Local KB modes."""

from __future__ import annotations

from local_kb_question import QuestionPlan, execute_plan
from countydle.utils import LOCAL_CONFIG as COUNTY_CONFIG
from powiatdle.utils import LOCAL_CONFIG as POWIAT_CONFIG
from us_statedle.utils import LOCAL_CONFIG as US_STATE_CONFIG
from wojewodztwodle.utils import LOCAL_CONFIG as VOIVODESHIP_CONFIG


def _plan(ast: dict, original: str = "test question") -> QuestionPlan:
    return QuestionPlan(
        original_question=original,
        valid=True,
        supported=True,
        improved_question=original,
        explanation="test",
        plan=ast,
    )


def test_us_statedle_geographic_and_direct_name_highlights():
    # Geographic: borders Texas (target: Oklahoma -> True)
    border_tx = execute_plan(
        US_STATE_CONFIG,
        "Oklahoma",
        _plan(
            {
                "operator": "contains_exact",
                "left": {"entity": "target_state", "relation": "borders_state"},
                "right": {"value": "Texas"},
            },
            "Does it border Texas?",
        ),
    )
    assert border_tx is not None
    assert border_tx.answer is True
    assert border_tx.map_highlight is not None
    assert border_tx.map_highlight["supported"] is True
    assert "Oklahoma" in border_tx.map_highlight["matched"]
    assert "New Mexico" in border_tx.map_highlight["matched"]
    assert "Texas" in border_tx.map_highlight["eliminated"]
    assert "California" in border_tx.map_highlight["eliminated"]

    # Direct name check answering False -> eliminates only the asked state
    is_ca = execute_plan(
        US_STATE_CONFIG,
        "Texas",
        _plan(
            {
                "operator": "equals",
                "left": {"entity": "target_state", "relation": "name"},
                "right": {"value": "California"},
            },
            "Is it California?",
        ),
    )
    assert is_ca is not None
    assert is_ca.answer is False
    assert is_ca.map_highlight == {
        "supported": True,
        "matched": [],
        "eliminated": ["California"],
        "note": None,
    }

    # Objective numeric fact (population) -> auto-colored
    pop = execute_plan(
        US_STATE_CONFIG,
        "Texas",
        _plan(
            {
                "operator": "greater_than",
                "left": {"entity": "target_state", "relation": "population"},
                "right": {"value": 10000000},
            },
            "Does it have more than 10 million people?",
        ),
    )
    assert pop is not None
    assert pop.answer is True
    assert pop.map_highlight is not None
    assert "Texas" in pop.map_highlight["matched"]

    # Fuzzy relation (nickname) -> excluded from auto-coloring
    nick = execute_plan(
        US_STATE_CONFIG,
        "Texas",
        _plan(
            {
                "operator": "contains_partial",
                "left": {"entity": "target_state", "relation": "nickname"},
                "right": {"value": "Lone Star"},
            },
            "Is its nickname Lone Star?",
        ),
    )
    assert nick is not None
    assert nick.map_highlight is None


def test_wojewodztwodle_geographic_and_non_geographic_highlights():
    coastal = execute_plan(
        VOIVODESHIP_CONFIG,
        "Pomorskie",
        _plan(
            {
                "operator": "equals",
                "left": {"entity": "target_voivodeship", "relation": "is_coastal"},
                "right": {"value": True},
            },
            "Czy ma dostęp do morza?",
        ),
    )
    assert coastal is not None
    assert coastal.answer is True
    assert coastal.map_highlight is not None
    assert coastal.map_highlight["supported"] is True
    assert "Pomorskie" in coastal.map_highlight["matched"]
    assert "Zachodniopomorskie" in coastal.map_highlight["matched"]
    assert "Małopolskie" in coastal.map_highlight["eliminated"]
    assert len(coastal.map_highlight["matched"]) + len(coastal.map_highlight["eliminated"]) == 16

    pop_v = execute_plan(
        VOIVODESHIP_CONFIG,
        "Mazowieckie",
        _plan(
            {
                "operator": "greater_than",
                "left": {"entity": "target_voivodeship", "relation": "population"},
                "right": {"value": 2000000},
            },
            "Czy ma ponad 2 mln mieszkańców?",
        ),
    )
    assert pop_v is not None
    assert pop_v.map_highlight is not None
    assert "Mazowieckie" in pop_v.map_highlight["matched"]


def test_powiatdle_geographic_and_non_geographic_highlights():
    in_malopolskie = execute_plan(
        POWIAT_CONFIG,
        "Kraków",
        _plan(
            {
                "operator": "equals",
                "left": {"entity": "target_powiat", "relation": "voivodeship"},
                "right": {"value": "Małopolskie"},
            },
            "Czy leży w Małopolsce?",
        ),
    )
    assert in_malopolskie is not None
    assert in_malopolskie.answer is True
    assert in_malopolskie.map_highlight is not None
    assert in_malopolskie.map_highlight["supported"] is True
    assert "Kraków" in in_malopolskie.map_highlight["matched"]
    assert "Warszawa" in in_malopolskie.map_highlight["eliminated"]
    assert len(in_malopolskie.map_highlight["matched"]) + len(in_malopolskie.map_highlight["eliminated"]) == 380

    plates = execute_plan(
        POWIAT_CONFIG,
        "Kraków",
        _plan(
            {
                "operator": "contains_exact",
                "left": {"entity": "target_powiat", "relation": "registration_plates"},
                "right": {"value": "KR"},
            },
            "Czy ma tablice KR?",
        ),
    )
    assert plates is not None
    assert plates.answer is True
    assert plates.map_highlight is not None
    assert "Kraków" in plates.map_highlight["matched"]

    # Fuzzy relation (health_resorts) -> excluded from auto-coloring
    resorts = execute_plan(
        POWIAT_CONFIG,
        "Kraków",
        _plan(
            {
                "operator": "exists",
                "left": {"entity": "target_powiat", "relation": "health_resorts"},
            },
            "Czy jest tu uzdrowisko?",
        ),
    )
    assert resorts is not None
    assert resorts.map_highlight is None


def test_countydle_geographic_and_direct_name_highlights():
    borders_wales = execute_plan(
        COUNTY_CONFIG,
        "Herefordshire",
        _plan(
            {
                "operator": "contains_exact",
                "left": {"entity": "target_county", "relation": "borders_country"},
                "right": {"value": "Wales"},
            },
            "Does it border Wales?",
        ),
    )
    assert borders_wales is not None
    assert borders_wales.answer is True
    assert borders_wales.map_highlight is not None
    assert borders_wales.map_highlight["supported"] is True
    assert "Herefordshire" in borders_wales.map_highlight["matched"]
    assert "Kent" in borders_wales.map_highlight["eliminated"]
    assert len(borders_wales.map_highlight["matched"]) + len(borders_wales.map_highlight["eliminated"]) == 48

    is_cornwall = execute_plan(
        COUNTY_CONFIG,
        "Kent",
        _plan(
            {
                "operator": "equals",
                "left": {"entity": "target_county", "relation": "name"},
                "right": {"value": "Cornwall"},
            },
            "Is it Cornwall?",
        ),
    )
    assert is_cornwall is not None
    assert is_cornwall.answer is False
    assert is_cornwall.map_highlight == {
        "supported": True,
        "matched": [],
        "eliminated": ["Cornwall"],
        "note": None,
    }


def test_complex_quantified_plans_skip_auto_coloring():
    from countrydle.local_answering import execute_local_plan

    # Countrydle: quantified `any` over borders_country is skipped for auto-coloring (answer still succeeds)
    complex_country_plan = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "borders_country"},
        "condition": {
            "operator": "contains",
            "left": {"entity": "item", "relation": "membership"},
            "right": {"value": "EU"},
        },
    }
    res_country = execute_local_plan(complex_country_plan, "Poland", "Does it border an EU member?")
    assert res_country is not None
    assert res_country.answer is True
    assert res_country.map_highlight is None

    # Regional local KB: quantified `any` is also skipped for auto-coloring
    complex_state_plan = {
        "operator": "any",
        "items": {"entity": "target_state", "relation": "borders_state"},
        "condition": {
            "operator": "equals",
            "left": {"entity": "item", "relation": "is_coastal"},
            "right": {"value": True},
        },
    }
    res_state = execute_plan(
        US_STATE_CONFIG,
        "Nevada",
        _plan(complex_state_plan, "Does it border a coastal state?"),
    )
    assert res_state is not None
    assert res_state.map_highlight is None
