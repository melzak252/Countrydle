import { useTranslation } from 'react-i18next';
import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useUSStatesGameStore, type MapMarkerColor } from '../stores/gameStore';
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

type FeatureLayer = L.Path & { feature?: Feature };

interface USStatesMapProps {
  correctStateName?: string;
  className?: string;
  onStateClick?: (name: string) => void;
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
        f.properties?.name.toUpperCase() === correctName.toUpperCase()
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

export default function USStatesMap({ correctStateName, className }: USStatesMapProps) {
  const state = useUSStatesGameStore();
  return <ControlledUSStatesMap className={className}
    correctStateName={correctStateName || state.correctEntity?.name}
    interaction={{
      entityMarkings: state.entityMarkings,
      activeMarkerColor: state.activeMarkerColor,
      setActiveMarkerColor: state.setActiveMarkerColor,
      handleEntityMapClick: state.handleEntityMapClick,
      clearMapMarkings: state.clearMapMarkings,
      isGameOver: !!state.gameState?.is_game_over,
    }} />;
}

export function ControlledUSStatesMap({
  correctStateName,
  className,
  onStateClick,
  interaction,
}: USStatesMapProps & { interaction: MapInteractionState }) {
  const { data: geoJsonData, error: mapError, retry: retryMap } = useMapData('/us-states.geojson');
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const { entityMarkings, activeMarkerColor, setActiveMarkerColor, clearMapMarkings, isGameOver } = interaction;
  const revealedName = isGameOver ? correctStateName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onStateClick });
  useLayoutEffect(() => {
    current.current = { interaction, revealedName, onStateClick };
  }, [interaction, revealedName, onStateClick]);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<FeatureLayer | null>(null);


  const getStyleFromState = useCallback((feature: Feature | undefined, markings: Record<string, MapMarkerColor>, currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties || !feature.properties.name) return {};

    const name = feature.properties.name.toUpperCase();
    const isCorrect = currentCorrect ? name === currentCorrect.toUpperCase() : false;
    const marker = markings[name];

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
  }, []);

  const getStyle = useCallback((feature: Feature | undefined) => (
    getStyleFromState(feature, current.current.interaction.entityMarkings, current.current.revealedName)
  ), [getStyleFromState]);
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

          if (revealedName && feature.properties?.name.toUpperCase() === revealedName.toUpperCase()) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData, getStyleFromState]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.name;
    
    layer.on({
      click: () => {
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), false);
        current.current.onStateClick?.(name);
      },
      contextmenu: (e: L.LeafletMouseEvent) => {
        e.originalEvent?.preventDefault?.();
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), true);
      },
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
      layer.bindTooltip(`${feature.properties.name}`, {
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
        f.properties?.name.toUpperCase() === targetName.toUpperCase()
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
    return <MapLoading className={className ?? 'border border-zinc-800 rounded-xl shadow-lg h-[400px] md:h-[600px]'} error={mapError} onRetry={retryMap} />;
  }

  return (
    <div className={`w-full overflow-hidden relative ${className ? className : 'bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg h-[400px] md:h-[600px]'}`}>
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
        onReset={() => { if (map) resetMapView(map, [37.8, -96], 4); }}
        className={revealedName ? 'max-md:!top-[10rem]' : 'max-md:!top-[7rem]'}
      />
      {revealedName && (
        <div className="absolute top-[7rem] left-[12px] md:top-[5.25rem] z-[1050]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 h-11 w-11 md:w-8 md:h-8 flex items-center justify-center cursor-pointer"
            title={isPl ? 'Przybliż poprawny stan' : 'Zoom to correct state'}
            aria-label={isPl ? 'Przybliż poprawny stan' : 'Zoom to correct state'}
          >
            <Check size={16} />
          </button>
        </div>
      )}

      <MapContainer 
        center={[37.8, -96]} 
        zoom={4} 
        style={{ height: '100%', width: '100%', background: '#242424' }}
        minZoom={3}
        maxZoom={10}
        attributionControl={false}
        wheelDebounceTime={40}
        wheelPxPerZoomLevel={60}
        zoomSnap={0}
        zoomDelta={0.5}
        doubleClickZoom={!L.Browser.mobile}
        ref={setMap}
        renderer={renderer}
      >
        <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
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

        <MapController correctName={revealedName} geoJsonData={geoJsonData} isGameOver={isGameOver} />
      </MapContainer>
    </div>
  );
}
