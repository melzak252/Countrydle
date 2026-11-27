import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Car,
  Play,
  Pause,
  RotateCcw,
  Flag,
  Check,
  X,
  Trophy,
  Eye,
  ChevronDown,
  ChevronUp,
  MapPin,
} from 'lucide-react';
import PowiatPlatesMap from '../components/PowiatPlatesMap';
import { GameResultDashboard } from '../components/result-dashboard';
import {
  buildPlatesIndex,
  formatQuizTime,
  matchPlateInput,
  normalizePlateInput,
} from '../lib/platesQuiz';
import {
  platesQuizService,
  type PlatesQuizSolve,
  type PlatesQuizStats,
} from '../services/api';

type InputFeedback =
  | { type: 'matched'; code: string; names: string[] }
  | { type: 'already_solved'; code: string }
  | { type: 'no_match'; code: string }
  | null;

export default function PowiatPlatesQuizPage() {
  const { t } = useTranslation();
  const index = useMemo(() => buildPlatesIndex(), []);
  const totalCount = index.catalog.length;

  // Gameplay state
  const [solvedIds, setSolvedIds] = useState<Set<number>>(() => new Set());
  const [lastSolvedIds, setLastSolvedIds] = useState<number[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isGivenUp, setIsGivenUp] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [inputVal, setInputVal] = useState<string>('');
  const [feedback, setFeedback] = useState<InputFeedback>(null);
  const [focusedPowiatName, setFocusedPowiatName] = useState<string | null>(null);
  const [expandedVoivodeships, setExpandedVoivodeships] = useState<Set<string>>(() => new Set());
  const [recapFilter, setRecapFilter] = useState<'missed' | 'solved' | 'all'>('missed');

  const inputRef = useRef<HTMLInputElement>(null);
  const elapsedRef = useRef<number>(0);
  elapsedRef.current = elapsedSeconds;

  const runRef = useRef<{
    start: Promise<{ run_id: string }> | null;
    startFailed: boolean;
    solves: PlatesQuizSolve[];
    result: { status: 'completed' | 'given_up'; elapsed_seconds: number; solves: PlatesQuizSolve[] } | null;
  }>({ start: null, startFailed: false, solves: [], result: null });

  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [community, setCommunity] = useState<PlatesQuizStats | null>(null);
  const [communityState, setCommunityState] = useState<'loading' | 'ready' | 'error'>('loading');
  const statsRequest = useRef(0);

  const solvedCount = solvedIds.size;
  const isCompleted = totalCount > 0 && solvedCount === totalCount;
  const pct = totalCount > 0 ? Math.round((solvedCount / totalCount) * 100) : 0;

  const loadCommunity = useCallback(() => {
    const req = ++statsRequest.current;
    setCommunityState('loading');
    platesQuizService
      .stats()
      .then((stats) => {
        if (req === statsRequest.current) {
          setCommunity(stats);
          setCommunityState('ready');
        }
      })
      .catch(() => {
        if (req === statsRequest.current) setCommunityState('error');
      });
  }, []);

  useEffect(() => {
    loadCommunity();
    return () => {
      statsRequest.current++;
    };
  }, [loadCommunity]);

  const beginRun = useCallback(() => {
    const run = runRef.current;
    if (!run.start && !run.startFailed) {
      const start = platesQuizService.start();
      run.start = start;
      start.catch(() => {
        if (run.start === start) {
          run.start = null;
          run.startFailed = true;
        }
      });
    }
  }, []);

  const saveRun = useCallback(
    (run: typeof runRef.current, retry = false) => {
      if (!run.result) return;
      if (run.startFailed && !retry) {
        setSaveState('error');
        return;
      }
      if (retry) run.startFailed = false;
      setSaveState('saving');
      const start = run.start ?? platesQuizService.start();
      run.start = start;
      start.catch(() => {
        if (run.start === start) {
          run.start = null;
          run.startFailed = true;
        }
      });
      start
        .then(({ run_id }) => platesQuizService.finish(run_id, run.result!))
        .then(() => {
          if (runRef.current === run) {
            setSaveState('saved');
            loadCommunity();
          }
        })
        .catch(() => {
          if (runRef.current === run) setSaveState('error');
        });
    },
    [loadCommunity],
  );

  const finishRun = useCallback(
    (status: 'completed' | 'given_up') => {
      const run = runRef.current;
      run.result = {
        status,
        elapsed_seconds: elapsedRef.current,
        solves: [...run.solves],
      };
      saveRun(run);
    },
    [saveRun],
  );

  // Stopwatch timer
  useEffect(() => {
    if (!isRunning || isPaused || isGivenUp || isCompleted) return;
    const interval = window.setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [isRunning, isPaused, isGivenUp, isCompleted]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const commitMatch = useCallback(
    (code: string, newlySolvedIds: number[]) => {
      if (!isRunning) {
        beginRun();
        setIsRunning(true);
        setIsPaused(false);
      }

      const nextSolved = new Set(solvedIds);
      for (const id of newlySolvedIds) {
        nextSolved.add(id);
      }
      setSolvedIds(nextSolved);
      setLastSolvedIds(newlySolvedIds);
      setInputVal('');

      const names = newlySolvedIds
        .map((id) => index.byId.get(id)?.name)
        .filter((name): name is string => Boolean(name));
      setFeedback({ type: 'matched', code, names });

      const completed = nextSolved.size === totalCount;
      runRef.current.solves.push({
        powiat_ids: newlySolvedIds,
        answer: code,
        elapsed_seconds: elapsedRef.current,
      });

      if (completed) {
        setIsRunning(false);
        finishRun('completed');
      }
    },
    [isRunning, beginRun, solvedIds, index.byId, totalCount, finishRun],
  );

  const handleInputChange = (raw: string) => {
    if (isGivenUp || isCompleted || isPaused) return;
    const upper = raw.toUpperCase().replace(/[^A-Z\s-]/g, '');
    setInputVal(upper);

    const normalized = normalizePlateInput(upper);
    if (normalized.length < 2) {
      if (feedback && feedback.type !== 'matched') setFeedback(null);
      return;
    }

    const match = matchPlateInput(normalized, solvedIds, index);
    if (match.status === 'matched') {
      commitMatch(match.code, match.newlySolvedIds);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (isGivenUp || isCompleted || isPaused) return;
    const normalized = normalizePlateInput(inputVal);
    if (!normalized) return;

    const match = matchPlateInput(normalized, solvedIds, index);
    if (match.status === 'matched') {
      commitMatch(match.code, match.newlySolvedIds);
    } else if (match.status === 'already_solved') {
      setFeedback({ type: 'already_solved', code: match.code });
      setInputVal('');
    } else {
      setFeedback({ type: 'no_match', code: match.code });
    }
  };

  const handleGiveUp = () => {
    if (isGivenUp || isCompleted) return;
    if (!runRef.current.start && !runRef.current.startFailed) {
      beginRun();
    }
    setIsGivenUp(true);
    setIsRunning(false);
    setIsPaused(false);
    setRecapFilter('missed');
    finishRun('given_up');
  };

  const handleReset = () => {
    runRef.current = { start: null, startFailed: false, solves: [], result: null };
    setSaveState('idle');
    setSolvedIds(new Set());
    setLastSolvedIds([]);
    setIsRunning(false);
    setIsPaused(false);
    setIsGivenUp(false);
    setElapsedSeconds(0);
    setInputVal('');
    setFeedback(null);
    setFocusedPowiatName(null);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  const toggleVoivodeship = (voiv: string) => {
    setExpandedVoivodeships((prev) => {
      const next = new Set(prev);
      if (next.has(voiv)) next.delete(voiv);
      else next.add(voiv);
      return next;
    });
  };

  const communityById = useMemo(() => {
    const map = new Map<number, { solved_count: number; average_active_seconds: number | null }>();
    if (community) {
      for (const item of community.powiats) {
        map.set(item.powiat_id, item);
      }
    }
    return map;
  }, [community]);

  const recapPowiats = useMemo(() => {
    if (!isCompleted && !isGivenUp) return [];
    return index.catalog
      .filter((p) => {
        if (recapFilter === 'missed') return !solvedIds.has(p.id);
        if (recapFilter === 'solved') return solvedIds.has(p.id);
        return true;
      })
      .sort((a, b) => a.name.localeCompare(b.name, 'pl'));
  }, [isCompleted, isGivenUp, index.catalog, recapFilter, solvedIds]);

  return (
    <div className="mx-auto max-w-6xl px-3 sm:px-6 py-6 sm:py-8 space-y-6">
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-white/10 pb-4">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-0.5 text-[11px] font-mono uppercase tracking-wider text-emerald-300">
            <Car size={13} />
            <span>{t('platesQuiz.badge', 'Poland · 380 Counties')}</span>
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-sand-100">
            {t('platesQuiz.title', 'Polish License Plates Map Quiz')}
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 max-w-2xl">
            {t(
              'platesQuiz.subtitle',
              'Type 2- or 3-letter Polish vehicle registration codes (e.g. WA, KR, KRA, DB) to fill all 380 counties on the map. Valid unsolved codes match automatically.',
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            to="/powiaty"
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <MapPin size={13} />
            <span>{t('platesQuiz.dailyPowiatdle', 'Daily Powiatdle')}</span>
          </Link>
          <Link
            to="/explore#tab=powiats"
            className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-xs font-medium text-sand-200 hover:border-emerald-400/50 hover:text-emerald-300 transition-colors"
          >
            <Eye size={13} />
            <span>{t('platesQuiz.atlas', 'Atlas')}</span>
          </Link>
        </div>
      </header>

      {/* Sticky Input & Scoreboard */}
      <section
        aria-label={t('platesQuiz.scoreboardAria', 'Plate input and scoreboard')}
        className="sticky top-14 xl:top-20 z-40 rounded-lg border border-white/10 bg-obsidian-950/95 backdrop-blur-md px-3 py-2.5 sm:px-4 sm:py-3 space-y-2.5 shadow-xl"
      >
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2.5">
          {/* Plate Input */}
          <div className="relative flex-1 min-w-0">
            <input
              ref={inputRef}
              type="text"
              autoFocus
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              maxLength={6}
              value={inputVal}
              disabled={isGivenUp || isCompleted || isPaused}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isPaused
                  ? t('platesQuiz.placeholderPaused', 'Paused — click Resume')
                  : t('platesQuiz.placeholder', 'Type plate code (e.g. KR, WA, GDA)...')
              }
              className="w-full min-h-[44px] rounded-md border border-emerald-500/50 bg-obsidian-900 pl-3.5 pr-11 py-2 font-mono uppercase tracking-widest text-sm sm:text-base font-bold text-sand-100 placeholder:font-sans placeholder:normal-case placeholder:tracking-normal placeholder:font-normal placeholder-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/25"
            />
            {inputVal && (
              <button
                type="button"
                onClick={() => {
                  setInputVal('');
                  inputRef.current?.focus();
                }}
                aria-label={t('platesQuiz.clearInput', 'Clear input')}
                className="absolute right-0 top-0 bottom-0 flex min-h-[44px] min-w-[44px] items-center justify-center text-zinc-400 hover:text-white cursor-pointer"
              >
                <X size={15} />
              </button>
            )}
          </div>

          {/* Score, Stopwatch & Controls */}
          <div className="flex items-center justify-between md:justify-end gap-1.5 sm:gap-2 w-full md:w-auto min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <div
                className="flex min-h-[40px] sm:min-h-[44px] items-center gap-1.5 rounded-md border border-white/15 bg-obsidian-900 px-2.5 sm:px-3 font-mono shrink-0"
                title={`${solvedCount} / ${totalCount} (${pct}%)`}
              >
                <Trophy size={14} className="hidden sm:block text-emerald-400 shrink-0" />
                <span className="text-sm sm:text-base font-extrabold text-emerald-400">
                  {solvedCount}
                </span>
                <span className="text-xs text-zinc-400">/{totalCount}</span>
                <span className="hidden min-[380px]:inline-block rounded bg-emerald-500/15 px-1.5 py-0.5 text-[11px] font-bold text-emerald-300">
                  {pct}%
                </span>
              </div>

              <div
                className="flex min-h-[40px] sm:min-h-[44px] items-center gap-1 rounded-md border border-white/15 bg-obsidian-900 px-2.5 sm:px-3 font-mono text-xs sm:text-sm text-sand-100 shrink-0"
                title={t('platesQuiz.elapsedTime', 'Elapsed time')}
              >
                <span className="hidden sm:inline text-xs">⏱</span>
                <span className="font-bold">{formatQuizTime(elapsedSeconds)}</span>
              </div>
            </div>

            <div className="flex items-center gap-1.5 shrink-0 ml-auto md:ml-0">
              {!isGivenUp && !isCompleted && (
                <button
                  type="button"
                  onClick={() => {
                    if (!isRunning) {
                      beginRun();
                      setIsRunning(true);
                      setIsPaused(false);
                      inputRef.current?.focus();
                    } else {
                      setIsPaused((p) => {
                        const next = !p;
                        if (!next) window.setTimeout(() => inputRef.current?.focus(), 0);
                        return next;
                      });
                    }
                  }}
                  aria-label={
                    !isRunning
                      ? t('platesQuiz.start', 'Start')
                      : isPaused
                      ? t('platesQuiz.resume', 'Resume')
                      : t('platesQuiz.pause', 'Pause')
                  }
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-md bg-emerald-400 px-3 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 cursor-pointer"
                >
                  {!isRunning || isPaused ? (
                    <Play size={14} className="shrink-0" />
                  ) : (
                    <Pause size={14} className="shrink-0" />
                  )}
                  <span className="hidden sm:inline">
                    {!isRunning
                      ? t('platesQuiz.start', 'Start')
                      : isPaused
                      ? t('platesQuiz.resume', 'Resume')
                      : t('platesQuiz.pause', 'Pause')}
                  </span>
                </button>
              )}

              {!isGivenUp && !isCompleted && (
                <button
                  type="button"
                  onClick={handleGiveUp}
                  aria-label={t('platesQuiz.giveUp', 'Give Up')}
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-md border border-rose-500/35 bg-rose-950/40 px-3 py-2 text-xs font-semibold text-rose-200 hover:bg-rose-900/50 cursor-pointer"
                >
                  <Flag size={13} className="shrink-0" />
                  <span className="hidden sm:inline">{t('platesQuiz.giveUp', 'Give Up')}</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleReset}
                aria-label={t('platesQuiz.reset', 'Reset')}
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-md border border-white/15 bg-obsidian-900 px-3 py-2 text-xs font-semibold text-sand-200 hover:border-emerald-400/50 cursor-pointer"
              >
                <RotateCcw size={13} className="shrink-0" />
                <span className="hidden sm:inline">{t('platesQuiz.reset', 'Reset')}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Feedback line + progress bar */}
        <div className="flex items-center justify-between gap-2 text-xs min-h-[20px]">
          <div className="truncate">
            {feedback?.type === 'matched' && (
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-300">
                <Check size={13} className="shrink-0" />
                <strong className="rounded bg-emerald-500/20 px-1.5 py-0.5">{feedback.code}</strong>
                <span className="font-sans text-sand-200 truncate">
                  {feedback.names.join(' + ')}
                </span>
              </span>
            )}
            {feedback?.type === 'already_solved' && (
              <span className="text-amber-300 font-mono">
                {t('platesQuiz.alreadySolved', '{{code}} is already solved.', { code: feedback.code })}
              </span>
            )}
            {feedback?.type === 'no_match' && (
              <span className="text-rose-300 font-mono">
                {t('platesQuiz.unknownCode', 'Unknown plate code: {{code}}', { code: feedback.code })}
              </span>
            )}
            {!feedback && (
              <span className="text-zinc-500">
                {t('platesQuiz.hint', 'Hover solved counties to see all accepted plates. Unsolved names stay hidden.')}
              </span>
            )}
          </div>
          <div className="hidden sm:flex items-center gap-3 text-[11px] text-zinc-400 shrink-0">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-xs bg-emerald-500 inline-block" />
              {t('platesQuiz.legendSolved', 'Solved')}
            </span>
            {isGivenUp && (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs bg-rose-600 inline-block" />
                {t('platesQuiz.legendMissed', 'Missed')}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-xs bg-zinc-700 border border-zinc-500 inline-block" />
              {t('platesQuiz.legendUnguessed', 'Unguessed')}
            </span>
          </div>
        </div>

        <div className="h-1.5 w-full overflow-hidden rounded-full bg-obsidian-900">
          <div
            className="h-full bg-emerald-500 transition-all duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
      </section>

      {/* Main Interactive Map */}
      <PowiatPlatesMap
        catalogByName={index.byName}
        solvedIds={solvedIds}
        lastSolvedIds={lastSolvedIds}
        isGivenUp={isGivenUp}
        focusedPowiatName={focusedPowiatName}
      />

      {/* Completion or Give-Up Result Dashboard & Recap */}
      {(isCompleted || isGivenUp) && (
        <section
          aria-label={t('platesQuiz.recapAria', 'Quiz recap')}
          className="space-y-4"
        >
          <GameResultDashboard
            variant="inline"
            mode="plates_quiz"
            modeKind="quiz"
            isDaily={false}
            gameName={t('platesQuiz.title', 'Polish License Plates Map Quiz')}
            gamePath="/quiz-tablic"
            won={isCompleted}
            outcomeLabel={isCompleted ? 'Quiz Completed!' : 'Quiz Ended'}
            targetLabel={t('platesQuiz.recapListTitle', 'Counties Filled')}
            targetName={`${solvedCount} / ${totalCount} (${pct}%)`}
            subtitle={
              isCompleted
                ? t('platesQuiz.completedTitle', 'Congratulations! You filled all {{total}} counties in {{time}}!', {
                    total: totalCount,
                    time: formatQuizTime(elapsedSeconds),
                  })
                : t(
                    'platesQuiz.recapSubtitle',
                    'All missed counties are now highlighted in rose on the map. Hover any county or click an entry below to zoom to it.',
                  )
            }
            score={solvedCount}
            maxScore={totalCount}
            elapsedSeconds={elapsedSeconds}
            primaryAction={{
              label: t('platesQuiz.playAgain', 'Play Again'),
              onClick: handleReset,
              icon: <RotateCcw size={14} />,
            }}
          />

          {/* Filterable Post-Game Table */}
          <div className="rounded-lg border border-white/10 bg-obsidian-900 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-serif text-base font-bold text-sand-100">
                {t('platesQuiz.recapListTitle', 'County Plates Breakdown')}
              </h3>
              <div className="flex items-center gap-1.5 text-xs">
                {(['missed', 'solved', 'all'] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setRecapFilter(tab)}
                    className={`rounded px-2.5 py-1 font-medium cursor-pointer transition-colors ${
                      recapFilter === tab
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : 'bg-obsidian-950 text-zinc-400 border border-white/10 hover:text-sand-200'
                    }`}
                  >
                    {tab === 'missed'
                      ? `${t('platesQuiz.filterMissed', 'Missed')} (${totalCount - solvedCount})`
                      : tab === 'solved'
                      ? `${t('platesQuiz.filterSolved', 'Solved')} (${solvedCount})`
                      : `${t('platesQuiz.filterAll', 'All')} (${totalCount})`}
                  </button>
                ))}
              </div>
            </div>

            {recapPowiats.length === 0 ? (
              <p className="text-xs text-zinc-400 py-2">
                {t('platesQuiz.noEntriesInFilter', 'No counties in this category.')}
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-80 overflow-y-auto pr-1">
                {recapPowiats.map((p) => {
                  const isSolved = solvedIds.has(p.id);
                  const stat = communityById.get(p.id);
                  const rate =
                    community && community.finished_runs > 0 && stat
                      ? Math.round((stat.solved_count / community.finished_runs) * 100)
                      : null;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setFocusedPowiatName(p.name)}
                      className={`flex items-start justify-between gap-2 rounded border px-2.5 py-2 text-left text-xs transition-colors cursor-pointer ${
                        isSolved
                          ? 'border-emerald-500/30 bg-emerald-950/25 hover:border-emerald-400/60'
                          : 'border-rose-500/30 bg-rose-950/20 hover:border-rose-400/60'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-sand-100 truncate">{p.name}</div>
                        <div className="font-mono text-[11px] text-zinc-300 break-words">
                          {p.registration_plates.join(', ')}
                        </div>
                      </div>
                      {rate !== null && (
                        <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                          {rate}%
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Community Statistics */}
      <section
        aria-label={t('platesQuiz.communityAria', 'Community quiz statistics')}
        className="rounded-lg border border-white/10 bg-obsidian-900 p-3.5 text-xs text-zinc-300 space-y-2"
      >
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-semibold text-sand-100">{t('platesQuiz.communityTitle', 'Community results')}</h2>
          {communityState === 'loading' && (
            <span role="status">{t('platesQuiz.communityLoading', 'Loading community results…')}</span>
          )}
          {communityState === 'error' && (
            <span role="alert">{t('platesQuiz.communityError', 'Community results could not be loaded.')}</span>
          )}
          {communityState === 'ready' && community?.finished_runs === 0 && (
            <span>{t('platesQuiz.communityEmpty', 'No finished runs tracked yet.')}</span>
          )}
          {communityState === 'ready' && community && community.finished_runs > 0 && (
            <span>
              {t('platesQuiz.communityCount', '{{count}} finished runs', { count: community.finished_runs })}
            </span>
          )}
          <button type="button" onClick={loadCommunity} className="underline cursor-pointer">
            {t('platesQuiz.refresh', 'Refresh')}
          </button>
        </div>
        {saveState === 'saving' && (
          <p role="status">{t('platesQuiz.savingRun', 'Saving your finished run…')}</p>
        )}
        {saveState === 'error' && (
          <p role="alert">
            {t('platesQuiz.saveError', 'Your run could not be saved.')}{' '}
            <button
              type="button"
              className="underline cursor-pointer"
              onClick={() => saveRun(runRef.current, true)}
            >
              {t('platesQuiz.retrySave', 'Retry saving')}
            </button>
          </p>
        )}
      </section>

      {/* Voivodeship Progress Bars */}
      <section aria-label={t('platesQuiz.voivodeshipsAria', 'Progress by voivodeship')} className="space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <h2 className="font-serif text-lg sm:text-xl font-bold text-sand-100">
            {t('platesQuiz.voivodeshipsTitle', 'Progress by Voivodeship')}
          </h2>
          <span className="text-xs text-zinc-400">
            {t('platesQuiz.voivodeshipsHint', 'Click a voivodeship to view solved counties')}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {index.voivodeshipGroups.map(({ voivodeship, items }) => {
            const voivSolved = items.filter((p) => solvedIds.has(p.id)).length;
            const voivPct = items.length > 0 ? Math.round((voivSolved / items.length) * 100) : 0;
            const isExpanded = expandedVoivodeships.has(voivodeship);
            const visibleItems = items.filter((p) => solvedIds.has(p.id) || isGivenUp);

            return (
              <div
                key={voivodeship}
                className="rounded-lg border border-white/10 bg-obsidian-900/90 p-3 space-y-2"
              >
                <button
                  type="button"
                  onClick={() => toggleVoivodeship(voivodeship)}
                  className="w-full text-left space-y-1.5 cursor-pointer"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-xs sm:text-sm capitalize text-sand-100 truncate">
                      {voivodeship}
                    </span>
                    <div className="flex items-center gap-1 shrink-0 font-mono text-xs">
                      <span className={voivSolved === items.length ? 'text-emerald-400 font-bold' : 'text-zinc-300'}>
                        {voivSolved}/{items.length}
                      </span>
                      {isExpanded ? (
                        <ChevronUp size={13} className="text-zinc-400" />
                      ) : (
                        <ChevronDown size={13} className="text-zinc-400" />
                      )}
                    </div>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-obsidian-950">
                    <div
                      className={`h-full transition-all duration-200 ${
                        voivSolved === items.length ? 'bg-emerald-400' : 'bg-emerald-500/80'
                      }`}
                      style={{ width: `${voivPct}%` }}
                    />
                  </div>
                </button>

                {isExpanded && (
                  <div className="pt-1.5 border-t border-white/10 space-y-1 max-h-44 overflow-y-auto">
                    {visibleItems.length === 0 ? (
                      <p className="text-[11px] text-zinc-500">
                        {t('platesQuiz.noneSolvedInVoiv', 'No counties solved yet.')}
                      </p>
                    ) : (
                      visibleItems.map((p) => {
                        const isSolved = solvedIds.has(p.id);
                        return (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => setFocusedPowiatName(p.name)}
                            className="w-full flex items-center justify-between gap-2 rounded px-1.5 py-1 text-left text-[11px] hover:bg-white/5 cursor-pointer"
                          >
                            <span
                              className={`truncate ${
                                isSolved ? 'text-emerald-300' : 'text-rose-300'
                              }`}
                            >
                              {p.name}
                            </span>
                            <span className="font-mono text-[10px] text-zinc-400 shrink-0">
                              {p.registration_plates.slice(0, 2).join(', ')}
                              {p.registration_plates.length > 2 ? '…' : ''}
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
