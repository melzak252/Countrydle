import { useEffect, useState, useRef } from 'react';
import { usePowiatyGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import GuessInput from '../components/GuessInput';
import GameActionComposer from '../components/GameActionComposer';
import BackToMapButton from '../components/BackToMapButton';
import PowiatyMap from '../components/PowiatyMap';
import GameInstructions from '../components/GameInstructions';
import QuestionChat from '../components/QuestionChat';
import {
  Loader2,
  ChevronUp,
  X,
  Check,
  Trophy,
  Compass,
  MessageSquare,
  Target,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import GameResultDashboard from '../components/result-dashboard/GameResultDashboard';
import { buildQADetailTabs } from '../components/result-dashboard/qaDetails';
import { useIsMobile } from '../hooks/useMediaQuery';

function getDistanceColor(distanceKm: number): string {
  if (distanceKm <= 50) {
    return 'border-app-accent/30 bg-app-accent/10 text-app-accent';
  }
  if (distanceKm <= 150) {
    return 'border-amber-700/25 bg-amber-500/10 text-amber-800';
  }
  return 'border-app-border/15 bg-app-surface-muted text-app-text-secondary';
}

export default function PowiatyGamePage() {
  const {
    gameState,
    questions,
    guesses,
    notices,
    addNotice,
    entities: powiaty,
    correctEntity: correctPowiat,
    isLoading,
    pendingQuestion,
    fetchGameState,
    fetchEntities: fetchPowiaty,
    askQuestion,
    makeGuess,
    syncGuestData,
    dailyDate,
  } = usePowiatyGameStore();
  const { t } = useTranslation();
// today removed

  // HUD & Chat state
  const isMobile = useIsMobile();
  const [userSelectedTab, setUserSelectedTab] = useState<'question' | 'guess' | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const activeInputTab: 'question' | 'guess' = userSelectedTab ?? (
    gameState && gameState.remaining_questions <= 0 && gameState.remaining_guesses > 0
      ? 'guess'
      : 'question'
  );
  const activeChatTab = activeInputTab === 'question' ? 'questions' : 'guesses';
  const [isResultDismissed, setIsResultDismissed] = useState(false);

  useEffect(() => {
    if (!isMobile) {
      setIsChatOpen(true);
    }
  }, [isMobile]);
  useEffect(() => {
    fetchGameState();
    fetchPowiaty();
    window.addEventListener('auth-login', syncGuestData);
    return () => window.removeEventListener('auth-login', syncGuestData);
  }, [fetchGameState, fetchPowiaty, syncGuestData]);

  const questionsContainerRef = useRef<HTMLDivElement>(null);
  const guessesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isChatOpen || activeChatTab !== 'questions' || !questionsContainerRef.current) return;
    questionsContainerRef.current.scrollTop = questionsContainerRef.current.scrollHeight;
  }, [questions.length, notices.length, activeChatTab, isChatOpen, pendingQuestion]);

  useEffect(() => {
    if (!isChatOpen || activeChatTab !== 'guesses' || !guessesContainerRef.current) return;
    guessesContainerRef.current.scrollTop = guessesContainerRef.current.scrollHeight;
  }, [guesses.length, activeChatTab, isChatOpen]);

  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-app-accent">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-mono text-app-text-secondary">Loading Powiatdle puzzle…</span>
      </div>
    );
  }

  if (!gameState) return null;

  const sortedQuestions = [...questions].sort((a, b) => a.id - b.id);
  const isGameOver = Boolean(gameState.is_game_over);
  const showResultModal = isGameOver && !isResultDismissed;

  const handleAsk = async (q: string) => {
    setUserSelectedTab('question');
    setIsChatOpen(true);
    return await askQuestion(q);
  };

  const handleGuess = async (name: string, id: number) => {
    setIsChatOpen(true);
    const accepted = await makeGuess(name, id);
    setUserSelectedTab(accepted === false ? 'question' : 'guess');
    return accepted;
  };

  const handleGuessWarning = (input: string) => {
    const isQuestion = input.trim().endsWith('?') || /^(?:is\s|czy\s|does\s|do\s|what\s|which\s|are\s|can\s|has\s|have\s)/i.test(input.trim());
    if (isQuestion) {
      addNotice({
        action: 'guess',
        input,
        title: 'Question entered in guess box',
        reason: 'You submitted a question while the "Guess" tab was active.',
        nextStep: 'Switched back to the "Question" tab for you.',
      });
    } else {
      addNotice({
        action: 'guess',
        input,
        title: 'Already guessed',
        reason: 'This location is already in your guess history. It was not submitted again.',
        nextStep: 'Switch to the Guesses tab and choose a different location.',
      });
    }
    setUserSelectedTab('question');
    setIsChatOpen(true);
  };

  const totalQuestions = 15;
  const totalGuesses = 3;

  return (
    <div className="relative flex-1 min-h-0 h-full w-full overflow-hidden bg-app-canvas font-sans select-none">
      <div className="game-map-layer absolute inset-0 z-0 w-full">
        <PowiatyMap
          correctPowiatName={isGameOver ? correctPowiat?.nazwa : undefined}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </div>

      {/* 2. Top Status HUD Bar */}
      <div className="game-status-bar pointer-events-none absolute inset-x-0 top-0 z-[1200] w-full md:inset-x-auto md:left-1/2 md:top-3 md:z-[1000] md:w-auto md:-translate-x-1/2 md:px-2 md:max-w-full">
        <div className="pointer-events-auto flex h-11 w-full items-stretch border-b border-app-border/15 bg-app-surface/95 text-xs font-mono text-app-text md:h-8 md:w-auto md:divide-x md:divide-app-border/15 md:rounded-sm md:border md:border-app-border/20 md:bg-app-surface/95 md:shadow-sm md:backdrop-blur-md">
          <div className="hidden md:flex items-center gap-2 px-3 text-xs text-app-text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-app-accent shrink-0" />
            <span>Powiaty</span>
            <span className="rounded-sm bg-amber-500/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              In Dev
            </span>
            <span className="font-semibold text-app-text hidden sm:inline">{dailyDate}</span>
          </div>
          <div className="flex md:hidden items-center px-2">
            <span className="rounded-sm bg-amber-500/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              Beta
            </span>
          </div>

          <div className="flex flex-1 items-center justify-center gap-1.5 px-2 md:flex-none md:px-3">
            <span className="text-xs text-app-text-muted">Q:</span>
            <span className="font-semibold text-app-text">
              {gameState.remaining_questions}
              <span className="text-[10px] text-app-text-muted">/{totalQuestions}</span>
            </span>
          </div>

          <div className="flex flex-1 items-center justify-center gap-1.5 px-2 md:flex-none md:px-3">
            <span className="text-xs text-app-text-muted">G:</span>
            <span className="font-semibold text-app-accent">
              {gameState.remaining_guesses}
              <span className="text-[10px] text-app-text-muted">/{totalGuesses}</span>
            </span>
          </div>

          <GameInstructions
            gameName={t('powiatyPage.title')}
            scoring={{ maxPoints: 3800, details: t('powiatyPage.scoringDetails', { returnObjects: true }) as string[] }}
            compact={true}
            triggerClassName="max-md:min-h-11 max-md:min-w-11 flex items-center gap-1.5 px-2.5 text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted transition-colors text-xs cursor-pointer whitespace-nowrap"
          />

          {isGameOver && (
            <button
              type="button"
              onClick={() => setIsResultDismissed(false)}
              className="max-md:min-h-11 flex items-center gap-1.5 bg-app-accent/10 px-3 text-xs font-semibold text-app-accent hover:bg-app-accent/20 transition-colors cursor-pointer"
            >
              <Trophy size={13} />
              <span>{'Result'}</span>
            </button>
          )}
        </div>
      </div>

      {/* 3. Unified Deduction Notebook & Chat */}

      <div className={`pointer-events-none ${
        isChatOpen
          ? 'game-notebook-layer absolute inset-0 z-[1100] md:absolute md:inset-0 md:z-[1000]'
          : 'absolute inset-x-0 bottom-0 z-[995] w-full bg-app-surface pb-[max(calc(env(safe-area-inset-bottom)+0.25rem),0.75rem)] md:absolute md:inset-x-auto md:left-4 md:bottom-4 md:z-[1000] md:w-fit md:max-w-[calc(100vw-2rem)] md:bg-transparent md:pb-0'
      }`}>
        {!isChatOpen ? (
          <div className="pointer-events-auto flex w-full gap-2 border-t border-app-border/15 bg-app-surface-raised p-1 shadow-sm md:block md:w-auto md:border md:border-app-border/20 md:bg-app-surface-raised md:p-0">
            <button type="button" onClick={() => { setUserSelectedTab('question'); setIsChatOpen(true); }} className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-sm border border-app-border/20 bg-app-surface px-3 font-mono text-xs text-app-text hover:bg-app-surface-muted md:hidden">
              {'Ask'} <span className="text-app-text-muted">{gameState.remaining_questions}/{totalQuestions}</span>
            </button>
            <button type="button" onClick={() => { setUserSelectedTab('guess'); setIsChatOpen(true); }} className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-sm border border-app-border/20 bg-app-surface px-3 font-mono text-xs text-app-text hover:bg-app-surface-muted md:hidden">
              {'Guess'} <span className="text-app-accent">{gameState.remaining_guesses}/{totalGuesses}</span>
            </button>
            <button type="button" onClick={() => setIsChatOpen(true)} className="hidden min-h-11 items-center gap-2 rounded-sm border border-app-border/20 bg-app-surface-raised px-3 py-1.5 font-mono text-xs text-app-text md:flex" aria-label={'Open notebook'}>
              <MessageSquare size={13} className="text-app-accent" />
              <span>{'Notebook'}</span>
              <span className="text-app-text font-semibold">Q: {questions.length}/{totalQuestions}</span>
              <span className="text-app-text-muted">·</span>
              <span className="text-app-accent font-semibold">G: {guesses.length}/{totalGuesses}</span>
              <ChevronUp size={13} className="text-app-text-muted ml-0.5" />
            </button>
          </div>
        ) : (
          <div onWheel={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()} className="pointer-events-auto absolute inset-0 flex h-full flex-col overflow-hidden bg-app-surface-raised shadow-sm md:inset-x-auto md:inset-y-auto md:left-4 md:bottom-4 md:h-[68vh] md:max-h-[72vh] md:w-[28rem] md:rounded-sm md:border md:border-app-border/20 md:bg-app-surface md:pb-0">

            {/* Header */}
            <div className="flex items-center justify-between border-b border-app-border/15 bg-app-surface-raised px-2 py-1 shrink-0 md:px-4 md:py-3 md:bg-app-surface">
              <div role="group" aria-label={'Choose question or guess'} className="flex items-center gap-1">
                <button
                  type="button"
                  aria-pressed={activeChatTab === 'questions'}
                  onClick={() => setUserSelectedTab('question')}
                  className={`flex min-h-11 items-center gap-1 rounded-sm px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'questions'
                      ? 'bg-app-surface-muted font-semibold text-app-text'
                      : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                  }`}
                >
                  <MessageSquare size={12} className={`hidden md:block ${activeChatTab === 'questions' ? 'text-app-accent' : ''}`} />
                  <span className="md:hidden">{'Ask'}</span>
                  <span className="hidden md:inline">{'Questions'}</span>
                  <span className="font-mono text-[10px] text-app-text-muted">({questions.length}/{totalQuestions})</span>
                </button>

                <button
                  type="button"
                  aria-pressed={activeChatTab === 'guesses'}
                  onClick={() => setUserSelectedTab('guess')}
                  className={`flex min-h-11 items-center gap-1 rounded-sm px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'guesses'
                      ? 'bg-app-surface-muted font-semibold text-app-text'
                      : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                  }`}
                >
                  <Target size={12} className={`hidden md:block ${activeChatTab === 'guesses' ? 'text-app-accent' : ''}`} />
                  <span className="md:hidden">{'Guess'}</span>
                  <span className="hidden md:inline">{'Guesses'}</span>
                  <span className="font-mono text-[10px] text-app-text-muted">({guesses.length}/{totalGuesses})</span>
                </button>
              </div>

              <BackToMapButton onClick={() => setIsChatOpen(false)} />
            </div>

            {/* Tab 1: Questions Stream */}
            {activeChatTab === 'questions' && (
              <div ref={questionsContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 custom-scrollbar overscroll-contain">
                <QuestionChat questions={sortedQuestions} notices={notices} mode="powiatdle" isGameOver={isGameOver} isLoading={isLoading} pendingQuestion={pendingQuestion} />
              </div>
            )}

            {/* Tab 2: Guesses Stream */}
            {activeChatTab === 'guesses' && (
              <div ref={guessesContainerRef} className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 text-xs custom-scrollbar overscroll-contain">
                {guesses.length === 0 ? (
                  <div className="py-7 text-center text-app-text-secondary space-y-1 border border-dashed border-app-border/25 rounded-sm bg-app-surface-muted p-4">
                    <Compass size={20} className="mx-auto text-app-text-muted" />
                    <p className="font-mono text-xs text-app-text">No attempts logged</p>
                    <p className="text-xs text-app-text-secondary">
                      Submit county guesses when ready (max {totalGuesses} tries).
                    </p>
                  </div>
                ) : (
                  guesses.map((g, index) => {
                    const hasDistance = g.distance_km !== undefined && g.distance_km !== null && !g.answer;
                    const hasBearing = Boolean(g.bearing_direction && !g.answer);

                    return (
                      <div key={g.id} className="space-y-1 border-b border-app-border/10 pb-2 last:border-0 last:pb-0">
                        <div className="flex items-center justify-between font-mono text-xs text-app-text-muted">
                          <span>#{String(index + 1).padStart(2, '0')} · Location Attempt</span>
                        </div>
                        <div
                          className={`flex items-center justify-between gap-3 border-l-2 bg-app-surface-muted px-3 py-2 rounded-r-sm transition-colors ${
                            g.answer
                              ? 'border-l-app-accent bg-app-accent/10'
                              : 'border-l-rose-500/60'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {g.answer ? (
                              <Check size={14} className="text-app-accent shrink-0" />
                            ) : (
                              <X size={14} className="text-rose-600 shrink-0" />
                            )}
                            <span className="text-xs font-medium text-app-text truncate">{g.guess}</span>
                          </div>

                          {g.answer ? (
                            <span className="font-mono text-xs font-semibold text-app-accent">
                              Correct
                            </span>
                          ) : hasDistance ? (
                            <div className="flex items-center gap-1.5 font-mono text-[11px] shrink-0">
                              <span className={`rounded-sm border px-2 py-0.5 font-semibold ${getDistanceColor(g.distance_km!)}`}>
                                {g.distance_km!.toLocaleString('en-US')} km
                              </span>
                              {hasBearing && (
                                <span
                                  className="inline-flex items-center gap-0.5 rounded-sm border border-app-accent/30 bg-app-accent/10 px-1.5 py-0.5 text-app-accent font-semibold"
                                  title={`${g.bearing_direction} (${g.bearing_degrees}°)`}
                                >
                                  <span>{g.bearing_arrow || '↗'}</span>
                                  <span>{g.bearing_direction}</span>
                                </span>
                              )}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
            {!isGameOver ? (
              <GameActionComposer
                activeAction={activeInputTab}
                onActionChange={setUserSelectedTab}
                showActionTabs={false}
              >
                {activeInputTab === 'question' ? (
                  <QuestionInput
                    onAsk={handleAsk}
                    isLoading={isLoading}
                    remainingQuestions={gameState.remaining_questions}
                    placeholder={t('powiatyPage.askPlaceholder', { count: gameState.remaining_questions })}
                    mode="powiaty"
                  />
                ) : (
                  <GuessInput
                    dropup={true}
                    countries={powiaty}
                    alreadyGuessedNames={guesses.map((g) => g.guess)}
                    alreadyGuessedIds={guesses.map((g) => g.powiat_id).filter(Boolean)}
                    onGuess={async (id, name) => handleGuess(name, Number(id))}
                    onWarning={handleGuessWarning}
                    onUnknownGuess={async (name) => handleGuess(name, 0)}
                    isLoading={isLoading}
                    remainingGuesses={gameState.remaining_guesses}
                    placeholder={t('powiatyPage.guessPlaceholder', { count: gameState.remaining_guesses })}
                  />
                )}
              </GameActionComposer>
            ) : (
              <div className="flex items-center justify-between gap-3 border-t border-app-border/15 bg-app-surface-raised px-4 py-3">
                <div className="flex items-center gap-3">
                  <Trophy size={16} className="text-amber-700" />
                  <span className="font-mono text-xs font-semibold text-app-text">
                    {gameState.won ? 'Fieldwork solved' : 'Investigation concluded'}
                  </span>
                  <span className="font-mono text-xs text-app-accent">{gameState.points} pts</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsResultDismissed(false)}
                  className="rounded-sm bg-app-accent px-3 py-1.5 font-mono text-xs font-semibold text-white hover:bg-app-accent-hover transition-colors shadow-sm cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
                >
                  View Result Card
                </button>
              </div>
            )}
          </div>
        )}
      </div>


      {/* 5. Game Over Dashboard Overlay */}
      {isGameOver && showResultModal && (
        <GameResultDashboard
          mode="powiatdle"
          modeKind="qa"
          gameName="Powiatdle"
          gamePath="/powiaty"
          date={dailyDate}
          won={gameState.won}
          points={gameState.points}
          questionsAsked={gameState.questions_asked}
          maxQuestions={totalQuestions}
          guessesMade={gameState.guesses_made}
          maxGuesses={totalGuesses}
          targetLabel="The Mystery County"
          targetName={correctPowiat?.nazwa || guesses.find((g) => g.answer)?.guess}
          subtitle={
            gameState.won
              ? 'Outstanding deduction! You uncovered the county.'
              : 'Better luck tomorrow! Study the clues and try again.'
          }
          detailTabs={buildQADetailTabs({
            reportMode: 'powiatdle',
            questions: sortedQuestions,
            guesses,
            notices,
          })}
          detailsTitle="Questions & Guesses"
          onClose={() => setIsResultDismissed(true)}
          closeLabel="Close and View Map"
        />
      )}
    </div>
  );
}
