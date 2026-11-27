from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import app
from db import get_db
from db.base import Base
from db.models.continental import ContinentCode, ContinentalDay, ContinentalState
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState
from db.models.countydle import CountydleDay, CountydleState
from db.models.english_county import EnglishCounty
from db.models.flagdle import FlagdleDay, FlagdleState
from db.models.guest_participation import GuestParticipation
from db.models.heraldry_daily import HeraldryDailySession
from db.models.heraldry_quiz import QuizRun
from db.models.mode_result import ModeResultRecord
from db.models.user import User
from flagdle.utils import generate_shades_token
from stats.registry import MODE_STATS_REGISTRY, resolve_mode_spec
from stats.service import record_mode_result
from users.utils import get_current_or_guest_user
from utils.guest_session import ALGORITHM, GUEST_IDENTITY_COOKIE, SECRET_KEY


TODAY = date(2026, 11, 20)
EARLIER_THIS_MONTH = date(2026, 11, 5)
PREV_MONTH = date(2026, 10, 15)


class AsyncSQLiteSession:
    """Minimal AsyncSession adapter over an in-memory SQLite Session for hermetic SQL tests."""

    def __init__(self, sync_session: Session):
        self._session = sync_session

    async def execute(self, statement, *args, **kwargs):
        return self._session.execute(statement, *args, **kwargs)

    async def scalar(self, statement, *args, **kwargs):
        return self._session.scalar(statement, *args, **kwargs)

    def add(self, instance):
        self._session.add(instance)

    def add_all(self, instances):
        self._session.add_all(instances)

    async def flush(self):
        self._session.flush()

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()


