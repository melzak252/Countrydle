import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import {
  Shield,
  Play,
  Pause,
  RotateCcw,
  Flag,
  Check,
  X,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Trophy,
  Eye,
  Loader2,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import POWIAT_CATALOG from '../data/powiats_quiz_catalog.json';

interface QuizPowiat {
  id: number;
  name: string;
  voivodeship: string;
  is_city_county: boolean;
  seat: string | null;
  population: number | null;
  area_km2: number | null;
  registration_plates: string[];
}

function normalizeQuizText(str: string): string {
  return str
    .toLowerCase()
    .replace(/ą/g, 'a')
    .replace(/ć/g, 'c')
    .replace(/ę/g, 'e')
    .replace(/ł/g, 'l')
    .replace(/ń/g, 'n')
    .replace(/ó/g, 'o')
    .replace(/ś/g, 's')
    .replace(/ź/g, 'z')
    .replace(/ż/g, 'z')
    .replace(/[-–—./]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getAcceptedForms(p: QuizPowiat): string[] {
  const rawCandidates = [p.name, p.name.replace(/\s*\([^)]*\)/g, '').trim()];
  const forms = new Set<string>();
  for (const cand of rawCandidates) {
    const full = normalizeQuizText(cand);
    if (!full) continue;
    forms.add(full);
    if (full.startsWith('powiat ')) {
      const shortName = full.slice('powiat '.length).trim();
      if (shortName) {
        forms.add(shortName);
        forms.add(`pow ${shortName}`);
      }
    } else {
      forms.add(`m ${full}`);
      forms.add(`miasto ${full}`);
    }
  }
  return Array.from(forms);
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

const VOIVODESHIP_LIST = [
  'dolnośląskie',
  'kujawsko-pomorskie',
  'lubelskie',
  'lubuskie',
  'łódzkie',
  'małopolskie',
  'mazowieckie',
  'opolskie',
  'podkarpackie',
  'podlaskie',
  'pomorskie',
  'śląskie',
  'świętokrzyskie',
  'warmińsko-mazurskie',
  'wielkopolskie',
  'zachodniopomorskie',
];

// Pre-calculate canonical voivodeship groups and dictionary lookup statically outside component
const VOIVODESHIP_GROUPS: Array<[string, QuizPowiat[]]> = VOIVODESHIP_LIST.map((v) => [
  v,
  (POWIAT_CATALOG as QuizPowiat[]).filter((p) => p.voivodeship.toLowerCase() === v),
]);

const ACTIVE_POOL: QuizPowiat[] = VOIVODESHIP_GROUPS.flatMap(([, items]) => items);
const TOTAL_COUNT = ACTIVE_POOL.length;

const ID_TO_INDEX = new Map<number, number>();
ACTIVE_POOL.forEach((p, idx) => ID_TO_INDEX.set(p.id, idx + 1));

const ACCEPTED_FORMS_BY_ID = new Map<number, string[]>();
ACTIVE_POOL.forEach((p) => ACCEPTED_FORMS_BY_ID.set(p.id, getAcceptedForms(p)));

const NAME_TO_IDS = new Map<string, number[]>();
ACTIVE_POOL.forEach((p) => {
  for (const form of getAcceptedForms(p)) {
    const list = NAME_TO_IDS.get(form) || [];
    list.push(p.id);
    NAME_TO_IDS.set(form, list);
  }
});

// Memoized Shield Cell Component — only re-renders when its own targeted/guessed state changes!
interface ShieldCellProps {
  powiat: QuizPowiat;
  isGuessed: boolean;
  isRevealedMissed: boolean;
  isTargeted: boolean;
  onSelect: (id: number) => void;
  onInspect: (id: number) => void;
  setRef: (id: number, el: HTMLButtonElement | null) => void;
  isPl: boolean;
}

const ShieldCell = React.memo(function ShieldCell({
  powiat,
  isGuessed,
  isRevealedMissed,
  isTargeted,
  onSelect,
  onInspect,
  setRef,
  isPl,
}: ShieldCellProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const thumbUrl = `/coats/${powiat.id}.png`;

  return (
    <div className="group flex flex-col items-center select-none">
      {/* Click the coat of arms itself to open fullscreen inspection */}
      <div
        role="button"
        tabIndex={-1}
        onClick={() => onInspect(powiat.id)}
        aria-label={isPl ? 'Powiększ herb' : 'Fullscreen coat of arms'}
        className="relative flex h-32 w-32 sm:h-36 sm:w-36 items-center justify-center rounded-lg p-2 cursor-zoom-in transition-transform duration-100 group-hover:scale-[1.03]"
      >
        {!loaded && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-zinc-500 font-mono text-[10px] animate-pulse">
            <Loader2 className="animate-spin text-emerald-400/60" size={20} />
            <span>{isPl ? 'Ładowanie...' : 'Loading...'}</span>
          </div>
        )}
        <img
          src={thumbUrl}
          alt={isGuessed || isRevealedMissed ? powiat.name : isPl ? 'Herb powiatu' : 'Coat of arms'}
          width={128}
          height={140}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => {
            setError(true);
            setLoaded(true);
          }}
          className={`max-h-28 max-w-28 sm:max-h-32 sm:max-w-32 w-auto h-auto object-contain pointer-events-none select-none drop-shadow-md transition-opacity duration-200 ${
            loaded ? 'opacity-100' : 'opacity-0'
          }`}
        />

        <span
          aria-hidden="true"
          className="pointer-events-none absolute bottom-1 right-1 inline-flex h-6 w-6 items-center justify-center rounded bg-obsidian-950/85 border border-white/15 text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Maximize2 size={12} />
        </span>
      </div>

      {/* Answer box under the coat: click to select, Tab / Shift+Tab to move */}
      {/* Answer box under the coat: clean JetPunk style with just the name */}
      <div className="mt-2 w-full max-w-[210px]">
        {isGuessed || isRevealedMissed ? (
          <div
            className={`flex h-9 items-center justify-center rounded border px-2 text-center text-xs font-bold leading-tight ${
              isGuessed
                ? 'border-emerald-500/60 bg-emerald-950/50 text-emerald-200'
                : 'border-rose-500/50 bg-rose-950/40 text-rose-200'
            }`}
            title={powiat.name}
          >
            <span className="truncate">{powiat.name.replace(/\s*\([^)]*\)/g, '')}</span>
          </div>
        ) : (
          <button
            ref={(el) => setRef(powiat.id, el)}
            type="button"
            onClick={() => onSelect(powiat.id)}
            aria-label={isPl ? 'Wybierz herb' : 'Select coat of arms'}
            className={`flex h-9 w-full items-center justify-center rounded border px-2 text-center font-mono text-xs transition-colors cursor-pointer ${
              isTargeted
                ? 'border-emerald-400 bg-emerald-500/15 ring-2 ring-emerald-400/40 shadow-md'
                : 'border-white/15 bg-obsidian-950/80 hover:border-white/35'
            }`}
          />
        )}
      </div>
    </div>
  );
});

