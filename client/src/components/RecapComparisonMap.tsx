import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import { useMapData } from '../hooks/useMapData';
import MapLoading from './MapLoading';
import { createMapRenderer } from '../lib/mapRenderer';

interface RecapComparisonMapProps {
  targetName: string;
  wrongGuesses: Array<{ guess: string; count: number }>;
  className?: string;
}

function canonicalNameKey(name: string): string {
  const clean = name.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const aliasMap: Record<string, string> = {
    'czech republic': 'czechia',
    'usa': 'united states',
    'united states of america': 'united states',
    'uk': 'united kingdom',
    'dr congo': 'democratic republic of the congo',
    'congo, democratic republic of the': 'democratic republic of the congo',
    'congo': 'republic of the congo',
  };
  return aliasMap[clean] || clean;
}

function featureMatchesName(feature: Feature | undefined, searchName: string): boolean {
  if (!feature?.properties) return false;
  const targetKey = canonicalNameKey(searchName);
  const p = feature.properties;
  const candidates = [p.SOVEREIGNT, p.ADMIN, p.NAME, p.NAME_LONG, p.NAME_EN]
    .filter((v): v is string => typeof v === 'string');
  return candidates.some((cand) => canonicalNameKey(cand) === targetKey);
}

export default function RecapComparisonMap({
  targetName,
  wrongGuesses,
  className = '',
}: RecapComparisonMapProps) {
  const { data: geoJsonData, error: mapError, retry } = useMapData('/countries_50m.geojson');
  const [map, setMap] = useState<L.Map | null>(null);
  const [renderer] = useState(createMapRenderer);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);



  // Track which countries were successfully matched in the GeoJSON
  const { absentTarget, absentGuesses } = useMemo(() => {
    if (!geoJsonData) return { absentTarget: false, absentGuesses: [] };
    let hasTarget = false;
    const foundGuesses = new Set<string>();

    for (const feat of geoJsonData.features) {
      if (!hasTarget && featureMatchesName(feat, targetName)) {
        hasTarget = true;
      }
      for (const wg of wrongGuesses) {
        if (!foundGuesses.has(wg.guess) && featureMatchesName(feat, wg.guess)) {
          foundGuesses.add(wg.guess);
        }
      }
    }

    const absent = wrongGuesses.filter((wg) => !foundGuesses.has(wg.guess)).map((wg) => wg.guess);
    return { absentTarget: !hasTarget, absentGuesses: absent };
  }, [geoJsonData, targetName, wrongGuesses]);

  // Styling rule
  const getStyle = useCallback(
    (feature?: Feature): PathOptions => {
      if (!feature?.properties) return {};

      // 1. Target Solution: Emerald
      if (featureMatchesName(feature, targetName)) {
        return {
          fillColor: '#10b981',
          weight: 2,
          opacity: 1,
          color: '#34d399',
          fillOpacity: 0.7,
        };
      }

      // 2. Common Recorded Misguess: Rose
      const isGuess = wrongGuesses.some((wg) => featureMatchesName(feature, wg.guess));
      if (isGuess) {
        return {
          fillColor: '#f43f5e',
          weight: 1.5,
          opacity: 0.9,
          color: '#fb7185',
          fillOpacity: 0.55,
        };
      }

      // 3. Unselected base: Dark neutral
      return {
        fillColor: '#18181b',
        weight: 0.5,
        opacity: 0.7,
        color: '#27272a',
        fillOpacity: 0.4,
      };
    },
    [targetName, wrongGuesses],
  );

  // Bind read-only tooltips with DOM textContent
  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      if (!feature.properties) return;
      const isTarget = featureMatchesName(feature, targetName);
      const matchedGuess = wrongGuesses.find((wg) => featureMatchesName(feature, wg.guess));

      if (isTarget) {
        const el = document.createElement('div');
        el.className = 'font-sans text-xs';
        const b = document.createElement('b');
        b.textContent = targetName;
        el.appendChild(b);
        el.appendChild(document.createElement('br'));
        const s = document.createElement('span');
        s.style.color = '#34d399';
        s.textContent = 'Target Solution';
        el.appendChild(s);
        layer.bindTooltip(el, { sticky: true });
      } else if (matchedGuess) {
        const el = document.createElement('div');
        el.className = 'font-sans text-xs';
        const b = document.createElement('b');
        b.textContent = matchedGuess.guess;
        el.appendChild(b);
        el.appendChild(document.createElement('br'));
        const s = document.createElement('span');
        s.style.color = '#fb7185';
        s.textContent = `${matchedGuess.count} recorded misguesses`;
        el.appendChild(s);
        layer.bindTooltip(el, { sticky: true });
      }
    },
    [targetName, wrongGuesses],
  );

  // Auto-fit bounds to highlighted target and wrong guesses
  useEffect(() => {
    if (!map || !geoJsonData || !geoJsonLayerRef.current) return;

    try {
      const bounds = L.latLngBounds([]);
      geoJsonLayerRef.current.eachLayer((layer: L.Layer) => {
        const featureLayer = layer as L.Layer & { feature?: Feature; getBounds?: () => L.LatLngBounds };
        const feat = featureLayer.feature;
        if (feat && (featureMatchesName(feat, targetName) || wrongGuesses.some((wg) => featureMatchesName(feat, wg.guess)))) {
          if (typeof featureLayer.getBounds === 'function') {
            bounds.extend(featureLayer.getBounds());
          }
        }
      });
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [32, 32], maxZoom: 5 });
      }
    } catch {
      // ignore
    }
  }, [map, geoJsonData, targetName, wrongGuesses]);


  return (
    <div className={`space-y-2 ${className}`}>
      <div className="relative h-64 sm:h-80 md:h-96 w-full rounded-lg border border-white/10 bg-obsidian-950 overflow-hidden">
        <style>{`
          .recap-map-pane .leaflet-container, .recap-map-pane .leaflet-tile-pane, .recap-map-pane .leaflet-pane {
              background-color: #18181b !important;
              background: #18181b !important;
          }
          .recap-map-pane .leaflet-interactive:focus {
              outline: none;
          }
          .recap-map-pane .leaflet-tooltip {
              background-color: rgba(24, 24, 27, 0.95) !important;
              border: 1px solid rgba(255, 255, 255, 0.15) !important;
              color: #f4f4f5 !important;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5) !important;
              pointer-events: none !important;
          }
        `}</style>

        {(!geoJsonData || mapError) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-obsidian-950/80">
            <MapLoading className="h-full" error={Boolean(mapError)} onRetry={retry} />
          </div>
        )}

        <div className="recap-map-pane h-full w-full">
          <MapContainer
            center={[15, 10]}
            zoom={2}
            style={{ height: '100%', width: '100%', background: '#18181b' }}
            minZoom={1}
            maxZoom={8}
            zoomSnap={0.5}
            attributionControl={true}
            ref={setMap}
            renderer={renderer}
          >
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              bounds={[[-78, -180], [82, 180]]}
              errorTileUrl="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
              noWrap={true}
              keepBuffer={2}
            />

            {geoJsonData && (
              <GeoJSON
                data={geoJsonData}
                style={getStyle}
                onEachFeature={onEachFeature}
                ref={geoJsonLayerRef}
              />
            )}
          </MapContainer>
        </div>
      </div>

      {/* Map Legend & Absent Geometry Notes */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-zinc-400 px-1">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium text-sand-100">
            <span className="inline-block h-3 w-3 rounded-sm border border-emerald-400 bg-emerald-500/80" />
            <span>Target ({targetName})</span>
          </span>
          <span className="flex items-center gap-1.5 font-medium text-sand-100">
            <span className="inline-block h-3 w-3 rounded-sm border border-rose-400 bg-rose-500/80" />
            <span>Common misguesses</span>
          </span>
          <span className="flex items-center gap-1.5 text-zinc-500">
            <span className="inline-block h-3 w-3 rounded-sm border border-zinc-700 bg-zinc-900" />
            <span>Other mapped areas</span>
          </span>
        </div>

        {(absentTarget || absentGuesses.length > 0) && (
          <div className="text-[11px] text-zinc-500 italic space-x-2">
            {absentTarget && <span>Target country ({targetName}) geometry absent from 50m GeoJSON polygons.</span>}
            {absentGuesses.length > 0 && <span>Absent from 50m GeoJSON polygons: {absentGuesses.join(', ')}.</span>}
          </div>
        )}
      </div>
    </div>
  );
}
