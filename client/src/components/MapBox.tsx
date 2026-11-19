import { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback, type CSSProperties } from 'react';

import { MapContainer, GeoJSON, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useGameStore } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check, Compass, RotateCcw } from 'lucide-react';
import type { MapInteractionState } from '../lib/mapMarkings';
import { isCountryAvailable } from '../lib/countryEligibility';
import { useMapData } from '../hooks/useMapData';
import { useMapZoomSync } from '../hooks/useMapZoomSync';
import MapLoading from './MapLoading';
import { focusMapBounds, resetMapView, trackMapZoom } from '../lib/mapView';
import { createMapRenderer } from '../lib/mapRenderer';
import { getCountryFeatureStyle, MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import { EARTH_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';

type FeatureLayer = L.Path & { feature?: Feature };

function countryNameKey(name: string): string {
  return name.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
}

function isCorrectCountryFeature(feature: Feature | undefined, targetName?: string) {
  const name = feature?.properties?.SOVEREIGNT;
  return typeof name === 'string' && !!targetName
    && name.localeCompare(targetName, undefined, { sensitivity: 'base' }) === 0;
}

const EQUATOR_COORDINATES: [number, number][] = [
  [0, -180],
  [0, 180],
];

const MERIDIAN_LATITUDES = [-58, -45, -30, -15, 0, 15, 30, 45, 60, 75, 84.6];
const PRIME_MERIDIAN_LINES: [number, number][][] = [
  [[-58, 0], [84.6, 0]],
];
const GRATICULE_LINES: [number, number][][] = [
  ...[-150, -120, -90, -60, -30, 30, 60, 90, 120, 150].map(longitude =>
    MERIDIAN_LATITUDES.map(latitude => [latitude, longitude] as [number, number])
  ),
  ...[-30, 30, 60].map(latitude =>
    Array.from({ length: 25 }, (_, index) => [latitude, -180 + index * 15] as [number, number])
  ),
];


const REFERENCE_LABEL_ICON = L.divIcon({
  className: 'map-reference-label',
  html: `<span class="font-mono text-xs leading-4 select-none pointer-events-none" style="color:${MAP_THEME.referenceLabel}">0°</span>`,
  iconSize: [20, 16],
  iconAnchor: [0, 0],
});

function ReferenceLineLabels() {
  const map = useMap();

  useEffect(() => {
    const labels = Array.from({ length: 5 }, () => L.marker([0, 0], {
      icon: REFERENCE_LABEL_ICON,
      interactive: false,
      keyboard: false,
      opacity: 0,
    }).addTo(map));

    let rafId: number | null = null;
    const update = () => {
      const { x: width, y: height } = map.getSize();
      const longitude = 0;
      const crossing = map.latLngToContainerPoint([0, longitude]);
      const meridianVisible = crossing.x >= 0 && crossing.x <= width;
      const equatorVisible = crossing.y >= 0 && crossing.y <= height;
      const labelX = crossing.x + 32 <= width - 12 ? crossing.x + 12 : crossing.x - 32;
      const labelY = crossing.y >= 36 ? crossing.y - 24 : crossing.y + 8;

      const place = (index: number, x: number, y: number, visible: boolean) => {
        const label = labels[index];
        if (!visible) {
          label.setOpacity(0);
          return;
        }
        label.setLatLng(map.containerPointToLatLng([x, y]));
        label.setOpacity(1);
      };

      const bounds = map.getBounds();
      // Leave room for the status bar and question dock over the map.
      place(0, labelX, 52, meridianVisible && bounds.getNorth() <= 85);
      place(1, labelX, height - 160, meridianVisible && bounds.getSouth() >= -85);
      place(2, 12, labelY, equatorVisible && bounds.getWest() >= -180);
      place(3, width - 32, labelY, equatorVisible && bounds.getEast() <= 180);
      place(4, labelX, labelY, meridianVisible && equatorVisible
        && crossing.x > 52 && crossing.x < width - 52
        && crossing.y > 100 && crossing.y < height - 184);
    };

    const scheduleUpdate = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        update();
      });
    };

    update();
    map.on('move zoom resize', scheduleUpdate);
    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      map.off('move zoom resize', scheduleUpdate);
      labels.forEach((label) => label.remove());
    };
  }, [map]);

  return null;
}

