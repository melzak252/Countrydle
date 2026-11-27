import { useState, useEffect, useLayoutEffect, useRef, useCallback, type CSSProperties } from 'react';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useCountydleGameStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check } from 'lucide-react';
import type { MapInteractionState } from '../lib/mapMarkings';
import { useMapData } from '../hooks/useMapData';
import { useMapZoomSync } from '../hooks/useMapZoomSync';
import MapLoading from './MapLoading';
import { focusMapBounds, resetMapView, trackMapZoom } from '../lib/mapView';
import { createMapRenderer } from '../lib/mapRenderer';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';
import { EARTH_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';

type FeatureLayer = L.Path & { feature?: Feature };

interface EnglandCountiesMapProps {
  correctCountyName?: string;
  className?: string;
  onCountyClick?: (name: string) => void;
}

const ENGLAND_CENTER: [number, number] = [52.85, -1.6];
const ENGLAND_ZOOM = 6;

function getCountyName(feature: Feature | undefined): string {
  const raw = feature?.properties?.name ?? feature?.properties?.NAME ?? '';
  return String(raw).trim();
}

function MapController({
  correctName,
  geoJsonData,
  isGameOver,
}: {
  correctName?: string;
  geoJsonData: FeatureCollection | null;
  isGameOver: boolean;
}) {
  const map = useMap();
  useMapZoomSync(map);
  useEffect(() => trackMapZoom(map), [map]);

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
    if (isGameOver && correctName && geoJsonData) {
      const correctFeature = geoJsonData.features.find(
        (f) => getCountyName(f).toUpperCase() === correctName.toUpperCase()
      );
      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          focusMapBounds(map, bounds);
        }
      }
    }
  }, [isGameOver, correctName, geoJsonData, map]);

  return null;
}

export default function EnglandCountiesMap({
  correctCountyName,
  className,
}: EnglandCountiesMapProps) {
  const state = useCountydleGameStore();
  return (
    <ControlledEnglandCountiesMap
      className={className}
      correctCountyName={correctCountyName || state.correctEntity?.name}
      interaction={{
        entityMarkings: state.entityMarkings,
        activeMarkerColor: state.activeMarkerColor,
        setActiveMarkerColor: state.setActiveMarkerColor,
        handleEntityMapClick: state.handleEntityMapClick,
        clearMapMarkings: state.clearMapMarkings,
        isGameOver: !!state.gameState?.is_game_over,
      }}
    />
  );
}

export function ControlledEnglandCountiesMap({
  correctCountyName,
  className,
  onCountyClick,
  interaction,
}: EnglandCountiesMapProps & { interaction: MapInteractionState }) {
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData(
    '/england-counties.geojson'
  );
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);

  const {
    entityMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    clearMapMarkings,
    isGameOver,
  } = interaction;
  const revealedName = isGameOver ? correctCountyName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onCountyClick });
  useLayoutEffect(() => {
    current.current = { interaction, revealedName, onCountyClick };
  }, [interaction, revealedName, onCountyClick]);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);

  const getStyleFromState = useCallback(
    (
      feature: Feature | undefined,
      markings: Record<string, MapMarkerColor>,
      currentCorrect?: string
    ): PathOptions => {
      const rawName = getCountyName(feature);
      if (!rawName) return {};

      const name = rawName.toUpperCase();
      const isCorrect = currentCorrect ? name === currentCorrect.toUpperCase() : false;
      const marker = markings[name];

      if (isCorrect) return MAP_THEME.countries.correct;
      if (marker) return MAP_THEME.countries.markers[marker];
      return MAP_THEME.countries.available;
    },
    []
  );

  const getStyle = useCallback(
    (feature: Feature | undefined) =>
      getStyleFromState(
        feature,
        current.current.interaction.entityMarkings,
        current.current.revealedName
      ),
    [getStyleFromState]
  );

  const hoverLayerRef = useRef<L.GeoJSON | null>(null);
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
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((item) => {
        const layer = item as FeatureLayer;
        const feature = layer.feature;
        if (feature) {
          const newStyle = getStyleFromState(feature, entityMarkings, revealedName);
          layer.setStyle(newStyle);

          if (
            revealedName &&
            getCountyName(feature).toUpperCase() === revealedName.toUpperCase()
          ) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData, getStyleFromState]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = getCountyName(feature);
    if (!name) return;

    layer.on({
      click: () => {
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), false);
        current.current.onCountyClick?.(name);
      },
      contextmenu: (e: L.LeafletMouseEvent) => {
        e.originalEvent?.preventDefault?.();
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), true);
      },
      mouseover: () => {
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
      },
    });

    layer.bindTooltip(name, {
      sticky: false,
      direction: 'auto',
      opacity: 0.95,
    });
  };

  const handleZoomToCorrect = () => {
    const targetName = revealedName;
    if (map && targetName && geoJsonData) {
      const correctFeature = geoJsonData.features.find(
        (f) => getCountyName(f).toUpperCase() === targetName.toUpperCase()
      );
      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          focusMapBounds(map, bounds);
        }
      }
    }
  };

  if (!geoJsonData) {
    return (
      <MapLoading
        className={
          className ??
          'border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'
        }
        error={mapError}
        onRetry={retryMap}
      />
    );
  }

  return (
    <div
      className={`w-full overflow-hidden relative ${
        className
          ? className
          : 'bg-[var(--map-ocean)] border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'
      }`}
      style={MAP_THEME_CSS_VARIABLES as CSSProperties}
    >
      <style>{`
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
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
        onReset={() => {
          if (map) resetMapView(map, ENGLAND_CENTER, ENGLAND_ZOOM);
        }}
        className={revealedName ? 'max-md:!top-[8.25rem]' : 'max-md:!top-[5.75rem]'}
      />
      {revealedName && (
        <div className="absolute top-[5.75rem] left-[12px] md:top-[5.25rem] z-[1050]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to correct county"
            aria-label="Zoom to correct county"
          >
            <Check size={16} />
          </button>
        </div>
      )}

      <MapContainer
        className="antique-map-surface"
        center={ENGLAND_CENTER}
        zoom={ENGLAND_ZOOM}
        style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor }}
        minZoom={5}
        maxZoom={11}
        maxBounds={EARTH_PAN_BOUNDS}
        maxBoundsViscosity={0}
        worldCopyJump={false}
        attributionControl={false}
        wheelDebounceTime={40}
        wheelPxPerZoomLevel={60}
        zoomSnap={0}
        zoomDelta={0.5}
        doubleClickZoom={!L.Browser.mobile}
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

        <MapController
          correctName={revealedName}
          geoJsonData={geoJsonData}
          isGameOver={isGameOver}
        />
        <MapCartographicTexture />
        <MapPaperEdge bounds={WORLD_SHEET_BOUNDS} />
      </MapContainer>
    </div>
  );
}
