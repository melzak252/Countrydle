import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, BookOpen, ChevronDown, Compass, Flag, Globe2, Map, MapPin, Sun, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import GuestProgress from '../components/GuestProgress';
import SpinningGlobe from '../components/SpinningGlobe';
import { useDailyDate } from '../hooks/useDailyClock';
import { useAuthStore } from '../stores/authStore';
import { useCountryGameStore } from '../stores/gameStore';

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
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
  const checkingProgress = authLoading || (guest && (isLoading || (!error && !currentGuestState)));
  const playLabel = currentGuestState?.is_game_over
    ? (isPl ? 'Zobacz dzisiejszy wynik' : 'View today’s result')
    : hasStarted
      ? (isPl ? 'Kontynuuj dzisiejszą grę' : 'Continue today’s country')
      : guest && error
        ? (isPl ? 'Otwórz dzisiejszą grę' : 'Open today’s country')
        : checkingProgress
          ? (isPl ? 'Otwórz dzisiejszą grę' : 'Open today’s country')
          : (isPl ? 'Zagraj w dzisiejszą grę' : 'Play today’s country');
  const progressNote = guest && error
    ? (isPl ? 'Nie udało się sprawdzić postępu. Otwórz grę, aby spróbować ponownie.' : 'We couldn’t check your progress. Open the puzzle to try again.')
    : checkingProgress
      ? (isPl ? 'Sprawdzamy dzisiejszy postęp…' : 'Checking today’s progress…')
      : currentGuestState?.is_game_over
        ? (isPl ? 'Dzisiejsza zagadka jest ukończona. Twój wynik jest gotowy.' : 'Today’s puzzle is complete. Your result is ready.')
        : hasStarted
          ? (isPl
            ? `Pozostałe pytania: ${currentGuestState.remaining_questions}. Pozostałe próby: ${currentGuestState.remaining_guesses}.`
            : `${currentGuestState.remaining_questions} questions and ${currentGuestState.remaining_guesses} guesses remaining today.`)
          : null;
  const copy = {
    daily: isPl ? 'Codzienna zagadka geograficzna' : 'Your daily geography puzzle',
    title: isPl ? 'Jeden świat.' : 'One world.',
    titleEnd: isPl ? 'Ukryte państwo.' : 'One hidden country.',
    intro: isPl
      ? 'Odkryj je pytaniami tak/nie. 10 pytań, 3 próby. Bez logowania.'
      : 'Find it with yes-or-no questions. 10 questions, 3 guesses. No sign-in needed.',
    choose: isPl ? 'Wybierz inną grę' : 'Explore other games',
    modes: isPl ? 'Co odkryjesz dalej?' : 'What will you discover next?',
    modeNote: isPl ? 'Wybierz flagi, kontynent lub mniejszą mapę.' : 'Choose flags, a continent or a closer look at the map.',
    flags: isPl ? 'Flagi' : 'Flags',
    continents: isPl ? 'Kontynenty' : 'Continents',
    regions: isPl ? 'Stany i regiony' : 'States and regions',
    questions: isPl ? 'Pytania' : 'Questions',
    guesses: isPl ? 'Próby' : 'Guesses',
    progress: isPl ? 'Twój postęp na tym urządzeniu' : 'Your progress on this device',
    how: isPl ? 'Jak grać w zagadkę państwa' : 'How to play the country puzzle',
    reset: isPl ? 'Nowa zagadka każdego dnia o 00:00 UTC.' : 'A new puzzle every day at 00:00 UTC.',
    steps: isPl
      ? [
          { title: 'Zadaj pytanie', text: 'Zacznij szeroko: czy państwo leży w Europie? Czy ma dostęp do morza? Otrzymasz odpowiedź tak lub nie.' },
          { title: 'Zawężaj mapę', text: 'Wykorzystaj odpowiedzi, aby wykluczać państwa. Masz 10 pytań, więc wybieraj je uważnie.' },
          { title: 'Zgadnij państwo', text: 'Wybierz państwo, gdy masz faworyta. Masz 3 próby odgadnięcia dzisiejszej odpowiedzi.' },
        ]
      : [
          { title: 'Ask a question', text: 'Start broad: is the country in Europe? Does it have a coastline? You’ll get a yes-or-no answer.' },
          { title: 'Narrow the map', text: 'Use the answers to rule out countries. You have 10 questions, so choose them carefully.' },
          { title: 'Guess the country', text: 'Choose a country when you have a candidate. You have 3 guesses to find today’s answer.' },
        ],
    friendTitle: isPl ? 'Zagraj ze znajomym' : 'Play with a friend',
    friendText: isPl ? 'Wybierzcie tajne miejsca i zmierzcie się w pojedynku 1 na 1.' : 'Choose secret places and race to find each other’s answer in a live duel.',
    blogTitle: isPl ? 'Poznaj historie miejsc' : 'Discover the stories behind the places',
    blogText: isPl ? 'Poprzednie zagadki, ciekawostki i geograficzne inspiracje na blogu.' : 'Past puzzles, surprising facts and more geography to explore on the blog.',
  };
  const gameGroups = [
    {
      title: copy.flags,
      games: [
        { id: 'flagdle', title: 'Flagdle', region: isPl ? 'Flagi świata' : 'World flags',
          description: isPl ? 'Odkrywaj flagę pole po polu i korzystaj z podpowiedzi kolorów. Masz 12 prób.' : 'Reveal the flag tile by tile and use color clues. You have 12 guesses.',
          path: '/flagdle', icon: Flag, questions: null, guesses: 12 },
      ],
    },
    {
      title: copy.continents,
      games: [
        { id: 'europe', title: isPl ? 'Europedle' : t('europeTitle', { defaultValue: 'Europedle' }), region: isPl ? 'Europa' : 'Europe',
          description: isPl ? 'Od nordyckich fiordów po śródziemnomorskie wyspy. Znajdź ukryte państwo Europy.' : 'From Nordic fjords to Mediterranean islands. Find the hidden European country.',
          path: '/europe', icon: Compass, questions: 8, guesses: 3 },
        { id: 'asia', title: isPl ? 'Asiadle' : t('asiaTitle', { defaultValue: 'Asiadle' }), region: isPl ? 'Azja' : 'Asia',
          description: isPl ? 'Stepy, wyspy i dawne cywilizacje. Odkryj dzisiejsze państwo Azji.' : 'Steppes, islands and ancient civilizations. Discover today’s Asian country.',
          path: '/asia', icon: Globe2, questions: 8, guesses: 3 },
        { id: 'africa', title: isPl ? 'Africadle' : t('africaTitle', { defaultValue: 'Africadle' }), region: isPl ? 'Afryka' : 'Africa',
          description: isPl ? 'Pustynie, sawanny i różnorodne kultury. Odgadnij ukryte państwo Afryki.' : 'Deserts, savannas and vibrant cultures. Deduce the hidden African country.',
          path: '/africa', icon: Sun, questions: 8, guesses: 3 },
        { id: 'americas', title: isPl ? 'Americadle' : t('americasTitle', { defaultValue: 'Americadle' }), region: isPl ? 'Ameryki' : 'The Americas',
          description: isPl ? 'Od arktycznej tundry po Patagonię. Wskaż dzisiejsze państwo obu Ameryk.' : 'From the Arctic tundra to Patagonia. Find today’s country in the Americas.',
          path: '/americas', icon: Map, questions: 8, guesses: 3 },
      ],
    },
    {
      title: copy.regions,
      games: [
        { id: 'us-states', title: isPl ? 'Stany USA' : t('home.games.usStatesTitle'), region: isPl ? 'Stany Zjednoczone' : 'United States',
          description: isPl ? 'Wybrzeża, granice i regiony. Który stan pasuje do odpowiedzi?' : 'Coastlines, borders and regions. Which state fits the clues?',
          path: '/us-states', icon: Map, questions: 8, guesses: 3 },
        { id: 'powiaty', title: isPl ? 'Powiatdle' : t('home.games.powiatyTitle'), region: isPl ? 'Polska · powiaty' : 'Poland · counties',
          description: isPl ? 'Przyjrzyj się Polsce z bliska i znajdź ukryty powiat.' : 'Take a closer look at Poland and track down the hidden county.',
          path: '/powiaty', icon: MapPin, questions: 15, guesses: 3 },
        { id: 'wojewodztwa', title: isPl ? 'Województwodle' : t('home.games.wojewodztwaTitle'), region: isPl ? 'Polska · województwa' : 'Poland · voivodeships',
          description: isPl ? 'Myśl regionalnie. Odgadnij województwo za pomocą kilku pytań.' : 'Think regionally. Identify the voivodeship with just a few questions.',
          path: '/wojewodztwa', icon: Flag, questions: 5, guesses: 2 },
      ],
    },
  ];
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
          <SpinningGlobe size={380} />
        </div>
      </section>

      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 py-6 md:py-10">
        <h2 id="maps-heading" className="text-2xl font-bold tracking-tight text-sand-50">{copy.modes}</h2>
        <p className="mb-4 mt-2 text-sm leading-relaxed text-slate-400">{copy.modeNote}</p>
        <div className="space-y-3">
          {gameGroups.map((group) => (
            <details key={group.title} className={disclosureClass}>
              <summary className={summaryClass}>
                <span className="min-w-0">{group.title}</span>
                <ChevronDown size={18} className="shrink-0 text-emerald-400 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
              </summary>
              <div className="grid gap-2 border-t border-white/10 p-3 sm:grid-cols-2 md:p-4">
                {group.games.map((game) => (
                  <Link key={game.id} to={game.path} className="min-w-0 rounded-md border border-white/5 bg-obsidian-950/50 p-4 transition-colors hover:border-emerald-400/30 hover:bg-emerald-500/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs text-slate-400">{game.region}</p>
                        <h3 className="mt-1 break-words text-lg font-semibold text-sand-50">{game.title}</h3>
                      </div>
                      <game.icon size={22} className="shrink-0 text-emerald-400" aria-hidden="true" />
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400">{game.description}</p>
                    <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-300">
                      {game.questions !== null && <div className="flex gap-1.5"><dt>{copy.questions}:</dt><dd>{game.questions}</dd></div>}
                      <div className="flex gap-1.5"><dt>{copy.guesses}:</dt><dd>{game.guesses}</dd></div>
                    </dl>
                  </Link>
                ))}
              </div>
            </details>
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

      <section aria-label={isPl ? 'Graj i odkrywaj więcej' : 'More ways to play and explore'} className="mt-6 grid gap-3 sm:grid-cols-2">
        {[
          { path: '/friends', title: copy.friendTitle, text: copy.friendText, icon: Users },
          { path: '/blog', title: copy.blogTitle, text: copy.blogText, icon: BookOpen },
        ].map((item) => (
          <Link key={item.path} to={item.path} className="min-w-0 rounded-lg border border-white/10 p-4 transition-colors hover:border-emerald-400/30 hover:bg-emerald-500/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 md:p-5">
            <div className="flex items-start gap-3">
              <item.icon size={20} className="mt-0.5 shrink-0 text-emerald-400" aria-hidden="true" />
              <h2 className="min-w-0 flex-1 font-semibold text-sand-50">{item.title}</h2>
              <ArrowRight size={16} className="mt-1 shrink-0 text-emerald-400" aria-hidden="true" />
            </div>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">{item.text}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
