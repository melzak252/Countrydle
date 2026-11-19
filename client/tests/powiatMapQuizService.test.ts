import { expect, test } from 'bun:test';

type MapQuizState = {
  date: string;
  round_count: number;
  expected_round: number;
  current_target: string | null;
  score: number;
  is_complete: boolean;
  answers: unknown[];
  last_answer: unknown | null;
};

type MapQuizService = {
  getDaily: () => Promise<MapQuizState>;
  submitAnswer: (payload: { guess_id: number; expected_round: number }) => Promise<MapQuizState>;
  claimDaily: () => Promise<MapQuizState>;
  getHistory: () => Promise<{ items: unknown[]; total: number }>;
  getDailyStats: () => Promise<{
    date: string;
    completed_count: number;
    average_score: number | null;
    score_distribution: Record<string, number> | null;
  }>;
};
type PowiatService = { getPowiaty: () => Promise<Array<{ id: number; nazwa: string }>> };

const calls: Array<{ method: string; path: string; body?: unknown }> = [];
const responses = new Map<string, unknown>([
  ['/powiatdle/map-quiz/daily', {
    date: '2026-06-01', round_count: 10, expected_round: 2, current_target: 'Powiat aleksandrowski',
    score: 1, is_complete: false, answers: [], last_answer: null,
  }],
  ['/powiatdle/map-quiz/daily/answer', {
    date: '2026-06-01', round_count: 10, expected_round: 3, current_target: 'Powiat łosicki',
    score: 2, is_complete: false, answers: [], last_answer: { round: 2, guess_id: 701, correct: false },
  }],
  ['/powiatdle/powiaty', [{ id: 702, nazwa: 'Powiat aleksandrowski' }]],
  ['/powiatdle/map-quiz/history', { items: [], total: 0 }],
  ['/powiatdle/map-quiz/daily/stats', {
    date: '2026-06-01', completed_count: 5, average_score: 6.2, score_distribution: { '6': 2 },
  }],
  ['/powiatdle/map-quiz/daily/claim', {
    date: '2026-06-01', round_count: 10, expected_round: 2, current_target: 'Powiat aleksandrowski',
    score: 1, is_complete: false, answers: [], last_answer: null,
  }],
]);
const apiClient = {
  interceptors: {
    request: { use: () => undefined },
    response: { use: () => undefined },
  },
  get: async (path: string) => {
    calls.push({ method: 'GET', path });
    return { data: responses.get(path) };
  },
  post: async (path: string, body?: unknown) => {
    calls.push({ method: 'POST', path, body });
    return { data: responses.get(path) };
  },
};

const bunMock = await import('bun:test');
bunMock.mock.module('axios', () => ({ default: { create: () => apiClient } }));

test('map quiz service exposes daily state, own history, aggregate stats, and guest claim routes', async () => {
  calls.length = 0;
  const module = await import('../src/services/api') as unknown as {
    powiatMapQuizService: MapQuizService;
    powiatService: PowiatService;
  };
  expect(module.powiatMapQuizService).toBeDefined();
  const service = module.powiatMapQuizService;

  expect((await service.getDaily()).expected_round).toBe(2);
  expect((await service.submitAnswer({ guess_id: 701, expected_round: 2 })).expected_round).toBe(3);
  expect((await service.getHistory()).total).toBe(0);
  expect((await service.getDailyStats()).average_score).toBe(6.2);
  expect((await module.powiatService.getPowiaty())[0]).toEqual({ id: 702, nazwa: 'Powiat aleksandrowski' });
  expect((await service.claimDaily()).current_target).toBe('Powiat aleksandrowski');
  expect(calls).toEqual([
    { method: 'GET', path: '/powiatdle/map-quiz/daily' },
    { method: 'POST', path: '/powiatdle/map-quiz/daily/answer', body: { guess_id: 701, expected_round: 2 } },
    { method: 'GET', path: '/powiatdle/map-quiz/history' },
    { method: 'GET', path: '/powiatdle/map-quiz/daily/stats' },
    { method: 'GET', path: '/powiatdle/powiaty' },
    { method: 'POST', path: '/powiatdle/map-quiz/daily/claim', body: {} },
  ]);
});
