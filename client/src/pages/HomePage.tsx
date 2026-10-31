import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, BookOpen, ChevronDown } from 'lucide-react';
import GuestProgress from '../components/GuestProgress';
import SpinningGlobe from '../components/SpinningGlobe';
import { useDailyDate } from '../hooks/useDailyClock';
import { useAuthStore } from '../stores/authStore';
import { useCountryGameStore } from '../stores/gameStore';
import { isPrerenderCapture } from '../lib/pageMetadata'
import { gameCatalog } from '../lib/gameCatalog';

export default function HomePage() {
  
  const today = useDailyDate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const { gameState, dailyDate, isGuest, isLoading, error, fetchGameState } = useCountryGameStore();
  const capture = isPrerenderCapture();

  useEffect(() => {
    if (!capture && !authLoading && !isAuthenticated) void fetchGameState();
  }, [capture, authLoading, isAuthenticated, today, fetchGameState]);

  const guest = !capture && !authLoading && !isAuthenticated;
  const currentGuestState = guest && isGuest && dailyDate === today && !isLoading && !error
    ? gameState
    : null;
  const hasStarted = currentGuestState && (currentGuestState.questions_asked > 0 || currentGuestState.guesses_made > 0);
  const checkingProgress = !capture && (authLoading || (guest && (isLoading || (!error && !currentGuestState))));
  const playLabel = currentGuestState?.is_game_over
    ? ('View today’s result')
    : hasStarted
      ? ('Continue today’s country')
      : guest && error
        ? ('Open today’s country')
        : checkingProgress
          ? ('Open today’s country')
          : ('Play today’s country');
  const progressNote = guest && error
    ? ('We couldn’t check your progress. Open the puzzle to try again.')
    : checkingProgress
      ? ('Checking today’s progress…')
      : currentGuestState?.is_game_over
        ? ('Today’s puzzle is complete. Your result is ready.')
        : hasStarted
          ? (`${currentGuestState.remaining_questions} questions and ${currentGuestState.remaining_guesses} guesses remaining today.`)
          : null;
  const copy = {
    daily: 'Your daily geography puzzle',
    title: 'Countrydle.',
    titleEnd: 'One hidden country.',
    intro: 'Find it with yes-or-no questions. 10 questions, 3 guesses. No sign-in needed.',
    choose: 'Explore other games',
    modes: 'What will you discover next?',
    modeNote: 'Choose another game to explore.',
    progress: 'Your progress on this device',
    how: 'How to play the country puzzle',
    reset: 'A new puzzle every day at 00:00 UTC.',
    steps: [
        { title: 'Ask a question', text: 'Start broad: is the country in Europe? Does it have a coastline? You’ll get a yes-or-no answer.' },
        { title: 'Narrow the map', text: 'Use the answers to rule out countries. You have 10 questions, so choose them carefully.' },
        { title: 'Guess the country', text: 'Choose a country when you have a candidate. You have 3 guesses to find today’s answer.' },
      ],
    blogTitle: 'Discover the stories behind the places',
    blogText: 'Past puzzles, surprising facts and more geography to explore on the blog.',
  };
  const disclosureClass = 'group rounded-lg border border-white/10 bg-obsidian-900/60';
  const summaryClass = 'flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-4 py-3 font-semibold text-sand-50 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 [&::-webkit-details-marker]:hidden';

  return (
    <div className="mx-auto min-w-0 max-w-6xl pb-6 md:pb-12">
      <section aria-labelledby="home-heading" className="grid min-w-0 items-center gap-5 border-b border-white/10 pb-6 md:grid-cols-[1.2fr_1fr] md:gap-12 md:pb-10">
        <div className="min-w-0">
          <p className="mb-2 text-sm font-medium text-emerald-400">{copy.daily}</p>
          <h1 id="home-heading" className="text-[1.75rem] font-extrabold leading-tight tracking-tight text-sand-50 sm:text-4xl lg:text-5xl">
            {copy.title}
            <span className="mt-1 block text-emerald-300">{copy.titleEnd}</span>
          </h1>
          <p className="mt-3 max-w-lg text-base leading-relaxed text-slate-300 md:mt-4 md:text-lg">{copy.intro}</p>
          <Link to="/game" className="mt-5 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-emerald-400 px-4 py-3 text-center text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 sm:w-auto sm:px-6">
            <span className="min-w-0">{playLabel}</span>
            <ArrowRight size={17} className="shrink-0" aria-hidden="true" />
          </Link>
          {progressNote && <p role="status" className="mt-3 max-w-lg text-sm leading-relaxed text-slate-400">{progressNote}</p>}
          <a href="#maps" className="mt-4 flex w-fit min-h-11 items-center gap-2 py-2 text-sm text-slate-300 underline decoration-white/20 underline-offset-4 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
            {copy.choose}<ArrowDown size={15} className="shrink-0" aria-hidden="true" />
          </a>
        </div>
        <div className="mx-auto w-full max-w-[224px] sm:max-w-[280px] md:max-w-[380px]">
          {!capture && <SpinningGlobe size={380} />}
        </div>
      </section>

      <section aria-labelledby="practice-heading" className="border-b border-white/10 py-6 md:py-8">
        <h2 id="practice-heading" className="text-xl font-bold text-sand-50">See a country deduction in action</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">
          For practice, imagine the hidden country is Poland. This example is illustrative, not a clue about today&apos;s puzzle.
        </p>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-300 marker:text-emerald-400">
          <li><strong>Is it in Europe? Yes.</strong> Keep European countries as candidates.</li>
          <li><strong>Is it landlocked? No.</strong> Poland has a Baltic Sea coast, so inland candidates can be ruled out.</li>
          <li><strong>Does it border Germany? Yes.</strong> This narrows the coastal candidates further, but does not by itself prove the answer.</li>
        </ol>
        <p className="mt-3 text-sm leading-relaxed text-slate-400">
          Check the geography in <a href="https://www.britannica.com/place/Poland" className="text-emerald-300 underline underline-offset-4">Britannica&apos;s Poland profile</a>, then explore the <Link to="/explore/modes/countrydle" className="text-emerald-300 underline underline-offset-4">country deduction guide</Link>.
        </p>
      </section>

      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 py-6 md:py-10">
        <h2 id="maps-heading" className="text-2xl font-bold tracking-tight text-sand-50">{copy.modes}</h2>
        <p className="mb-4 mt-2 text-sm leading-relaxed text-slate-400">{copy.modeNote}</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {gameCatalog.map((group) => (
            <section key={group.title} aria-labelledby={`games-${group.title.replaceAll(' ', '-').toLowerCase()}`} className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60 p-4">
              <h3 id={`games-${group.title.replaceAll(' ', '-').toLowerCase()}`} className="font-semibold text-sand-50">{group.title}</h3>
              <ul className="mt-2 space-y-1">
                {group.games.map((game) => (
                  <li key={game.path}>
                    <Link to={game.path} className="flex min-h-10 items-center justify-between gap-2 rounded-md px-2 py-2 text-sm text-slate-300 transition-colors hover:bg-white/5 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400">
                      <span>{game.name}</span>
                      <ArrowRight size={15} className="shrink-0 text-emerald-400" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </section>

      <div className="space-y-3 border-t border-white/10 pt-6">
        <details className={disclosureClass}>
          <summary className={summaryClass}>
            <h2 className="min-w-0 text-base">{copy.how}</h2>
            <ChevronDown size={18} className="shrink-0 text-emerald-400 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
          </summary>
          <div className="border-t border-white/10 p-4 md:p-5">
            <ol className="grid gap-5 md:grid-cols-3">
              {copy.steps.map((step) => (
                <li key={step.title}>
                  <h3 className="font-semibold text-sand-50">{step.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-slate-400">{step.text}</p>
                </li>
              ))}
            </ol>
            <p className="mt-4 text-sm text-emerald-300">{copy.reset}</p>
          </div>
        </details>
        {guest && (
          <details className={disclosureClass}>
            <summary className={summaryClass}>
              <span className="min-w-0">{copy.progress}</span>
              <ChevronDown size={18} className="shrink-0 text-emerald-400 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
            </summary>
            <div className="border-t border-white/10 p-3 md:p-4"><GuestProgress gameType="country" today={today} /></div>
          </details>
        )}
      </div>

      <section aria-label="Explore the blog" className="mt-6">
        <Link to="/blog" className="block min-w-0 rounded-lg border border-white/10 p-4 transition-colors hover:border-emerald-400/30 hover:bg-emerald-500/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 md:p-5">
          <div className="flex items-start gap-3">
            <BookOpen size={20} className="mt-0.5 shrink-0 text-emerald-400" aria-hidden="true" />
            <h2 className="min-w-0 flex-1 font-semibold text-sand-50">{copy.blogTitle}</h2>
            <ArrowRight size={16} className="mt-1 shrink-0 text-emerald-400" aria-hidden="true" />
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">{copy.blogText}</p>
        </Link>
      </section>
    </div>
  );
}
