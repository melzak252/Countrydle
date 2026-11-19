import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, ChevronDown, Loader2, Search, Users } from 'lucide-react';
import type { LeaderboardEntry, LeaderboardPeriod, RegionalSymbolScope } from '../types';
import { africaService, americasService, asiaService, europeService, flagdleService, gameService, countyFlagsService, powiatHeraldryService, powiatService, regionalSymbolLabels, regionalSymbolPath, regionalSymbolsService, usStateService, wojewodztwoService } from '../services/api';
import { useAvailableRegionalGames } from '../lib/gameCatalog';
import { useAuthStore } from '../stores/authStore';

const PAGE_SIZE = 25;

const GAME_MODES = [
  { id: 'country', label: 'Countrydle', group: 'World & flags' },
  { id: 'flagdle', label: 'Flagdle', group: 'World & flags' },
  { id: 'europe', label: 'Europe', group: 'Continents' },
  { id: 'asia', label: 'Asia', group: 'Continents' },
  { id: 'africa', label: 'Africa', group: 'Continents' },
  { id: 'americas', label: 'Americas', group: 'Continents' },
  { id: 'us_state', label: 'US States', group: 'Regional' },
  { id: 'wojewodztwo', label: 'Polish Voivodeships', group: 'Regional' },
  { id: 'powiat', label: 'Powiatdle', group: 'Regional' },
  { id: 'heraldry', label: 'County Coats of Arms', group: 'Regional' },
  { id: 'county_flags', label: 'County Flags', group: 'Regional' },
] as const;

type GameType = typeof GAME_MODES[number]['id'] | `regional_symbols:${RegionalSymbolScope}:${'coat' | 'flag'}`;
type RankedPlayer = { entry: LeaderboardEntry; rank: number };

async function loadLeaderboard(game: GameType, period: LeaderboardPeriod): Promise<LeaderboardEntry[]> {
  if (game.startsWith('regional_symbols:')) {
    const [, scope, symbol] = game.split(':') as ['regional_symbols', RegionalSymbolScope, 'coat' | 'flag'];
    return regionalSymbolsService(scope, symbol === 'flag').getLeaderboard(period);
  }
  switch (game) {
    case 'country': return gameService.getLeaderboard(period);
    case 'powiat': return powiatService.getLeaderboard(period);
    case 'us_state': return usStateService.getLeaderboard(period);
    case 'wojewodztwo': return wojewodztwoService.getLeaderboard(period);
    case 'europe': return europeService.getLeaderboard(period);
    case 'asia': return asiaService.getLeaderboard(period);
    case 'africa': return africaService.getLeaderboard(period);
    case 'americas': return americasService.getLeaderboard(period);
    case 'flagdle': return flagdleService.getLeaderboard(period);
    case 'heraldry': return powiatHeraldryService.getLeaderboard(period);
    case 'county_flags': return countyFlagsService.getLeaderboard(period);
    default: throw new Error(`Unknown leaderboard: ${game}`);
  }
}

