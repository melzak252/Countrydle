import { useState, useEffect } from 'react';
import {
  HelpCircle,
  Trophy,
  X,
  MessageSquare,
  Compass,
  ArrowRight,
  MousePointerClick,
  Flag,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { createPortal } from 'react-dom';

interface GameInstructionsProps {
  gameName: string;
  examples: string[];
  scoring?: {
    maxPoints: number;
    details: string[];
  };
  triggerClassName?: string;
  compact?: boolean;
}

const STORAGE_KEY = 'countrydle_guide_seen';

const GameInstructions = ({ gameName, examples, scoring, triggerClassName, compact = false }: GameInstructionsProps) => {
  // Automatically open on first visit; remember dismissal in localStorage
  const [isOpen, setIsOpen] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== 'true';
    } catch {
      return false;
    }
  });

  const { t, i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const handleClose = () => {
    setIsOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // Ignore storage errors in private browsing / sandboxes
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const modalContent = (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-2 sm:p-6 overflow-y-auto animate-in fade-in duration-200" style={{ maxHeight: 'var(--app-height, 100dvh)' }}>
      {/* Full-screen Dark Backdrop */}
      <div
        className="fixed inset-0 bg-black/85 backdrop-blur-md transition-opacity cursor-pointer"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Spacious, Uncluttered Modal Dialog */}
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t('instructions.title', 'How to Play & Guide')}
        className="relative z-10 w-full max-w-3xl max-h-full sm:max-h-[calc(var(--app-height,100dvh)-3rem)] overflow-y-auto rounded-md border border-white/15 bg-obsidian-950 p-4 sm:p-8 shadow-2xl space-y-4 sm:space-y-6 my-auto text-sand-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Title & Close Button */}
        <div className="flex items-start justify-between border-b border-white/10 pb-4 text-left gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-sand-100 flex items-center gap-2.5">
              <span>🗺️ {isPl ? `Jak grać w ${gameName}?` : `How to play ${gameName}`}</span>
            </h2>
            <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed max-w-xl">
              {isPl
                ? 'Zadawaj pytania Tak/Nie, eliminuj obszary na mapie i odgadnij ukryty cel w ograniczonej liczbie prób.'
                : 'Ask strategic Yes/No questions, narrow down possibilities on the map, and deduce the secret location in limited attempts.'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
            aria-label="Close"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* 3 Core Gameplay Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* Step 1: Ask in Chat */}
          <div className="rounded-sm border border-emerald-500/25 bg-obsidian-900/60 p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                <MessageSquare size={15} className="shrink-0" />
                <span>{isPl ? '1. Pytaj w Czacie' : '1. Ask in Chat'}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Otwórz zakładkę pytań (Pytaj na telefonie), aby zapytać po polsku lub angielsku o granice, morza, ludność czy stolicę. Literówki nie zużywają tury!'
                  : 'Open Questions (Ask on phones) to ask in English or Polish about borders, seas, population, or capitals. Typos never cost a turn!'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-emerald-300/80 pt-1 block">
              {isPl ? 'Otwórz zakładkę pytań' : 'Open the question tab to ask'}
            </span>
          </div>

          {/* Step 2: Mark the Map */}
          <div className="rounded-sm border border-cyan-500/25 bg-obsidian-900/60 p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-cyan-400">
                <MousePointerClick size={15} className="shrink-0" />
                <span>{isPl ? '2. Oznaczaj Mapę' : '2. Mark the Map'}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Na telefonie dotknij obszaru, aby oznaczyć go na czerwono; dotknij ponownie, aby usunąć oznaczenie. Na komputerze wybierz kolor w narzędziach mapy.'
                  : 'On phones, tap an area to mark it red; tap it again to remove the mark. On desktop, choose a color in the map toolbar.'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-cyan-300/80 pt-1 block">
              {isPl ? 'Dotknij ponownie, aby usunąć oznaczenie' : 'Tap again to remove a mark'}
            </span>
          </div>

          {/* Step 3: Guess & Compass */}
          <div className="rounded-sm border border-amber-500/25 bg-obsidian-900/60 p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-amber-400">
                <Compass size={15} className="shrink-0" />
                <span>{isPl ? '3. Strzał & Kompas' : '3. Guess & Compass'}</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Przełącz na zakładkę „Strzał”, by wytypować cel. Błędny strzał daje odległość w km i strzałkę kierunkową (np. ↗ 3,200 km) prowadzącą do celu.'
                  : 'Switch to the "Guess" tab when ready. Incorrect guesses reveal the distance in km and a directional arrow (e.g. ↗ 3,200 km) pointing towards the target.'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-amber-300/80 pt-1 block">
              {isPl ? 'Strzałka wskazuje azymut' : 'Arrow points to target'}
            </span>
          </div>
        </div>

        {/* Example Questions Bank (Full text, no cutoff) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
            <span className="flex items-center gap-1.5 uppercase tracking-wider text-sand-300 font-semibold">
              <HelpCircle size={13} className="text-emerald-400" />
              {isPl ? 'Przykłady pytań w tym trybie:' : 'Great questions to ask in this game:'}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {examples.map((example, index) => (
              <div
                key={index}
                className="rounded-sm border border-white/10 bg-obsidian-900/80 px-3 py-2 font-mono text-xs text-sand-200 flex items-start gap-2"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0 mt-1" />
                <span className="break-words whitespace-normal leading-relaxed">"{example}"</span>
              </div>
            ))}
          </div>
        </div>

        {/* Compact Scoring & Rotation Strip */}
        <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-400">
          <div className="flex items-center gap-2">
            <Trophy size={15} className="text-emerald-400 shrink-0" />
            <span>
              {scoring ? (
                <>
                  <strong className="text-sand-100">
                    {t('instructions.upToPoints', { maxPoints: scoring.maxPoints, defaultValue: `Up to +${scoring.maxPoints} pts` })}
                  </strong>{' '}
                  ({isPl ? 'premia za mało pytań, trafny strzał, czas i serie' : 'speed, efficiency, accuracy, and daily streaks'})
                </>
              ) : (
                <span className="text-sand-200">{isPl ? 'Zbieraj punkty i buduj codzienną serię zwycięstw' : 'Earn points and build your daily winning streak'}</span>
              )}
            </span>
          </div>
          <span className="font-mono text-[11px] text-zinc-500 shrink-0">
            {isPl ? 'Reset o 00:00 UTC' : 'New puzzle daily at 00:00 UTC'}
          </span>
        </div>

        {/* Help Us Patch Mistakes (Honest, Grounded Feedback Callout) */}
        <div className="rounded-sm border border-amber-500/20 bg-amber-500/[0.04] p-3.5 flex items-start gap-3 text-xs">
          <Flag size={15} className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-zinc-300 leading-relaxed">
            <strong className="text-amber-300">{isPl ? 'Zauważyłeś błąd?' : 'Spot a mistake?'}</strong>{' '}
            {isPl
              ? 'Po zakończeniu gry kliknij ikonę flagi na dowolnej karcie odpowiedzi, aby dodać uwagę — pomaga nam to wyłapywać błędy i szybko je poprawiać.'
              : 'After the game ends, click the flag icon on any answer card in your history to report it with notes — it helps us see mistakes and patch them quickly.'}
          </p>
        </div>

        {/* Bottom Action Bar */}
        <div className="border-t border-white/10 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-zinc-500 font-mono text-center sm:text-left">
            {isPl
              ? 'Przewodnik nie pojawi się ponownie automatycznie. Możesz go otworzyć w każdej chwili przyciskiem (?).'
              : "This guide won't show on startup again. You can always reopen it via the (?) button."}
          </p>
          <button
            type="button"
            onClick={handleClose}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-6 py-2.5 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 shrink-0"
          >
            <span>{isPl ? 'Rozumiem, gramy!' : "Got it, let's play!"}</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </section>
    </div>
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`${triggerClassName || "flex h-9 items-center gap-1.5 px-3 rounded-sm border border-white/15 bg-obsidian-900 text-zinc-300 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors text-xs font-semibold cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"} ${compact ? 'max-md:h-11 max-md:flex-1 max-md:justify-center max-md:px-2' : ''}`}
        title={t('instructions.title', 'How to Play & Guide')}
        aria-label={t('instructions.title', 'How to Play & Guide')}
      >
        <HelpCircle size={compact ? 13 : 15} className="text-emerald-400 shrink-0" aria-hidden="true" />
        {compact && <span className="md:hidden">{isPl ? 'Zasady' : 'Guide'}</span>}
        <span className={compact ? 'hidden md:inline' : undefined}>{t('instructions.title', 'Rules & Guide')}</span>
      </button>

      {isOpen && createPortal(modalContent, document.body)}
    </>
  );
};

export default GameInstructions;
