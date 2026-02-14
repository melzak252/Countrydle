from dataclasses import dataclass

@dataclass(frozen=True)
class GameConfig:
    max_questions: int
    max_guesses: int

@dataclass(frozen=True)
class GameState:
    questions_used: int
    guesses_used: int
    is_won: bool
    is_lost: bool
    
    @property
    def is_game_over(self) -> bool:
        return self.is_won or self.is_lost

class GameRules:
    def __init__(self, config: GameConfig):
        self.config = config

    def initial_state(self) -> GameState:
        return GameState(questions_used=0, guesses_used=0, is_won=False, is_lost=False)

    def can_ask_question(self, state: GameState) -> bool:
        return not state.is_game_over and state.questions_used < self.config.max_questions

    def can_make_guess(self, state: GameState) -> bool:
        return not state.is_game_over and state.guesses_used < self.config.max_guesses

    def process_question(self, state: GameState) -> GameState:
        if not self.can_ask_question(state):
            raise ValueError("Cannot ask question: Limit reached or game over")
        
        return GameState(
            questions_used=state.questions_used + 1,
            guesses_used=state.guesses_used,
            is_won=state.is_won,
            is_lost=state.is_lost
        )

    def process_guess(self, state: GameState, is_correct: bool) -> GameState:
        if not self.can_make_guess(state):
            raise ValueError("Cannot make guess: Limit reached or game over")

        new_guesses_used = state.guesses_used + 1
        is_won = is_correct
        # Lost if not won AND no guesses left
        is_lost = not is_won and (new_guesses_used >= self.config.max_guesses)

        return GameState(
            questions_used=state.questions_used,
            guesses_used=new_guesses_used,
            is_won=is_won,
            is_lost=is_lost
        )
