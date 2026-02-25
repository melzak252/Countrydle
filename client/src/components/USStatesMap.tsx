import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useUSStatesGameStore } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import { RotateCcw, Check } from 'lucide-react';

interface USStatesMapProps {
  correctStateName?: string;
  className?: string;
}

function MapController({ correctName, geoJsonData }: { correctName?: string, geoJsonData: any }) {
  const map = useMap();
  const { gameState } = useUSStatesGameStore();

  useEffect(() => {
    if (gameState?.won && correctName && geoJsonData) {
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
  }, [gameState?.won, correctName, geoJsonData, map]);

  return null;
}

export default function USStatesMap({ correctStateName, className }: USStatesMapProps) {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const { selectedEntityNames, toggleEntitySelection, clearSelection, gameState, correctEntity } = useUSStatesGameStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  
  useEffect(() => {
    fetch('/us-states.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load US states map data', err));
  }, []);

  const getStyleFromState = (feature: any, currentSelected: string[], currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties || !feature.properties.name) return {};

    const name = feature.properties.name;
    let isCorrect = false;
    if (currentCorrect) {
        isCorrect = name.toUpperCase() === currentCorrect.toUpperCase();
    }
    const isSelected = currentSelected.includes(name.toUpperCase());

    return {
      fillColor: isCorrect ? '#22cc22' : (isSelected ? '#cc2222' : '#242424'),
      weight: 1,
      opacity: 1,
      color: 'white',
      fillOpacity: 0.7,
    };
  };

  const getStyle = (feature: any) => {
      const { selectedEntityNames, correctEntity, gameState } = useUSStatesGameStore.getState();
      return getStyleFromState(
          feature, 
          selectedEntityNames, 
          gameState?.won ? correctEntity?.name : undefined
      );
  }

  useEffect(() => {
    if (geoJsonLayerRef.current) {
        geoJsonLayerRef.current.eachLayer((layer: any) => {
             const feature = layer.feature;
             if (feature) {
                 const { gameState, correctEntity } = useUSStatesGameStore.getState();
                 const newStyle = getStyleFromState(
                     feature, 
                     selectedEntityNames, 
                      gameState?.won ? correctStateName || correctEntity?.name : undefined
                  );
                 layer.setStyle(newStyle);
                 
                  if (gameState?.won && (correctStateName || correctEntity?.name) && (feature.properties.name.toUpperCase() === (correctStateName || correctEntity?.name).toUpperCase())) {
                      layer.bringToFront();
                  }
             }
        });
    }
  }, [selectedEntityNames, gameState?.won, correctStateName]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.name;
    
    layer.on({
      click: () => {
        toggleEntitySelection(name.toUpperCase());
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
        const { selectedEntityNames: currentSelected, correctEntity, gameState } = useUSStatesGameStore.getState();
        
        const style = getStyleFromState(
            feature, 
            currentSelected, 
            gameState?.won ? correctEntity?.name : undefined
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
      <div className="absolute top-0 left-0 mt-20 ml-3 flex flex-col gap-2 z-[1000]">
        <button
          onClick={clearSelection}
          className="bg-zinc-800 text-white p-2 rounded shadow-md hover:bg-zinc-700 transition-colors border border-zinc-600 w-8 h-8 flex items-center justify-center cursor-pointer"
          title="Reset Selection"
        >
          <RotateCcw size={16} />
        </button>
        
        {gameState?.won && (
          <button
            onClick={handleZoomToCorrect}
            className="bg-green-600 text-white p-2 rounded shadow-md hover:bg-green-700 transition-colors border border-green-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to Correct State"
          >
            <Check size={16} />
          </button>
        )}
      </div>

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
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
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
