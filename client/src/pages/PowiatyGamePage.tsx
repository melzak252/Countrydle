import { useEffect, useState, useRef } from 'react';
import { usePowiatyGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import GuessInput from '../components/GuessInput';
import PowiatyMap from '../components/PowiatyMap';
import GameInstructions from '../components/GameInstructions';
import AnswerReportForm from '../components/AnswerReportForm';
import {
  Loader2,
  ChevronDown,
  ChevronUp,
  X,
  Check,
  AlertTriangle,
  Trophy,
  Compass,
  Eye,
  MessageSquare,
  Target,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import GuestProgress from '../components/GuestProgress';
import { useDailyDate } from '../hooks/useDailyClock';

function getDistanceColor(distanceKm: number): string {
  if (distanceKm <= 50) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  }
  if (distanceKm <= 150) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  }
  return 'border-white/10 bg-white/5 text-zinc-300';
}

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

  // HUD & Chat state
  const [userSelectedTab, setUserSelectedTab] = useState<'question' | 'guess' | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [activeChatTab, setActiveChatTab] = useState<'questions' | 'guesses'>('questions');
  const [isResultDismissed, setIsResultDismissed] = useState(false);

  // Auto-scroll refs
  const questionsBottomRef = useRef<HTMLDivElement>(null);
  const guessesBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchGameState();
    fetchPowiaty();
    window.addEventListener('auth-login', syncGuestData);
    return () => window.removeEventListener('auth-login', syncGuestData);
  }, [fetchGameState, fetchPowiaty, syncGuestData]);

  // Auto-scroll when new question arrives
  useEffect(() => {
    if (isChatOpen && activeChatTab === 'questions') {
      const timer = setTimeout(() => {
        questionsBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [questions.length, isChatOpen, activeChatTab]);

  // Auto-scroll when new guess arrives
  useEffect(() => {
    if (isChatOpen && activeChatTab === 'guesses') {
      const timer = setTimeout(() => {
        guessesBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [guesses.length, isChatOpen, activeChatTab]);

  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-mono text-zinc-400">Loading Powiatdle puzzle…</span>
      </div>
    );
  }

  if (!gameState) return null;

  const sortedQuestions = [...questions].sort((a, b) => a.id - b.id);
  const isGameOver = Boolean(gameState.is_game_over);
  const showResultModal = isGameOver && !isResultDismissed;
  const activeInputTab: 'question' | 'guess' = userSelectedTab ?? (
    (gameState.remaining_questions <= 0 && gameState.remaining_guesses > 0)
      ? 'guess'
      : 'question'
  );

  const handleAsk = async (q: string) => {
    setActiveChatTab('questions');
    setIsChatOpen(true);
    return await askQuestion(q);
  };

  const handleGuess = async (name: string, id: number) => {
    setActiveChatTab('guesses');
    setIsChatOpen(true);
    return await makeGuess(name, id);
  };

  const totalQuestions = 15;
  const totalGuesses = 3;

  return (
    <div className="relative h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-obsidian-950 font-sans select-none">
      {/* 1. Full-Canvas Map */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <PowiatyMap
          correctPowiatName={isGameOver ? correctPowiat?.nazwa : undefined}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </div>

      {/* 2. Top Status HUD Bar */}
      <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 px-2">
        <div className="pointer-events-auto flex h-8 items-stretch divide-x divide-white/10 rounded-sm border border-white/15 bg-obsidian-900/85 shadow-lg backdrop-blur-md overflow-hidden text-xs font-mono">
          <div className="flex items-center gap-2 px-3 text-[10px] uppercase tracking-[0.16em] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span>Powiaty</span>
            <span className="font-semibold text-sand-100">{dailyDate}</span>
          </div>

          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">Q:</span>
            <span className="font-semibold text-sand-100">
              {gameState.remaining_questions}
              <span className="text-[10px] text-zinc-500">/{totalQuestions}</span>
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">G:</span>
            <span className="font-semibold text-emerald-400">
              {gameState.remaining_guesses}
              <span className="text-[10px] text-zinc-500">/{totalGuesses}</span>
            </span>
          </div>

          <GameInstructions
            gameName={t('powiatyPage.title')}
            examples={t('powiatyPage.examples', { returnObjects: true }) as string[]}
            scoring={{ maxPoints: 3800, details: t('powiatyPage.scoringDetails', { returnObjects: true }) as string[] }}
            compact={true}
            triggerClassName="flex items-center gap-1.5 px-2.5 text-zinc-400 hover:text-sand-100 hover:bg-white/5 transition-colors text-[10px] uppercase tracking-[0.16em] cursor-pointer whitespace-nowrap"
          />

          {isGameOver && (
            <button
              type="button"
              onClick={() => setIsResultDismissed(false)}
              className="flex items-center gap-1.5 bg-emerald-500/20 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-300 hover:bg-emerald-500/30 transition-colors cursor-pointer"
            >
              <Trophy size={13} />
              <span>Result</span>
            </button>
          )}
        </div>
      </div>

      {/* 3. Unified Deduction Notebook (Left Side on Map) */}
      <div className="pointer-events-none absolute left-11 sm:left-12 top-11 sm:top-12 z-[990] w-84 sm:w-96 max-w-[calc(100vw-4rem)]">
        {!isChatOpen ? (
          /* Collapsed Button */
          <button
            type="button"
            onClick={() => setIsChatOpen(true)}
            className="pointer-events-auto flex items-center gap-2 rounded-sm border border-white/15 bg-obsidian-900/80 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100 shadow-xl backdrop-blur-md hover:bg-obsidian-850 transition-colors cursor-pointer"
            aria-label="Expand Deduction Chat"
          >
            <MessageSquare size={13} className="text-emerald-400" />
            <span>Chat</span>
            <span className="text-zinc-500">·</span>
            <span className="text-sand-100 font-semibold">Q: {questions.length}/{totalQuestions}</span>
            <span className="text-zinc-500">·</span>
            <span className="text-emerald-400 font-semibold">G: {guesses.length}/{totalGuesses}</span>
            <ChevronDown size={13} className="text-zinc-400 ml-0.5" />
          </button>
        ) : (
          /* Expanded Translucent Window */
          <div className="pointer-events-auto flex max-h-[50vh] sm:max-h-[56vh] flex-col overflow-hidden rounded-sm border border-white/15 bg-obsidian-900/80 shadow-2xl backdrop-blur-md transition-all">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-obsidian-950/70 px-3 py-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveChatTab('questions')}
                  className={`flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer ${
                    activeChatTab === 'questions'
                      ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <MessageSquare size={12} className={activeChatTab === 'questions' ? 'text-emerald-400' : ''} />
                  <span>Inquiries</span>
                  <span className="font-mono text-[10px] text-zinc-500">({questions.length}/{totalQuestions})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChatTab('guesses')}
                  className={`flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer ${
                    activeChatTab === 'guesses'
                      ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <Target size={12} className={activeChatTab === 'guesses' ? 'text-emerald-400' : ''} />
                  <span>Guesses</span>
                  <span className="font-mono text-[10px] text-zinc-500">({guesses.length}/{totalGuesses})</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                className="rounded-sm p-1 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
                title="Minimize chat"
                aria-label="Minimize chat"
              >
                <ChevronUp size={14} />
              </button>
            </div>

            {/* Tab 1: Questions Stream */}
            {activeChatTab === 'questions' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs scroll-smooth custom-scrollbar">
                {sortedQuestions.length === 0 ? (
                  <div className="py-7 text-center text-zinc-400 space-y-2 border border-dashed border-white/10 rounded-sm p-4">
                    <MessageSquare size={20} className="mx-auto text-zinc-600" />
                    <p className="font-mono text-[11px] uppercase tracking-wider text-sand-200">Dialogue channel ready</p>
                    <p className="text-xs leading-relaxed text-zinc-500 max-w-[240px] mx-auto">
                      Submit a yes-or-no inquiry below about the mystery Polish county (powiat).
                    </p>
                  </div>
                ) : (
                  sortedQuestions.map((q, index) => {
                    const showExplanation = Boolean(q.explanation) && (!q.valid || isGameOver);
                    const isYes = q.valid && q.answer === true;
                    const isNo = q.valid && q.answer === false;
                    const isInvalid = !q.valid;
                    const answerLabel = isInvalid ? 'Invalid question' : isYes ? 'Yes' : isNo ? 'No' : 'Unknown';
                    const answerColor = isInvalid
                      ? 'border-amber-300/15 bg-amber-300/[0.08] text-amber-200'
                      : isYes
                      ? 'border-emerald-300/15 bg-emerald-300/[0.10] text-emerald-300'
                      : isNo
                      ? 'border-rose-300/15 bg-rose-300/[0.10] text-rose-300'
                      : 'border-white/10 bg-white/5 text-zinc-300';

                    return (
                      <div key={q.id} className="space-y-1.5 border-b border-white/5 pb-2.5 last:border-0 last:pb-0">
                        {/* Player Inquiry */}
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
                              #{String(index + 1).padStart(2, '0')} · You
                            </span>
                          </div>
                          <div className="rounded-sm border border-white/10 bg-white/[0.05] px-3 py-2 text-xs font-medium text-sand-100 leading-relaxed">
                            {q.original_question}
                          </div>
                        </div>

                        {/* Dispatch Response */}
                        <div className="pt-0.5">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-emerald-400 font-semibold">
                              Atlas Dispatch
                            </span>
                          </div>

                          <div className={`rounded-sm border px-3 py-1.5 flex items-center justify-between gap-2 ${answerColor}`}>
                            <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-bold uppercase tracking-wider">
                              {isYes && <Check size={14} strokeWidth={2.5} />}
                              {isNo && <X size={14} strokeWidth={2.5} />}
                              {isInvalid && <AlertTriangle size={14} />}
                              <span>{answerLabel}</span>
                            </span>

                            {showExplanation && (
                              <span className="font-mono text-[10px] text-zinc-400">
                                {isInvalid ? 'details' : 'clue'}
                              </span>
                            )}
                          </div>

                          {showExplanation && (
                            <div className="mt-1 rounded-sm border border-white/10 bg-black/40 px-3 py-2 text-[11px] leading-relaxed text-zinc-300">
                              {isInvalid && (
                                <p className="font-mono text-[10px] uppercase tracking-wider text-amber-300 mb-0.5 font-medium">
                                  {t('history.invalidReason')}
                                </p>
                              )}
                              <p>{q.explanation}</p>
                            </div>
                          )}

                          {isGameOver && q.id > 0 && (
                            <div className="mt-1.5 border-t border-white/5 pt-1.5">
                              <AnswerReportForm mode="powiatdle" questionId={q.id} reportToken={q.report_token} />
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={questionsBottomRef} />
              </div>
            )}

            {/* Tab 2: Guesses Stream */}
            {activeChatTab === 'guesses' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2 text-xs scroll-smooth custom-scrollbar">
                {guesses.length === 0 ? (
                  <div className="py-7 text-center text-zinc-400 space-y-1 border border-dashed border-white/10 rounded-sm p-4">
                    <Compass size={20} className="mx-auto text-zinc-600" />
                    <p className="font-mono text-[11px] uppercase tracking-wider text-sand-200">No attempts logged</p>
                    <p className="text-xs text-zinc-500">
                      Submit county guesses when ready (max {totalGuesses} tries).
                    </p>
                  </div>
                ) : (
                  guesses.map((g, index) => {
                    const hasDistance = g.distance_km !== undefined && g.distance_km !== null && !g.answer;
                    const hasBearing = Boolean(g.bearing_direction && !g.answer);

                    return (
                      <div key={g.id} className="space-y-1 border-b border-white/5 pb-2 last:border-0 last:pb-0">
                        <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
                          <span>#{String(index + 1).padStart(2, '0')} · Location Attempt</span>
                        </div>
                        <div
                          className={`flex items-center justify-between gap-3 border-l-2 bg-obsidian-950/70 px-3 py-2 rounded-r-sm transition-colors ${
                            g.answer
                              ? 'border-l-emerald-400 bg-emerald-500/10'
                              : 'border-l-rose-500/60'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {g.answer ? (
                              <Check size={14} className="text-emerald-400 shrink-0" />
                            ) : (
                              <X size={14} className="text-rose-400 shrink-0" />
                            )}
                            <span className="text-xs font-medium text-sand-100 truncate">{g.guess}</span>
                          </div>

                          {g.answer ? (
                            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                              Correct
                            </span>
                          ) : hasDistance ? (
                            <div className="flex items-center gap-1.5 font-mono text-[11px] shrink-0">
                              <span className={`rounded-sm border px-2 py-0.5 font-semibold ${getDistanceColor(g.distance_km!)}`}>
                                {g.distance_km!.toLocaleString()} km
                              </span>
                              {hasBearing && (
                                <span
                                  className="inline-flex items-center gap-0.5 rounded-sm border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-400 font-semibold"
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
                <div ref={guessesBottomRef} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. Floating Action Inputs Dock on the Map (Bottom Center) */}
      <div className="pointer-events-none absolute bottom-5 left-1/2 z-[1000] w-full max-w-xl -translate-x-1/2 px-4">
        <div className="pointer-events-auto flex flex-col gap-2 rounded-sm border border-white/15 bg-obsidian-900/85 p-3 shadow-2xl backdrop-blur-md transition-all">
          {!isGameOver ? (
            <>
              <div className="flex items-center border-b border-white/10 mb-1 pb-1">
                <button
                  type="button"
                  onClick={() => setUserSelectedTab('question')}
                  className={`flex items-center gap-1.5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                    activeInputTab === 'question'
                      ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                      : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
                  }`}
                >
                  <span>Ask a question</span>
                  <span className="font-mono text-[10px] text-zinc-500">({gameState.remaining_questions}/{totalQuestions})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setUserSelectedTab('guess')}
                  className={`flex items-center gap-1.5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                    activeInputTab === 'guess'
                      ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                      : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
                  }`}
                >
                  <span>Name location</span>
                  <span className="font-mono text-[10px] text-zinc-500">({gameState.remaining_guesses}/{totalGuesses})</span>
                </button>
              </div>

              <div className="pt-0.5">
                {activeInputTab === 'question' ? (
                  <QuestionInput
                    onAsk={handleAsk}
                    isLoading={isLoading}
                    remainingQuestions={gameState.remaining_questions}
                    placeholder={t('powiatyPage.askPlaceholder', { count: gameState.remaining_questions })}
                  />
                ) : (
                  <GuessInput
                    dropup={true}
                    countries={powiaty}
                    onGuess={async (id, name) => handleGuess(name, Number(id))}
                    onUnknownGuess={async (name) => handleGuess(name, 0)}
                    isLoading={isLoading}
                    remainingGuesses={gameState.remaining_guesses}
                    placeholder={t('powiatyPage.guessPlaceholder', { count: gameState.remaining_guesses })}
                  />
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between gap-3 px-2 py-1">
              <div className="flex items-center gap-3">
                <Trophy size={16} className="text-amber-400" />
                <span className="font-mono text-xs uppercase tracking-wider font-semibold text-sand-100">
                  {gameState.won ? 'Fieldwork solved' : 'Investigation concluded'}
                </span>
                <span className="font-mono text-xs text-emerald-400">
                  {gameState.points} pts
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsResultDismissed(false)}
                className="rounded-sm bg-emerald-400 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-obsidian-950 hover:bg-emerald-300 transition-colors shadow cursor-pointer"
              >
                View Result Card
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 5. Game Over Modal Overlay */}
      {isGameOver && showResultModal && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setIsResultDismissed(true)}
          className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
        >
          <div
            className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-sm border border-white/20 bg-obsidian-950/95 p-4 sm:p-6 shadow-2xl cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setIsResultDismissed(true)}
              className="absolute right-4 top-4 rounded-sm border border-white/10 bg-white/5 p-1.5 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
              title="Inspect Map"
              aria-label="Close modal and explore map"
            >
              <X size={15} />
            </button>

            <ShareResultCard
              gameName="Powiatdle"
              gamePath="/powiaty"
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={totalQuestions}
              guessesMade={gameState.guesses_made}
              maxGuesses={totalGuesses}
              targetName={correctPowiat?.nazwa || guesses.find((g) => g.answer)?.guess}
              isGuest={isGuest}
              discovery={questions.find((q) => q.valid && q.explanation)?.explanation}
              onClose={() => setIsResultDismissed(true)}
            />

            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={() => setIsResultDismissed(true)}
                className="flex items-center gap-2 rounded-sm border border-white/15 bg-white/5 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-300 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
              >
                <Eye size={13} />
                <span>Explore Map & Revealed County</span>
              </button>
            </div>

            {isGuest && (
              <div className="mt-4 pt-3 border-t border-white/10">
                <GuestProgress gameType="powiaty" today={today} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
