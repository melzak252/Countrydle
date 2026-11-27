import { useState, useEffect, useLayoutEffect, useRef, useCallback, type CSSProperties } from 'react';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import { RotateCcw } from 'lucide-react';
import { useMapData } from '../hooks/useMapData';
import { useMapZoomSync } from '../hooks/useMapZoomSync';
import MapLoading from './MapLoading';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';
import { focusMapBounds, resetMapView, trackMapZoom } from '../lib/mapView';
import { createMapRenderer } from '../lib/mapRenderer';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import { POLAND_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';
import { normalizePowiatKey, type PlatesQuizPowiat } from '../lib/platesQuiz';

type FeatureLayer = L.Path & { feature?: Feature };

const POLAND_CENTER: [number, number] = [52.065, 19.48];
const POLAND_ZOOM = 6;

interface PowiatPlatesMapProps {
  catalogByName: Map<string, PlatesQuizPowiat>;
  solvedIds: ReadonlySet<number>;
  lastSolvedIds: readonly number[];
  isGivenUp: boolean;
  focusedPowiatName?: string | null;
  className?: string;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function PlatesMapController({
  geoJsonData,
  focusedPowiatName,
}: {
  geoJsonData: FeatureCollection | null;
  focusedPowiatName?: string | null;
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
    if (!focusedPowiatName || !geoJsonData) return;
    const key = normalizePowiatKey(focusedPowiatName);
    const feature = geoJsonData.features.find(
      (f) => normalizePowiatKey(String(f.properties?.nazwa ?? '')) === key,
    );
    if (!feature) return;
    const layer = L.geoJSON(feature);
    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      focusMapBounds(map, bounds);
    }
  }, [focusedPowiatName, geoJsonData, map]);

  return null;
}

