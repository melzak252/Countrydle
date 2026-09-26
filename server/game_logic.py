from dataclasses import dataclass
from datetime import date, timedelta


def count_consecutive_daily_wins(
    completed_games: list[tuple[date, bool]], puzzle_date: date
) -> int:
    """Count consecutive wins on days preceding the puzzle being scored."""
    expected_date = puzzle_date - timedelta(days=1)
    streak = 0
    for played_date, won in completed_games:
        if played_date >= puzzle_date:
            continue
        if played_date != expected_date or not won:
            break
        streak += 1
        expected_date -= timedelta(days=1)
    return streak


def is_valid_synced_game_state(
    config: "GameConfig",
    *,
    guesses_made: int,
    remaining_guesses: int,
    is_game_over: bool,
    won: bool,
    correct_guesses: list[bool],
    questions_asked: int | None = None,
    remaining_questions: int | None = None,
    synced_questions: int | None = None,
) -> bool:
    guess_count = len(correct_guesses)
    won_from_guesses = bool(guess_count and correct_guesses[-1]) and not any(
        correct_guesses[:-1]
    )
    expected_game_over = won_from_guesses or guess_count == config.max_guesses
    if (
        guesses_made != guess_count
        or not 0 <= guess_count <= config.max_guesses
        or remaining_guesses != config.max_guesses - guess_count
        or any(correct_guesses[:-1])
        or won != won_from_guesses
        or is_game_over != expected_game_over
    ):
        return False

    if synced_questions is not None:
        if (
            questions_asked != synced_questions
            or not 0 <= synced_questions <= config.max_questions
            or remaining_questions != config.max_questions - synced_questions
        ):
            return False
    return True



@dataclass(frozen=True)
class GameConfig:
    max_questions: int
    max_guesses: int

COUNTRYDLE_CONFIG = GameConfig(max_questions=10, max_guesses=3)
WOJEWODZTWDLE_CONFIG = GameConfig(max_questions=5, max_guesses=2)
POWIATDLE_CONFIG = GameConfig(max_questions=15, max_guesses=3)
USSTATEDLE_CONFIG = GameConfig(max_questions=8, max_guesses=3)
CONTINENTAL_CONFIG = GameConfig(max_questions=8, max_guesses=3)
FLAGDLE_CONFIG = GameConfig(max_questions=0, max_guesses=12)

def calculate_flagdle_points(
    won: bool,
    guesses_used: int,
    elapsed_seconds: int | None = None,
    streak: int = 0,
) -> int:
    if not won:
        return 0

    base_points = 500
    guess_bonus_map = {1: 1500, 2: 1300, 3: 1100, 4: 950, 5: 800, 6: 650, 7: 500, 8: 400, 9: 300, 10: 200, 11: 100, 12: 50}
    guess_bonus = guess_bonus_map.get(guesses_used, 25)

    speed_bonus = 0
    if elapsed_seconds is not None and elapsed_seconds > 0:
        decay_factor = max(0.0, (180 - elapsed_seconds) / 180)
        speed_bonus = int(300 * (decay_factor ** 1.5))

    streak_bonus = min(500, max(0, streak) * 50)
    return base_points + guess_bonus + speed_bonus + streak_bonus

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
