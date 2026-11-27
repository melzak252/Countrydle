import { useMemo } from 'react';
import { ArrowRight, Swords } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useDailyClock } from '../../hooks/useDailyClock';

interface NextModeShelfProps {
  currentPath: string;
  duelMode?: string;
}

interface DailyModeChip {
  path: string;
  name: string;
  storageKey?: (today: string) => string;
}

const DAILY_MODE_POOL: DailyModeChip[] = [
  {
    path: '/game',
    name: 'Countrydle',
    storageKey: (d) => `guess_game_countrydle_${d}`,
  },
  {
    path: '/flagdle',
    name: 'Flagdle',
    storageKey: (d) => `guess_game_flagdle_${d}`,
  },
  {
    path: '/flag-shades',
    name: 'Flag Shades',
    storageKey: (d) => `flag_shades_daily_${d}`,
  },
  {
    path: '/us-states',
    name: 'US Statedle',
    storageKey: (d) => `guess_game_us_statedle_${d}`,
  },
  {
    path: '/europe',
    name: 'Europedle',
    storageKey: (d) => `guess_game_europe_${d}`,
  },
  {
    path: '/border-hop',
    name: 'Border Hop',
  },
  {
    path: '/wojewodztwa',
    name: 'Województwodle',
    storageKey: (d) => `guess_game_wojewodztwodle_${d}`,
  },
  {
    path: '/herby-powiatow',
    name: 'County Coats',
    storageKey: (d) => `powiat_heraldry_daily_token_${d}`,
  },
];

function isModeCompletedToday(card: DailyModeChip, today: string): boolean {
  if (!card.storageKey || typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem(card.storageKey(today));
    if (!raw) return false;
    if (raw.startsWith('{')) {
      const parsed = JSON.parse(raw) as {
        state?: { is_game_over?: boolean };
        is_game_over?: boolean;
      };
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
    return [...unplayed, ...played].slice(0, 3);
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
    <nav
      aria-label="Up next"
      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-t border-white/[0.08] pt-5"
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="shrink-0 font-mono text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          Up next
        </span>

        <div className="flex items-center gap-2 overflow-x-auto pb-0.5 sm:pb-0 no-scrollbar">
          {suggestions.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="group shrink-0 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-xs font-medium text-sand-100 hover:border-emerald-400/40 hover:bg-emerald-400/10 hover:text-emerald-200 transition-colors"
            >
              <span>{item.name}</span>
              <ArrowRight
                size={12}
                className="text-zinc-500 group-hover:text-emerald-300 transition-colors"
                aria-hidden="true"
              />
            </Link>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <Link
          to={`/friends?mode=${encodeURIComponent(resolvedDuelMode)}`}
          className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/25 bg-amber-400/[0.08] px-3.5 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-400/15 transition-colors"
        >
          <Swords size={13} className="text-amber-300 shrink-0" aria-hidden="true" />
          <span>1v1 Duel</span>
        </Link>

        <Link
          to="/#maps"
          className="font-mono text-[11px] text-zinc-500 hover:text-zinc-200 transition-colors"
        >
          All modes
        </Link>
      </div>
    </nav>
  );
}
