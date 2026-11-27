import { expect, test } from 'bun:test';
import type { FeatureCollection } from 'geojson';
import { usePowiatyGameStore } from '../src/stores/gameStore';
import {
  answerMapChallenge,
  createIsolatedMapInteraction,
  createMapChallengeState,
  getMapChallengePool,
} from '../src/lib/mapChallenge';
import { parseMapGameMode } from '../src/lib/mapGameMode';
import {
  getRevealedOptimalPath,
  mapBorderHopMarkings,
  matchTypedNeighbor,
  resetMapBorderHop,
  undoMapBorderHop,
} from '../src/lib/mapBorderHop';

test('route mode parsing defaults safely and recognizes US states', () => {
  expect(parseMapGameMode('us_states')).toBe('us_states');
  expect(parseMapGameMode('powiaty')).toBe('powiaty');
  expect(parseMapGameMode(null)).toBe('powiaty');
  expect(parseMapGameMode('unknown')).toBe('powiaty');
});

test('US map challenge target pool excludes DC and Puerto Rico', () => {
  const map = {
    type: 'FeatureCollection',
    features: ['Alabama', 'District of Columbia', 'Puerto Rico', 'Hawaii'].map((name) => ({
      type: 'Feature',
      properties: { name },
      geometry: { type: 'Point', coordinates: [0, 0] },
    })),
  } as FeatureCollection;

  expect(getMapChallengePool(map, 'us_states')).toEqual(['Alabama', 'Hawaii']);
});

test('map challenge chooses ten unique prompts and scores a correct click once', () => {
  const prompts = Array.from({ length: 12 }, (_, index) => `Region ${index}`);
  const game = createMapChallengeState(prompts, () => 0);
  const target = game.prompts[game.currentPromptIndex];

  expect(game.prompts).toHaveLength(10);
  expect(new Set(game.prompts).size).toBe(10);
  const answered = answerMapChallenge(game, target);
  expect(answered.score).toBe(1);
  expect(answered.status).toBe('correct');
  expect(answered.markings[target.toUpperCase()]).toBe('green');
  expect(answerMapChallenge(answered, target)).toBe(answered);
});

test('a wrong map click scores zero and marks the correct region red', () => {
  const game = createMapChallengeState(['Target', 'Wrong'], () => 0);
  const target = game.prompts[game.currentPromptIndex];
  const wrong = game.prompts.find((name) => name !== target)!;
  const answered = answerMapChallenge(game, wrong);

  expect(answered.score).toBe(0);
  expect(answered.status).toBe('incorrect');
  expect(answered.markings[target.toUpperCase()]).toBe('red');
});

test('quiz map interaction is isolated from daily game-store handlers', () => {
  const dailyStore = usePowiatyGameStore.getState();
  const markingsBefore = { ...dailyStore.entityMarkings };
  const interaction = createIsolatedMapInteraction({});

  interaction.handleEntityMapClick('ALABAMA');
  interaction.clearMapMarkings();
  interaction.setActiveMarkerColor('red');

  expect(usePowiatyGameStore.getState().entityMarkings).toEqual(markingsBefore);
});

test('typed Border Hop accepts only an unvisited listed neighbor', () => {
  expect(matchTypedNeighbor('  texas ', ['Texas', 'Oklahoma'], ['Alabama'])).toBe('Texas');
  expect(matchTypedNeighbor('Florida', ['Texas', 'Oklahoma'], ['Alabama'])).toBeNull();
  expect(matchTypedNeighbor('Texas', ['Texas', 'Oklahoma'], ['Texas'])).toBeNull();
  expect(matchTypedNeighbor('krakowski', ['Powiat krakowski', 'Kraków'], [])).toBe('Powiat krakowski');
  expect(matchTypedNeighbor('bielski', ['Powiat bielski (śląskie)', 'Powiat żywiecki'], [])).toBe('Powiat bielski (śląskie)');
  expect(matchTypedNeighbor('lodzki wschodni', ['Powiat łódzki wschodni'], [])).toBe('Powiat łódzki wschodni');
});

test('Border Hop marks start, target, player path, and shared optimal route distinctly', () => {
  expect(mapBorderHopMarkings(
    ['Start', 'Detour', 'Shared', 'Target'],
    'Start',
    'Target',
    ['Start', 'Shared', 'Target'],
  )).toEqual({
    START: 'green',
    DETOUR: 'orange',
    SHARED: 'yellow',
    TARGET: 'blue',
  });
});

test('Border Hop reveals the shortest route only after a valid longer route', () => {
  const verification = {
    valid: true,
    hops: 3,
    optimal_hops: 2,
    optimal_path: ['Start', 'Shortcut', 'Target'],
  };
  expect(getRevealedOptimalPath(verification)).toEqual(['Start', 'Shortcut', 'Target']);
  expect(getRevealedOptimalPath({
    ...verification,
    hops: 2,
    optimal_hops: 2,
  })).toBeNull();
  expect(getRevealedOptimalPath({
    ...verification,
    valid: false,
  })).toBeNull();
});

test('Border Hop undo and reset return to the requested route positions', () => {
  expect(undoMapBorderHop(['Alabama'])).toEqual(['Alabama']);
  expect(undoMapBorderHop(['Alabama', 'Georgia', 'Florida'])).toEqual(['Alabama', 'Georgia']);
  expect(resetMapBorderHop('Alabama')).toEqual(['Alabama']);
  expect(resetMapBorderHop(null)).toEqual([]);
});
