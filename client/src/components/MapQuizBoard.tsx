import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { GeoJSON, MapContainer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import { RotateCcw } from 'lucide-react';
import type { MapQuizRoundAnswer, MapQuizScope } from '../types';
import { useMapData } from '../hooks/useMapData';
import { useMapZoomSync } from '../hooks/useMapZoomSync';
import { createMapRenderer } from '../lib/mapRenderer';
import { trackMapZoom } from '../lib/mapView';
import MapLoading from './MapLoading';
import RegionalGeographyCredit from './RegionalGeographyCredit';

type FeatureLayer = L.Path & { feature?: Feature };

interface ScopeMapConfig {
  geojsonUrl: string;
  center: [number, number];
  zoom: number;
  minZoom: number;
  maxZoom: number;
}

const SCOPE_CONFIG: Record<MapQuizScope, ScopeMapConfig> = {
  london_boroughs: {
    geojsonUrl: '/london-boroughs.geojson',
    center: [51.505, -0.11],
    zoom: 10,
    minZoom: 9,
    maxZoom: 13,
  },
  england_counties: {
    geojsonUrl: '/england-counties.geojson',
    center: [52.85, -1.5],
    zoom: 6,
    minZoom: 5,
    maxZoom: 11,
  },
};

export interface MapQuizFeedback {
  targetId: number;
  clickedId: number;
  correct: boolean;
}

interface MapQuizBoardProps {
  scope: MapQuizScope;
  answers: MapQuizRoundAnswer[];
  feedback: MapQuizFeedback | null;
  isCompleted: boolean;
  disabled?: boolean;
  onSelectEntity: (entity: { id: number; name: string }) => void;
  className?: string;
}

function MapBoundsController({
  geoJsonData,
  resetSignal,
  highlightEntityId,
}: {
  geoJsonData: FeatureCollection | null;
  resetSignal: number;
  highlightEntityId: number | null;
}) {
  const map = useMap();
  useMapZoomSync(map);
  useEffect(() => trackMapZoom(map), [map]);

  const fitAll = useCallback(() => {
    if (!geoJsonData) return;
    const bounds = L.geoJSON(geoJsonData).getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [18, 18], animate: false });
    }
  }, [geoJsonData, map]);

  useEffect(() => {
    const container = map.getContainer();
    if (!container) return;
    map.invalidateSize();
    fitAll();

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
  }, [map, fitAll]);

  useEffect(() => {
    if (resetSignal > 0) {
      fitAll();
    }
  }, [resetSignal, fitAll]);

  useEffect(() => {
    if (!highlightEntityId || !geoJsonData) return;
    const feature = geoJsonData.features.find(
      (f) => Number(f.properties?.id) === highlightEntityId,
    );
    if (!feature) return;
    const bounds = L.geoJSON(feature).getBounds();
    if (bounds.isValid()) {
      const targetZoom = Math.min(map.getBoundsZoom(bounds, false, L.point(64, 64)), map.getMaxZoom());
      if (targetZoom > map.getZoom()) {
        map.panTo(bounds.getCenter(), { animate: true, duration: 0.35 });
      }
    }
  }, [highlightEntityId, geoJsonData, map]);

  return null;
}