export default function PowiatCoatsQuizPage() {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  // Gameplay state
  const [guessedIds, setGuessedIds] = useState<Set<number>>(() => new Set());
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isGivenUp, setIsGivenUp] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [inputVal, setInputVal] = useState<string>('');
  const [targetedId, setTargetedId] = useState<number | null>(() => ACTIVE_POOL[0]?.id ?? null);
  const [lastSolvedLabel, setLastSolvedLabel] = useState<string | null>(null);

  // Fullscreen inspector state
  const [inspectedId, setInspectedId] = useState<number | null>(null);
  const [modalImgLoaded, setModalImgLoaded] = useState<boolean>(false);
  const [inspectZoom, setInspectZoom] = useState<number>(1);

  const headerInputRef = useRef<HTMLInputElement>(null);
  const slotRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  const guessedCount = guessedIds.size;
  const isCompleted = TOTAL_COUNT > 0 && guessedCount === TOTAL_COUNT;

  // Stopwatch timer
  useEffect(() => {
    if (!isRunning || isPaused || isGivenUp || isCompleted) return;
    const interval = window.setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [isRunning, isPaused, isGivenUp, isCompleted]);
  // On start: focus the top input box automatically
  useEffect(() => {
    headerInputRef.current?.focus();
  }, []);


  const setSlotRef = useCallback((id: number, el: HTMLButtonElement | null) => {
    if (el) slotRefs.current.set(id, el);
    else slotRefs.current.delete(id);
  }, []);

  // Selection function that does NOT scroll if already in view, and uses instant scroll if not
  const selectShieldSlot = useCallback((powiatId: number | null) => {
    setTargetedId(powiatId);
    setInputVal('');

    // Focus input synchronously
    headerInputRef.current?.focus();

    if (powiatId === null) return;

    // Check if element is already in viewport below sticky headers (56px/80px site header + ~70px quiz header)
    const el = slotRefs.current.get(powiatId);
    if (el) {
      const rect = el.getBoundingClientRect();
      const headerBuffer = window.innerWidth >= 1280 ? 175 : 150;
      const inView = rect.top >= headerBuffer && rect.bottom <= (window.innerHeight - 20);
      if (!inView) {
        if (rect.top < headerBuffer) {
          window.scrollBy({ top: rect.top - headerBuffer - 16, behavior: 'auto' });
        } else {
          el.scrollIntoView({ block: 'nearest', behavior: 'auto' });
        }
      }
    }
  }, []);
  const handleCloseInspect = useCallback(() => {
    const closedId = inspectedId;
    setInspectedId(null);
    if (closedId !== null && !guessedIds.has(closedId) && !isGivenUp) {
      selectShieldSlot(closedId);
    } else {
      headerInputRef.current?.focus();
    }
  }, [inspectedId, guessedIds, isGivenUp, selectShieldSlot]);

  // Close inspector on Escape and auto-focus input
  useEffect(() => {
    if (inspectedId === null) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseInspect();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [inspectedId, handleCloseInspect]);

  // Instant navigation forward / backward among unguessed coats of arms
  const selectRelativeUnguessed = useCallback(
    (fromId: number | null, direction: 1 | -1, nextGuessedSet?: Set<number>) => {
      const solvedSet = nextGuessedSet || guessedIds;
      if (solvedSet.size >= TOTAL_COUNT) {
        setTargetedId(null);
        return;
      }

      if (fromId === null) {
        const first = ACTIVE_POOL.find((p) => !solvedSet.has(p.id));
        if (first) selectShieldSlot(first.id);
        return;
      }

      const currentIdx = ACTIVE_POOL.findIndex((p) => p.id === fromId);
      if (currentIdx === -1) {
        const first = ACTIVE_POOL.find((p) => !solvedSet.has(p.id));
        if (first) selectShieldSlot(first.id);
        return;
      }

      for (let step = 1; step <= ACTIVE_POOL.length; step++) {
        const idx = (currentIdx + direction * step + ACTIVE_POOL.length) % ACTIVE_POOL.length;
        const candidate = ACTIVE_POOL[idx];
        if (!solvedSet.has(candidate.id)) {
          selectShieldSlot(candidate.id);
          return;
        }
      }
    },
    [guessedIds, selectShieldSlot]
  );

  const handleResetQuiz = useCallback(() => {
    setGuessedIds(new Set());
    setInputVal('');
    setIsGivenUp(false);
    setIsPaused(false);
    setIsRunning(false);
    setElapsedSeconds(0);
    setTargetedId(ACTIVE_POOL[0]?.id ?? null);
    setLastSolvedLabel(null);
    headerInputRef.current?.focus();
  }, []);

  // 100% Client-side evaluation — instant O(1) hash map lookup
  const handleHeaderInputChange = (raw: string) => {
    setInputVal(raw);
    if (isGivenUp || isCompleted) return;

    const clean = normalizeQuizText(raw);
    if (clean.length < 2) return;

    if (!isRunning) {
      setIsRunning(true);
      setIsPaused(false);
    }

    // 1. If a specific answer box is targeted, check only that shield
    if (targetedId !== null && !guessedIds.has(targetedId)) {
      const forms = ACCEPTED_FORMS_BY_ID.get(targetedId) || [];
      if (forms.includes(clean)) {
        const solved = ACTIVE_POOL.find((p) => p.id === targetedId);
        const next = new Set(guessedIds);
        next.add(targetedId);
        setGuessedIds(next);
        setInputVal('');
        setLastSolvedLabel(solved?.name || null);
        selectRelativeUnguessed(targetedId, 1, next);
      }
      return;
    }

    // 2. Otherwise instant dictionary match across all unguessed counties
    const candidateIds = NAME_TO_IDS.get(clean);
    if (candidateIds && candidateIds.length > 0) {
      const newlyMatched = candidateIds.filter((id) => !guessedIds.has(id));
      if (newlyMatched.length > 0) {
        const next = new Set(guessedIds);
        newlyMatched.forEach((id) => next.add(id));
        setGuessedIds(next);
        setInputVal('');
        const firstSolved = ACTIVE_POOL.find((p) => p.id === newlyMatched[0]);
        setLastSolvedLabel(
          newlyMatched.length === 1
            ? firstSolved?.name || null
            : `${firstSolved?.name} (×${newlyMatched.length})`
        );
      }
    }
  };

  const handleHeaderKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Tab' && !isGivenUp && !isCompleted) {
      e.preventDefault();
      selectRelativeUnguessed(targetedId, e.shiftKey ? -1 : 1);
    } else if (e.key === 'Escape' && targetedId !== null) {
      setTargetedId(null);
    }
  };

  const handleInspect = useCallback((id: number) => {
    setInspectZoom(1);
    setModalImgLoaded(false);
    setInspectedId(id);
  }, []);

  const targetedPowiat = useMemo(
    () => (targetedId !== null ? ACTIVE_POOL.find((p) => p.id === targetedId) || null : null),
    [targetedId]
  );

  const inspectedPowiat = useMemo(
    () => (inspectedId !== null ? ACTIVE_POOL.find((p) => p.id === inspectedId) || null : null),
    [inspectedId]
  );

  const pct = TOTAL_COUNT > 0 ? Math.round((guessedCount / TOTAL_COUNT) * 100) : 0;

  return (
    <div className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-6 space-y-6">
      {/* Simple, Clean Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <h1 className="font-serif text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">
            {isPl ? 'Quiz: Wszystkie Herby Powiatów w Polsce' : 'Polish County Coats of Arms Quiz'}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-zinc-400">
            {isPl
              ? 'Wpisuj nazwy powiatów w górnym polu. Kliknij dowolny herb, aby go powiększyć. Kliknij pole pod herbem, aby go wybrać (Tab = następny, Shift+Tab = poprzedni).'
              : 'Type county names in the top input. Click any coat of arms for fullscreen inspection. Click a box below to select (Tab = next, Shift+Tab = previous).'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            to="/herby-powiatow"
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <Shield size={13} />
            <span>{isPl ? 'Dzienna zagadka' : 'Daily Puzzle'}</span>
          </Link>
          <Link
            to="/explore#tab=powiats"
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <Eye size={13} />
            <span>{isPl ? 'Atlas' : 'Atlas'}</span>
          </Link>
        </div>
      </header>

      {/* FAST FIXED STICKY TOP CONTROLS & INPUT */}
      <section
        aria-label={isPl ? 'Pole wpisywania i wynik' : 'Input and Scoreboard'}
        className="sticky top-14 xl:top-20 z-40 rounded-b-lg border border-emerald-500/40 bg-obsidian-950/98 px-4 py-3 shadow-2xl backdrop-blur-md space-y-2.5"
      >
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Main Top Input Field */}
          <div className="relative flex-1">
            <input
              ref={headerInputRef}
              type="text"
              autoFocus
              value={inputVal}
              disabled={isGivenUp || isCompleted || isPaused}
              onChange={(e) => handleHeaderInputChange(e.target.value)}
              onKeyDown={handleHeaderKeyDown}
              placeholder={
                isPaused
                  ? isPl
                    ? 'Quiz wstrzymany — kliknij Wznów...'
                    : 'Quiz paused — click Resume...'
                  : targetedPowiat
                  ? isPl
                    ? `Wybrany herb (${targetedPowiat.voivodeship}) — wpisz powiat (Tab = następny, Shift+Tab = poprzedni)...`
                    : `Selected coat (${targetedPowiat.voivodeship}) — type county (Tab = next, Shift+Tab = prev)...`
                  : isPl
                  ? 'Wpisz nazwę powiatu lub kliknij pole pod herbem (Tab = następny, Shift+Tab = poprzedni)...'
                  : 'Type county name or click box under any shield (Tab = next, Shift+Tab = prev)...'
              }
              className="w-full rounded-md border border-emerald-500/50 bg-obsidian-900 px-3.5 py-2 text-sm font-medium text-sand-100 placeholder-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/25"
            />
            {inputVal && (
              <button
                type="button"
                onClick={() => {
                  setInputVal('');
                  headerInputRef.current?.focus();
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white cursor-pointer"
              >
                <X size={15} />
              </button>
            )}
          </div>

          {/* Quick Score, Stopwatch & Controls */}
          <div className="flex flex-wrap items-center justify-between md:justify-end gap-2">
            {lastSolvedLabel && (
              <span className="hidden xl:inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs font-mono text-emerald-300">
                <Check size={12} />
                <span className="truncate max-w-[150px]">{lastSolvedLabel.replace(/\s*\([^)]*\)/g, '')}</span>
              </span>
            )}

            <div className="flex items-center gap-2 rounded-md border border-white/15 bg-obsidian-900 px-3 py-1.5 font-mono">
              <Trophy size={15} className="text-emerald-400 shrink-0" />
              <span className="text-base font-extrabold text-emerald-400">
                {guessedCount}
              </span>
              <span className="text-xs text-zinc-400">/ {TOTAL_COUNT}</span>
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[11px] font-bold text-emerald-300">
                {pct}%
              </span>
            </div>

            <div className="flex items-center gap-1.5 rounded-md border border-white/15 bg-obsidian-900 px-3 py-1.5 font-mono text-sm text-sand-100">
              <span>⏱</span>
              <span className="font-bold">{formatTime(elapsedSeconds)}</span>
            </div>

            {!isGivenUp && !isCompleted && (
              <button
                type="button"
                onClick={() => {
                  if (!isRunning) {
                    setIsRunning(true);
                    setIsPaused(false);
                    const first = ACTIVE_POOL.find((p) => !guessedIds.has(p.id));
                    if (first) selectShieldSlot(first.id);
                  } else {
                    setIsPaused((p) => !p);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-md bg-emerald-400 px-3.5 py-1.5 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 cursor-pointer"
              >
                {!isRunning || isPaused ? <Play size={14} /> : <Pause size={14} />}
                <span>
                  {!isRunning
                    ? 'Start'
                    : isPaused
                    ? isPl
                      ? 'Wznów'
                      : 'Resume'
                    : isPl
                    ? 'Pauza'
                    : 'Pause'}
                </span>
              </button>
            )}

            {!isGivenUp && !isCompleted && (
              <button
                type="button"
                onClick={() => {
                  setIsGivenUp(true);
                  setIsRunning(false);
                  setTargetedId(null);
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/35 bg-rose-950/40 px-3 py-1.5 text-xs font-semibold text-rose-200 hover:bg-rose-900/50 cursor-pointer"
              >
                <Flag size={13} />
                <span>{isPl ? 'Poddaj się' : 'Give Up'}</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleResetQuiz}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-semibold text-sand-200 hover:border-emerald-400/50 cursor-pointer"
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>
          </div>
        </div>

        <div className="h-1.5 w-full overflow-hidden rounded-full bg-obsidian-900">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
      </section>

      {/* Completion or Give-Up Summary Banner */}
      {(isCompleted || isGivenUp) && (
        <div
          className={`flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4 ${
            isCompleted
              ? 'border-emerald-500/40 bg-emerald-950/30 text-emerald-200'
              : 'border-amber-500/40 bg-amber-950/25 text-amber-200'
          }`}
        >
          <div className="space-y-1">
            <h2 className="font-serif text-lg font-bold">
              {isCompleted
                ? isPl
                  ? `Gratulacje! Odgadłeś wszystkie ${TOTAL_COUNT} herbów w czasie ${formatTime(elapsedSeconds)}!`
                  : `Congratulations! You solved all ${TOTAL_COUNT} coats of arms in ${formatTime(elapsedSeconds)}!`
                : isPl
                ? `Koniec quizu — odgadnięto ${guessedCount} z ${TOTAL_COUNT} herbów (${pct}%) w czasie ${formatTime(elapsedSeconds)}.`
                : `Quiz ended — you solved ${guessedCount} of ${TOTAL_COUNT} coats of arms (${pct}%) in ${formatTime(elapsedSeconds)}.`}
            </h2>
            <p className="text-xs text-zinc-300">
              {isPl
                ? 'Wszystkie brakujące nazwy zostały odsłonięte na siatce poniżej. Kliknij dowolny herb, aby powiększyć go na pełny ekran.'
                : 'All missed county names are now revealed below. Click any coat of arms for fullscreen inspection.'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleResetQuiz}
            className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 cursor-pointer"
          >
            <RotateCcw size={14} />
            <span>{isPl ? 'Zagraj ponownie' : 'Play Again'}</span>
          </button>
        </div>
      )}

      {/* COATS OF ARMS ORGANIZED BY 16 VOIVODESHIPS */}
      <div className="space-y-10">
        {VOIVODESHIP_GROUPS.map(([voiv, items]) => {
          const voivSolved = items.filter((p) => guessedIds.has(p.id)).length;
          return (
            <section key={voiv} className="space-y-4">
              <div className="flex items-center justify-between border-b border-white/15 pb-2">
                <h2 className="font-serif text-xl sm:text-2xl font-bold capitalize text-sand-100">
                  Województwo {voiv}
                </h2>
                <span className="rounded bg-white/5 border border-white/10 px-2.5 py-0.5 font-mono text-xs text-emerald-400 font-bold">
                  {voivSolved} / {items.length}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {items.map((p) => (
                  <ShieldCell
                    key={p.id}
                    powiat={p}
                    isGuessed={guessedIds.has(p.id)}
                    isRevealedMissed={!guessedIds.has(p.id) && isGivenUp}
                    isTargeted={targetedId === p.id && !guessedIds.has(p.id) && !isGivenUp}
                    onSelect={selectShieldSlot}
                    onInspect={handleInspect}
                    setRef={setSlotRef}
                    isPl={isPl}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>

      {/* Fullscreen Coat of Arms Detail Inspector */}
      {inspectedPowiat && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-label={isPl ? 'Podgląd herbu' : 'Coat of arms preview'}
          onClick={handleCloseInspect}
          className="fixed inset-0 z-[2200] flex flex-col bg-obsidian-950/95 backdrop-blur-md select-none"
        >
          {/* Top Toolbar */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-obsidian-900/90 px-4 py-3 sm:px-6 shrink-0"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Shield size={16} className="text-emerald-400 shrink-0" />
              <span className="font-serif text-sm font-bold text-sand-100 truncate">
                {guessedIds.has(inspectedPowiat.id) || isGivenUp
                  ? inspectedPowiat.name
                  : isPl
                  ? 'Herb powiatu'
                  : 'County coat of arms'}
              </span>
              <span className="font-mono text-xs text-zinc-400">
                • woj. {inspectedPowiat.voivodeship}
              </span>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                disabled={inspectZoom <= 1}
                className="inline-flex items-center justify-center rounded border border-white/15 bg-obsidian-950 p-1.5 text-zinc-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ZoomOut size={15} />
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom(1)}
                className="rounded border border-white/15 bg-obsidian-950 px-2 py-1 font-mono text-xs text-sand-200 cursor-pointer"
              >
                {Math.round(inspectZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                disabled={inspectZoom >= 3}
                className="inline-flex items-center justify-center rounded border border-white/15 bg-obsidian-950 p-1.5 text-zinc-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ZoomIn size={15} />
              </button>
              <button
                type="button"
                onClick={handleCloseInspect}
                className="inline-flex items-center gap-1 rounded border border-white/20 bg-white/10 px-2.5 py-1 text-xs font-semibold text-sand-100 hover:bg-rose-500/20 hover:text-rose-200 cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Perfectly Centered Shield Canvas */}
          <div
            onClick={handleCloseInspect}
            className="flex-1 overflow-auto flex items-center justify-center p-4 sm:p-8"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="relative flex items-center justify-center rounded-2xl border border-white/15 bg-obsidian-900/95 shadow-2xl shadow-black/80 p-6 sm:p-10 transition-colors duration-200"
            >
              {/* Instant Cached Preview Image (Displays immediately with 0ms wait!) */}
              <img
                src={`/coats/${inspectedPowiat.id}.png`}
                alt=""
                aria-hidden="true"
                style={{
                  height: `${Math.round(68 * inspectZoom)}vh`,
                  maxHeight: `${Math.round(68 * inspectZoom)}vh`,
                  width: 'auto',
                }}
                className={`max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-opacity duration-200 ${
                  modalImgLoaded ? 'opacity-0 pointer-events-none' : 'opacity-100'
                }`}
              />

              {/* High-Resolution Vector SVG (Fades in over preview once loaded in background) */}
              <img
                src={`/api/explore/powiats/${inspectedPowiat.id}/coat?v=2`}
                alt={
                  guessedIds.has(inspectedPowiat.id) || isGivenUp
                    ? inspectedPowiat.name
                    : 'Coat of arms'
                }
                onLoad={() => setModalImgLoaded(true)}
                onError={() => setModalImgLoaded(true)}
                style={{
                  height: `${Math.round(68 * inspectZoom)}vh`,
                  maxHeight: `${Math.round(68 * inspectZoom)}vh`,
                  width: 'auto',
                }}
                className={`max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-opacity duration-200 ${
                  modalImgLoaded ? 'opacity-100' : 'opacity-0'
                } absolute`}
              />
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
