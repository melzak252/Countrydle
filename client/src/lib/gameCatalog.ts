import { useEffect, useState } from 'react';
import { assetUrl, regionalSymbolGames, regionalSymbolLabels, regionalSymbolPath, regionalSymbolsService } from '../services/api';
import { isPrerenderCapture } from './pageMetadata';
import type { RegionalSymbolScope } from '../types';
import { MAP_QUIZ_PATHS } from './mapGameMode';

export interface AvailableRegionalGame {
  scope: RegionalSymbolScope;
  flags: boolean;
  count: number;
  artworkUrl?: string;
}

export function useAvailableRegionalGames(): AvailableRegionalGame[] {
  const [available, setAvailable] = useState<AvailableRegionalGame[]>([]);
  useEffect(() => {
    if (isPrerenderCapture()) return;
    let active = true;
    void Promise.all(regionalSymbolGames.map(async (game) => {
      try {
        const catalog = await regionalSymbolsService(game.scope, game.flags).getCatalog();
        if (catalog.length < 2) return null;
        // Prefer the centered, versioned thumbnail; older catalog entries may only include the full asset.
        const representativeAsset = catalog[0].thumbnail_asset_url || catalog[0].flag_asset_url;
        return {
          ...game,
          count: catalog.length,
          ...(representativeAsset ? { artworkUrl: assetUrl(representativeAsset) } : {}),
        };
      } catch {
        return null;
      }
    })).then((games) => {
      if (active) setAvailable(games.filter((game): game is AvailableRegionalGame => game !== null));
    });
    return () => { active = false; };
  }, []);
  return available;
}

export type CatalogGeography = 'worldwide' | 'continents' | 'poland' | 'united-states' | 'uk';

interface CatalogGame {
  path: string;
  name: string;
  geography: CatalogGeography;
  artworkUrls?: readonly string[];
  artworkUrl?: string;
  artworkFallbackUrl?: string;
  primary?: number;
}
export type CatalogGroupId = 'true-false' | 'daily' | 'quizzes' | 'map-quizzes' | 'more';

interface CatalogGroup {
  id: CatalogGroupId;
  title: string;
  games: CatalogGame[];
}

const worldFlagSamples = [
  'https://flagcdn.com/w320/jp.png',
  'https://flagcdn.com/w320/br.png',
  'https://flagcdn.com/w320/za.png',
  'https://flagcdn.com/w320/se.png',
] as const;
const countyFlagArtworkUrl = assetUrl('/powiatdle/flags/thumbnails/1?v=bed7cd48ef9547b227dd942429cee042ef10e7279d5cf367a3640857ab9770e3');
const countyFlagArtworkFallbackUrl = 'https://upload.wikimedia.org/wikipedia/commons/8/82/POL_Bia%C5%82a_Podlaska_flag.svg';

export const gameCatalog: CatalogGroup[] = [
  { id: 'true-false', title: 'True / False games', games: [
    { path: '/game', name: 'Countrydle', geography: 'worldwide', primary: 1 },
    { path: '/us-states', name: 'US Statedle', geography: 'united-states', primary: 4 },
    { path: '/europe', name: 'Europedle', geography: 'continents' },
    { path: '/asia', name: 'Asiadle', geography: 'continents' },
    { path: '/africa', name: 'Africadle', geography: 'continents' },
    { path: '/americas', name: 'Americadle', geography: 'continents' },
    { path: '/wojewodztwa', name: 'Województwodle', geography: 'poland' },
    { path: '/powiaty', name: 'Powiatdle', geography: 'poland' },
  ] },
  { id: 'daily', title: 'Daily guessing', games: [
    { path: '/flagdle', name: 'Flagdle', geography: 'worldwide', artworkUrls: worldFlagSamples, primary: 2 },
    { path: '/flag-shades', name: 'Flag Shades', geography: 'worldwide', artworkUrls: worldFlagSamples, primary: 3 },
    { path: '/herby-powiatow', name: 'County Coats of Arms', geography: 'poland' },
    { path: '/flagi-powiatow', name: 'County Flags', geography: 'poland', artworkUrl: countyFlagArtworkUrl, artworkFallbackUrl: countyFlagArtworkFallbackUrl },
  ] },
  { id: 'quizzes', title: 'Quizzes', games: [
    { path: '/quiz-herbow', name: 'Coats of Arms Quiz', geography: 'poland' },
    { path: '/quiz-flag-powiatow', name: 'County Flags Quiz', geography: 'poland', artworkUrl: countyFlagArtworkUrl, artworkFallbackUrl: countyFlagArtworkFallbackUrl },
  ] },
  { id: 'map-quizzes', title: 'Map quizzes', games: [
    { path: MAP_QUIZ_PATHS.powiaty, name: 'Powiat Map Quiz', geography: 'poland' },
    { path: MAP_QUIZ_PATHS.us_states, name: 'US State Map Quiz', geography: 'united-states' },
  ] },
  { id: 'more', title: 'More ways to play', games: [
    { path: '/border-hop', name: 'Border Hop', geography: 'worldwide' },
    { path: '/friends', name: 'Friend duels', geography: 'worldwide' },
  ] },
];

// The primary navigation uses the same entries as the complete directory.
export const primaryGames = gameCatalog.flatMap(({ games }) => games)
  .filter((game) => game.primary !== undefined)
  .sort((a, b) => (a.primary ?? 0) - (b.primary ?? 0));

export function useGameCatalog(): CatalogGroup[] {
  const available = useAvailableRegionalGames();
  if (!available.length) return gameCatalog;
  const daily: CatalogGame[] = [];
  const quizzes: CatalogGame[] = [];
  for (const { scope, flags, count, artworkUrl } of available) {
    const path = regionalSymbolPath(scope, flags);
    const name = `${regionalSymbolLabels[scope]} ${flags ? 'Flags' : 'Coats of Arms'}`;
    const geography: CatalogGeography = scope === 'voivodeships' ? 'poland' : 'uk';
    daily.push({ path, name: `${name} (${count})`, geography, artworkUrl });
    quizzes.push({ path: `${path}/quiz`, name: `${name} Quiz (${count})`, geography, artworkUrl });
  }
  return gameCatalog.map((group) => group.id === 'daily'
    ? { ...group, games: [...group.games, ...daily] }
    : group.id === 'quizzes'
      ? { ...group, games: [...group.games, ...quizzes] }
      : group);
}
