import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useWojewodztwaGameStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check } from 'lucide-react';
import type { MapInteractionState } from '../lib/mapMarkings';

interface WojewodztwaMapProps {
  correctWojewodztwoName?: string;
  className?: string;
  onWojewodztwoClick?: (name: string) => void;
}

function MapController({ correctName, geoJsonData, isGameOver }: { correctName?: string, geoJsonData: FeatureCollection | null, isGameOver: boolean }) {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    if (!container) return;
    map.invalidateSize();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [map]);

  useEffect(() => {
    if (isGameOver && correctName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.nazwa.toUpperCase() === correctName.toUpperCase()
      );

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
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
  const [geoJsonData, setGeoJsonData] = useState<FeatureCollection | null>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const { entityMarkings, activeMarkerColor, setActiveMarkerColor, clearMapMarkings, isGameOver } = interaction;
  const revealedName = isGameOver ? correctWojewodztwoName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onWojewodztwoClick });
  current.current = { interaction, revealedName, onWojewodztwoClick };
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<L.Layer | null>(null);

  useEffect(() => {
    if (!map) return;
    const onMapMouseOut = () => {
      if (activeHoverLayerRef.current) {
        const prev = activeHoverLayerRef.current as any;
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
  }, [map]);
  useEffect(() => {
    fetch('/wojewodztwa.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load wojewodztwa map data', err));
  }, []);

  const getStyleFromState = (feature: any, markings: Record<string, MapMarkerColor>, currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties || !feature.properties.nazwa) return {};

    const name = feature.properties.nazwa.toUpperCase();
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
        weight: 2,
        opacity: 1,
        color: '#6ee7b7',
        fillOpacity: 0.65,
      };
    }

    if (marker === 'red') {
      return {
        fillColor: '#18181b',
        weight: 1.5,
        opacity: 0.8,
        color: '#f43f5e',
        dashArray: '3, 4',
        fillOpacity: 0.85,
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

  const getStyle = (feature: any) => {
    return getStyleFromState(feature, current.current.interaction.entityMarkings, current.current.revealedName);
  };

  useEffect(() => {
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((layer: any) => {
        const feature = layer.feature;
        if (feature) {
          const newStyle = getStyleFromState(
            feature,
            entityMarkings,
            revealedName
          );
          layer.setStyle(newStyle);

          if (revealedName && feature.properties.nazwa.toUpperCase() === revealedName.toUpperCase()) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.nazwa;
    
    layer.on({
      click: () => {
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), false);
        current.current.onWojewodztwoClick?.(name);
      },
      contextmenu: (e: any) => {
        e.originalEvent?.preventDefault?.();
        current.current.interaction.handleEntityMapClick(name.toUpperCase(), true);
      },
      mouseover: (e: any) => {
        const l = e.target;
        if (activeHoverLayerRef.current && activeHoverLayerRef.current !== l) {
          const prev = activeHoverLayerRef.current as any;
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
      mouseout: (e: any) => {
        const l = e.target;
        const style = getStyle(feature);
        l.setStyle(style);
        l.closeTooltip?.();
        if (activeHoverLayerRef.current === l) {
          activeHoverLayerRef.current = null;
        }
      }
    });

    if (feature.properties) {
      layer.bindTooltip(`${feature.properties.nazwa}`, {
        sticky: true,
        direction: 'auto',
        opacity: 0.95,
      });
    }
  };

  const handleZoomToCorrect = () => {
    const targetName = revealedName;
    
    if (map && targetName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.nazwa.toUpperCase() === targetName.toUpperCase()
      );

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
        }
      }
    }
  };

  if (!geoJsonData) {
    return <div className="h-[350px] md:h-[500px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">Loading voivodeship map...</div>;
  }

  return (
    <div className={`w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg relative z-0 ${className ? className : 'h-[400px] md:h-[600px]'}`}>
      <style>{`
        .leaflet-interactive:focus {
            outline: none;
        }
        .leaflet-tooltip {
            pointer-events: none !important;
        }
      `}</style>
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
      />
      {revealedName && (
        <div className="absolute top-0 left-0 mt-16 md:mt-20 ml-2 md:ml-3 z-[1000]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to correct voivodeship"
          >
            <Check size={16} />
          </button>
        </div>
      )}

      <MapContainer 
        center={[52.065, 19.48]} 
        zoom={6} 
        style={{ height: '100%', width: '100%', background: '#242424' }}
        minZoom={5}
        maxZoom={10}
        attributionControl={false}
        ref={setMap}
      >
        <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
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
