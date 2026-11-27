import type { MapMarkerColor } from '../stores/gameStore';
import type { Question } from '../types';

export interface MapInteractionState {
  entityMarkings: Record<string, MapMarkerColor>;
  autoEntityMarkings?: Record<string, MapMarkerColor>;
  showAutoMarkings?: boolean;
  onToggleAutoMarkings?: () => void;
  activeMarkerColor: MapMarkerColor;
  setActiveMarkerColor: (color: MapMarkerColor) => void;
  handleEntityMapClick: (name: string, isSecondary?: boolean) => void;
  clearMapMarkings: () => void;
  isGameOver: boolean;
}

function normalizeAutoKey(name: string): string {
  return name.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
}

export function computeAutoEntityMarkings(questions: readonly Question[]): Record<string, MapMarkerColor> {
  const ruledOut = new Set<string>();
  let positive: Set<string> | null = null;

  for (const question of questions) {
    const highlight = question.map_highlight;
    if (!highlight || !highlight.supported) continue;

    if (question.answer === false) {
      // Only color the countries the question asked about as ruled-out (orange); leave the rest untouched.
      for (const name of highlight.eliminated || []) {
        ruledOut.add(normalizeAutoKey(name));
      }
    } else if (question.answer === true) {
      // Only color the countries the question matched as possible (blue), narrowing cumulatively.
      const matchedSet = new Set((highlight.matched || []).map(normalizeAutoKey));
      if (positive === null) {
        positive = matchedSet;
      } else {
        const next = new Set<string>();
        for (const name of positive) {
          if (matchedSet.has(name)) next.add(name);
        }
        positive = next;
      }
    }
  }

  const markings: Record<string, MapMarkerColor> = {};
  for (const name of ruledOut) {
    markings[name] = 'orange';
  }
  if (positive) {
    for (const name of positive) {
      if (!ruledOut.has(name)) {
        markings[name] = 'blue';
      }
    }
  }
  return markings;
}

export function mapClickColor(activeColor: MapMarkerColor, isSecondary = false): MapMarkerColor {
  if (typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches) {
    return 'red';
  }
  if (!isSecondary) return activeColor;
  switch (activeColor) {
    case 'green': return 'red';
    case 'red': return 'green';
    case 'blue': return 'orange';
    case 'orange': return 'blue';
    case 'yellow': return 'orange';
  }
}

export function toggleMapMarking(
  markings: Record<string, MapMarkerColor>,
  name: string,
  color: MapMarkerColor,
): Record<string, MapMarkerColor> {
  const normalized = name.toUpperCase();
  const nextMarkings = { ...markings };
  if (nextMarkings[normalized] === color) {
    delete nextMarkings[normalized];
  } else {
    nextMarkings[normalized] = color;
  }
  return nextMarkings;
}
