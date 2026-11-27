import { useState, useEffect, useRef, useMemo, useCallback, type CSSProperties } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { type PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import { useMapData } from '../hooks/useMapData';
import MapLoading from './MapLoading';
import { createMapRenderer } from '../lib/mapRenderer';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';
import MapCartographicTexture from './MapCartographicTexture';
import { EARTH_MAP_BOUNDS } from '../lib/mapBounds';

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

      if (featureMatchesName(feature, targetName)) return MAP_THEME.countries.correct;
      if (wrongGuesses.some((wg) => featureMatchesName(feature, wg.guess))) return MAP_THEME.countries.markers.red;
      return MAP_THEME.countries.available;
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
        s.style.color = MAP_THEME.countries.correct.color;
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
        s.style.color = MAP_THEME.countries.markers.red.color;
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
      <div className="relative h-64 sm:h-80 md:h-96 w-full rounded-lg border border-[var(--map-frame-border)] bg-[var(--map-ocean)] overflow-hidden" style={MAP_THEME_CSS_VARIABLES as CSSProperties}>

        {(!geoJsonData || mapError) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--map-ocean)]">
            <MapLoading className="h-full" error={Boolean(mapError)} onRetry={retry} />
          </div>
        )}

        <div className="recap-map-pane h-full w-full">
          <MapContainer
            className="antique-map-surface"
            center={[15, 10]}
            zoom={2}
            style={{ height: '100%', width: '100%', background: MAP_THEME.map.backgroundColor }}
            minZoom={1}
            maxZoom={8}
            maxBounds={EARTH_MAP_BOUNDS}
            maxBoundsViscosity={1}
            worldCopyJump={false}
            zoomSnap={0.5}
            attributionControl={true}
            ref={setMap}
            renderer={renderer}
          >
            <TileLayer
              url={MAP_THEME.map.tileUrl}
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              bounds={EARTH_MAP_BOUNDS}
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
            <MapCartographicTexture />
          </MapContainer>
        </div>
      </div>

      {/* Map Legend & Absent Geometry Notes */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-app-text-muted px-1">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium text-app-text">
            <span className="inline-block h-3 w-3 rounded-sm border border-emerald-700 bg-emerald-600/80" />
            <span>Target ({targetName})</span>
          </span>
          <span className="flex items-center gap-1.5 font-medium text-app-text">
            <span className="inline-block h-3 w-3 rounded-sm border border-rose-700 bg-rose-600/80" />
            <span>Common misguesses</span>
          </span>
          <span className="flex items-center gap-1.5 text-app-text-muted">
            <span className="inline-block h-3 w-3 rounded-sm border border-app-border/50 bg-[#e1d7bf]" />
            <span>Other mapped areas</span>
          </span>
        </div>

        {(absentTarget || absentGuesses.length > 0) && (
          <div className="text-[11px] text-app-text-muted italic space-x-2">
            {absentTarget && <span>Target country ({targetName}) geometry absent from 50m GeoJSON polygons.</span>}
            {absentGuesses.length > 0 && <span>Absent from 50m GeoJSON polygons: {absentGuesses.join(', ')}.</span>}
          </div>
        )}
      </div>
    </div>
  );
}
