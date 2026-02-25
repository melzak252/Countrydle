import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useWojewodztwaGameStore } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import { RotateCcw, Check } from 'lucide-react';

interface WojewodztwaMapProps {
  correctWojewodztwoName?: string;
  className?: string;
}

function MapController({ correctName, geoJsonData }: { correctName?: string, geoJsonData: any }) {
  const map = useMap();
  const { gameState } = useWojewodztwaGameStore();

  useEffect(() => {
    if (gameState?.won && correctName && geoJsonData) {
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
  }, [gameState?.won, correctName, geoJsonData, map]);

  return null;
}

export default function WojewodztwaMap({ correctWojewodztwoName, className }: WojewodztwaMapProps) {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const { selectedEntityNames, toggleEntitySelection, clearSelection, gameState, correctEntity } = useWojewodztwaGameStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  
  useEffect(() => {
    fetch('/wojewodztwa.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load wojewodztwa map data', err));
  }, []);

  const getStyleFromState = (feature: any, currentSelected: string[], currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties || !feature.properties.nazwa) return {};

    const name = feature.properties.nazwa;
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
      const { selectedEntityNames, correctEntity, gameState } = useWojewodztwaGameStore.getState();
      return getStyleFromState(
          feature, 
          selectedEntityNames, 
          gameState?.won ? correctEntity?.nazwa : undefined
      );
  }

  useEffect(() => {
    if (geoJsonLayerRef.current) {
        geoJsonLayerRef.current.eachLayer((layer: any) => {
             const feature = layer.feature;
             if (feature) {
                 const { gameState, correctEntity } = useWojewodztwaGameStore.getState();
                 const newStyle = getStyleFromState(
                     feature, 
                     selectedEntityNames, 
                      gameState?.won ? correctWojewodztwoName || correctEntity?.nazwa : undefined
                  );
                 layer.setStyle(newStyle);
                 
                  if (gameState?.won && (correctWojewodztwoName || correctEntity?.nazwa) && (feature.properties.nazwa.toUpperCase() === (correctWojewodztwoName || correctEntity?.nazwa).toUpperCase())) {
                      layer.bringToFront();
                  }
             }
        });
    }
  }, [selectedEntityNames, gameState?.won, correctWojewodztwoName]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.nazwa;
    
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
        const { selectedEntityNames: currentSelected, correctEntity, gameState } = useWojewodztwaGameStore.getState();
        
        const style = getStyleFromState(
            feature, 
            currentSelected, 
            gameState?.won ? correctEntity?.nazwa : undefined
        );
        l.setStyle(style);
      }
    });

    if (feature.properties) {
        layer.bindTooltip(`${feature.properties.nazwa}`);
    }
  };

  const handleZoomToCorrect = () => {
    const targetName = correctWojewodztwoName || correctEntity?.nazwa;
    
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
    return <div className="h-[350px] md:h-[500px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">Ładowanie mapy województw...</div>;
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
          title="Resetuj zaznaczenie"
        >
          <RotateCcw size={16} />
        </button>
        
        {gameState?.won && (
          <button
            onClick={handleZoomToCorrect}
            className="bg-green-600 text-white p-2 rounded shadow-md hover:bg-green-700 transition-colors border border-green-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Pokaż poprawne województwo"
          >
            <Check size={16} />
          </button>
        )}
      </div>

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
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        
        <GeoJSON 
            data={geoJsonData} 
            style={getStyle} 
            onEachFeature={onEachFeature}
            ref={geoJsonLayerRef}
        />

        <MapController correctName={correctWojewodztwoName} geoJsonData={geoJsonData} />
      </MapContainer>
    </div>
  );
}
