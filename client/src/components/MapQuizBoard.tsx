import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { GeoJSON, MapContainer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import type { MapQuizRoundAnswer, MapQuizScope } from '../types';
import { useMapData } from '../hooks/useMapData';
import { useMapZoomSync } from '../hooks/useMapZoomSync';
import { createMapRenderer } from '../lib/mapRenderer';
import { trackMapZoom } from '../lib/mapView';
import { bindRegionTooltip, restoreRegionTooltip } from '../lib/mapRegionTooltips';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import { EARTH_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';
import MapLoading from './MapLoading';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';

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
    minZoom: 8,
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
  targetName: string;
  clickedName: string;
  correct: boolean;
}

interface MapQuizBoardProps {
  scope: MapQuizScope;
  answers: MapQuizRoundAnswer[];
  feedback: MapQuizFeedback | null;
  isCompleted: boolean;
  disabled?: boolean;
  resetSignal?: number;
  onSelectEntity: (entity: { id: number; name: string }) => void;
  onRetryMap?: () => void;
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
      map.fitBounds(bounds, {
        paddingTopLeft: [24, 96],
        paddingBottomRight: [24, 24],
        animate: false,
      });
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
  resetSignal = 0,
  onSelectEntity,
  onRetryMap,
  className,
}: MapQuizBoardProps) {
  const config = SCOPE_CONFIG[scope];
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData(config.geojsonUrl);
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const hoverLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);

  const visibleRegionNames = useMemo(() => {
    const names = new Set<string>();
    for (const answer of answers) {
      if (answer.target_name) names.add(answer.target_name);
    }
    if (feedback?.targetName) {
      names.add(feedback.targetName);
    }
    return Array.from(names);
  }, [answers, feedback]);

  const hideUnlistedTooltips = !isCompleted;

  const stateRef = useRef({
    answers,
    feedback,
    isCompleted,
    disabled,
    onSelectEntity,
    visibleRegionNames,
    hideUnlistedTooltips,
  });
  useLayoutEffect(() => {
    stateRef.current = {
      answers,
      feedback,
      isCompleted,
      disabled,
      onSelectEntity,
      visibleRegionNames,
      hideUnlistedTooltips,
    };
  }, [answers, feedback, isCompleted, disabled, onSelectEntity, visibleRegionNames, hideUnlistedTooltips]);

  const getStyleFromState = useCallback(
    (
      feature: Feature | undefined,
      currentAnswers: MapQuizRoundAnswer[],
      currentFeedback: MapQuizFeedback | null,
    ): PathOptions => {
      const entityId = Number(feature?.properties?.id);
      if (!Number.isFinite(entityId)) return MAP_THEME.countries.available;

      if (currentFeedback) {
        if (entityId === currentFeedback.targetId) {
          return MAP_THEME.countries.correct;
        }
        if (!currentFeedback.correct && entityId === currentFeedback.clickedId) {
          return MAP_THEME.countries.markers.red;
        }
      }

      const prevAnswer = currentAnswers.find((ans) => ans.target_id === entityId);
      if (prevAnswer) {
        return prevAnswer.correct
          ? MAP_THEME.countries.markers.green
          : MAP_THEME.countries.markers.red;
      }

      return MAP_THEME.countries.available;
    },
    [],
  );

  const getStyle = useCallback(
    (feature: Feature | undefined) =>
      getStyleFromState(
        feature,
        stateRef.current.answers,
        stateRef.current.feedback,
      ),
    [getStyleFromState],
  );

  // Separate SVG hover overlay matching PowiatyMap and USStatesMap
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
        const prev = activeHoverLayerRef.current;
        const name = prev.feature?.properties?.name;
        if (typeof name === 'string') {
          restoreRegionTooltip(
            prev,
            name,
            currentVisibleNames(),
          );
        } else {
          prev.closeTooltip?.();
        }
        activeHoverLayerRef.current = null;
      }
    };

    const currentVisibleNames = () => stateRef.current.visibleRegionNames;
    map.on('mouseout', onMapMouseOut);
    return () => {
      map.off('mouseout', onMapMouseOut);
      hoverLayer.remove();
      hoverLayerRef.current = null;
    };
  }, [map]);

  // Update polygon styles on answer/feedback change
  useEffect(() => {
    const group = geoJsonLayerRef.current;
    if (!group) return;
    group.eachLayer((item) => {
      const layer = item as FeatureLayer;
      const feature = layer.feature;
      if (!feature) return;
      const entityId = Number(feature.properties?.id);
      layer.setStyle(getStyleFromState(feature, answers, feedback));

      if (feedback && (entityId === feedback.targetId || entityId === feedback.clickedId)) {
        layer.bringToFront();
      }
    });
  }, [answers, feedback, geoJsonData, getStyleFromState]);

  // Update tooltips: label-free during active rounds, revealed on completed/answered polygons
  useEffect(() => {
    const group = geoJsonLayerRef.current;
    if (!group) return;
    group.eachLayer((item) => {
      const layer = item as FeatureLayer;
      const name = layer.feature?.properties?.name;
      if (typeof name !== 'string' || !name) return;
      bindRegionTooltip(layer, name, hideUnlistedTooltips, visibleRegionNames);
    });
  }, [geoJsonData, hideUnlistedTooltips, visibleRegionNames]);

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
          const activeLayer = layer as FeatureLayer;
          if (activeHoverLayerRef.current && activeHoverLayerRef.current !== activeLayer) {
            const previous = activeHoverLayerRef.current;
            const previousName = previous.feature?.properties?.name;
            if (typeof previousName === 'string') {
              restoreRegionTooltip(previous, previousName, stateRef.current.visibleRegionNames);
            } else {
              previous.closeTooltip?.();
            }
          }
          activeHoverLayerRef.current = activeLayer;
          if (hoverLayerRef.current) {
            hoverLayerRef.current.clearLayers();
            hoverLayerRef.current.addData(feature);
          }
          activeLayer.openTooltip?.();
        },
        mouseout: () => {
          const activeLayer = layer as FeatureLayer;
          if (name) {
            restoreRegionTooltip(activeLayer, name, stateRef.current.visibleRegionNames);
          } else {
            activeLayer.closeTooltip?.();
          }
          if (activeHoverLayerRef.current === activeLayer) {
            hoverLayerRef.current?.clearLayers();
            activeHoverLayerRef.current = null;
          }
        },
      });

      if (name) {
        bindRegionTooltip(
          layer,
          name,
          stateRef.current.hideUnlistedTooltips,
          stateRef.current.visibleRegionNames,
        );
      }
    },
    [],
  );

  if (!geoJsonData) {
    return (
      <MapLoading
        className={
          className ??
          'border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'
        }
        error={mapError}
        onRetry={onRetryMap ?? retryMap}
      />
    );
  }

  return (
    <div
      className={`w-full overflow-hidden relative ${
        className ??
        'bg-[var(--map-ocean)] border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'
      }`}
      style={MAP_THEME_CSS_VARIABLES as CSSProperties}
    >
      <style>{`
        .leaflet-interactive:focus {
          outline: none;
        }
        .leaflet-interactive:focus-visible {
          outline: 3px solid #f59e0b;
          outline-offset: 2px;
        }
        .leaflet-tooltip {
          pointer-events: none !important;
        }
        .leaflet-top, .leaflet-bottom, .leaflet-control {
          z-index: 1050 !important;
        }
      `}</style>

      <MapContainer
        key={scope}
        className="antique-map-surface"
        center={config.center}
        zoom={config.zoom}
        minZoom={config.minZoom}
        maxZoom={config.maxZoom}
        maxBounds={EARTH_PAN_BOUNDS}
        maxBoundsViscosity={0}
        worldCopyJump={false}
        style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor }}
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
        <MapCartographicTexture />
        <MapPaperEdge bounds={WORLD_SHEET_BOUNDS} />
      </MapContainer>
    </div>
  );
}
