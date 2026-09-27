import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from countrydle.local_answering import (
    DEFAULT_DB_PATH,
    execute_local_plan,
    find_country,
)
from countrydle.local_planner import analyze_question_for_local_plan
from countrydle.template_compiler import compile_template_plan


def test_find_country_micronesia():
    """Verify that find_country resolves English and Polish aliases for Federated States of Micronesia."""
    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        
        row_en = find_country(conn, "Micronesia")
        assert row_en is not None
        assert row_en["app_country_name"] == "Federated States of Micronesia"

        row_fsm = find_country(conn, "FSM")
        assert row_fsm is not None
        assert row_fsm["app_country_name"] == "Federated States of Micronesia"

        row_pl = find_country(conn, "Mikronezja")
        assert row_pl is not None
        assert row_pl["app_country_name"] == "Federated States of Micronesia"

        row_pl_gen = find_country(conn, "Mikronezji")
        assert row_pl_gen is not None
        assert row_pl_gen["app_country_name"] == "Federated States of Micronesia"


def test_compile_template_micronesia():
    """Verify deterministic template compiler resolves 'Czy to mikronezja?' and 'Is it Micronesia?'."""
    plan_pl, improved_pl = compile_template_plan("Czy to mikronezja?")
    assert plan_pl == [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "Federated States of Micronesia"}}
    ]
    assert improved_pl == "Is the country Federated States of Micronesia?"

    plan_en, improved_en = compile_template_plan("Is it Micronesia?")
    assert plan_en == [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "Federated States of Micronesia"}}
    ]
    assert improved_en == "Is the country Federated States of Micronesia?"


def test_analyze_question_for_local_plan_micronesia():
    """Verify analyze_question_for_local_plan marks 'Czy to mikronezja?' as valid and supported."""
    result = analyze_question_for_local_plan("Czy to mikronezja?")
    assert result.valid is True
    assert result.supported is True
    assert result.plan == [
        {"operator": "equals", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "Federated States of Micronesia"}}
    ]


def test_execute_local_plan_micronesia():
    """Verify execution of the plan against target countries."""
    plan, improved = compile_template_plan("Czy to mikronezja?")
    
    # Negative test against Poland
    ans_poland = execute_local_plan(plan, "Poland", improved)
    assert ans_poland is not None
    assert ans_poland.answer is False
    assert "name" in ans_poland.relation

    # Positive test against Federated States of Micronesia
    ans_fsm = execute_local_plan(plan, "Federated States of Micronesia", improved)
    assert ans_fsm is not None
    assert ans_fsm.answer is True
    assert "name" in ans_fsm.relation


def test_other_countries_previously_failing_polish_and_english():
    """Verify other countries with Polish names and English variations compile and resolve."""
    cases = [
        ("Czy to Irlandia?", "Ireland"),
        ("Czy to RPA?", "South Africa"),
        ("Czy to Łotwa?", "Latvia"),
        ("Czy to Węgry?", "Hungary"),
        ("Czy to Rumunia?", "Romania"),
        ("Czy to Szwajcaria?", "Switzerland"),
        ("Is it the Gambia?", "Gambia"),
        ("Is it the Netherlands?", "Netherlands"),
        ("Is it Cote d'Ivoire?", "Ivory Coast"),
        ("Is it Vatican?", "Vatican City"),
        ("Is it Swaziland?", "Eswatini"),
        ("Is it Burma?", "Myanmar"),
        ("Is it Sao Tome & Principe?", "São Tomé and Príncipe"),
    ]
    for question, expected_country in cases:
        plan, improved = compile_template_plan(question)
        assert plan is not None, f"Failed template compilation for: {question}"
        assert plan[0]["right"]["value"] == expected_country, (
            f"Wrong country for {question}: expected {expected_country}, got {plan[0]['right']['value']}"
        )

        res = analyze_question_for_local_plan(question)
        assert res.valid is True, f"Question marked invalid: {question}"
        assert res.supported is True, f"Question marked unsupported: {question}"


@pytest.mark.anyio
async def test_countrydle_question_endpoint_micronesia(async_client):
    """POST /countrydle/question with 'Czy to mikronezja?' returns valid=True with answer."""
    mock_country = MagicMock()
    mock_country.id = 58
    mock_country.name = "Federated States of Micronesia"
    mock_country.official_name = "Federated States of Micronesia"

    mock_day = MagicMock()
    mock_day.id = 1
    mock_day.country_id = 58
    mock_day.country = mock_country
    mock_q = MagicMock()
    mock_q.id = 1
    mock_q.valid = True
    mock_q.answer = True
    mock_q.user_id = None
    mock_q.day_id = 1
    mock_q.user = None
    mock_q.country = mock_country
    mock_q.question = "Czy to mikronezja?"
    mock_q.original_question = "Czy to mikronezja?"
    mock_q.explanation = "Federated States of Micronesia: name = Federated States of Micronesia."
    mock_q.context = "local_kb:name"

    with (
        patch("db.repositories.countrydle.CountrydleRepository.get_day_country_by_date", new_callable=AsyncMock) as m_today,
        patch("db.repositories.question.CountrydleQuestionsRepository.create_question", new_callable=AsyncMock) as m_create_q,
    ):
        m_today.return_value = mock_day
        m_create_q.return_value = mock_q
        res = await async_client.post("/countrydle/question", json={"question": "Czy to mikronezja?"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["answer"] is True
