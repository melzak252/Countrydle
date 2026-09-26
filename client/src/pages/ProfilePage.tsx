import { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { gameService, authService } from '../services/api';
import { ArrowLeft, CalendarDays, ChevronDown, Loader2, Trophy, Target, Edit2, Check, X, Flame, Percent, Sparkles } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

const GAME_GROUPS = [
  { label: 'profile.world', modes: [{ id: 'countrydle', label: 'tabs.countries' }, { id: 'flagdle', label: 'profile.flagdle' }] },
  { label: 'profile.continents', modes: [{ id: 'europe', label: 'profile.europe' }, { id: 'asia', label: 'profile.asia' }, { id: 'africa', label: 'profile.africa' }, { id: 'americas', label: 'profile.americas' }] },
  { label: 'profile.regional', modes: [{ id: 'powiatdle', label: 'tabs.powiaty' }, { id: 'us_statedle', label: 'tabs.usStates' }, { id: 'wojewodztwodle', label: 'tabs.wojewodztwa' }] },
] as const;
type DailyMode = typeof GAME_GROUPS[number]['modes'][number];
const DAILY_MODES = GAME_GROUPS.flatMap<DailyMode>(group => group.modes);
type GameMode = DailyMode['id'];
type ProfileTab = GameMode | 'friend_matches';
type GameStats = {
  points: number;
  wins: number;
  games_played: number;
  streak: number;
  completed_games: number;
  win_rate: number;
  best_streak: number;
  average_points: number;
  average_winning_guesses: number;
  history: { date: string; won: boolean; points: number; attempts: number; target_name: string }[];
};
type FriendMatchStats = {
  games_played: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  history: { id: string; finished_at: string; mode: string; outcome: 'won' | 'lost' | 'draw' }[];
};
type ProfileStats = Record<GameMode, GameStats> & {
  friend_matches: FriendMatchStats;
  user: { id: number; username: string; created_at: string | null };
};

const focusStyle = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400';

export default function ProfilePage() {
  const { username } = useParams();
  const navigate = useNavigate();
  const { user: currentUser, setUser } = useAuthStore();
  const { t, i18n } = useTranslation();
  const [loaded, setLoaded] = useState<{ username: string; data: ProfileStats } | null>(null);
  const [failure, setFailure] = useState<{ username: string; notFound: boolean } | null>(null);
  const [reload, setReload] = useState(0);
  const [activeTab, setActiveTab] = useState<ProfileTab>('countrydle');
  const [isEditing, setIsEditing] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [updateLoading, setUpdateLoading] = useState(false);
  const stats = loaded && loaded.username === username ? loaded.data : null;
  const error = failure?.username === username ? failure : null;
  const isOwnProfile = Boolean(stats && currentUser?.id === stats.user.id);
  const formatNumber = (value: number) => value.toLocaleString(i18n.language);

  useEffect(() => {
    if (!username) return;
    let current = true;
    setLoaded(null);
    setFailure(null);
    setIsEditing(false);
    gameService.getUserProfileStats(username)
      .then((data: ProfileStats) => {
        if (!current) return;
        setLoaded({ username, data });
        setNewUsername(data.user.username);
      })
      .catch((error: unknown) => {
        if (current) setFailure({ username, notFound: isAxiosError(error) && error.response?.status === 404 });
      });
    return () => { current = false; };
  }, [username, reload]);

  const handleUpdateUsername = async () => {
    if (!stats || !currentUser || !isOwnProfile || updateLoading) return;
    const trimmed = newUsername.trim();
    if (!trimmed) return;
    if (trimmed === stats.user.username) {
      setIsEditing(false);
      return;
    }
    setUpdateLoading(true);
    try {
      await authService.updateProfile({ username: trimmed, email: currentUser.email });
      setUser({ ...currentUser, username: trimmed });
      setIsEditing(false);
      toast.success(t('profile.updateSuccess'));
      navigate(`/profile/${encodeURIComponent(trimmed)}`, { replace: true });
    } catch (error: unknown) {
      const detail = isAxiosError<{ detail?: unknown }>(error) ? error.response?.data.detail : undefined;
      toast.error(typeof detail === 'string' ? detail : t('profile.updateError'));
    } finally {
      setUpdateLoading(false);
    }
  };

  if (error || !username) return (
    <section className="mx-auto max-w-5xl border-y border-white/10 py-20 text-center" role="alert">
      <h1 className="font-serif text-3xl text-sand-100">{t(error?.notFound || !username ? 'profile.userNotFound' : 'profile.loadError')}</h1>
      <div className="mt-6 flex justify-center gap-6 text-sm">
        {error && !error.notFound && <button type="button" onClick={() => setReload(value => value + 1)} className={`text-emerald-300 ${focusStyle}`}>{t('profile.retry')}</button>}
        <Link to="/leaderboard" className={`text-zinc-400 hover:text-sand-100 ${focusStyle}`}>{t('leaderboard.title')}</Link>
      </div>
    </section>
  );

  if (!stats) return (
    <div role="status" className="flex min-h-80 items-center justify-center gap-3 text-sm text-zinc-400">
      <Loader2 className="animate-spin text-emerald-400" size={22} aria-hidden="true" />
      {t('profile.loading')}
    </div>
  );

  const friendStats = activeTab === 'friend_matches' ? stats.friend_matches : null;
  const currentStats = activeTab === 'friend_matches' ? null : stats[activeTab];
  const modeLabel = activeTab === 'friend_matches'
    ? t('profile.friendMatches')
    : t(DAILY_MODES.find(mode => mode.id === activeTab)!.label);
  const metrics = currentStats ? [
    { label: t('profile.totalPoints'), value: formatNumber(currentStats.points), icon: Trophy },
    { label: t('profile.totalWins'), value: formatNumber(currentStats.wins), icon: Check },
    { label: t('profile.gamesPlayed'), value: formatNumber(currentStats.games_played), icon: Target },
    { label: t('profile.winRate'), value: `${Math.round(currentStats.win_rate * 100)}%`, detail: t('profile.completedGames', { count: currentStats.completed_games }), icon: Percent },
    { label: t('profile.currentStreak'), value: formatNumber(currentStats.streak), icon: Flame },
    { label: t('profile.bestStreak'), value: formatNumber(currentStats.best_streak), icon: Flame },
    { label: t('profile.averagePoints'), value: formatNumber(currentStats.average_points), icon: Trophy },
    { label: t('profile.averageWinningGuesses'), value: formatNumber(currentStats.average_winning_guesses), icon: Target },
  ] : [
    { label: t('profile.matchesPlayed'), value: formatNumber(friendStats!.games_played), icon: Target },
    { label: t('profile.matchWins'), value: formatNumber(friendStats!.wins), icon: Check },
    { label: t('profile.matchLosses'), value: formatNumber(friendStats!.losses), icon: X },
    { label: t('profile.matchDraws'), value: formatNumber(friendStats!.draws), icon: Sparkles },
    { label: t('profile.matchWinRate'), value: `${Math.round(friendStats!.win_rate * 100)}%`, icon: Percent },
  ];

  return (
    <div className="mx-auto min-w-0 max-w-5xl pb-12">
      <Link to="/leaderboard" className={`mb-8 inline-flex min-h-10 items-center gap-2 text-sm text-zinc-400 transition-colors hover:text-emerald-300 ${focusStyle}`}>
        <ArrowLeft size={15} aria-hidden="true" />{t('leaderboard.title')}
      </Link>

      <header className="border-b border-white/10 pb-8 sm:pb-10">
        <p className="mb-6 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">{t('profile.playerProfile')}</p>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-6">
          <div aria-hidden="true" className="flex h-20 w-20 shrink-0 items-center justify-center rounded-sm border border-emerald-400/25 bg-emerald-400/[0.06] font-serif text-3xl text-emerald-300 sm:h-24 sm:w-24 sm:text-4xl">
            {stats.user.username.substring(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            {isEditing && isOwnProfile ? (
              <form onSubmit={event => { event.preventDefault(); void handleUpdateUsername(); }} className="max-w-xl">
                <label htmlFor="profile-username" className="mb-2 block text-xs text-zinc-400">{t('profile.editNickname')}</label>
                <div className="flex gap-2">
                  <input id="profile-username" autoFocus required value={newUsername} disabled={updateLoading} onChange={event => setNewUsername(event.target.value)} className="min-h-12 min-w-0 flex-1 rounded-sm border border-white/20 bg-obsidian-900 px-3 text-base text-sand-100 focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/20" />
                  <button type="submit" disabled={updateLoading || !newUsername.trim()} aria-label={t('profile.save')} className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-sm bg-emerald-400 text-obsidian-950 hover:bg-emerald-300 disabled:opacity-40 ${focusStyle}`}>
                    {updateLoading ? <Loader2 size={19} className="animate-spin" aria-hidden="true" /> : <Check size={19} aria-hidden="true" />}
                  </button>
                  <button type="button" disabled={updateLoading} aria-label={t('profile.cancel')} onClick={() => { setIsEditing(false); setNewUsername(stats.user.username); }} className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-sm border border-white/15 text-zinc-400 hover:text-sand-100 disabled:opacity-40 ${focusStyle}`}><X size={19} aria-hidden="true" /></button>
                </div>
                <p className="mt-2 text-xs leading-5 text-zinc-500">{t('profile.usernameChangeInfo')}</p>
              </form>
            ) : (
              <div className="flex items-start gap-3">
                <h1 className="min-w-0 break-words font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">{stats.user.username || t('profile.anonymous')}</h1>
                {isOwnProfile && <button type="button" onClick={() => setIsEditing(true)} aria-label={t('profile.editNickname')} className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-sm border border-white/10 text-zinc-400 hover:border-emerald-400/40 hover:text-emerald-300 ${focusStyle}`}><Edit2 size={16} aria-hidden="true" /></button>}
              </div>
            )}
            {stats.user.created_at && <p className="mt-3 flex items-center gap-2 text-sm text-zinc-400"><CalendarDays size={14} className="shrink-0 text-zinc-500" aria-hidden="true" />{t('profile.memberSince', { date: new Date(stats.user.created_at).toLocaleDateString(i18n.language, { month: 'long', year: 'numeric' }) })}</p>}
          </div>
          {isOwnProfile && <span className="self-start rounded-sm border border-emerald-400/20 px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest text-emerald-300 sm:self-center">{t('profile.yourProfile')}</span>}
        </div>
      </header>

      <section aria-label={t('profile.gameStatistics')} className="py-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div><h2 className="font-serif text-2xl text-sand-100">{t('profile.gameStatistics')}</h2><p className="mt-2 max-w-xl text-sm leading-6 text-zinc-400">{t(friendStats ? 'profile.friendMatchesInfo' : 'profile.statisticsDescription')}</p></div>
          <div className="w-full sm:w-64">
            <label htmlFor="profile-game" className="mb-2 block text-xs text-zinc-400">{t('profile.chooseGame')}</label>
            <div className="relative">
              <select id="profile-game" value={activeTab} onChange={event => setActiveTab(event.target.value as ProfileTab)} className="min-h-12 w-full appearance-none rounded-sm border border-white/15 bg-obsidian-900 py-3 pl-4 pr-10 text-sm text-sand-100 focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/20">
                {GAME_GROUPS.map(group => <optgroup key={group.label} label={t(group.label)}>{group.modes.map(mode => <option key={mode.id} value={mode.id}>{t(mode.label)}</option>)}</optgroup>)}
                <optgroup label={t('profile.justForFun')}><option value="friend_matches">{t('profile.friendMatches')}</option></optgroup>
              </select>
              <ChevronDown size={16} aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-emerald-400" />
            </div>
          </div>
        </div>
        <dl className={`grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-white/10 bg-white/10 ${currentStats ? 'md:grid-cols-4' : 'lg:grid-cols-5'}`}>
          {metrics.map((metric) => (
            <div key={metric.label} className={`min-w-0 bg-obsidian-900 p-4 sm:p-6 ${friendStats ? 'last:col-span-2 lg:last:col-span-1' : ''}`}>
              <dt className="flex min-h-8 items-center gap-2 text-xs text-zinc-400"><metric.icon size={14} className="shrink-0 text-emerald-400/80" aria-hidden="true" />{metric.label}</dt>
              <dd className="mt-4 break-words font-mono text-2xl tabular-nums tracking-tight text-sand-100 sm:text-3xl">{metric.value}</dd>
              {'detail' in metric && metric.detail && <dd className="mt-2 text-xs text-zinc-500">{metric.detail}</dd>}
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="profile-history-title">
        <h2 id="profile-history-title" className="mb-5 font-serif text-2xl text-sand-100">{t(activeTab === 'friend_matches' ? 'profile.recentFriendMatches' : 'profile.recentGames', { mode: modeLabel })}</h2>
        {currentStats && (currentStats.history.length > 0 ? (
          <ul className="divide-y divide-white/10 overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
            {currentStats.history.map((game, index) => (
              <li key={`${game.date}-${index}`} className="flex items-center gap-3 px-4 py-5 sm:gap-5 sm:px-6">
                <span className={`hidden h-9 w-9 shrink-0 items-center justify-center rounded-sm border sm:flex ${game.won ? 'border-emerald-400/20 bg-emerald-400/[0.05] text-emerald-400' : 'border-white/10 text-zinc-500'}`} aria-hidden="true">{game.won ? <Check size={16} /> : <X size={16} />}</span>
                <div className="min-w-0 flex-1">
                  <time dateTime={game.date} className="font-mono text-xs text-zinc-500">{game.date}</time>
                  <p className="mt-1 break-words text-sm font-medium text-sand-100">{game.target_name === '???' ? t('profile.hiddenAnswer') : game.target_name}</p>
                  <p className="mt-1 text-xs text-zinc-500"><span className={game.won ? 'text-emerald-400' : 'text-zinc-400'}>{t(game.won ? 'profile.won' : 'profile.lost')}</span><span aria-hidden="true"> · </span>{t('profile.attempts', { count: game.attempts })}</p>
                </div>
                <p className={`max-w-[45%] break-words text-right font-mono text-sm tabular-nums sm:text-lg ${game.won ? 'text-emerald-300' : 'text-zinc-400'}`}>{t('profile.points', { points: formatNumber(game.points) })}</p>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-center gap-3 rounded-sm border border-dashed border-white/15 py-14 text-center text-sm text-zinc-400"><Target size={24} className="text-emerald-400/60" aria-hidden="true" /><p>{t('profile.noGames')}</p></div>
        ))}
        {friendStats && (friendStats.history.length > 0 ? (
          <ul className="divide-y divide-white/10 overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
            {friendStats.history.map(match => (
              <li key={match.id} className="flex items-center gap-3 px-4 py-5 sm:gap-5 sm:px-6">
                <span className={`hidden h-9 w-9 shrink-0 items-center justify-center rounded-sm border sm:flex ${match.outcome === 'won' ? 'border-emerald-400/20 bg-emerald-400/[0.05] text-emerald-400' : 'border-white/10 text-zinc-500'}`} aria-hidden="true">{match.outcome === 'won' ? <Check size={16} /> : match.outcome === 'lost' ? <X size={16} /> : <Sparkles size={15} />}</span>
                <div className="min-w-0 flex-1">
                  <time dateTime={match.finished_at} className="font-mono text-xs text-zinc-500">{new Date(match.finished_at).toLocaleString(i18n.language)}</time>
                  <p className="mt-1 text-sm font-medium text-sand-100">{t(`profile.friendModes.${match.mode}`, { defaultValue: match.mode })}</p>
                </div>
                <p className={`text-right text-sm font-medium ${match.outcome === 'won' ? 'text-emerald-300' : 'text-zinc-400'}`}>{t(`profile.matchOutcome.${match.outcome}`)}</p>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-center gap-3 rounded-sm border border-dashed border-white/15 py-14 text-center text-sm text-zinc-400"><Target size={24} className="text-emerald-400/60" aria-hidden="true" /><p>{t('profile.noFriendMatches')}</p></div>
        ))}
      </section>
    </div>
  );
}
