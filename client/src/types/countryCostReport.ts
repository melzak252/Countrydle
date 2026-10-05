export interface CountryCostUsage {
  input_tokens: number;
  cached_input_tokens: number;
  cached_input_unknown_tokens: number;
  output_tokens: number;
  thought_tokens: number;
  total_tokens: number;
  unknown_usage_calls: number;
  cost_lower_usd?: number;
  cost_upper_usd?: number;
  cost_incomplete?: boolean;
  cost_bounded?: boolean;
  new_planner_calls?: number;
  plan_cache_hits?: number;
  fallback_cache_hits?: number;
  fallback_model_calls?: number;
  retries?: number;
  failed_attempts?: number;
}

export interface CountryCostDay {
  day: string;
  completed_games: number;
  requests: number;
  answered: number;
  invalid: number;
  quota_failures: number;
  provider_failures: number;
  template_answers: number;
  fallback_cache_hits: number;
  fallback_model_calls: number;
  retries: number;
  failed_attempts: number;
  new_planner_calls: number;
  planner_cache_hits: number;
  new_planner_rate_per_1000_games: number | null;
  new_planner_share_of_requests: number | null;
  new_planner_share_of_planner_requests: number | null;
  stage_usage: Record<string, Record<string, CountryCostUsage>>;
  priced_models: Record<string, CountryCostUsage>;
  unpriced_models: string[];
  unpriced_model_usage: Record<string, CountryCostUsage>;
  cost_lower_usd: number | null;
  cost_upper_usd: number | null;
  cost_lower_per_1000_games_usd: number | null;
  cost_upper_per_1000_games_usd: number | null;
  cost_status: 'no_data' | 'not_measured' | 'incomplete_coverage' | 'incomplete' | 'bounded' | 'complete';
  measurement_coverage: 'none' | 'partial_startup_day' | 'after_measurement_start';
}

export interface CountryCostReport {
  days: CountryCostDay[];
  period_utc: { start: string; end: string };
  metrics_started_at_utc: string | null;
  coverage_note: string;
  denominator_note: string;
  scope_note: string;
  pricing_note: string;
}
