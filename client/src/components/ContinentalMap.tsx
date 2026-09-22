import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getContinentalStore, type MapMarkerColor } from '../stores/gameStore';
import L, { type PathOptions } from 'leaflet';
import type { Feature, GeoJsonObject } from 'geojson';
import MapToolbar from './MapToolbar';
import { Check, RotateCcw } from 'lucide-react';

export type ContinentKey = 'europe' | 'asia' | 'africa' | 'americas';

interface ContinentalMapProps {
  continent: ContinentKey;
  correctCountryName?: string;
  className?: string;
}

interface ViewportConfig {
  center: [number, number];
  zoom: number;
  minZoom: number;
  maxZoom: number;
}

const CONTINENTAL_VIEWPORTS: Record<ContinentKey, ViewportConfig> = {
  europe: { center: [54, 15], zoom: 3.8, minZoom: 2.5, maxZoom: 8 },
  asia: { center: [34, 95], zoom: 3, minZoom: 2, maxZoom: 8 },
  africa: { center: [2, 20], zoom: 3, minZoom: 2, maxZoom: 8 },
  americas: { center: [15, -85], zoom: 2.5, minZoom: 1.8, maxZoom: 8 },
};

function MapControls({
  continent,
  correctCountryName,
  geoJsonData,
  map,
}: {
  continent: ContinentKey;
  correctCountryName?: string;
  geoJsonData: unknown;
  map: L.Map | null;
}) {
  const useStore = getContinentalStore(continent);
  const {
    gameState,
    activeMarkerColor,
    setActiveMarkerColor,
    clearMapMarkings,
  } = useStore();

  const handleZoomToCorrect = () => {
    if (map && correctCountryName && geoJsonData) {
      const geo = geoJsonData as { features: Feature[] };
      const correctFeature = geo.features.find((f: Feature) => {
        const p = f.properties as Record<string, string> | undefined;
        const sName = p?.SOVEREIGNT?.toUpperCase();
        const aName = p?.ADMIN?.toUpperCase();
        const cName = correctCountryName.toUpperCase();
        return sName === cName || aName === cName;
      });

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
    if (map) {
      const vp = CONTINENTAL_VIEWPORTS[continent];
      map.flyTo(vp.center, vp.zoom, { duration: 1 });
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
        <button
          onClick={(e) => {
            e.preventDefault();
            handleResetView();
          }}
          className="bg-zinc-800 text-zinc-200 p-2 rounded shadow-md hover:bg-zinc-700 hover:text-white transition-colors border border-zinc-700 w-8 h-8 flex items-center justify-center cursor-pointer"
          title="Reset continental view"
        >
          <RotateCcw size={15} />
        </button>
        {gameState?.is_game_over && (
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

function MapController({
  correctCountryName,
  geoJsonData,
  isGameOver,
}: {
  correctCountryName?: string;
  geoJsonData: unknown;
  isGameOver?: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (isGameOver && correctCountryName && geoJsonData) {
      const geo = geoJsonData as { features: Feature[] };
      const correctFeature = geo.features.find((f: Feature) => {
        const p = f.properties as Record<string, string> | undefined;
        const sName = p?.SOVEREIGNT?.toUpperCase();
        const aName = p?.ADMIN?.toUpperCase();
        const cName = correctCountryName.toUpperCase();
        return sName === cName || aName === cName;
      });

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

export default function ContinentalMap({
  continent,
  correctCountryName,
  className,
}: ContinentalMapProps) {
  const [geoJsonData, setGeoJsonData] = useState<unknown>(null);
  const [map, setMap] = useState<L.Map | null>(null);

  const useStore = getContinentalStore(continent);
  const {
    entityMarkings,
    handleEntityMapClick,
    gameState,
    entities,
    correctEntity,
  } = useStore();

  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const viewport = CONTINENTAL_VIEWPORTS[continent];

  // Whitelist of country names belonging to this continent
  const inScopeNames = useMemo(() => {
    const names = new Set<string>();
    entities.forEach((e: { name?: string; official_name?: string }) => {
      if (e.name) names.add(e.name.toUpperCase());
      if (e.official_name) names.add(e.official_name.toUpperCase());
    });
    return names;
  }, [entities]);

  useEffect(() => {
    fetch('/countries_50m.geojson')
      .then((res) => res.json())
      .then((data) => setGeoJsonData(data))
      .catch((err) => console.error('Failed to load countries geojson', err));
  }, []);

  const getFeatureCountryName = (feature: Feature): string => {
    const props = feature.properties as Record<string, string> | undefined;
    return props?.SOVEREIGNT || props?.ADMIN || props?.NAME_LONG || '';
  };

  const isFeatureInScope = (feature: Feature): boolean => {
    const props = feature.properties as Record<string, string> | undefined;
    const sName = (props?.SOVEREIGNT || '').toUpperCase();
    const aName = (props?.ADMIN || '').toUpperCase();
    const lName = (props?.NAME_LONG || '').toUpperCase();
    return (
      inScopeNames.has(sName) ||
      inScopeNames.has(aName) ||
      inScopeNames.has(lName)
    );
  };

  const isCorrectCountry = (feature: Feature, targetName?: string): boolean => {
    if (!targetName) return false;
    const props = feature.properties as Record<string, string> | undefined;
    const tClean = targetName.toUpperCase();
    return (
      props?.SOVEREIGNT?.toUpperCase() === tClean ||
      props?.ADMIN?.toUpperCase() === tClean ||
      props?.NAME_LONG?.toUpperCase() === tClean
    );
  };

  const getStyleFromState = (
    feature: Feature,
    markings: Record<string, MapMarkerColor>,
    currentCorrectName?: string
  ): PathOptions => {
    const inScope = isFeatureInScope(feature);

    // 1. Out-of-scope background context
    if (!inScope) {
      return {
        fillColor: '#18181b',
        weight: 1,
        opacity: 0.3,
        color: '#27272a',
        fillOpacity: 0.25,
      };
    }

    // 2. In-scope continental candidates
    const countryName = getFeatureCountryName(feature).toUpperCase();
    const isCorrect = isCorrectCountry(feature, currentCorrectName);
    const marker = markings[countryName];

    if (isCorrect) {
      return {
        fillColor: '#22c55e',
        weight: 2,
        opacity: 1,
        color: '#4ade80',
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
      fillColor: '#27272a',
      weight: 1,
      opacity: 1,
      color: '#52525b',
      fillOpacity: 0.7,
    };
  };

  const getStyle = (feature: unknown) => {
    return getStyleFromState(
      feature as Feature,
      entityMarkings,
      gameState?.is_game_over
        ? correctCountryName || correctEntity?.name
        : undefined
    );
  };

  // Imperative style updates when markings or game over state changes
  useEffect(() => {
    if (geoJsonLayerRef.current) {
      const activeCorrect = gameState?.is_game_over
        ? correctCountryName || correctEntity?.name
        : undefined;
      geoJsonLayerRef.current.eachLayer((layer) => {
        const pathLayer = layer as L.Path & { feature?: Feature };
        if (pathLayer.feature) {
          const newStyle = getStyleFromState(
            pathLayer.feature,
            entityMarkings,
            activeCorrect
          );
          pathLayer.setStyle(newStyle);
          if (isCorrectCountry(pathLayer.feature, activeCorrect)) {
            pathLayer.bringToFront();
          }
        }
      });
    }
  }, [entityMarkings, gameState?.is_game_over, correctCountryName, correctEntity?.name, inScopeNames]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const inScope = isFeatureInScope(feature);
    const countryName = getFeatureCountryName(feature);

    if (!inScope) {
      // Non-interactive out-of-scope countries
      return;
    }

    layer.on({
      click: () => {
        const activeCorrect = correctCountryName || correctEntity?.name;
        if (gameState?.is_game_over && isCorrectCountry(feature, activeCorrect)) {
          return;
        }
        handleEntityMapClick(countryName.toUpperCase(), false);
      },
      contextmenu: (e: L.LeafletMouseEvent) => {
        e.originalEvent?.preventDefault?.();
        const activeCorrect = correctCountryName || correctEntity?.name;
        if (gameState?.is_game_over && isCorrectCountry(feature, activeCorrect)) {
          return;
        }
        handleEntityMapClick(countryName.toUpperCase(), true);
      },
      mouseover: (e: L.LeafletMouseEvent) => {
        const pathLayer = e.target as L.Path;
        const currentStyle = getStyleFromState(
          feature,
          entityMarkings,
          gameState?.is_game_over ? correctCountryName || correctEntity?.name : undefined
        );
        pathLayer.setStyle({
          weight: (currentStyle.weight as number || 1) + 1,
          color: '#ffffff',
          fillOpacity: Math.min(1, ((currentStyle.fillOpacity as number) || 0.7) + 0.15),
        });
        pathLayer.bringToFront();
      },
      mouseout: (e: L.LeafletMouseEvent) => {
        const pathLayer = e.target as L.Path;
        const currentStyle = getStyleFromState(
          feature,
          entityMarkings,
          gameState?.is_game_over ? correctCountryName || correctEntity?.name : undefined
        );
        pathLayer.setStyle(currentStyle);
      },
    });

    const props = feature.properties as Record<string, string> | undefined;
    if (props) {
      layer.bindTooltip(
        `<div class="text-sm font-semibold">${props.SOVEREIGNT || props.ADMIN} ${
          props.ADMIN && props.SOVEREIGNT && props.ADMIN !== props.SOVEREIGNT ? `(${props.ADMIN})` : ''
        }</div>`,
        { sticky: true, direction: 'auto' }
      );
    }
  };

  if (!geoJsonData) {
    return (
      <div className="h-[400px] w-full bg-zinc-900 rounded-xl animate-pulse flex items-center justify-center text-zinc-500">
        Loading Continental Map...
      </div>
    );
  }

  return (
    <div
      className={`w-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg relative z-0 ${
        className ? className : 'h-[350px] md:h-[520px] mb-4 md:mb-8'
      }`}
    >
      <style>{`
        .leaflet-interactive:focus {
          outline: none;
        }
      `}</style>
      <MapContainer
        center={viewport.center}
        zoom={viewport.zoom}
        style={{ height: '100%', width: '100%', background: '#18181b' }}
        minZoom={viewport.minZoom}
        maxZoom={viewport.maxZoom}
        attributionControl={false}
        ref={setMap}
      >
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
        />

        <GeoJSON
          data={geoJsonData as GeoJsonObject}
          style={getStyle}
          onEachFeature={onEachFeature}
          ref={geoJsonLayerRef}
        />

        <MapController
          correctCountryName={correctCountryName || correctEntity?.name}
          geoJsonData={geoJsonData}
          isGameOver={gameState?.is_game_over}
        />
      </MapContainer>
      <MapControls
        continent={continent}
        correctCountryName={correctCountryName || correctEntity?.name}
        geoJsonData={geoJsonData}
        map={map}
      />
    </div>
  );
}
