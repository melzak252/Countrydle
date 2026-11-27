import type { ReactNode } from 'react';

export type ResultDashboardModeKind = 'qa' | 'visual' | 'quiz' | 'route';

export interface ResultDashboardMetric {
  label: string;
  value: string;
  subtext?: string;
  accent?: 'emerald' | 'amber' | 'rose' | 'default';
}

export interface ResultDashboardDetailTab {
  id: string;
  label: string;
  badge?: string | number;
  icon?: ReactNode;
  content: ReactNode;
}

export interface ResultDashboardAction {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
}

export interface GameResultDashboardProps {
  /** Backend stats registry mode key (e.g. 'countrydle', 'flagdle', 'heraldry', 'border_hop'). */
  mode: string;
  /** Controls which distribution charts and KPI defaults are shown. */
  modeKind?: ResultDashboardModeKind;
  /** Human-readable game name (e.g. 'Countrydle'). */
  gameName: string;
  /** Route path for this mode (e.g. '/game', '/flagdle'). */
  gamePath: string;
  /** Daily puzzle ISO date (YYYY-MM-DD). */
  date?: string | null;
  /** Whether this result is from today's daily challenge vs practice/challenge round. */
  isDaily?: boolean;
  /** Whether the player won / completed the puzzle. */
  won: boolean;
  /** Optional custom outcome pill text (defaults to Solved / Game Over). */
  outcomeLabel?: string;
  /** Optional subtitle under target title. */
  subtitle?: string;
  /** Points earned (if applicable). */
  points?: number | null;
  /** Label above the revealed target (e.g. 'The Mystery Location'). */
  targetLabel?: string;
  /** Revealed target name (e.g. 'Poland', 'California'). */
  targetName?: string;
  /** Optional secondary line under target name (e.g. official name or voivodeship). */
  targetSubtitle?: string;
  /** ISO2 country code for flagcdn thumbnail when no targetImageUrl is provided. */
  targetCountryCode?: string | null;
  /** Custom image URL for flag/coat-of-arms thumbnail. */
  targetImageUrl?: string | null;
  /** Alt text for target thumbnail. */
  targetImageAlt?: string;
  /** Optional badge rendered beside the target reveal (e.g. PolishLicensePlateBadge). */
  targetAccessory?: ReactNode;
  /** QA mode question stats. */
  questionsAsked?: number;
  maxQuestions?: number;
  /** Guess stats. */
  guessesMade?: number;
  maxGuesses?: number;
  /** Quiz / route score stats. */
  score?: number;
  maxScore?: number;
  elapsedSeconds?: number;
  /** Optional explicit KPI strip items (overrides auto-generated KPIs). */
  metrics?: ResultDashboardMetric[];
  /** Custom spoiler-free share text; auto-generated if omitted. */
  shareText?: string;
  /** Title passed to navigator.share(). */
  shareTitle?: string;
  /** Duel mode query param for the 1v1 Duel CTA (defaults to inferred mode). */
  duelMode?: string;
  /** Optional primary mode action (e.g. Play Challenge Round / Play Again). */
  primaryAction?: ResultDashboardAction;
  /** Optional extra secondary action nodes in the share/actions panel. */
  secondaryActions?: ReactNode;
  /** Single details section (e.g. Attribution, Optimal Path, Field Notes). */
  detailsSlot?: ReactNode;
  /** Multi-tab details section (e.g. Field Notes + Question History). */
  detailTabs?: ResultDashboardDetailTab[];
  /** Collapsible section heading on mobile for detailsSlot/detailTabs. */
  detailsTitle?: string;
  /** Callback when the user closes/dismisses the modal dashboard. */
  onClose?: () => void;
  /** Label for the close button in footer. */
  closeLabel?: string;
  /** Render as full-screen modal overlay (default) or inline bento panel. */
  variant?: 'modal' | 'inline';
}
