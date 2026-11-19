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
  scoring?: {
    maxPoints: number;
    details: string[];
  };
  triggerClassName?: string;
  compact?: boolean;
}

const STORAGE_KEY = 'countrydle_guide_seen';

const GameInstructions = ({ gameName, scoring, triggerClassName, compact = false }: GameInstructionsProps) => {
  // Automatically open on first visit; remember dismissal in localStorage
  const [isOpen, setIsOpen] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== 'true';
    } catch {
      return false;
    }
  });

  const { t } = useTranslation();
  

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
        className="fixed inset-0 bg-app-canvas/85 backdrop-blur-sm transition-opacity cursor-pointer"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Spacious, Uncluttered Modal Dialog */}
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t('instructions.title', 'How to Play & Guide')}
        className="relative z-10 w-full max-w-3xl max-h-full sm:max-h-[calc(var(--app-height,100dvh)-3rem)] overflow-y-auto rounded-sm border border-app-border/20 bg-app-surface-raised p-4 sm:p-8 shadow-xl space-y-4 sm:space-y-6 my-auto text-app-text"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Title & Close Button */}
        <div className="flex items-start justify-between border-b border-app-border/15 pb-4 text-left gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-app-text flex items-center gap-2.5">
              <span>{`How to play ${gameName}`}</span>
            </h2>
            <p className="mt-1.5 text-sm text-app-text-secondary leading-relaxed max-w-xl">
              {'Ask strategic Yes/No questions, narrow down possibilities on the map, and deduce the secret location in limited attempts.'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm bg-app-surface-muted text-app-text-secondary hover:bg-app-canvas hover:text-app-text transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            aria-label="Close"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* 3 Core Gameplay Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* Step 1: Ask in Chat */}
          <div className="rounded-sm border border-app-border/15 bg-app-surface p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-semibold text-app-text-secondary">
                <MessageSquare size={15} className="shrink-0" />
                <span>{'1. Ask in Chat'}</span>
              </div>
              <p className="text-xs text-app-text-secondary leading-relaxed">
                {'Open Questions (Ask on phones) to ask in English or Polish about borders, seas, population, or capitals. Typos never cost a turn.'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-app-accent pt-1 block">
              {'Open the question tab to ask'}
            </span>
          </div>

          {/* Step 2: Mark the Map */}
          <div className="rounded-sm border border-app-border/15 bg-app-surface p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-semibold text-app-text-secondary">
                <MousePointerClick size={15} className="shrink-0" />
                <span>{'2. Mark the Map'}</span>
              </div>
              <p className="text-xs text-app-text-secondary leading-relaxed">
                {'On phones, tap an area to mark it red; tap it again to remove the mark. On desktop, choose a color in the map toolbar.'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-app-accent pt-1 block">
              {'Tap again to remove a mark'}
            </span>
          </div>

          {/* Step 3: Guess & Compass */}
          <div className="rounded-sm border border-app-border/15 bg-app-surface p-4 space-y-2 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-mono text-xs font-semibold text-app-text-secondary">
                <Compass size={15} className="shrink-0" />
                <span>{'3. Guess & Compass'}</span>
              </div>
              <p className="text-xs text-app-text-secondary leading-relaxed">
                {'Switch to the "Guess" tab when ready. Incorrect guesses reveal the distance in km and a directional arrow (e.g. ↗ 3,200 km) pointing towards the target.'}
              </p>
            </div>
            <span className="font-mono text-[10px] text-app-accent pt-1 block">
              {'Arrow points to target'}
            </span>
          </div>
        </div>


        {/* Compact Scoring & Rotation Strip */}
        <div className="rounded-sm border border-app-border/15 bg-app-surface-muted p-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-app-text-secondary">
          <div className="flex items-center gap-2">
            <Trophy size={15} className="text-app-accent shrink-0" />
            <span>
              {scoring ? (
                <>
                  <strong className="text-app-text">
                    {t('instructions.upToPoints', { maxPoints: scoring.maxPoints, defaultValue: `Up to +${scoring.maxPoints} pts` })}
                  </strong>{' '}
                  ({'speed, efficiency, accuracy, and daily streaks'})
                </>
              ) : (
                <span className="text-app-text">{'Earn points and build your daily winning streak'}</span>
              )}
            </span>
          </div>
          <span className="font-mono text-[11px] text-app-text-muted shrink-0">
            {'New puzzle daily at 00:00 UTC'}
          </span>
        </div>

        {/* Help Us Patch Mistakes (Honest, Grounded Feedback Callout) */}
        <div className="rounded-sm border border-amber-200 bg-amber-50 p-3.5 flex items-start gap-3 text-xs">
          <Flag size={15} className="text-amber-700 shrink-0 mt-0.5" />
          <p className="text-app-text-secondary leading-relaxed">
            <strong className="text-amber-900">{'Spot a mistake?'}</strong>{' '}
            {'After the game ends, click the flag icon on any answer card in your history to report it with notes — it helps us see mistakes and patch them quickly.'}
          </p>
        </div>

        {/* Bottom Action Bar */}
        <div className="border-t border-app-border/15 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-app-text-muted font-mono text-center sm:text-left">
            {"This guide won't show on startup again. You can always reopen it via the (?) button."}
          </p>
          <button
            type="button"
            onClick={handleClose}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-app-accent hover:bg-app-accent-hover px-6 py-2.5 text-sm font-semibold text-white transition-colors shadow-sm cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus shrink-0"
          >
            <span>{"Got it, let's play"}</span>
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
        className={`${triggerClassName || "flex h-9 items-center gap-1.5 px-3 rounded-sm border border-app-border/20 bg-app-surface-raised text-app-text-secondary hover:border-app-accent/40 hover:text-app-accent transition-colors text-xs font-semibold cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"} ${compact ? 'max-md:h-11 max-md:flex-1 max-md:justify-center max-md:px-2' : ''}`}
        title={t('instructions.title', 'How to Play & Guide')}
        aria-label={t('instructions.title', 'How to Play & Guide')}
      >
        <HelpCircle size={compact ? 13 : 15} className="text-app-accent shrink-0" aria-hidden="true" />
        {compact && <span className="md:hidden">{'Guide'}</span>}
        <span className={compact ? 'hidden md:inline' : undefined}>{t('instructions.title', 'Rules & Guide')}</span>
      </button>

      {isOpen && createPortal(modalContent, document.body)}
    </>
  );
};

export default GameInstructions;
