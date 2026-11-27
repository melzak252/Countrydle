import type { FeatureCollection, Position } from 'geojson';
import { MAP_QUIZ_PATHS } from '../lib/mapGameMode';
import { MAP_THEME } from '../lib/mapTheme';
import { useMapData } from '../hooks/useMapData';
import type { CatalogGeography } from '../lib/gameCatalog';

type ExploreGame = { name: string; path: string; geography: CatalogGeography; artworkUrl?: string; artworkFallbackUrl?: string; artworkUrls?: readonly string[] };
type MapUrl = '/countries_50m.geojson' | '/europe.geojson' | '/asia.geojson' | '/africa.geojson' | '/americas.geojson' | '/powiaty-min.geojson' | '/wojewodztwa.geojson' | '/us-states.geojson';
type MapFrameId = 'worldwide' | 'europe' | 'asia' | 'africa' | 'americas' | 'united-states' | 'poland';
type MapBounds = readonly [west: number, south: number, east: number, north: number];
type MapFrame = { id: MapFrameId; bounds?: MapBounds; longitudeScale: number };
type MapViewportId = 'full' | 'duel-top' | 'duel-bottom';
type MapViewport = { id: MapViewportId; x: number; y: number; width: number; height: number; padding: number };

const mapPathCache = new WeakMap<FeatureCollection, Map<MapFrameId, Map<MapViewportId, string>>>();
const artworkSize = { width: 160, height: 160, padding: 5 };
const longitudeScaleAt = (latitude: number) => Math.cos((latitude * Math.PI) / 180);
const mapFrames: Record<MapFrameId, MapFrame> = {
  worldwide: { id: 'worldwide', longitudeScale: longitudeScaleAt(40) },
  europe: { id: 'europe', bounds: [-35, 30, 70, 82], longitudeScale: longitudeScaleAt(56) },
  asia: { id: 'asia', bounds: [25, -15, 205, 82], longitudeScale: longitudeScaleAt(33.5) },
  africa: { id: 'africa', bounds: [-20, -37, 52, 38], longitudeScale: longitudeScaleAt(0.5) },
  americas: { id: 'americas', bounds: [-180, -58, -30, 85], longitudeScale: longitudeScaleAt(13.5) },
  'united-states': { id: 'united-states', bounds: [-190, 17, -65, 73], longitudeScale: longitudeScaleAt(45) },
  poland: { id: 'poland', longitudeScale: longitudeScaleAt(52) },
};
// Landscape duel panels use the equatorial parallel to keep world outlines wide.
const duelMapFrame: MapFrame = { ...mapFrames.worldwide, longitudeScale: longitudeScaleAt(0) };
const fullViewport: MapViewport = { id: 'full', x: 0, y: 0, ...artworkSize };
const duelTopViewport: MapViewport = { id: 'duel-top', x: 5, y: 3, width: 150, height: 70, padding: 3 };
const duelBottomViewport: MapViewport = { id: 'duel-bottom', x: 5, y: 87, width: 150, height: 70, padding: 3 };

function isCoatArtwork(game: ExploreGame): boolean {
  const route = game.path.split('?')[0].toLowerCase();
  return route === '/herby-powiatow' || route === '/quiz-herbow' ||
    route.startsWith('/regional-symbols/') && route.split('/')[3] === 'coat';
}

function isFlagArtwork(game: ExploreGame): boolean {
  const route = game.path.split('?')[0].toLowerCase();
  return route === '/flagdle' || route === '/flag-shades' ||
    route === '/flagi-powiatow' || route === '/quiz-flag-powiatow' ||
    route.startsWith('/regional-symbols/') && route.split('/')[3] === 'flag';
}

function mapUrlForGame(game: ExploreGame): MapUrl {
  const route = game.path.split('?')[0].toLowerCase();
  const query = game.path.split('?')[1] ?? '';
  if (route === MAP_QUIZ_PATHS.us_states || route === '/map-border-hop' && query.includes('mode=us_states') || game.geography === 'united-states') {
    return '/us-states.geojson';
  }
  if (route === MAP_QUIZ_PATHS.powiaty || route.includes('powiat') || query.includes('mode=powiaty') || game.name.toLowerCase().includes('county')) {
    return '/powiaty-min.geojson';
  }
  if (route === '/wojewodztwa' || route.includes('voivodeship')) return '/wojewodztwa.geojson';
  if (route === '/europe') return '/europe.geojson';
  if (route === '/asia') return '/asia.geojson';
  if (route === '/africa') return '/africa.geojson';
  if (route === '/americas') return '/americas.geojson';
  if (game.geography === 'uk') return '/europe.geojson';
  return '/countries_50m.geojson';
}

