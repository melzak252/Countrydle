from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from db.models.friend_match import FriendMatch, FriendSeat, FriendMove, FriendAdvisory
from friend_matches.schemas import ActionRequest
from friend_matches.service import transition, project_move, project_guidance, expire_match, THINK_SECONDS, INFRASTRUCTURE_GRACE_SECONDS


NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
POLAND = {"id": "POL", "name": "Poland", "code": "PL"}
GERMANY = {"id": "DEU", "name": "Germany", "code": "DE"}


def active_game():
    game = FriendMatch(id=str(uuid4()), mode="countrydle", status="active", phase="thinking", version=1,
                       turn=1, move_ordinal=0, deadline=NOW + timedelta(seconds=THINK_SECONDS))
    seats = [FriendSeat(id=str(uuid4()), match_id=game.id, position=i, name=str(i), secret=POLAND,
                        ready=True, rematch_ready=False, question_count=0, guess_count=0, timeout_count=0,
                        last_seen_at=NOW) for i in range(2)]
    game.active_player_id = seats[0].id
    return game, seats


def action(kind, **payload):
    return ActionRequest(action_id=uuid4(), expected_version=1, type=kind, payload=payload)


@pytest.mark.parametrize("mode,name", [("countrydle", "Israel"), ("europe", "Azerbaijan")])
def test_disabled_existing_secret_interrupts_play_without_erasing_history(mode, name):
    game, seats = active_game()
    game.mode = mode
    seats[0].secret = {"id": "old-secret", "name": name, "code": None}
    assert expire_match(game, seats, NOW)
    assert game.result == "interrupted"
    assert game.winner_id is None
    assert seats[0].secret["name"] == name


def test_completed_duel_with_disabled_secret_keeps_its_result():
    game, seats = active_game()
    game.status = "finished"
    game.result = "solved"
    game.winner_id = seats[0].id
    seats[0].secret = {"id": "ISR", "name": "Israel", "code": "IL"}
    assert not expire_match(game, seats, NOW)
    assert game.result == "solved"
    assert game.winner_id == seats[0].id


def test_unlimited_wrong_guesses_spend_one_turn_each_and_cannot_double_move():
    game, seats = active_game()
    for _ in range(12):
        transition(game, seats, seats[0], action("guess", entity_id="DEU"), NOW, entity=GERMANY)
        assert game.active_player_id == seats[1].id
        with pytest.raises(HTTPException) as exc:
            transition(game, seats, seats[0], action("guess", entity_id="DEU"), NOW, entity=GERMANY)
        assert exc.value.status_code == 409
        transition(game, seats, seats[1], action("pass"), NOW)
    assert seats[0].guess_count == 12
    assert game.turn == 25
    assert game.status == "active"


def test_only_secret_owner_answers_and_answer_is_not_a_second_turn():
    game, seats = active_game()
    question = transition(game, seats, seats[0], action("ask", question="Is it in Europe?"), NOW)
    with pytest.raises(HTTPException) as exc:
        transition(game, seats, seats[0], action("answer", question_id=question.id, answer="yes"), NOW, move=question)
    assert exc.value.status_code == 403
    transition(game, seats, seats[1], action("answer", question_id=question.id, answer="mostly_yes"), NOW, move=question)
    assert game.active_player_id == seats[1].id
    assert game.turn == 2
    assert question.answer == "mostly_yes"
    assert seats[1].guess_count == 0


def test_opener_correct_and_reply_correct_is_draw_without_terminal_rewrite():
    game, seats = active_game()
    transition(game, seats, seats[0], action("guess", entity_id="POL"), NOW, entity=POLAND)
    assert game.phase == "reply" and game.pending_winner_id == seats[0].id
    transition(game, seats, seats[1], action("guess", entity_id="POL"), NOW, entity=POLAND)
    assert game.result == "draw" and game.winner_id is None
    with pytest.raises(HTTPException):
        transition(game, seats, seats[0], action("pass"), NOW)
    assert game.result == "draw"


def test_failed_reply_awards_pending_winner_and_second_seat_normal_win_is_final():
    game, seats = active_game()
    transition(game, seats, seats[0], action("guess", entity_id="POL"), NOW, entity=POLAND)
    transition(game, seats, seats[1], action("pass"), NOW)
    assert game.winner_id == seats[0].id and game.result == "solved"
    game, seats = active_game()
    transition(game, seats, seats[0], action("pass"), NOW)
    transition(game, seats, seats[1], action("guess", entity_id="POL"), NOW, entity=POLAND)
    assert game.winner_id == seats[1].id and game.status == "finished"


def test_draw_offer_never_pauses_clock_and_only_opponent_accepts():
    game, seats = active_game()
    deadline = game.deadline
    transition(game, seats, seats[0], action("offer_draw"), NOW)
    assert game.deadline == deadline
    with pytest.raises(HTTPException):
        transition(game, seats, seats[0], action("accept_draw"), NOW)
    transition(game, seats, seats[1], action("accept_draw"), NOW)
    assert game.result == "draw"
    with pytest.raises(HTTPException):
        transition(game, seats, seats[0], action("guess", entity_id="POL"), NOW, entity=POLAND)
    assert game.result == "draw"