const GRATICULE_STYLE: PathOptions = {
  color: MAP_THEME.graticule.color,
  weight: 0.7,
  opacity: MAP_THEME.graticule.opacity,
  interactive: false,
};

const REFERENCE_LINE_STYLE: PathOptions = {
  color: MAP_THEME.referenceLines.color,
  weight: 1.2,
  opacity: MAP_THEME.referenceLines.opacity,
  dashArray: '5, 7',
  interactive: false,
};

interface MapBoxProps {
  correctCountryName?: string;
  className?: string;
  onCountryCode?: (code: string | undefined) => void;
  center?: [number, number];
  zoom?: number;
  minZoom?: number;
  maxZoom?: number;
  onCountryClick?: (name: string) => void;
  geoJsonUrl?: string;
  eligibleCountries: readonly { name: string }[];
  countryMode?: string;
}

interface MapControlsProps {
  correctCountryName?: string;
  geoJsonData: FeatureCollection | null;
  map: L.Map | null;
  interaction: MapInteractionState;
  defaultCenter?: [number, number];
  defaultZoom?: number;
  showReferenceLines?: boolean;
  onToggleReferenceLines?: () => void;
}
function MapControls({
  correctCountryName,
  geoJsonData,
  map,
  interaction,
  defaultCenter,
  defaultZoom,
  showReferenceLines,
  onToggleReferenceLines,
}: MapControlsProps) {
  
  
  const { isGameOver, activeMarkerColor, setActiveMarkerColor, clearMapMarkings } = interaction;
  const handleZoomToCorrect = () => {
    if (map && correctCountryName && geoJsonData) {
      const correctFeature = geoJsonData.features.find(feature => isCorrectCountryFeature(feature, correctCountryName));

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            focusMapBounds(map, bounds);
        }
      }
    }
  };
  const handleResetView = () => {
    if (map && defaultCenter) {
      resetMapView(map, defaultCenter, defaultZoom ?? 2);
    }
  };

  return (
    <>
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
        className={isGameOver && correctCountryName ? 'max-md:!top-[13.5rem]' : 'max-md:!top-[11rem]'}
      />
      <div className="absolute top-[5.75rem] left-[12px] md:top-[5.25rem] md:left-[12px] z-[1050] flex flex-col gap-1 md:gap-2">
        {defaultCenter && (
          <button
            onClick={(e) => {
              e.preventDefault();
              handleResetView();
            }}
            className="bg-[var(--map-control-bg)] text-[var(--map-control-ink)] p-2 rounded shadow-sm hover:bg-[var(--map-control-hover)] hover:text-[var(--map-control-strong-ink)] transition-colors border border-[var(--map-control-border)] h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)]"
            title={'Reset view'}
            aria-label={'Reset view'}
          >
            <RotateCcw size={15} />
          </button>
        )}
        {onToggleReferenceLines && (
          <button
            onClick={(e) => {
              e.preventDefault();
              onToggleReferenceLines();
            }}
            className={`p-2 rounded shadow-sm transition-colors border h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)] ${
              showReferenceLines
                ? 'bg-[var(--map-control-active)] text-[var(--map-control-strong-ink)] border-[var(--map-control-strong-border)] hover:bg-[var(--map-control-hover)]'
                : 'bg-[var(--map-control-bg)] text-[var(--map-control-muted-ink)] border-[var(--map-control-border)] hover:bg-[var(--map-control-hover)] hover:text-[var(--map-control-ink)]'
            }`}
            title={showReferenceLines
              ? ('Hide Equator & Greenwich lines')
              : ('Show Equator & Greenwich lines')}
            aria-label={'Toggle Equator and Greenwich reference lines'}
            aria-pressed={showReferenceLines}
          >
            <Compass size={15} />
          </button>
        )}
        {isGameOver && correctCountryName && (
          <button
            onClick={(e) => {
              e.preventDefault();
              handleZoomToCorrect();
            }}
            className="bg-[var(--map-correct-fill)] text-white p-2 rounded shadow-sm hover:bg-[var(--map-correct-hover)] transition-colors border border-[var(--map-correct-edge)] h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)]"
            title={'Zoom to correct country'}
            aria-label={'Zoom to correct country'}
          >
            <Check size={16} />
          </button>
        )}
      </div>
    </>
  );
}

