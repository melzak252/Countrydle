import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, BookOpen, Compass, Play, Users } from 'lucide-react';
import ExploreGameArtwork from '../components/ExploreGameArtwork';
import GuestProgress from '../components/GuestProgress';
import SpinningGlobe from '../components/SpinningGlobe';
import { useDailyDate } from '../hooks/useDailyClock';
import { useAuthStore } from '../stores/authStore';
import { useCountryGameStore } from '../stores/gameStore';
import { isPrerenderCapture } from '../lib/pageMetadata';
import { primaryGames, type CatalogGeography } from '../lib/gameCatalog';

const MODE_SUMMARIES: Record<string, { tag: string; summary: string; stripe: string }> = {
  '/game': { tag: '10 questions · 3 guesses', summary: 'Ask yes-or-no questions to uncover today’s secret country.', stripe: 'border-t-[#2a5942]' },
  '/flagdle': { tag: '12 tile guesses', summary: 'Identify the country as its national flag is uncovered.', stripe: 'border-t-[#a84436]' },
  '/flag-shades': { tag: 'Grayscale challenge', summary: 'Recognize the flag from proportions and luminance alone.', stripe: 'border-t-[#355c7d]' },
  '/us-states': { tag: '8 questions · 3 guesses', summary: 'Deduce today’s hidden US state on the map.', stripe: 'border-t-[#9a6b2f]' },
};

const QUICK_OTHER_MODES: { path: string; name: string; tag: string; geography: CatalogGeography }[] = [
  { path: '/powiaty', name: 'Powiatdle', tag: '380 Polish counties', geography: 'poland' },
  { path: '/wojewodztwa', name: 'Województwodle', tag: '16 Polish regions', geography: 'poland' },
  { path: '/border-hop', name: 'Border Hop', tag: 'Follow land borders', geography: 'worldwide' },
  { path: '/herby-powiatow', name: 'County Coats of Arms', tag: 'Daily heraldry', geography: 'poland' },
];

const HOW_IT_WORKS = [
  { step: '01', title: 'Ask', text: 'Start broad: continent, coastline, borders, or population. Every question gets a verified yes or no.' },
  { step: '02', title: 'Narrow', text: 'Mark off ruled-out places right on the map as your picture sharpens.' },
  { step: '03', title: 'Guess', text: 'Lock in your answer within 3 guesses. A new puzzle arrives daily at 00:00 UTC.' },
];