function formatNumber(value: number): string {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function formatAverage(value: number): string {
  const rounded = Math.round(value * 10) / 10 === value ? value.toFixed(1) : value.toFixed(2);
  const [intPart, decPart] = rounded.split('.');
  const spacedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return decPart !== undefined ? `${spacedInt}.${decPart}` : spacedInt;
}

export default function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const available = useAvailableRegionalGames();
  const regionalModes = available.map(({ scope, flags }) => ({
    id: `regional_symbols:${scope}:${flags ? 'flag' : 'coat'}` as GameType,
    label: `${regionalSymbolLabels[scope]} ${flags ? 'Flags' : 'Coats of Arms'}`,
    group: 'Regional' as const,
    path: regionalSymbolPath(scope, flags),
  }));
  const gameModes = [...GAME_MODES, ...regionalModes];
  const gameType = gameModes.find((mode) => mode.id === searchParams.get('mode'))?.id ?? 'country';
  const [leaderboardType, setLeaderboardType] = useState<LeaderboardPeriod>('monthly');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [requestGeneration, setRequestGeneration] = useState(0);
  const [findMeRequest, setFindMeRequest] = useState(0);
  const [findMessage, setFindMessage] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ key: string; data: LeaderboardEntry[] } | null>(null);
  const [loadState, setLoadState] = useState<{ key: string; status: 'ready' | 'error' } | null>(null);
  const myRowRef = useRef<HTMLTableRowElement>(null);
  const pendingFindMe = useRef(false);
  const { t } = useTranslation();
  const { user, isAuthenticated } = useAuthStore();
  const currentUserId = isAuthenticated ? user?.id : undefined;
  const requestKey = `${gameType}:${leaderboardType}:${requestGeneration}`;
  const currentData = loaded?.key === requestKey ? loaded.data : null;
  const currentStatus = loadState?.key === requestKey ? loadState.status : 'loading';

  useEffect(() => {
    let isCurrentRequest = true;

    loadLeaderboard(gameType, leaderboardType)
      .then((data) => {
        if (!isCurrentRequest) return;
        setLoaded({ key: requestKey, data });
        setLoadState({ key: requestKey, status: 'ready' });
      })
      .catch(() => {
        if (isCurrentRequest) setLoadState({ key: requestKey, status: 'error' });
      });

    return () => {
      isCurrentRequest = false;
    };
  }, [gameType, leaderboardType, requestKey]);

  const rankedPlayers = useMemo<RankedPlayer[]>(() => {
    if (!currentData) return [];
    const query = searchQuery.trim().toLocaleLowerCase();
    const ranked: RankedPlayer[] = [];

    currentData.forEach((entry, index) => {
      if (!query || entry.username.toLocaleLowerCase().includes(query)) {
        ranked.push({ entry, rank: index + 1 });
      }
    });
    return ranked;
  }, [currentData, searchQuery]);

  const pageCount = Math.max(1, Math.ceil(rankedPlayers.length / PAGE_SIZE));
  const visiblePage = Math.min(page, pageCount);
  const pagePlayers = useMemo(
    () => rankedPlayers.slice((visiblePage - 1) * PAGE_SIZE, visiblePage * PAGE_SIZE),
    [rankedPlayers, visiblePage],
  );
  const gameLabel = gameModes.find((mode) => mode.id === gameType)?.label ?? 'Leaderboard';
  const isContinentalGame = gameType === 'europe' || gameType === 'asia' || gameType === 'africa' || gameType === 'americas';
  const averageMinimum = isContinentalGame ? 3 : 5;
  const periodDescription = leaderboardType === 'monthly'
    ? 'Ranked by total points during the current UTC calendar month; wins break ties.'
    : `Ranked by average points per completed game during the current UTC calendar month. At least ${averageMinimum} completed games are required to qualify.`;

  useEffect(() => {
    if (!pendingFindMe.current) return;
    if (myRowRef.current) {
      myRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      myRowRef.current.focus({ preventScroll: true });
    }
    pendingFindMe.current = false;
  }, [findMeRequest, pagePlayers]);

  const changeGame = (game: GameType) => {
    const next = new URLSearchParams(searchParams);
    next.set('mode', game);
    setSearchParams(next);
    setPage(1);
    setRequestGeneration((generation) => generation + 1);
    setFindMessage(null);
  };

  const changePeriod = (period: LeaderboardPeriod) => {
    setLeaderboardType(period);
    setPage(1);
    setRequestGeneration((generation) => generation + 1);
    setFindMessage(null);
  };

  const findMe = () => {
    if (currentUserId === undefined || !currentData) return;
    const playerIndex = currentData.findIndex((entry) => entry.id === currentUserId);
    setSearchQuery('');
    setFindMessage(null);
    if (playerIndex < 0) {
      setPage(1);
      setFindMessage("You aren't listed on this leaderboard.");
      return;
    }
    pendingFindMe.current = true;
    setPage(Math.floor(playerIndex / PAGE_SIZE) + 1);
    setFindMeRequest((request) => request + 1);
  };

  const isLoading = currentStatus === 'loading';
  const hasError = currentStatus === 'error';
  const hasSearch = searchQuery.trim().length > 0;
  const firstVisibleResult = rankedPlayers.length === 0 ? 0 : (visiblePage - 1) * PAGE_SIZE + 1;
  const lastVisibleResult = Math.min(visiblePage * PAGE_SIZE, rankedPlayers.length);

  return (
    <div className="mx-auto max-w-5xl pb-8 text-app-text">
      <header className="mb-8 border-b border-app-border pb-6 md:pb-8">
        <p className="mb-3 font-mono text-xs text-app-accent">The standings</p>
        <h1 className="font-serif text-4xl tracking-tight text-app-text md:text-5xl">{t('leaderboard.title')}</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-app-text-secondary">
          Daily challenges, ranked. Find a player or jump straight to your own row. Friend games are just for fun — no points or rankings.
        </p>
        {gameType === 'heraldry' && <Link to="/herby-powiatow" className="mt-3 inline-block text-sm text-app-accent underline">Play County Coats of Arms</Link>}
        {gameType === 'county_flags' && <Link to="/flagi-powiatow" className="mt-3 inline-block text-sm text-app-accent underline">Play County Flags</Link>}
        {regionalModes.filter((mode) => mode.id === gameType).map((mode) => <Link key={mode.id} to={mode.path} className="mt-3 inline-block text-sm text-app-accent underline">Play {mode.label}</Link>)}
      </header>

      <div className="mb-6 border-b border-app-border pb-6">
        <label htmlFor="leaderboard-game" className="mb-2 block text-xs font-medium text-app-text-muted">Choose a game</label>
        <div className="relative w-full sm:max-w-xs">
          <select
            id="leaderboard-game"
            value={gameType}
            onChange={(event) => changeGame(event.target.value as GameType)}
            className="min-h-12 w-full appearance-none rounded-sm border border-app-border bg-app-surface py-3 pl-4 pr-11 text-base font-medium text-app-text focus:border-app-focus focus:outline-none focus:ring-2 focus:ring-app-focus"
          >
            {(['World & flags', 'Continents', 'Regional'] as const).map((group) => (
              <optgroup key={group} label={group}>
                {gameModes.filter((mode) => mode.group === group).map(({ id, label }) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <ChevronDown size={18} aria-hidden="true" className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-app-accent" />
        </div>
      </div>

      <section aria-label={`${gameLabel} standings`}>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-medium text-app-text">{gameLabel}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-app-text-secondary">{periodDescription}</p>
          </div>
          <div role="group" aria-label="Ranking period" className="inline-flex rounded-sm border border-app-border p-1">
            {(['monthly', 'average'] as const).map((period) => (
              <button
                key={period}
                type="button"
                onClick={() => changePeriod(period)}
                aria-pressed={leaderboardType === period}
                className={`min-h-11 rounded-sm px-4 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${leaderboardType === period ? 'bg-app-accent text-app-canvas' : 'text-app-text-secondary hover:text-app-accent'}`}
              >
                {period === 'monthly' ? 'Monthly' : 'Average'}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div role="status" aria-live="polite" className="flex min-h-64 items-center justify-center gap-3 border-y border-app-border text-sm text-app-text-muted">
            <Loader2 className="animate-spin text-app-accent" size={20} aria-hidden="true" />
            Loading {gameLabel.toLocaleLowerCase()} standings…
          </div>
        ) : hasError ? (
          <div role="alert" className="flex min-h-48 flex-col items-center justify-center gap-4 border-y border-app-border px-5 text-center">
            <p className="text-sm text-app-text-secondary">We couldn’t load these standings. Check your connection and try again.</p>
            <button
              type="button"
              onClick={() => setRequestGeneration((generation) => generation + 1)}
              className="min-h-11 rounded-sm border border-app-accent px-4 text-sm font-medium text-app-accent transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
            >
              Retry
            </button>
          </div>
        ) : currentData ? (
          <>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <label className="relative block w-full sm:max-w-sm">
                <span className="sr-only">Search players by username</span>
                <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => {
                    setSearchQuery(event.target.value);
                    setPage(1);
                    setFindMessage(null);
                  }}
                  placeholder="Search username"
                  className="min-h-12 w-full rounded-sm border border-app-border bg-app-surface py-2.5 pl-10 pr-3 text-base text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none focus:ring-2 focus:ring-app-focus"
                />
              </label>
              {isAuthenticated && user && (
                <button
                  type="button"
                  onClick={findMe}
                  className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-sm border border-app-border px-4 text-sm font-medium text-app-text transition-colors hover:border-app-accent hover:text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                  <Users size={16} aria-hidden="true" />
                  Find me
                </button>
              )}
            </div>
            {findMessage && <p role="status" className="mb-4 text-sm text-app-text-secondary">{findMessage}</p>}

            {rankedPlayers.length === 0 ? (
              <div className="flex min-h-48 flex-col items-center justify-center border-y border-app-border px-5 text-center">
                <p className="text-sm text-app-text-secondary">
                  {hasSearch ? `No players match “${searchQuery.trim()}”.` : 'No eligible players yet for this leaderboard.'}
                </p>
                {hasSearch && (
                  <button type="button" onClick={() => setSearchQuery('')} className="mt-3 min-h-10 px-3 text-sm text-app-accent hover:text-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <>
                <div role="region" aria-label={`${gameLabel} leaderboard`} tabIndex={0} className="overflow-hidden rounded-sm border border-app-border bg-app-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus md:overflow-x-auto">
                  <table className="w-full min-w-0 table-fixed text-left text-sm md:min-w-[600px]">
                    <caption className="sr-only">
                      {gameLabel} — {leaderboardType === 'monthly' ? 'monthly points standings' : 'monthly average standings'}
                    </caption>
                    <thead className="border-b border-app-border text-xs text-app-text-muted">
                      <tr>
                        <th scope="col" className="w-12 px-2 py-3.5 text-center font-medium sm:w-16 sm:px-3">Rank</th>
                        <th scope="col" className="px-2 py-3.5 font-medium sm:px-3">Player</th>
                        <th
                          scope="col"
                          className={`w-24 px-2 py-3.5 text-right font-medium sm:w-28 sm:px-3 ${
                            leaderboardType === 'monthly' ? 'text-emerald-400' : ''
                          }`}
                        >
                          Points{leaderboardType === 'monthly' ? ' ★' : ''}
                        </th>
                        <th
                          scope="col"
                          className={`hidden w-24 px-2 py-3.5 text-right font-medium sm:w-28 sm:px-3 md:table-cell ${
                            leaderboardType === 'average' ? 'text-emerald-400' : ''
                          }`}
                        >
                          Avg / Game{leaderboardType === 'average' ? ' ★' : ''}
                        </th>
                        <th scope="col" className="hidden w-16 px-2 py-3.5 text-right font-medium sm:w-20 sm:px-3 md:table-cell">
                          Games
                        </th>
                        <th scope="col" className="hidden w-14 px-2 py-3.5 text-right font-medium sm:w-20 sm:px-3 md:table-cell">
                          Wins
                        </th>
                        <th scope="col" className="hidden w-16 px-2 py-3.5 text-right font-medium sm:w-24 sm:px-3 md:table-cell">
                          Win %
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-app-border">
                      {pagePlayers.map((row) => {
                        const isMe = row.entry.id === currentUserId;
                        const winRate = row.entry.games_played > 0
                          ? Math.round((row.entry.wins / row.entry.games_played) * 100)
                          : 0;
                        return (
                          <tr
                            key={row.entry.id}
                            ref={isMe ? myRowRef : undefined}
                            tabIndex={isMe ? -1 : undefined}
                            aria-current={isMe ? 'true' : undefined}
                            className={`transition-colors hover:bg-app-surface-muted ${isMe ? 'bg-app-surface-muted ring-1 ring-inset ring-app-accent' : ''}`}
                          >
                            <td className={`px-2 py-4 text-center font-mono tabular-nums sm:px-3 ${row.rank === 1 ? 'text-app-accent' : 'text-app-text-muted'}`}>
                              #{row.rank}
                            </td>
                            <td className="px-2 py-4 sm:px-3">
                              <div className="flex min-w-0 items-center gap-2 sm:gap-3">
                                <span aria-hidden="true" className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-app-border font-mono text-xs text-app-text-muted sm:flex">
                                  {row.entry.username.substring(0, 2).toUpperCase()}
                                </span>
                                <Link to={`/profile/${row.entry.username}`} title={row.entry.username} className="min-w-0 break-words font-medium text-app-text hover:text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">
                                  {row.entry.username}
                                </Link>
                                {isMe && <span className="shrink-0 rounded-sm bg-app-surface-muted px-1.5 py-0.5 text-xs font-semibold text-app-accent">You</span>}
                              </div>
                              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-app-text-muted md:hidden">
                                <span>Avg / Game <span className="font-mono tabular-nums text-app-text-secondary">{formatAverage(row.entry.average_points)}</span></span>
                                <span>Games <span className="font-mono tabular-nums text-app-text-secondary">{formatNumber(row.entry.games_played)}</span></span>
                                <span>Wins <span className="font-mono tabular-nums text-app-text-secondary">{formatNumber(row.entry.wins)}</span></span>
                                <span>Win % <span className="font-mono tabular-nums text-app-text-secondary">{winRate}%</span></span>
                              </div>
                            </td>
                            <td className={`px-2 py-4 text-right font-mono tabular-nums sm:px-3 ${
                              leaderboardType === 'monthly' ? 'font-semibold text-app-accent' : 'text-app-text'
                            }`}>
                              {formatNumber(row.entry.points)}
                            </td>
                            <td className={`hidden px-2 py-4 text-right font-mono tabular-nums sm:px-3 md:table-cell ${
                              leaderboardType === 'average' ? 'font-semibold text-app-accent' : 'text-app-text-secondary'
                            }`}>
                              {formatAverage(row.entry.average_points)}
                            </td>
                            <td className="hidden px-2 py-4 text-right font-mono tabular-nums text-app-text-secondary sm:px-3 md:table-cell">
                              {formatNumber(row.entry.games_played)}
                            </td>
                            <td className="hidden px-2 py-4 text-right font-mono tabular-nums text-app-text-secondary sm:px-3 md:table-cell">
                              {formatNumber(row.entry.wins)}
                            </td>
                            <td className="hidden px-2 py-4 text-right font-mono tabular-nums text-app-text-muted sm:px-3 md:table-cell">
                              {winRate}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <p role="status" className="text-app-text-muted">
                    Showing {firstVisibleResult}–{lastVisibleResult} of {formatNumber(rankedPlayers.length)} {rankedPlayers.length === 1 ? 'player' : 'players'}{hasSearch ? ' matching your search' : ''}. Global ranks are preserved.
                  </p>
                  {pageCount > 1 && (
                    <nav aria-label="Leaderboard pagination" className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.max(1, current - 1))}
                        disabled={visiblePage === 1}
                        aria-label="Previous page"
                        className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-app-border px-3 text-app-text-secondary hover:border-app-accent disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <ArrowLeft size={15} aria-hidden="true" />
                        Previous
                      </button>
                      <span aria-current="page" className="px-2 text-app-text-secondary">Page {visiblePage} of {pageCount}</span>
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                        disabled={visiblePage === pageCount}
                        aria-label="Next page"
                        className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-app-border px-3 text-app-text-secondary hover:border-app-accent disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Next
                        <ArrowRight size={15} aria-hidden="true" />
                      </button>
                    </nav>
                  )}
                </div>
              </>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}
