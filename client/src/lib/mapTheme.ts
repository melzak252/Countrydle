import type { Feature } from 'geojson';
import type { PathOptions } from 'leaflet';
import type { MapMarkerColor } from '../stores/gameStore';

export const MAP_THEME = {
  map: {
    backgroundColor: '#ebe3cf',
    tileUrl: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    tileFilter: 'sepia(0.18) saturate(0.72)',
  },
  frameBorder: '#a89a7a',
  controls: {
    surface: '#f5eedc',
    activeSurface: '#e7ddc5',
    hoverSurface: '#ece4d1',
    ink: '#554b39',
    strongInk: '#40392d',
    mutedInk: '#766c58',
    border: '#b6a985',
    strongBorder: '#8d7957',
    focus: '#816642',
    correctHover: '#426a48',
  },
  graticule: {
    color: '#a8997a',
    opacity: 0.48,
  },
  referenceLines: {
    color: '#8b7450',
    opacity: 0.8,
  },
  referenceLabel: '#705a3d',
  countries: {
    available: {
      fillColor: '#decb9f',
      weight: 1.35,
      opacity: 0.98,
      color: '#3f3424',
      fillOpacity: 0.82,
    },
    unavailable: {
      fillColor: '#e4dac2',
      weight: 0.95,
      opacity: 0.84,
      color: '#756850',
      fillOpacity: 0.72,
    },
    correct: {
      fillColor: '#527c55',
      weight: 2.2,
      opacity: 1,
      color: '#294c30',
      fillOpacity: 0.95,
    },
    markers: {
      green: {
        fillColor: '#92ad78',
        weight: 1.7,
        opacity: 1,
        color: '#4e6d40',
        fillOpacity: 0.87,
      },
      red: {
        fillColor: '#c77b63',
        weight: 2,
        opacity: 1,
        color: '#834a3b',
        fillOpacity: 0.84,
      },
      blue: {
        fillColor: '#7793a1',
        weight: 1.8,
        opacity: 1,
        color: '#455f6c',
        fillOpacity: 0.84,
      },
      orange: {
        fillColor: '#c79850',
        weight: 1.8,
        opacity: 1,
        color: '#835f2b',
        fillOpacity: 0.84,
      },
      yellow: {
        fillColor: '#e7cf6f',
        weight: 2,
        opacity: 1,
        color: '#66501f',
        fillOpacity: 0.92,
      },
    },
  },
} as const satisfies {
  map: {
    backgroundColor: string;
    tileUrl: string;
    tileFilter: string;
  };
  frameBorder: string;
  controls: {
    surface: string;
    activeSurface: string;
    hoverSurface: string;
    ink: string;
    strongInk: string;
    mutedInk: string;
    border: string;
    strongBorder: string;
    focus: string;
    correctHover: string;
  };
  graticule: {
    color: string;
    opacity: number;
  };
  referenceLines: {
    color: string;
    opacity: number;
  };
  referenceLabel: string;
  countries: {
    available: PathOptions;
    unavailable: PathOptions;
    correct: PathOptions;
    markers: Record<MapMarkerColor, PathOptions>;
  };
};

export const MAP_THEME_CSS_VARIABLES = {
  '--map-ocean': MAP_THEME.map.backgroundColor,
  '--map-tile-filter': MAP_THEME.map.tileFilter,
  '--map-frame-border': MAP_THEME.frameBorder,
  '--map-control-bg': MAP_THEME.controls.surface,
  '--map-control-active': MAP_THEME.controls.activeSurface,
  '--map-control-hover': MAP_THEME.controls.hoverSurface,
  '--map-control-ink': MAP_THEME.controls.ink,
  '--map-control-strong-ink': MAP_THEME.controls.strongInk,
  '--map-control-muted-ink': MAP_THEME.controls.mutedInk,
  '--map-control-border': MAP_THEME.controls.border,
  '--map-control-strong-border': MAP_THEME.controls.strongBorder,
  '--map-control-focus': MAP_THEME.controls.focus,
  '--map-correct-fill': MAP_THEME.countries.correct.fillColor,
  '--map-correct-edge': MAP_THEME.countries.correct.color,
  '--map-correct-hover': MAP_THEME.controls.correctHover,
} as const;

function countryNameKey(name: string): string {
  return name.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
}

function isCorrectCountryFeature(feature: Feature, targetName?: string): boolean {
  const name = feature.properties?.SOVEREIGNT;
  return typeof name === 'string' && !!targetName
    && name.localeCompare(targetName, undefined, { sensitivity: 'base' }) === 0;
}

export function getCountryFeatureStyle(
  feature: Feature | undefined,
  eligibleNames: ReadonlySet<string>,
  markings: Record<string, MapMarkerColor>,
  currentCorrectName?: string,
  autoMarkings?: Record<string, MapMarkerColor>,
  showAutoMarkings = true,
): PathOptions {
  if (!feature?.properties) return MAP_THEME.countries.unavailable;
  const countryName = feature.properties.SOVEREIGNT;
  if (typeof countryName !== 'string') return MAP_THEME.countries.unavailable;
  if (!eligibleNames.has(countryNameKey(countryName))) return MAP_THEME.countries.unavailable;
  if (isCorrectCountryFeature(feature, currentCorrectName)) return MAP_THEME.countries.correct;

  const key = countryName.toUpperCase();
  const manualMarker = markings[key];
  if (manualMarker) return MAP_THEME.countries.markers[manualMarker];

  if (showAutoMarkings && autoMarkings) {
    const autoMarker = autoMarkings[countryNameKey(countryName)] ?? autoMarkings[key];
    if (autoMarker) {
      const base = MAP_THEME.countries.markers[autoMarker];
      return {
        ...base,
        fillOpacity: autoMarker === 'orange' ? 0.45 : 0.68,
      };
    }
  }

  return MAP_THEME.countries.available;
}
