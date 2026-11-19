import type { LatLngBoundsExpression } from 'leaflet';

const MAX_MERCATOR_LATITUDE = 85.05112878;

export const EARTH_MAP_BOUNDS: LatLngBoundsExpression = [
  [-MAX_MERCATOR_LATITUDE, -180],
  [MAX_MERCATOR_LATITUDE, 180],
];

// Crop empty Antarctica from the bottom of the world map sheet while keeping Cape Horn (-56°S) and Greenland (83.6°N).
export const WORLD_SHEET_BOUNDS: LatLngBoundsExpression = [
  [-58, -180],
  [84.6, 180],
];

export const EARTH_PAN_BOUNDS: LatLngBoundsExpression = [
  [-62, -540],
  [85, 540],
];

export const POLAND_MAP_BOUNDS: LatLngBoundsExpression = [
  [46.5, 11.5],
  [56.5, 27.5],
];

export const POLAND_PAN_BOUNDS: LatLngBoundsExpression = [
  [-62, -540],
  [85, 540],
];

export const US_STATES_MAP_BOUNDS: LatLngBoundsExpression = [
  [15, -180],
  [73, -62],
];

// Wide pan bounds so players can drag any state/island freely west or east without snap-back.
export const US_STATES_PAN_BOUNDS: LatLngBoundsExpression = [
  [-62, -540],
  [85, 540],
];
