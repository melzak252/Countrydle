import type { MapMarkerColor } from '../stores/gameStore';

export interface MapInteractionState {
  entityMarkings: Record<string, MapMarkerColor>;
  activeMarkerColor: MapMarkerColor;
  setActiveMarkerColor: (color: MapMarkerColor) => void;
  handleEntityMapClick: (name: string, isSecondary?: boolean) => void;
  clearMapMarkings: () => void;
  isGameOver: boolean;
}

export function mapClickColor(activeColor: MapMarkerColor, isSecondary = false): MapMarkerColor {
  if (!isSecondary) return activeColor;
  switch (activeColor) {
    case 'green': return 'red';
    case 'red': return 'green';
    case 'blue': return 'orange';
    case 'orange': return 'blue';
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
