import { useEffect } from 'react';
import { usePowiatyGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import History from '../components/History';
import GuessInput from '../components/GuessInput';
import GuessHistory from '../components/GuessHistory';
import PowiatyMap from '../components/PowiatyMap';
import GameInstructions from '../components/GameInstructions';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import GuestProgress from '../components/GuestProgress';
import { useDailyDate } from '../hooks/useDailyClock';

export default function PowiatyGamePage() {
  const {
    gameState,
    questions,
    guesses,
    entities: powiaty,
    correctEntity: correctPowiat,
    isLoading,
    fetchGameState,
    fetchEntities: fetchPowiaty,
    askQuestion,
    makeGuess,
    syncGuestData,
    isGuest,
    dailyDate,
  } = usePowiatyGameStore();
  const { t } = useTranslation();
  const today = useDailyDate();
  

  useEffect(() => {
    fetchGameState();
    fetchPowiaty();
    const handleLogin = () => { syncGuestData(); };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, [fetchGameState, fetchPowiaty, syncGuestData]);

  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm">{'Loading the puzzle…'}</span>
      </div>
    );
  }

  if (!gameState) return null;

  return (
    <div className="mx-auto w-full max-w-7xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div>
          <p className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
            <span>{'Daily fieldwork'}</span>
            <span className="text-zinc-400">{dailyDate}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight text-sand-100 sm:text-2xl">{t('powiatyPage.title')}</h1>
          {isGuest && <p className="mt-1 text-xs text-zinc-400">Guest · no account needed</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <dl className="flex divide-x divide-white/10 rounded-sm border border-white/10 bg-obsidian-900">
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.questionsLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-sand-100">{gameState.remaining_questions}<span className="text-xs text-zinc-500"> / 15</span></dd>
            </div>
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.guessesLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-emerald-400">{gameState.remaining_guesses}<span className="text-xs text-zinc-500"> / 3</span></dd>
            </div>
          </dl>
          <GameInstructions
            gameName={t('powiatyPage.title')}
            examples={t('powiatyPage.examples', { returnObjects: true }) as string[]}
            scoring={{ maxPoints: 3800, details: t('powiatyPage.scoringDetails', { returnObjects: true }) as string[] }}
          />
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.48fr)]">
        <section className="min-w-0 space-y-5" aria-label={'Map and deduction'}>
          <div className="overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">
              <span>Atlas / Powiatdle</span>
              <span className="text-emerald-400">{gameState.is_game_over ? ('Result') : ('Search area')}</span>
            </div>
            <div className="relative h-[310px] sm:h-[420px] lg:h-[460px]">
              <PowiatyMap correctPowiatName={gameState.is_game_over ? correctPowiat?.nazwa : undefined} className="h-full" />
            </div>
          </div>

          {gameState.is_game_over ? (
            <ShareResultCard
              gameName="Powiatdle"
              gamePath="/powiaty"
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={15}
              guessesMade={gameState.guesses_made}
              maxGuesses={3}
              targetName={correctPowiat?.nazwa || guesses.find(g => g.answer)?.guess}
              isGuest={isGuest}
              discovery={questions.find(q => q.valid && q.explanation)?.explanation}
            />
          ) : (
            <div className="space-y-5 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
              <div>
                <h2 className="mb-2 text-sm font-medium text-sand-100">{'Ask a yes-or-no question'}</h2>
                <QuestionInput
                  onAsk={askQuestion}
                  isLoading={isLoading}
                  remainingQuestions={gameState.remaining_questions}
                  placeholder={t('powiatyPage.askPlaceholder', { count: gameState.remaining_questions })}
                />
              </div>
              <div className="border-t border-white/10 pt-4">
                <h2 className="mb-2 text-sm font-medium text-sand-100">{'Name the location'}</h2>
                <GuessInput
                  countries={powiaty}
                  onGuess={async (id, name) => makeGuess(name, id)}
                  onUnknownGuess={async name => makeGuess(name, 0)}
                  isLoading={isLoading}
                  remainingGuesses={gameState.remaining_guesses}
                  placeholder={t('powiatyPage.guessPlaceholder', { count: gameState.remaining_guesses })}
                />
              </div>
            </div>
          )}
          {isGuest && <GuestProgress gameType="powiaty" today={today} />}
        </section>

        <aside className="min-w-0 rounded-sm border border-white/10 bg-obsidian-900" aria-label={'Deduction notebook'}>
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
            <History mode="powiatdle" questions={questions} isGameOver={gameState.is_game_over} />
          </section>
        </aside>
      </div>
    </div>
  );
}
