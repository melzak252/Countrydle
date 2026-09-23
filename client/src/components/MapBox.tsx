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
  geoJsonUrl?: string;
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
      <div className="absolute top-[5.25rem] left-2.5 md:left-3 z-[1050] flex flex-col gap-2">
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

function MapController({
  correctCountryName,
  geoJsonData,
  isGameOver,
}: {
  correctCountryName?: string;
  geoJsonData: FeatureCollection | null;
  isGameOver: boolean;
}) {
  const map = useMap();

  // Keep Leaflet viewport and tiles updated when container size changes
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
        // Ignore micro-subpixel shifts during pan/zoom transforms
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

const geoJsonCache = new Map<string, FeatureCollection>();
const geoJsonPromiseCache = new Map<string, Promise<FeatureCollection>>();

function loadGeoJson(url: string): Promise<FeatureCollection> {
  const cached = geoJsonCache.get(url);
  if (cached) {
    return Promise.resolve(cached);
  }
  let p = geoJsonPromiseCache.get(url);
  if (!p) {
    p = fetch(url)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status} loading ${url}`);
        return res.json();
      })
      .then(data => {
        geoJsonCache.set(url, data);
        geoJsonPromiseCache.delete(url);
        return data;
      })
      .catch(err => {
        geoJsonPromiseCache.delete(url);
        throw err;
      });
    geoJsonPromiseCache.set(url, p);
  }
  return p;
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
  geoJsonUrl = '/countries_50m.geojson',
}: MapBoxProps & { interaction: MapInteractionState }) {
  const targetUrl = geoJsonUrl || '/countries_50m.geojson';
  const [geoJsonData, setGeoJsonData] = useState<FeatureCollection | null>(() => geoJsonCache.get(targetUrl) || null);
  const [map, setMap] = useState<L.Map | null>(null);
  const { entityMarkings, isGameOver } = interaction;
  const revealedName = isGameOver ? correctCountryName : undefined;
  // Leaflet retains handlers from layer creation; refs keep them on the current props.
  const current = useRef({ interaction, revealedName, onCountryClick });
  current.current = { interaction, revealedName, onCountryClick };
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const activeHoverLayerRef = useRef<L.Layer | null>(null);

  // Close lingering tooltips when mouse moves out of the map container
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
    let active = true;
    loadGeoJson(targetUrl)
      .then(data => {
        if (active) {
          setGeoJsonData(data);
        }
      })
      .catch(err => console.error('Failed to load map data', err));
    return () => {
      active = false;
    };
  }, [targetUrl]);
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
        weight: 1.5,
        opacity: 0.8,
        color: '#6ee7b7',
        fillOpacity: 0.35,
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
      const name = feature.properties.SOVEREIGNT || feature.properties.ADMIN;
      const sub = feature.properties.ADMIN && feature.properties.ADMIN !== feature.properties.SOVEREIGNT
        ? ` (${feature.properties.ADMIN})`
        : '';
      layer.bindTooltip(`<b>${name}</b>${sub}`, {
        sticky: true,
        direction: 'auto',
        opacity: 0.95,
      });
    }
  };

  if (!geoJsonData) {
    return (
      <div className={`w-full bg-obsidian-950 flex items-center justify-center text-zinc-400 font-mono text-xs ${className ? className : 'border border-white/10 rounded-sm h-[350px] md:h-[500px]'}`}>
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Loading map...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`w-full overflow-hidden relative ${className ? className : 'bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg h-[350px] md:h-[500px] mb-4 md:mb-8'}`}>
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
      <MapContainer 
        center={center} 
        zoom={zoom} 
        style={{ height: '100%', width: '100%', background: '#242424' }}
        minZoom={minZoom}
        maxZoom={maxZoom}
        attributionControl={false}
        wheelDebounceTime={80}
        wheelPxPerZoomLevel={120}
        ref={setMap}
      >
        <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
            keepBuffer={8}
            updateInterval={100}
            updateWhenZooming={false}
            updateWhenIdle={false}
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
