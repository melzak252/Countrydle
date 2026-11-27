import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Play,
  Pause,
  RotateCcw,
  Flag,
  Check,
  X,
  Trophy,
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
  const [voivPanelOpen, setVoivPanelOpen] = useState<boolean>(false);
  const [expandedVoivodeships, setExpandedVoivodeships] = useState<Set<string>>(() => new Set());
  const [recapFilter, setRecapFilter] = useState<'missed' | 'solved' | 'all'>('missed');
  const [resultsModalOpen, setResultsModalOpen] = useState<boolean>(false);

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

  const completedVoivodeshipsCount = useMemo(
    () =>
      index.voivodeshipGroups.filter(
        ({ items }) => items.length > 0 && items.every((p) => solvedIds.has(p.id)),
      ).length,
    [index.voivodeshipGroups, solvedIds],
  );

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
        setRecapFilter('solved');
        setResultsModalOpen(true);
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
    setResultsModalOpen(true);
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
    setResultsModalOpen(false);
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

  const recapDetailsSlot = (
    <div className="space-y-4">
      {/* Filter tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {(['missed', 'solved', 'all'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setRecapFilter(tab)}
              className={`rounded-sm px-2.5 py-1 font-medium cursor-pointer transition-colors border ${
                recapFilter === tab
                  ? 'border-app-accent/60 bg-app-accent/15 text-app-accent'
                  : 'border-app-border/40 bg-app-surface-muted text-app-text-secondary hover:text-app-text'
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

        <div className="flex flex-wrap items-center gap-2 text-[11px] text-app-text-muted">
          {communityState === 'loading' && (
            <span role="status">{t('platesQuiz.communityLoading', 'Loading community results...')}</span>
          )}
          {communityState === 'error' && (
            <span role="alert">{t('platesQuiz.communityError', 'Community results could not be loaded.')}</span>
          )}
          {communityState === 'ready' && community?.finished_runs === 0 && (
            <span>{t('platesQuiz.communityEmpty', 'No finished runs tracked yet.')}</span>
          )}
          {communityState === 'ready' && community && community.finished_runs > 0 && (
            <span>
              {t('platesQuiz.communityCount', '{{count}} finished runs', {
                count: community.finished_runs,
              })}
            </span>
          )}
          <button
            type="button"
            onClick={loadCommunity}
            className="underline text-app-text-secondary hover:text-app-accent cursor-pointer"
          >
            {t('platesQuiz.refresh', 'Refresh')}
          </button>
        </div>
      </div>

      {saveState === 'saving' && (
        <p role="status" className="text-xs text-app-text-secondary">
          {t('platesQuiz.savingRun', 'Saving your finished run...')}
        </p>
      )}
      {saveState === 'error' && (
        <p role="alert" className="text-xs text-[#c85243]">
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

      {recapPowiats.length === 0 ? (
        <p className="text-xs text-app-text-muted py-2">
          {t('platesQuiz.noEntriesInFilter', 'No counties in this category.')}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-72 overflow-y-auto pr-1">
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
                onClick={() => {
                  setFocusedPowiatName(p.name);
                  setResultsModalOpen(false);
                }}
                className={`flex items-start justify-between gap-2 rounded-sm border px-2.5 py-2 text-left text-xs transition-colors cursor-pointer ${
                  isSolved
                    ? 'border-app-accent/40 bg-app-accent/10 hover:border-app-accent'
                    : 'border-[#c85243]/40 bg-[#c85243]/10 hover:border-[#c85243]'
                }`}
              >
                <div className="min-w-0">
                  <div className="font-semibold text-app-text truncate">{p.name}</div>
                  <div className="font-mono text-[11px] text-app-text-secondary break-words">
                    {p.registration_plates.join(', ')}
                  </div>
                </div>
                {rate !== null && (
                  <span className="shrink-0 rounded-sm bg-app-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-app-text-muted">
                    {rate}%
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div className="relative flex-1 min-h-0 h-full w-full overflow-hidden bg-app-canvas select-none">
      {/* Fullscreen Interactive Map Layer */}
      <div className="absolute inset-0 z-0">
        <PowiatPlatesMap
          catalogByName={index.byName}
          solvedIds={solvedIds}
          lastSolvedIds={lastSolvedIds}
          isGivenUp={isGivenUp}
          focusedPowiatName={focusedPowiatName}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </div>

      {/* Floating Top-Center Input & Scoreboard HUD */}
      <section
        aria-label={t('platesQuiz.scoreboardAria', 'Plate input and scoreboard')}
        className="absolute inset-x-0 top-3 z-[1050] mx-auto max-w-3xl pl-3 pr-14 lg:px-3 pointer-events-none"
      >
        <div className="pointer-events-auto rounded-md border border-app-border bg-app-surface/95 backdrop-blur-md px-3 py-2.5 shadow-lg space-y-2">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2">
            {/* Uppercase Plate Input */}
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
                    ? t('platesQuiz.placeholderPaused', 'Paused. Click Resume to continue')
                    : t('platesQuiz.placeholder', 'Type plate code (e.g. KR, WA, GDA)...')
                }
                className="w-full min-h-[40px] rounded-md border border-app-border/60 bg-app-surface-raised pl-3 pr-10 py-1.5 font-mono uppercase tracking-widest text-sm sm:text-base font-bold text-app-text placeholder:font-sans placeholder:normal-case placeholder:tracking-normal placeholder:font-normal placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-accent/25 disabled:opacity-60"
              />
              {inputVal && (
                <button
                  type="button"
                  onClick={() => {
                    setInputVal('');
                    inputRef.current?.focus();
                  }}
                  aria-label={t('platesQuiz.clearInput', 'Clear input')}
                  className="absolute right-0 top-0 bottom-0 flex min-h-[40px] min-w-[38px] items-center justify-center text-app-text-muted hover:text-app-text cursor-pointer"
                >
                  <X size={15} />
                </button>
              )}
            </div>

            {/* Score, Stopwatch & Controls */}
            <div className="flex items-center justify-between md:justify-end gap-1.5 w-full md:w-auto min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <div
                  className="flex min-h-[38px] items-center gap-1.5 rounded-md border border-app-border/50 bg-app-surface-raised px-2.5 font-mono shrink-0"
                  title={`${solvedCount} / ${totalCount} (${pct}%)`}
                >
                  <Trophy size={13} className="hidden sm:block text-app-accent shrink-0" />
                  <span className="text-sm font-extrabold text-app-accent tabular-nums">
                    {solvedCount}
                  </span>
                  <span className="text-xs text-app-text-muted tabular-nums">/{totalCount}</span>
                  <span className="hidden min-[380px]:inline-block rounded bg-app-accent/15 px-1.5 py-0.5 text-[11px] font-bold text-app-accent tabular-nums">
                    {pct}%
                  </span>
                </div>

                <div
                  className="flex min-h-[38px] items-center gap-1 rounded-md border border-app-border/50 bg-app-surface-raised px-2.5 font-mono text-xs sm:text-sm text-app-text shrink-0 tabular-nums"
                  title={t('platesQuiz.elapsedTime', 'Elapsed time')}
                >
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
                    className="inline-flex min-h-[38px] min-w-[38px] items-center justify-center gap-1.5 rounded-md bg-app-accent px-2.5 py-1.5 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors cursor-pointer"
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
                    className="inline-flex min-h-[38px] min-w-[38px] items-center justify-center gap-1.5 rounded-md border border-[#c85243]/45 bg-[#c85243]/10 px-2.5 py-1.5 text-xs font-semibold text-[#c85243] hover:bg-[#c85243]/20 transition-colors cursor-pointer"
                  >
                    <Flag size={13} className="shrink-0" />
                    <span className="hidden sm:inline">{t('platesQuiz.giveUp', 'Give Up')}</span>
                  </button>
                )}

                {(isCompleted || isGivenUp) && (
                  <button
                    type="button"
                    onClick={() => setResultsModalOpen(true)}
                    aria-label={t('platesQuiz.results', 'Results')}
                    className="inline-flex min-h-[38px] min-w-[38px] items-center justify-center gap-1.5 rounded-md bg-app-accent px-2.5 py-1.5 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors cursor-pointer"
                  >
                    <Trophy size={13} className="shrink-0" />
                    <span className="hidden sm:inline">{t('platesQuiz.results', 'Results')}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleReset}
                  aria-label={t('platesQuiz.reset', 'Reset')}
                  className="inline-flex min-h-[38px] min-w-[38px] items-center justify-center gap-1.5 rounded-md border border-app-border/50 bg-app-surface-raised px-2.5 py-1.5 text-xs font-semibold text-app-text hover:border-app-accent hover:text-app-accent transition-colors cursor-pointer"
                >
                  <RotateCcw size={13} className="shrink-0" />
                  <span className="hidden sm:inline">{t('platesQuiz.reset', 'Reset')}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Slim Inline Feedback Line & Legend (fixed height to prevent layout jump) */}
          <div className="flex items-center justify-between gap-2 text-xs h-5">
            <div className="truncate min-w-0">
              {feedback?.type === 'matched' && (
                <span className="inline-flex items-center gap-1.5 font-mono text-app-accent">
                  <Check size={13} className="shrink-0" />
                  <strong className="rounded bg-app-accent/15 px-1.5 py-0.5 text-[11px]">
                    {feedback.code}
                  </strong>
                  <span className="font-sans text-app-text-secondary truncate">
                    {feedback.names.join(' + ')}
                  </span>
                </span>
              )}
              {feedback?.type === 'already_solved' && (
                <span className="text-[#c68f42] font-mono">
                  {t('platesQuiz.alreadySolved', '{{code}} is already solved.', {
                    code: feedback.code,
                  })}
                </span>
              )}
              {feedback?.type === 'no_match' && (
                <span className="text-[#c85243] font-mono">
                  {t('platesQuiz.unknownCode', 'Unknown plate code: {{code}}', {
                    code: feedback.code,
                  })}
                </span>
              )}
              {!feedback && (
                <span className="text-app-text-muted">
                  {t(
                    'platesQuiz.hint',
                    'Hover solved counties to see all accepted plates. Unsolved names stay hidden.',
                  )}
                </span>
              )}
            </div>

            <div className="hidden sm:flex items-center gap-3 text-[11px] text-app-text-muted shrink-0">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs bg-app-accent inline-block" />
                {t('platesQuiz.legendSolved', 'Solved')}
              </span>
              {isGivenUp && (
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-xs bg-[#c85243] inline-block" />
                  {t('platesQuiz.legendMissed', 'Missed')}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs bg-app-surface-muted border border-app-border inline-block" />
                {t('platesQuiz.legendUnguessed', 'Unguessed')}
              </span>
            </div>
          </div>

          {/* Slim Overall Progress Bar */}
          <div className="h-1 w-full overflow-hidden rounded-full bg-app-surface-muted">
            <div
              className="h-full bg-app-accent transition-all duration-200"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </section>

      {/* Collapsible Floating Voivodeships Progress Panel */}
      <aside
        aria-label={t('platesQuiz.voivodeshipsAria', 'Progress by voivodeship')}
        className="absolute bottom-4 left-4 z-[1050] max-w-[calc(100vw-2rem)] flex flex-col items-start gap-2 pointer-events-none"
      >
        {voivPanelOpen && (
          <div className="pointer-events-auto w-72 sm:w-80 max-h-[45vh] overflow-y-auto rounded-md border border-app-border bg-app-surface/95 backdrop-blur-md p-3 shadow-lg space-y-2">
            <div className="flex items-center justify-between gap-2 border-b border-app-border/40 pb-1.5">
              <h2 className="font-serif text-sm font-bold text-app-text">
                {t('platesQuiz.voivodeshipsTitle', 'Progress by Voivodeship')}
              </h2>
              <span className="font-mono text-[11px] text-app-text-muted tabular-nums">
                {completedVoivodeshipsCount}/{index.voivodeshipGroups.length}
              </span>
            </div>

            <div className="space-y-2">
              {index.voivodeshipGroups.map(({ voivodeship, items }) => {
                const voivSolved = items.filter((p) => solvedIds.has(p.id)).length;
                const voivPct = items.length > 0 ? Math.round((voivSolved / items.length) * 100) : 0;
                const isExpanded = expandedVoivodeships.has(voivodeship);
                const visibleItems = items.filter((p) => solvedIds.has(p.id) || isGivenUp);

                return (
                  <div
                    key={voivodeship}
                    className="rounded-sm border border-app-border/35 bg-app-surface-raised/80 p-2 space-y-1.5"
                  >
                    <button
                      type="button"
                      onClick={() => toggleVoivodeship(voivodeship)}
                      className="w-full text-left space-y-1 cursor-pointer"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-xs capitalize text-app-text truncate">
                          {voivodeship}
                        </span>
                        <div className="flex items-center gap-1 shrink-0 font-mono text-[11px] tabular-nums">
                          <span
                            className={
                              voivSolved === items.length
                                ? 'text-app-accent font-bold'
                                : 'text-app-text-secondary'
                            }
                          >
                            {voivSolved}/{items.length}
                          </span>
                          {isExpanded ? (
                            <ChevronUp size={12} className="text-app-text-muted" />
                          ) : (
                            <ChevronDown size={12} className="text-app-text-muted" />
                          )}
                        </div>
                      </div>
                      <div className="h-1 w-full overflow-hidden rounded-full bg-app-surface-muted">
                        <div
                          className="h-full bg-app-accent transition-all duration-200"
                          style={{ width: `${voivPct}%` }}
                        />
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="pt-1 border-t border-app-border/30 space-y-0.5 max-h-32 overflow-y-auto">
                        {visibleItems.length === 0 ? (
                          <p className="text-[11px] text-app-text-muted">
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
                                className="w-full flex items-center justify-between gap-2 rounded-sm px-1.5 py-0.5 text-left text-[11px] hover:bg-app-surface-muted cursor-pointer"
                              >
                                <span
                                  className={`truncate ${
                                    isSolved ? 'text-app-accent font-medium' : 'text-[#c85243]'
                                  }`}
                                >
                                  {p.name}
                                </span>
                                <span className="font-mono text-[10px] text-app-text-muted shrink-0">
                                  {p.registration_plates.slice(0, 2).join(', ')}
                                  {p.registration_plates.length > 2 ? '...' : ''}
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
          </div>
        )}

        <button
          type="button"
          onClick={() => setVoivPanelOpen((open) => !open)}
          aria-expanded={voivPanelOpen}
          className="pointer-events-auto inline-flex items-center gap-2 rounded-md border border-app-border bg-app-surface/95 backdrop-blur-md px-3 py-2 text-xs font-semibold text-app-text shadow-lg hover:border-app-accent transition-colors cursor-pointer"
        >
          <MapPin size={14} className="text-app-accent shrink-0" />
          <span>{t('platesQuiz.voivodeshipsToggle', 'Voivodeships')}</span>
          <span className="rounded bg-app-surface-muted px-1.5 py-0.5 font-mono text-[11px] text-app-text-secondary tabular-nums">
            {completedVoivodeshipsCount}/{index.voivodeshipGroups.length}
          </span>
          {voivPanelOpen ? (
            <ChevronDown size={14} className="text-app-text-muted shrink-0" />
          ) : (
            <ChevronUp size={14} className="text-app-text-muted shrink-0" />
          )}
        </button>
      </aside>

      {/* Completion or Give-Up Result Dashboard Modal */}
      {(isCompleted || isGivenUp) && resultsModalOpen && (
        <GameResultDashboard
          variant="modal"
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
              ? t(
                  'platesQuiz.completedTitle',
                  'Congratulations! You filled all {{total}} counties in {{time}}!',
                  {
                    total: totalCount,
                    time: formatQuizTime(elapsedSeconds),
                  },
                )
              : t(
                  'platesQuiz.recapSubtitle',
                  'All missed counties are now highlighted in rose on the map. Hover any county or click an entry below to zoom to it.',
                )
          }
          score={solvedCount}
          maxScore={totalCount}
          elapsedSeconds={elapsedSeconds}
          onClose={() => setResultsModalOpen(false)}
          closeLabel={t('platesQuiz.inspectMap', 'Inspect Map')}
          primaryAction={{
            label: t('platesQuiz.playAgain', 'Play Again'),
            onClick: handleReset,
            icon: <RotateCcw size={14} />,
          }}
          detailsTitle={t('platesQuiz.recapListTitle', 'County Plates Breakdown')}
          detailsSlot={recapDetailsSlot}
        />
      )}
    </div>
  );
}