function MapController({
  correctCountryName,
  geoJsonData,
  isGameOver,
}: {
  correctCountryName?: string;
  geoJsonData: FeatureCollection | null;
  isGameOver: boolean;
}) {
  const map = useMap();
  useMapZoomSync(map);
  useEffect(() => trackMapZoom(map), [map]);

  // Keep Leaflet viewport and tiles updated when container size changes
  useEffect(() => {
    const container = map.getContainer();
    if (!container) return;

    map.invalidateSize();

    if (typeof ResizeObserver === 'undefined') return;
    let lastWidth = container.clientWidth;
    let lastHeight = container.clientHeight;
    let resizeTimer: number | undefined;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        // Ignore micro-subpixel shifts during pan/zoom transforms
        if (Math.abs(width - lastWidth) > 3 || Math.abs(height - lastHeight) > 3) {
          lastWidth = width;
          lastHeight = height;
          window.clearTimeout(resizeTimer);
          resizeTimer = window.setTimeout(() => {
            map.invalidateSize({ animate: false });
          }, 100);
        }
      }
    });
    observer.observe(container);
    return () => {
      window.clearTimeout(resizeTimer);
      observer.disconnect();
    };
  }, [map]);

  useEffect(() => {
    if (isGameOver && correctCountryName && geoJsonData) {
      // Find the feature for the correct country
      const correctFeature = geoJsonData.features.find(feature => isCorrectCountryFeature(feature, correctCountryName));

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            focusMapBounds(map, bounds);
        }
      }
    }
  }, [isGameOver, correctCountryName, geoJsonData, map]);

  return null;
}

export default function MapBox({ correctCountryName, className, onCountryCode }: Omit<MapBoxProps, 'eligibleCountries'>) {
  const state = useGameStore();
  return <ControlledMapBox className={className} onCountryCode={onCountryCode}
    eligibleCountries={state.entities}
    correctCountryName={correctCountryName || state.correctEntity?.name}
    interaction={{
      entityMarkings: state.entityMarkings,
      activeMarkerColor: state.activeMarkerColor,
      setActiveMarkerColor: state.setActiveMarkerColor,
      handleEntityMapClick: state.handleEntityMapClick,
      clearMapMarkings: state.clearMapMarkings,
      isGameOver: !!state.gameState?.is_game_over,
    }} />;
}



