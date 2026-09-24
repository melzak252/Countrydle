import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, BookOpen, Compass, Flag, Globe, Globe2, Map, MapPin, Sparkles, Sun, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import GuestProgress from '../components/GuestProgress';
import SpinningGlobe from '../components/SpinningGlobe';
import { useDailyDate } from '../hooks/useDailyClock';
import { useAuthStore } from '../stores/authStore';
import { useCountryGameStore } from '../stores/gameStore';

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');
  const today = useDailyDate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const { gameState, dailyDate, isGuest, isLoading, error, fetchGameState } = useCountryGameStore();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) void fetchGameState();
  }, [authLoading, isAuthenticated, today, fetchGameState]);

  const guest = !authLoading && !isAuthenticated;
  const currentGuestState = guest && isGuest && dailyDate === today && !isLoading && !error
    ? gameState
    : null;
  const hasStarted = currentGuestState && (currentGuestState.questions_asked > 0 || currentGuestState.guesses_made > 0);
  const playLabel = currentGuestState?.is_game_over
    ? 'View today’s result'
    : hasStarted ? 'Continue today’s country' : 'Play today’s country';
  const progressNote = currentGuestState?.is_game_over
    ? 'Today’s country puzzle is complete. Your result is ready.'
    : hasStarted
      ? `${currentGuestState.remaining_questions} questions and ${currentGuestState.remaining_guesses} guesses remaining today.`
      : null;
  const copy = {
    eyebrow: isPl ? 'Codzienna łamigłówka geograficzna' : 'Daily Geography Deduction',
    eyebrowTag: isPl ? 'Odnawia się o 00:00 UTC' : 'Rotates at 00:00 UTC',
    title: isPl ? 'Cały świat.' : 'A whole world.',
    titleEnd: isPl ? 'Jedno ukryte miejsce.' : 'One hidden place.',
    intro: isPl
      ? 'Odkryj dzisiejsze ukryte państwo pytaniami tak/nie. Masz 10 pytań i 3 próby. Bez konieczności logowania.'
      : 'Find today’s hidden country with yes-or-no questions. 10 questions. 3 guesses. Free and instant.',
    choose: isPl ? 'Przeglądaj wszystkie mapy' : 'Explore all maps',
    playWithFriend: isPl ? 'Zagraj ze znajomym' : 'Play with a Friend',
    duelBadge: isPl ? 'Pojedynek 1v1' : '1v1 Live Duel',
    modes: isPl ? 'Codzienne mapy i wyzwania' : 'Daily Maps & Challenges',
    modeNote: isPl
      ? 'Dziewięć unikalnych wyzwań oraz pojedynki 1v1 na żywo.'
      : 'Nine daily geography modes plus real-time 1v1 multiplayer duels.',
    duelBannerTitle: isPl ? 'Zmierz się ze znajomym w czasie rzeczywistym' : 'Duel a Friend in Real-Time',
    duelBannerDesc: isPl
      ? 'Wybierzcie swoje tajne państwa, zadawajcie pytania na zmianę i sprawdźcie, kto szybciej odgadnie lokalizację z natychmiastowym sędzią AI.'
      : 'Pick secret entities, exchange natural-language questions, and race to deduce each other’s location with an instant AI referee.',
    duelBannerCta: isPl ? 'Rozpocznij pojedynek' : 'Start a Duel',
    questions: isPl ? 'Pytania' : 'Questions',
    guesses: isPl ? 'Próby' : 'Guesses',
    play: isPl ? 'Zagraj' : 'Play',
    how: isPl ? 'Od pytania do lokalizacji.' : 'From question to location.',
    howLabel: isPl ? 'Zasady gry' : 'How it works',
    steps: isPl
      ? [
          { title: 'Zadaj pytanie', text: 'Zacznij szeroko: czy to państwo leży na północy? Czy ma dostęp do morza?' },
          { title: 'Zawężaj mapę', text: 'Wykorzystaj odpowiedzi, aby eliminować opcje. Każde pytanie przybliża Cię do celu.' },
          { title: 'Podaj lokalizację', text: 'Gdy masz faworyta, zgadnij państwo. Wybieraj mądrze: liczba prób jest ograniczona.' },
        ]
      : [
          { title: 'Ask a question', text: 'Start broad: is the place in the north? Does it have a coastline?' },
          { title: 'Narrow the map', text: 'Use the answers to rule out possibilities. Each new question brings you closer.' },
          { title: 'Name the place', text: 'When you have a candidate, submit your guess. Choose carefully: attempts are limited.' },
        ],
    journalLabel: isPl ? 'Notatki z podróży' : 'Field notes',
    journalTitle: isPl ? 'Gra się kończy, odkrywanie trwa.' : 'The puzzle ends. The discovery doesn’t.',
    journalText: isPl
      ? 'Sprawdź poprzednie zagadki i poznaj fascynujące ciekawostki o odgadniętych miejscach.'
      : 'Revisit past puzzles and get to know the geographic lore behind each daily answer.',
    journalLink: isPl ? 'Odwiedź bloga' : 'Explore the blog',
  };

  const games = [
    { id: 'world', title: t('home.games.worldTitle'), region: 'The world',
      description: 'From islands to landlocked nations. Find the mystery country.',
      path: '/game', icon: Globe, questions: 10, guesses: 3, count: 195 },
    { id: 'flagdle', title: 'Flagdle', region: isPl ? 'Codzienne flagi' : 'Daily Flags',
      description: isPl
        ? 'Odkrywanie 12 pól i matryca kolorów. Zgadnij flagę w maksymalnie 12 próbach.'
        : 'Progressive unmasking and color matrix. Deduce the daily secret flag in 12 guesses.',
      path: '/flagdle', icon: Flag, questions: 0, guesses: 12, count: 195 },
    { id: 'europe', title: t('europeTitle', { defaultValue: 'Europedle' }), region: 'Europe',
      description: 'From Nordic fjords to Mediterranean archipelagos. Find the mystery European country.',
      path: '/europe', icon: Compass, questions: 8, guesses: 3, count: 47 },
    { id: 'asia', title: t('asiaTitle', { defaultValue: 'Asiadle' }), region: 'Asia',
      description: 'Steppes, islands, and ancient civilizations. Pinpoint the hidden Asian nation.',
      path: '/asia', icon: Globe2, questions: 8, guesses: 3, count: 46 },
    { id: 'africa', title: t('africaTitle', { defaultValue: 'Africadle' }), region: 'Africa',
      description: 'Deserts, savannas, and vibrant cultures. Discover today’s mystery African country.',
      path: '/africa', icon: Sun, questions: 8, guesses: 3, count: 54 },
    { id: 'americas', title: t('americasTitle', { defaultValue: 'Americadle' }), region: 'The Americas',
      description: 'Spanning from the Arctic tundra to Patagonia. Uncover the mystery American state.',
      path: '/americas', icon: Map, questions: 8, guesses: 3, count: 35 },
    { id: 'us-states', title: t('home.games.usStatesTitle'), region: 'United States',
      description: 'Coastlines, borders and regions. Which state fits the clues?',
      path: '/us-states', icon: Map, questions: 8, guesses: 3, count: 50 },
    { id: 'powiaty', title: t('home.games.powiatyTitle'), region: 'Poland / Counties',
      description: 'Take a closer look at Poland. Track down the hidden county.',
      path: '/powiaty', icon: MapPin, questions: 15, guesses: 3, count: 380 },
    { id: 'wojewodztwa', title: t('home.games.wojewodztwaTitle'), region: 'Poland / Voivodeships',
      description: 'Think regionally. Identify the voivodeship with just a few questions.',
      path: '/wojewodztwa', icon: Flag, questions: 5, guesses: 2, count: 16 },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6 md:pb-24 md:pt-14">
      {/* Hero Section */}
      <section aria-labelledby="home-heading" className="grid items-center gap-10 border-b border-white/10 pb-12 md:grid-cols-[1.35fr_1fr] md:gap-12 md:pb-16">
        <div>
          {/* Eyebrow badge */}
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-emerald-400">
            <Sparkles size={13} className="text-emerald-400" aria-hidden="true" />
            <span>{copy.eyebrow}</span>
            <span className="text-emerald-500/60" aria-hidden="true">·</span>
            <span className="text-zinc-400">{copy.eyebrowTag}</span>
          </div>

          <h1 id="home-heading" className="text-4xl font-extrabold tracking-tight text-sand-50 sm:text-5xl lg:text-6xl">
            {copy.title}{' '}
            <span className="block mt-1 bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-300 bg-clip-text text-transparent">
              {copy.titleEnd}
            </span>
          </h1>

          <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-300 md:text-lg">
            {copy.intro}
          </p>

          {/* Action buttons in cohesive derivative emerald-obsidian palette */}
          <div className="mt-8 flex flex-wrap items-center gap-3.5">
            <Link
              to="/game"
              className="inline-flex min-h-12 items-center justify-center gap-2.5 rounded-md bg-emerald-400 px-6 py-3 text-sm font-semibold text-obsidian-950 shadow-sm shadow-emerald-950/40 transition-all hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
            >
              <span>{playLabel}</span>
              <ArrowRight size={16} aria-hidden="true" />
            </Link>

            <Link
              to="/friends"
              className="inline-flex min-h-12 items-center justify-center gap-2.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-5 py-3 text-sm font-semibold text-emerald-300 transition-all hover:border-emerald-400/60 hover:bg-emerald-500/20 hover:text-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
            >
              <Users size={16} className="text-emerald-400" aria-hidden="true" />
              <span>{copy.playWithFriend}</span>
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/15 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                {copy.duelBadge}
              </span>
            </Link>

            <a
              href="#maps"
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-300 transition-all hover:border-emerald-400/30 hover:bg-emerald-500/5 hover:text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
            >
              <span>{copy.choose}</span>
              <ArrowDown size={15} aria-hidden="true" />
            </a>
          </div>

          {progressNote && (
            <p role="status" className="mt-4 flex items-center gap-2 font-mono text-xs text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
              {progressNote}
            </p>
          )}
          {guest && error && (
            <p role="status" className="mt-3 text-xs text-slate-400">
              We couldn’t check today’s progress. Open the puzzle to try again.
            </p>
          )}
        </div>

        {/* Dynamic 3D Green Transparent Spinning Globe */}
        <div className="w-full">
          <SpinningGlobe size={340} />
        </div>
      </section>

      {guest && (
        <div className="pt-8">
          <GuestProgress gameType="country" today={today} />
        </div>
      )}

      {/* Daily Maps & Challenges */}
      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 py-10 md:py-14">
        <div className="mb-6 flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <h2 id="maps-heading" className="text-2xl font-bold tracking-tight text-sand-50 sm:text-3xl">
              {copy.modes}
            </h2>
            <p className="mt-1 text-sm text-slate-400">{copy.modeNote}</p>
          </div>
        </div>

        {/* Featured 1v1 Duel Banner in cohesive Obsidian-Emerald palette */}
        <div className="mb-6 flex flex-col items-start justify-between gap-5 rounded-lg border border-emerald-500/30 bg-gradient-to-r from-emerald-950/40 via-obsidian-900 to-obsidian-900 p-6 md:flex-row md:items-center md:p-7 shadow-lg shadow-emerald-950/20">
          <div className="max-w-2xl space-y-2">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
                <Users size={13} className="text-emerald-400" aria-hidden="true" />
                {copy.duelBadge}
              </span>
              <span className="font-mono text-xs text-zinc-400">Multiplayer 1v1</span>
            </div>
            <h3 className="text-xl font-bold tracking-tight text-sand-50 md:text-2xl">
              {copy.duelBannerTitle}
            </h3>
            <p className="text-sm leading-relaxed text-slate-300">
              {copy.duelBannerDesc}
            </p>
          </div>

          <Link
            to="/friends"
            className="inline-flex min-h-12 shrink-0 items-center gap-3 rounded-md bg-emerald-400 px-6 py-3 text-sm font-semibold text-obsidian-950 shadow-sm shadow-emerald-950/40 transition-all hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
          >
            <span>{copy.duelBannerCta}</span>
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>

        {/* Game Cards Grid */}
        <div className="grid gap-3.5 sm:grid-cols-2">
          {games.map((game, index) => (
            <Link
              key={game.id}
              to={game.path}
              className="group flex flex-col rounded-lg border border-white/10 bg-obsidian-900/80 p-6 backdrop-blur-sm transition-all hover:border-emerald-500/40 hover:bg-obsidian-850 hover:shadow-lg hover:shadow-emerald-950/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 md:p-7"
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                  {String(index + 1).padStart(2, '0')} / {game.region}
                </span>
                <game.icon size={22} strokeWidth={1.5} className="shrink-0 text-emerald-400 transition-transform group-hover:scale-110" aria-hidden="true" />
              </div>
              <h3 className="break-words text-2xl font-bold tracking-tight text-sand-50 group-hover:text-white">
                {game.title}
              </h3>
              <p className="mb-6 mt-2.5 max-w-md flex-1 text-sm leading-relaxed text-slate-400">
                {game.description}
              </p>
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-4">
                <dl className="flex gap-5 text-xs">
                  <div className="flex items-baseline gap-2">
                    <dt className="text-slate-400">{copy.questions}</dt>
                    <dd className="font-mono font-medium text-sand-100">{game.questions}</dd>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <dt className="text-slate-400">{copy.guesses}</dt>
                    <dd className="font-mono font-medium text-sand-100">{game.guesses}</dd>
                  </div>
                </dl>
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-400 transition-all group-hover:gap-3 group-hover:text-emerald-300">
                  {copy.play}
                  <ArrowRight size={16} aria-hidden="true" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* How to Play Section */}
      <section aria-labelledby="how-heading" className="border-y border-white/10 py-10 md:py-14">
        <div className="mb-8">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">
            {copy.howLabel}
          </p>
          <h2 id="how-heading" className="text-2xl font-bold tracking-tight text-sand-50 sm:text-3xl">
            {copy.how}
          </h2>
        </div>

        <ol className="grid gap-6 md:grid-cols-3 md:gap-8">
          {copy.steps.map((step, index) => (
            <li
              key={step.title}
              className="flex flex-col rounded-lg border border-white/5 bg-obsidian-900/40 p-5 md:p-6"
            >
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/10 font-mono text-xs font-semibold text-emerald-400">
                  0{index + 1}
                </span>
                <h3 className="font-semibold text-sand-50">{step.title}</h3>
              </div>
              <p className="text-sm leading-relaxed text-slate-400">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Blog & Lore Section */}
      <section aria-labelledby="journal-heading" className="flex flex-col justify-between gap-6 pt-10 sm:flex-row sm:items-center md:pt-14">
        <div className="max-w-xl">
          <p className="mb-2.5 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400/80">
            <BookOpen size={14} aria-hidden="true" />
            {copy.journalLabel}
          </p>
          <h2 id="journal-heading" className="text-2xl font-bold tracking-tight text-sand-50 sm:text-3xl">
            {copy.journalTitle}
          </h2>
          <p className="mt-2.5 text-sm leading-relaxed text-slate-400">
            {copy.journalText}
          </p>
        </div>

        <Link
          to="/blog"
          className="inline-flex min-h-12 shrink-0 items-center justify-center gap-3 self-start rounded-md border border-emerald-500/30 bg-emerald-500/5 px-6 py-3 text-sm font-semibold text-emerald-300 transition-all hover:border-emerald-400/50 hover:bg-emerald-500/15 hover:text-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 sm:self-auto"
        >
          <span>{copy.journalLink}</span>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}