def _make_guest_cookie(guest_id: str) -> str:
    return jwt.encode(
        {
            "sub": guest_id,
            "purpose": "guest_identity",
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


@pytest.fixture
def stats_db():
    engine = create_engine("sqlite://")
    tables = [
        User.__table__,
        Country.__table__,
        CountrydleDay.__table__,
        CountrydleState.__table__,
        EnglishCounty.__table__,
        CountydleDay.__table__,
        CountydleState.__table__,
        ContinentalDay.__table__,
        ContinentalState.__table__,
        FlagdleDay.__table__,
        FlagdleState.__table__,
        GuestParticipation.__table__,
        HeraldryDailySession.__table__,
        QuizRun.__table__,
        ModeResultRecord.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as sync_session:
        sync_session.add_all(
            [
                User(id=1, username="alice", email="alice@example.com", hashed_password="x"),
                User(id=2, username="bob", email="bob@example.com", hashed_password="x"),
                User(id=3, username="charlie", email="charlie@example.com", hashed_password="x"),
                User(id=4, username="diana", email="diana@example.com", hashed_password="x"),
                User(id=5, username="test_bot", email="bot@example.com", hashed_password="x"),
                Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
                Country(id=2, name="Germany", official_name="Federal Republic of Germany", md_file="germany.md"),
                CountrydleDay(id=1, country_id=1, date=TODAY),
                CountrydleDay(id=2, country_id=2, date=EARLIER_THIS_MONTH),
                CountrydleDay(id=3, country_id=1, date=PREV_MONTH),
                ContinentalDay(id=10, country_id=1, continent=ContinentCode.EUROPE, date=TODAY),
                FlagdleDay(id=20, country_id=1, date=TODAY),
            ]
        )
        sync_session.commit()
        async_session = AsyncSQLiteSession(sync_session)

        async def _override_get_db():
            yield async_session

        app.dependency_overrides[get_db] = _override_get_db
        try:
            yield sync_session, async_session
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_or_guest_user, None)
    engine.dispose()


def test_registry_covers_all_existing_and_new_modes():
    expected_modes = {
        "countrydle",
        "wojewodztwodle",
        "powiatdle",
        "us_statedle",
        "continental:europe",
        "continental:asia",
        "continental:africa",
        "continental:americas",
        "flagdle",
        "heraldry",
        "county_flags",
        "regional_symbols:voivodeships:coat",
        "regional_symbols:voivodeships:flag",
        "regional_symbols:london_boroughs:coat",
        "regional_symbols:london_boroughs:flag",
        "regional_symbols:england_counties:coat",
        "regional_symbols:england_counties:flag",
        "coats_quiz",
        "county_flags_quiz",
        "regional_symbols:voivodeships:coat:quiz",
        "regional_symbols:voivodeships:flag:quiz",
        "regional_symbols:london_boroughs:coat:quiz",
        "regional_symbols:london_boroughs:flag:quiz",
        "regional_symbols:england_counties:coat:quiz",
        "regional_symbols:england_counties:flag:quiz",
        "flag_shades",
        "border_hop",
        "plates_quiz",
        "map_quiz_london_boroughs",
        "map_quiz_england_counties",
        "map_quiz_powiaty",
        "map_quiz_us_states",
        "countydle",
    }
    assert expected_modes.issubset(set(MODE_STATS_REGISTRY.keys()))
    assert resolve_mode_spec("powiat_plates_quiz").mode == "plates_quiz"
    assert resolve_mode_spec("london_boroughs_quiz").mode == "map_quiz_london_boroughs"
    assert resolve_mode_spec("historic_counties_quiz").mode == "map_quiz_england_counties"
    assert resolve_mode_spec("powiat_map_quiz").mode == "map_quiz_powiaty"
    assert resolve_mode_spec("us_state_map_quiz").mode == "map_quiz_us_states"
    assert resolve_mode_spec("english_countydle").mode == "countydle"
    assert resolve_mode_spec("nonexistent_mode") is None


@pytest.mark.anyio
async def test_qa_daily_summary_distributions_percentile_and_pinned_leaderboard(stats_db):
    db, _ = stats_db
    guest_uuid = str(uuid4())

    # Today's Countrydle plays:
    # alice (id=1): won in 2 Qs, 1 guess, 1900 pts
    # bob (id=2): won in 4 Qs, 2 guesses, 1500 pts
    # charlie (id=3): lost in 10 Qs, 3 guesses, 0 pts
    # diana (id=4): won in 6 Qs, 1 guess, 1200 pts
    # test_bot (id=5): should be excluded from leaderboard
    # guest: won in 4 Qs, 1 guess
    db.add_all(
        [
            CountrydleState(user_id=1, day_id=1, questions_asked=2, guesses_made=1, is_game_over=True, won=True, points=1900),
            CountrydleState(user_id=2, day_id=1, questions_asked=4, guesses_made=2, is_game_over=True, won=True, points=1500),
            CountrydleState(user_id=3, day_id=1, questions_asked=10, guesses_made=3, is_game_over=True, won=False, points=0),
            CountrydleState(user_id=4, day_id=1, questions_asked=6, guesses_made=1, is_game_over=True, won=True, points=1200),
            CountrydleState(user_id=5, day_id=1, questions_asked=1, guesses_made=1, is_game_over=True, won=True, points=2500),
            GuestParticipation(guest_id=guest_uuid, mode="countrydle", day_id=1, questions_asked=4, guesses_made=1, won=True),
            # Earlier this month (affects monthly + all_time)
            CountrydleState(user_id=4, day_id=2, questions_asked=3, guesses_made=1, is_game_over=True, won=True, points=1800),
            # Previous month (affects all_time only)
            CountrydleState(user_id=2, day_id=3, questions_asked=2, guesses_made=1, is_game_over=True, won=True, points=2000),
        ]
    )
    db.commit()

    # 1. Request as Diana (id=4) with limit=2 so Diana (daily rank #3) is pinned outside top 2
    diana = SimpleNamespace(id=4, username="diana")
    app.dependency_overrides[get_current_or_guest_user] = lambda: diana

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/stats/countrydle/summary?date={TODAY.isoformat()}&period=daily&limit=2")
        assert res.status_code == 200
        data = res.json()

        assert data["mode"] == "countrydle"
        assert data["mode_kind"] == "qa_daily"
        assert data["played_today"] == 6
        assert data["completed_today"] == 6
        assert data["winners_today"] == 5
        assert data["win_rate_pct"] == 83.3
        # Won Qs: 2, 4, 6, 1 (test_bot), 4 (guest) -> avg = 17/5 = 3.4
        assert data["avg_questions_won"] == 3.4
        # Won guesses: 1, 2, 1, 1, 1 -> avg = 1.2
        assert data["avg_guesses_won"] == 1.2

        # Distributions: Diana won in 6 Qs, 1 guess
        q_buckets = {b["label"]: b for b in data["distributions"]["questions"]}
        assert q_buckets["6"]["count"] == 1
        assert q_buckets["6"]["is_player"] is True
        assert q_buckets["4"]["count"] == 2
        assert q_buckets["X"]["count"] == 1

        g_buckets = {b["label"]: b for b in data["distributions"]["guesses"]}
        assert g_buckets["1"]["count"] == 4
        assert g_buckets["1"]["is_player"] is True
        assert g_buckets["X"]["count"] == 1

        # Player summary & cross-period ranks
        player = data["player"]
        assert player["played"] is True
        assert player["completed"] is True
        assert player["won"] is True
        assert player["questions_used"] == 6
        assert player["guesses_used"] == 1
        assert player["points"] == 1200
        # Diana beats charlie (loss) and ties/equals herself -> 2/6 = 33.3%
        assert player["percentile"] == 33.3
        # Daily: alice(1900), bob(1500), diana(1200), charlie(0) -> rank 3 (test_bot excluded)
        assert player["daily_rank"] == 3
        # Monthly: diana(3000), alice(1900), bob(1500), charlie(0) -> rank 1
        assert player["monthly_rank"] == 1
        # All-time: bob(3500), diana(3000), alice(1900), charlie(0) -> rank 2
        assert player["all_time_rank"] == 2

        # Leaderboard top 2 + pinned current_user_entry
        lb = data["leaderboard"]
        assert lb["total_ranked"] == 4
        assert [e["username"] for e in lb["entries"]] == ["alice", "bob"]
        assert lb["current_user_entry"] is not None
        assert lb["current_user_entry"]["username"] == "diana"
        assert lb["current_user_entry"]["rank"] == 3
        assert lb["current_user_entry"]["is_current_user"] is True

        # Check monthly & all_time leaderboard endpoint directly
        res_monthly = await client.get(f"/stats/countrydle/leaderboard?period=monthly&date={TODAY.isoformat()}&limit=10")
        assert res_monthly.status_code == 200
        assert [e["username"] for e in res_monthly.json()["entries"]] == ["diana", "alice", "bob", "charlie"]
        assert res_monthly.json()["current_user_entry"] is None  # Already in top 10

        res_all = await client.get(f"/stats/countrydle/leaderboard?period=all_time&date={TODAY.isoformat()}&limit=10")
        assert res_all.status_code == 200
        assert [e["username"] for e in res_all.json()["entries"]] == ["bob", "diana", "alice", "charlie"]

    # 2. Request as Guest (cookie highlighting)
    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={GUEST_IDENTITY_COOKIE: _make_guest_cookie(guest_uuid)},
    ) as client:
        res_guest = await client.get(f"/stats/countrydle/summary?date={TODAY.isoformat()}")
        assert res_guest.status_code == 200
        g_data = res_guest.json()
        assert g_data["player"]["played"] is True
        assert g_data["player"]["is_guest"] is True
        assert g_data["player"]["won"] is True
        assert g_data["player"]["questions_used"] == 4
        assert g_data["player"]["daily_rank"] is None
        q_buckets = {b["label"]: b for b in g_data["distributions"]["questions"]}
        assert q_buckets["4"]["is_player"] is True


@pytest.mark.anyio
async def test_heraldry_daily_and_quiz_run_stats(stats_db):
    db, _ = stats_db
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

    # Heraldry daily sessions
    db.add_all(
        [
            HeraldryDailySession(
                id=str(uuid4()),
                date=TODAY,
                symbol_mode="coat",
                entity_scope="county",
                user_id=1,
                target_id=10,
                target_name="Powiat A",
                guesses=[{"id": 10, "name": "Powiat A"}],
                started_at=now - timedelta(seconds=30),
                completed_at=now,
                won=True,
                points=2100,
            ),
            HeraldryDailySession(
                id=str(uuid4()),
                date=TODAY,
                symbol_mode="coat",
                entity_scope="county",
                user_id=2,
                target_id=10,
                target_name="Powiat A",
                guesses=[{"id": 1, "name": "X"}, {"id": 2, "name": "Y"}, {"id": 10, "name": "Powiat A"}],
                started_at=now - timedelta(seconds=90),
                completed_at=now,
                won=True,
                points=1700,
            ),
            # Plates quiz runs (new Area 1/3 mode using QuizRun with symbol_mode='plates')
            QuizRun(
                id=str(uuid4()),
                user_id=1,
                started_at=now,
                finished_at=now + timedelta(seconds=200),
                status="completed",
                symbol_mode="plates",
                entity_scope="county",
                elapsed_seconds=200.0,
                solved_count=380,
            ),
            QuizRun(
                id=str(uuid4()),
                user_id=2,
                started_at=now,
                finished_at=now + timedelta(seconds=150),
                status="given_up",
                symbol_mode="plates",
                entity_scope="county",
                elapsed_seconds=150.0,
                solved_count=190,
            ),
        ]
    )
    db.commit()

    alice = SimpleNamespace(id=1, username="alice")
    app.dependency_overrides[get_current_or_guest_user] = lambda: alice

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_h = await client.get(f"/stats/heraldry/summary?date={TODAY.isoformat()}")
        assert res_h.status_code == 200
        h_data = res_h.json()
        assert h_data["played_today"] == 2
        assert h_data["win_rate_pct"] == 100.0
        assert h_data["avg_guesses_won"] == 2.0
        assert h_data["avg_elapsed_seconds"] == 60.0
        assert h_data["distributions"]["questions"] is None
        assert h_data["distributions"]["guesses"] is not None
        g_map = {b["label"]: b for b in h_data["distributions"]["guesses"]}
        assert g_map["1"]["is_player"] is True
        assert [e["username"] for e in h_data["leaderboard"]["entries"]] == ["alice", "bob"]

        res_p = await client.get(f"/stats/plates_quiz/summary?date={TODAY.isoformat()}&period=all_time")
        assert res_p.status_code == 200
        p_data = res_p.json()
        assert p_data["mode"] == "plates_quiz"
        assert p_data["mode_kind"] == "quiz_run"
        assert p_data["played_today"] == 2
        assert p_data["avg_score"] == 285.0
        score_map = {b["label"]: b for b in p_data["distributions"]["score"]}
        assert score_map["100%"]["count"] == 1
        assert score_map["100%"]["is_player"] is True
        assert score_map["41-60%"]["count"] == 1
        assert p_data["leaderboard"]["entries"][0]["username"] == "alice"
        assert p_data["leaderboard"]["entries"][0]["best_score"] == 380


@pytest.mark.anyio
async def test_flag_shades_and_border_hop_record_and_query(stats_db):
    db, _ = stats_db
    today_utc = datetime.now(timezone.utc).date()
    poland = SimpleNamespace(id=1, name="Poland", official_name="Republic of Poland")
    germany = SimpleNamespace(id=2, name="Germany", official_name="Federal Republic of Germany")

    async def mock_get(cid):
        return poland if cid == 1 else germany if cid == 2 else None

    alice = SimpleNamespace(id=1, username="alice")
    app.dependency_overrides[get_current_or_guest_user] = lambda: alice

    # 1. Flag Shades terminal daily guess persists into mode_result_records
    daily_token = generate_shades_token(f"daily-{today_utc.isoformat()}", 1)
    with (
        patch("db.repositories.country.CountryRepository.get", side_effect=mock_get),
        patch("db.repositories.country.CountryRepository.get_all_countries", new_callable=AsyncMock, return_value=[poland, germany]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/flagdle/shades/guess",
                json={"token": daily_token, "guess": "Poland", "country_id": 1, "guesses_made": 3},
            )
            assert res.status_code == 200
            assert res.json()["won"] is True

            # Verify DB persistence
            rows = db.execute(select(ModeResultRecord).where(ModeResultRecord.mode == "flag_shades")).scalars().all()
            assert len(rows) == 1
            assert rows[0].user_id == 1
            assert rows[0].won is True
            assert rows[0].guesses_used == 3
            assert rows[0].points > 0

            # Verify /stats/flag_shades/summary surfaces the recorded result
            summary_res = await client.get(f"/stats/flag_shades/summary?date={today_utc.isoformat()}")
            assert summary_res.status_code == 200
            s_data = summary_res.json()
            assert s_data["played_today"] == 1
            assert s_data["winners_today"] == 1
            assert s_data["player"]["won"] is True
            assert s_data["player"]["guesses_used"] == 3
            g_map = {b["label"]: b for b in s_data["distributions"]["guesses"]}
            assert g_map["3"]["is_player"] is True

    # 2. Border Hop daily verify persists into mode_result_records
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_bh = await client.post(
            "/explore/border-hop/verify",
            json={
                "mode": "countries",
                "start": "Portugal",
                "target": "Poland",
                "path": ["Portugal", "Spain", "France", "Germany", "Poland"],
                "is_daily": True,
                "elapsed_seconds": 42.5,
            },
        )
        assert res_bh.status_code == 200
        assert res_bh.json()["valid"] is True
        assert res_bh.json()["rank"] == "gold"

        bh_rows = db.execute(select(ModeResultRecord).where(ModeResultRecord.mode == "border_hop")).scalars().all()
        assert len(bh_rows) == 1
        assert bh_rows[0].user_id == 1
        assert bh_rows[0].points == 1000
        assert bh_rows[0].score == 4
        assert bh_rows[0].max_score == 4

        bh_summary = await client.get(f"/stats/border_hop/summary?date={today_utc.isoformat()}")
        assert bh_summary.status_code == 200
        bh_data = bh_summary.json()
        assert bh_data["played_today"] == 1
        assert bh_data["player"]["points"] == 1000
        score_map = {b["label"]: b for b in bh_data["distributions"]["score"]}
        assert score_map["Optimal"]["count"] == 1
        assert score_map["Optimal"]["is_player"] is True


@pytest.mark.anyio
async def test_stats_error_handling_and_new_mode_placeholders(stats_db):
    _, async_session = stats_db
    await record_mode_result(
        async_session,
        mode="map_quiz_london_boroughs",
        record_date=None,
        user_id=1,
        guest_id=None,
        completed=True,
        won=True,
        points=33,
        score=33,
        max_score=33,
        elapsed_seconds=95.0,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_404 = await client.get("/stats/does_not_exist/summary")
        assert res_404.status_code == 404

        res_400 = await client.get("/stats/countrydle/summary?date=not-a-date")
        assert res_400.status_code == 400

        res_map = await client.get("/stats/map_quiz_london_boroughs/summary?period=all_time")
        assert res_map.status_code == 200
        assert res_map.json()["leaderboard"]["entries"][0]["username"] == "alice"

        res_county = await client.get(f"/stats/countydle/summary?date={TODAY.isoformat()}")
        assert res_county.status_code == 200
        assert res_county.json()["played_today"] == 0


@pytest.mark.anyio
async def test_powiat_and_us_state_map_quiz_stats(stats_db):
    db, async_session = stats_db
    today_utc = datetime.now(timezone.utc).date()

    # 1. Powiat Map Quiz recorded results + alias resolution
    await record_mode_result(
        async_session,
        mode="map_quiz_powiaty",
        record_date=today_utc,
        user_id=1,
        guest_id=None,
        completed=True,
        won=True,
        points=900,
        score=9,
        max_score=10,
        elapsed_seconds=48.0,
    )
    await record_mode_result(
        async_session,
        mode="map_quiz_powiaty",
        record_date=today_utc,
        user_id=2,
        guest_id=None,
        completed=True,
        won=False,
        points=400,
        score=4,
        max_score=10,
        elapsed_seconds=72.0,
    )

    alice = SimpleNamespace(id=1, username="alice")
    app.dependency_overrides[get_current_or_guest_user] = lambda: alice

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_powiat = await client.get(f"/stats/map_quiz_powiaty/summary?date={today_utc.isoformat()}")
        assert res_powiat.status_code == 200
        p_data = res_powiat.json()
        assert p_data["mode"] == "map_quiz_powiaty"
        assert p_data["played_today"] == 2
        assert p_data["winners_today"] == 1
        assert p_data["avg_score"] == 6.5
        assert p_data["player"]["score"] == 9
        assert p_data["player"]["won"] is True
        assert [e["username"] for e in p_data["leaderboard"]["entries"]] == ["alice", "bob"]

        res_powiat_alias = await client.get(f"/stats/powiat_map_quiz/summary?date={today_utc.isoformat()}")
        assert res_powiat_alias.status_code == 200
        assert res_powiat_alias.json()["mode"] == "map_quiz_powiaty"

        # 2. US State Map Quiz server-authoritative scope entities & deterministic daily targets
        res_entities = await client.get("/map-quiz/us_states/entities")
        assert res_entities.status_code == 200
        entities = res_entities.json()
        assert len(entities) == 50
        assert any(e["name"] == "California" for e in entities)

    # 3. US State Map Quiz recorded results (authenticated + guest) & summary/alias resolution
    guest_uuid = str(uuid4())
    await record_mode_result(
        async_session,
        mode="map_quiz_us_states",
        record_date=today_utc,
        user_id=1,
        guest_id=None,
        completed=True,
        won=True,
        points=950,
        score=8,
        max_score=10,
        elapsed_seconds=35.5,
    )
    await record_mode_result(
        async_session,
        mode="map_quiz_us_states",
        record_date=today_utc,
        user_id=None,
        guest_id=guest_uuid,
        completed=True,
        won=False,
        points=540,
        score=5,
        max_score=10,
        elapsed_seconds=52.0,
    )

    app.dependency_overrides[get_current_or_guest_user] = lambda: alice
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_us = await client.get(f"/stats/us_state_map_quiz/summary?date={today_utc.isoformat()}")
        assert res_us.status_code == 200
        u_data = res_us.json()
        assert u_data["mode"] == "map_quiz_us_states"
        assert u_data["played_today"] == 2
        assert u_data["player"]["score"] == 8
        assert u_data["leaderboard"]["entries"][0]["username"] == "alice"

    app.dependency_overrides[get_current_or_guest_user] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={GUEST_IDENTITY_COOKIE: _make_guest_cookie(guest_uuid)},
    ) as client:
        res_guest_summary = await client.get(f"/stats/map_quiz_us_states/summary?date={today_utc.isoformat()}")
        assert res_guest_summary.status_code == 200
        g_data = res_guest_summary.json()
        assert g_data["played_today"] == 2
        assert g_data["player"]["played"] is True
        assert g_data["player"]["is_guest"] is True
        assert g_data["player"]["score"] == 5
        assert g_data["player"]["won"] is False


@pytest.mark.anyio
async def test_in_progress_sessions_excluded_from_leaderboards_and_distributions(stats_db):
    db, _ = stats_db
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

    # User 1 finished Countrydle; User 2 asked 2 questions but has NOT finished (is_game_over=False)
    db.add_all(
        [
            CountrydleState(
                user_id=1, day_id=1, questions_asked=3, guesses_made=1, is_game_over=True, won=True, points=1700
            ),
            CountrydleState(
                user_id=2, day_id=1, questions_asked=2, guesses_made=0, is_game_over=False, won=False, points=0
            ),
            # Heraldry daily: User 1 finished; User 2 made 1 guess but has NOT finished (completed_at=None)
            HeraldryDailySession(
                id=str(uuid4()),
                date=TODAY,
                symbol_mode="coat",
                entity_scope="county",
                user_id=1,
                target_id=10,
                target_name="Powiat A",
                guesses=[{"id": 10, "name": "Powiat A"}],
                started_at=now - timedelta(seconds=20),
                completed_at=now,
                won=True,
                points=2100,
            ),
            HeraldryDailySession(
                id=str(uuid4()),
                date=TODAY,
                symbol_mode="coat",
                entity_scope="county",
                user_id=2,
                target_id=10,
                target_name="Powiat A",
                guesses=[{"id": 99, "name": "Powiat X"}],
                started_at=now - timedelta(seconds=10),
                completed_at=None,
                won=False,
                points=0,
            ),
        ]
    )
    db.commit()

    alice = SimpleNamespace(id=1, username="alice")
    app.dependency_overrides[get_current_or_guest_user] = lambda: alice

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Countrydle daily + monthly leaderboards must only include alice (not in-progress bob)
        res_c = await client.get(f"/stats/countrydle/summary?date={TODAY.isoformat()}&period=daily")
        assert res_c.status_code == 200
        c_data = res_c.json()
        assert c_data["played_today"] == 2
        assert c_data["completed_today"] == 1
        assert [e["username"] for e in c_data["leaderboard"]["entries"]] == ["alice"]
        assert c_data["leaderboard"]["total_ranked"] == 1

        res_c_mo = await client.get(f"/stats/countrydle/leaderboard?date={TODAY.isoformat()}&period=monthly")
        assert res_c_mo.status_code == 200
        assert [e["username"] for e in res_c_mo.json()["entries"]] == ["alice"]

        # Heraldry daily + monthly leaderboards must only include alice (not in-progress bob)
        res_h = await client.get(f"/stats/heraldry/summary?date={TODAY.isoformat()}&period=daily")
        assert res_h.status_code == 200
        h_data = res_h.json()
        assert h_data["played_today"] == 2
        assert h_data["completed_today"] == 1
        assert [e["username"] for e in h_data["leaderboard"]["entries"]] == ["alice"]
        assert h_data["leaderboard"]["total_ranked"] == 1

        res_h_mo = await client.get(f"/stats/heraldry/leaderboard?date={TODAY.isoformat()}&period=monthly")
        assert res_h_mo.status_code == 200
        assert [e["username"] for e in res_h_mo.json()["entries"]] == ["alice"]
