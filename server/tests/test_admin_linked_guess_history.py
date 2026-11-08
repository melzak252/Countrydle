from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.base import Base
from db.models.continental import ContinentalDay, ContinentalGuess, ContinentalQuestion, ContinentalState
from db.models.country import Country
from db.models.guest_participation import GuestParticipation
from db.models.user import User


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


@pytest.fixture
def linked_history_db():
    from admin.resolver import ADMIN_MODE_CONFIGS

    engine = create_engine("sqlite://")
    event_models = [model for cfg in ADMIN_MODE_CONFIGS.values() for model in (cfg.question_model, cfg.guess_model)]
    tables = list(dict.fromkeys(model.__table__ for model in (
        User, Country, ContinentalDay, ContinentalState, GuestParticipation, *event_models,
    )))
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        session.add_all([
            User(id=11, username="one", email="one@example.com"), User(id=22, username="two", email="two@example.com"),
            Country(id=1, name="Poland", official_name="Republic of Poland", md_file="poland.md"),
            ContinentalDay(id=10, country_id=1, continent="europe", date=date(2026, 9, 23)),
        ])
        session.flush()
        yield session, AsyncSessionAdapter(session)
    engine.dispose()


@pytest.mark.anyio
async def test_linked_guest_events_belong_to_account_without_duplicate_guest(linked_history_db):
    from admin.resolver import query_admin_game_sessions

    db, session = linked_history_db
    db.add_all([
        ContinentalState(user_id=11, day_id=10, guesses_made=1, is_game_over=False, won=False),
        GuestParticipation(guest_id="linked-one", mode="continental:europe", day_id=10, user_id=11),
        GuestParticipation(guest_id="linked-two", mode="continental:europe", day_id=10, user_id=22),
        ContinentalQuestion(user_id=None, guest_id="linked-one", day_id=10, original_question="one q", question="one q", valid=True, answer=True),
        ContinentalGuess(user_id=None, guest_id="linked-one", day_id=10, guess="one guess", country_id=1, answer=False),
        ContinentalGuess(user_id=None, guest_id="linked-two", day_id=10, guess="two guess", country_id=1, answer=False),
        ContinentalGuess(user_id=None, guest_id=None, day_id=10, guess="historical anonymous", country_id=1, answer=False),
        # An event explicitly assigned to another account is never reassigned through a guest link.
        ContinentalGuess(user_id=22, guest_id="linked-one", day_id=10, guess="account two", country_id=1, answer=False),
    ])
    db.flush()

    sessions, total = await query_admin_game_sessions(session, mode="continental:europe", target_date=date(2026, 9, 23))

    assert total == 3
    by_user = {item.user_id: item for item in sessions if item.user_id is not None}
    assert set(by_user) == {11, 22}
    assert [event.guess for event in by_user[11].timeline if event.event_type == "guess"] == ["one guess"]
    assert [event.guess for event in by_user[22].timeline if event.event_type == "guess"] == ["two guess", "account two"]
    assert [event.question for event in by_user[11].timeline if event.event_type == "question"] == ["one q"]
    anonymous = next(item for item in sessions if item.is_guest)
    assert [event.guess for event in anonymous.timeline] == ["historical anonymous"]
