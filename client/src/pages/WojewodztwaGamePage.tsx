import { useEffect, useState } from 'react';
import { useWojewodztwaGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import History from '../components/History';
import GuessInput from '../components/GuessInput';
import GuessHistory from '../components/GuessHistory';
import WojewodztwaMap from '../components/WojewodztwaMap';
import GameInstructions from '../components/GameInstructions';
import { Loader2, Trophy } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import GuestProgress from '../components/GuestProgress';
import { useDailyDate } from '../hooks/useDailyClock';

export default function WojewodztwaGamePage() {
  const {
    gameState,
    questions,
    guesses,
    entities: wojewodztwa,
    correctEntity: correctWojewodztwo,
    isLoading,
    fetchGameState,
    fetchEntities: fetchWojewodztwa,
    askQuestion,
    makeGuess,
    syncGuestData,
    isGuest,
    dailyDate,
  } = useWojewodztwaGameStore();
  const { t, i18n } = useTranslation();
  const today = useDailyDate();
  const [showResultModal, setShowResultModal] = useState(true);

  useEffect(() => {
    if (gameState?.is_game_over) {
      setShowResultModal(true);
    }
  }, [gameState?.is_game_over]);

  useEffect(() => {
    fetchGameState();
    fetchWojewodztwa();
    const handleLogin = () => { syncGuestData(); };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, [fetchGameState, fetchWojewodztwa, syncGuestData]);

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
          <h1 className="text-xl font-semibold tracking-tight text-sand-100 sm:text-2xl">{t('wojewodztwaPage.title')}</h1>
          {isGuest && <p className="mt-1 text-xs text-zinc-400">Guest · no account needed</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <dl className="flex divide-x divide-white/10 rounded-sm border border-white/10 bg-obsidian-900">
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.questionsLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-sand-100">{gameState.remaining_questions}<span className="text-xs text-zinc-500"> / 5</span></dd>
            </div>
            <div className="px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-zinc-400">{t('gamePage.guessesLeft')}</dt>
              <dd className="mt-0.5 font-mono text-lg text-emerald-400">{gameState.remaining_guesses}<span className="text-xs text-zinc-500"> / 2</span></dd>
            </div>
          </dl>
          <GameInstructions
            gameName={t('wojewodztwaPage.title')}
            examples={t('wojewodztwaPage.examples', { returnObjects: true }) as string[]}
            scoring={{ maxPoints: 3300, details: t('wojewodztwaPage.scoringDetails', { returnObjects: true }) as string[] }}
          />
          {gameState.is_game_over && (
            <button
              type="button"
              onClick={() => setShowResultModal(true)}
              className="inline-flex items-center gap-1.5 rounded-sm border border-emerald-400/40 bg-emerald-950/40 px-3 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-900/50 transition-colors cursor-pointer"
            >
              <Trophy size={14} />
              <span>{i18n.language.startsWith('pl') ? 'Wyniki' : 'Results'}</span>
            </button>
          )}
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.48fr)]">
        <section className="min-w-0 space-y-5" aria-label={'Map and deduction'}>
          <div className="overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">
              <span>Atlas / Województwodle</span>
              <span className="text-emerald-400">{gameState.is_game_over ? ('Result') : ('Search area')}</span>
            </div>
            <div className="relative h-[310px] sm:h-[420px] lg:h-[460px]">
              <WojewodztwaMap correctWojewodztwoName={gameState.is_game_over ? correctWojewodztwo?.nazwa : undefined} className="h-full" />
            </div>
          </div>

          {gameState.is_game_over ? (
            <div className="rounded-sm border border-emerald-500/30 bg-obsidian-900 p-4 sm:p-5 flex items-center justify-between gap-4">
              <div>
                <span className="font-mono text-xs uppercase tracking-wider text-emerald-400">
                  {gameState.won ? (i18n.language.startsWith('pl') ? 'Wygrana!' : 'Solved!') : (i18n.language.startsWith('pl') ? 'Koniec gry' : 'Game Over')}
                </span>
                <h3 className="text-lg font-semibold text-sand-100">
                  {correctWojewodztwo?.nazwa || guesses.find(g => g.answer)?.guess || (i18n.language.startsWith('pl') ? 'Dzisiejsza zagadka' : "Today's Puzzle")}
                </h3>
                {gameState.won && gameState.points && gameState.points > 0 ? (
                  <p className="font-mono text-xs text-emerald-400">+{gameState.points.toLocaleString()} pts</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => setShowResultModal(true)}
                className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 cursor-pointer"
              >
                <Trophy size={16} aria-hidden="true" />
                <span>{i18n.language.startsWith('pl') ? 'Pokaż wyniki' : 'View Results'}</span>
              </button>
            </div>
          ) : (
            <div className="space-y-5 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
              <div>
                <h2 className="mb-2 text-sm font-medium text-sand-100">{'Ask a yes-or-no question'}</h2>
                <QuestionInput
                  onAsk={askQuestion}
                  isLoading={isLoading}
                  remainingQuestions={gameState.remaining_questions}
                  placeholder={t('wojewodztwaPage.askPlaceholder', { count: gameState.remaining_questions })}
                />
              </div>
              <div className="border-t border-white/10 pt-4">
                <h2 className="mb-2 text-sm font-medium text-sand-100">{'Name the location'}</h2>
                <GuessInput
                  countries={wojewodztwa}
                  onGuess={async (id, name) => makeGuess(name, id)}
                  onUnknownGuess={async name => makeGuess(name, 0)}
                  isLoading={isLoading}
                  remainingGuesses={gameState.remaining_guesses}
                  placeholder={t('wojewodztwaPage.guessPlaceholder', { count: gameState.remaining_guesses })}
                />
              </div>
            </div>
          )}
          {isGuest && <GuestProgress gameType="wojewodztwa" today={today} />}
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
            <History mode="wojewodztwodle" questions={questions} isGameOver={gameState.is_game_over} />
          </section>
        </aside>
      </div>

      {/* Centered Results Modal */}
      {gameState.is_game_over && showResultModal && (
        <div
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/80 p-3 sm:p-4 backdrop-blur-sm overflow-y-auto"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowResultModal(false);
          }}
        >
          <div className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-sm shadow-2xl my-auto">
            <ShareResultCard
              gameName="Województwodle"
              gamePath="/wojewodztwa"
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={5}
              guessesMade={gameState.guesses_made}
              maxGuesses={2}
              targetName={correctWojewodztwo?.nazwa || guesses.find(g => g.answer)?.guess}
              isGuest={isGuest}
              discovery={questions.find(q => q.valid && q.explanation)?.explanation}
              onClose={() => setShowResultModal(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
