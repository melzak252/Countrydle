import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { isAxiosError } from 'axios';
import { Loader2, Play, RefreshCw, Sparkles, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../services/api';
import type { AnswerReport, QuestionTestEntity, QuestionTestMode, QuestionTestRequest, QuestionTestResult } from '../types';

const MODE_LABELS: Record<QuestionTestMode | 'continental', string> = {
  countrydle: 'Countrydle',
  us_statedle: 'US Statedle',
  powiatdle: 'Powiatdle',
  wojewodztwodle: 'Województwodle',
  continental: 'Europedle / Continental',
  europe: 'Europa',
  asia: 'Azja',
  africa: 'Afryka',
  americas: 'Ameryki',
  flagdle: 'Flagdle',
};
export interface QuestionTestBridgeTarget {
  mode: string;
  targetName?: string;
  questionText?: string;
}

function initialTestMode(report: AnswerReport | null, target?: QuestionTestBridgeTarget | null): QuestionTestMode {
  if (target?.mode) {
    const cleanMode = target.mode.startsWith('continental') ? 'countrydle' : target.mode;
    if (cleanMode in MODE_LABELS) return cleanMode as QuestionTestMode;
  }
  if (!report) return 'countrydle';
  if (report.mode === 'continental') return 'countrydle';
  return report.mode;
}

function matchesReportMode(mode: QuestionTestMode, reportMode: AnswerReport['mode']): boolean {
  if (mode === reportMode) return true;
  if (reportMode === 'continental' && (mode === 'countrydle' || mode === 'europe' || mode === 'asia' || mode === 'africa' || mode === 'americas')) return true;
  return false;
}
const SOURCE_LABELS: Record<QuestionTestResult['source'], string> = {
  local_kb: 'Lokalna baza wiedzy',
  local_planner: 'Lokalny planer',
  fallback: 'Ścieżka zapasowa modelu',
  flag_kb: 'Lokalna baza flag',
};
const controlClass = 'admin-control w-full min-w-0';
const cardClass = 'admin-panel min-w-0 space-y-4 p-4 sm:p-5';

function errorMessage(cause: unknown, fallback: string): string {
  if (isAxiosError(cause) && typeof cause.response?.data?.detail === 'string') {
    return `${fallback} ${cause.response.data.detail}`;
  }
  return fallback;
}

function Answer({ valid, answer }: { valid: boolean; answer: boolean | null }) {
  const { t } = useTranslation('translation', { keyPrefix: 'adminQuestionTests' });
  return (
    <div className="space-y-1">
      <p className={`font-semibold ${valid ? 'text-emerald-300' : 'text-amber-300'}`}>{valid ? t('validQuestion') : t('invalidQuestion')}</p>
      <p className="text-xl font-semibold text-sand-100">{!valid || answer === null ? t('noAnswer') : answer ? t('yes') : t('no')}</p>
    </div>
  );
}

type CompletedTest = {
  request: QuestionTestRequest;
  entity: QuestionTestEntity;
  result: QuestionTestResult;
  comparableReportId: number | null;
};

export default function QuestionTestsPanel({
  report,
  onClearReport,
  initialTarget,
  onClearInitialTarget,
}: {
  report: AnswerReport | null;
  onClearReport: () => void;
  initialTarget?: QuestionTestBridgeTarget | null;
  onClearInitialTarget?: () => void;
}) {
  const { t, i18n } = useTranslation('translation', { keyPrefix: 'adminQuestionTests' });
  const { t: modesT } = useTranslation('translation');
  const [mode, setMode] = useState<QuestionTestMode>(initialTestMode(report, initialTarget));
  const [question, setQuestion] = useState(initialTarget?.questionText || report?.details.original_question || '');
  const [entityId, setEntityId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [revision, setRevision] = useState(0);
  const [entities, setEntities] = useState<{ mode: QuestionTestMode; items: QuestionTestEntity[]; error: string | null } | null>(null);
  const [completed, setCompleted] = useState<CompletedTest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(false);
  const pending = useRef(false);
  const loadingEntities = entities === null || entities.mode !== mode;
  const availableEntities = loadingEntities ? [] : entities.items;
  const selectedEntity = availableEntities.find((entity) => entity.id === entityId);
  const matchingTargets = report && matchesReportMode(mode, report.mode)
    ? availableEntities.filter((entity) => entity.name === report.details.target_name)
    : [];
  const normalizedSearch = search.trim().toLocaleLowerCase('pl');
  const filteredEntities = availableEntities.filter((entity) => entity.name.toLocaleLowerCase('pl').includes(normalizedSearch));
  const visibleEntities = selectedEntity && !filteredEntities.some((entity) => entity.id === selectedEntity.id)
    ? [selectedEntity, ...filteredEntities]
    : filteredEntities;
  const trimmedQuestion = question.trim();
  const canSubmit = !busy && !loadingEntities && !!selectedEntity && trimmedQuestion.length > 0 && question.length <= 100;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (initialTarget) {
      if (initialTarget.mode) {
        const cleanMode = initialTarget.mode.startsWith('continental') ? 'countrydle' : initialTarget.mode;
        if (cleanMode in MODE_LABELS) setMode(cleanMode as QuestionTestMode);
      }
      if (initialTarget.questionText) {
        setQuestion(initialTarget.questionText);
      }
      setCompleted(null);
      setError(null);
    }
  }, [initialTarget]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setEntities(null);
    setEntityId(null);
    setCompleted(null);
    setError(null);
    adminService.getQuestionTestEntities(mode, controller.signal)
      .then((items) => {
        if (cancelled) return;
        setEntities({ mode, items, error: null });
        const matches = report && matchesReportMode(mode, report.mode)
          ? items.filter((entity) => entity.name === report.details.target_name)
          : initialTarget?.targetName
          ? items.filter((entity) => entity.name.toLowerCase() === initialTarget.targetName?.toLowerCase())
          : [];
        if (matches.length >= 1) setEntityId(matches[0].id);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setEntities({ mode, items: [], error: errorMessage(cause, t('loadEntitiesError')) });
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [mode, report, initialTarget, revision]);
  const clearResult = () => {
    setCompleted(null);
    setError(null);
  };

  const runTest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending.current || !canSubmit || !selectedEntity) return;
    pending.current = true;
    setBusy(true);
    clearResult();
    const request: QuestionTestRequest = { mode, entity_id: selectedEntity.id, question: trimmedQuestion };
    const comparableReportId = report && matchesReportMode(mode, report.mode)
      && matchingTargets.length === 1 && matchingTargets[0].id === selectedEntity.id
      && report.details.original_question.trim() === request.question ? report.id : null;
    try {
      const result = await adminService.testQuestion(request);
      if (mounted.current) setCompleted({ request, entity: selectedEntity, result, comparableReportId });
    } catch (cause: unknown) {
      if (mounted.current) setError(errorMessage(cause, t('testError')));
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  return (
    <section aria-labelledby="admin-page-title" className="min-w-0 space-y-5">
      <details className="admin-panel p-4">
        <summary className="cursor-pointer text-sm font-medium text-emerald-300">{t('howTestingWorks')}</summary>
        <p className="mt-3 max-w-3xl whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{t('caveats')}</p>
      </details>

      {initialTarget && (
        <div className="flex flex-wrap items-start justify-between gap-3 rounded-sm border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-200">
          <div className="flex min-w-0 items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="min-w-0 break-words">{initialTarget.targetName ? t('bridgeTarget', { target: initialTarget.targetName, question: initialTarget.questionText }) : t('bridgeQuestion', { question: initialTarget.questionText })}</p>
          </div>
          {onClearInitialTarget && (
            <button type="button" onClick={onClearInitialTarget} className="admin-button" aria-label={t('clearTestTarget')}>
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
      <div className={`grid min-w-0 gap-4 ${report ? 'space-y-4' : 'xl:grid-cols-2'}`}>
      <form onSubmit={(event) => void runTest(event)} className={cardClass} aria-busy={busy}>
        <fieldset disabled={busy} className="min-w-0 space-y-4">
          <legend className="sr-only">{t('formLegend')}</legend>
          <div className="grid min-w-0 gap-4 sm:grid-cols-2">
            <label className="flex min-w-0 flex-col gap-1.5 text-sm text-slate-300">
              {t('mode')}
              <select value={mode} onChange={(event) => {
                setMode(event.target.value as QuestionTestMode);
                setEntityId(null);
                setSearch('');
                clearResult();
              }} className={controlClass}>
                {Object.entries(MODE_LABELS).filter(([value]) => value !== 'continental').map(([value, label]) => <option key={value} value={value}>{modesT(`adminModes.modes.${value}`, { defaultValue: label })}</option>)}
              </select>
            </label>
            <label className="flex min-w-0 flex-col gap-1.5 text-sm text-slate-300">
              {t('searchEntity')}
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('searchPlaceholder')} disabled={loadingEntities || !!entities?.error} className={controlClass} />
            </label>
            <label className="flex min-w-0 flex-col gap-1.5 text-sm text-slate-300 sm:col-span-2">
              {t('target')}
              <select value={entityId ?? ''} disabled={loadingEntities || !!entities?.error || availableEntities.length === 0} required onChange={(event) => {
                setEntityId(event.target.value ? Number(event.target.value) : null);
                clearResult();
              }} className={controlClass}>
                <option value="">{loadingEntities ? t('loadingEntities') : t('selectEntity')}</option>
                {visibleEntities.map((entity) => <option key={entity.id} value={entity.id}>{entity.name} · ID {entity.id}</option>)}
              </select>
            </label>
          </div>
          {loadingEntities && <p role="status" className="text-sm text-slate-300">{t('loadingEntities')}</p>}
          {entities?.error && !loadingEntities && <div role="alert" className="space-y-2 text-sm text-rose-300">
            <p>{entities.error}</p>
            <button type="button" onClick={() => { setEntities(null); setRevision((value) => value + 1); }} className="admin-button flex items-center gap-2"><RefreshCw size={14} aria-hidden="true" />{t('retry')}</button>
          </div>}
          {!loadingEntities && !entities?.error && availableEntities.length === 0 && <p role="status" className="text-sm text-slate-300">{t('noEntities')}</p>}
          {!loadingEntities && availableEntities.length > 0 && filteredEntities.length === 0 && <p role="status" className="text-sm text-slate-300">{t('noSearchResults')}</p>}
          {report && matchesReportMode(mode, report.mode) && !loadingEntities && !entities?.error && matchingTargets.length !== 1 && <p role="status" className="text-sm text-amber-300">{t('noUniqueTarget', { target: report.details.target_name })}</p>}
          <label className="flex min-w-0 flex-col gap-1.5 text-sm text-slate-300">
            {t('question')}
            <textarea value={question} maxLength={100} rows={3} required aria-describedby="question-test-counter" onChange={(event) => {
              setQuestion(event.target.value);
              clearResult();
            }} placeholder={t('questionPlaceholder')} className={`${controlClass} resize-y`} />
          </label>
          <p id="question-test-counter" className="text-right text-sm text-slate-300">{t('characterCount', { count: question.length })}</p>
          <button type="submit" disabled={!canSubmit} className="admin-button admin-button-primary flex items-center gap-2">
            {busy ? <Loader2 size={16} aria-hidden="true" className="animate-spin" /> : <Play size={16} aria-hidden="true" />}
            {busy ? t('testing') : completed ? t('runAgain') : t('runTest')}
          </button>
        </fieldset>
        {busy && <p role="status" className="text-sm text-slate-300">{t('waiting')}</p>}
        {error && <p role="alert" className="whitespace-pre-wrap break-words text-sm text-rose-300">{error}</p>}
      </form>
      <div className="min-w-0 space-y-4">
      {report && <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-300">
        <p>{t('reportComparison', { id: report.id })}</p>
        <button type="button" disabled={busy} onClick={onClearReport} className="admin-button">{t('detachReport')}</button>
      </div>}
      <div className={`grid min-w-0 gap-4 ${report ? 'xl:grid-cols-2' : ''}`}>
        {report && <article className={cardClass} aria-labelledby="historical-answer-title">
          <h2 id="historical-answer-title" className="text-lg font-semibold text-sand-100">{t('historicalAnswer', { id: report.id })}</h2>
          <p className="break-words text-sm text-slate-300">{modesT(`adminModes.modes.${report.mode}`, { defaultValue: MODE_LABELS[report.mode] })} · {report.details.target_name} · {report.details.game_date}</p>
          <p className="whitespace-pre-wrap break-words text-base text-sand-100">{report.details.original_question}</p>
          <Answer valid={report.details.valid} answer={report.details.answer} />
          <dl className="space-y-3 text-sm">
            <div><dt className="text-sm text-slate-400">{t('historicalServer')}</dt><dd className="break-words font-mono text-sm text-slate-300">{report.details.server_version ?? t('notRecorded')}</dd></div>
            <div><dt className="text-sm text-slate-400">{t('historicalExplanation')}</dt><dd className="whitespace-pre-wrap break-words text-slate-300">{report.details.explanation || t('noExplanation')}</dd></div>
          </dl>
        </article>}
        {completed ? <article className={cardClass} aria-labelledby="current-answer-title">
          <h2 id="current-answer-title" className="text-lg font-semibold text-sand-100">{t('currentResult')}</h2>
          <p className="break-words text-sm text-slate-300">{modesT(`adminModes.modes.${completed.request.mode}`, { defaultValue: MODE_LABELS[completed.request.mode] })} · {completed.entity.name} · {t('entityId', { id: completed.request.entity_id })}</p>
          <dl className="space-y-3 text-sm">
            <div><dt className="text-sm text-slate-400">{t('sentQuestion')}</dt><dd className="whitespace-pre-wrap break-words text-sand-100">{completed.request.question}</dd></div>
            <div><dt className="text-sm text-slate-400">{t('interpretedQuestion')}</dt><dd className="whitespace-pre-wrap break-words text-slate-300">{completed.result.question ?? t('noInterpretation')}</dd></div>
          </dl>
          <Answer valid={completed.result.valid} answer={completed.result.answer} />
          {report && <p role="status" className={`rounded-sm border p-3 text-sm ${completed.comparableReportId === report.id ? 'border-emerald-400/30 text-sand-100' : 'border-slate-500 text-slate-300'}`}>
            {completed.comparableReportId !== report.id
              ? t('notComparable')
              : completed.result.valid === report.details.valid && completed.result.answer === report.details.answer
                ? t('answersMatch')
                : t('answersDiffer')}
          </p>}
          <dl className="grid min-w-0 gap-3 text-sm sm:grid-cols-2">
            <div className="min-w-0 sm:col-span-2"><dt className="text-sm text-slate-400">{t('explanation')}</dt><dd className="whitespace-pre-wrap break-words text-slate-300">{completed.result.explanation || t('noExplanation')}</dd></div>
            <div className="min-w-0"><dt className="text-sm text-slate-400">{t('answerSource')}</dt><dd className="text-slate-300">{t(`sources.${completed.result.source}`, { defaultValue: SOURCE_LABELS[completed.result.source] })} <span className="font-mono text-xs">({completed.result.source})</span></dd></div>
            <div><dt className="text-sm text-slate-400">{t('serverDuration')}</dt><dd className="text-slate-300">{completed.result.duration_ms.toLocaleString(i18n.language)} ms</dd></div>
            <div className="min-w-0 sm:col-span-2"><dt className="text-sm text-slate-400">{t('currentServer')}</dt><dd className="break-words font-mono text-sm text-slate-300">{completed.result.server_version}</dd></div>
          </dl>
          <details className="min-w-0 border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-sm text-emerald-300">{t('diagnostics')}</summary>
            <p className="mt-2 text-sm text-slate-300">{t('diagnosticsHelp')}</p>
            <pre tabIndex={0} aria-label={t('diagnostics')} className="admin-diagnostics mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(completed.result.diagnostics, null, 2)}</pre>
          </details>
          <details className="min-w-0 border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-sm text-emerald-300">{t('context')}</summary>
            <pre tabIndex={0} aria-label={t('context')} className="admin-diagnostics mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words">{completed.result.context || t('noContext')}</pre>
          </details>
          <details className="min-w-0 border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-sm text-emerald-300">{t('queryPlan')}</summary>
            <pre tabIndex={0} aria-label={t('queryPlan')} className="admin-diagnostics mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words">{completed.result.plan === null ? t('noPlan') : JSON.stringify(completed.result.plan, null, 2)}</pre>
          </details>
        </article> : <div className={`${cardClass} text-sm text-slate-300`}><p>{busy ? t('waiting') : t('emptyResult')}</p></div>}
      </div>
      </div>
      </div>
    </section>
  );
}
