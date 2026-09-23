import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from countrydle.local_answering import execute_local_plan
from countrydle.local_planner import QuestionPlan
from db.models import Country, CountrydleDay, Wojewodztwo, WojewodztwodleDay
from db.repositories.countrydle import CountrydleRepository
from db.repositories.wojewodztwodle import WojewodztwodleDayRepository


def test_flag_color_evaluation():
    p_red = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_color"},
        "right": {"value": "red"},
    }
    p_green = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_color"},
        "right": {"value": "green"},
    }

    # Poland has red, but not green
    assert execute_local_plan(p_red, "Poland", "Is there red on the flag?").answer is True
    assert execute_local_plan(p_green, "Poland", "Is there green on the flag?").answer is False

    # Brazil has green, but not red
    assert execute_local_plan(p_green, "Brazil", "Is there green on the flag?").answer is True
    assert execute_local_plan(p_red, "Brazil", "Is there red on the flag?").answer is False


def test_flag_symbol_evaluation():
    p_star = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_symbol"},
        "right": {"value": "star"},
    }
    p_cross = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "flag_symbol"},
        "right": {"value": "cross"},
    }

    # USA has stars
    assert execute_local_plan(p_star, "United States", "Does the flag have a star?").answer is True
    assert execute_local_plan(p_cross, "United States", "Does the flag have a cross?").answer is False

    # United Kingdom has cross
    assert execute_local_plan(p_cross, "United Kingdom", "Does the flag have a cross?").answer is True
    assert execute_local_plan(p_star, "United Kingdom", "Does the flag have a star?").answer is False


def test_historical_unions_evaluation():
    p_ussr = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "historical_union"},
        "right": {"value": "USSR"},
    }
    p_yugo = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "historical_union"},
        "right": {"value": "Yugoslavia"},
    }

    # Russia was in USSR
    assert execute_local_plan(p_ussr, "Russia", "Was it part of USSR?").answer is True
    # Poland was not in USSR
    assert execute_local_plan(p_ussr, "Poland", "Was it part of USSR?").answer is False

    # Croatia was in Yugoslavia
    assert execute_local_plan(p_yugo, "Croatia", "Was it in Yugoslavia?").answer is True
    # Poland was not in Yugoslavia
    assert execute_local_plan(p_yugo, "Poland", "Was it in Yugoslavia?").answer is False


def test_factual_explanation_formatting():
    p_border = {
        "operator": "contains",
        "left": {"entity": "target_country", "relation": "borders_country"},
        "right": {"value": "Germany"},
    }
    # Polish query receives English explanation
    ans_pl = execute_local_plan(p_border, "Poland", "Czy ten kraj graniczy z Niemcami?")
    assert ans_pl.answer is True
    assert "Poland shares a land border with Germany." in ans_pl.explanation
    # English query
    ans_en = execute_local_plan(p_border, "Poland", "Does it border Germany?")
    assert ans_en.answer is True
    assert "Poland shares a land border with Germany." in ans_en.explanation


@pytest.mark.real_database
@pytest.mark.anyio
async def test_countrydle_cooldown_excludes_recent_entities():
    mock_session = AsyncMock()
    repo = CountrydleRepository(mock_session)

    # 3 countries exist: ID 1 (Poland), ID 2 (Germany), ID 3 (France)
    c1 = Country(id=1, name="Poland")
    c2 = Country(id=2, name="Germany")
    c3 = Country(id=3, name="France")

    with (
        patch(
            "db.repositories.country.CountryRepository.get_all_countries",
            new_callable=AsyncMock,
            return_value=[c1, c2, c3],
        ),
        patch.object(repo, "create_day_country", new_callable=AsyncMock) as mock_create,
    ):
        # Recent IDs: [1, 2] (Poland and Germany were chosen recently)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [1, 2]
        mock_session.execute.return_value = mock_result

        await repo.generate_new_day_country(cooldown_days=2)

        # Must pick France (ID 3) since 1 and 2 are in cooldown!
        assert mock_create.call_count == 1
        chosen_country = mock_create.call_args[0][0]
        assert chosen_country.id == 3
        assert chosen_country.name == "France"
