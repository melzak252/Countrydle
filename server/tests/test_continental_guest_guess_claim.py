from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy import select
from db.models import Country, User
from db.models.guest_participation import GuestParticipation
from db.models.continental import ContinentalDay, ContinentalGuess, ContinentalState, ContinentCode
from tests.test_question_accounting import accounting_db
from utils.guest_session import link_guest_participation


@pytest.mark.real_database
@pytest.mark.anyio
async def test_guest_guess_sync_claims_matching_signed_guest_row_once(accounting_db, monkeypatch):
    import continental

    identity = "00000000-0000-0000-0000-000000000071"
    async with accounting_db() as session:
        session.add_all([
            ContinentalDay(id=1, date=date.today(), country_id=1, continent=ContinentCode.EUROPE),
            ContinentalState(user_id=1, day_id=1, questions_asked=0, remaining_questions=8,
                             guesses_made=0, remaining_guesses=3, is_game_over=False, won=False),
            GuestParticipation(guest_id=identity, mode="continental:europe", day_id=1, guesses_made=1),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="Germany",
                             country_id=2, answer=False, elapsed_seconds=9),
            ContinentalGuess(user_id=None, guest_id=None, day_id=1, guess="Legacy", country_id=2,
                             answer=False, elapsed_seconds=12),
        ])
        session.add(Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"))
        await session.commit()

    async def get_day(self, *args, **kwargs):
        async with accounting_db() as session:
            return await session.get(ContinentalDay, 1)

    async def validate_guess(self, *args, **kwargs):
        return None

    monkeypatch.setattr(continental, "link_guest_participation", link_guest_participation)
    body = SimpleNamespace(
        date=str(date.today()), questions=[],
        guesses=[SimpleNamespace(guess="Germany", country_id=2, elapsed_seconds=9)],
        state=SimpleNamespace(questions_asked=0, remaining_questions=8, guesses_made=1,
                              remaining_guesses=2, is_game_over=False, won=False),
    )
    request = Request({"type": "http", "scheme": "https", "path": "/sync", "headers": []})
    request.state.guest_identity = identity
    async with accounting_db() as session:
        await continental.sync_guest_data(ContinentCode.EUROPE, body, request, await session.get(User, 1), session)
        rows = (await session.scalars(select(ContinentalGuess).where(ContinentalGuess.day_id == 1))).all()
        assert len(rows) == 2
        linked = next(row for row in rows if row.guess == "Germany")
        historical = next(row for row in rows if row.guess == "Legacy")
        assert (linked.user_id, linked.guest_id) == (1, identity)
        assert (historical.user_id, historical.guest_id) == (None, None)


@pytest.mark.real_database
@pytest.mark.anyio
async def test_existing_account_progress_does_not_claim_guest_guess(accounting_db, monkeypatch):
    import continental

    identity = "00000000-0000-0000-0000-000000000072"
    async with accounting_db() as session:
        session.add(Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"))
        await session.flush()
        session.add_all([
            ContinentalDay(id=1, date=date.today(), country_id=1, continent=ContinentCode.EUROPE),
            ContinentalState(user_id=1, day_id=1, questions_asked=0, remaining_questions=8,
                             guesses_made=1, remaining_guesses=2, is_game_over=False, won=False),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="Germany",
                             country_id=2, answer=False, elapsed_seconds=9),
        ])
        await session.commit()

    async def get_day(self, *args, **kwargs):
        async with accounting_db() as session:
            return await session.get(ContinentalDay, 1)

    monkeypatch.setattr(continental.ContinentalDayRepository, "get_day_by_date", get_day)
    request = Request({"type": "http", "scheme": "https", "path": "/sync", "headers": []})
    request.state.guest_identity = identity
    body = SimpleNamespace(date=str(date.today()), questions=[], guesses=[], state=None)
    async with accounting_db() as session:
        await continental.sync_guest_data(ContinentCode.EUROPE, body, request, await session.get(User, 1), session)
        row = await session.scalar(select(ContinentalGuess).where(ContinentalGuess.day_id == 1))
        assert row.user_id is None
        assert row.guest_id == identity
@pytest.mark.real_database
@pytest.mark.anyio
async def test_guess_sync_cannot_claim_browser_already_linked_to_another_account(accounting_db, monkeypatch):
    import continental

    identity = "00000000-0000-0000-0000-000000000073"
    async with accounting_db() as session:
        session.add_all([
            User(id=2, username="other", email="other@example.com", hashed_password="unused"),
            Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"),
        ])
        await session.flush()
        session.add_all([
            ContinentalDay(id=1, date=date.today(), country_id=1, continent=ContinentCode.EUROPE),
            ContinentalState(user_id=1, day_id=1, questions_asked=0, remaining_questions=8,
                             guesses_made=0, remaining_guesses=3, is_game_over=False, won=False),
            GuestParticipation(guest_id=identity, mode="continental:europe", day_id=1, user_id=2,
                               guesses_made=1),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="Germany",
                             country_id=2, answer=False, elapsed_seconds=9),
        ])
        await session.commit()

    async def get_day(self, *args, **kwargs):
        async with accounting_db() as session:
            return await session.get(ContinentalDay, 1)

    async def validate_guess(self, *args, **kwargs):
        return None

    monkeypatch.setattr(continental.ContinentalDayRepository, "get_day_by_date", get_day)
    monkeypatch.setattr(continental.CountryRepository, "validate_guess", validate_guess)
    request = Request({"type": "http", "scheme": "https", "path": "/sync", "headers": []})
    request.state.guest_identity = identity
    body = SimpleNamespace(
        date=str(date.today()), questions=[],
        guesses=[SimpleNamespace(guess="Germany", country_id=2, elapsed_seconds=9)],
        state=SimpleNamespace(questions_asked=0, remaining_questions=8, guesses_made=1,
                              remaining_guesses=2, is_game_over=False, won=False),
    )
    async with accounting_db() as session:
        await continental.sync_guest_data(ContinentCode.EUROPE, body, request, await session.get(User, 1), session)
    async with accounting_db() as session:
        rows = (await session.scalars(select(ContinentalGuess).where(ContinentalGuess.day_id == 1))).all()
        owner = await session.scalar(select(GuestParticipation.user_id).where(
            GuestParticipation.guest_id == identity,
            GuestParticipation.mode == "continental:europe",
            GuestParticipation.day_id == 1,
        ))
        guest_row = next(row for row in rows if row.guest_id == identity)
        assert guest_row.user_id is None
        assert [(row.guess, row.user_id) for row in rows if row.user_id == 1] == [("Germany", 1)]
        assert owner == 2
