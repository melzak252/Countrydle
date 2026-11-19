export type MapGameMode = 'powiaty' | 'us_states';

export const MAP_QUIZ_PATHS = {
  powiaty: '/powiat-map-quiz',
  us_states: '/us-state-map-quiz',
} as const satisfies Record<MapGameMode, string>;

export function parseMapGameMode(mode: string | null | undefined): MapGameMode {
  return mode === 'us_states' ? 'us_states' : 'powiaty';
}

export function normalizeMapRegionName(name: string): string {
  return name.trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/ł/gi, 'l')
    .toLowerCase();
}
