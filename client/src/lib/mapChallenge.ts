import type { FeatureCollection } from 'geojson';
import type { MapMarkerColor } from '../stores/gameStore';
import type { MapInteractionState } from './mapMarkings';
import { normalizeMapRegionName, type MapGameMode } from './mapGameMode';

export const MAP_CHALLENGE_PROMPT_COUNT = 10;

export const MAP_CHALLENGE_FEEDBACK_DELAY_MS = 700;

export interface MapChallengeState {
  prompts: string[];
  currentPromptIndex: number;
  score: number;
  status: 'playing' | 'correct' | 'incorrect' | 'finished';
  markings: Record<string, MapMarkerColor>;
}

const noOperation = () => undefined;

export function createIsolatedMapInteraction(
  entityMarkings: Record<string, MapMarkerColor>,
): MapInteractionState {
  return {
    entityMarkings,
    activeMarkerColor: 'green',
    setActiveMarkerColor: noOperation,
    handleEntityMapClick: noOperation,
    clearMapMarkings: noOperation,
    isGameOver: false,
  };
}

export function getMapChallengePool(data: FeatureCollection | null, mode: MapGameMode): string[] {
  if (!data) return [];

  const names: string[] = [];
  const seen = new Set<string>();
  for (const feature of data.features) {
    const properties = feature.properties as Record<string, unknown> | null;
    const rawName = properties?.[mode === 'powiaty' ? 'nazwa' : 'name'];
    if (typeof rawName !== 'string' || !rawName.trim()) continue;
    const name = rawName.trim();
    const key = normalizeMapRegionName(name);
    if (!key || seen.has(key)) continue;
    if (mode === 'us_states' && ['district of columbia', 'washington dc', 'washington d c', 'puerto rico'].includes(key)) continue;
    seen.add(key);
    names.push(name);
  }
  return names;
}

export function createMapChallengeState(
  names: readonly string[],
  random: () => number = Math.random,
): MapChallengeState {
  const uniqueNames = Array.from(new Map(
    names.map((name) => [normalizeMapRegionName(name), name.trim()] as const),
  ).values()).filter(Boolean);
  const shuffled = uniqueNames.slice();
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }
  const prompts = shuffled.slice(0, MAP_CHALLENGE_PROMPT_COUNT);
  return {
    prompts,
    currentPromptIndex: 0,
    score: 0,
    status: prompts.length ? 'playing' : 'finished',
    markings: {},
  };
}

export function answerMapChallenge(state: MapChallengeState, clickedName: string): MapChallengeState {
  if (state.status !== 'playing') return state;
  const target = state.prompts[state.currentPromptIndex];
  if (!target) return state;

  const isCorrect = normalizeMapRegionName(clickedName) === normalizeMapRegionName(target);
  return {
    ...state,
    score: state.score + (isCorrect ? 1 : 0),
    status: isCorrect ? 'correct' : 'incorrect',
    markings: { ...state.markings, [target.toUpperCase()]: isCorrect ? 'green' : 'red' },
  };
}

export function advanceMapChallenge(state: MapChallengeState): MapChallengeState {
  if (state.status !== 'correct' && state.status !== 'incorrect') return state;
  const nextIndex = state.currentPromptIndex + 1;
  if (nextIndex >= state.prompts.length) return { ...state, status: 'finished' };
  return { ...state, currentPromptIndex: nextIndex, status: 'playing' };
}