export function ControlledMapBox({
  correctCountryName,
  className,
  onCountryCode,
  interaction,
  center = [16, 12],
  zoom = 3.2,
  minZoom = 2.7,
  maxZoom = 10,
  onCountryClick,
  geoJsonUrl = '/countries_50m.geojson',
  eligibleCountries,
  countryMode,
}: MapBoxProps & { interaction: MapInteractionState }) {
  const targetUrl = geoJsonUrl || '/countries_50m.geojson';
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData(targetUrl);
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  const [showReferenceLines, setShowReferenceLines] = useState<boolean>(true);
  const { entityMarkings, isGameOver } = interaction;
  const eligibleNames = useMemo(() => new Set(eligibleCountries
    .filter(country => isCountryAvailable(country.name, countryMode))
    .map(country => countryNameKey(country.name))), [eligibleCountries, countryMode]);
  const revealedName = isGameOver && correctCountryName && eligibleNames.has(countryNameKey(correctCountryName))
    ? correctCountryName
    : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onCountryClick, eligibleNames });
  useLayoutEffect(() => {
    current.current = { interaction, revealedName, onCountryClick, eligibleNames };
  }, [interaction, revealedName, onCountryClick, eligibleNames]);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);

  const getStyle = useCallback((feature: Feature | undefined) => (
    getCountryFeatureStyle(feature, current.current.eligibleNames, current.current.interaction.entityMarkings, current.current.revealedName)
  ), []);

  const hoverLayerRef = useRef<L.GeoJSON | null>(null);

  // Dedicated lightweight SVG overlay for hover so pointer moves don't repaint the entire L.Canvas.
  useEffect(() => {
    if (!map) return;
    const hoverRenderer = L.svg({ padding: 0.5 });
    const hoverLayer = L.geoJSON(undefined, {
      renderer: hoverRenderer,
      interactive: false,
      style: {
        weight: 2,
        color: MAP_THEME.controls.strongInk,
        fillColor: MAP_THEME.controls.ink,
        fillOpacity: 0.12,
      },
    } as L.GeoJSONOptions & { renderer: L.Renderer }).addTo(map);
    hoverLayerRef.current = hoverLayer;

    const onMapMouseOut = () => {
      hoverLayer.clearLayers();
      if (activeHoverLayerRef.current) {
        activeHoverLayerRef.current.closeTooltip?.();
        activeHoverLayerRef.current = null;
      }
    };
    map.on('mouseout', onMapMouseOut);
    return () => {
      map.off('mouseout', onMapMouseOut);
      hoverLayer.remove();
      hoverLayerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    if (!onCountryCode) return;
    const name = revealedName?.toLowerCase();
    const feature = geoJsonData?.features.find((item: Feature) => {
      const properties = item.properties;
      return name && [properties?.ADMIN, properties?.NAME_LONG, properties?.NAME_EN]
        .some(value => typeof value === 'string' && value.toLowerCase() === name);
    });
    const code = [feature?.properties?.ISO_A2, feature?.properties?.WB_A2]
      .find(value => typeof value === 'string' && /^[a-z]{2}$/i.test(value));
    onCountryCode(code?.toLowerCase());
  }, [revealedName, geoJsonData, onCountryCode]);

  // Optimization: Update styles imperatively instead of re-rendering whole map
  useEffect(() => {
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((item) => {
        const layer = item as FeatureLayer;
        const feature = layer.feature;
        if (feature) {
          const newStyle = getCountryFeatureStyle(
            feature,
            eligibleNames,
            entityMarkings,
            revealedName
          );
          layer.setStyle(newStyle);
          if (isCorrectCountryFeature(feature, revealedName)) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData, eligibleNames]);
  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const countryName = feature.properties?.SOVEREIGNT;
    
    // Bind click handler
    layer.on({
      click: () => {
        if (!current.current.eligibleNames.has(countryNameKey(countryName)) || isCorrectCountryFeature(feature, current.current.revealedName)) {
          return;
        }

        current.current.interaction.handleEntityMapClick(countryName.toUpperCase(), false);
        current.current.onCountryClick?.(countryName);
      },
      contextmenu: (e: L.LeafletMouseEvent) => {
        e.originalEvent?.preventDefault?.();
        if (!current.current.eligibleNames.has(countryNameKey(countryName)) || isCorrectCountryFeature(feature, current.current.revealedName)) {
          return;
        }

        current.current.interaction.handleEntityMapClick(countryName.toUpperCase(), true);
      },
      mouseover: () => {
        if (!current.current.eligibleNames.has(countryNameKey(countryName))) return;
        const l = layer as FeatureLayer;
        if (activeHoverLayerRef.current && activeHoverLayerRef.current !== l) {
          activeHoverLayerRef.current.closeTooltip?.();
        }
        activeHoverLayerRef.current = l;
        if (hoverLayerRef.current) {
          hoverLayerRef.current.clearLayers();
          hoverLayerRef.current.addData(feature);
        }
        l.openTooltip?.();
      },
      mouseout: () => {
        const l = layer as FeatureLayer;
        l.closeTooltip?.();
        if (activeHoverLayerRef.current === l) {
          hoverLayerRef.current?.clearLayers();
          activeHoverLayerRef.current = null;
        }
      }
    });

    if (feature.properties) {
      const name = feature.properties.SOVEREIGNT || feature.properties.ADMIN;
      const sub = feature.properties.ADMIN && feature.properties.ADMIN !== feature.properties.SOVEREIGNT
        ? ` (${feature.properties.ADMIN})`
        : '';
      layer.bindTooltip(`<b>${name}</b>${sub}`, {
        sticky: false,
        direction: 'auto',
        opacity: 0.95,
      });
    }
  };

  if (!geoJsonData) {
    return <MapLoading
      className={className ?? 'border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[350px] md:h-[500px] mb-4 md:mb-8'}
      error={mapError}
      onRetry={retryMap}
    />;
  }

  return (
    <div className={`country-map-theme w-full overflow-hidden relative ${className ? className : 'bg-[var(--map-ocean)] border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[350px] md:h-[500px] mb-4 md:mb-8'}`} style={MAP_THEME_CSS_VARIABLES as CSSProperties}>
      <style>{`
        .country-map-theme .leaflet-top,
        .country-map-theme .leaflet-bottom,
        .country-map-theme .leaflet-control {
            z-index: 1050 !important;
        }
      `}</style>
      <MapContainer 
        className="antique-map-surface"
        center={center} 
        zoom={zoom}
        style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor, backgroundColor: MAP_THEME.map.backgroundColor }}
        minZoom={minZoom}
        maxZoom={maxZoom}
        maxBounds={EARTH_PAN_BOUNDS}
        maxBoundsViscosity={0}
        worldCopyJump={false}
        zoomSnap={0}
        zoomDelta={0.5}
        doubleClickZoom={!L.Browser.mobile}
        wheelPxPerZoomLevel={60}
        wheelDebounceTime={40}
        attributionControl={false}
        ref={setMap}
        renderer={renderer}
      >
        <ParchmentWorldBackdrop />
        
        <GeoJSON 
            data={geoJsonData} 
            style={getStyle} 
            onEachFeature={onEachFeature}
            ref={geoJsonLayerRef}
        />
        {GRATICULE_LINES.map((coordinates, index) => (
          <Polyline
            key={`graticule-${index}`}
            positions={coordinates}
            pathOptions={GRATICULE_STYLE}
          />
        ))}
        {showReferenceLines && (
          <>
            {/* Equator (0° Latitude) */}
            <Polyline
              positions={EQUATOR_COORDINATES}
              pathOptions={REFERENCE_LINE_STYLE}
            />

            {/* Prime Meridian / Greenwich Line (0° Longitude) & duplicates */}
            {PRIME_MERIDIAN_LINES.map((lineCoords, idx) => (
              <Polyline
                key={`prime-meridian-${idx}`}
                positions={lineCoords}
                pathOptions={REFERENCE_LINE_STYLE}
              />
            ))}

            <ReferenceLineLabels />
          </>
        )}
        
        <MapController correctCountryName={revealedName} geoJsonData={geoJsonData} isGameOver={isGameOver} />
        <MapCartographicTexture />
        <MapPaperEdge bounds={WORLD_SHEET_BOUNDS} />
      </MapContainer>
      <MapControls
        correctCountryName={revealedName}
        geoJsonData={geoJsonData}
        map={map}
        interaction={interaction}
        defaultCenter={center}
        defaultZoom={zoom}
        showReferenceLines={showReferenceLines}
        onToggleReferenceLines={() => setShowReferenceLines((prev) => !prev)}
      />
    </div>
  );
}
