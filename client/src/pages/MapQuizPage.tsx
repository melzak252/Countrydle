import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import { CheckCircle2, Clock, MapPin, Share2, Trophy, XCircle } from 'lucide-react';
import type { MapQuizDailyState, MapQuizRoundAnswer, MapQuizScope } from '../types';
import { mapQuizService } from '../services/api';
import MapQuizBoard, { type MapQuizFeedback } from '../components/MapQuizBoard';
import CountdownTimer from '../components/CountdownTimer';

const FEEDBACK_DURATION_MS = 1400;

function formatElapsed(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

export default function MapQuizPage({ scope }: { scope: MapQuizScope }) {
  const { t } = useTranslation();
  const [state, setState] = useState<MapQuizDailyState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<MapQuizFeedback | null>(null);
  const [lastResult, setLastResult] = useState<MapQuizRoundAnswer | null>(null);
  const [pendingState, setPendingState] = useState<MapQuizDailyState | null>(null);
  const feedbackTimerRef = useRef<number | null>(null);

  const scopeTitle =
    scope === 'london_boroughs'
      ? t('mapQuiz.londonBoroughsTitle', 'London Boroughs Map Quiz')
      : t('mapQuiz.englandCountiesTitle', 'English Counties Map Quiz');

  const scopeSubtitle =
    scope === 'london_boroughs'
      ? t('mapQuiz.londonBoroughsSubtitle', 'Find 10 London boroughs on the map. New challenge daily at 00:00 UTC.')
      : t('mapQuiz.englandCountiesSubtitle', 'Find 10 English ceremonial counties on the map. New challenge daily at 00:00 UTC.');

  const clearFeedbackTimer = useCallback(() => {
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current);
      feedbackTimerRef.current = null;
    }
  }, []);

  const loadDaily = useCallback(async () => {
    setLoading(true);
    setError(null);
    clearFeedbackTimer();
    setFeedback(null);
    setLastResult(null);
    setPendingState(null);
    try {
      const data = await mapQuizService(scope).getDaily();
      setState(data);
    } catch {
      setError(t('mapQuiz.loadError', 'Could not load today’s map quiz. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, [scope, clearFeedbackTimer, t]);

  useEffect(() => {
    void loadDaily();
    return () => clearFeedbackTimer();
  }, [loadDaily, clearFeedbackTimer]);

  const advancePending = useCallback(() => {
    clearFeedbackTimer();
    setFeedback(null);
    setPendingState((next) => {
      if (next) setState(next);
      return null;
    });
  }, [clearFeedbackTimer]);

  const handleSelectEntity = useCallback(
    async (entity: { id: number; name: string }) => {
      if (!state || state.is_completed || submitting || feedback) return;
      setSubmitting(true);
      try {
        const resp = await mapQuizService(scope).submitAnswer({
          entity_id: entity.id,
          round: state.current_round,
        });
        try {
          localStorage.setItem(`map_quiz_${scope}_daily_${resp.state.date}`, '1');
        } catch {
          // Ignore storage unavailability
        }
        setLastResult(resp.result);
        setFeedback({
          targetId: resp.result.target_id,
          clickedId: resp.result.clicked_id,
          correct: resp.result.correct,
        });
        setPendingState(resp.state);
        clearFeedbackTimer();
        feedbackTimerRef.current = window.setTimeout(() => {
          setFeedback(null);
          setState(resp.state);
          setPendingState(null);
          feedbackTimerRef.current = null;
        }, FEEDBACK_DURATION_MS);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 409) {
          void loadDaily();
        } else {
          toast.error(t('mapQuiz.submitError', 'Could not record your click. Try again.'));
        }
      } finally {
        setSubmitting(false);
      }
    },
    [state, submitting, feedback, scope, clearFeedbackTimer, loadDaily, t],
  );

  const handleShare = useCallback(async () => {
    if (!state) return;
    const grid = state.answers.map((a) => (a.correct ? '🟩' : '🟥')).join('');
    const url =
      scope === 'london_boroughs'
        ? 'https://countrydle.online/map-quiz/london-boroughs'
        : 'https://countrydle.online/map-quiz/england-counties';
    const text = `${scopeTitle} ${state.date}\n${state.score}/${state.total_rounds}${
      state.points !== null ? ` · ${state.points} pts` : ''
    }\n${grid}\n${url}`;
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t('mapQuiz.copied', 'Result copied to clipboard!'));
    } catch {
      toast.error(t('mapQuiz.copyError', 'Could not copy result.'));
    }
  }, [state, scope, scopeTitle, t]);

  const displayedState = state;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
            <MapPin size={14} />
            <span>{t('mapQuiz.dailyBadge', 'Daily 10-Round Map Quiz')}</span>
          </div>
          <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-sand-50">{scopeTitle}</h1>
          <p className="mt-1 text-sm text-zinc-400">{scopeSubtitle}</p>
        </div>
        <CountdownTimer label={t('mapQuiz.nextQuizIn', 'Next quiz in')} />
      </div>

      {loading && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-8 text-center text-zinc-400">
          {t('mapQuiz.loading', 'Loading today’s map challenge…')}
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-6 text-center space-y-3">
          <p className="text-rose-200">{error}</p>
          <button
            type="button"
            onClick={() => void loadDaily()}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition-colors cursor-pointer"
          >
            {t('mapQuiz.retry', 'Retry')}
          </button>
        </div>
      )}

      {!loading && displayedState && (
        <>
          {/* Progress bar + prompt / feedback */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-1.5" aria-label="Round progress">
                {Array.from({ length: displayedState.total_rounds }, (_, idx) => {
                  const ans = (pendingState ?? displayedState).answers[idx];
                  const isCurrent =
                    !displayedState.is_completed &&
                    !pendingState &&
                    idx === displayedState.answers.length;
                  let cls = 'bg-zinc-700';
                  if (ans) cls = ans.correct ? 'bg-emerald-500' : 'bg-rose-500';
                  else if (isCurrent) cls = 'bg-sand-100 ring-2 ring-emerald-400/60';
                  return <span key={idx} className={`h-2.5 w-6 rounded-full transition-colors ${cls}`} />;
                })}
              </div>

              <div className="flex items-center gap-4 text-sm">
                <span className="text-zinc-400">
                  {t('mapQuiz.roundLabel', 'Round')}{' '}
                  <strong className="text-sand-50">
                    {displayedState.current_round}/{displayedState.total_rounds}
                  </strong>
                </span>
                <span className="text-zinc-400">
                  {t('mapQuiz.scoreLabel', 'Score')}{' '}
                  <strong className="text-emerald-400">
                    {(pendingState ?? displayedState).score}/{displayedState.total_rounds}
                  </strong>
                </span>
              </div>
            </div>

            {feedback && lastResult ? (
              <div
                className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 ${
                  lastResult.correct
                    ? 'border-emerald-700/60 bg-emerald-950/40 text-emerald-200'
                    : 'border-amber-700/60 bg-amber-950/40 text-amber-100'
                }`}
              >
                <div className="flex items-center gap-2.5 text-sm sm:text-base font-medium">
                  {lastResult.correct ? (
                    <CheckCircle2 className="shrink-0 text-emerald-400" size={20} />
                  ) : (
                    <XCircle className="shrink-0 text-rose-400" size={20} />
                  )}
                  {lastResult.correct ? (
                    <span>
                      {t('mapQuiz.correctFeedback', 'Correct! That’s {{name}}.', {
                        name: lastResult.target_name,
                      })}
                    </span>
                  ) : (
                    <span>
                      {t('mapQuiz.wrongFeedback', 'You clicked {{clicked}}. {{target}} is highlighted in amber.', {
                        clicked: lastResult.clicked_name,
                        target: lastResult.target_name,
                      })}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={advancePending}
                  className="rounded-md border border-white/15 bg-white/10 px-3 py-1 text-xs font-semibold text-white hover:bg-white/20 transition-colors cursor-pointer"
                >
                  {pendingState?.is_completed
                    ? t('mapQuiz.seeResults', 'See results')
                    : t('mapQuiz.nextRound', 'Next')}
                </button>
              </div>
            ) : !displayedState.is_completed && displayedState.current_target ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-700/80 bg-zinc-950/70 px-4 py-3">
                <div className="flex items-baseline gap-2.5">
                  <span className="text-xs uppercase tracking-wider text-zinc-400">
                    {t('mapQuiz.locatePrompt', 'Click on the map:')}
                  </span>
                  <span className="text-xl sm:text-2xl font-bold text-sand-50">
                    {displayedState.current_target.name}
                  </span>
                </div>
                <span className="text-xs text-zinc-400">
                  {t('mapQuiz.noLabelsHint', 'Labels are hidden while playing')}
                </span>
              </div>
            ) : null}
          </div>

          {/* Interactive Map */}
          <MapQuizBoard
            scope={scope}
            answers={displayedState.answers}
            feedback={feedback}
            isCompleted={displayedState.is_completed}
            disabled={submitting || feedback !== null}
            onSelectEntity={handleSelectEntity}
          />

          {/* Completion Summary Card */}
          {displayedState.is_completed && (
            <div className="rounded-xl border border-emerald-800/50 bg-zinc-900/90 p-5 space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-sand-50">
                    {t('mapQuiz.completedTitle', 'Daily Map Quiz Complete!')}
                  </h2>
                  <p className="text-sm text-zinc-400 mt-0.5">
                    {t('mapQuiz.exploreHint', 'Hover any region on the map above to inspect its name.')}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void handleShare()}
                    className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 transition-colors cursor-pointer"
                  >
                    <Share2 size={16} />
                    {t('mapQuiz.shareResult', 'Share result')}
                  </button>
                  <Link
                    to={`/leaderboard?mode=map_quiz:${scope}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-700 transition-colors"
                  >
                    <Trophy size={16} />
                    {t('mapQuiz.viewLeaderboard', 'Leaderboard')}
                  </Link>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 text-center">
                  <div className="text-xs uppercase text-zinc-400">{t('mapQuiz.scoreLabel', 'Score')}</div>
                  <div className="mt-1 text-2xl font-bold text-emerald-400">
                    {displayedState.score}/{displayedState.total_rounds}
                  </div>
                </div>
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 text-center">
                  <div className="text-xs uppercase text-zinc-400">{t('mapQuiz.pointsLabel', 'Points')}</div>
                  <div className="mt-1 text-2xl font-bold text-sand-50">
                    {displayedState.points ?? 0}
                  </div>
                </div>
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 text-center">
                  <div className="flex items-center justify-center gap-1 text-xs uppercase text-zinc-400">
                    <Clock size={12} />
                    {t('mapQuiz.timeLabel', 'Time')}
                  </div>
                  <div className="mt-1 text-2xl font-bold text-sand-50">
                    {formatElapsed(displayedState.elapsed_seconds)}
                  </div>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-2">
                {displayedState.answers.map((ans) => (
                  <div
                    key={ans.round}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-mono text-zinc-500 w-5">{ans.round}.</span>
                      {ans.correct ? (
                        <CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
                      ) : (
                        <XCircle size={15} className="shrink-0 text-rose-400" />
                      )}
                      <span className="font-medium text-sand-50 truncate">{ans.target_name}</span>
                    </div>
                    {!ans.correct && (
                      <span className="text-xs text-rose-300 truncate shrink-0">
                        {t('mapQuiz.clickedShort', 'clicked {{name}}', { name: ans.clicked_name })}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
