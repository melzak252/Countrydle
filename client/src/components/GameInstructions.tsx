import { useState, useEffect } from 'react';
import { Info, HelpCircle, Languages, Trophy, X } from 'lucide-react';
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

const GameInstructions = ({ gameName, examples, scoring, triggerClassName, compact = false }: GameInstructionsProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const { t, i18n } = useTranslation();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const modalContent = (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-3 sm:p-4 overflow-y-auto animate-in fade-in duration-200">
      {/* Full-screen Dark Backdrop */}
      <div
        className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity cursor-pointer"
        onClick={() => setIsOpen(false)}
        aria-hidden="true"
      />

      {/* Modal Dialog Content */}
      <div 
        role="dialog"
        aria-modal="true"
        aria-label={t('instructions.title', 'How to Play & Info')}
        className="relative z-10 w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-5 sm:p-6 shadow-2xl space-y-5 my-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Row */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3 -mt-1 text-left">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-emerald-400">
              {i18n.language.startsWith('pl') ? 'Zasady i wskazówki' : 'Rules & Guide'}
            </span>
          </div>
          <button 
            type="button"
            onClick={() => setIsOpen(false)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
            aria-label="Close"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Title */}
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-sand-100 flex items-center gap-2">
            <span>🚩 {t('instructions.title', 'How to Play')}</span>
          </h2>
          <p className="mt-1.5 text-xs sm:text-sm text-zinc-400 leading-relaxed">
            {i18n.language.startsWith('pl')
              ? `Odgadnij ukryty cel w ${gameName} zadając pytania tak/nie i typując prawidłową lokalizację.`
              : `Deduce today’s hidden target in ${gameName} with strategic yes/no questions and precise guesses.`}
          </p>
        </div>

        {/* Core Rules Callout Cards */}
        <div className="space-y-3 text-xs sm:text-sm text-zinc-300 leading-relaxed">
          {/* Card 1: Question Asking */}
          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-sand-100">
              <HelpCircle size={16} className="text-emerald-400 shrink-0" />
              <span>{i18n.language.startsWith('pl') ? '1. Pytania tak/nie' : '1. Yes/No Questions'}</span>
            </div>
            <p className="text-zinc-400">
              {i18n.language.startsWith('pl')
                ? 'Zadawaj pytania o położenie, kontynent, sąsiadów, dostęp do wody, ludność czy flagę. Pytania są weryfikowane przez lokalną bazę faktów bez halucynacji.'
                : 'Ask questions about hemisphere, borders, water access, population, capital, or flags. Each query is evaluated against verified local fact tables with 0 hallucination.'}
            </p>
          </div>

          {/* Card 2: Multilingual Support */}
          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-sand-100">
              <Languages size={16} className="text-emerald-400 shrink-0" />
              <span>{i18n.language.startsWith('pl') ? '2. Język pytań' : '2. Any Language'}</span>
            </div>
            <p className="text-zinc-400">
              {i18n.language.startsWith('pl')
                ? 'Możesz pytać po polsku lub po angielsku (np. "Czy leży w Europie?" lub "Does it border Germany?").'
                : 'You can ask naturally in English or Polish (e.g. "Is it in Europe?" or "Czy ma dostęp do morza?").'}
            </p>
          </div>

          {/* Card 3: Typos & Penalties */}
          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-sand-100">
              <Info size={16} className="text-emerald-400 shrink-0" />
              <span>{i18n.language.startsWith('pl') ? '3. Ochrona przed literówkami' : '3. Zero-Penalty Validation'}</span>
            </div>
            <p className="text-zinc-400">
              {i18n.language.startsWith('pl')
                ? 'Pytania otwarte lub z błędami są oznaczane jako nieprawidłowe i nie zużywają Twojego limitu pytań.'
                : 'Open-ended or unparseable questions are flagged without deducting from your question budget.'}
            </p>
          </div>
        </div>

        {/* Scoring Breakdown */}
        {scoring && (
          <div className="space-y-2.5 pt-1">
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-sand-400">
              <Trophy size={14} className="text-emerald-400" />
              <span>{t('instructions.scoring', 'Scoring Breakdown')}</span>
            </div>
            <div className="rounded-sm border border-emerald-500/25 bg-emerald-950/20 p-3.5">
              <div className="text-xl font-bold font-mono text-emerald-300 mb-2">
                {t('instructions.upToPoints', { maxPoints: scoring.maxPoints, defaultValue: `Up to +${scoring.maxPoints} pts` })}
              </div>
              <ul className="space-y-1.5 text-xs text-zinc-300">
                {scoring.details.map((detail, index) => (
                  <li key={index} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                    <span>{detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Example Questions */}
        <div className="space-y-2.5 pt-1">
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-sand-400">
            <HelpCircle size={14} className="text-emerald-400" />
            <span>{t('instructions.examples', 'Example Questions')}</span>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {examples.map((example, index) => (
              <div
                key={index}
                className="rounded-sm border border-white/10 bg-obsidian-900 px-3.5 py-2 font-mono text-xs text-sand-200"
              >
                "{example}"
              </div>
            ))}
          </div>
        </div>

        {/* Dismiss Button */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="w-full rounded-sm bg-emerald-400 hover:bg-emerald-300 py-3 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer"
          >
            {i18n.language.startsWith('pl') ? 'Rozumiem, gramy!' : "Got it, let's play!"}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button 
        type="button"
        onClick={() => setIsOpen(true)}
        className={triggerClassName || "flex h-9 items-center gap-1.5 px-3 rounded-sm border border-white/15 bg-obsidian-900 text-zinc-300 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors text-xs font-semibold cursor-pointer"}
        title={t('instructions.title', 'How to Play & Info')}
      >
        <HelpCircle size={compact ? 13 : 15} className="text-emerald-400 shrink-0" aria-hidden="true" />
        <span>{compact ? (i18n.language.startsWith('pl') ? 'Zasady' : 'Guide') : (i18n.language.startsWith('pl') ? 'Jak grać' : 'How to Play')}</span>
      </button>
      {isOpen && createPortal(modalContent, document.body)}
    </>
  );
};

export default GameInstructions;

