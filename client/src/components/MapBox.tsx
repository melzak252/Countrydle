import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useGameStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check } from 'lucide-react';

interface MapBoxProps {
  correctCountryName?: string;
  className?: string;
  onCountryCode?: (code: string | undefined) => void;
}

interface MapControlsProps {
  correctCountryName?: string;
  geoJsonData: any;
  map: L.Map | null;
}

function MapControls({ correctCountryName, geoJsonData, map }: MapControlsProps) {
  const {
    gameState,
    activeMarkerColor,
    setActiveMarkerColor,
    clearMapMarkings,
  } = useGameStore();

  const handleZoomToCorrect = () => {
    if (map && correctCountryName && geoJsonData) {
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.SOVEREIGNT.toUpperCase() === correctCountryName.toUpperCase()
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

  return (
    <>
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
      />
      {gameState?.is_game_over && (
        <div className="absolute top-0 left-0 mt-16 md:mt-20 ml-2 md:ml-3 z-[1000]">
          <button
            onClick={(e) => {
              e.preventDefault();
              handleZoomToCorrect();
            }}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to correct country"
          >
            <Check size={16} />
          </button>
        </div>
      )}
    </>
  );
}

function MapController({ correctCountryName, geoJsonData }: { correctCountryName?: string, geoJsonData: any }) {
  const map = useMap();
  const { gameState } = useGameStore();

  useEffect(() => {
    if (gameState?.is_game_over && correctCountryName && geoJsonData) {
      // Find the feature for the correct country
      const correctFeature = geoJsonData.features.find((f: any) => 
        f.properties.SOVEREIGNT.toUpperCase() === correctCountryName.toUpperCase()
      );

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
        }
      }
    }
  }, [gameState?.is_game_over, correctCountryName, geoJsonData, map]);

  return null;
}

export default function MapBox({ correctCountryName, className, onCountryCode }: MapBoxProps) {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const {
    entityMarkings,
    handleEntityMapClick,
    gameState,
  } = useGameStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);

  const isCorrectCountryFeature = (feature: any, currentCorrectName?: string) => {
    if (!feature?.properties || !currentCorrectName) return false;
    return feature.properties.SOVEREIGNT.toUpperCase() === currentCorrectName.toUpperCase();
  };
  
  useEffect(() => {
    fetch('/countries_50m.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load map data', err));
  }, []);

  useEffect(() => {
    if (!onCountryCode) return;
    const name = correctCountryName?.toLowerCase();
    const feature = geoJsonData?.features.find((item: Feature) => {
      const properties = item.properties;
      return name && [properties?.ADMIN, properties?.NAME_LONG, properties?.NAME_EN]
        .some(value => typeof value === 'string' && value.toLowerCase() === name);
    });
    const code = [feature?.properties?.ISO_A2, feature?.properties?.WB_A2]
      .find(value => typeof value === 'string' && /^[a-z]{2}$/i.test(value));
    onCountryCode(code);
  }, [correctCountryName, geoJsonData, onCountryCode]);

  const getStyleFromState = (
    feature: any,
    markings: Record<string, MapMarkerColor>,
    currentCorrectName?: string
  ): PathOptions => {
    if (!feature || !feature.properties) return {};

    const countryName = feature.properties.SOVEREIGNT.toUpperCase();
    const isCorrect = isCorrectCountryFeature(feature, currentCorrectName);
    const marker = markings[countryName];

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
    const { entityMarkings: em, correctEntity } = useGameStore.getState();
    return getStyleFromState(feature, em, correctEntity?.name);
  };
  // Optimization: Update styles imperatively instead of re-rendering whole map
  useEffect(() => {
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((layer: any) => {
        const feature = layer.feature;
        if (feature) {
          const { gameState, correctEntity } = useGameStore.getState();
          const newStyle = getStyleFromState(
            feature,
            entityMarkings,
            gameState?.is_game_over ? correctCountryName || correctEntity?.name : undefined
          );
          layer.setStyle(newStyle);
          const countryName = feature.properties.SOVEREIGNT.toUpperCase();
          if (gameState?.is_game_over && correctCountryName && (countryName === correctCountryName.toUpperCase())) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, gameState?.is_game_over, correctCountryName]);
  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const countryName = feature.properties?.SOVEREIGNT;
    
    // Bind click handler
    layer.on({
      click: () => {
        const { gameState: currentGameState, correctEntity } = useGameStore.getState();
        const currentCorrectName = correctCountryName || correctEntity?.name;

        if (currentGameState?.is_game_over && isCorrectCountryFeature(feature, currentCorrectName)) {
          return;
        }

        handleEntityMapClick(countryName.toUpperCase(), false);
      },
      contextmenu: (e: any) => {
        e.originalEvent?.preventDefault?.();
        const { gameState: currentGameState, correctEntity } = useGameStore.getState();
        const currentCorrectName = correctCountryName || correctEntity?.name;

        if (currentGameState?.is_game_over && isCorrectCountryFeature(feature, currentCorrectName)) {
          return;
        }

        handleEntityMapClick(countryName.toUpperCase(), true);
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
        // Reset to computed style using direct store access
        const { entityMarkings: em, gameState: currentGameState, correctEntity } = useGameStore.getState();
        const style = getStyleFromState(
            feature, 
            em,
            currentGameState?.is_game_over ? correctCountryName || correctEntity?.name : undefined
        );
        l.setStyle(style);
      }
    });

    if (feature.properties) {
        layer.bindTooltip(`
          <b>${feature.properties.SOVEREIGNT}</b>
          <br/>
          ${feature.properties.ADMIN === feature.properties.SOVEREIGNT ? '' : `(${feature.properties.ADMIN})`}
          `);
    }
  };

  if (!geoJsonData) {
    return <div className="h-[400px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">Loading Map...</div>;
  }

  return (
    <div className={`w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg relative z-0 ${className ? className : 'h-[350px] md:h-[500px] mb-4 md:mb-8'}`}>
      <style>{`
        .leaflet-interactive:focus {
            outline: none;
        }
      `}</style>
      <MapContainer 
        center={[20, 0]} 
        zoom={2} 
        style={{ height: '100%', width: '100%', background: '#242424' }}
        minZoom={2}
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
        
        <MapController correctCountryName={correctCountryName} geoJsonData={geoJsonData} />
      </MapContainer>
      <MapControls correctCountryName={correctCountryName} geoJsonData={geoJsonData} map={map} />
    </div>
  );
}
