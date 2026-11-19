import type { MapMarkerColor } from '../stores/gameStore';
import type { BorderHopVerification } from '../services/api';
import { normalizeMapRegionName } from './mapGameMode';

function foldRegionText(value: string): string {
  return normalizeMapRegionName(value)
    .replace(/ł/g, 'l')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '');
}

function stripPowiatWord(value: string): string {
  return value.replace(/^powiat\s+/i, '').replace(/\s+powiat$/i, '').trim();
}

function stripVoivodeshipQualifier(value: string): string {
  return value.replace(/\s*\([^)]*\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
}

export function matchTypedNeighbor(
  typedName: string,
  neighbors: readonly string[],
  visitedPath: readonly string[] = [],
): string | null {
  const typedKey = foldRegionText(typedName);
  if (!typedKey) return null;

  const typedWithoutPowiat = stripPowiatWord(typedKey);
  const typedBase = stripPowiatWord(stripVoivodeshipQualifier(typedKey));

  let matchedName = neighbors.find((neighbor) => foldRegionText(neighbor) === typedKey);
  if (!matchedName) {
    matchedName = neighbors.find((neighbor) => stripPowiatWord(foldRegionText(neighbor)) === typedWithoutPowiat);
  }
  if (!matchedName && typedBase) {
    const baseMatches = neighbors.filter(
      (neighbor) => stripPowiatWord(stripVoivodeshipQualifier(foldRegionText(neighbor))) === typedBase,
    );
    if (baseMatches.length === 1) {
      matchedName = baseMatches[0];
    }
  }
  if (!matchedName) return null;
  const matchedKey = normalizeMapRegionName(matchedName);
  return visitedPath.some((visited) => normalizeMapRegionName(visited) === matchedKey) ? null : matchedName;
}

export function getRevealedOptimalPath(
  verification: BorderHopVerification | null | undefined,
): string[] | null {
  if (
    !verification?.valid
    || verification.optimal_hops === null
    || verification.hops <= verification.optimal_hops
  ) return null;
  return verification.optimal_path ?? null;
}

export function undoMapBorderHop(path: readonly string[]): string[] {
  return path.length > 1 ? path.slice(0, -1) : path.slice();
}

export function resetMapBorderHop(start: string | null | undefined): string[] {
  return start?.trim() ? [start.trim()] : [];
}

export function mapBorderHopMarkings(
  path: readonly string[],
  start: string | null | undefined = path[0],
  target?: string | null,
  optimalPath?: readonly string[] | null,
): Record<string, MapMarkerColor> {
  const markings: Record<string, MapMarkerColor> = {};
  const startKey = start ? normalizeMapRegionName(start) : null;
  const targetKey = target ? normalizeMapRegionName(target) : null;

  if (start) markings[start.toUpperCase()] = 'green';
  if (target) markings[target.toUpperCase()] = 'blue';

  path.forEach((name) => {
    const key = normalizeMapRegionName(name);
    if (key === startKey || key === targetKey) return;
    markings[name.toUpperCase()] = 'orange';
  });
  optimalPath?.forEach((name) => {
    const key = normalizeMapRegionName(name);
    if (key === startKey || key === targetKey) return;
    markings[name.toUpperCase()] = 'yellow';
  });
  return markings;
}
