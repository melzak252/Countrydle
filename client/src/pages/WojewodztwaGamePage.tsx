import { useEffect, useState, useRef } from 'react';
import { useWojewodztwaGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import GuessInput from '../components/GuessInput';
import GameActionComposer from '../components/GameActionComposer';
import WojewodztwaMap from '../components/WojewodztwaMap';
import GameInstructions from '../components/GameInstructions';
import QuestionChat from '../components/QuestionChat';
import {
  Loader2,
  ChevronDown,
  ChevronUp,
  X,
  Check,
  Trophy,
  Compass,
  MessageSquare,
  Target,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ShareResultCard from '../components/ShareResultCard';
import { useIsMobile } from '../hooks/useMediaQuery';

function getDistanceColor(distanceKm: number): string {
  if (distanceKm <= 100) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  }
  if (distanceKm <= 300) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  }
  return 'border-white/10 bg-white/5 text-zinc-300';
}

export default function WojewodztwaGamePage() {
  const {
    gameState,
    questions,
    guesses,
    notices,
    addNotice,
    entities: wojewodztwa,
    correctEntity: correctWojewodztwo,
    isLoading,
    pendingQuestion,
    fetchGameState,
    fetchEntities: fetchWojewodztwa,
    askQuestion,
    makeGuess,
    syncGuestData,
    dailyDate,
  } = useWojewodztwaGameStore();
  const { t, i18n } = useTranslation();
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
    fetchWojewodztwa();
    window.addEventListener('auth-login', syncGuestData);
    return () => window.removeEventListener('auth-login', syncGuestData);
  }, [fetchGameState, fetchWojewodztwa, syncGuestData]);

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
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-mono text-zinc-400">Loading Województwodle puzzle…</span>
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
    const isQuestion = input.trim().endsWith('?') || /^(?:is\s|czy\s|does\s|what\s|which\s|are\s|can\s|has\s|have\s)/i.test(input.trim());
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

  const totalQuestions = 5;
  const totalGuesses = 2;

  return (
    <div className="relative flex-1 min-h-0 h-full w-full overflow-hidden bg-obsidian-950 font-sans select-none">
      <div className="game-map-layer absolute inset-0 z-0 w-full">
        <WojewodztwaMap
          correctWojewodztwoName={isGameOver ? correctWojewodztwo?.nazwa : undefined}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </div>

      {/* 2. Top Status HUD Bar */}
      <div className="game-status-bar pointer-events-none absolute inset-x-0 top-0 z-[1200] w-full md:inset-x-auto md:left-1/2 md:top-3 md:z-[1000] md:w-auto md:-translate-x-1/2 md:px-2 md:max-w-full">
        <div className="pointer-events-auto flex h-11 w-full items-stretch border-b border-white/10 bg-obsidian-950 text-xs font-mono md:h-8 md:w-auto md:divide-x md:divide-white/10 md:rounded-sm md:border md:border-white/15 md:bg-obsidian-900/85 md:shadow-lg md:backdrop-blur-md">
          <div className="hidden md:flex items-center gap-2 px-3 text-[10px] uppercase tracking-[0.16em] text-zinc-400">
            <span>Województwa</span>
            <span className="font-semibold text-sand-100 hidden sm:inline">{dailyDate}</span>
          </div>

          <div className="flex flex-1 items-center justify-center gap-1.5 px-2 md:flex-none md:px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">Q:</span>
            <span className="font-semibold text-sand-100">
              {gameState.remaining_questions}
              <span className="text-[10px] text-zinc-500">/{totalQuestions}</span>
            </span>
          </div>

          <div className="flex flex-1 items-center justify-center gap-1.5 px-2 md:flex-none md:px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">G:</span>
            <span className="font-semibold text-emerald-400">
              {gameState.remaining_guesses}
              <span className="text-[10px] text-zinc-500">/{totalGuesses}</span>
            </span>
          </div>

          <GameInstructions
            gameName={t('wojewodztwaPage.title')}
            examples={t('wojewodztwaPage.examples', { returnObjects: true }) as string[]}
            scoring={{ maxPoints: 3500, details: t('wojewodztwaPage.scoringDetails', { returnObjects: true }) as string[] }}
            compact={true}
            triggerClassName="max-md:min-h-11 max-md:min-w-11 flex items-center gap-1.5 px-2.5 text-zinc-400 hover:text-sand-100 hover:bg-white/5 transition-colors text-[10px] uppercase tracking-[0.16em] cursor-pointer whitespace-nowrap"
          />

          {isGameOver && (
            <button
              type="button"
              onClick={() => setIsResultDismissed(false)}
              className="max-md:min-h-11 flex items-center gap-1.5 bg-emerald-500/20 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-300 hover:bg-emerald-500/30 transition-colors cursor-pointer"
            >
              <Trophy size={13} />
              <span>{i18n.language.startsWith('pl') ? 'Wynik' : 'Result'}</span>
            </button>
          )}
        </div>
      </div>

      {/* 3. Unified Deduction Notebook & Chat */}

      <div className={`pointer-events-none ${
        isChatOpen
          ? 'game-notebook-layer absolute inset-0 z-[1100] md:absolute md:inset-0 md:z-[1000]'
          : 'absolute inset-x-0 bottom-0 z-[995] w-full pb-[env(safe-area-inset-bottom)] md:absolute md:inset-x-auto md:left-4 md:bottom-4 md:z-[1000] md:w-fit md:max-w-[calc(100vw-2rem)]'
      }`}>
        {!isChatOpen ? (
          <div className="pointer-events-auto flex w-full gap-2 border-t border-white/15 bg-obsidian-950 p-1 shadow-xl md:block md:w-auto md:border md:bg-obsidian-900/90 md:p-0">
            <button type="button" onClick={() => { setUserSelectedTab('question'); setIsChatOpen(true); }} className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-sm border border-white/10 bg-obsidian-900 px-3 font-mono text-xs text-sand-100 hover:bg-obsidian-850 md:hidden">
              {i18n.language.startsWith('pl') ? 'Pytaj' : 'Ask'} <span className="text-zinc-400">{gameState.remaining_questions}/{totalQuestions}</span>
            </button>
            <button type="button" onClick={() => { setUserSelectedTab('guess'); setIsChatOpen(true); }} className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-sm border border-white/10 bg-obsidian-900 px-3 font-mono text-xs text-sand-100 hover:bg-obsidian-850 md:hidden">
              {i18n.language.startsWith('pl') ? 'Zgadnij' : 'Guess'} <span className="text-emerald-400">{gameState.remaining_guesses}/{totalGuesses}</span>
            </button>
            <button type="button" onClick={() => setIsChatOpen(true)} className="hidden min-h-11 items-center gap-2 rounded-sm border border-white/15 bg-obsidian-900/90 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100 md:flex" aria-label={i18n.language.startsWith('pl') ? 'Otwórz notatnik' : 'Open notebook'}>
              <MessageSquare size={13} className="text-emerald-400" />
              <span>{i18n.language.startsWith('pl') ? 'Notatnik' : 'Notebook'}</span>
              <span className="text-sand-100 font-semibold">Q: {questions.length}/{totalQuestions}</span>
              <span className="text-zinc-500">·</span>
              <span className="text-emerald-400 font-semibold">G: {guesses.length}/{totalGuesses}</span>
              <ChevronUp size={13} className="text-zinc-400 ml-0.5" />
            </button>
          </div>
        ) : (
          <div onWheel={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()} className="pointer-events-auto absolute inset-0 flex h-full flex-col overflow-hidden bg-obsidian-950 pb-[env(safe-area-inset-bottom)] shadow-2xl transition-all md:inset-x-auto md:inset-y-auto md:left-4 md:bottom-4 md:h-[68vh] md:max-h-[72vh] md:w-[28rem] md:rounded-2xl md:border md:bg-obsidian-900/85 md:pb-0">

            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-obsidian-950 px-2 py-1 shrink-0 md:px-4 md:py-3">
              <div role="group" aria-label={i18n.language.startsWith('pl') ? 'Wybierz pytanie lub zgadnięcie' : 'Choose question or guess'} className="flex items-center gap-1">
                <button
                  type="button"
                  aria-pressed={activeChatTab === 'questions'}
                  onClick={() => setUserSelectedTab('question')}
                  className={`flex min-h-11 items-center gap-1 rounded-xl px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'questions'
                      ? 'bg-emerald-400/15 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <MessageSquare size={12} className={`hidden md:block ${activeChatTab === 'questions' ? 'text-emerald-400' : ''}`} />
                  <span className="md:hidden">{i18n.language.startsWith('pl') ? 'Pytaj' : 'Ask'}</span>
                  <span className="hidden md:inline">{i18n.language.startsWith('pl') ? 'Pytania' : 'Questions'}</span>
                  <span className="font-mono text-[10px] text-zinc-500">({questions.length}/{totalQuestions})</span>
                </button>

                <button
                  type="button"
                  aria-pressed={activeChatTab === 'guesses'}
                  onClick={() => setUserSelectedTab('guess')}
                  className={`flex min-h-11 items-center gap-1 rounded-xl px-2 py-2 text-xs transition-colors cursor-pointer ${
                    activeChatTab === 'guesses'
                      ? 'bg-emerald-400/15 font-semibold text-sand-100'
                      : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                  }`}
                >
                  <Target size={12} className={`hidden md:block ${activeChatTab === 'guesses' ? 'text-emerald-400' : ''}`} />
                  <span className="md:hidden">{i18n.language.startsWith('pl') ? 'Zgadnij' : 'Guess'}</span>
                  <span className="hidden md:inline">{i18n.language.startsWith('pl') ? 'Zgadnięcia' : 'Guesses'}</span>
                  <span className="font-mono text-[10px] text-zinc-500">({guesses.length}/{totalGuesses})</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                className="flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-sm px-2 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
                title={i18n.language.startsWith('pl') ? 'Pokaż mapę' : 'Show map'}
                aria-label={i18n.language.startsWith('pl') ? 'Pokaż mapę' : 'Show map'}
              >
                <span className="text-xs md:hidden">{i18n.language.startsWith('pl') ? 'Mapa' : 'Map'}</span>
                <ChevronDown size={14} />
              </button>
            </div>

            {/* Tab 1: Questions Stream */}
            {activeChatTab === 'questions' && (
              <div ref={questionsContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 custom-scrollbar overscroll-contain">
                <QuestionChat questions={sortedQuestions} notices={notices} mode="wojewodztwodle" isGameOver={isGameOver} isLoading={isLoading} pendingQuestion={pendingQuestion} />
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
                      Submit voivodeship guesses when ready (max {totalGuesses} tries).
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
                    placeholder={t('wojewodztwaPage.askPlaceholder', { count: gameState.remaining_questions })}
                    mode="wojewodztwa"
                  />
                ) : (
                  <GuessInput
                    dropup={true}
                    countries={wojewodztwa}
                    alreadyGuessedNames={guesses.map((g) => g.guess)}
                    alreadyGuessedIds={guesses.map((g) => g.wojewodztwo_id).filter(Boolean)}
                    onGuess={async (id, name) => handleGuess(name, Number(id))}
                    onWarning={handleGuessWarning}
                    onUnknownGuess={async (name) => handleGuess(name, 0)}
                    isLoading={isLoading}
                    remainingGuesses={gameState.remaining_guesses}
                    placeholder={t('wojewodztwaPage.guessPlaceholder', { count: gameState.remaining_guesses })}
                  />
                )}
              </GameActionComposer>
            ) : (
              <div className="flex items-center justify-between gap-3 border-t border-white/10 bg-obsidian-950/80 px-4 py-3">
                <div className="flex items-center gap-3">
                  <Trophy size={16} className="text-amber-400" />
                  <span className="font-mono text-xs uppercase tracking-wider font-semibold text-sand-100">
                    {gameState.won ? 'Fieldwork solved' : 'Investigation concluded'}
                  </span>
                  <span className="font-mono text-xs text-emerald-400">{gameState.points} pts</span>
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
        )}
      </div>


      {/* 5. Game Over Modal Overlay */}
      {isGameOver && showResultModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Daily Results"
          onClick={() => setIsResultDismissed(true)}
          className="fixed inset-0 z-[1200] flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
        >
          <div
            className="relative z-10 w-full max-w-2xl sm:max-w-3xl rounded-sm shadow-2xl cursor-default"
            onClick={(e) => e.stopPropagation()}
          >
            <ShareResultCard
              gameName="Województwodle"
              gamePath="/wojewodztwa"
              date={dailyDate}
              won={gameState.won}
              points={gameState.points}
              questionsAsked={gameState.questions_asked}
              maxQuestions={totalQuestions}
              guessesMade={gameState.guesses_made}
              maxGuesses={totalGuesses}
              targetName={correctWojewodztwo?.nazwa || guesses.find((g) => g.answer)?.guess}
              onClose={() => setIsResultDismissed(true)}
              questions={sortedQuestions}
              notices={notices}
              mode="wojewodztwodle"
            />
          </div>
        </div>
      )}
    </div>
  );
}
