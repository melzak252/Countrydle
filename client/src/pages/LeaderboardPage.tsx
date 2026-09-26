import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, ChevronDown, Loader2, Search, Users } from 'lucide-react';
import type { LeaderboardEntry, LeaderboardPeriod } from '../types';
import { africaService, americasService, asiaService, europeService, flagdleService, gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
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
] as const;

type GameType = typeof GAME_MODES[number]['id'];
type RankedPlayer = { entry: LeaderboardEntry; rank: number };

async function loadLeaderboard(game: GameType, period: LeaderboardPeriod): Promise<LeaderboardEntry[]> {
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
    default: {
      const exhaustiveCheck: never = game;
      return exhaustiveCheck;
    }
  }
}

const numberFormat = new Intl.NumberFormat('en-US');
const averageFormat = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 });

export default function LeaderboardPage() {
  const [gameType, setGameType] = useState<GameType>('country');
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
  const gameLabel = GAME_MODES.find((mode) => mode.id === gameType)?.label ?? 'Leaderboard';
  const isContinentalGame = gameType === 'europe' || gameType === 'asia' || gameType === 'africa' || gameType === 'americas';
  const averageMinimum = isContinentalGame ? 3 : 5;
  const periodDescription = leaderboardType === 'monthly'
    ? 'Ranked by total points; wins break ties. Includes actual play during the current UTC calendar month.'
    : `Ranked by average points per completed game across all time. At least ${averageMinimum} completed games are required to qualify.`;

  useEffect(() => {
    if (!pendingFindMe.current) return;
    if (myRowRef.current) {
      myRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      myRowRef.current.focus({ preventScroll: true });
    }
    pendingFindMe.current = false;
  }, [findMeRequest, pagePlayers]);

  const changeGame = (game: GameType) => {
    setGameType(game);
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
    <div className="mx-auto max-w-5xl pb-8">
      <header className="mb-8 border-b border-white/10 pb-6 md:pb-8">
        <p className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">The standings</p>
        <h1 className="font-serif text-4xl tracking-tight text-sand-100 md:text-5xl">{t('leaderboard.title')}</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          Daily challenges, ranked. Find a player or jump straight to your own row. Friend games are just for fun — no points or rankings.
        </p>
      </header>

      <div className="mb-6 border-b border-white/10 pb-6">
        <label htmlFor="leaderboard-game" className="mb-2 block text-xs font-medium uppercase tracking-widest text-zinc-500">Choose a game</label>
        <div className="relative w-full sm:max-w-xs">
          <select
            id="leaderboard-game"
            value={gameType}
            onChange={(event) => changeGame(event.target.value as GameType)}
            className="min-h-12 w-full appearance-none rounded-sm border border-white/15 bg-obsidian-900 py-3 pl-4 pr-11 text-base font-medium text-sand-100 focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/20"
          >
            {(['World & flags', 'Continents', 'Regional'] as const).map((group) => (
              <optgroup key={group} label={group}>
                {GAME_MODES.filter((mode) => mode.group === group).map(({ id, label }) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <ChevronDown size={18} aria-hidden="true" className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-emerald-400" />
        </div>
      </div>

      <section aria-label={`${gameLabel} standings`}>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-medium text-sand-100">{gameLabel}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-400">{periodDescription}</p>
          </div>
          <div role="group" aria-label="Ranking period" className="inline-flex rounded-sm border border-white/15 p-1">
            {(['monthly', 'average'] as const).map((period) => (
              <button
                key={period}
                type="button"
                onClick={() => changePeriod(period)}
                aria-pressed={leaderboardType === period}
                className={`min-h-10 rounded-sm px-4 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 ${leaderboardType === period ? 'bg-sand-100 text-obsidian-950' : 'text-zinc-400 hover:text-sand-100'}`}
              >
                {period === 'monthly' ? 'Monthly' : 'Average'}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div role="status" aria-live="polite" className="flex min-h-64 items-center justify-center gap-3 border-y border-white/10 text-sm text-zinc-400">
            <Loader2 className="animate-spin text-emerald-400" size={20} aria-hidden="true" />
            Loading {gameLabel.toLocaleLowerCase()} standings…
          </div>
        ) : hasError ? (
          <div role="alert" className="flex min-h-48 flex-col items-center justify-center gap-4 border-y border-white/10 px-5 text-center">
            <p className="text-sm text-zinc-300">We couldn’t load these standings. Check your connection and try again.</p>
            <button
              type="button"
              onClick={() => setRequestGeneration((generation) => generation + 1)}
              className="min-h-11 rounded-sm border border-emerald-400/40 px-4 text-sm font-medium text-emerald-300 transition-colors hover:bg-emerald-400/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
            >
              Retry
            </button>
          </div>
        ) : currentData ? (
          <>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <label className="relative block w-full sm:max-w-sm">
                <span className="sr-only">Search players by username</span>
                <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => {
                    setSearchQuery(event.target.value);
                    setPage(1);
                    setFindMessage(null);
                  }}
                  placeholder="Search username"
                  className="min-h-12 w-full rounded-sm border border-white/15 bg-obsidian-900 py-2.5 pl-10 pr-3 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/20"
                />
              </label>
              {isAuthenticated && user && (
                <button
                  type="button"
                  onClick={findMe}
                  className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-sm border border-white/15 px-4 text-sm font-medium text-sand-100 transition-colors hover:border-emerald-400/40 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
                >
                  <Users size={16} aria-hidden="true" />
                  Find me
                </button>
              )}
            </div>
            {findMessage && <p role="status" className="mb-4 text-sm text-zinc-400">{findMessage}</p>}

            {rankedPlayers.length === 0 ? (
              <div className="flex min-h-48 flex-col items-center justify-center border-y border-white/10 px-5 text-center">
                <p className="text-sm text-zinc-300">
                  {hasSearch ? `No players match “${searchQuery.trim()}”.` : 'No eligible players yet for this leaderboard.'}
                </p>
                {hasSearch && (
                  <button type="button" onClick={() => setSearchQuery('')} className="mt-3 min-h-10 px-3 text-sm text-emerald-300 hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <>
                <div role="region" aria-label={`${gameLabel} leaderboard`} tabIndex={0} className="overflow-x-auto rounded-sm border border-white/10 bg-obsidian-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
                  <table className="w-full table-fixed text-left text-sm">
                    <caption className="sr-only">
                      {gameLabel} — {leaderboardType === 'monthly' ? 'monthly standings' : 'all-time average standings'}
                    </caption>
                    <thead className="border-b border-white/10 text-xs text-zinc-400">
                      <tr>
                        <th scope="col" className="w-10 px-2 py-4 text-center font-medium sm:w-16 sm:px-4">Rank</th>
                        <th scope="col" className="px-2 py-4 font-medium sm:px-4">Player</th>
                        <th scope="col" className="w-24 px-2 py-4 text-right font-medium sm:w-40 sm:px-4">
                          {leaderboardType === 'monthly' ? 'Points' : 'Avg points / game'}
                        </th>
                        <th scope="col" className="w-14 px-2 py-4 text-right font-medium sm:w-32 sm:px-4">
                          {leaderboardType === 'monthly' ? 'Wins' : 'Games'}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {pagePlayers.map((row) => {
                        const isMe = row.entry.id === currentUserId;
                        return (
                          <tr
                            key={row.entry.id}
                            ref={isMe ? myRowRef : undefined}
                            tabIndex={isMe ? -1 : undefined}
                            aria-current={isMe ? 'true' : undefined}
                            className={`transition-colors hover:bg-white/[0.03] ${isMe ? 'bg-emerald-400/[0.07] ring-1 ring-inset ring-emerald-400/25' : ''}`}
                          >
                            <td className={`px-2 py-5 text-center font-mono tabular-nums sm:px-4 ${row.rank === 1 ? 'text-emerald-300' : 'text-zinc-500'}`}>#{row.rank}</td>
                            <td className="px-2 py-5 sm:px-4">
                              <div className="flex min-w-0 items-center gap-2 sm:gap-3">
                                <span aria-hidden="true" className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-white/10 font-mono text-xs text-zinc-400 sm:flex">
                                  {row.entry.username.substring(0, 2).toUpperCase()}
                                </span>
                                <Link to={`/profile/${row.entry.username}`} title={row.entry.username} className="min-w-0 truncate font-medium text-sand-100 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
                                  {row.entry.username}
                                </Link>
                                {isMe && <span className="shrink-0 rounded-sm bg-emerald-400/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">You</span>}
                              </div>
                            </td>
                            <td className="px-2 py-5 text-right font-mono font-medium tabular-nums text-sand-100 sm:px-4">
                              {leaderboardType === 'monthly' ? numberFormat.format(row.entry.points) : averageFormat.format(row.entry.average_points)}
                              <span className="mt-1 block font-sans text-xs font-normal text-zinc-500">
                                {leaderboardType === 'average'
                                  ? `${numberFormat.format(row.entry.points)} total points`
                                  : `${numberFormat.format(row.entry.games_played)} games`}
                              </span>
                            </td>
                            <td className="px-2 py-5 text-right font-mono tabular-nums text-zinc-400 sm:px-4">
                              {numberFormat.format(leaderboardType === 'monthly' ? row.entry.wins : row.entry.games_played)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <p role="status" className="text-zinc-400">
                    Showing {firstVisibleResult}–{lastVisibleResult} of {numberFormat.format(rankedPlayers.length)} {rankedPlayers.length === 1 ? 'player' : 'players'}{hasSearch ? ' matching your search' : ''}. Global ranks are preserved.
                  </p>
                  {pageCount > 1 && (
                    <nav aria-label="Leaderboard pagination" className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.max(1, current - 1))}
                        disabled={visiblePage === 1}
                        aria-label="Previous page"
                        className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-white/15 px-3 text-zinc-300 hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <ArrowLeft size={15} aria-hidden="true" />
                        Previous
                      </button>
                      <span aria-current="page" className="px-2 text-zinc-300">Page {visiblePage} of {pageCount}</span>
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                        disabled={visiblePage === pageCount}
                        aria-label="Next page"
                        className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-white/15 px-3 text-zinc-300 hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-40"
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
