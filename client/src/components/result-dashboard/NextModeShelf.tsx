import { useMemo } from 'react';
import { ArrowRight, Compass, Swords } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useDailyClock } from '../../hooks/useDailyClock';

interface NextModeShelfProps {
  currentPath: string;
  duelMode?: string;
}

interface DailyModeCard {
  path: string;
  name: string;
  tag: string;
  storageKey?: (today: string) => string;
}

const DAILY_MODE_POOL: DailyModeCard[] = [
  {
    path: '/game',
    name: 'Countrydle',
    tag: 'World · Q&A',
    storageKey: (d) => `guess_game_countrydle_${d}`,
  },
  {
    path: '/flagdle',
    name: 'Flagdle',
    tag: 'Flags · Daily',
    storageKey: (d) => `guess_game_flagdle_${d}`,
  },
  {
    path: '/flag-shades',
    name: 'Flag Shades',
    tag: 'Grayscale',
    storageKey: (d) => `flag_shades_daily_${d}`,
  },
  {
    path: '/us-states',
    name: 'US Statedle',
    tag: 'USA · Q&A',
    storageKey: (d) => `guess_game_us_statedle_${d}`,
  },
  {
    path: '/europe',
    name: 'Europedle',
    tag: 'Europe · Q&A',
    storageKey: (d) => `guess_game_europe_${d}`,
  },
  {
    path: '/border-hop',
    name: 'Border Hop',
    tag: 'Routes',
  },
  {
    path: '/wojewodztwa',
    name: 'Województwodle',
    tag: 'Poland · Q&A',
    storageKey: (d) => `guess_game_wojewodztwodle_${d}`,
  },
  {
    path: '/herby-powiatow',
    name: 'County Coats',
    tag: 'Heraldry',
    storageKey: (d) => `powiat_heraldry_daily_token_${d}`,
  },
];

function isModeCompletedToday(card: DailyModeCard, today: string): boolean {
  if (!card.storageKey || typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem(card.storageKey(today));
    if (!raw) return false;
    if (raw.startsWith('{')) {
      const parsed = JSON.parse(raw) as { state?: { is_game_over?: boolean }; is_game_over?: boolean };
      return Boolean(parsed?.state?.is_game_over ?? parsed?.is_game_over);
    }
    return true;
  } catch {
    return false;
  }
}

export default function NextModeShelf({ currentPath, duelMode }: NextModeShelfProps) {
  const { today } = useDailyClock();

  const suggestions = useMemo(() => {
    const candidates = DAILY_MODE_POOL.filter((item) => item.path !== currentPath);
    const unplayed = candidates.filter((item) => !isModeCompletedToday(item, today));
    const played = candidates.filter((item) => isModeCompletedToday(item, today));
    return [...unplayed, ...played].slice(0, 4);
  }, [currentPath, today]);

  const resolvedDuelMode =
    duelMode ||
    (currentPath === '/powiaty'
      ? 'powiatdle'
      : currentPath === '/wojewodztwa'
      ? 'wojewodztwodle'
      : currentPath === '/us-states'
      ? 'us_statedle'
      : 'countrydle');

  return (
    <section
      aria-label="Play next"
      className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Compass size={14} className="text-emerald-400 shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
            Play Next Today
          </h3>
        </div>
        <Link
          to="/#maps"
          className="font-mono text-[11px] text-zinc-400 hover:text-emerald-300 transition-colors"
        >
          All modes
        </Link>
      </div>

      {/* Horizontal chips on mobile, 2x2 grid on desktop */}
      <div className="flex gap-2 overflow-x-auto pb-1 snap-x lg:grid lg:grid-cols-2 lg:overflow-visible lg:pb-0">
        {suggestions.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className="group snap-start shrink-0 min-w-[145px] lg:min-w-0 flex items-center justify-between gap-2 rounded-xs border border-white/10 bg-obsidian-950/70 px-3 py-2.5 hover:border-emerald-400/40 hover:bg-white/[0.04] transition-colors"
          >
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
                {item.name}
              </div>
              <div className="font-mono text-[10px] text-zinc-400">{item.tag}</div>
            </div>
            <ArrowRight
              size={13}
              className="shrink-0 text-zinc-500 group-hover:text-emerald-400 transition-colors"
              aria-hidden="true"
            />
          </Link>
        ))}
      </div>

      {/* 1v1 Duel CTA */}
      <Link
        to={`/friends?mode=${encodeURIComponent(resolvedDuelMode)}`}
        className="flex min-h-11 items-center justify-between gap-2 rounded-xs border border-amber-400/25 bg-amber-400/[0.07] px-3 py-2 text-xs font-semibold text-amber-200 hover:bg-amber-400/15 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Swords size={15} className="text-amber-300 shrink-0" aria-hidden="true" />
          <span className="truncate">Challenge a friend in 1v1 Duel</span>
        </div>
        <ArrowRight size={14} className="shrink-0 text-amber-300" aria-hidden="true" />
      </Link>
    </section>
  );
}