export default function PowiatPlatesMap({
  catalogByName,
  solvedIds,
  lastSolvedIds,
  isGivenUp,
  focusedPowiatName,
  className,
}: PowiatPlatesMapProps) {
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData('/powiaty-min.geojson');
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);

  const lastSolvedSet = new Set(lastSolvedIds);

  // Leaflet retains handlers from layer creation; refs keep them synced with latest React props.
  const currentRef = useRef({
    catalogByName,
    solvedIds,
    lastSolvedSet,
    isGivenUp,
  });
  useLayoutEffect(() => {
    currentRef.current = {
      catalogByName,
      solvedIds,
      lastSolvedSet,
      isGivenUp,
    };
  }, [catalogByName, solvedIds, lastSolvedSet, isGivenUp]);

  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);

  const getPowiatForFeature = useCallback(
    (feature: Feature | undefined, byName: Map<string, PlatesQuizPowiat>) => {
      const rawName = feature?.properties?.nazwa;
      if (!rawName) return undefined;
      return byName.get(normalizePowiatKey(String(rawName)));
    },
    [],
  );

  const getStyleFromState = useCallback(
    (
      feature: Feature | undefined,
      byName: Map<string, PlatesQuizPowiat>,
      solved: ReadonlySet<number>,
      recent: ReadonlySet<number>,
      givenUp: boolean,
    ): PathOptions => {
      const powiat = getPowiatForFeature(feature, byName);
      if (!powiat) {
        return {
          ...MAP_THEME.countries.available,
          weight: 0.6,
        };
      }

      if (recent.has(powiat.id)) {
        return {
          ...MAP_THEME.countries.correct,
          weight: 1.4,
          fillOpacity: 0.9,
        };
      }

      if (solved.has(powiat.id)) {
        return {
          ...MAP_THEME.countries.correct,
          weight: 0.65,
          fillOpacity: 0.76,
        };
      }

      if (givenUp) {
        return {
          ...MAP_THEME.countries.markers.red,
          weight: 0.65,
          fillOpacity: 0.55,
        };
      }

      return {
        ...MAP_THEME.countries.available,
        weight: 0.6,
      };
    },
    [getPowiatForFeature],
  );

  const getStyle = useCallback(
    (feature: Feature | undefined) => {
      const { catalogByName: byName, solvedIds: solved, lastSolvedSet: recent, isGivenUp: givenUp } =
        currentRef.current;
      return getStyleFromState(feature, byName, solved, recent, givenUp);
    },
    [getStyleFromState],
  );

  const buildTooltipHtml = useCallback(
    (powiat: PlatesQuizPowiat | undefined, solved: ReadonlySet<number>, givenUp: boolean): string | null => {
      if (!powiat) return null;
      const isSolved = solved.has(powiat.id);
      if (!isSolved && !givenUp) {
        // Strictly hide unsolved powiat names and plate codes during active play.
        return null;
      }
      const platesText = powiat.registration_plates.join(', ');
      return `<div style="font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.3;">
        <div style="font-weight: 700; color: ${isSolved ? '#6ee7b7' : '#fda4af'};">${escapeHtml(powiat.name)}</div>
        <div style="font-family: ui-monospace, monospace; font-size: 11px; margin-top: 2px; color: #e4e4e7;">${escapeHtml(platesText)}</div>
      </div>`;
    },
    [],
  );

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

  // Sync polygon styles and tooltips whenever solvedIds, lastSolvedIds, or isGivenUp change.
  useEffect(() => {
    if (!geoJsonLayerRef.current) return;
    const recentSet = new Set(lastSolvedIds);
    geoJsonLayerRef.current.eachLayer((item) => {
      const layer = item as FeatureLayer;
      const feature = layer.feature;
      if (!feature) return;

      const style = getStyleFromState(feature, catalogByName, solvedIds, recentSet, isGivenUp);
      layer.setStyle(style);

      const powiat = getPowiatForFeature(feature, catalogByName);
      if (powiat && recentSet.has(powiat.id)) {
        layer.bringToFront();
      }

      const tooltipHtml = buildTooltipHtml(powiat, solvedIds, isGivenUp);
      if (tooltipHtml) {
        if (layer.getTooltip()) {
          layer.setTooltipContent(tooltipHtml);
        } else {
          layer.bindTooltip(tooltipHtml, {
            sticky: true,
            direction: 'auto',
            opacity: 0.96,
            className: 'plates-map-tooltip',
          });
        }
      } else if (layer.getTooltip()) {
        layer.unbindTooltip();
      }
    });
  }, [catalogByName, solvedIds, lastSolvedIds, isGivenUp, geoJsonData, getStyleFromState, getPowiatForFeature, buildTooltipHtml]);

  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      layer.on({
        mouseover: () => {
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
            fillOpacity: 0.9,
          });
          if (l.getTooltip()) {
            l.openTooltip?.();
          }
        },
        mouseout: () => {
          const l = layer as FeatureLayer;
          l.setStyle(getStyle(feature));
          l.closeTooltip?.();
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
      <MapLoading
        className={className ?? 'border border-white/10 rounded-xl shadow-lg h-[440px] md:h-[580px]'}
        error={mapError}
        onRetry={retryMap}
      />
    );
  }

  return (
    <div
      className={`w-full overflow-hidden relative ${
        className ? className : 'bg-zinc-900 border border-white/10 rounded-xl shadow-lg h-[440px] md:h-[580px]'
      }`}
    >
      <style>{`
        .leaflet-interactive:focus {
          outline: none;
        }
        .leaflet-tooltip {
          pointer-events: none !important;
        }
        .plates-map-tooltip {
          background: rgba(10, 12, 16, 0.94) !important;
          border: 1px solid rgba(255, 255, 255, 0.16) !important;
          border-radius: 6px !important;
          padding: 6px 9px !important;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45) !important;
        }
        .plates-map-tooltip::before {
          display: none !important;
        }
        .leaflet-top, .leaflet-bottom, .leaflet-control {
          z-index: 500 !important;
        }
      `}</style>

      <div className="absolute top-3 right-3 z-[500]">
        <button
          type="button"
          onClick={() => {
            if (map) resetMapView(map, POLAND_CENTER, POLAND_ZOOM);
          }}
          title="Reset map view"
          aria-label="Reset map view"
          className="inline-flex h-9 w-9 items-center justify-center rounded-sm border border-app-border bg-app-surface/95 text-app-text shadow-md hover:border-app-accent hover:text-app-accent transition-colors cursor-pointer"
        >
          <RotateCcw size={15} />
        </button>
      </div>

      <MapContainer
        className="antique-map-surface"
        center={POLAND_CENTER}
        zoom={POLAND_ZOOM}
        style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor, ...(MAP_THEME_CSS_VARIABLES as CSSProperties) }}
        minZoom={5}
        maxZoom={11}
        maxBounds={POLAND_PAN_BOUNDS}
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

        <PlatesMapController geoJsonData={geoJsonData} focusedPowiatName={focusedPowiatName} />
        <MapCartographicTexture />
        <MapPaperEdge bounds={WORLD_SHEET_BOUNDS} />
      </MapContainer>
    </div>
  );
}
