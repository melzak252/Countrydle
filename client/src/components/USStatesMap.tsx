import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useUSStatesGameStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check } from 'lucide-react';

interface USStatesMapProps {
  correctStateName?: string;
  className?: string;
}

function MapController({ correctName, geoJsonData }: { correctName?: string, geoJsonData: any }) {
  const map = useMap();
  const { gameState } = useUSStatesGameStore();

  useEffect(() => {
    if (gameState?.is_game_over && correctName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.name.toUpperCase() === correctName.toUpperCase()
      );

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
        }
      }
    }
  }, [gameState?.is_game_over, correctName, geoJsonData, map]);

  return null;
}

export default function USStatesMap({ correctStateName, className }: USStatesMapProps) {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const {
    entityMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    handleEntityMapClick,
    clearMapMarkings,
    gameState,
    correctEntity,
  } = useUSStatesGameStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  
  useEffect(() => {
    fetch('/us-states.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load US states map data', err));
  }, []);

  const getStyleFromState = (feature: any, markings: Record<string, MapMarkerColor>, currentCorrect?: string): PathOptions => {
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
    const { entityMarkings: em, correctEntity: ce, gameState: gs } = useUSStatesGameStore.getState();
    return getStyleFromState(feature, em, gs?.is_game_over ? ce?.name : undefined);
  };

  useEffect(() => {
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((layer: any) => {
        const feature = layer.feature;
        if (feature) {
          const { gameState: gs, correctEntity: ce } = useUSStatesGameStore.getState();
          const newStyle = getStyleFromState(
            feature,
            entityMarkings,
            gs?.is_game_over ? correctStateName || ce?.name : undefined
          );
          layer.setStyle(newStyle);

          if (gs?.is_game_over && (correctStateName || ce?.name) && (feature.properties.name.toUpperCase() === (correctStateName || ce?.name).toUpperCase())) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, gameState?.is_game_over, correctStateName]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.name;
    
    layer.on({
      click: () => {
        handleEntityMapClick(name.toUpperCase(), false);
      },
      contextmenu: (e: any) => {
        e.originalEvent?.preventDefault?.();
        handleEntityMapClick(name.toUpperCase(), true);
      },
      mouseover: (e) => {
        const l = e.target;
        l.setStyle({
          weight: 2,
          fillOpacity: 0.8,
        });
        l.bringToFront();
      },
      mouseout: (e) => {
        const l = e.target;
        const { entityMarkings: em, correctEntity: ce, gameState: gs } = useUSStatesGameStore.getState();
        const style = getStyleFromState(
          feature,
          em,
          gs?.is_game_over ? ce?.name : undefined
        );
        l.setStyle(style);
      }
    });

    if (feature.properties) {
        layer.bindTooltip(`${feature.properties.name}`);
    }
  };

  const handleZoomToCorrect = () => {
    const targetName = correctStateName || correctEntity?.name;
    
    if (map && targetName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.name.toUpperCase() === targetName.toUpperCase()
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
    return <div className="h-[350px] md:h-[500px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">Loading US Map...</div>;
  }

  return (
    <div className={`w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg relative z-0 ${className ? className : 'h-[400px] md:h-[600px]'}`}>
      <style>{`
        .leaflet-interactive:focus {
            outline: none;
        }
      `}</style>
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
      />
      {gameState?.is_game_over && (
        <div className="absolute top-0 left-0 mt-16 md:mt-20 ml-2 md:ml-3 z-[1000]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to Correct State"
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

        <MapController correctName={correctStateName} geoJsonData={geoJsonData} />
      </MapContainer>
    </div>
  );
}
