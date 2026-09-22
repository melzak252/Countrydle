import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { usePowiatyGameStore } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check } from 'lucide-react';

interface PowiatyMapProps {
  correctPowiatName?: string;
  className?: string;
}

function MapController({ correctName, geoJsonData }: { correctName?: string, geoJsonData: any }) {
  const map = useMap();
  const { gameState } = usePowiatyGameStore();

  useEffect(() => {
    if (gameState?.is_game_over && correctName && geoJsonData) {
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
  }, [gameState?.is_game_over, correctName, geoJsonData, map]);

  return null;
}

export default function PowiatyMap({ correctPowiatName, className }: PowiatyMapProps) {
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const {
    candidateEntities,
    eliminatedEntities,
    mapInteractionMode,
    setMapInteractionMode,
    handleEntityMapClick,
    clearMapMarkings,
    gameState,
  } = usePowiatyGameStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  
  useEffect(() => {
    fetch('/powiaty-min.geojson?v=' + new Date().getTime())
      .then(res => res.json())
      .then(data => {
        setGeoJsonData(data);
      })
      .catch(err => console.error("Error loading geojson:", err));
  }, []);

  const getStyleFromState = (feature: any, candidates: string[], eliminated: string[], currentCorrect?: string): PathOptions => {
    if (!feature || !feature.properties) return {};

    const name = (feature.properties.nazwa || '').toUpperCase();
    const isCorrect = currentCorrect ? name === currentCorrect.toUpperCase() : false;
    const isCandidate = candidates.includes(name);
    const isEliminated = eliminated.includes(name);

    if (isCorrect) {
      return {
        fillColor: '#10b981',
        weight: 2,
        opacity: 1,
        color: '#34d399',
        fillOpacity: 0.85,
      };
    }

    if (isCandidate) {
      return {
        fillColor: '#059669',
        weight: 2,
        opacity: 1,
        color: '#6ee7b7',
        fillOpacity: 0.65,
      };
    }

    if (isEliminated) {
      return {
        fillColor: '#09090b',
        weight: 1.5,
        opacity: 0.7,
        color: '#f43f5e',
        dashArray: '3, 4',
        fillOpacity: 0.85,
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
    const { candidateEntities: c, eliminatedEntities: el, correctEntity: ce, gameState: gs } = usePowiatyGameStore.getState();
    return getStyleFromState(feature, c, el, gs?.is_game_over ? ce?.nazwa : undefined);
  };

  useEffect(() => {
    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.eachLayer((layer: any) => {
        const feature = layer.feature;
        if (feature) {
          const { gameState: gs, correctEntity: ce } = usePowiatyGameStore.getState();
          const newStyle = getStyleFromState(
            feature,
            candidateEntities,
            eliminatedEntities,
            gs?.is_game_over ? correctPowiatName || ce?.nazwa : undefined
          );
          layer.setStyle(newStyle);

          if (gs?.is_game_over && (correctPowiatName || ce?.nazwa) && ((feature.properties.nazwa || '').toUpperCase() === (correctPowiatName || ce?.nazwa).toUpperCase())) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [candidateEntities, eliminatedEntities, gameState?.is_game_over, correctPowiatName]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.nazwa;
    
    layer.on({
      click: () => {
        handleEntityMapClick((name || '').toUpperCase(), false);
      },
      contextmenu: (e: any) => {
        e.originalEvent?.preventDefault?.();
        handleEntityMapClick((name || '').toUpperCase(), true);
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
        const { candidateEntities: c, eliminatedEntities: el, correctEntity: ce, gameState: gs } = usePowiatyGameStore.getState();
        const style = getStyleFromState(
          feature,
          c,
          el,
          gs?.is_game_over ? ce?.nazwa : undefined
        );
        l.setStyle(style);
      }
    });

    if (feature.properties) {
        layer.bindTooltip(`${feature.properties.nazwa}`);
    }
  };

  const handleZoomToCorrect = () => {
    const { correctEntity } = usePowiatyGameStore.getState();
    const targetName = correctPowiatName || correctEntity?.nazwa;
    
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
    return <div className="h-[350px] md:h-[500px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">Loading county map...</div>;
  }

  return (
    <div className={`w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg relative z-0 ${className ? className : 'h-[400px] md:h-[600px]'}`}>
      <style>{`
        .leaflet-interactive:focus {
            outline: none;
        }
      `}</style>
      <MapToolbar
        mode={mapInteractionMode}
        onModeChange={setMapInteractionMode}
        onClear={clearMapMarkings}
      />
      {gameState?.is_game_over && (
        <div className="absolute top-0 left-0 mt-16 md:mt-20 ml-2 md:ml-3 z-[1000]">
          <button
            onClick={handleZoomToCorrect}
            className="bg-emerald-600 text-white p-2 rounded shadow-md hover:bg-emerald-700 transition-colors border border-emerald-500 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Zoom to correct county"
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
        maxZoom={12}
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

        <MapController correctName={correctPowiatName} geoJsonData={geoJsonData} />
      </MapContainer>
    </div>
  );
}