export default function MapQuizBoard({
  scope,
  answers,
  feedback,
  isCompleted,
  disabled = false,
  onSelectEntity,
  className,
}: MapQuizBoardProps) {
  const config = SCOPE_CONFIG[scope];
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData(config.geojsonUrl);
  const [renderer] = useState(createMapRenderer);
  const [resetSignal, setResetSignal] = useState(0);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);

  const stateRef = useRef({ answers, feedback, isCompleted, disabled, onSelectEntity });
  useLayoutEffect(() => {
    stateRef.current = { answers, feedback, isCompleted, disabled, onSelectEntity };
  }, [answers, feedback, isCompleted, disabled, onSelectEntity]);

  const getStyleFromState = useCallback(
    (
      feature: Feature | undefined,
      currentAnswers: MapQuizRoundAnswer[],
      currentFeedback: MapQuizFeedback | null,
      completed: boolean,
    ): PathOptions => {
      const entityId = Number(feature?.properties?.id);
      if (!Number.isFinite(entityId)) return {};

      if (currentFeedback) {
        if (entityId === currentFeedback.targetId) {
          return currentFeedback.correct
            ? {
                fillColor: '#10b981',
                color: '#6ee7b7',
                weight: 2.5,
                opacity: 1,
                fillOpacity: 0.85,
              }
            : {
                fillColor: '#f59e0b',
                color: '#fde68a',
                weight: 2.5,
                opacity: 1,
                fillOpacity: 0.85,
              };
        }
        if (!currentFeedback.correct && entityId === currentFeedback.clickedId) {
          return {
            fillColor: '#dc2626',
            color: '#fca5a5',
            weight: 2.5,
            opacity: 1,
            fillOpacity: 0.8,
          };
        }
      }

      const prevAnswer = currentAnswers.find((ans) => ans.target_id === entityId);
      if (prevAnswer) {
        if (prevAnswer.correct) {
          return {
            fillColor: '#059669',
            color: '#34d399',
            weight: 1.5,
            opacity: 1,
            fillOpacity: completed ? 0.72 : 0.45,
          };
        }
        return {
          fillColor: '#b45309',
          color: '#fbbf24',
          weight: 1.5,
          opacity: 1,
          fillOpacity: completed ? 0.65 : 0.35,
        };
      }

      return {
        fillColor: '#27272a',
        color: '#a1a1aa',
        weight: 1.1,
        opacity: 0.9,
        fillOpacity: 0.82,
      };
    },
    [],
  );

  const getStyle = useCallback(
    (feature: Feature | undefined) =>
      getStyleFromState(
        feature,
        stateRef.current.answers,
        stateRef.current.feedback,
        stateRef.current.isCompleted,
      ),
    [getStyleFromState],
  );

  useEffect(() => {
    const group = geoJsonLayerRef.current;
    if (!group) return;
    group.eachLayer((item) => {
      const layer = item as FeatureLayer;
      const feature = layer.feature;
      if (!feature) return;
      const entityId = Number(feature.properties?.id);
      const name = String(feature.properties?.name ?? '');
      layer.setStyle(getStyleFromState(feature, answers, feedback, isCompleted));

      if (feedback && (entityId === feedback.targetId || entityId === feedback.clickedId)) {
        layer.bringToFront();
      }

      // Label-free during active rounds; show tooltips only once completed.
      layer.unbindTooltip();
      if (isCompleted && name) {
        layer.bindTooltip(name, {
          sticky: true,
          direction: 'auto',
          opacity: 0.95,
        });
      }
    });
  }, [answers, feedback, isCompleted, geoJsonData, getStyleFromState]);

  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      const entityId = Number(feature.properties?.id);
      const name = String(feature.properties?.name ?? '');

      layer.on({
        click: () => {
          const { disabled: isDisabled, isCompleted: done, onSelectEntity: select } = stateRef.current;
          if (isDisabled || done) return;
          if (Number.isFinite(entityId) && name) {
            select({ id: entityId, name });
          }
        },
        mouseover: () => {
          const l = layer as FeatureLayer;
          if (activeHoverLayerRef.current && activeHoverLayerRef.current !== l) {
            const prev = activeHoverLayerRef.current;
            if (prev.feature) prev.setStyle(getStyle(prev.feature));
          }
          activeHoverLayerRef.current = l;
          if (!stateRef.current.disabled && !stateRef.current.isCompleted) {
            l.setStyle({
              weight: 2.2,
              color: '#f4f4f5',
              fillOpacity: 0.95,
            });
            l.bringToFront();
          }
        },
        mouseout: () => {
          const l = layer as FeatureLayer;
          l.setStyle(getStyle(feature));
          if (activeHoverLayerRef.current === l) {
            activeHoverLayerRef.current = null;
          }
        },
      });
    },
    [getStyle],
  );

  if (!geoJsonData) {
    return (
      <div className="space-y-2">
        <MapLoading
          className={className ?? 'border border-zinc-800 rounded-xl shadow-lg h-[420px] md:h-[560px]'}
          error={mapError}
          onRetry={retryMap}
        />
        <RegionalGeographyCredit scope={scope} />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        className={`w-full overflow-hidden relative ${
          className ?? 'bg-zinc-950 border border-zinc-800 rounded-xl shadow-lg h-[420px] md:h-[560px]'
        }`}
      >
        <style>{`
          .leaflet-interactive:focus { outline: none; }
          .leaflet-tooltip { pointer-events: none !important; }
          .leaflet-top, .leaflet-bottom, .leaflet-control { z-index: 1050 !important; }
        `}</style>

        <div className="absolute top-3 right-3 z-[1050]">
          <button
            type="button"
            onClick={() => setResetSignal((n) => n + 1)}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900/90 px-2.5 py-1.5 text-xs font-medium text-zinc-200 shadow hover:bg-zinc-800 transition-colors cursor-pointer"
            title="Reset map view"
            aria-label="Reset map view"
          >
            <RotateCcw size={14} />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>

        <MapContainer
          key={scope}
          center={config.center}
          zoom={config.zoom}
          minZoom={config.minZoom}
          maxZoom={config.maxZoom}
          style={{ height: '100%', width: '100%', background: '#14161a' }}
          attributionControl={false}
          wheelDebounceTime={40}
          wheelPxPerZoomLevel={60}
          zoomSnap={0.25}
          zoomDelta={0.5}
          doubleClickZoom={!L.Browser.mobile}
          renderer={renderer}
        >
          <GeoJSON
            key={`${scope}-layer`}
            data={geoJsonData}
            style={getStyle}
            onEachFeature={onEachFeature}
            ref={geoJsonLayerRef}
          />
          <MapBoundsController
            geoJsonData={geoJsonData}
            resetSignal={resetSignal}
            highlightEntityId={feedback && !feedback.correct ? feedback.targetId : null}
          />
        </MapContainer>
      </div>
      <RegionalGeographyCredit scope={scope} />
    </div>
  );
}
