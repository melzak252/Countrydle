"""Automated tests for Admin Gameplay Sessions & AI Truthfulness Audit APIs."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app import app
from db import get_db
from db.base import Base
from db.models import (
    AnswerReport,
    ContinentCode,
    ContinentalDay,
    ContinentalGuess,
    ContinentalQuestion,
    ContinentalState,
    Country,
    CountrydleDay,
    CountrydleGuess,
    CountrydleQuestion,
    CountrydleState,
    GuestParticipation,
    Powiat,
    PowiatdleDay,
    PowiatdleGuess,
    PowiatdleQuestion,
    PowiatdleState,
    USState,
    USStatedleDay,
    USStatedleGuess,
    USStatedleQuestion,
    USStatedleState,
    User,
    Wojewodztwo,
    WojewodztwodleDay,
    WojewodztwodleGuess,
    WojewodztwodleQuestion,
    WojewodztwodleState,
)
from db.models.fallback_answer import FallbackAnswer, FallbackAnswerBlock
from db.repositories import fallback_answers
from users.utils import get_admin_user, get_current_user

pytestmark = pytest.mark.anyio


class AsyncSessionAdapter:
    def __init__(self, session: Session):
        self.session = session

    def get_bind(self):
        return self.session.get_bind()

    async def execute(self, statement):
        return self.session.execute(statement)

    async def get(self, model, key):
        return self.session.get(model, key)

    def add(self, instance):
        self.session.add(instance)

    def add_all(self, instances):
        self.session.add_all(instances)

    async def commit(self):
        self.session.commit()

    async def flush(self):
        self.session.flush()

    async def refresh(self, instance):
        self.session.refresh(instance)

    async def rollback(self):
        self.session.rollback()


@pytest.fixture
async def admin_fixture(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "admin-audit-secret-key")
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        User.__table__,
        Country.__table__,
        CountrydleDay.__table__,
        CountrydleQuestion.__table__,
        CountrydleGuess.__table__,
        CountrydleState.__table__,
        Powiat.__table__,
        PowiatdleDay.__table__,
        PowiatdleQuestion.__table__,
        PowiatdleGuess.__table__,
        PowiatdleState.__table__,
        USState.__table__,
        USStatedleDay.__table__,
        USStatedleQuestion.__table__,
        USStatedleGuess.__table__,
        USStatedleState.__table__,
        Wojewodztwo.__table__,
        WojewodztwodleDay.__table__,
        WojewodztwodleQuestion.__table__,
        WojewodztwodleGuess.__table__,
        WojewodztwodleState.__table__,
        ContinentalDay.__table__,
        ContinentalQuestion.__table__,
        ContinentalGuess.__table__,
        ContinentalState.__table__,
        GuestParticipation.__table__,
        AnswerReport.__table__,
        FallbackAnswer.__table__,
        FallbackAnswerBlock.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    test_date = date(2026, 9, 20)

    with Session(engine, expire_on_commit=False) as session:
        # Users
        admin_user = User(id=1, username="admin_alice", email="admin@example.com", is_admin=True)
        regular_user = User(id=2, username="player_bob", email="bob@example.com", is_admin=False)
        session.add_all([admin_user, regular_user])
        session.commit()

        # Seed target entities
        poland = Country(id=1, name="Poland", md_file="poland.md")
        krakowski = Powiat(id=1, nazwa="powiat krakowski")
        texas = USState(id=1, name="Texas", code="TX")
        malopolskie = Wojewodztwo(id=1, nazwa="małopolskie")
        france = Country(id=2, name="France", md_file="france.md")
        session.add_all([poland, krakowski, texas, malopolskie, france])
        session.commit()

        # Seed Days
        c_day = CountrydleDay(id=1, country_id=poland.id, date=test_date)
        p_day = PowiatdleDay(id=1, powiat_id=krakowski.id, date=test_date)
        us_day = USStatedleDay(id=1, us_state_id=texas.id, date=test_date)
        w_day = WojewodztwodleDay(id=1, wojewodztwo_id=malopolskie.id, date=test_date)
        cont_day = ContinentalDay(id=1, continent=ContinentCode.EUROPE, country_id=france.id, date=test_date)
        session.add_all([c_day, p_day, us_day, w_day, cont_day])
        session.commit()

        # Seed Questions
        # 1. Countrydle question - Local KB
        q1 = CountrydleQuestion(
            id=1,
            user_id=regular_user.id,
            day_id=c_day.id,
            original_question="Is it in Europe?",
            question="Is the country in Europe?",
            valid=True,
            answer=True,
            explanation="Poland is located in Central Europe.",
            context="local_kb:continent",
            asked_at=datetime(2026, 9, 20, 10, 0, 0),
        )
        # 2. Countrydle question - Fallback LLM with context & Report
        q2 = CountrydleQuestion(
            id=2,
            user_id=None,
            guest_id="guest-uuid-1234",
            day_id=c_day.id,
            original_question="Did Poland win the 1974 World Cup?",
            question="Did Poland win the 1974 World Cup?",
            valid=True,
            answer=False,
            explanation="Poland took 3rd place in 1974, not 1st.",
            context="Poland national football team finished third in the 1974 FIFA World Cup.",
            asked_at=datetime(2026, 9, 20, 10, 2, 0),
        )
        # 3. Powiatdle question - Local KB
        q3 = PowiatdleQuestion(
            id=1,
            user_id=regular_user.id,
            day_id=p_day.id,
            original_question="Czy ma tablice KRA?",
            question="Czy ten powiat ma wyróżnik tablic KRA?",
            valid=True,
            answer=True,
            explanation="Powiat krakowski ma tablice rejestracyjne KRA.",
            context="local_kb:license_plate",
            asked_at=datetime(2026, 9, 20, 10, 5, 0),
        )
        # 4. US Statedle question - Invalid
        q4 = USStatedleQuestion(
            id=1,
            user_id=regular_user.id,
            day_id=us_day.id,
            original_question="What is the weather?",
            valid=False,
            answer=None,
            explanation="Please ask a yes/no question about geographical facts.",
            context="local_planner:invalid",
            asked_at=datetime(2026, 9, 20, 10, 8, 0),
        )
        # 5. Continental question - Local KB
        q5 = ContinentalQuestion(
            id=1,
            user_id=regular_user.id,
            day_id=cont_day.id,
            original_question="Does it border Spain?",
            valid=True,
            answer=True,
            explanation="France borders Spain along the Pyrenees.",
            context="local_kb:borders",
            asked_at=datetime(2026, 9, 20, 10, 10, 0),
        )
        session.add_all([q1, q2, q3, q4, q5])
        session.commit()

        # Seed AnswerReport on q2
        report = AnswerReport(
            id=1,
            mode="countrydle",
            question_id=q2.id,
            reporter_id=regular_user.id,
            comment="Wrong answer explanation",
            details={
                "target_name": "Poland",
                "original_question": q2.original_question,
                "context": q2.context,
            },
            created_at=datetime(2026, 9, 20, 10, 5, 0),
        )
        session.add(report)

        # Seed Guesses for session replay
        g1 = CountrydleGuess(
            id=1,
            user_id=regular_user.id,
            day_id=c_day.id,
            guess="Germany",
            answer=False,
            guessed_at=datetime(2026, 9, 20, 10, 1, 0),
        )
        g2 = CountrydleGuess(
            id=2,
            user_id=regular_user.id,
            day_id=c_day.id,
            guess="Poland",
            answer=True,
            guessed_at=datetime(2026, 9, 20, 10, 3, 0),
        )
        # Guest guess
        g3 = CountrydleGuess(
            id=3,
            user_id=None,
            guest_id="guest-uuid-1234",
            day_id=c_day.id,
            guess="Czech Republic",
            answer=False,
            guessed_at=datetime(2026, 9, 20, 10, 4, 0),
        )
        session.add_all([g1, g2, g3])

        # Seed Game State for regular user
        state = CountrydleState(
            id=1,
            user_id=regular_user.id,
            day_id=c_day.id,
            remaining_questions=9,
            remaining_guesses=1,
            questions_asked=1,
            guesses_made=2,
            is_game_over=True,
            won=True,
        )
        # Seed GuestParticipation
        gp = GuestParticipation(
            id=1,
            guest_id="guest-uuid-1234",
            mode="countrydle",
            day_id=c_day.id,
            questions_asked=1,
            guesses_made=1,
            won=False,
        )
        session.add_all([state, gp])

        # Seed fallback answer cache for q2
        identity = fallback_answers.make_identity(
            mode="countrydle",
            entity_id=poland.id,
            entity_name="Poland",
            original_question=q2.original_question,
            question=q2.question,
            context=q2.context,
            system_prompt="Rules",
            question_prompt="Data",
            model="gpt-4o-mini",
            game_date=test_date,
        )
        fb_answer = FallbackAnswer(
            key=identity.key,
            signature=identity.signature,
            game_date=test_date,
            answer=False,
            explanation="Poland took 3rd place in 1974.",
        )
        session.add(fb_answer)
        session.commit()

        adapter = AsyncSessionAdapter(session)

        async def get_test_db():
            yield adapter

        app.dependency_overrides[get_db] = get_test_db
        app.dependency_overrides[get_admin_user] = lambda: admin_user

        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        yield SimpleNamespace(
            client=client,
            session=adapter,
            admin=admin_user,
            user=regular_user,
            test_date=test_date,
            q2=q2,
            identity=identity,
        )

        app.dependency_overrides.clear()
    engine.dispose()


async def test_admin_live_feed_target_and_source(admin_fixture):
    response = await admin_fixture.client.get("/admin/live-feed")
    assert response.status_code == 200
    data = response.json()
    questions = {(item["mode"], item["id"]): item for item in data["recent_questions"]}
    expected = [
        ("countrydle", 1, "Poland", "local_kb", True, True),
        ("countrydle", 2, "Poland", "fallback", True, False),
        ("powiatdle", 1, "powiat krakowski", "local_kb", True, True),
        ("us_statedle", 1, "Texas", "invalid", False, None),
        ("continental", 1, "France", "local_kb", True, True),
    ]
    for mode, question_id, target, source, valid, answer in expected:
        item = questions[(mode, question_id)]
        assert (item["target_name"], item["source"], item["valid"], item["answer"]) == (
            target, source, valid, answer
        )
    assert questions[("us_statedle", 1)]["target_subtitle"] == "TX"
    guesses = {(item["mode"], item["id"]): item for item in data["recent_guesses"]}
    for guess_id, guess, answer in [(1, "Germany", False), (2, "Poland", True), (3, "Czech Republic", False)]:
        item = guesses[("countrydle", guess_id)]
        assert (item["guess"], item["answer"], item["target_name"]) == (guess, answer, "Poland")


async def test_admin_questions_list_multi_mode(admin_fixture):
    """Verify questions return correct target_name, source, relation, and has_report across modes."""
    response = await admin_fixture.client.get("/admin/questions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5

    items_by_mode = {item["mode"]: item for item in data["items"]}

    # 1. Countrydle question check
    c_q = next(item for item in data["items"] if item["id"] == 1 and item["mode"] == "countrydle")
    assert c_q["target_name"] == "Poland"
    assert c_q["source"] == "local_kb"
    assert c_q["relation"] == "continent"
    assert c_q["has_report"] is False
    assert c_q["username"] == "player_bob"
    assert c_q["is_guest"] is False

    # 2. Countrydle question with report and fallback
    reported_q = next(item for item in data["items"] if item["id"] == 2 and item["mode"] == "countrydle")
    assert reported_q["target_name"] == "Poland"
    assert reported_q["source"] == "fallback"
    assert reported_q["has_report"] is True
    assert reported_q["report_id"] == 1
    assert reported_q["is_guest"] is True
    assert "Guest" in reported_q["username"]

    # 3. Powiatdle check
    p_q = items_by_mode["powiatdle"]
    assert p_q["target_name"] == "powiat krakowski"
    assert p_q["source"] == "local_kb"
    assert p_q["relation"] == "license_plate"

    # 4. US Statedle check (Invalid)
    us_q = items_by_mode["us_statedle"]
    assert us_q["target_name"] == "Texas"
    assert us_q["target_subtitle"] == "TX"
    assert us_q["source"] == "invalid"
    assert us_q["valid"] is False

    # 5. Continental check
    cont_q = items_by_mode["continental"]
    assert cont_q["target_name"] == "France"
    assert cont_q["source"] == "local_kb"
    assert cont_q["relation"] == "borders"


async def test_admin_questions_filtering_and_search(admin_fixture):
    """Verify server-side filtering by mode, search substring, source, answer, and report."""
    client = admin_fixture.client

    # 1. Mode filter
    res = await client.get("/admin/questions?mode=powiatdle")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["mode"] == "powiatdle"

    # 2. Search substring in question text
    res = await client.get("/admin/questions?search=1974")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert "1974" in data["items"][0]["original_question"]

    # 3. Search target entity name
    res = await client.get("/admin/questions?search=Texas")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["target_name"] == "Texas"

    # 4. Source filter: fallback
    res = await client.get("/admin/questions?source=fallback")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["source"] == "fallback"

    # 5. Source filter: local_kb
    res = await client.get("/admin/questions?source=local_kb")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    for it in data["items"]:
        assert it["source"] == "local_kb"

    # 6. Source filter: invalid
    res = await client.get("/admin/questions?source=invalid")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["valid"] is False

    # 7. Answer filter: YES
    res = await client.get("/admin/questions?answer=yes")
    assert res.status_code == 200
    data = res.json()
    for it in data["items"]:
        assert it["valid"] is True and it["answer"] is True

    # 8. Has report filter: True
    res = await client.get("/admin/questions?has_report=true")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["has_report"] is True


async def test_admin_game_sessions_timeline(admin_fixture):
    """Verify GET /admin/game-sessions returns chronologically ordered timeline events with timestamps."""
    client = admin_fixture.client
    res = await client.get(f"/admin/game-sessions?mode=countrydle&date={admin_fixture.test_date.isoformat()}")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 2  # 1 registered user session + 1 guest session
    sessions = data["items"]

    # Find registered user session
    user_sess = next(s for s in sessions if not s["is_guest"])
    assert user_sess["username"] == "player_bob"
    assert user_sess["target_name"] == "Poland"
    assert user_sess["status"] == "won"
    assert user_sess["questions_asked"] == 1
    assert user_sess["guesses_made"] == 2
    assert user_sess["duration_seconds"] == 180  # 10:00:00 to 10:03:00 = 180 seconds

    # Timeline ordering check
    tl = user_sess["timeline"]
    assert len(tl) == 3
    assert tl[0]["event_type"] == "question"
    assert tl[0]["question"] == "Is the country in Europe?"
    assert tl[0]["answer"] is True
    assert tl[0]["source"] == "local_kb"

    assert tl[1]["event_type"] == "guess"
    assert tl[1]["guess"] == "Germany"
    assert tl[1]["correct"] is False

    assert tl[2]["event_type"] == "guess"
    assert tl[2]["guess"] == "Poland"
    assert tl[2]["correct"] is True

    # Guest session check
    guest_sess = next(s for s in sessions if s["is_guest"])
    assert guest_sess["is_guest"] is True
    assert "guest-uuid" in guest_sess["session_id"]
    assert len(guest_sess["timeline"]) == 2


async def test_admin_game_sessions_stats(admin_fixture):
    """Verify deduction strategy stats aggregate questions and guesses for the daily target."""
    client = admin_fixture.client
    res = await client.get(f"/admin/game-sessions/stats?mode=countrydle&date={admin_fixture.test_date.isoformat()}")
    assert res.status_code == 200
    stats = res.json()

    assert stats["target_name"] == "Poland"
    assert stats["total_players"] == 2
    assert stats["win_rate_pct"] == 50.0  # 1 winner out of 2 players

    # Top questions
    assert len(stats["top_questions"]) >= 1
    top_q = next((q for q in stats["top_questions"] if "Europe" in q["text"]), None)
    assert top_q is not None
    assert top_q["count"] == 1
    assert top_q["yes_pct"] == 100.0
    assert top_q["win_correlation"] == 100.0

    # Top guesses
    assert len(stats["top_guesses"]) >= 2
    correct_g = next(g for g in stats["top_guesses"] if g["guess"] == "Poland")
    assert correct_g["correct_pct"] == 100.0

    mistake_g = next(g for g in stats["top_guesses"] if g["guess"] == "Germany")
    assert mistake_g["correct_pct"] == 0.0


async def test_admin_invalidate_fallback_answer(admin_fixture):
    """Verify invalidating a question via POST /admin/questions/invalidate-fallback removes cached answer."""
    client = admin_fixture.client
    session = admin_fixture.session

    # Verify cached answer exists initially
    ans = (
        await session.execute(
            select(FallbackAnswer).where(FallbackAnswer.signature == admin_fixture.identity.signature)
        )
    ).scalar_one_or_none()
    assert ans is not None

    # Call invalidate endpoint on q2
    payload = {"mode": "countrydle", "question_id": 2}
    res = await client.post("/admin/questions/invalidate-fallback", json=payload)
    assert res.status_code == 200
    resp_data = res.json()
    assert resp_data["success"] is True
    assert "invalidated" in resp_data["message"]

    # Verify cached answer is deleted from FallbackAnswer
    deleted = (
        await session.execute(
            select(FallbackAnswer).where(FallbackAnswer.signature == admin_fixture.identity.signature)
        )
    ).scalar_one_or_none()
    assert deleted is None

    # Verify signature is blocked in FallbackAnswerBlock
    blocked = (
        await session.execute(
            select(FallbackAnswerBlock).where(FallbackAnswerBlock.signature == admin_fixture.identity.signature)
        )
    ).scalar_one_or_none()
    assert blocked is not None

    # Attempting to invalidate a non-fallback (local_kb) question should return 400
    res_err = await client.post("/admin/questions/invalidate-fallback", json={"mode": "countrydle", "question_id": 1})
    assert res_err.status_code == 400
    assert "not answered by AI fallback" in res_err.json()["detail"]

async def test_admin_endpoints_permission_guard(admin_fixture):
    """Verify unauthorized or non-admin requests are properly rejected."""
    unauthed_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    # 1. Anonymous request -> 401
    app.dependency_overrides.pop(get_admin_user, None)
    app.dependency_overrides.pop(get_current_user, None)
    res_anon = await unauthed_client.get("/admin/questions")
    assert res_anon.status_code == 401
    feed_anon = await unauthed_client.get("/admin/live-feed")
    assert feed_anon.status_code == 401

    # 2. Non-admin user -> 403
    app.dependency_overrides[get_current_user] = lambda: admin_fixture.user
    res_forbidden = await unauthed_client.get("/admin/questions")
    assert res_forbidden.status_code == 403
    feed_forbidden = await unauthed_client.get("/admin/live-feed")
    assert feed_forbidden.status_code == 403

    res_forbidden_sess = await unauthed_client.get("/admin/game-sessions")
    assert res_forbidden_sess.status_code == 403

    res_forbidden_post = await unauthed_client.post(
        "/admin/questions/invalidate-fallback",
        json={"mode": "countrydle", "question_id": 1},
    )
    assert res_forbidden_post.status_code == 403
