import { useEffect, useState } from 'react';
import { regionalSymbolGames, regionalSymbolLabels, regionalSymbolPath, regionalSymbolsService } from '../services/api';
import { isPrerenderCapture } from './pageMetadata';
import type { RegionalSymbolScope } from '../types';

export interface AvailableRegionalGame {
  scope: RegionalSymbolScope;
  flags: boolean;
  count: number;
}

export function useAvailableRegionalGames(): AvailableRegionalGame[] {
  const [available, setAvailable] = useState<AvailableRegionalGame[]>([]);
  useEffect(() => {
    if (isPrerenderCapture()) return;
    let active = true;
    void Promise.all(regionalSymbolGames.map(async (game) => {
      try {
        const catalog = await regionalSymbolsService(game.scope, game.flags).getCatalog();
        return catalog.length >= 2 ? { ...game, count: catalog.length } : null;
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
  primary?: number;
}

interface CatalogGroup {
  id: 'true-false' | 'daily' | 'quizzes' | 'more';
  title: string;
  games: CatalogGame[];
}

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
    { path: '/flagdle', name: 'Flagdle', geography: 'worldwide', primary: 2 },
    { path: '/flag-shades', name: 'Flag Shades', geography: 'worldwide', primary: 3 },
    { path: '/herby-powiatow', name: 'County Coats of Arms', geography: 'poland' },
    { path: '/flagi-powiatow', name: 'County Flags', geography: 'poland' },
  ] },
  { id: 'quizzes', title: 'Quizzes', games: [
    { path: '/quiz-herbow', name: 'Coats of Arms Quiz', geography: 'poland' },
    { path: '/quiz-flag-powiatow', name: 'County Flags Quiz', geography: 'poland' },
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
  for (const { scope, flags, count } of available) {
    const path = regionalSymbolPath(scope, flags);
    const name = `${regionalSymbolLabels[scope]} ${flags ? 'Flags' : 'Coats of Arms'}`;
    const geography: CatalogGeography = scope === 'voivodeships' ? 'poland' : 'uk';
    daily.push({ path, name: `${name} (${count})`, geography });
    quizzes.push({ path: `${path}/quiz`, name: `${name} Quiz (${count})`, geography });
  }
  return gameCatalog.map((group) => group.id === 'daily'
    ? { ...group, games: [...group.games, ...daily] }
    : group.id === 'quizzes'
      ? { ...group, games: [...group.games, ...quizzes] }
      : group);
}