@pytest.mark.real_database
@pytest.mark.anyio
async def test_partial_guest_guess_sync_does_not_link_unsubmitted_guest_history(accounting_db, monkeypatch):
    import continental

    identity = "00000000-0000-0000-0000-000000000074"
    async with accounting_db() as session:
        session.add_all([
            ContinentalDay(id=1, date=date.today(), country_id=1, continent=ContinentCode.EUROPE),
            ContinentalState(user_id=1, day_id=1, questions_asked=0, remaining_questions=8,
                             guesses_made=0, remaining_guesses=3, is_game_over=False, won=False),
            GuestParticipation(guest_id=identity, mode="continental:europe", day_id=1, guesses_made=2),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="Germany",
                             country_id=2, answer=False, elapsed_seconds=9),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="France",
                             country_id=2, answer=False, elapsed_seconds=12),
            Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"),
        ])
        await session.commit()

    async def get_day(self, *args, **kwargs):
        async with accounting_db() as session:
            return await session.get(ContinentalDay, 1)

    async def validate_guess(self, *args, **kwargs):
        return None

    monkeypatch.setattr(continental.ContinentalDayRepository, "get_day_by_date", get_day)
    monkeypatch.setattr(continental.CountryRepository, "validate_guess", validate_guess)
    request = Request({"type": "http", "scheme": "https", "path": "/sync", "headers": []})
    request.state.guest_identity = identity
    body = SimpleNamespace(
        date=str(date.today()), questions=[],
        guesses=[SimpleNamespace(guess="Germany", country_id=2, elapsed_seconds=9)],
        state=SimpleNamespace(questions_asked=0, remaining_questions=8, guesses_made=1,
                              remaining_guesses=2, is_game_over=False, won=False),
    )
    async with accounting_db() as session:
        await continental.sync_guest_data(ContinentCode.EUROPE, body, request, await session.get(User, 1), session)
    async with accounting_db() as session:
        rows = (await session.scalars(select(ContinentalGuess).where(
            ContinentalGuess.day_id == 1
        ).order_by(ContinentalGuess.id))).all()
        owner = await session.scalar(select(GuestParticipation.user_id).where(
            GuestParticipation.guest_id == identity,
            GuestParticipation.mode == "continental:europe",
            GuestParticipation.day_id == 1,
        ))
        assert [(row.guess, row.user_id) for row in rows if row.guest_id == identity] == [("Germany", None), ("France", None)]
        assert [(row.guess, row.user_id) for row in rows if row.user_id == 1] == [("Germany", 1)]
        assert owner is None


