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
  const everEliminated = new Set<string>();
  let currentPossible: Set<string> | null = null;

  for (const question of questions) {
    const highlight = question.map_highlight;
    if (!highlight || !highlight.supported) continue;

    for (const name of highlight.eliminated || []) {
      everEliminated.add(normalizeAutoKey(name));
    }

    const matchedSet = new Set((highlight.matched || []).map(normalizeAutoKey));
    if (currentPossible === null) {
      currentPossible = matchedSet;
    } else {
      const next = new Set<string>();
      for (const name of currentPossible) {
        if (matchedSet.has(name)) next.add(name);
      }
      currentPossible = next;
    }
  }

  const markings: Record<string, MapMarkerColor> = {};
  for (const name of everEliminated) {
    markings[name] = 'orange';
  }
  if (currentPossible) {
    for (const name of currentPossible) {
      if (!everEliminated.has(name)) {
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
