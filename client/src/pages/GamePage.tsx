import { useEffect, useState, useRef } from 'react';
import { useGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import GuessInput from '../components/GuessInput';
import MapBox from '../components/MapBox';
import GameInstructions from '../components/GameInstructions';
import QuestionChat from '../components/QuestionChat';
import {
  Loader2,
  MessageSquare,
  Target,
  ChevronDown,
  ChevronUp,
  X,
  Check,
  Trophy,
  Compass,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import { useIsMobile } from '../hooks/useMediaQuery';

function getDistanceColor(distanceKm: number): string {
  if (distanceKm <= 500) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  }
  if (distanceKm <= 2000) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  }
  return 'border-white/10 bg-white/5 text-zinc-300';
}

export default function GamePage() {
  const {
    gameState,
    questions,
    guesses,
    notices,
    addNotice,
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
  } = useGameStore();
  const { t } = useTranslation();
// today removed
  const [revealedFlag, setRevealedFlag] = useState<string | undefined>();

  // HUD & Chat state
  const isMobile = useIsMobile();
  const [userSelectedTab, setUserSelectedTab] = useState<'question' | 'guess' | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatTab, setActiveChatTab] = useState<'questions' | 'guesses'>('questions');
  const [isResultDismissed, setIsResultDismissed] = useState(false);

  useEffect(() => {
    if (!isMobile) {
      setIsChatOpen(true);
    }
  }, [isMobile]);
  useEffect(() => {
    fetchGameState();
    fetchCountries();
    window.addEventListener('auth-login', syncGuestData);
    return () => window.removeEventListener('auth-login', syncGuestData);
  }, [fetchGameState, fetchCountries, syncGuestData]);

  // Auto-scroll refs
  const questionsContainerRef = useRef<HTMLDivElement>(null);
  const guessesContainerRef = useRef<HTMLDivElement>(null);
  const prevQuestionsCount = useRef(questions.length);
  const prevNoticesCount = useRef(notices.length);
  const prevGuessesCount = useRef(guesses.length);

  // Auto-scroll the question stream when a question or warning arrives
  useEffect(() => {
    const hasNewQuestion = questions.length > prevQuestionsCount.current;
    const hasNewNotice = notices.length > prevNoticesCount.current;
    if (!questionsContainerRef.current) return;
    prevQuestionsCount.current = questions.length;
    prevNoticesCount.current = notices.length;
    if (hasNewQuestion || hasNewNotice) {
      questionsContainerRef.current.scrollTop = questionsContainerRef.current.scrollHeight;
    }
  }, [questions.length, notices.length, activeChatTab, isChatOpen]);

  // Auto-scroll ONLY when a new guess actually arrives
  useEffect(() => {
    if (guesses.length > prevGuessesCount.current) {
      prevGuessesCount.current = guesses.length;
      if (guessesContainerRef.current) {
        guessesContainerRef.current.scrollTop = guessesContainerRef.current.scrollHeight;
      }
    } else {
      prevGuessesCount.current = guesses.length;
    }
  }, [guesses.length]);


  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-mono text-zinc-400">Loading fieldwork puzzle…</span>
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
    setIsChatOpen(true);
    const accepted = await makeGuess(name, id);
    setActiveChatTab(accepted === false ? 'questions' : 'guesses');
    return accepted;
  };

  const handleDuplicateGuess = (input: string) => {
    addNotice({
      action: 'guess',
      input,
      title: 'Already guessed',
      reason: 'This location is already in your guess history. It was not submitted again.',
      nextStep: 'Choose a different location from the suggestions.',
    });
    setActiveChatTab('questions');
    setIsChatOpen(true);
  };

  return (
    <div className="relative h-[calc(100vh-3.5rem)] sm:h-[calc(100vh-5rem)] w-full overflow-hidden bg-obsidian-950 font-sans select-none">
      {/* 1. Full-Canvas Map */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <MapBox
          correctCountryName={isGameOver ? correctCountry?.name : undefined}
          onCountryCode={setRevealedFlag}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </div>

      {/* 2. Top Status HUD Bar */}
      <div className="pointer-events-none absolute left-14 sm:left-1/2 top-2 sm:top-3 z-[1000] -translate-x-0 sm:-translate-x-1/2 px-1 sm:px-2 max-w-[calc(100vw-4.5rem)] sm:max-w-none">
        <div className="pointer-events-auto flex h-7 sm:h-8 items-stretch divide-x divide-white/10 rounded-sm border border-white/15 bg-obsidian-900/85 shadow-lg backdrop-blur-md overflow-hidden text-xs font-mono">
          <div className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 text-[10px] uppercase tracking-[0.16em] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
            <span className="hidden sm:inline">Daily fieldwork</span>
            <span className="font-semibold text-sand-100 hidden sm:inline">{dailyDate}</span>
            <span className="font-semibold text-sand-100 sm:hidden">Daily</span>
          </div>

          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">Q:</span>
            <span className="font-semibold text-sand-100">
              {gameState.remaining_questions}
              <span className="text-[10px] text-zinc-500">/10</span>
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">G:</span>
            <span className="font-semibold text-emerald-400">
              {gameState.remaining_guesses}
              <span className="text-[10px] text-zinc-500">/3</span>
            </span>
          </div>

          <GameInstructions
            gameName={t('gamePage.title')}
            examples={t('gamePage.examples', { returnObjects: true }) as string[]}
            scoring={{ maxPoints: 3300, details: t('gamePage.scoringDetails', { returnObjects: true }) as string[] }}
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

      {/* 3. Unified Deduction Notebook & Chat */}
      {/* Mobile Drawer Backdrop */}
      {isChatOpen && (
        <div
          onClick={() => setIsChatOpen(false)}
          className="fixed inset-0 z-[1090] bg-black/60 backdrop-blur-xs md:hidden"
          aria-hidden="true"
        />
      )}

      <div className={`pointer-events-none ${
        isChatOpen
          ? 'max-md:fixed max-md:inset-x-0 max-md:bottom-0 max-md:z-[1100] max-md:w-full md:absolute md:left-4 md:bottom-4 md:z-[1000] md:w-80 md:sm:w-92 md:max-w-[calc(100vw-2rem)]'
          : 'max-md:fixed max-md:bottom-20 max-md:left-3 max-md:z-[995] md:absolute md:left-4 md:bottom-4 md:z-[1000] md:w-80 md:sm:w-92 md:max-w-[calc(100vw-2rem)]'
      }`}>
        {!isChatOpen ? (
          /* Collapsed Pill Button */
          <button
            type="button"
            onClick={() => setIsChatOpen(true)}
            className="pointer-events-auto flex items-center gap-2 rounded-sm border border-white/15 bg-obsidian-900/90 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100 shadow-xl backdrop-blur-md hover:bg-obsidian-850 transition-colors cursor-pointer"
            aria-label="Expand Deduction Chat"
          >
            <MessageSquare size={13} className="text-emerald-400" />
            <span>Chat</span>
            <span className="text-sand-100 font-semibold">Q: {questions.length}/10</span>
            <span className="text-zinc-500">·</span>
            <span className="text-emerald-400 font-semibold">G: {guesses.length}/3</span>
            <ChevronUp size={13} className="text-zinc-400 ml-0.5" />
          </button>
        ) : (
          /* Expanded Chat: Mobile Bottom Sheet Drawer / Desktop Bottom-Left Window */
          <div
            onWheel={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="pointer-events-auto flex flex-col overflow-hidden bg-obsidian-950/95 shadow-2xl backdrop-blur-xl transition-all max-md:h-[72vh] max-md:max-h-[75vh] max-md:rounded-t-2xl max-md:border-t max-md:border-white/20 md:h-[48vh] md:sm:h-[52vh] md:max-h-[48vh] md:sm:max-h-[52vh] md:w-80 md:sm:w-92 md:rounded-2xl md:border md:border-white/15 md:bg-obsidian-900/85"
          >
            {/* Mobile Drag Handle (Tap to collapse) */}
            <button
              type="button"
              onClick={() => setIsChatOpen(false)}
              className="w-full flex items-center justify-center pt-2.5 pb-1 md:hidden cursor-pointer touch-manipulation focus:outline-none"
              aria-label="Collapse chat drawer"
            >
              <div className="h-1.5 w-12 rounded-full bg-white/30 hover:bg-white/50 active:bg-white/60 transition-colors" />
            </button>

            {/* Notebook Tabbed Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-obsidian-950/80 px-4 py-3 shrink-0">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveChatTab('questions')}
                  className={`flex items-center gap-1.5 rounded-xl px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'questions'
                      ? 'bg-emerald-400/15 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <MessageSquare size={12} className={activeChatTab === 'questions' ? 'text-emerald-400' : ''} />
                  <span>Questions</span>
                  <span className="font-mono text-[10px] text-zinc-500">({questions.length}/10)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveChatTab('guesses')}
                  className={`flex items-center gap-1.5 rounded-xl px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'guesses'
                      ? 'bg-emerald-400/15 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <Target size={12} className={activeChatTab === 'guesses' ? 'text-emerald-400' : ''} />
                  <span>Guesses</span>
                  <span className="font-mono text-[10px] text-zinc-500">({guesses.length}/3)</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                className="rounded-sm p-1 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
                title="Minimize chat"
                aria-label="Minimize chat"
              >
                <ChevronDown size={14} />
              </button>
            </div>

            {/* Tab 1: Questions Stream */}
            {activeChatTab === 'questions' && (
              <div ref={questionsContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 custom-scrollbar overscroll-contain">
                <QuestionChat questions={sortedQuestions} notices={notices} mode="countrydle" isGameOver={isGameOver} />
              </div>
            )}

            {/* Tab 2: Guesses Stream */}
            {activeChatTab === 'guesses' && (
              <div ref={guessesContainerRef} className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 text-xs custom-scrollbar overscroll-contain">
                {guesses.length === 0 ? (
                  <div className="py-7 text-center text-zinc-400 space-y-1 border border-dashed border-white/10 rounded-sm p-4">
                    <Compass size={20} className="mx-auto text-zinc-600" />
                    <p className="font-mono text-[11px] uppercase tracking-wider text-sand-200">No attempts logged</p>
                    <p className="text-xs text-zinc-500">
                      Submit country guesses when ready (max 3 tries).
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
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. Floating Action Inputs Dock on the Map */}
      <div className="pointer-events-none max-md:fixed max-md:bottom-0 max-md:inset-x-0 max-md:z-[1000] max-md:w-full max-md:px-0 md:absolute md:bottom-4 md:left-1/2 md:z-[990] md:w-full md:max-w-md md:-translate-x-1/2 md:px-3">
        <div className="pointer-events-auto flex flex-col gap-2 bg-obsidian-950/95 shadow-2xl backdrop-blur-md transition-all max-md:rounded-none max-md:border-t max-md:border-white/15 max-md:p-2.5 max-md:pb-[max(0.75rem,env(safe-area-inset-bottom))] md:rounded-sm md:border md:border-white/15 md:bg-obsidian-900/85 md:p-3">
          {/* Action Tabs Switcher */}
          {!isGameOver ? (
            <>
              <div className="flex items-center justify-between border-b border-white/10 mb-1 pb-1">
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setUserSelectedTab('question')}
                    className={`flex items-center gap-1.5 px-2 sm:px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                      activeInputTab === 'question'
                        ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                        : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
                    }`}
                  >
                    <span>Question</span>
                    <span className="font-mono text-[10px] text-zinc-500">({gameState.remaining_questions}/10)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setUserSelectedTab('guess')}
                    className={`flex items-center gap-1.5 px-2 sm:px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                      activeInputTab === 'guess'
                        ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                        : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
                    }`}
                  >
                    <span>Guess</span>
                    <span className="font-mono text-[10px] text-zinc-500">({gameState.remaining_guesses}/3)</span>
                  </button>
                </div>

                {/* Mobile Chat Shortcut Trigger */}
                <button
                  type="button"
                  onClick={() => setIsChatOpen(true)}
                  className="md:hidden flex items-center gap-1 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-400 hover:bg-white/5 rounded-sm"
                  aria-label="Open chat"
                >
                  <MessageSquare size={12} />
                  <span>Chat</span>
                  <span className="text-sand-200">({questions.length})</span>
                </button>
              </div>
              {/* Active Input Component */}
              <div className="pt-0.5">
                {activeInputTab === 'question' ? (
                  <QuestionInput
                    onAsk={handleAsk}
                    isLoading={isLoading}
                    remainingQuestions={gameState.remaining_questions}
                    placeholder={t('gamePage.askPlaceholder', { count: gameState.remaining_questions })}
                    mode="country"
                  />
                ) : (
                  <GuessInput
                    dropup={true}
                    countries={countries}
                    alreadyGuessedNames={guesses.map((g) => g.guess)}
                    alreadyGuessedIds={guesses.map((g) => g.country_id).filter(Boolean)}
                    onGuess={async (id, name) => handleGuess(name, Number(id))}
                    onWarning={handleDuplicateGuess}
                    onUnknownGuess={async (name) => handleGuess(name, 0)}
                    isLoading={isLoading}
                    remainingGuesses={gameState.remaining_guesses}
                    placeholder={t('gamePage.guessPlaceholder', { count: gameState.remaining_guesses })}
                  />
                )}
              </div>
            </>
          ) : (
            /* Game Finished Bottom Bar */
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
          aria-label="Daily Results"
          onClick={() => setIsResultDismissed(true)}
          className="fixed inset-0 z-[1200] flex items-center justify-center p-3 sm:p-6 bg-black/75 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer overflow-y-auto"
        >
          <div
            className="relative z-10 w-full max-w-2xl sm:max-w-3xl max-h-[92vh] overflow-y-auto rounded-sm shadow-2xl my-auto cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <ShareResultCard
              gameName="Countrydle"
              gamePath="/game"
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={10}
              guessesMade={gameState.guesses_made}
              maxGuesses={3}
              targetName={correctCountry?.name || guesses.find((g) => g.answer)?.guess}
              isGuest={isGuest}
              targetCountryCode={correctCountry?.iso2 || revealedFlag}
              onClose={() => setIsResultDismissed(true)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
