import { useState, useEffect } from 'react';
import {
  HelpCircle,
  Languages,
  Trophy,
  X,
  MessageSquare,
  Compass,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  Zap,
  Check,
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
  // Show automatically on first visit; remember dismissal in localStorage
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
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-3 sm:p-6 overflow-y-auto animate-in fade-in duration-200">
      {/* Full-screen Dark Backdrop */}
      <div
        className="fixed inset-0 bg-black/85 backdrop-blur-md transition-opacity cursor-pointer"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Content — WIDER CONTAINER (max-w-4xl) */}
      <section
        role="dialog"
        aria-modal="true"
        aria-label={t('instructions.title', 'How to Play & Guide')}
        className="relative z-10 w-full max-w-4xl max-h-[92vh] overflow-y-auto rounded-md border border-white/15 bg-obsidian-950 p-6 sm:p-8 shadow-2xl space-y-6 my-auto text-sand-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Row */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4 text-left">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-400">
              <Zap size={13} aria-hidden="true" />
              {isPl ? 'Przewodnik Nowego Gracza' : 'New Player Guide'}
            </span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
            aria-label="Close"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Title & Core Premise */}
        <div>
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-serif font-bold tracking-tight text-sand-100 flex items-center gap-2.5">
            <span>🗺️ {isPl ? `Jak Grać w ${gameName}?` : `How to Play ${gameName}`}</span>
          </h2>
          <p className="mt-2 text-sm sm:text-base text-zinc-400 leading-relaxed max-w-2xl">
            {isPl
              ? `Odgadnij dzisiejszą tajną lokalizację w ${gameName}. Zadawaj strategiczne pytania Tak/Nie, eliminuj obszary i wytypuj prawidłowy cel w ograniczonej liczbie prób.`
              : `Deduce today’s mystery location in ${gameName}. Ask strategic Yes/No questions, eliminate candidates on the map, and submit your final guess in limited attempts.`}
          </p>
        </div>

        {/* 4-Step Progressive Walkthrough Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Step 1: Ask Questions */}
          <div className="rounded-sm border border-emerald-500/30 bg-obsidian-900/80 p-5 space-y-2.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                  <MessageSquare size={16} className="shrink-0" />
                  <span>{isPl ? 'Krok 1: Pytania Tak/Nie' : 'Step 1: Ask Yes/No Questions'}</span>
                </div>
                <span className="font-mono text-[10px] text-zinc-500">0% Hallucination</span>
              </div>
              <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Zadawaj pytania o położenie geograficzne, granice, dostęp do morza, populację, rzeki czy historię. Pytania są sprawdzane w relacyjnej bazie faktów bez zmyślania odpowiedzi.'
                  : 'Ask about hemisphere, neighboring borders, ocean access, population, mountain ranges, or flags. Queries are verified against offline fact tables with 0 hallucinations.'}
              </p>
            </div>
            <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-[11px] font-mono text-emerald-300/80">
              <Languages size={13} className="shrink-0" />
              <span>{isPl ? 'Działa po polsku i angielsku' : 'Ask in English or Polish'}</span>
            </div>
          </div>

          {/* Step 2: Instant Feedback & Clues */}
          <div className="rounded-sm border border-cyan-500/30 bg-obsidian-900/80 p-5 space-y-2.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-cyan-400">
                  <CheckCircle2 size={16} className="shrink-0" />
                  <span>{isPl ? 'Krok 2: Wskazówki i Bezpieczeństwo' : 'Step 2: Instant Clues & Zero Penalty'}</span>
                </div>
                <span className="font-mono text-[10px] text-zinc-500">Fast Verification</span>
              </div>
              <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Zweryfikowane odpowiedzi pojawiają się na osi czasu jako zielone TAK lub szare NIE. Literówki są korygowane, a pytania otwarte są bezpiecznie odrzucane bez utraty tury!'
                  : 'Verified answers appear in your timeline as green YES or gray NO cards. Misspellings are auto-resolved, and invalid/open questions are safely rejected without losing a turn!'}
              </p>
            </div>
            <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-[11px] font-mono text-cyan-300/80">
              <ShieldCheck size={13} className="shrink-0" />
              <span>{isPl ? '0 utraty tury przy błędach' : 'Zero turns deducted on invalid input'}</span>
            </div>
          </div>

          {/* Step 3: Location Guesses & Distance Hints */}
          <div className="rounded-sm border border-amber-500/30 bg-obsidian-900/80 p-5 space-y-2.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-amber-400">
                  <Compass size={16} className="shrink-0" />
                  <span>{isPl ? 'Krok 3: Typowanie i Kompas' : 'Step 3: Guesses & Compass Hints'}</span>
                </div>
                <span className="font-mono text-[10px] text-zinc-500">Directional Clues</span>
              </div>
              <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Gdy zawęzisz obszar, przełącz się na zakładkę „Strzał” i wytypuj lokalizację. Niepoprawny strzał podaje dokładną odległość w km i strzałkę kierunkową (np. ↗ 3,200 km).'
                  : 'When ready, switch to the "Guess" tab. Each incorrect guess reveals the exact distance in km and a compass bearing arrow (e.g. ↗ 3,200 km) pointing directly towards the mystery target.'}
              </p>
            </div>
            <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-[11px] font-mono text-amber-300/80">
              <Compass size={13} className="shrink-0" />
              <span>{isPl ? 'Strzałka wskazuje azymut' : 'Bearing arrow points to secret location'}</span>
            </div>
          </div>

          {/* Step 4: Scoring & Daily Streaks */}
          <div className="rounded-sm border border-indigo-500/30 bg-obsidian-900/80 p-5 space-y-2.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-indigo-400">
                  <Trophy size={16} className="shrink-0" />
                  <span>{isPl ? 'Krok 4: Punkty i Serie Zwycięstw' : 'Step 4: Scores & Daily Streaks'}</span>
                </div>
                <span className="font-mono text-[10px] text-zinc-500">00:00 UTC Reset</span>
              </div>
              <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                {isPl
                  ? 'Zdobywaj punkty za oszczędność pytań (do +1,500 pkt), trafność pierwszego strzału (do +500 pkt), szybkość i codzienną serię zwycięstw (+50 pkt za dzień). Nowa zagadka co północ UTC!'
                  : 'Earn points for question efficiency (up to +1,500), first-guess accuracy (up to +500), speed, and daily winning streaks (+50/day). A brand new puzzle resets daily at 00:00 UTC!'}
              </p>
            </div>
            <div className="pt-2 border-t border-white/5 flex items-center gap-1.5 text-[11px] font-mono text-indigo-300/80">
              <Trophy size={13} className="shrink-0" />
              <span>{isPl ? 'Codzienna rotacja o północy UTC' : 'Deterministic daily midnight rotation'}</span>
            </div>
          </div>
        </div>

        {/* Example Questions Bank */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between font-mono text-xs text-zinc-400 border-b border-white/10 pb-2">
            <span className="uppercase tracking-wider font-semibold text-sand-300 flex items-center gap-1.5">
              <HelpCircle size={14} className="text-emerald-400" />
              {isPl ? 'Przykłady pytań w tym trybie:' : 'Great questions to ask in this game:'}
            </span>
            <span className="text-[11px] text-zinc-500">{isPl ? 'Kliknij pole pytania i wpisz własne' : 'Try asking these in the game'}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {examples.map((example, index) => (
              <div
                key={index}
                className="rounded-sm border border-white/10 bg-obsidian-900/90 px-3.5 py-2.5 font-mono text-xs text-sand-200 flex items-center gap-2"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                <span className="truncate">"{example}"</span>
              </div>
            ))}
          </div>
        </div>

        {/* Scoring Breakdown (if provided) */}
        {scoring && (
          <div className="rounded-sm border border-white/10 bg-obsidian-900/50 p-4 space-y-2">
            <div className="flex items-center justify-between font-mono text-xs text-zinc-400">
              <span className="uppercase tracking-wider font-semibold text-sand-300 flex items-center gap-1.5">
                <Trophy size={14} className="text-emerald-400" />
                {t('instructions.scoring', 'Scoring Details')}
              </span>
              <span className="font-bold text-emerald-300">
                {t('instructions.upToPoints', { maxPoints: scoring.maxPoints, defaultValue: `Up to +${scoring.maxPoints} pts` })}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
              {scoring.details.map((detail, index) => (
                <div key={index} className="rounded-sm border border-white/5 bg-obsidian-950/60 p-2.5 text-xs text-zinc-300 flex items-start gap-2">
                  <Check size={13} className="text-emerald-400 shrink-0 mt-0.5" />
                  <span>{detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bottom Action & Onboarding Note Bar */}
        <div className="border-t border-white/10 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-zinc-500 font-mono text-center sm:text-left">
            {isPl
              ? 'Przewodnik nie pojawi się ponownie automatycznie. Możesz go zawsze otworzyć przyciskiem (?) na górze.'
              : "This guide won't show automatically on startup again. You can always reopen it via the (?) button."}
          </p>
          <button
            type="button"
            onClick={handleClose}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-6 py-3 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 shrink-0"
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
        className={triggerClassName || "flex h-9 items-center gap-1.5 px-3 rounded-sm border border-white/15 bg-obsidian-900 text-zinc-300 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors text-xs font-semibold cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"}
        title={t('instructions.title', 'How to Play & Guide')}
      >
        <HelpCircle size={compact ? 13 : 15} className="text-emerald-400 shrink-0" aria-hidden="true" />
        <span>{t('instructions.title', 'Rules & Guide')}</span>
      </button>

      {isOpen && createPortal(modalContent, document.body)}
    </>
  );
};

export default GameInstructions;
