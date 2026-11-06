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
import POWIAT_CATALOG from '../data/powiats_quiz_catalog.json';
import COAT_THUMBNAILS from '../data/coat_thumbnails.json';
import { API_URL, coatsQuizService, countyFlagsQuizService, countyFlagsService, regionalSymbolsService, regionalSymbolLabels, regionalSymbolNouns, type CoatsQuizSolve, type CoatsQuizStats } from '../services/api';
import { countyFlagQuizCatalog } from '../lib/countyFlagCatalog';
import RegionalGeographyCredit from '../components/RegionalGeographyCredit';
import { isPrerenderCapture } from '../lib/pageMetadata';
import SymbolComponentCredits from '../components/SymbolComponentCredits';
import type { PowiatHeraldrySourceAttribution, RegionalSymbolScope } from '../types';

interface QuizPowiat {
  id: number;
  name: string;
  voivodeship: string;
  is_city_county: boolean;
  seat: string | null;
  population: number | null;
  area_km2: number | null;
  registration_plates: string[];
  flag_asset_url?: string;
  thumbnail_asset_url?: string;
  aliases?: string[];
  source_attribution?: PowiatHeraldrySourceAttribution | null;
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

function normalizeRegionalText(str: string): string {
  return str.toLowerCase().replace(/ł/g, 'l').normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '').replace(/[-–]/g, ' ').replace(/\s+/g, ' ').trim();
}

