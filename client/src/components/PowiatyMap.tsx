
import { useState, useEffect, useLayoutEffect, useRef, useCallback, type CSSProperties } from 'react';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { usePowiatyGameStore, type MapMarkerColor } from '../stores/gameStore';
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
import {
  bindMapRegionHintAccessibility,
  bindRegionTooltip,
  getRegionHint,
  restoreRegionTooltip,
  routeMapRegionActivation,
} from '../lib/mapRegionTooltips';
import { normalizeMapRegionName } from '../lib/mapGameMode';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';
import { POLAND_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';

type FeatureLayer = L.Path & { feature?: Feature };
const EMPTY_REGION_NAMES: readonly string[] = [];

const EMPTY_REGION_HINTS: Readonly<Record<string, string>> = {};

interface PowiatyMapProps {
  correctPowiatName?: string;
  className?: string;
  onPowiatClick?: (name: string) => void;
  hideUnlistedTooltips?: boolean;
  visibleRegionNames?: readonly string[];
  showMapToolbar?: boolean;
  onRetryMap?: () => void;
  regionHints?: Readonly<Record<string, string>>;
  activeHintName?: string | null;
  onHintOpen?: (name: string) => void;
  onHintClose?: (name: string) => void;
}

function MapController({ correctName, geoJsonData, isGameOver }: { correctName?: string, geoJsonData: FeatureCollection | null, isGameOver: boolean }) {
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
      const correctFeature = geoJsonData.features.find((f) =>
        f.properties?.nazwa.toUpperCase() === correctName.toUpperCase()
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

export default function PowiatyMap({ correctPowiatName, className }: PowiatyMapProps) {
  const state = usePowiatyGameStore();
  return <ControlledPowiatyMap className={className}
    correctPowiatName={correctPowiatName || state.correctEntity?.nazwa}
    interaction={{
      entityMarkings: state.entityMarkings,
      activeMarkerColor: state.activeMarkerColor,
      setActiveMarkerColor: state.setActiveMarkerColor,
      handleEntityMapClick: state.handleEntityMapClick,
      clearMapMarkings: state.clearMapMarkings,
      isGameOver: !!state.gameState?.is_game_over,
    }} />;
}

export function ControlledPowiatyMap({
  correctPowiatName,
  className,
  onPowiatClick,
  interaction,
  hideUnlistedTooltips = false,
  visibleRegionNames = EMPTY_REGION_NAMES,
  regionHints = EMPTY_REGION_HINTS,
  activeHintName = null,
  onHintOpen,
  onHintClose,
  showMapToolbar = true,
  onRetryMap,
}: PowiatyMapProps & { interaction: MapInteractionState }) {
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData('/powiaty-min.geojson');
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  
  
  const { entityMarkings, activeMarkerColor, setActiveMarkerColor, clearMapMarkings, isGameOver } = interaction;
  const revealedName = isGameOver ? correctPowiatName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({
    interaction,
    revealedName,
    onPowiatClick,
    hideUnlistedTooltips,
    visibleRegionNames,
    regionHints,
    activeHintName,
    onHintOpen,
    onHintClose,
  });
  useLayoutEffect(() => {
    current.current = {
      interaction,
      revealedName,
      onPowiatClick,
      hideUnlistedTooltips,
      visibleRegionNames,
      regionHints,
      activeHintName,
      onHintOpen,
      onHintClose,
    };
  }, [
    interaction,
    revealedName,
    onPowiatClick,
    hideUnlistedTooltips,
    visibleRegionNames,
    regionHints,
    activeHintName,
    onHintOpen,
    onHintClose,
  ]);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);
  const hintAccessibilityCleanup = useRef(new WeakMap<L.Layer, () => void>());
  const bindHintAccessibility = useCallback((layer: FeatureLayer, name: string) => {
    const existingCleanup = hintAccessibilityCleanup.current.get(layer);
    if (!current.current.hideUnlistedTooltips) {
      existingCleanup?.();
      hintAccessibilityCleanup.current.delete(layer);
      return;
    }

    const attach = () => {
      const path = layer.getElement();
      if (!path) return;
      hintAccessibilityCleanup.current.get(layer)?.();
      const hint = getRegionHint(name, current.current.regionHints);
      const cleanup = bindMapRegionHintAccessibility(
        path,
        name,
        hint,
        (regionName) => {
          current.current.onHintOpen?.(regionName);
          layer.openTooltip?.();
        },
        (regionName) => {
          current.current.onHintClose?.(regionName);
          layer.closeTooltip?.();
        },
      );
      hintAccessibilityCleanup.current.set(layer, cleanup);
    };

    if (layer.getElement()) attach();
    else layer.once('add', attach);
  }, []);


  const getStyleFromState = useCallback((feature: Feature | undefined, markings: Record<string, MapMarkerColor>, currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties) return {};

    const name = (feature.properties.nazwa || '').toUpperCase();
    const isCorrect = currentCorrect ? name === currentCorrect.toUpperCase() : false;
    const marker = markings[name];

    if (isCorrect) return MAP_THEME.countries.correct;
    if (marker) return MAP_THEME.countries.markers[marker];
    return MAP_THEME.countries.available;
  }, []);

  const getStyle = useCallback((feature: Feature | undefined) => (
    getStyleFromState(feature, current.current.interaction.entityMarkings, current.current.revealedName)
  ), [getStyleFromState]);
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
        const prev = activeHoverLayerRef.current;
        const name = prev.feature?.properties?.nazwa;
        if (typeof name === 'string') {
          restoreRegionTooltip(
            prev,
            name,
            current.current.visibleRegionNames,
            getRegionHint(name, current.current.regionHints),
            current.current.activeHintName,
          );
        }
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
          const newStyle = getStyleFromState(
            feature,
            entityMarkings,
            revealedName
          );
          layer.setStyle(newStyle);

          if (revealedName && (feature.properties?.nazwa || '').toUpperCase() === revealedName.toUpperCase()) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData, getStyleFromState]);
  useEffect(() => {
    geoJsonLayerRef.current?.eachLayer((item) => {
      const layer = item as FeatureLayer;
      const name = layer.feature?.properties?.nazwa;
      if (typeof name !== 'string') return;
      const hint = getRegionHint(name, regionHints);
      bindRegionTooltip(layer, name, hideUnlistedTooltips, visibleRegionNames, hint);
      bindHintAccessibility(layer, name);
      if (hint && activeHintName && normalizeMapRegionName(activeHintName) === normalizeMapRegionName(name)) {
        layer.openTooltip?.();
      } else if (hint) {
        layer.closeTooltip?.();
      }
    });
  }, [geoJsonData, hideUnlistedTooltips, visibleRegionNames, regionHints, activeHintName, bindHintAccessibility]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.nazwa;

    layer.on({
      click: () => {
        if (typeof name !== 'string') return;
        routeMapRegionActivation(
          name,
          current.current.visibleRegionNames,
          (regionName) => {
            if (!getRegionHint(regionName, current.current.regionHints)) return;
            current.current.onHintOpen?.(regionName);
            layer.openTooltip?.();
          },
          (regionName) => {
            if (current.current.activeHintName) {
              current.current.onHintClose?.(current.current.activeHintName);
            }
            current.current.interaction.handleEntityMapClick(regionName.toUpperCase(), false);
            current.current.onPowiatClick?.(regionName);
          },
        );
      },
      contextmenu: (event: L.LeafletMouseEvent) => {
        event.originalEvent?.preventDefault?.();
        current.current.interaction.handleEntityMapClick((name || '').toUpperCase(), true);
      },
      mouseover: () => {
        const activeLayer = layer as FeatureLayer;
        if (activeHoverLayerRef.current && activeHoverLayerRef.current !== activeLayer) {
          const previous = activeHoverLayerRef.current;
          const previousName = previous.feature?.properties?.nazwa;
          if (typeof previousName === 'string') {
            restoreRegionTooltip(
              previous,
              previousName,
              current.current.visibleRegionNames,
              getRegionHint(previousName, current.current.regionHints),
              current.current.activeHintName,
            );
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
        if (typeof name === 'string') {
          restoreRegionTooltip(
            activeLayer,
            name,
            current.current.visibleRegionNames,
            getRegionHint(name, current.current.regionHints),
            current.current.activeHintName,
          );
        } else {
          activeLayer.closeTooltip?.();
        }
        if (activeHoverLayerRef.current === activeLayer) {
          hoverLayerRef.current?.clearLayers();
          activeHoverLayerRef.current = null;
        }
      },
    });

    if (typeof name === 'string') {
      const featureLayer = layer as FeatureLayer;
      bindRegionTooltip(
        layer,
        name,
        current.current.hideUnlistedTooltips,
        current.current.visibleRegionNames,
        getRegionHint(name, current.current.regionHints),
      );
      bindHintAccessibility(featureLayer, name);
    }
  };

  const handleZoomToCorrect = () => {
    const targetName = revealedName;
    
    if (map && targetName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f) =>
        f.properties?.nazwa.toUpperCase() === targetName.toUpperCase()
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
    return <MapLoading className={className ?? 'border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'} error={mapError} onRetry={onRetryMap ?? retryMap} />;
  }

  return (
    <div className={`w-full overflow-hidden relative ${className ? className : 'bg-[var(--map-ocean)] border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'}`} style={MAP_THEME_CSS_VARIABLES as CSSProperties}>
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
      {showMapToolbar && (
        <MapToolbar
          activeColor={activeMarkerColor}
          onColorChange={setActiveMarkerColor}
          onClear={clearMapMarkings}
          onReset={() => { if (map) resetMapView(map, [52.065, 19.48], 6); }}
          className={revealedName ? 'max-md:!top-[8.25rem]' : 'max-md:!top-[5.75rem]'}
        />
      )}
      {revealedName && (
        <div className="absolute top-[5.75rem] left-[12px] md:top-[5.25rem] z-[1050]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title={'Zoom to correct county'}
            aria-label={'Zoom to correct county'}
          >
            <Check size={16} />
          </button>
        </div>
      )}

      <MapContainer 
        className="antique-map-surface"
        center={[52.065, 19.48]} 
        zoom={6} 
        style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor }}
        minZoom={5}
        maxZoom={12}
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

        <MapController correctName={revealedName} geoJsonData={geoJsonData} isGameOver={isGameOver} />
        <MapCartographicTexture />
        <MapPaperEdge bounds={WORLD_SHEET_BOUNDS} />
      </MapContainer>
    </div>
  );
}
