import POWIAT_CATALOG from '../data/powiats_quiz_catalog.json';

export interface PlatesQuizPowiat {
  id: number;
  name: string;
  voivodeship: string;
  is_city_county: boolean;
  seat: string | null;
  population: number | null;
  area_km2: number | null;
  registration_plates: string[];
}

export interface VoivodeshipGroup {
  voivodeship: string;
  items: PlatesQuizPowiat[];
}

export interface PlatesIndex {
  catalog: PlatesQuizPowiat[];
  byId: Map<number, PlatesQuizPowiat>;
  byName: Map<string, PlatesQuizPowiat>;
  codeToIds: Map<string, number[]>;
  prefixCodes: Set<string>;
  voivodeshipGroups: VoivodeshipGroup[];
}

export type PlateMatchResult =
  | {
      status: 'matched';
      code: string;
      newlySolvedIds: number[];
      alreadySolvedIds: number[];
    }
  | {
      status: 'already_solved';
      code: string;
      ids: number[];
    }
  | {
      status: 'no_match';
      code: string;
    };

export const VOIVODESHIP_LIST: readonly string[] = [
  'dolnośląskie',
  'kujawsko-pomorskie',
  'lubelskie',
  'lubuskie',
  'łódzkie',
  'małopolskie',
  'mazowieckie',
  'opolskie',
  'podkarpackie',
  'podlaskie',
  'pomorskie',
  'śląskie',
  'świętokrzyskie',
  'warmińsko-mazurskie',
  'wielkopolskie',
  'zachodniopomorskie',
] as const;

export function normalizePlateInput(raw: string): string {
  return raw.trim().toUpperCase().replace(/[^A-Z]/g, '');
}

export function normalizePowiatKey(name: string): string {
  return name.trim().toLowerCase();
}

export function buildPlatesIndex(
  catalog: PlatesQuizPowiat[] = POWIAT_CATALOG as PlatesQuizPowiat[],
): PlatesIndex {
  const byId = new Map<number, PlatesQuizPowiat>();
  const byName = new Map<string, PlatesQuizPowiat>();
  const codeToIds = new Map<string, number[]>();

  for (const powiat of catalog) {
    byId.set(powiat.id, powiat);
    byName.set(normalizePowiatKey(powiat.name), powiat);
    for (const rawPlate of powiat.registration_plates) {
      const code = normalizePlateInput(rawPlate);
      if (!code) continue;
      const existing = codeToIds.get(code);
      if (existing) {
        if (!existing.includes(powiat.id)) existing.push(powiat.id);
      } else {
        codeToIds.set(code, [powiat.id]);
      }
    }
  }

  // Track 2-letter codes that are also prefixes of 3-letter codes (e.g., KR -> KRA/KRK, DB -> DBA).
  const prefixCodes = new Set<string>();
  for (const code of codeToIds.keys()) {
    if (code.length >= 3) {
      const two = code.slice(0, 2);
      if (codeToIds.has(two)) {
        prefixCodes.add(two);
      }
    }
  }

  const voivodeshipGroups: VoivodeshipGroup[] = VOIVODESHIP_LIST.map((voivodeship) => ({
    voivodeship,
    items: catalog
      .filter((p) => p.voivodeship.toLowerCase() === voivodeship)
      .sort((a, b) => a.name.localeCompare(b.name, 'pl')),
  }));

  return {
    catalog,
    byId,
    byName,
    codeToIds,
    prefixCodes,
    voivodeshipGroups,
  };
}

/**
 * Match a raw user plate input against the O(1) plate index.
 *
 * For 2-vs-3-letter prefix overlaps (e.g. KR vs KRA, DB vs DBA):
 * - On instant auto-match: if the 2-letter code has at least one unsolved powiat, it matches
 *   immediately; once all powiaty for the 2-letter code are solved, typing the 2-letter prefix
 *   returns `already_solved` so the input is NOT cleared and the user can type the 3rd letter.
 */
export function matchPlateInput(
  rawInput: string,
  solvedIds: ReadonlySet<number>,
  index: PlatesIndex,
): PlateMatchResult {
  const code = normalizePlateInput(rawInput);
  if (!code) {
    return { status: 'no_match', code: '' };
  }

  const ids = index.codeToIds.get(code);
  if (!ids || ids.length === 0) {
    return { status: 'no_match', code };
  }

  const newlySolvedIds: number[] = [];
  const alreadySolvedIds: number[] = [];
  for (const id of ids) {
    if (solvedIds.has(id)) {
      alreadySolvedIds.push(id);
    } else {
      newlySolvedIds.push(id);
    }
  }

  if (newlySolvedIds.length > 0) {
    return {
      status: 'matched',
      code,
      newlySolvedIds,
      alreadySolvedIds,
    };
  }

  return {
    status: 'already_solved',
    code,
    ids: alreadySolvedIds,
  };
}

export function formatQuizTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}