function mapFrameForGame(game: ExploreGame): MapFrame {
  switch (mapUrlForGame(game)) {
    case '/europe.geojson': return mapFrames.europe;
    case '/asia.geojson': return mapFrames.asia;
    case '/africa.geojson': return mapFrames.africa;
    case '/americas.geojson': return mapFrames.americas;
    case '/us-states.geojson': return mapFrames['united-states'];
    case '/powiaty-min.geojson':
    case '/wojewodztwa.geojson': return mapFrames.poland;
    default: return mapFrames.worldwide;
  }
}

type MapProperties = { CONTINENT?: string; NAME?: string; name?: string } | null;

function shouldIncludeFeature(frame: MapFrame, properties: MapProperties): boolean {
  if (frame.id === 'europe') return properties?.CONTINENT === 'Europe';
  if (frame.id === 'asia') return properties?.CONTINENT === 'Asia' || properties?.NAME === 'Russia';
  if (frame.id === 'americas') return properties?.CONTINENT === 'North America' || properties?.CONTINENT === 'South America';
  if (frame.id === 'africa') return properties?.CONTINENT === 'Africa';
  return true;
}

function projectedLongitude(longitude: number, frame: MapFrame): number {
  let adjustedLongitude = longitude;
  if (frame.id === 'asia' && adjustedLongitude < 25) adjustedLongitude += 360;
  if (frame.id === 'united-states' && adjustedLongitude > 160) adjustedLongitude -= 360;
  return adjustedLongitude * frame.longitudeScale;
}

function polygonIntersectsFrame(ring: Position[], frame: MapFrame): boolean {
  if (!frame.bounds) return true;
  let minLongitude = Infinity;
  let maxLongitude = -Infinity;
  let minLatitude = Infinity;
  let maxLatitude = -Infinity;
  for (const position of ring) {
    const longitude = projectedLongitude(position[0], frame);
    minLongitude = Math.min(minLongitude, longitude);
    maxLongitude = Math.max(maxLongitude, longitude);
    minLatitude = Math.min(minLatitude, position[1]);
    maxLatitude = Math.max(maxLatitude, position[1]);
  }
  if (!Number.isFinite(minLongitude)) return false;
  const west = projectedLongitude(frame.bounds[0], frame);
  const east = projectedLongitude(frame.bounds[2], frame);
  return maxLongitude >= west && minLongitude <= east && maxLatitude >= frame.bounds[1] && minLatitude <= frame.bounds[3];
}

function clipRingToFrame(ring: Position[], frame: MapFrame): Position[] {
  const bounds = frame.bounds;
  if (!bounds) return ring;
  const west = projectedLongitude(bounds[0], frame);
  const east = projectedLongitude(bounds[2], frame);
  const south = bounds[1];
  const north = bounds[3];
  let points: Position[] = ring.map((position) => [projectedLongitude(position[0], frame), position[1]]);
  const first = points[0];
  const last = points[points.length - 1];
  if (points.length > 1 && first[0] === last[0] && first[1] === last[1]) points.pop();

  const clip = (
    inside: (point: Position) => boolean,
    intersection: (from: Position, to: Position) => Position,
  ) => {
    if (!points.length) return;
    const input = points;
    const output: Position[] = [];
    let previous = input[input.length - 1];
    let previousInside = inside(previous);
    for (const current of input) {
      const currentInside = inside(current);
      if (currentInside) {
        if (!previousInside) output.push(intersection(previous, current));
        output.push(current);
      } else if (previousInside) {
        output.push(intersection(previous, current));
      }
      previous = current;
      previousInside = currentInside;
    }
    points = output;
  };

  clip((point) => point[0] >= west, (from, to) => [
    west,
    from[1] + (to[1] - from[1]) * ((west - from[0]) / (to[0] - from[0])),
  ]);
  clip((point) => point[0] <= east, (from, to) => [
    east,
    from[1] + (to[1] - from[1]) * ((east - from[0]) / (to[0] - from[0])),
  ]);
  clip((point) => point[1] >= south, (from, to) => [
    from[0] + (to[0] - from[0]) * ((south - from[1]) / (to[1] - from[1])),
    south,
  ]);
  clip((point) => point[1] <= north, (from, to) => [
    from[0] + (to[0] - from[0]) * ((north - from[1]) / (to[1] - from[1])),
    north,
  ]);
  if (points.length < 3) return [];
  points.push(points[0]);
  return points;
}

