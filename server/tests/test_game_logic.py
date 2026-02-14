import pytest
from game_logic import GameConfig, GameRules, GameState

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