def test_public_question_and_private_guidance_do_not_reveal_target():
    game, seats = active_game()
    question = transition(game, seats, seats[0], action("ask", question="Is it in Europe?"), NOW)
    public = project_move(question)
    assert public["entity"] is None
    assert "target" not in public and "explanation" not in public
    advisory = FriendAdvisory(question_id=question.id, owner_id=seats[1].id, status="completed",
                              answer="YES", explanation="Poland is in Europe", source="local_kb", late=False)
    assert project_guidance(advisory, seats[0].id) is None
    assert project_guidance(advisory, seats[1].id)["explanation"] == "Poland is in Europe"


def test_owner_correction_keeps_exposure_history_and_is_rejected_after_finish():
    game, seats = active_game()
    question = transition(game, seats, seats[0], action("ask", question="Is it in Europe?"), NOW)
    transition(game, seats, seats[1], action("answer", question_id=question.id, answer="no"), NOW, move=question)
    with pytest.raises(HTTPException):
        transition(game, seats, seats[0], action("correct_answer", question_id=question.id, answer="yes", expected_revision=1), NOW, move=question)
    advice = FriendAdvisory(status="completed", completed_at=NOW)
    transition(game, seats, seats[1], action("correct_answer", question_id=question.id, answer="yes",
               expected_revision=1, observed_ai_question_id=question.id), NOW, move=question, advisory=advice)
    assert [r["answer"] for r in question.revisions] == ["no", "yes"]
    assert [r["ai_seen_before_answer"] for r in question.revisions] == [False, True]
    with pytest.raises(HTTPException):
        transition(game, seats, seats[1], action("correct_answer", question_id=question.id, answer="unknown", expected_revision=1), NOW, move=question)
    transition(game, seats, seats[1], action("guess", entity_id="POL"), NOW, entity=POLAND)
    with pytest.raises(HTTPException):
        transition(game, seats, seats[1], action("correct_answer", question_id=question.id, answer="no", expected_revision=2), NOW, move=question)
    assert game.winner_id == seats[1].id and question.answer == "yes"


def test_first_timeout_passes_second_consecutive_timeout_forfeits_and_outage_interrupts():
    game, seats = active_game()
    timeout_moves = []
    assert expire_match(game, seats, NOW + timedelta(seconds=THINK_SECONDS + 1), timeout_moves=timeout_moves)
    assert game.status == "active" and game.active_player_id == seats[1].id
    assert timeout_moves[0].type == "pass" and timeout_moves[0].timed_out is True
    assert seats[0].timeout_count == 1
    transition(game, seats, seats[1], action("pass"), NOW + timedelta(seconds=THINK_SECONDS + 2))
    assert expire_match(game, seats, NOW + timedelta(seconds=THINK_SECONDS * 2 + 4))
    assert game.result == "forfeit" and game.winner_id == seats[1].id
    game, seats = active_game()
    assert expire_match(game, seats, NOW + timedelta(seconds=THINK_SECONDS + INFRASTRUCTURE_GRACE_SECONDS + 5))
    assert game.result == "interrupted" and game.winner_id is None


def test_owner_timeout_sends_ai_fallback_answer():
    game, seats = active_game()
    question = transition(game, seats, seats[0], action("ask", question="Is it in Europe?"), NOW)
    assert expire_match(game, seats, NOW + timedelta(seconds=61), pending_move=question)
    assert question.answer == "unknown" and question.revisions == [] and question.timed_out is True
    assert project_move(question)["answered_by"] == "ai"
    assert game.active_player_id == seats[1].id and seats[1].timeout_count == 1
    transition(game, seats, seats[1], action("pass"), NOW + timedelta(seconds=62))
    assert seats[1].timeout_count == 0


def test_reply_deadline_confirms_pending_winner_as_solved():
    game, seats = active_game()
    transition(game, seats, seats[0], action("guess", entity_id="POL"), NOW, entity=POLAND)
    assert expire_match(game, seats, NOW + timedelta(seconds=121))
    assert game.result == "solved" and game.winner_id == seats[0].id

def test_origin_checks_reject_hostile_private_reads_missing_mutation_origin_and_null_origin(monkeypatch):
    from types import SimpleNamespace
    from friend_matches.routes import require_origin
    monkeypatch.setenv("FRIEND_ALLOWED_ORIGINS", "http://localhost:5178")
    def request(origin):
        return SimpleNamespace(headers={"origin": origin, "host": "internal:8080"},
                               url=SimpleNamespace(scheme="http"))
    for origin in ("https://evil.example", "null", None):
        with pytest.raises(HTTPException) as exc:
            require_origin(request(origin))
        assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        require_origin(request("https://evil.example"), required=False)
    require_origin(request(None), required=False)
    require_origin(request("http://localhost:5178"))


def test_human_answer_schema_rejects_public_explanations_and_sixth_answer():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        action("answer", question_id=str(uuid4()), answer="yes", explanation="secret identifying note")
    with pytest.raises(ValidationError):
        action("answer", question_id=str(uuid4()), answer="INVALID")