@pytest.mark.real_database
@pytest.mark.anyio
async def test_sync_with_omitted_guest_question_does_not_link_history(accounting_db, monkeypatch):
    import continental
    from db.models.continental import ContinentalQuestion

    identity = "00000000-0000-0000-0000-000000000075"
    async with accounting_db() as session:
        session.add(Country(id=2, name="Germany", official_name="Germany", md_file="germany.md"))
        await session.flush()
        session.add_all([
            ContinentalDay(id=1, date=date.today(), country_id=1, continent=ContinentCode.EUROPE),
            ContinentalState(user_id=1, day_id=1, questions_asked=0, remaining_questions=8,
                             guesses_made=0, remaining_guesses=3, is_game_over=False, won=False),
            GuestParticipation(guest_id=identity, mode="continental:europe", day_id=1,
                               questions_asked=1, guesses_made=1),
            ContinentalQuestion(user_id=None, guest_id=identity, day_id=1,
                                original_question="Is it in Europe?", valid=True, answer=True),
            ContinentalGuess(user_id=None, guest_id=identity, day_id=1, guess="Germany",
                             country_id=2, answer=False, elapsed_seconds=9),
        ])
        await session.commit()

    async def validate_guess(self, *args, **kwargs):
        return None

    monkeypatch.setattr(continental.CountryRepository, "validate_guess", validate_guess)
    request = Request({"type": "http", "scheme": "https", "path": "/sync", "headers": []})
    request.state.guest_identity = identity
    body = SimpleNamespace(
        date=str(date.today()), questions=[],
        guesses=[SimpleNamespace(guess="Germany", country_id=2, elapsed_seconds=9)],
        state=SimpleNamespace(questions_asked=0, remaining_questions=8, guesses_made=1,
                              remaining_guesses=2, is_game_over=False, won=False),
    )
    async with accounting_db() as session:
        await continental.sync_guest_data(ContinentCode.EUROPE, body, request, await session.get(User, 1), session)
    async with accounting_db() as session:
        participation = (await session.scalars(select(GuestParticipation))).one()
        question = (await session.scalars(select(ContinentalQuestion))).one()
        guesses = (await session.scalars(select(ContinentalGuess).order_by(ContinentalGuess.id))).all()
        assert participation.user_id is None
        assert question.user_id is None
        assert [(guess.user_id, guess.guess) for guess in guesses] == [(None, "Germany"), (1, "Germany")]
