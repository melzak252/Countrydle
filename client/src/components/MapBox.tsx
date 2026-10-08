import { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { MapContainer, TileLayer, GeoJSON, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useGameStore, type MapMarkerColor } from '../stores/gameStore';
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

const PRIME_MERIDIAN_LINES: [number, number][][] = [
  [[-85, 0], [85, 0]],
];

const REFERENCE_LABEL_ICON = L.divIcon({
  className: 'map-reference-label',
  html: '<span class="text-zinc-300 font-mono text-xs leading-4 select-none pointer-events-none">0°</span>',
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
    }));

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
          label.remove();
          return;
        }
        label.setLatLng(map.containerPointToLatLng([x, y]));
        if (!map.hasLayer(label)) label.addTo(map);
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

    update();
    map.on('move zoom resize', update);
    return () => {
      map.off('move zoom resize', update);
      labels.forEach((label) => label.remove());
    };
  }, [map]);

  return null;
}

const REFERENCE_LINE_STYLE: PathOptions = {
  color: '#a1a1aa',
  weight: 1.5,
  opacity: 0.85,
  dashArray: '6, 6',
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
  const { i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');
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
        className={isGameOver && correctCountryName ? 'max-md:!top-[17rem]' : 'max-md:!top-[14rem]'}
      />
      <div className="absolute top-[7rem] left-[12px] md:top-[5.25rem] md:left-[12px] z-[1050] flex flex-col gap-1 md:gap-2">
        {defaultCenter && (
          <button
            onClick={(e) => {
              e.preventDefault();
              handleResetView();
            }}
            className="bg-zinc-800 text-zinc-200 p-2 rounded shadow-md hover:bg-zinc-700 hover:text-white transition-colors border border-zinc-700 h-11 w-11 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title={isPl ? 'Resetuj widok' : 'Reset view'}
            aria-label={isPl ? 'Resetuj widok' : 'Reset view'}
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
            className={`p-2 rounded shadow-md transition-colors border h-11 w-11 md:w-8 md:h-8 flex items-center justify-center cursor-pointer ${
              showReferenceLines
                ? 'bg-zinc-700 text-zinc-100 border-zinc-500 hover:bg-zinc-600'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700 hover:bg-zinc-700 hover:text-white'
            }`}
            title={showReferenceLines
              ? (isPl ? 'Ukryj równik i południk Greenwich' : 'Hide Equator & Greenwich lines')
              : (isPl ? 'Pokaż równik i południk Greenwich' : 'Show Equator & Greenwich lines')}
            aria-label={isPl ? 'Przełącz linie równika i południka Greenwich' : 'Toggle Equator and Greenwich reference lines'}
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
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 h-11 w-11 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title={isPl ? 'Przybliż poprawne państwo' : 'Zoom to correct country'}
            aria-label={isPl ? 'Przybliż poprawne państwo' : 'Zoom to correct country'}
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

const getStyleFromState = (
  feature: Feature | undefined,
  eligibleNames: ReadonlySet<string>,
  markings: Record<string, MapMarkerColor>,
  currentCorrectName?: string
): PathOptions => {
  if (!feature || !feature.properties) return {};

  const countryName = feature.properties.SOVEREIGNT.toUpperCase();
  if (!eligibleNames.has(countryNameKey(countryName))) {
    return {
      fillColor: '#18181b',
      weight: 1,
      opacity: 0.4,
      color: '#71717a',
      fillOpacity: 0.7,
      dashArray: undefined,
    };
  }
  const isCorrect = isCorrectCountryFeature(feature, currentCorrectName);
  const marker = markings[countryName];

  if (isCorrect) {
    return {
      fillColor: '#10b981',
      weight: 2,
      opacity: 1,
      color: '#34d399',
      fillOpacity: 0.85,
    };
  }

  if (marker === 'green') {
    return {
      fillColor: '#059669',
      weight: 1.5,
      opacity: 0.8,
      color: '#6ee7b7',
      fillOpacity: 0.35,
    };
  }

  if (marker === 'red') {
    return {
      fillColor: '#b91c1c',
      weight: 2.5,
      opacity: 1,
      color: '#ef4444',
      fillOpacity: 0.45,
      dashArray: undefined,
    };
  }

  if (marker === 'blue') {
    return {
      fillColor: '#1d4ed8',
      weight: 2,
      opacity: 1,
      color: '#60a5fa',
      fillOpacity: 0.6,
    };
  }

  if (marker === 'orange') {
    return {
      fillColor: '#c2410c',
      weight: 2,
      opacity: 1,
      color: '#fb923c',
      fillOpacity: 0.6,
    };
  }

  return {
    fillColor: '#242424',
    weight: 1,
    opacity: 1,
    color: 'white',
    fillOpacity: 0.7,
    dashArray: undefined,
  };
};


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
    getStyleFromState(feature, current.current.eligibleNames, current.current.interaction.entityMarkings, current.current.revealedName)
  ), []);

  // Close lingering tooltips when mouse moves out of the map container
  useEffect(() => {
    if (!map) return;
    const onMapMouseOut = () => {
      if (activeHoverLayerRef.current) {
        const prev = activeHoverLayerRef.current;
        prev.closeTooltip?.();
        if (prev.feature) {
          prev.setStyle?.(getStyle(prev.feature));
        }
        activeHoverLayerRef.current = null;
      }
    };
    map.on('mouseout', onMapMouseOut);
    return () => {
      map.off('mouseout', onMapMouseOut);
    };
  }, [map, getStyle]);

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
          const newStyle = getStyleFromState(
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
          const prev = activeHoverLayerRef.current;
          prev.closeTooltip?.();
          if (prev.feature) {
            prev.setStyle?.(getStyle(prev.feature));
          }
        }
        activeHoverLayerRef.current = l;

        l.setStyle({
          weight: 2,
          fillOpacity: 0.85,
        });
        l.openTooltip?.();
      },
      mouseout: () => {
        const l = layer as FeatureLayer;
        const style = getStyle(feature);
        l.setStyle(style);
        l.closeTooltip?.();
        if (activeHoverLayerRef.current === l) {
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
      className={className ?? 'border border-zinc-800 rounded-xl shadow-lg h-[350px] md:h-[500px] mb-4 md:mb-8'}
      error={mapError}
      onRetry={retryMap}
    />;
  }

  return (
    <div className={`w-full overflow-hidden relative ${className ? className : 'bg-[#232227] border border-zinc-800 rounded-xl shadow-lg h-[350px] md:h-[500px] mb-4 md:mb-8'}`}>
      <style>{`
        .leaflet-container, .leaflet-tile-pane, .leaflet-map-pane, .leaflet-pane {
            background-color: #232227 !important;
            background: #232227 !important;
        }
        .leaflet-tile {
            background-color: #232227 !important;
        }
        .leaflet-interactive:focus {
            outline: none;
        }
        .leaflet-tooltip {
            pointer-events: none !important;
        }
        .leaflet-top, .leaflet-bottom, .leaflet-control {
            z-index: 1050 !important;
        }
      `}</style>
      <MapContainer 
        center={center} 
        zoom={zoom}
        style={{ height: '100%', width: '100%', background: '#232227', backgroundColor: '#232227' }}
        minZoom={minZoom}
        maxZoom={maxZoom}
        maxBounds={[[-80, -215], [84, 215]]}
        maxBoundsViscosity={0.85}
        zoomSnap={0}
        zoomDelta={0.5}
        doubleClickZoom={!L.Browser.mobile}
        wheelPxPerZoomLevel={60}
        wheelDebounceTime={40}
        attributionControl={false}
        ref={setMap}
        renderer={renderer}
      >
        <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
            bounds={[[-78, -180], [82, 180]]}
            errorTileUrl="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
            noWrap={true}
            keepBuffer={2}
            updateInterval={200}
            updateWhenZooming={false}
        />
        
        <GeoJSON 
            data={geoJsonData} 
            style={getStyle} 
            onEachFeature={onEachFeature}
            ref={geoJsonLayerRef}
        />
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
