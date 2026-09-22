import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, BookOpen, Compass, Flag, Globe, Globe2, Map, MapPin, Sun, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import GuestProgress from '../components/GuestProgress';
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
    eyebrow: isPl ? 'Codzienna łamigłówka geograficzna' : 'The daily geography puzzle',
    title: isPl ? 'Cały świat.' : 'A whole world.',
    titleEnd: isPl ? 'Jedno ukryte miejsce.' : 'One hidden place.',
    intro: isPl
      ? 'Odkryj dzisiejsze ukryte państwo pytaniami tak/nie. Masz 10 pytań i 3 próby. Bez konieczności logowania.'
      : 'Find today’s hidden country with yes-or-no questions. You have 10 questions and 3 guesses. No sign-up needed.',
    choose: isPl ? 'Przeglądaj wszystkie mapy' : 'Explore other maps',
    playWithFriend: isPl ? 'Zagraj ze znajomym' : 'Play with a Friend',
    duelBadge: isPl ? 'Pojedynek 1v1' : '1v1 Live Duel',
    atlas: isPl ? 'Atlas dedukcji' : 'An atlas of deduction',
    diagram: isPl ? 'Szerokość i długość geograficzna' : 'Latitude and longitude',
    modes: isPl ? 'Codzienne mapy i wyzwania' : 'Daily Maps & Challenges',
    modeNote: isPl
      ? 'Dziewięć unikalnych map codziennych oraz pojedynki 1v1 na żywo.'
      : 'Nine unique daily game modes plus real-time 1v1 multiplayer duels.',
    duelBannerTitle: isPl ? 'Zmierz się ze znajomym w czasie rzeczywistym' : 'Duel a Friend in Real-Time',
    duelBannerDesc: isPl
      ? 'Wybierzcie swoje tajne państwa, zadawajcie pytania na zmianę i sprawdźcie, kto szybciej odgadnie lokalizację z natychmiastowym sędzią AI.'
      : 'Pick your secret country or state, exchange natural-language questions, and race to deduce each other’s location with an instant AI referee.',
    duelBannerCta: isPl ? 'Rozpocznij pojedynek' : 'Start a Duel',
    questions: isPl ? 'Pytania' : 'Questions',
    guesses: isPl ? 'Próby' : 'Guesses',
    play: isPl ? 'Zagraj' : 'Play',
    how: isPl ? 'Od pytania do lokalizacji.' : 'From question to location.',
    howLabel: isPl ? 'Jak grać' : 'How to play',
    steps: isPl
      ? [
          { title: 'Zadaj pytanie', text: 'Zacznij szeroko: czy to państwo leży na północy? Czy ma dostęp do morza?' },
          { title: 'Zawężaj mapę', text: 'Wykorzystaj odpowiedzi, aby eliminować opcje. Każde pytanie przybliża Cię do celu.' },
          { title: 'Podaj lokalizację', text: 'Gdy masz faworyta, zgadnij państwo. Wybieraj mądrze: liczba prób jest ograniczona.' },
        ]
      : [
          { title: 'Ask a question', text: 'Start broad: is the place in the north? Does it have a coastline?' },
          { title: 'Narrow the map', text: 'Use the answers to rule out possibilities. Each new question can bring you closer.' },
          { title: 'Name the place', text: 'When you have a candidate, submit your guess. Choose carefully: your attempts are limited.' },
        ],
    journalLabel: isPl ? 'Notatki z podróży' : 'Field notes',
    journalTitle: isPl ? 'Gra się kończy, odkrywanie trwa.' : 'The puzzle ends. The discovery doesn’t.',
    journalText: isPl
      ? 'Sprawdź poprzednie zagadki i poznaj fascynujące ciekawostki o odgadniętych miejscach.'
      : 'Revisit past puzzles and get to know the places behind the answers.',
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
      path: '/asia', icon: Globe2, questions: 8, guesses: 3, count: 47 },
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
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 md:pb-24 md:pt-16">
      <section aria-labelledby="home-heading" className="grid items-center gap-10 border-b border-white/10 pb-12 md:grid-cols-[1.4fr_1fr] md:pb-16">
        <div>
          <p className="mb-6 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">
            <span aria-hidden="true" className="h-px w-7 bg-emerald-400" />
            {copy.eyebrow}
          </p>
          <h1 id="home-heading" className="text-4xl font-semibold leading-[1.08] tracking-tight text-sand-100 sm:text-5xl lg:text-6xl">
            {copy.title}
            <span className="mt-2 block font-serif font-normal italic text-sand-200">{copy.titleEnd}</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-slate-400 md:text-lg">{copy.intro}</p>
          <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-3">
            <Link to="/game" className="inline-flex min-h-12 items-center gap-3 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
              {playLabel}<ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link
              to="/friends"
              className="inline-flex min-h-12 items-center gap-2.5 rounded-sm border border-amber-400/40 bg-amber-400/10 px-5 py-3 text-sm font-semibold text-amber-200 transition-all hover:border-amber-400 hover:bg-amber-400/20 hover:text-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber-400"
            >
              <Users size={17} className="text-amber-400" aria-hidden="true" />
              <span>{copy.playWithFriend}</span>
              <span className="rounded-full bg-amber-400/20 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-300">
                {copy.duelBadge}
              </span>
            </Link>
            <a href="#maps" className="inline-flex min-h-12 items-center gap-2 rounded-sm px-3 py-3 text-sm font-medium text-sand-200 transition-colors hover:text-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
              {copy.choose}<ArrowDown size={16} aria-hidden="true" />
            </a>
          </div>
          {progressNote && <p role="status" className="mt-3 text-sm text-emerald-400">{progressNote}</p>}
          {guest && error && <p role="status" className="mt-3 text-xs text-slate-400">We couldn’t check today’s progress. Open the puzzle to try again.</p>}
        </div>

        <figure className="mx-auto hidden w-full max-w-sm md:block">
          <svg viewBox="0 0 360 310" fill="none" className="w-full text-emerald-400" aria-hidden="true">
            <path d="M26 155h308M180 16v278" stroke="currentColor" strokeOpacity="0.18" strokeDasharray="3 6" />
            <circle cx="180" cy="155" r="124" stroke="currentColor" strokeOpacity="0.5" />
            <ellipse cx="180" cy="155" rx="83" ry="124" stroke="currentColor" strokeOpacity="0.22" />
            <ellipse cx="180" cy="155" rx="34" ry="124" stroke="currentColor" strokeOpacity="0.22" />
            <path d="M73 93h214M56 155h248M73 217h214" stroke="currentColor" strokeOpacity="0.22" />
            <circle cx="180" cy="155" r="5" fill="currentColor" />
            <path d="M170 155h-13m46 0h-13m-10-10v-13m0 46v-13" stroke="currentColor" />
            <text x="313" y="159" fill="currentColor" fillOpacity="0.7" fontSize="10" fontFamily="monospace">0°</text>
          </svg>
          <figcaption className="flex justify-between border-t border-white/10 pt-3 font-mono text-[10px] uppercase tracking-wider text-slate-500">
            <span>{copy.atlas}</span><span>{copy.diagram}</span>
          </figcaption>
        </figure>
      </section>

      {guest && (
        <div className="pt-8">
          <GuestProgress gameType="country" today={today} />
        </div>
      )}

      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 py-10 md:py-14">
        <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <h2 id="maps-heading" className="text-2xl font-semibold tracking-tight text-sand-100">{copy.modes}</h2>
          <p className="text-sm text-slate-400">{copy.modeNote}</p>
        </div>

        {/* Featured 1v1 Duel Banner */}
        <div className="mb-6 rounded-sm border border-amber-400/30 bg-gradient-to-r from-amber-950/40 via-obsidian-900 to-obsidian-900 p-6 md:p-7 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          <div className="space-y-1.5 max-w-2xl">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/15 border border-amber-400/30 px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-amber-300">
                <Users size={13} className="text-amber-400" aria-hidden="true" />
                {copy.duelBadge}
              </span>
              <span className="font-mono text-xs text-zinc-400">Multiplayer 1v1</span>
            </div>
            <h3 className="text-xl md:text-2xl font-bold tracking-tight text-sand-100">
              {copy.duelBannerTitle}
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed">
              {copy.duelBannerDesc}
            </p>
          </div>
          <Link
            to="/friends"
            className="inline-flex min-h-12 shrink-0 items-center gap-3 rounded-sm bg-amber-400 px-6 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-amber-400"
          >
            <span>{copy.duelBannerCta}</span>
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {games.map((game, index) => (
            <Link key={game.id} to={game.path} className="group flex flex-col rounded-sm border border-white/10 bg-obsidian-900 p-6 transition-colors hover:border-emerald-400/50 hover:bg-obsidian-850 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 md:p-7">
              <div className="mb-5 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">{String(index + 1).padStart(2, '0')} / {game.region}</span>
                <game.icon size={22} strokeWidth={1.5} className="shrink-0 text-emerald-400" aria-hidden="true" />
              </div>
              <h3 className="break-words text-2xl font-semibold tracking-tight text-sand-100">{game.title}</h3>
              <p className="mb-7 mt-3 max-w-md flex-1 text-sm leading-relaxed text-slate-400">{game.description}</p>
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-4">
                <dl className="flex gap-5 text-xs">
                  <div className="flex items-baseline gap-2"><dt className="text-slate-400">{copy.questions}</dt><dd className="font-mono text-sand-100">{game.questions}</dd></div>
                  <div className="flex items-baseline gap-2"><dt className="text-slate-400">{copy.guesses}</dt><dd className="font-mono text-sand-100">{game.guesses}</dd></div>
                </dl>
                <span className="inline-flex items-center gap-3 text-sm font-medium text-emerald-400">{copy.play}<ArrowRight size={17} aria-hidden="true" /></span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="how-heading" className="border-y border-white/10 py-9 md:py-12">
        <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">{copy.howLabel}</p>
        <h2 id="how-heading" className="text-2xl font-semibold tracking-tight text-sand-100">{copy.how}</h2>
        <ol className="mt-7 grid gap-7 md:grid-cols-3 md:gap-10">
          {copy.steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span aria-hidden="true" className="mt-1 font-mono text-xs text-emerald-400">0{index + 1}</span>
              <div><h3 className="font-medium text-sand-100">{step.title}</h3><p className="mt-2 text-sm leading-relaxed text-slate-400">{step.text}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="journal-heading" className="flex flex-col justify-between gap-6 pt-10 sm:flex-row sm:items-center md:pt-12">
        <div className="max-w-xl">
          <p className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-400"><BookOpen size={14} aria-hidden="true" />{copy.journalLabel}</p>
          <h2 id="journal-heading" className="font-serif text-2xl text-sand-100">{copy.journalTitle}</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">{copy.journalText}</p>
        </div>
        <Link to="/blog" className="inline-flex min-h-12 shrink-0 items-center justify-center gap-4 self-start rounded-sm border border-white/20 px-5 py-3 text-sm font-medium text-sand-100 transition-colors hover:border-emerald-400/50 hover:text-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 sm:self-auto">
          {copy.journalLink}<ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}
