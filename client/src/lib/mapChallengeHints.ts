import POWIAT_CATALOG from '../data/powiats_quiz_catalog.json';
import { normalizeMapRegionName } from './mapGameMode';

interface PowiatMapFact {
  name: string;
  voivodeship: string;
  seat: string | null;
  registration_plates: string[];
}

const powiatFacts = new Map(
  (POWIAT_CATALOG as PowiatMapFact[]).map((fact) => [normalizeMapRegionName(fact.name), fact]),
);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim());
}

export function getMapChallengePowiatHint(name: string): string | null {
  const fact = powiatFacts.get(normalizeMapRegionName(name));
  if (!fact) return null;

  const details = [
    fact.voivodeship ? `Voivodeship: ${fact.voivodeship}` : null,
    fact.seat ? `Seat: ${fact.seat}` : null,
    fact.registration_plates.length ? `Registration plates: ${fact.registration_plates.join(', ')}` : null,
  ].filter((detail): detail is string => detail !== null);
  return details.length ? details.join(' · ') : null;
}

export function getMapChallengeStateHint(detail: unknown): string | null {
  if (!isRecord(detail)) return null;

  const fields = [
    ['Neighboring states', 'neighboring_states'],
    ['Neighboring countries', 'neighboring_countries'],
    ['Water access', 'water_access'],
    ['Major rivers', 'major_rivers'],
    ['Mountain ranges', 'mountain_ranges'],
    ['Major highways', 'major_highways'],
  ] as const;

  for (const [label, key] of fields) {
    const facts = stringList(detail[key]);
    if (facts.length) return `${label}: ${facts.join(', ')}`;
  }
  return null;
}
