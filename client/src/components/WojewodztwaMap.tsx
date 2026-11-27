
import { useState, useEffect, useLayoutEffect, useRef, useCallback, type CSSProperties } from 'react';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useWojewodztwaGameStore, type MapMarkerColor } from '../stores/gameStore';
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
import { getRegionFeatureStyle, MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import MapCartographicTexture from './MapCartographicTexture';
import MapPaperEdge from './MapPaperEdge';
import ParchmentWorldBackdrop from './ParchmentWorldBackdrop';
import { POLAND_PAN_BOUNDS, WORLD_SHEET_BOUNDS } from '../lib/mapBounds';

type FeatureLayer = L.Path & { feature?: Feature };

interface WojewodztwaMapProps {
  correctWojewodztwoName?: string;
  className?: string;
  onWojewodztwoClick?: (name: string) => void;
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

export default function WojewodztwaMap({ correctWojewodztwoName, className }: WojewodztwaMapProps) {
  const state = useWojewodztwaGameStore();
  return <ControlledWojewodztwaMap className={className}
    correctWojewodztwoName={correctWojewodztwoName || state.correctEntity?.nazwa}
    interaction={{
      entityMarkings: state.entityMarkings,
      autoEntityMarkings: state.autoEntityMarkings,
      showAutoMarkings: state.showAutoMarkings,
      onToggleAutoMarkings: state.toggleAutoMarkings,
      activeMarkerColor: state.activeMarkerColor,
      setActiveMarkerColor: state.setActiveMarkerColor,
      handleEntityMapClick: state.handleEntityMapClick,
      clearMapMarkings: state.clearMapMarkings,
      isGameOver: !!state.gameState?.is_game_over,
    }} />;
}

export function ControlledWojewodztwaMap({
  correctWojewodztwoName,
  className,
  onWojewodztwoClick,
  interaction,
}: WojewodztwaMapProps & { interaction: MapInteractionState }) {
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData('/wojewodztwa.geojson');
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  
  
  const {
    entityMarkings,
    autoEntityMarkings,
    showAutoMarkings = true,
    onToggleAutoMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    clearMapMarkings,
    isGameOver,
  } = interaction;
  const revealedName = isGameOver ? correctWojewodztwoName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onWojewodztwoClick });
  useLayoutEffect(() => {
    current.current = { interaction, revealedName, onWojewodztwoClick };
  }, [interaction, revealedName, onWojewodztwoClick]);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);


  const getStyleFromState = useCallback((
    feature: Feature | undefined,
    markings: Record<string, MapMarkerColor>,
    currentCorrect?: string,
    autoMarkings?: Record<string, MapMarkerColor>,
    showAuto = true,
  ): PathOptions => (
    getRegionFeatureStyle(feature?.properties?.nazwa, markings, currentCorrect, autoMarkings, showAuto)
  ), []);

  const getStyle = useCallback((feature: Feature | undefined) => (
    getStyleFromState(
      feature,
      current.current.interaction.entityMarkings,
      current.current.revealedName,
      current.current.interaction.autoEntityMarkings,
      current.current.interaction.showAutoMarkings !== false,
    )
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
          const newStyle = getStyleFromState(
            feature,
            entityMarkings,
            revealedName,
            autoEntityMarkings,
            showAutoMarkings,
          );
          layer.setStyle(newStyle);

          if (revealedName && feature.properties?.nazwa.toUpperCase() === revealedName.toUpperCase()) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, autoEntityMarkings, showAutoMarkings, revealedName, geoJsonData, getStyleFromState]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.nazwa;
    
    layer.on({
      click: () => {
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), false);
        current.current.onWojewodztwoClick?.(name);
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
      }
    });

    if (feature.properties) {
      layer.bindTooltip(`${feature.properties.nazwa}`, {
        sticky: false,
        direction: 'auto',
        opacity: 0.95,
      });
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
    return <MapLoading className={className ?? 'border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'} error={mapError} onRetry={retryMap} />;
  }

  return (
    <div className={`w-full overflow-hidden relative ${className ? className : 'bg-[var(--map-ocean)] border border-[var(--map-frame-border)] rounded-xl shadow-lg h-[400px] md:h-[600px]'}`} style={MAP_THEME_CSS_VARIABLES as CSSProperties}>
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
        onReset={() => { if (map) resetMapView(map, [52.065, 19.48], 6); }}
        showAutoMarkings={showAutoMarkings}
        onToggleAutoMarkings={onToggleAutoMarkings}
        className={revealedName ? 'max-md:!top-[8.25rem]' : 'max-md:!top-[5.75rem]'}
      />
      {revealedName && (
        <div className="absolute top-[5.75rem] left-[12px] md:top-[5.25rem] z-[1050]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 h-9 w-9 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title={'Zoom to correct voivodeship'}
            aria-label={'Zoom to correct voivodeship'}
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
        maxZoom={10}
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
