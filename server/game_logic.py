from dataclasses import dataclass

@dataclass(frozen=True)
class GameConfig:
    max_questions: int
    max_guesses: int

COUNTRYDLE_CONFIG = GameConfig(max_questions=10, max_guesses=3)
WOJEWODZTWDLE_CONFIG = GameConfig(max_questions=5, max_guesses=2)
POWIATDLE_CONFIG = GameConfig(max_questions=15, max_guesses=3)
USSTATEDLE_CONFIG = GameConfig(max_questions=8, max_guesses=3)

@dataclass(frozen=True)
class GameState:
    questions_used: int
    guesses_used: int
    is_won: bool
    is_lost: bool
    
    @property
    def is_game_over(self) -> bool:
        return self.is_won or self.is_lost


def calculate_points(
    config: GameConfig,
    won: bool,
    questions_used: int,
    guesses_used: int,
    elapsed_seconds: int | None = None,
    streak: int = 0,
) -> int:
    """
    Calculate dynamic game points based on:
    1. Base Win Floor (+500 pts)
    2. Question Efficiency (Exponential curve: 0 to 1,500 pts rewarding bold deductions)
    3. Guess Efficiency (Up to +500 pts for 1st guess)
    4. Speed Bonus (0 to +300 pts, decays over 5 minutes)
    5. Daily Streak Bonus (+50 pts per consecutive day, up to +500 pts)
    """
    if not won:
        return 0

    try:
        q_used = int(questions_used)
    except (TypeError, ValueError):
        q_used = 0

    try:
        g_used = int(guesses_used)
    except (TypeError, ValueError):
        g_used = 1

    try:
        cur_streak = int(streak)
    except (TypeError, ValueError):
        cur_streak = 0

    # 1. Base Win Floor
    base_points = 500

    # 2. Question Efficiency (Exponential curve: rewards fewer questions used)
    remaining_ratio = max(0.0, (config.max_questions - q_used) / config.max_questions)
    question_bonus = round(1500 * (remaining_ratio ** 1.5))

    # 3. Guess Efficiency (500 pts on 1st guess, scaled down per guess)
    guess_ratio = max(0.0, (config.max_guesses - g_used + 1) / config.max_guesses)
    guess_bonus = round(500 * guess_ratio)

    # 4. Speed Bonus (0 to 300 pts, decays over 5 minutes)
    speed_bonus = 0
    if elapsed_seconds is not None:
        try:
            el = int(elapsed_seconds)
            if el >= 0:
                speed_bonus = max(0, min(300, 300 - int(el * 1.0)))
        except (TypeError, ValueError):
            pass

    # 5. Daily Streak Bonus (50 pts per day up to 500 cap)
    streak_bonus = min(500, max(0, cur_streak * 50))

    return base_points + question_bonus + guess_bonus + speed_bonus + streak_bonus
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

    def calculate_score(
        self,
        state: GameState,
        elapsed_seconds: int | None = None,
        streak: int = 0,
    ) -> int:
        return calculate_points(
            config=self.config,
            won=state.is_won,
            questions_used=state.questions_used,
            guesses_used=state.guesses_used,
            elapsed_seconds=elapsed_seconds,
            streak=streak,
        )