export default function HomePage() {
  const location = useLocation();
  const today = useDailyDate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const { gameState, dailyDate, isGuest, isLoading, error, fetchGameState } = useCountryGameStore();
  const capture = isPrerenderCapture();

  useEffect(() => {
    if (!capture && !authLoading && !isAuthenticated) void fetchGameState();
  }, [capture, authLoading, isAuthenticated, today, fetchGameState]);

  useEffect(() => {
    if (location.hash === '#maps') {
      document.getElementById('maps')?.scrollIntoView();
      document.getElementById('maps-heading')?.focus({ preventScroll: true });
    }
  }, [location.hash, location.key]);

  const guest = !capture && !authLoading && !isAuthenticated;
  const currentGuestState = guest && isGuest && dailyDate === today && !isLoading && !error
    ? gameState
    : null;
  const hasStarted = currentGuestState && (currentGuestState.questions_asked > 0 || currentGuestState.guesses_made > 0);
  const checkingProgress = !capture && (authLoading || (guest && (isLoading || (!error && !currentGuestState))));

  const playLabel = currentGuestState?.is_game_over
    ? 'View today’s result'
    : hasStarted
      ? 'Continue today’s country'
      : 'Play today’s country';

  const progressNote = guest && error
    ? 'We couldn’t check your progress. Open the puzzle to try again.'
    : checkingProgress
      ? 'Checking today’s progress…'
      : currentGuestState?.is_game_over
        ? 'Today’s puzzle is complete. Your result is ready.'
        : hasStarted
          ? `${currentGuestState.remaining_questions} questions and ${currentGuestState.remaining_guesses} guesses remaining today.`
          : null;

  return (
    <div className="mx-auto min-w-0 max-w-6xl space-y-10 pb-8 text-app-text md:space-y-12 md:pb-12">
      {/* Hero */}
      <section aria-labelledby="home-heading" className="grid min-w-0 items-center gap-6 border-b border-app-border pb-8 md:grid-cols-[1.15fr_1fr] md:gap-12 md:pb-10">
        <motion.div
          initial={capture ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="min-w-0"
        >
          <div className="inline-flex items-center gap-2 rounded-sm border border-app-border/70 bg-app-surface-muted/70 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-app-accent">
            <Compass size={13} aria-hidden="true" />
            <span>Daily geography puzzle · 00:00 UTC</span>
          </div>

          <h1 id="home-heading" className="mt-4 font-serif text-4xl font-semibold leading-[1.08] tracking-tight text-app-text sm:text-5xl lg:text-[3.25rem]">
            Countrydle.
            <span className="mt-1 block text-app-accent">One hidden country.</span>
          </h1>

          <p className="mt-4 max-w-lg text-base leading-relaxed text-app-text-secondary sm:text-lg">
            Deduce today’s secret country using yes-or-no questions and an interactive map. 10 questions, 3 guesses, no account needed.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              to="/game"
              className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-sm bg-app-accent px-6 py-3 text-sm font-semibold text-app-canvas shadow-[0_2px_8px_rgba(85,75,57,0.18)] transition-all hover:-translate-y-0.5 hover:bg-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-app-focus sm:w-auto"
            >
              <span>{playLabel}</span>
              <ArrowRight size={17} className="shrink-0" aria-hidden="true" />
            </Link>
            <Link
              to="/friends"
              className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-sm border border-app-border bg-app-surface px-5 py-3 text-sm font-semibold text-app-text transition-colors hover:border-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-app-focus sm:w-auto"
            >
              <Users size={16} className="text-app-accent" aria-hidden="true" />
              <span>Duel a friend</span>
            </Link>
          </div>

          {progressNote && (
            <p role="status" className="mt-3 max-w-lg font-mono text-xs leading-relaxed text-app-text-muted">
              {progressNote}
            </p>
          )}
        </motion.div>

        <motion.div
          initial={capture ? false : { opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="relative mx-auto flex w-full max-w-[230px] items-center justify-center sm:max-w-[290px] md:max-w-[380px]"
        >
          <div className="relative z-10 w-full">
            {!capture && <SpinningGlobe size={380} />}
          </div>
        </motion.div>
      </section>

      {/* Featured Daily Modes */}
      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 space-y-5 border-b border-app-border pb-10">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-app-accent">Daily challenges</p>
            <h2 id="maps-heading" tabIndex={-1} className="mt-1 font-serif text-2xl font-semibold tracking-tight text-app-text sm:text-3xl">
              Featured puzzles
            </h2>
          </div>
          <Link
            to="/explore"
            className="inline-flex min-h-10 items-center gap-2 self-start text-sm font-semibold text-app-accent underline decoration-app-border underline-offset-4 transition-colors hover:text-app-accent-hover sm:self-auto"
          >
            <span>Explore all modes &amp; atlas</span>
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {primaryGames.map((game, idx) => {
            const meta = MODE_SUMMARIES[game.path] ?? { tag: 'Daily puzzle', summary: 'Test your geography knowledge.', stripe: 'border-t-app-accent' };
            return (
              <motion.div
                key={game.path}
                initial={capture ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                whileHover={capture ? undefined : { y: -3 }}
                transition={{ duration: 0.25, delay: idx * 0.05, ease: [0.16, 1, 0.3, 1] }}
                className="h-full"
              >
                <Link
                  to={game.path}
                  className={`group relative flex h-full flex-col rounded-sm border border-app-border border-t-[3px] ${meta.stripe} bg-app-surface p-4 text-app-text shadow-[1px_3px_10px_rgba(85,75,57,0.08)] transition-all duration-200 hover:border-app-accent hover:bg-app-surface-raised hover:shadow-[2px_8px_20px_rgba(85,75,57,0.14)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus`}
                >
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <ExploreGameArtwork game={game} />
                    <span className="rounded-sm bg-app-surface-muted px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-app-accent">
                      {meta.tag}
                    </span>
                  </div>
                  <h3 className="font-serif text-lg font-semibold leading-snug text-app-text">{game.name}</h3>
                  <p className="mt-1.5 flex-1 text-xs leading-5 text-app-text-secondary">{meta.summary}</p>
                  <span className="mt-3 inline-flex items-center justify-between border-t border-app-border/60 pt-2.5 text-xs font-semibold text-app-accent">
                    <span>Play</span>
                    <Play size={12} className="transition-transform group-hover:translate-x-1" aria-hidden="true" />
                  </span>
                </Link>
              </motion.div>
            );
          })}
        </div>

        {/* Compact secondary quick-links */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="mr-1 font-mono text-[11px] uppercase tracking-wider text-app-text-muted">Also popular:</span>
          {QUICK_OTHER_MODES.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="inline-flex items-center gap-2 rounded-sm border border-app-border bg-app-surface px-3 py-1.5 text-xs font-medium text-app-text transition-colors hover:border-app-accent hover:bg-app-surface-muted"
            >
              <span>{item.name}</span>
              <span className="font-mono text-[10px] text-app-text-muted">· {item.tag}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* How It Works — Clean 3-step strip */}
      <section aria-labelledby="how-heading" className="border-b border-app-border pb-10">
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="how-heading" className="font-serif text-2xl font-semibold tracking-tight text-app-text">
            How it works
          </h2>
          <Link to="/how-it-works" className="text-xs font-semibold text-app-accent underline decoration-app-border underline-offset-4 hover:text-app-accent-hover">
            Full guide &amp; deduction tips
          </Link>
        </div>
        <ol className="grid gap-4 md:grid-cols-3">
          {HOW_IT_WORKS.map((item) => (
            <li key={item.step} className="rounded-sm border border-app-border bg-app-surface p-4">
              <div className="flex items-baseline gap-2.5">
                <span className="font-mono text-xs font-bold text-app-accent">{item.step}</span>
                <h3 className="font-serif text-lg font-semibold text-app-text">{item.title}</h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-app-text-secondary">{item.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Progress & Blog */}
      <div className={`grid gap-5 ${guest ? 'lg:grid-cols-[1.2fr_1fr]' : 'grid-cols-1'}`}>
        {guest && <GuestProgress gameType="country" today={today} />}
        <Link
          to="/blog"
          className="group flex flex-col justify-between rounded-sm border border-app-border bg-app-surface p-5 transition-all hover:-translate-y-0.5 hover:border-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-app-focus"
        >
          <div>
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-app-accent">
                <BookOpen size={14} aria-hidden="true" />
                <span>Field Notes &amp; Recaps</span>
              </span>
              <ArrowRight size={16} className="text-app-accent transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
            </div>
            <h2 className="mt-3 font-serif text-xl font-semibold text-app-text">
              Discover the stories behind the places
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-app-text-secondary">
              Daily puzzle debriefs, player deduction stats, and geography facts from past Countrydle targets.
            </p>
          </div>
          <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-app-accent">
            <span>Read the blog</span>
            <ArrowRight size={13} aria-hidden="true" />
          </span>
        </Link>
      </div>
    </div>
  );
}
