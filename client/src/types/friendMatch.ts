export type FriendMode = 'countrydle' | 'europe' | 'asia' | 'africa' | 'americas' | 'us_statedle' | 'wojewodztwodle' | 'powiatdle';
export type HumanAnswer = 'yes' | 'mostly_yes' | 'mostly_no' | 'no' | 'unknown';
export interface FriendEntity { id: string; name: string; code?: string | null }
export interface FriendPlayer {
  id: string; name: string; ready: boolean; connected: boolean;
  guess_count: number; question_count: number; rematch_ready: boolean;
  timeout_count?: number;
}
export interface FriendHistory {
  id: string; ordinal: number; type: 'question' | 'guess' | 'pass';
  player_id: string; subject_id: string; question: string | null;
  entity: FriendEntity | null; answer: HumanAnswer | null; correct: boolean | null;
  revision: number; created_at: string;
  timed_out?: boolean;
  revisions: { answer: HumanAnswer; revision: number; created_at: string }[];
}
export interface FriendGuidance {
  question_id: string; status: 'pending' | 'running' | 'completed' | 'failed';
  answer: 'YES' | 'NO' | 'INVALID' | null; explanation: string | null;
  source: string | null; completed_at: string | null; late: boolean;
}
export interface FriendSnapshot {
  id: string; invite_code: string; mode: FriendMode; version: number;
  status: 'lobby' | 'active' | 'finished';
  phase: 'lobby' | 'thinking' | 'answering' | 'reply' | 'finished';
  you: string; players: FriendPlayer[]; own_secret: FriendEntity | null;
  active_player_id: string | null; pending_question_id: string | null;
  pending_winner_id: string | null; winner_id: string | null;
  result: 'solved' | 'draw' | 'forfeit' | 'interrupted' | 'cancelled' | null;
  draw_offer_by: string | null; turn: number; deadline: string | null;
  history: FriendHistory[]; history_has_more: boolean; guidance: FriendGuidance[];
  reveals: { player_id: string; entity: FriendEntity }[] | null;
  rematch_id: string | null; rematch_code: string | null;
  session_score?: { player_id: string; wins: number }[]; draw_count?: number;
}
export interface FriendInvite {
  id: string; invite_code: string; mode: FriendMode;
  status: FriendSnapshot['status']; players: { name: string }[]; full: boolean;
}
export interface FriendHistoryPage {
  history: FriendHistory[]; history_has_more: boolean; next_before: number | null;
  guidance?: FriendGuidance[];
}
export interface FriendActionPayloads {
  select_secret: { entity_id: string }; randomize_secret: Record<string, never>;
  ready: { ready: boolean }; ask: { question: string };
  answer: { question_id: string; answer: HumanAnswer; observed_ai_question_id?: string };
  guess: { entity_id: string }; pass: Record<string, never>;
  correct_answer: { question_id: string; answer: HumanAnswer; expected_revision: number; observed_ai_question_id?: string };
  offer_draw: Record<string, never>; accept_draw: Record<string, never>;
  decline_draw: Record<string, never>; leave: Record<string, never>; rematch: Record<string, never>;
}
export type FriendActionType = keyof FriendActionPayloads;
export type FriendAction = {
  [K in FriendActionType]: { action_id: string; expected_version: number; type: K; payload: FriendActionPayloads[K] }
}[FriendActionType];
