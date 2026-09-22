import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useGameStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature, FeatureCollection } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check, RotateCcw } from 'lucide-react';
import type { MapInteractionState } from '../lib/mapMarkings';

function isCorrectCountryFeature(feature: Feature | undefined, targetName?: string) {
  const name = feature?.properties?.SOVEREIGNT;
  return typeof name === 'string' && !!targetName
    && name.localeCompare(targetName, undefined, { sensitivity: 'base' }) === 0;
}

interface MapBoxProps {
  correctCountryName?: string;
  className?: string;
  onCountryCode?: (code: string | undefined) => void;
  center?: [number, number];
  zoom?: number;
  minZoom?: number;
  maxZoom?: number;
  onCountryClick?: (name: string) => void;
}

interface MapControlsProps {
  correctCountryName?: string;
  geoJsonData: FeatureCollection | null;
  map: L.Map | null;
  interaction: MapInteractionState;
  defaultCenter?: [number, number];
  defaultZoom?: number;
}
function MapControls({ correctCountryName, geoJsonData, map, interaction, defaultCenter, defaultZoom }: MapControlsProps) {
  const { isGameOver, activeMarkerColor, setActiveMarkerColor, clearMapMarkings } = interaction;
  const handleZoomToCorrect = () => {
    if (map && correctCountryName && geoJsonData) {
      const correctFeature = geoJsonData.features.find(feature => isCorrectCountryFeature(feature, correctCountryName));

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
        }
      }
    }
  };
  const handleResetView = () => {
    if (map && defaultCenter) {
      map.flyTo(defaultCenter, defaultZoom || 2, { duration: 1 });
    }
  };

  return (
    <>
      <MapToolbar
        activeColor={activeMarkerColor}
        onColorChange={setActiveMarkerColor}
        onClear={clearMapMarkings}
      />
      <div className="absolute top-0 left-0 mt-16 md:mt-20 ml-2 md:ml-3 z-[1000] flex flex-col gap-2">
        {defaultCenter && (
          <button
            onClick={(e) => {
              e.preventDefault();
              handleResetView();
            }}
            className="bg-zinc-800 text-zinc-200 p-2 rounded shadow-md hover:bg-zinc-700 hover:text-white transition-colors border border-zinc-700 w-8 h-8 flex items-center justify-center cursor-pointer"
            title="Reset view"
          >
            <RotateCcw size={15} />
          </button>
        )}
        {isGameOver && correctCountryName && (
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
        )}
      </div>
    </>
  );
}

function MapController({ correctCountryName, geoJsonData, isGameOver }: { correctCountryName?: string, geoJsonData: FeatureCollection | null, isGameOver: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (isGameOver && correctCountryName && geoJsonData) {
      // Find the feature for the correct country
      const correctFeature = geoJsonData.features.find(feature => isCorrectCountryFeature(feature, correctCountryName));

      if (correctFeature) {
        const layer = L.geoJSON(correctFeature);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
            map.flyToBounds(bounds, { duration: 2 });
        }
      }
    }
  }, [isGameOver, correctCountryName, geoJsonData, map]);

  return null;
}

export default function MapBox({ correctCountryName, className, onCountryCode }: MapBoxProps) {
  const state = useGameStore();
  return <ControlledMapBox className={className} onCountryCode={onCountryCode}
    correctCountryName={correctCountryName || state.correctEntity?.name}
    interaction={{
      entityMarkings: state.entityMarkings,
      activeMarkerColor: state.activeMarkerColor,
      setActiveMarkerColor: state.setActiveMarkerColor,
      handleEntityMapClick: state.handleEntityMapClick,
      clearMapMarkings: state.clearMapMarkings,
      isGameOver: !!state.gameState?.is_game_over,
    }} />;
}

export function ControlledMapBox({
  correctCountryName,
  className,
  onCountryCode,
  interaction,
  center = [20, 0],
  zoom = 2,
  minZoom = 2,
  maxZoom = 10,
  onCountryClick,
}: MapBoxProps & { interaction: MapInteractionState }) {
  const [geoJsonData, setGeoJsonData] = useState<FeatureCollection | null>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const { entityMarkings, isGameOver } = interaction;
  const revealedName = isGameOver ? correctCountryName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onCountryClick });
  current.current = { interaction, revealedName, onCountryClick };
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    fetch('/countries_50m.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error('Failed to load map data', err));
  }, []);

  useEffect(() => {
    if (!onCountryCode) return;
    const name = revealedName?.toLowerCase();
    const feature = geoJsonData?.features.find((item: Feature) => {
      const properties = item.properties;
      return name && [properties?.ADMIN, properties?.NAME_LONG, properties?.NAME_EN]
        .some(value => typeof value === 'string' && value.toLowerCase() === name);
    });
    const code = [feature?.properties?.ISO_A2, feature?.properties?.WB_A2]
      .find(value => typeof value === 'string' && /^[a-z]{2}$/i.test(value));
    onCountryCode(code);
  }, [revealedName, geoJsonData, onCountryCode]);

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
    return getStyleFromState(feature, current.current.interaction.entityMarkings, current.current.revealedName);
  };
  // Optimization: Update styles imperatively instead of re-rendering whole map
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
          if (isCorrectCountryFeature(feature, revealedName)) {
            layer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, revealedName, geoJsonData]);
  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const countryName = feature.properties?.SOVEREIGNT;
    
    // Bind click handler
    layer.on({
      click: () => {
        if (isCorrectCountryFeature(feature, current.current.revealedName)) {
          return;
        }

        current.current.interaction.handleEntityMapClick(countryName.toUpperCase(), false);
        current.current.onCountryClick?.(countryName);
      },
      contextmenu: (e: any) => {
        e.originalEvent?.preventDefault?.();
        if (isCorrectCountryFeature(feature, current.current.revealedName)) {
          return;
        }

        current.current.interaction.handleEntityMapClick(countryName.toUpperCase(), true);
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
        const style = getStyle(feature);
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
        key={`${center[0]}-${center[1]}-${zoom}`}
        center={center} 
        zoom={zoom} 
        style={{ height: '100%', width: '100%', background: '#242424' }}
        minZoom={minZoom}
        maxZoom={maxZoom}
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
        
        <MapController correctCountryName={revealedName} geoJsonData={geoJsonData} isGameOver={isGameOver} />
      </MapContainer>
      <MapControls correctCountryName={revealedName} geoJsonData={geoJsonData} map={map} interaction={interaction} defaultCenter={center} defaultZoom={zoom} />
    </div>
  );
}
