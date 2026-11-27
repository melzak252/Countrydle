import { useMemo } from 'react';
import { ArrowRight, Compass, Swords } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useDailyClock } from '../../hooks/useDailyClock';
import { MAP_QUIZ_PATHS } from '../../lib/mapGameMode';

interface NextModeShelfProps {
  currentPath: string;
  duelMode?: string;
}

export interface DailyModeCard {
  path: string;
  name: string;
  tag: string;
  accent: string;
  storageKey?: (today: string) => string;
}

// Curated daily progression:
// Countrydle -> Flagdle -> Flag Shades -> US State Map Quiz -> Powiat Map Quiz -> County Coats of Arms -> rest
export const DAILY_MODE_POOL: DailyModeCard[] = [
  {
    path: '/game',
    name: 'Countrydle',
    tag: '10 questions · World',
    accent: 'border-t-app-accent',
    storageKey: (d) => `guess_game_countrydle_${d}`,
  },
  {
    path: '/flagdle',
    name: 'Flagdle',
    tag: '12 tile flag reveal',
    accent: 'border-t-[#a84436]',
    storageKey: (d) => `guess_game_flagdle_${d}`,
  },
  {
    path: '/flag-shades',
    name: 'Flag Shades',
    tag: 'Grayscale challenge',
    accent: 'border-t-[#9a6b2f]',
    storageKey: (d) => `flag_shades_daily_${d}`,
  },
  {
    path: MAP_QUIZ_PATHS.us_states,
    name: 'US State Map Quiz',
    tag: 'Daily · 10 map picks',
    accent: 'border-t-[#355c7d]',
  },
  {
    path: MAP_QUIZ_PATHS.powiaty,
    name: 'Powiat Map Quiz',
    tag: 'Daily · 10 powiats',
    accent: 'border-t-app-accent',
  },
  {
    path: '/herby-powiatow',
    name: 'County Coats of Arms',
    tag: 'Daily Polish heraldry',
    accent: 'border-t-[#9a6b2f]',
    storageKey: (d) => `powiat_heraldry_daily_token_${d}`,
  },
  {
    path: '/countydle',
    name: 'Countydle',
    tag: '8 questions · England',
    accent: 'border-t-[#355c7d]',
    storageKey: (d) => `guess_game_countydle_${d}`,
  },
  {
    path: '/map-quiz/london-boroughs',
    name: 'London Boroughs',
    tag: 'Daily · 10 map picks',
    accent: 'border-t-[#9a6b2f]',
    storageKey: (d) => `map_quiz_london_boroughs_${d}`,
  },
  {
    path: '/map-quiz/england-counties',
    name: 'English Counties',
    tag: 'Daily · 10 map picks',
    accent: 'border-t-[#a84436]',
    storageKey: (d) => `map_quiz_england_counties_${d}`,
  },
  {
    path: '/us-states',
    name: 'US Statedle',
    tag: '8 questions · 50 states',
    accent: 'border-t-[#355c7d]',
    storageKey: (d) => `guess_game_us_statedle_${d}`,
  },
  {
    path: '/wojewodztwa',
    name: 'Województwodle',
    tag: '5 questions · Poland',
    accent: 'border-t-[#a84436]',
    storageKey: (d) => `guess_game_wojewodztwodle_${d}`,
  },
  {
    path: '/europe',
    name: 'Europedle',
    tag: '8 questions · Europe',
    accent: 'border-t-app-accent',
    storageKey: (d) => `guess_game_europe_${d}`,
  },
  {
    path: '/border-hop',
    name: 'Border Hop',
    tag: 'Shortest land route',
    accent: 'border-t-[#355c7d]',
  },
  {
    path: '/quiz-tablic',
    name: 'License Plates Quiz',
    tag: 'Fill 380 Polish counties',
    accent: 'border-t-app-accent',
  },
];

function isModeCompletedToday(card: DailyModeCard, today: string): boolean {
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

export function getNextDailyGame(currentPath: string, today: string): DailyModeCard | null {
  const normalized = currentPath.split('?')[0];
  const currentIdx = DAILY_MODE_POOL.findIndex((item) => item.path === normalized);
  const ordered =
    currentIdx >= 0
      ? [...DAILY_MODE_POOL.slice(currentIdx + 1), ...DAILY_MODE_POOL.slice(0, currentIdx)]
      : DAILY_MODE_POOL.filter((item) => item.path !== normalized);
  if (ordered.length === 0) return null;
  return ordered.find((item) => !isModeCompletedToday(item, today)) ?? ordered[0];
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
      aria-label="Recommended other modes"
      className="rounded-md border border-app-border bg-app-surface p-4 sm:p-5 space-y-3.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Compass size={15} className="text-app-accent shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-[0.14em] text-app-text">
            Recommended Other Modes
          </h3>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/friends?mode=${encodeURIComponent(resolvedDuelMode)}`}
            className="inline-flex items-center gap-1.5 rounded-sm border border-[#9a6b2f]/40 bg-[#9a6b2f]/10 px-3 py-1 text-xs font-semibold text-[#c68f42] hover:bg-[#9a6b2f]/20 transition-colors"
          >
            <Swords size={12} className="text-[#c68f42] shrink-0" aria-hidden="true" />
            <span>1v1 Duel</span>
          </Link>

          <Link
            to="/#maps"
            className="font-mono text-[11px] font-medium text-app-text-secondary underline decoration-app-border underline-offset-4 hover:text-app-accent transition-colors"
          >
            All modes
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        {suggestions.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`group flex items-center justify-between gap-2 rounded-sm border border-app-border/80 border-t-2 ${item.accent} bg-app-canvas px-3.5 py-2.5 hover:border-app-accent hover:bg-app-surface-muted/70 transition-colors`}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-serif font-semibold text-app-text group-hover:text-app-accent transition-colors">
                {item.name}
              </p>
              <p className="truncate font-mono text-[10px] text-app-text-muted mt-0.5">
                {item.tag}
              </p>
            </div>
            <ArrowRight
              size={14}
              className="shrink-0 text-app-text-muted group-hover:translate-x-0.5 group-hover:text-app-accent transition-all"
              aria-hidden="true"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}
