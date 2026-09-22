import { useEffect, useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { getContinentalStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import History from '../components/History';
import GuessInput from '../components/GuessInput';
import GuessHistory from '../components/GuessHistory';
import { ControlledMapBox } from '../components/MapBox';
import GameInstructions from '../components/GameInstructions';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import GuestProgress from '../components/GuestProgress';
import { useDailyDate } from '../hooks/useDailyClock';

export type ContinentKey = 'europe' | 'asia' | 'africa' | 'americas';
interface ContinentalGamePageProps {
  continent?: ContinentKey;
}

interface ContinentMeta {
  key: ContinentKey;
  title: string;
  subtitle: string;
  path: string;
  count: number;
  center: [number, number];
  zoom: number;
  minZoom: number;
  maxZoom: number;
}

const CONTINENT_META: Record<ContinentKey, ContinentMeta> = {
  europe: {
    key: 'europe',
    title: 'Europedle',
    subtitle: '47 European Nations · 8 Questions · 3 Guesses',
    path: '/europe',
    count: 47,
    center: [52, 16],
    zoom: 3.8,
    minZoom: 2.5,
    maxZoom: 8,
  },
  asia: {
    key: 'asia',
    title: 'Asiadle',
    subtitle: '47 Asian Nations · 8 Questions · 3 Guesses',
    path: '/asia',
    count: 47,
    center: [34, 95],
    zoom: 3,
    minZoom: 2,
    maxZoom: 8,
  },
  africa: {
    key: 'africa',
    title: 'Africadle',
    subtitle: '54 African Nations · 8 Questions · 3 Guesses',
    path: '/africa',
    count: 54,
    center: [2, 20],
    zoom: 3,
    minZoom: 2,
    maxZoom: 8,
  },
  americas: {
    key: 'americas',
    title: 'Americadle',
    subtitle: '35 Nations (23 North + 12 South) · 8 Questions · 3 Guesses',
    path: '/americas',
    count: 35,
    center: [15, -85],
    zoom: 2.5,
    minZoom: 1.8,
    maxZoom: 8,
  },
};

export default function ContinentalGamePage({ continent: continentProp }: ContinentalGamePageProps) {
  const { continent: continentParam } = useParams<{ continent?: string }>();
  const location = useLocation();

  const activeContinent: ContinentKey = useMemo(() => {
    if (continentProp && continentProp in CONTINENT_META) {
      return continentProp;
    }
    if (continentParam && continentParam in CONTINENT_META) {
      return continentParam as ContinentKey;
    }
    const pathSegment = location.pathname.replace(/^\//, '').split('/')[0] as ContinentKey;
    if (pathSegment in CONTINENT_META) {
      return pathSegment;
    }
    return 'europe';
  }, [continentProp, continentParam, location.pathname]);

  const meta = CONTINENT_META[activeContinent];
  const useStore = getContinentalStore(activeContinent);

  const {
    gameState,
    questions,
    guesses,
    entities: countries,
    correctEntity: correctCountry,
    isLoading,
    fetchGameState,
    fetchEntities: fetchCountries,
    askQuestion,
    makeGuess,
    syncGuestData,
    isGuest,
    dailyDate,
    entityMarkings,
    activeMarkerColor,
    setActiveMarkerColor,
    handleEntityMapClick,
    clearMapMarkings,
  } = useStore();

  const { t } = useTranslation();
  const today = useDailyDate();

  useEffect(() => {
    fetchGameState();
    fetchCountries();
    const handleLogin = () => {
      syncGuestData();
    };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, [activeContinent, fetchGameState, fetchCountries, syncGuestData]);

  if (!gameState && isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="animate-spin text-emerald-500" size={32} />
      </div>
    );
  }

  if (!gameState) return null;

  const title = t(`${activeContinent}Title`, { defaultValue: meta.title });
  const subtitle = t(`${activeContinent}Subtitle`, { defaultValue: meta.subtitle });

  return (
    <div className="mx-auto w-full max-w-7xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div>
          <p className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
            <span>Daily fieldwork</span>
            <span className="text-zinc-400">{dailyDate}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight text-sand-100 sm:text-2xl">{title}</h1>
          <p className="mt-0.5 text-xs text-zinc-400">{subtitle}</p>
          {isGuest && <p className="mt-1 text-xs text-zinc-500">Guest · no account needed</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <dl className="flex divide-x divide-white/10 rounded-sm border border-white/10 bg-obsidian-900">
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.questionsLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-sand-100">
                {gameState.remaining_questions}
                <span className="text-xs text-zinc-500"> / 8</span>
              </dd>
            </div>
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.guessesLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-emerald-400">
                {gameState.remaining_guesses}
                <span className="text-xs text-zinc-500"> / 3</span>
              </dd>
            </div>
          </dl>
          <GameInstructions
            gameName={title}
            examples={[
              t('instructions.example1', { defaultValue: 'Is the country landlocked?' }),
              t('instructions.example2', { defaultValue: 'Does it border Germany?' }),
              t('instructions.example3', { defaultValue: 'Is the population over 10 million?' }),
            ]}
            scoring={{
              maxPoints: 3300,
              details: [
                'Base win floor: +500 pts',
                'Question bonus: up to +1,500 pts (rewards using fewer questions)',
                'Guess accuracy: up to +500 pts on first try',
                'Speed bonus: up to +300 pts within 5 minutes',
                'Streak bonus: +50 pts per day (capped at +500 pts)',
              ],
            }}
          />
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.48fr)]">
        <section className="min-w-0 space-y-5" aria-label="Map and deduction">
          <div className="overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">
              <span>Atlas / {title}</span>
              <span className="text-emerald-400">{gameState.is_game_over ? 'Result' : 'Search area'}</span>
            </div>
            <div className="relative h-[310px] sm:h-[420px] lg:h-[460px]">
              <ControlledMapBox
                correctCountryName={gameState.is_game_over ? correctCountry?.name : undefined}
                className="h-full"
                center={meta.center}
                zoom={meta.zoom}
                minZoom={meta.minZoom}
                maxZoom={meta.maxZoom}
                interaction={{
                  entityMarkings,
                  activeMarkerColor,
                  setActiveMarkerColor,
                  handleEntityMapClick,
                  clearMapMarkings,
                  isGameOver: !!gameState.is_game_over,
                }}
              />
            </div>
          </div>
          {gameState.is_game_over ? (
            <ShareResultCard
              gameName={title}
              gamePath={meta.path}
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={8}
              guessesMade={gameState.guesses_made}
              maxGuesses={3}
              targetName={correctCountry?.name || guesses.find((g: { answer?: boolean; guess: string }) => g.answer)?.guess}
              isGuest={isGuest}
              discovery={questions.find((q: { valid: boolean; explanation?: string }) => q.valid && q.explanation)?.explanation}
            />
          ) : (
            <div className="space-y-5 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
              <div>
                <h2 className="mb-2 text-sm font-medium text-sand-100">Ask a yes-or-no question</h2>
                <QuestionInput
                  onAsk={askQuestion}
                  isLoading={isLoading}
                  remainingQuestions={gameState.remaining_questions}
                  placeholder={t('askPlaceholder', {
                    count: gameState.remaining_questions,
                    defaultValue: `Ask a yes/no question about the country... (${gameState.remaining_questions} left)`,
                  })}
                />
              </div>
              <div className="border-t border-white/10 pt-4">
                <h2 className="mb-2 text-sm font-medium text-sand-100">Name the location</h2>
                <GuessInput
                  countries={countries}
                  onGuess={async (id, name) => makeGuess(name, id)}
                  onUnknownGuess={async name => makeGuess(name, 0)}
                  isLoading={isLoading}
                  remainingGuesses={gameState.remaining_guesses}
                  placeholder={t('guessPlaceholder', {
                    count: gameState.remaining_guesses,
                    defaultValue: `Guess the country... (${gameState.remaining_guesses} left)`,
                  })}
                />
              </div>
            </div>
          )}
          {isGuest && <GuestProgress gameType={activeContinent} today={today} />}
        </section>

        <aside className="min-w-0 rounded-sm border border-white/10 bg-obsidian-900" aria-label="Deduction notebook">
          <section className="border-b border-white/10 p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-sand-100">{t('gamePage.yourGuesses')}</h2>
              <span className="font-mono text-xs text-zinc-500">{guesses.length.toString().padStart(2, '0')}</span>
            </div>
            <GuessHistory guesses={guesses} />
          </section>
          <section className="p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-sand-100">{t('gamePage.history')}</h2>
              <span className="font-mono text-xs text-zinc-500">{questions.length.toString().padStart(2, '0')}</span>
            </div>
            <History mode="countrydle" questions={questions} isGameOver={gameState.is_game_over} />
          </section>
        </aside>
      </div>
    </div>
  );
}