function getAcceptedForms(p: QuizPowiat, regional: boolean): string[] {
  const rawCandidates = regional ? [p.name, ...(p.aliases || [])] : [p.name, p.name.replace(/\s*\([^)]*\)/g, '').trim(), ...(p.aliases || [])];
  const forms = new Set<string>();
  for (const cand of rawCandidates) {
    const full = regional ? normalizeRegionalText(cand) : normalizeQuizText(cand);
    if (!full) continue;
    forms.add(full);
    if (regional) continue;
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

function makeQuizIndex(catalog: QuizPowiat[], scope?: RegionalSymbolScope) {
  const groups: Array<[string, QuizPowiat[]]> = scope
    ? [[regionalSymbolLabels[scope], catalog]]
    : VOIVODESHIP_LIST.map((v) => [v, catalog.filter((p) => p.voivodeship.toLowerCase() === v)]);
  const pool = groups.flatMap(([, items]) => items);
  const forms = new Map<number, string[]>();
  const names = new Map<string, number[]>();
  pool.forEach((p) => {
    const accepted = getAcceptedForms(p, Boolean(scope));
    forms.set(p.id, accepted);
    for (const form of accepted) names.set(form, [...(names.get(form) || []), p.id]);
  });
  return { groups, pool, forms, names };
}

function assetUrl(url: string): string {
  return url.startsWith('/') ? `${API_URL.replace(/\/$/, '')}${url.replace(/^\/api(?=\/)/, '')}` : url;
}

function flagUrl(powiat: QuizPowiat): string {
  return assetUrl(powiat.flag_asset_url || '');
}

function thumbnailUrl(powiat: QuizPowiat): string {
  return powiat.thumbnail_asset_url ? assetUrl(powiat.thumbnail_asset_url)
    : powiat.flag_asset_url ? flagUrl(powiat) : (COAT_THUMBNAILS as Record<string, string>)[String(powiat.id)] || `/coats/${powiat.id}.png`;
}

// Memoized Shield Cell Component — only re-renders when its own targeted/guessed state changes!
interface ShieldCellProps {
  powiat: QuizPowiat;
  isGuessed: boolean;
  isRevealedMissed: boolean;
  isTargeted: boolean;
  onSelect: (id: number) => void;
  onInspect: (id: number, trigger: HTMLElement) => void;
  setRef: (id: number, el: HTMLButtonElement | null) => void;
  flags: boolean;
  regional: boolean;
}

const ShieldCell = React.memo(function ShieldCell({
  powiat,
  isGuessed,
  isRevealedMissed,
  isTargeted,
  onSelect,
  onInspect,
  flags,
  regional,
  setRef,
}: ShieldCellProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [usingOriginal, setUsingOriginal] = useState(false);
  const thumbUrl = thumbnailUrl(powiat);

  return (
    <div className="group flex flex-col items-center select-none">
      {/* Click the coat of arms itself to open fullscreen inspection */}
      <div
        role="button"
        tabIndex={0}
        onClick={(event) => onInspect(powiat.id, event.currentTarget)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onInspect(powiat.id, event.currentTarget);
          }
        }}
        aria-label={flags ? 'Fullscreen flag' : 'Fullscreen coat of arms'}
        className="relative flex h-28 w-28 sm:h-36 sm:w-36 items-center justify-center rounded-lg p-1.5 sm:p-2 cursor-zoom-in"
      >
        {!loaded && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-zinc-500 font-mono text-[10px]">
            <Loader2 className="animate-spin text-emerald-400/60" size={20} />
            <span>{'Loading...'}</span>
          </div>
        )}
        {error && <span role="alert" className="text-xs text-rose-300">Image unavailable</span>}
        <img
          src={usingOriginal ? (powiat.flag_asset_url ? flagUrl(powiat) : `/coats/${powiat.id}.png`) : thumbUrl}
          alt={isGuessed || isRevealedMissed ? powiat.name : flags ? regional ? 'Flag' : 'County flag' : 'Coat of arms'}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => {
            const original = powiat.flag_asset_url ? flagUrl(powiat) : `/coats/${powiat.id}.png`;
            if (!usingOriginal && thumbUrl !== original) {
              setUsingOriginal(true);
            } else {
              setError(true);
              setLoaded(true);
            }
          }}
          className={`max-h-24 max-w-24 sm:max-h-32 sm:max-w-32 w-auto h-auto object-contain pointer-events-none select-none drop-shadow-md transition-opacity duration-200 ${
            loaded && !error ? 'opacity-100' : 'opacity-0'
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
      <div className="mt-1.5 sm:mt-2 w-full max-w-[210px]">
        {isGuessed || isRevealedMissed ? (
          <div
            className={`flex min-h-[38px] sm:min-h-[44px] items-center justify-center rounded border px-1.5 sm:px-2 py-1 text-center text-[11px] sm:text-xs font-semibold leading-tight ${
              isGuessed
                ? 'border-emerald-500/60 bg-emerald-950/50 text-emerald-200'
                : 'border-rose-500/50 bg-rose-950/40 text-rose-200'
            }`}
            title={powiat.name}
          >
            <span className="break-words line-clamp-2">{powiat.name.replace(/\s*\([^)]*\)/g, '')}</span>
          </div>
        ) : (
          <button
            ref={(el) => setRef(powiat.id, el)}
            type="button"
            onClick={() => onSelect(powiat.id)}
            aria-label={flags ? 'Select flag' : 'Select coat of arms'}
            className={`flex min-h-[44px] w-full items-center justify-center rounded border px-1.5 sm:px-2 text-center font-mono text-xs transition-colors cursor-pointer ${
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

export default function PowiatCoatsQuizPage({ flags = false, scope }: { flags?: boolean; scope?: RegionalSymbolScope }) {
  if (scope && isPrerenderCapture()) return <h1>{regionalSymbolLabels[scope]} {flags ? 'Flags' : 'Coats of Arms'} Quiz</h1>;
  return <CountyQuizLoader key={`${scope ?? 'counties'}-${flags}`} flags={flags} scope={scope} />;
}

function CountyQuizLoader({ flags, scope }: { flags: boolean; scope?: RegionalSymbolScope }) {
  const [catalog, setCatalog] = useState<QuizPowiat[] | null>(flags || scope ? null : POWIAT_CATALOG as QuizPowiat[]);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if ((!flags && !scope) || (scope && isPrerenderCapture())) return;
    let active = true;
    const request: Promise<QuizPowiat[]> = scope
      ? regionalSymbolsService(scope, flags).getCatalog().then((entries) =>
          entries.map((entry) => ({ ...entry, is_city_county: false, seat: null, population: null, area_km2: null, registration_plates: [] })))
      : countyFlagsService.getCatalog().then((entries) => {
          const joined = countyFlagQuizCatalog(entries, POWIAT_CATALOG as QuizPowiat[]);
          if (joined.length !== entries.length) throw new Error('Incomplete county flag catalog');
          return joined;
        });
    request.then((joined) => {
      if (!active) return;
      if (!joined.length) setError(true);
      else setCatalog(joined);
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [flags, scope, attempt]);
  if (error) return <p role="alert" className="p-8 text-rose-300">The verified {scope ? 'symbol' : 'county flag'} catalog is unavailable. <button type="button" className="underline" onClick={() => { setError(false); setAttempt((n) => n + 1); }}>Retry</button></p>;
  if (!catalog) return <p role="status" className="p-8">Loading verified {scope ? 'symbols' : 'county flags'}…</p>;
  return <CountyQuiz flags={flags} scope={scope} catalog={catalog} />;
}

function CountyQuiz({ flags, scope, catalog }: { flags: boolean; scope?: RegionalSymbolScope; catalog: QuizPowiat[] }) {
  const { groups: VOIVODESHIP_GROUPS, pool: ACTIVE_POOL, forms: ACCEPTED_FORMS_BY_ID, names: NAME_TO_IDS } = useMemo(() => makeQuizIndex(catalog, scope), [catalog, scope]);
  const TOTAL_COUNT = ACTIVE_POOL.length;
  const quizService = useMemo(() => scope ? regionalSymbolsService(scope, flags).quiz : flags ? countyFlagsQuizService : coatsQuizService, [scope, flags]);
  const label = scope ? regionalSymbolLabels[scope] : 'Polish County';
  const noun = scope ? regionalSymbolNouns[scope] : 'county';
  const regionalPath = scope ? `/regional-symbols/${scope}/${flags ? 'flag' : 'coat'}` : null;

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
  const [modalImgError, setModalImgError] = useState(false);
  const [inspectZoom, setInspectZoom] = useState<number>(1);

  const headerInputRef = useRef<HTMLInputElement>(null);
  const inspectorRef = useRef<HTMLDivElement>(null);
  const inspectorTriggerRef = useRef<HTMLElement | null>(null);
  const slotRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const runRef = useRef<{ start: Promise<{ run_id: string }> | null; startFailed: boolean; solves: CoatsQuizSolve[]; result: { status: 'completed' | 'given_up'; elapsed_seconds: number; solves: CoatsQuizSolve[] } | null }>({ start: null, startFailed: false, solves: [], result: null });
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [community, setCommunity] = useState<CoatsQuizStats | null>(null);
  const [communityState, setCommunityState] = useState<'loading' | 'ready' | 'error'>('loading');
  const statsRequest = useRef(0);
  const loadCommunity = useCallback(() => {
    const request = ++statsRequest.current;
    setCommunityState('loading');
    quizService.stats().then((stats) => {
      if (request === statsRequest.current) { setCommunity(stats); setCommunityState('ready'); }
    }).catch(() => {
      if (request === statsRequest.current) setCommunityState('error');
    });
  }, [quizService]);
  useEffect(() => {
    loadCommunity();
    return () => { statsRequest.current++; };
  }, [loadCommunity]);
  const beginRun = () => {
    const run = runRef.current;
    if (!run.start && !run.startFailed) {
      const start = quizService.start();
      run.start = start;
      start.catch(() => {
        if (run.start === start) { run.start = null; run.startFailed = true; }
      });
    }
  };
  const saveRun = (run: typeof runRef.current, retry = false) => {
    if (!run.result) return;
    if (run.startFailed && !retry) { setSaveState('error'); return; }
    if (retry) run.startFailed = false;
    setSaveState('saving');
    const start = run.start ?? quizService.start();
    run.start = start;
    start.catch(() => {
      if (run.start === start) { run.start = null; run.startFailed = true; }
    });
    start.then(({ run_id }) => quizService.finish(run_id, run.result!)).then(() => {
      if (runRef.current === run) { setSaveState('saved'); loadCommunity(); }
    }).catch(() => {
      if (runRef.current === run) setSaveState('error');
    });
  };
  const finishRun = (status: 'completed' | 'given_up') => {
    const run = runRef.current;
    run.result = { status, elapsed_seconds: elapsedSeconds, solves: [...run.solves] };
    saveRun(run);
  };
  const recordSolve = (ids: number[], answer: string, completed: boolean) => {
    runRef.current.solves.push({ powiat_ids: ids, answer, elapsed_seconds: elapsedSeconds });
    if (completed) finishRun('completed');
  };

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
      const headerBuffer = window.innerWidth >= 1280 ? 175 : window.innerWidth < 640 ? 210 : 160;
      const inView = rect.top >= headerBuffer && rect.bottom <= (window.innerHeight - 20);
      if (!inView) {
        if (rect.top < headerBuffer) {
          window.scrollBy({ top: rect.top - headerBuffer - 12, behavior: 'auto' });
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
    if (inspectorTriggerRef.current?.isConnected) inspectorTriggerRef.current.focus();
  }, [inspectedId, guessedIds, isGivenUp, selectShieldSlot]);

  // Place keyboard focus in the inspector and keep it there until it closes.
  useEffect(() => {
    if (inspectedId !== null) inspectorRef.current?.querySelector<HTMLButtonElement>('[aria-label="Close"]')?.focus();
  }, [inspectedId]);

  // Close inspector on Escape and keep Tab within its controls.
  useEffect(() => {
    if (inspectedId === null) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseInspect();
      } else if (e.key === 'Tab' && inspectorRef.current) {
        const controls = Array.from(inspectorRef.current.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), [tabindex]:not([tabindex="-1"])'));
        if (!controls.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (e.shiftKey && (document.activeElement === first || !inspectorRef.current.contains(document.activeElement))) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || !inspectorRef.current.contains(document.activeElement))) {
          e.preventDefault();
          first.focus();
        }
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
    [guessedIds, selectShieldSlot, ACTIVE_POOL, TOTAL_COUNT]
  );

  const handleResetQuiz = useCallback(() => {
    runRef.current = { start: null, startFailed: false, solves: [], result: null };
    setSaveState('idle');
    setGuessedIds(new Set());
    setInputVal('');
    setIsGivenUp(false);
    setIsPaused(false);
    setIsRunning(false);
    setElapsedSeconds(0);
    setTargetedId(ACTIVE_POOL[0]?.id ?? null);
    setLastSolvedLabel(null);
    headerInputRef.current?.focus();
  }, [ACTIVE_POOL]);

  // 100% Client-side evaluation — instant O(1) hash map lookup
  const handleHeaderInputChange = (raw: string) => {
    setInputVal(raw);
    if (isGivenUp || isCompleted) return;

    const clean = scope ? normalizeRegionalText(raw) : normalizeQuizText(raw);
    if (clean.length < 2) return;

    if (!isRunning) {
      beginRun();
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
        recordSolve([targetedId], raw, next.size === TOTAL_COUNT);
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
        recordSolve(newlyMatched, raw, next.size === TOTAL_COUNT);
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

  const handleInspect = useCallback((id: number, trigger: HTMLElement) => {
    inspectorTriggerRef.current = trigger;
    setInspectZoom(1);
    setModalImgLoaded(false);
    setModalImgError(false);
    setInspectedId(id);
  }, []);

  const targetedPowiat = useMemo(
    () => (targetedId !== null ? ACTIVE_POOL.find((p) => p.id === targetedId) || null : null),
    [targetedId, ACTIVE_POOL]
  );

  const inspectedPowiat = useMemo(
    () => (inspectedId !== null ? ACTIVE_POOL.find((p) => p.id === inspectedId) || null : null),
    [inspectedId, ACTIVE_POOL]
  );

  const pct = TOTAL_COUNT > 0 ? Math.round((guessedCount / TOTAL_COUNT) * 100) : 0;

  return (
    <div className="mx-auto w-full max-w-7xl px-2.5 py-3 sm:px-6 sm:py-4 space-y-4 sm:space-y-6">
      {/* Simple, Clean Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <h1 className="font-serif text-xl sm:text-3xl font-bold tracking-tight text-sand-100">
            {`${label} ${flags ? 'Flags' : 'Coats of Arms'} Quiz`}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-zinc-400">
            {`Type ${noun} names in the top input. Click any ${flags ? 'flag' : 'coat of arms'} for fullscreen inspection. Click a box below to select (Tab = next, Shift+Tab = previous).`}
          </p>
          {scope === 'england_counties' && <p className="mt-1 text-xs text-zinc-400">{flags ? 'Community flags with historic and cultural associations to present-day ceremonial counties; historic boundaries may differ. These are not flags of modern ceremonial authority.' : 'Council arms associated with these counties; not necessarily arms of the ceremonial county or a current authority.'}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            to={regionalPath ?? (flags ? '/flagi-powiatow' : '/herby-powiatow')}
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <Shield size={13} />
            <span>{'Daily Puzzle'}</span>
          </Link>
          {!scope && <Link
            to="/explore#tab=powiats"
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <Eye size={13} />
            <span>{'Atlas'}</span>
          </Link>}
        </div>
      </header>

      {/* FAST FIXED STICKY TOP CONTROLS & INPUT */}
      <section
        aria-label={'Input and Scoreboard'}
        className="sticky top-14 xl:top-20 z-40 rounded-b-lg border border-white/10 bg-obsidian-950 px-2.5 py-1.5 sm:px-4 sm:py-3 space-y-1.5 sm:space-y-2.5"
      >
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-1.5 sm:gap-2.5 md:gap-3">
          {/* Main Top Input Field */}
          <div className="relative flex-1 min-w-0">
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
                  ? 'Paused — click Resume'
                  : targetedPowiat
                  ? scope ? `Type ${noun}...` : `Type: ${targetedPowiat.voivodeship}...`
                  : `Type ${noun}...`
              }
              className="w-full min-h-[44px] rounded-md border border-emerald-500/50 bg-obsidian-900 pl-3 pr-11 py-2 text-xs sm:text-sm font-medium text-sand-100 placeholder-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/25 truncate placeholder:truncate"
            />
            {inputVal && (
              <button
                type="button"
                onClick={() => {
                  setInputVal('');
                  headerInputRef.current?.focus();
                }}
                aria-label={'Clear input'}
                className="absolute right-0 top-0 bottom-0 flex min-h-[44px] min-w-[44px] items-center justify-center text-zinc-400 hover:text-white cursor-pointer"
              >
                <X size={15} />
              </button>
            )}
          </div>

          {/* Quick Score, Stopwatch & Controls */}
          <div className="flex items-center justify-between md:justify-end gap-1 sm:gap-2 w-full md:w-auto min-w-0">
            <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
              {lastSolvedLabel && (
                <span className="hidden xl:inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs font-mono text-emerald-300">
                  <Check size={12} />
                  <span className="truncate max-w-[150px]">{lastSolvedLabel.replace(/\s*\([^)]*\)/g, '')}</span>
                </span>
              )}

              <div
                className="flex min-h-[38px] sm:min-h-[44px] items-center gap-1 sm:gap-2 rounded-md border border-white/15 bg-obsidian-900 px-1.5 sm:px-3 font-mono shrink-0"
                title={`Guessed: ${guessedCount} of ${TOTAL_COUNT} (${pct}%)`}
              >
                <Trophy size={13} className="hidden sm:block text-emerald-400 shrink-0 sm:w-[15px] sm:h-[15px]" />
                <span className="text-xs sm:text-base font-extrabold text-emerald-400">
                  {guessedCount}
                </span>
                <span className="text-[10px] sm:text-xs text-zinc-400">/{TOTAL_COUNT}</span>
                <span className="hidden min-[380px]:inline-block rounded bg-emerald-500/15 px-1 py-0.5 text-[10px] sm:text-[11px] font-bold text-emerald-300">
                  {pct}%
                </span>
              </div>

              <div
                className="flex min-h-[38px] sm:min-h-[44px] items-center gap-1 rounded-md border border-white/15 bg-obsidian-900 px-1.5 sm:px-3 font-mono text-xs sm:text-sm text-sand-100 shrink-0"
                title={'Elapsed time'}
              >
                <span className="hidden sm:inline text-[11px] sm:text-xs">⏱</span>
                <span className="font-bold">{formatTime(elapsedSeconds)}</span>
              </div>
            </div>

            <div className="flex items-center gap-1 sm:gap-1.5 shrink-0 ml-auto md:ml-0">
              {!isGivenUp && !isCompleted && (
                <button
                  type="button"
                  onClick={() => {
                    if (!isRunning) {
                      beginRun();
                      setIsRunning(true);
                      setIsPaused(false);
                      const first = ACTIVE_POOL.find((p) => !guessedIds.has(p.id));
                      if (first) selectShieldSlot(first.id);
                    } else {
                      setIsPaused((p) => !p);
                    }
                  }}
                  aria-label={
                    !isRunning
                      ? 'Start'
                      : isPaused
                      ? 'Resume'
                      : 'Pause'
                  }
                  title={
                    !isRunning
                      ? 'Start'
                      : isPaused
                      ? 'Resume'
                      : 'Pause'
                  }
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 sm:gap-1.5 rounded-md bg-emerald-400 px-2.5 py-1.5 sm:px-3.5 sm:py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 cursor-pointer"
                >
                  {!isRunning || isPaused ? <Play size={14} className="shrink-0" /> : <Pause size={14} className="shrink-0" />}
                  <span className="hidden sm:inline">
                    {!isRunning
                      ? 'Start'
                      : isPaused
                      ? 'Resume'
                      : 'Pause'}
                  </span>
                </button>
              )}

              {!isGivenUp && !isCompleted && (
                <button
                  type="button"
                  onClick={() => {
                    finishRun('given_up');
                    setIsGivenUp(true);
                    setIsRunning(false);
                    setTargetedId(null);
                  }}
                  aria-label={'Give Up'}
                  title={'Give Up'}
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 sm:gap-1.5 rounded-md border border-rose-500/35 bg-rose-950/40 px-2.5 py-1.5 sm:px-3 sm:py-2 text-xs font-semibold text-rose-200 hover:bg-rose-900/50 cursor-pointer"
                >
                  <Flag size={13} className="shrink-0" />
                  <span className="hidden sm:inline">
                    {'Give Up'}
                  </span>
                </button>
              )}

              <button
                type="button"
                onClick={handleResetQuiz}
                aria-label={'Reset quiz'}
                title={'Reset quiz'}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 sm:gap-1.5 rounded-md border border-white/15 bg-obsidian-900 px-2.5 py-1.5 sm:px-3 sm:py-2 text-xs font-semibold text-sand-200 hover:border-emerald-400/50 cursor-pointer"
              >
                <RotateCcw size={13} className="shrink-0" />
                <span className="hidden sm:inline">Reset</span>
              </button>
            </div>
          </div>
        </div>

        <div className="h-1 sm:h-1.5 w-full overflow-hidden rounded-full bg-obsidian-900">
          <div
            className="h-full bg-emerald-500"
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
                ? `Congratulations! You solved all ${TOTAL_COUNT} ${flags ? 'flags' : 'coats of arms'} in ${formatTime(elapsedSeconds)}!`
                : `Quiz ended — you solved ${guessedCount} of ${TOTAL_COUNT} ${flags ? 'flags' : 'coats of arms'} (${pct}%) in ${formatTime(elapsedSeconds)}.`}
            </h2>
            <p className="text-xs text-zinc-300">
              {`All missed ${noun} names are now revealed below. Click any ${flags ? 'flag' : 'coat of arms'} for fullscreen inspection.`}
            </p>
          </div>
          <button
            type="button"
            onClick={handleResetQuiz}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 cursor-pointer"
          >
            <RotateCcw size={14} />
            <span>{'Play Again'}</span>
          </button>
        </div>
      )}
      <section aria-label="Community quiz statistics" className="rounded-lg border border-white/10 bg-obsidian-900 p-3 text-xs text-zinc-300 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-semibold text-sand-100">Community results</h2>
          {communityState === 'loading' && <span role="status">Loading community results…</span>}
          {communityState === 'error' && <span role="alert">Community results could not be loaded.</span>}
          {communityState === 'ready' && community?.finished_runs === 0 && <span>No finished runs tracked yet.</span>}
          {communityState === 'ready' && community && community.finished_runs > 0 && <span>{community.finished_runs} finished runs</span>}
          <button type="button" onClick={loadCommunity} className="underline">Refresh</button>
        </div>
        <details><summary className="cursor-pointer">About these results</summary><p className="mt-1">Percentages use completed and given-up runs, excluding abandoned runs. Average time is client-reported active elapsed time since quiz start among correct solves, not time spent on that {flags ? 'flag' : 'coat'}. Earlier untracked play is not included.</p></details>
        {saveState === 'saving' && <p role="status">Saving your finished run…</p>}
        {saveState === 'error' && <p role="alert">Your run could not be saved. <button type="button" className="underline" onClick={() => saveRun(runRef.current, true)}>Retry saving</button></p>}
      </section>

      {/* COATS OF ARMS ORGANIZED BY 16 VOIVODESHIPS */}
      <div className="space-y-10">
        {VOIVODESHIP_GROUPS.map(([voiv, items]) => {
          const voivSolved = items.filter((p) => guessedIds.has(p.id)).length;
          return (
            <section key={voiv} className="space-y-4">
              <div className="flex items-center justify-between border-b border-white/15 pb-2">
                <h2 className="font-serif text-xl sm:text-2xl font-bold capitalize text-sand-100">
                  {scope ? voiv : `Voivodeship ${voiv}`}
                </h2>
                <span className="rounded bg-white/5 border border-white/10 px-2.5 py-0.5 font-mono text-xs text-emerald-400 font-bold">
                  {voivSolved} / {items.length}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-6 sm:gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {items.map((p) => (
                  <ShieldCell
                    key={p.id}
                    flags={flags}
                    regional={Boolean(scope)}
                    powiat={p}
                    isGuessed={guessedIds.has(p.id)}
                    isRevealedMissed={!guessedIds.has(p.id) && isGivenUp}
                    isTargeted={targetedId === p.id && !guessedIds.has(p.id) && !isGivenUp}
                    onSelect={selectShieldSlot}
                    onInspect={handleInspect}
                    setRef={setSlotRef}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
      {scope && <RegionalGeographyCredit scope={scope} />}

      {/* Fullscreen Coat of Arms Detail Inspector */}
      {inspectedPowiat && typeof document !== 'undefined' && createPortal(
        <div
          ref={inspectorRef}
          role="dialog"
          aria-modal="true"
          aria-label={flags ? 'Flag preview' : 'Coat of arms preview'}
          onClick={handleCloseInspect}
          className="fixed inset-0 z-[2200] flex flex-col bg-obsidian-950/95 backdrop-blur-md select-none"
        >
          {/* Top Toolbar */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex items-center justify-between gap-2 border-b border-white/10 bg-obsidian-900/90 px-2 sm:px-6 py-2 shrink-0 min-h-[56px]"
          >
            <div className="flex items-center gap-2 min-w-0 flex-1 py-0.5">
              <Shield size={18} className="text-emerald-400 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="font-serif text-xs sm:text-sm font-bold text-sand-100 leading-snug break-words">
                  {guessedIds.has(inspectedPowiat.id) || isGivenUp
                    ? inspectedPowiat.name
                    : scope ? (flags ? 'Flag' : 'Coat of arms') : flags ? 'County flag' : 'County coat of arms'}
                </div>
                {!scope && <div className="font-mono text-[10px] sm:text-xs text-zinc-400 leading-tight">
                  woj. {inspectedPowiat.voivodeship}
                </div>}
                {(flags || scope) && (
                  <div aria-label={scope ? 'Symbol attribution' : 'Flag attribution'} className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-xs text-zinc-300">
                    {(inspectedPowiat.source_attribution?.author || inspectedPowiat.source_attribution?.artist) && <span>Author: {inspectedPowiat.source_attribution.author || inspectedPowiat.source_attribution.artist}</span>}
                    {inspectedPowiat.source_attribution?.source_url && <a href={inspectedPowiat.source_attribution.source_url} target="_blank" rel="noopener noreferrer" className="text-emerald-300 underline">Image source</a>}
                    {inspectedPowiat.source_attribution?.license && (inspectedPowiat.source_attribution.license_url
                      ? <a href={inspectedPowiat.source_attribution.license_url} target="_blank" rel="noopener noreferrer" className="text-emerald-300 underline">{inspectedPowiat.source_attribution.license}</a>
                      : <span>{inspectedPowiat.source_attribution.license}</span>)}
                    {inspectedPowiat.source_attribution?.description && <span>Modification: {inspectedPowiat.source_attribution.description}</span>}
                    {inspectedPowiat.source_attribution?.context && <span>Context: {inspectedPowiat.source_attribution.context}</span>}
                    {scope && <SymbolComponentCredits credits={inspectedPowiat.source_attribution?.component_credits} />}
                    {!inspectedPowiat.source_attribution && <span>Attribution unavailable</span>}
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                disabled={inspectZoom <= 1}
                aria-label={'Zoom out'}
                title={'Zoom out'}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded border border-white/15 bg-obsidian-950 p-2 text-zinc-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ZoomOut size={16} />
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom(1)}
                aria-label={'Reset zoom'}
                title={'Reset zoom'}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded border border-white/15 bg-obsidian-950 px-2 font-mono text-[11px] sm:text-xs text-sand-200 hover:border-emerald-400/50 cursor-pointer"
              >
                {Math.round(inspectZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                disabled={inspectZoom >= 3}
                aria-label={'Zoom in'}
                title={'Zoom in'}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded border border-white/15 bg-obsidian-950 p-2 text-zinc-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ZoomIn size={16} />
              </button>
              <button
                type="button"
                onClick={handleCloseInspect}
                aria-label={'Close'}
                title={'Close'}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1 rounded border border-white/20 bg-white/10 px-2.5 sm:px-3 text-xs font-semibold text-sand-100 hover:bg-rose-500/20 hover:text-rose-200 cursor-pointer"
              >
                <X size={16} />
                <span className="hidden sm:inline">{'Close'}</span>
              </button>
            </div>
          </div>

          {/* Perfectly Centered Shield Canvas */}
          <div
            onClick={handleCloseInspect}
            className="flex-1 overflow-auto flex items-center justify-center p-3 sm:p-8"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="relative flex items-center justify-center rounded-2xl border border-white/15 bg-obsidian-900/95 shadow-2xl shadow-black/80 p-4 sm:p-10 transition-colors duration-200"
            >
              {modalImgError && <p role="alert" className="absolute text-rose-300">Full-resolution image unavailable; showing preview if available.</p>}
              {/* Show the quiz rendition while the original loads. */}
              <img
                src={thumbnailUrl(inspectedPowiat)}
                alt=""
                aria-hidden="true"
                style={{
                  height: `${Math.round(68 * inspectZoom)}vh`,
                  maxHeight: `${Math.round(68 * inspectZoom)}vh`,
                  width: 'auto',
                }}
                className={`max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-opacity duration-200 ${
                  modalImgLoaded && !modalImgError ? 'opacity-0 pointer-events-none' : 'opacity-100'
                }`}
              />

              {/* High-Resolution Vector SVG (Fades in over preview once loaded in background) */}
              <img
                src={inspectedPowiat.flag_asset_url ? flagUrl(inspectedPowiat) : `/api/explore/powiats/${inspectedPowiat.id}/coat?v=2`}
                alt={
                  guessedIds.has(inspectedPowiat.id) || isGivenUp
                    ? inspectedPowiat.name
                    : flags ? scope ? 'Flag' : 'County flag' : 'Coat of arms'
                }
                onLoad={() => setModalImgLoaded(true)}
                onError={() => { setModalImgLoaded(true); setModalImgError(true); }}
                style={{
                  height: `${Math.round(68 * inspectZoom)}vh`,
                  maxHeight: `${Math.round(68 * inspectZoom)}vh`,
                  width: 'auto',
                }}
                className={`max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-opacity duration-200 ${
                  modalImgLoaded && !modalImgError ? 'opacity-100' : 'opacity-0'
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
