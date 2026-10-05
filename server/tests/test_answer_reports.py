"""Report API contracts against real SQL persistence without external services."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app import app
from db import get_db
from db.base import Base
from db.models import (
    ContinentCode, ContinentalDay, ContinentalQuestion, Country, CountrydleDay,
    CountrydleQuestion, Powiat, PowiatdleDay, PowiatdleQuestion, USState,
    USStatedleDay, USStatedleQuestion, User, Wojewodztwo, WojewodztwodleDay,
    WojewodztwodleQuestion,
)
from schemas.continental import ContinentalQuestionDisplay, InvalidContinentalQuestionDisplay
from schemas.countrydle import FullQuestionDisplay, InvalidQuestionDisplay
from schemas.powiatdle import PowiatQuestionDisplay
from schemas.us_statedle import USStateQuestionDisplay
from schemas.wojewodztwodle import WojewodztwoQuestionDisplay
from users.utils import get_current_or_guest_user, get_current_user


MODES = {
    "countrydle": (Country, CountrydleDay, CountrydleQuestion, FullQuestionDisplay, "country_id", {"name": "Poland", "md_file": "poland.md"}),
    "us_statedle": (USState, USStatedleDay, USStatedleQuestion, USStateQuestionDisplay, "us_state_id", {"name": "Alaska"}),
    "powiatdle": (Powiat, PowiatdleDay, PowiatdleQuestion, PowiatQuestionDisplay, "powiat_id", {"nazwa": "krakowski"}),
    "wojewodztwodle": (Wojewodztwo, WojewodztwodleDay, WojewodztwodleQuestion, WojewodztwoQuestionDisplay, "wojewodztwo_id", {"nazwa": "mazowieckie"}),
    "continental": (Country, ContinentalDay, ContinentalQuestion, ContinentalQuestionDisplay, "country_id", {"name": "Italy", "md_file": "italy.md"}),
}


class AsyncSessionAdapter:
    """Exercise SQLAlchemy queries/constraints using the stdlib SQLite driver."""

    def __init__(self, session):
        self.session = session

    def get_bind(self):
        return self.session.get_bind()

    async def execute(self, statement):
        return self.session.execute(statement)

    async def get(self, model, key):
        return self.session.get(model, key)

    def add(self, instance):
        self.session.add(instance)

    async def commit(self):
        self.session.commit()

    async def refresh(self, instance):
        self.session.refresh(instance)

    async def rollback(self):
        self.session.rollback()


@pytest.fixture
async def reports_api(monkeypatch):
    from db.repositories import fallback_answers as answer_cache

    monkeypatch.setenv("SECRET_KEY", "report-tests-secret")
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    seen_tables = {User.__table__}
    tables = [User.__table__]
    for entity, day, question, *_ in MODES.values():
        for t in (entity.__table__, day.__table__, question.__table__):
            if t not in seen_tables:
                seen_tables.add(t)
                tables.append(t)
    for table_name in ("answer_reports", "fallback_answers", "fallback_answer_blocks"):
        table = Base.metadata.tables.get(table_name)
        if table is not None and table not in seen_tables:
            seen_tables.add(table)
            tables.append(table)
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine, expire_on_commit=False) as session:
        owner = User(id=1, username="owner", email="owner@example.com", is_admin=False)
        outsider = User(id=2, username="outsider", email="outsider@example.com", is_admin=False)
        admin = User(id=3, username="admin", email="admin@example.com", is_admin=True)
        session.add_all([owner, outsider, admin])
        session.commit()
        questions = {}
        for mode, (entity_cls, day_cls, question_cls, _, fk, fields) in MODES.items():
            eid = 2 if mode == "continental" else 1
            entity = session.get(entity_cls, eid)
            if entity is None:
                entity = entity_cls(id=eid, **fields)
                session.add(entity)
                session.flush()
            day_kwargs = {fk: eid}
            if mode == "continental":
                day_kwargs["continent"] = ContinentCode.EUROPE
            day = day_cls(id=1, date=date(2026, 9, 20), **day_kwargs)
            session.add(day)
            session.flush()
            question = question_cls(
                id=1, user_id=owner.id, day_id=1,
                original_question="Original player question?", question="Canonical question?",
                valid=True, answer=False, explanation="Persisted explanation",
                context="Private retrieved context", asked_at=datetime(2026, 9, 20, 12),
            )
            if mode == "countrydle":
                question.server_version = "test-version"
            session.add(question)
            questions[mode] = question
        session.commit()
        adapter = AsyncSessionAdapter(session)

        async def database():
            yield adapter

        app.dependency_overrides[get_db] = database
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield SimpleNamespace(client=client, session=session, owner=owner, outsider=outsider, admin=admin, questions=questions)
        for dependency in (get_db, get_current_user, get_current_or_guest_user):
            app.dependency_overrides.pop(dependency, None)
    engine.dispose()


def login(user):
    async def current_user():
        return user

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_current_or_guest_user] = current_user


def token_for(api, mode, question=None):
    schema = MODES[mode][3]
    return schema.model_validate(question or api.questions[mode]).model_dump()["report_token"]


def payload(mode="countrydle", **overrides):
    return {"mode": mode, "question_id": 1, "comment": "  The answer seems incorrect.  ", **overrides}


@pytest.mark.anyio
@pytest.mark.parametrize("mode", MODES)
async def test_owner_submission_snapshots_canonical_data_without_leaking_it(reports_api, mode):
    api = reports_api
    login(api.owner)
    response = await api.client.post("/answer-reports", json=payload(mode))
    assert response.status_code == 201
    report_id = response.json()["id"]
    assert response.json() == {"id": report_id}

    # Later question edits must not rewrite an already-submitted report.
    api.questions[mode].context = "Changed after submission"
    api.questions[mode].explanation = "Changed after submission"
    api.session.commit()
    login(api.admin)
    response = await api.client.get("/admin/answer-reports")
    assert response.status_code == 200
    report = response.json()["items"][0]
    assert report["comment"] == "The answer seems incorrect."
    assert report["reporter_username"] == "owner"
    assert report["details"] == {
        "original_question": "Original player question?", "question": "Canonical question?",
        "valid": True, "answer": False, "explanation": "Persisted explanation",
        "context": "Private retrieved context", "day_id": 1, "game_date": "2026-09-20",
        "target_name": next(iter(MODES[mode][5].values())),
        "server_version": "test-version" if mode == "countrydle" else None,
    }
    assert "report_token" not in report


@pytest.mark.anyio
async def test_client_cannot_spoof_report_snapshot(reports_api):
    login(reports_api.owner)
    response = await reports_api.client.post("/answer-reports", json=payload(details={"target_name": "fake"}, context="fake", answer=True))
    assert response.status_code == 422
    login(reports_api.admin)
    assert (await reports_api.client.get("/admin/answer-reports")).json()["total"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize("mode", MODES)
async def test_guest_token_remains_valid_after_question_is_synced(reports_api, mode):
    api = reports_api
    question = api.questions[mode]
    question.user_id = None
    question.valid = False
    question.answer = None
    question.question = None
    api.session.commit()
    token = token_for(api, mode)
    question.user_id = api.owner.id
    api.session.commit()
    response = await api.client.post("/answer-reports", json=payload(mode, report_token=token))
    assert response.status_code == 201
    login(api.admin)
    report = (await api.client.get("/admin/answer-reports")).json()["items"][0]
    assert report["reporter_username"] is None
    assert report["details"]["valid"] is False
    assert report["details"]["answer"] is None


@pytest.mark.anyio
async def test_nonexistent_question_or_mode_cannot_be_reported(reports_api):
    api = reports_api
    attempts = [
        payload("us_statedle", question_id=999),
        payload("countrydle", question_id=999),
    ]
    login(api.outsider)
    for body in attempts:
        response = await api.client.post("/answer-reports", json=body)
        assert response.status_code == 404
        assert set(response.json()) == {"detail"}
        assert "Private retrieved context" not in response.text

@pytest.mark.anyio
@pytest.mark.parametrize("comment", [" \n\t ", "x" * 2001])
async def test_comment_validation_rejects_empty_or_overlong_comments(reports_api, comment):
    login(reports_api.owner)
    assert (await reports_api.client.post("/answer-reports", json=payload(comment=comment))).status_code == 422


@pytest.mark.anyio
async def test_trimmed_comment_limit_and_duplicate_constraint(reports_api):
    api = reports_api
    login(api.owner)
    response = await api.client.post("/answer-reports", json=payload(comment="  " + "x" * 2000 + "  "))
    assert response.status_code == 201
    assert (await api.client.post("/answer-reports", json=payload())).status_code == 409
    login(api.admin)
    reports = (await api.client.get("/admin/answer-reports")).json()
    assert reports["total"] == 1
    assert reports["items"][0]["comment"] == "x" * 2000


@pytest.mark.anyio
async def test_admin_permissions_review_transitions_filters_and_pagination(reports_api):
    api = reports_api
    for method, path, kwargs in [("get", "/admin/answer-reports", {}), ("patch", "/admin/answer-reports/1", {"json": {"reviewed": True}})]:
        assert (await getattr(api.client, method)(path, **kwargs)).status_code == 401
    login(api.owner)
    ids = []
    for mode in ("countrydle", "us_statedle"):
        ids.append((await api.client.post("/answer-reports", json=payload(mode))).json()["id"])
    assert (await api.client.get("/admin/answer-reports")).status_code == 403
    assert (await api.client.patch(f"/admin/answer-reports/{ids[0]}", json={"reviewed": True})).status_code == 403
    login(api.admin)
    reviewed = await api.client.patch(f"/admin/answer-reports/{ids[0]}", json={"reviewed": True})
    assert reviewed.status_code == 200
    reviewed_at = reviewed.json()["reviewed_at"]
    assert reviewed_at is not None
    repeated = await api.client.patch(f"/admin/answer-reports/{ids[0]}", json={"reviewed": True})
    assert repeated.json()["reviewed_at"] == reviewed_at
    assert (await api.client.get("/admin/answer-reports?status=open")).json()["items"][0]["mode"] == "us_statedle"
    assert (await api.client.get("/admin/answer-reports?status=reviewed")).json()["total"] == 1
    page = (await api.client.get("/admin/answer-reports?status=all&page=2&limit=1")).json()
    assert page["total"] == 2
    assert page["items"][0]["id"] == ids[0]
    filtered = (await api.client.get("/admin/answer-reports?status=all&mode=countrydle")).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == ids[0]
    reopened = await api.client.patch(f"/admin/answer-reports/{ids[0]}", json={"reviewed": False})
    assert reopened.json()["reviewed_at"] is None
    assert (await api.client.get("/admin/answer-reports?status=open")).json()["total"] == 2
    assert (await api.client.patch("/admin/answer-reports/999", json={"reviewed": True})).status_code == 404
    assert (await api.client.get("/admin/answer-reports?status=bad")).status_code == 422
    assert (await api.client.get("/admin/answer-reports?page=0")).status_code == 422


@pytest.mark.anyio
async def test_synthetic_question_is_not_reportable(reports_api):
    api = reports_api
    for mode, (_, _, _, schema, *_) in MODES.items():
        data = schema.model_validate(api.questions[mode]).model_dump()
        data["id"] = 0
        assert schema.model_validate(data).model_dump()["report_token"] is None
    invalid = InvalidQuestionDisplay.model_validate(api.questions["countrydle"])
    assert invalid.model_dump()["report_token"] == token_for(api, "countrydle")
    invalid_continental = InvalidContinentalQuestionDisplay.model_validate(api.questions["continental"])
    assert invalid_continental.model_dump()["report_token"] == token_for(api, "continental")
    login(api.owner)
    assert (await api.client.post("/answer-reports", json=payload(question_id=0))).status_code == 422


@pytest.mark.anyio
async def test_guest_token_auto_resolves_mode_on_mismatch_and_rejects_invalid(reports_api):
    api = reports_api
    login(None)
    # 1. Guest without token is rejected
    res_no_tok = await api.client.post("/answer-reports", json=payload("countrydle"))
    assert res_no_tok.status_code == 403

    # 2. Guest with invalid token is rejected
    res_bad_tok = await api.client.post("/answer-reports", json=payload("countrydle", report_token="bad-token"))
    assert res_bad_tok.status_code == 403

    # 3. Guest with continental token sent with mode=countrydle auto-resolves to continental
    token = token_for(api, "continental")
    res_mismatch = await api.client.post("/answer-reports", json=payload("countrydle", report_token=token))
    assert res_mismatch.status_code == 201
    login(api.admin)
    report = (await api.client.get("/admin/answer-reports")).json()["items"][0]
    assert report["mode"] == "continental"
    assert report["details"]["target_name"] == next(iter(MODES["continental"][5].values()))


@pytest.mark.anyio
async def test_admin_template_divergences_api(reports_api):
    from db.models.template_divergence import TemplateDivergence
    from db.base import Base
    from users.utils import get_admin_user

    api = reports_api
    # Create table in the test sqlite engine
    if "template_divergences" in Base.metadata.tables:
        Base.metadata.tables["template_divergences"].create(api.session.bind, checkfirst=True)

    # Insert sample divergence
    div = TemplateDivergence(
        id=1,
        mode="countrydle",
        question="Is it on te southern part of africa",
        template_plan=[{"operator": "contains", "left": {"entity": "target_country", "relation": "continent"}, "right": {"value": "Africa"}}],
        gemini_plan=[{"operator": "contains", "left": {"entity": "target_country", "relation": "geographic_area"}, "right": {"value": "Southern Africa"}}],
        divergence_type="value_mismatch",
        details={"template_value": "Africa", "gemini_value": "Southern Africa"},
    )
    api.session.add(div)
    api.session.commit()

    # 1. Non-admin is rejected
    res_unauth = await api.client.get("/admin/template-divergences")
    assert res_unauth.status_code == 401

    # 2. Admin can list open divergences
    async def mock_admin():
        return api.admin
    app.dependency_overrides[get_admin_user] = mock_admin
    try:
        res_open = await api.client.get("/admin/template-divergences?status=open")
        assert res_open.status_code == 200
        data = res_open.json()
        assert data["total"] == 1
        assert data["items"][0]["divergence_type"] == "value_mismatch"
        assert data["items"][0]["reviewed_at"] is None

        # 3. Admin can mark divergence reviewed
        res_patch = await api.client.patch("/admin/template-divergences/1", json={"reviewed": True})
        assert res_patch.status_code == 200
        assert res_patch.json()["reviewed_at"] is not None

        # 4. Now open list has 0, reviewed list has 1
        res_open_after = await api.client.get("/admin/template-divergences?status=open")
        assert res_open_after.json()["total"] == 0
        res_rev_after = await api.client.get("/admin/template-divergences?status=reviewed")
        assert res_rev_after.json()["total"] == 1
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


@pytest.mark.anyio
async def test_committed_report_blocks_disputed_fallback_answer_in_sql(reports_api):
    from db.repositories import fallback_answers as cache

    record = reports_api.questions["countrydle"]
    identity = cache.make_identity(
        mode="countrydle", entity_id=1, entity_name="Poland",
        original_question=record.original_question, question=record.question,
        context=record.context, system_prompt="Game rules.",
        question_prompt="Question data.", model="test-model",
        game_date=date(2026, 9, 20),
    )
    async_session = AsyncSessionAdapter(reports_api.session)
    await cache.store(async_session, identity, False, "The country did not host the event.")
    await async_session.commit()

    login(reports_api.owner)
    response = await reports_api.client.post("/answer-reports", json=payload())
    assert response.status_code == 201

    with Session(reports_api.session.get_bind(), expire_on_commit=False) as fresh_session:
        fresh_adapter = AsyncSessionAdapter(fresh_session)
        assert await cache.lookup(fresh_adapter, identity) is None
        await cache.store(fresh_adapter, identity, True, "A later generation.")
        await fresh_adapter.commit()
        assert await cache.lookup(fresh_adapter, identity) is None