function forEachRing(data: FeatureCollection, frame: MapFrame, visit: (ring: Position[], projected: boolean) => void): void {
  for (const feature of data.features) {
    const properties = feature.properties as MapProperties;
    if (!shouldIncludeFeature(frame, properties)) continue;
    const geometry = feature.geometry;
    if (!geometry) continue;
    const visitPolygon = (rings: Position[][]) => {
      for (const ring of rings) {
        if (!polygonIntersectsFrame(ring, frame)) continue;
        const clipped = frame.bounds ? clipRingToFrame(ring, frame) : ring;
        if (clipped.length >= 3) visit(clipped, frame.bounds !== undefined);
      }
    };
    if (geometry.type === 'Polygon') {
      visitPolygon(geometry.coordinates);
    } else if (geometry.type === 'MultiPolygon') {
      for (const polygon of geometry.coordinates) visitPolygon(polygon);
    }
  }
}

function createMapPath(data: FeatureCollection, frame: MapFrame, viewport = fullViewport): string {
  let frames = mapPathCache.get(data);
  if (!frames) {
    frames = new Map();
    mapPathCache.set(data, frames);
  }
  let viewports = frames.get(frame.id);
  if (!viewports) {
    viewports = new Map();
    frames.set(frame.id, viewports);
  }
  const cached = viewports.get(viewport.id);
  if (cached !== undefined) return cached;

  let minLongitude = frame.bounds ? projectedLongitude(frame.bounds[0], frame) : Infinity;
  let maxLongitude = frame.bounds ? projectedLongitude(frame.bounds[2], frame) : -Infinity;
  let minLatitude = frame.bounds?.[1] ?? Infinity;
  let maxLatitude = frame.bounds?.[3] ?? -Infinity;
  if (!frame.bounds) {
    forEachRing(data, frame, (ring, projected) => {
      for (const position of ring) {
        const longitude = projected ? position[0] : projectedLongitude(position[0], frame);
        minLongitude = Math.min(minLongitude, longitude);
        maxLongitude = Math.max(maxLongitude, longitude);
        minLatitude = Math.min(minLatitude, position[1]);
        maxLatitude = Math.max(maxLatitude, position[1]);
      }
    });
  }
  if (!Number.isFinite(minLongitude) || maxLongitude === minLongitude || maxLatitude === minLatitude) {
    viewports.set(viewport.id, '');
    return '';
  }

  const scale = Math.min(
    (viewport.width - viewport.padding * 2) / (maxLongitude - minLongitude),
    (viewport.height - viewport.padding * 2) / (maxLatitude - minLatitude),
  );
  const mapWidth = (maxLongitude - minLongitude) * scale;
  const mapHeight = (maxLatitude - minLatitude) * scale;
  const offsetX = viewport.x + (viewport.width - mapWidth) / 2;
  const offsetY = viewport.y + (viewport.height - mapHeight) / 2;
  let path = '';
  forEachRing(data, frame, (ring, projected) => {
    for (let index = 0; index < ring.length; index += 1) {
      const position = ring[index];
      const longitude = projected ? position[0] : projectedLongitude(position[0], frame);
      const x = offsetX + (longitude - minLongitude) * scale;
      const y = offsetY + (maxLatitude - position[1]) * scale;
      path += `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    }
    path += 'Z';
  });
  viewports.set(viewport.id, path);
  return path;
}

type MapArtworkVariant = 'map' | 'border-map' | 'duel-map';

function mapArtworkVariantForGame(game: ExploreGame): MapArtworkVariant {
  const route = game.path.split('?')[0].toLowerCase();
  if (route === '/friends') return 'duel-map';
  if (route === '/border-hop' || route === '/map-border-hop') return 'border-map';
  return 'map';
}

function MapArtwork({ url, frame, variant }: { url: MapUrl; frame: MapFrame; variant: MapArtworkVariant }) {
  const { data } = useMapData(url);
  const path = data && variant !== 'duel-map' ? createMapPath(data, frame) : '';
  const topWorld = data && variant === 'duel-map' ? createMapPath(data, duelMapFrame, duelTopViewport) : '';
  const bottomWorld = data && variant === 'duel-map' ? createMapPath(data, duelMapFrame, duelBottomViewport) : '';
  return (
    <svg data-game-artwork={variant} data-map-frame={frame.id} aria-hidden="true" focusable="false" shapeRendering="optimizeSpeed" viewBox={`0 0 ${artworkSize.width} ${artworkSize.height}`} preserveAspectRatio="xMidYMid meet" className="h-full w-full">
      {topWorld && (
        <path
          d={topWorld}
          data-map-panel="challenger"
          fill={MAP_THEME.countries.available.fillColor}
          fillRule="evenodd"
          stroke={MAP_THEME.countries.available.color}
          strokeWidth="0.8"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {bottomWorld && (
        <path
          d={bottomWorld}
          data-map-panel="opponent"
          fill={MAP_THEME.countries.unavailable.fillColor}
          fillRule="evenodd"
          stroke={MAP_THEME.countries.unavailable.color}
          strokeWidth="0.8"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {variant === 'duel-map' && (
        <>
          <path d="M12 80H66M94 80H148" fill="none" stroke={MAP_THEME.countries.available.color} strokeWidth="0.8" />
          <rect x="68" y="72" width="24" height="16" fill="#e9dfca" />
          <text x="80" y="83" textAnchor="middle" fill={MAP_THEME.countries.available.color} fontFamily="serif" fontSize="8" fontWeight="700">VS</text>
        </>
      )}
      {path && variant !== 'duel-map' && (
        <path
          d={path}
          fill={variant === 'border-map' ? 'none' : MAP_THEME.countries.available.fillColor}
          fillRule="evenodd"
          stroke={MAP_THEME.countries.available.color}
          strokeWidth={variant === 'border-map' ? '1.2' : '0.8'}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}

export default function ExploreGameArtwork({ game, featured = false }: { game: ExploreGame; featured?: boolean }) {
  const dimensions = featured ? 'h-32 w-32' : 'h-24 w-24';
  const imgSize = featured ? 104 : 72;
  const flagTileW = featured ? 48 : 34;
  const flagTileH = featured ? 32 : 22;
  const frameClass = `grid aspect-square shrink-0 place-items-center overflow-hidden border border-app-border bg-[#e9dfca] ${dimensions}`;
  if (isCoatArtwork(game)) {
    return (
      <span data-game-artwork-frame className={`${frameClass} p-3`}>
        <img data-game-artwork="coat" src={game.artworkUrl || '/coats/1.png'} alt="" width={imgSize} height={imgSize} loading={featured ? 'eager' : 'lazy'} decoding="async" className="block max-h-full max-w-full min-h-0 object-contain object-center" />
      </span>
    );
  }
  if (isFlagArtwork(game)) {
    if (game.artworkUrls?.length) {
      const isFlagShadesArtwork = game.path.split('?')[0].toLowerCase() === '/flag-shades';
      return (
        <span data-game-artwork-frame data-game-artwork={isFlagShadesArtwork ? 'flag-shades' : 'flag-montage'} aria-hidden="true" className={`${frameClass} p-3`}>
          <span className="grid h-full w-full grid-cols-2 gap-1">
            {game.artworkUrls.map((artworkUrl) => (
              <img key={artworkUrl} src={artworkUrl} alt="" width={flagTileW} height={flagTileH} loading={featured ? 'eager' : 'lazy'} decoding="async" className={`block h-full w-full object-contain object-center${isFlagShadesArtwork ? ' grayscale' : ''}`} />
            ))}
          </span>
        </span>
      );
    }
    const fallbackImageUrl = game.artworkFallbackUrl;
    return (
      <span data-game-artwork-frame aria-hidden="true" className={`${frameClass} p-3`}>
        <img
          data-game-artwork="flag"
          src={game.artworkUrl}
          alt=""
          loading={featured ? 'eager' : 'lazy'}
          decoding="async"
          className="block max-h-full max-w-full min-h-0 object-contain object-center"
          onError={fallbackImageUrl ? (event) => {
            if (event.currentTarget.src !== fallbackImageUrl) event.currentTarget.src = fallbackImageUrl;
          } : undefined}
        />
      </span>
    );
  }
  return (
    <span data-game-artwork-frame className={frameClass}>
      <MapArtwork url={mapUrlForGame(game)} frame={mapFrameForGame(game)} variant={mapArtworkVariantForGame(game)} />
    </span>
  );
}
