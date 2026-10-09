import type { CountryDisplay } from './index';

export interface BlogPostSummary {
    id: number;
    date: string;
    slug: string;
    title: string;
    subtitle: string;
    reading_time_minutes: number;
    summary: string;
    country_name: string;
    country_code?: string | null;
    continent?: string | null;
    difficulty?: string | null;
    win_rate_pct?: number | null;
    total_players?: number | null;
    created_at: string;
}

export interface BlogFastFacts {
    capital?: string | null;
    continent?: string | null;
    region?: string | null;
    population?: string | number | null;
    area?: string | number | null;
    coastline?: string | null;
    borders?: string | null;
    languages?: string | null;
}

export interface BlogFunFact {
    title: string;
    description?: string | null;
}

export interface BlogDeductionStep {
    step?: number;
    question: string;
    answer: string;
    explanation?: string | null;
    count?: number;
    pct?: number | null;
}

export interface BlogQuiz {
    question?: string | null;
    correct_answer?: string | null;
    incorrect_distractor?: string | null;
    explanation?: string | null;
}

export interface BlogDeductionMasterclass {
    steps?: BlogDeductionStep[] | null;
    pro_tip?: string | null;
    quiz?: BlogQuiz | null;
}

export interface BlogTopQuestionStat extends BlogDeductionStep {
    count: number;
}

export interface BlogWrongGuessStat {
    guess: string;
    count: number;
}

export interface BlogCommunityGameDebrief {
    has_telemetry: boolean;
    total_challengers: number;
    total_solvers: number;
    win_rate_pct: number;
    avg_questions_to_win: number;
    avg_guesses: number;
    high_score?: number | null;
    top_questions: BlogTopQuestionStat[];
    common_pitfalls: BlogWrongGuessStat[];
    decisive_clue?: string | null;
}

export interface BlogPlayerStats {
    total_players: number;
    winners_count?: number;
    win_rate_pct?: number;
    total_questions?: number;
    total_guesses?: number;
    avg_questions_won?: number;
    avg_guesses_won?: number;
}

export interface BlogPostDisplay extends BlogPostSummary {
    country_id: number;
    fast_facts?: BlogFastFacts | null;
    fun_facts: BlogFunFact[];
    deduction_masterclass?: BlogDeductionMasterclass | null;
    content_markdown: string;
    country?: CountryDisplay | null;
    player_stats?: BlogPlayerStats | null;
    game_debrief?: BlogCommunityGameDebrief | null;
    related_posts?: BlogPostSummary[] | null;
}

export interface BlogPostListResponse {
    total: number;
    posts: BlogPostSummary[];
}
