import { useState, useEffect } from 'react';
import { gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
import { Loader2, Globe, Map, Flag, MapPin } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

type GameType = 'country' | 'powiat' | 'us_state' | 'wojewodztwo';
type LeaderboardType = 'monthly' | 'average';

interface LeaderboardEntry {
  id: number;
  username: string;
  points?: number;
  wins?: number;
  average_points?: number;
  games_played?: number;
}

export default function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [gameType, setGameType] = useState<GameType>('country');
  const [leaderboardType, setLeaderboardType] = useState<LeaderboardType>('monthly');
  const { t } = useTranslation();

  useEffect(() => {
    setLoading(true);
    const fetchLeaderboard = async () => {
      try {
        let data = [];
        if (gameType === 'country') data = await gameService.getLeaderboard(leaderboardType);
        else if (gameType === 'powiat') data = await powiatService.getLeaderboard(leaderboardType);
        else if (gameType === 'us_state') data = await usStateService.getLeaderboard(leaderboardType);
        else if (gameType === 'wojewodztwo') data = await wojewodztwoService.getLeaderboard(leaderboardType);
        setLeaderboard(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchLeaderboard();
  }, [gameType, leaderboardType]);

  const tabs = [
    { id: 'country', label: t('tabs.countries'), icon: Globe },
    { id: 'powiat', label: t('tabs.powiaty'), icon: Map },
    { id: 'us_state', label: t('tabs.usStates'), icon: Flag },
    { id: 'wojewodztwo', label: t('tabs.wojewodztwa'), icon: MapPin },
  ] as const;

  return (
    <div className="mx-auto max-w-5xl pb-8">
      <header className="mb-8 border-b border-white/10 pb-6 md:pb-8">
        <p className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">The standings</p>
        <h1 className="font-serif text-4xl tracking-tight text-sand-100 md:text-5xl">{t('leaderboard.title')}</h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-zinc-400">Compare your deductions with the community. Choose a map and see who leads the way.</p>
      </header>

      <div role="group" aria-label="Game mode" className="mb-6 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setGameType(id)}
            aria-pressed={gameType === id}
            className={`flex min-h-12 items-center gap-2.5 rounded-sm border px-3 py-2.5 text-left text-sm transition-colors sm:px-4 ${gameType === id ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-300' : 'border-white/10 bg-obsidian-900 text-zinc-400 hover:border-white/25 hover:text-sand-100'}`}
          >
            <Icon size={16} className="shrink-0" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-base font-medium text-sand-100">{tabs.find(tab => tab.id === gameType)?.label}</h2>
        <div role="group" aria-label="Ranking period" className="inline-flex rounded-sm border border-white/15 p-1">
          {(['monthly', 'average'] as const).map(period => (
            <button
              key={period}
              type="button"
              onClick={() => setLeaderboardType(period)}
              aria-pressed={leaderboardType === period}
              className={`min-h-10 rounded-sm px-4 text-sm transition-colors ${leaderboardType === period ? 'bg-sand-100 text-obsidian-950' : 'text-zinc-400 hover:text-sand-100'}`}
            >
              {period === 'monthly' ? 'Monthly' : 'Average'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div role="status" className="flex min-h-64 items-center justify-center gap-3 border-y border-white/10 text-sm text-zinc-400">
          <Loader2 className="animate-spin text-emerald-400" size={20} aria-hidden="true" />
          Loading standings…
        </div>
      ) : (
        <div className="overflow-x-auto rounded-sm border border-white/10 bg-obsidian-900">
          <table className="w-full table-fixed text-left text-sm">
            <caption className="sr-only">{tabs.find(tab => tab.id === gameType)?.label} — {leaderboardType === 'monthly' ? 'monthly points and wins' : 'average points and games played'}</caption>
            <thead className="border-b border-white/10 text-xs text-zinc-400">
              <tr>
                <th scope="col" className="w-10 px-2 py-4 text-center font-medium sm:w-16 sm:px-4">#</th>
                <th scope="col" className="px-2 py-4 font-medium sm:px-4">{t('leaderboard.player')}</th>
                <th scope="col" className="w-24 px-2 py-4 text-right font-medium sm:w-36 sm:px-4">{leaderboardType === 'monthly' ? t('leaderboard.points') : 'Avg Points'}</th>
                <th scope="col" className="w-16 px-2 py-4 text-right font-medium sm:w-24 sm:px-4">{leaderboardType === 'monthly' ? t('leaderboard.wins') : 'Games'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {leaderboard.map((entry, index) => (
                <tr key={entry.id} className="transition-colors hover:bg-white/[0.03]">
                  <td className={`px-2 py-5 text-center font-mono tabular-nums sm:px-4 ${index === 0 ? 'text-emerald-300' : 'text-zinc-500'}`}>{index + 1}</td>
                  <td className="px-2 py-5 sm:px-4">
                    <Link to={`/profile/${entry.username}`} title={entry.username} className="flex min-w-0 items-center gap-3 font-medium text-sand-100 hover:text-emerald-300">
                      <span aria-hidden="true" className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-white/10 font-mono text-xs text-zinc-400 sm:flex">{entry.username.substring(0, 2).toUpperCase()}</span>
                      <span className="truncate">{entry.username}</span>
                    </Link>
                  </td>
                  <td className="px-2 py-5 text-right font-mono font-medium tabular-nums text-sand-100 sm:px-4">{leaderboardType === 'monthly' ? entry.points : entry.average_points}</td>
                  <td className="px-2 py-5 text-right font-mono tabular-nums text-zinc-400 sm:px-4">{leaderboardType === 'monthly' ? entry.wins : entry.games_played}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {leaderboard.length === 0 && <p className="px-5 py-12 text-center text-sm text-zinc-400">{t('leaderboard.empty')}</p>}
        </div>
      )}
    </div>
  );
}
