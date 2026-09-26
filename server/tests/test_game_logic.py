from datetime import date, timedelta

import pytest
from game_logic import (
    GameConfig,
    GameRules,
    GameState,
    calculate_points,
    count_consecutive_daily_wins,
    is_valid_synced_game_state,
    COUNTRYDLE_CONFIG,
    WOJEWODZTWDLE_CONFIG,
    POWIATDLE_CONFIG,
    USSTATEDLE_CONFIG,
)

def test_initial_state():
    config = GameConfig(max_questions=10, max_guesses=3)
    rules = GameRules(config)
    state = rules.initial_state()
    
    assert state.questions_used == 0
    assert state.guesses_used == 0
    assert state.is_won is False
    assert state.is_lost is False
    assert state.is_game_over is False

def test_ask_question():
    config = GameConfig(max_questions=2, max_guesses=3)
    rules = GameRules(config)
    state = rules.initial_state()
    
    # Ask 1st question
    assert rules.can_ask_question(state)
    state = rules.process_question(state)
    assert state.questions_used == 1
    
    # Ask 2nd question
    assert rules.can_ask_question(state)
    state = rules.process_question(state)
    assert state.questions_used == 2
    
    # Try 3rd question (should fail)
    assert not rules.can_ask_question(state)
    with pytest.raises(ValueError):
        rules.process_question(state)

def test_make_guess_correct():
    config = GameConfig(max_questions=10, max_guesses=3)
    rules = GameRules(config)
    state = rules.initial_state()
    
    assert rules.can_make_guess(state)
    state = rules.process_guess(state, is_correct=True)
    
    assert state.is_won is True
    assert state.is_lost is False
    assert state.is_game_over is True
    assert state.guesses_used == 1

def test_make_guess_incorrect():
    config = GameConfig(max_questions=10, max_guesses=2)
    rules = GameRules(config)
    state = rules.initial_state()
    
    # 1st wrong guess
    state = rules.process_guess(state, is_correct=False)
    assert state.is_won is False
    assert state.is_lost is False
    assert state.guesses_used == 1
    
    # 2nd wrong guess (Game Over)
    state = rules.process_guess(state, is_correct=False)
    assert state.is_won is False
    assert state.is_lost is True
    assert state.is_game_over is True
    assert state.guesses_used == 2
    
    # Try guessing after loss
    assert not rules.can_make_guess(state)
    with pytest.raises(ValueError):
        rules.process_guess(state, is_correct=True)

def test_mixed_gameplay():
    config = GameConfig(max_questions=5, max_guesses=3)
    rules = GameRules(config)
    state = rules.initial_state()
    
    state = rules.process_question(state)
    state = rules.process_guess(state, is_correct=False)
    state = rules.process_question(state)
    
    assert state.questions_used == 2
    assert state.guesses_used == 1
    assert not state.is_game_over


def test_calculate_points_loss():
    score = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=False,
        questions_used=5,
        guesses_used=3,
    )
    assert score == 0


def test_calculate_points_baseline_win():
    # Won on last guess, all questions burned, slow, no streak
    score = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=True,
        questions_used=10,
        guesses_used=3,
        elapsed_seconds=400,
        streak=0,
    )
    # Base (500) + Question (0) + Guess (167) + Speed (0) + Streak (0) = 667
    assert score == 667


def test_calculate_points_question_efficiency():
    # Fewer questions must strictly yield higher scores
    scores = [
        calculate_points(
            config=COUNTRYDLE_CONFIG,
            won=True,
            questions_used=q,
            guesses_used=1,
        )
        for q in range(11)
    ]
    # Check strictly monotonically decreasing
    for i in range(len(scores) - 1):
        assert scores[i] > scores[i + 1]

    # 0 questions used gives +1500 question efficiency
    assert scores[0] == 500 + 1500 + 500
    # 10 questions used gives 0 question efficiency
    assert scores[10] == 500 + 0 + 500


def test_calculate_points_guess_efficiency():
    score_g1 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1
    )
    score_g2 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=2
    )
    score_g3 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=3
    )

    assert score_g1 > score_g2 > score_g3


def test_calculate_points_speed_bonus():
    score_fast = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=True,
        questions_used=5,
        guesses_used=1,
        elapsed_seconds=30,
    )
    score_medium = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=True,
        questions_used=5,
        guesses_used=1,
        elapsed_seconds=120,
    )
    score_slow = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=True,
        questions_used=5,
        guesses_used=1,
        elapsed_seconds=350,
    )

    assert score_fast > score_medium > score_slow
    # At 30s: 300 - 30 = +270 bonus
    # At 120s: 300 - 120 = +180 bonus
    assert score_fast - score_medium == 90
    # At 350s: speed bonus caps at 0
    score_no_time = calculate_points(
        config=COUNTRYDLE_CONFIG,
        won=True,
        questions_used=5,
        guesses_used=1,
        elapsed_seconds=None,
    )
    assert score_slow == score_no_time


def test_calculate_points_streak_bonus():
    score_s0 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1, streak=0
    )
    score_s1 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1, streak=1
    )
    score_s5 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1, streak=5
    )
    score_s10 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1, streak=10
    )
    score_s20 = calculate_points(
        config=COUNTRYDLE_CONFIG, won=True, questions_used=5, guesses_used=1, streak=20
    )

    assert score_s1 - score_s0 == 50
    assert score_s5 - score_s0 == 250
    assert score_s10 - score_s0 == 500
    # Caps at 500 pts max
    assert score_s20 == score_s10


def test_game_rules_calculate_score():
    rules = GameRules(COUNTRYDLE_CONFIG)
    state = rules.initial_state()
    state = rules.process_question(state)
    state = rules.process_question(state)
    state = rules.process_guess(state, is_correct=True)

    score = rules.calculate_score(state, elapsed_seconds=45, streak=3)
    # Base (500) + Q (1500 * (0.8^1.5) = 1073) + Guess (500) + Speed (255) + Streak (150) = 2478
    assert score == 500 + 1073 + 500 + 255 + 150


def test_all_game_mode_configs():
    for cfg in [COUNTRYDLE_CONFIG, WOJEWODZTWDLE_CONFIG, POWIATDLE_CONFIG, USSTATEDLE_CONFIG]:
        score = calculate_points(
            config=cfg,
            won=True,
            questions_used=cfg.max_questions // 2,
            guesses_used=1,
            elapsed_seconds=60,
            streak=2,
        )
        assert score > 1000


def test_consecutive_daily_streak_stops_at_gap_and_excludes_scored_day():
    today = date(2026, 9, 26)
    completed_games = [
        (today, True),
        (today - timedelta(days=1), True),
        (today - timedelta(days=3), True),
    ]

    assert count_consecutive_daily_wins(completed_games, today) == 1


def test_synced_win_requires_actual_last_guess_and_consistent_budgets():
    config = GameConfig(max_questions=8, max_guesses=3)

    assert not is_valid_synced_game_state(
        config,
        guesses_made=0,
        remaining_guesses=3,
        is_game_over=True,
        won=True,
        correct_guesses=[],
        questions_asked=0,
        remaining_questions=8,
        synced_questions=0,
    )
    assert is_valid_synced_game_state(
        config,
        guesses_made=2,
        remaining_guesses=1,
        is_game_over=True,
        won=True,
        correct_guesses=[False, True],
        questions_asked=1,
        remaining_questions=7,
        synced_questions=1,
    )
