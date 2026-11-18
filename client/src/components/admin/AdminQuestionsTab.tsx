import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isAxiosError } from 'axios';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2, RefreshCw, Search, ShieldAlert, Sparkles, Trash2, User as UserIcon, UserX, X } from 'lucide-react';
import { adminService } from '../../services/api';
import type { AdminQuestionItem } from '../../types';

export interface AdminQuestionsTabProps {
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
  initialMode?: string;
  initialSearch?: string;
}

const MODES = [
  ['all', 'allModes'], ['countrydle', 'modeCountries'], ['powiatdle', 'modePowiaty'],
  ['us_statedle', 'modeStates'], ['wojewodztwodle', 'modeVoivodeships'], ['continental', 'modeContinental'],
] as const;
const SOURCES = [['all', 'allSources'], ['fallback', 'sourceFallback'], ['local_kb', 'sourceLocal'], ['invalid', 'sourceInvalid']] as const;
const ANSWERS = [['all', 'allAnswers'], ['yes', 'yes'], ['no', 'no'], ['invalid', 'invalid']] as const;
const PAGE_LIMIT = 30;
const panelBaseClass = 'rounded-md border p-4';
const panelClass = `${panelBaseClass} border-app-border bg-app-surface text-app-text`;
const controlClass = 'min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-3 py-2 text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonBaseClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonClass = `${buttonBaseClass} border-app-border bg-app-surface-muted text-app-text hover:border-app-accent-hover hover:bg-app-surface-raised`;
const dangerButtonClass = `${buttonBaseClass} border-rose-300 bg-rose-50 text-rose-800 hover:border-rose-400 hover:bg-rose-100`;
const badgeBaseClass = 'inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium';
const badgeClass = `${badgeBaseClass} border-app-border bg-app-surface-muted text-app-text-secondary`;
const successBadgeClass = `${badgeBaseClass} border-emerald-300 bg-emerald-50 text-emerald-800`;
const warningBadgeClass = `${badgeBaseClass} border-amber-300 bg-amber-50 text-amber-900`;
const errorBadgeClass = `${badgeBaseClass} border-rose-300 bg-rose-50 text-rose-800`;
const metaClass = 'text-xs leading-5 text-app-text-muted';
const questionClass = 'break-words text-base leading-6 text-app-text [overflow-wrap:anywhere]';
const diagnosticsClass = 'max-w-full overflow-auto whitespace-pre-wrap break-words rounded-sm border border-app-border bg-app-surface-muted p-3 font-mono text-xs leading-5 text-app-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus';
const tableClass = 'w-full table-fixed border-collapse text-left text-sm leading-6 [&_th]:border-b [&_th]:border-app-border [&_th]:p-3 [&_th]:text-left [&_th]:font-semibold [&_th]:text-app-text-secondary [&_td]:border-b [&_td]:border-app-border [&_td]:p-3 [&_td]:align-top';
const pagerClass = 'flex flex-wrap items-center justify-between gap-3';


export const AdminQuestionsTab: React.FC<AdminQuestionsTabProps> = ({ onTestInQA, initialMode = 'all', initialSearch = '' }) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState(initialMode);
  const [search, setSearch] = useState(initialSearch);
  const [debouncedSearch, setDebouncedSearch] = useState(initialSearch);
  const [date, setDate] = useState('');
  const [source, setSource] = useState('all');
  const [answer, setAnswer] = useState('all');
  const [hasReport, setHasReport] = useState(false);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AdminQuestionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [invalidatingId, setInvalidatingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [retryVersion, setRetryVersion] = useState(0);
  const [isWide, setIsWide] = useState(false);
  const requestSequence = useRef(0);
  const mounted = useRef(false);
  const generatedId = useId().replace(/:/g, '');
  const locale = 'en-US';
  const queryKey = JSON.stringify([mode, debouncedSearch.trim(), date, source, answer, hasReport, page]);
  const [resultQueryKey, setResultQueryKey] = useState<string | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; requestSequence.current += 1; };
  }, []);

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1280px)');
    const update = () => setIsWide(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const fetchQuestions = useCallback(async () => {
    const requestId = ++requestSequence.current;
    setIsLoading(true);
    setError(null);
    setItems([]);
    setTotal(0);
    try {
      const res = await adminService.getQuestions({
        mode: mode === 'all' ? undefined : mode,
        search: debouncedSearch.trim() || undefined,
        date: date || undefined,
        source: source === 'all' ? undefined : source,
        answer: answer === 'all' ? undefined : answer,
        has_report: hasReport ? true : undefined,
        page,
        limit: PAGE_LIMIT,
      });
      if (!mounted.current || requestId !== requestSequence.current) return;
      setItems(res.items);
      setTotal(res.total);
      setResultQueryKey(queryKey);
    } catch (err) {
      if (!mounted.current || requestId !== requestSequence.current) return;
      console.error('Failed to fetch admin questions:', err);
      setError(isAxiosError(err) && typeof err.response?.data?.detail === 'string' ? err.response.data.detail : t('adminAudit.error'));
      setResultQueryKey(queryKey);
    } finally {
      if (mounted.current && requestId === requestSequence.current) setIsLoading(false);
    }
  }, [mode, debouncedSearch, date, source, answer, hasReport, page, retryVersion, queryKey, t]);

  useEffect(() => { void fetchQuestions(); }, [fetchQuestions]);

  const handleInvalidate = async (item: AdminQuestionItem) => {
    const key = `${item.mode}:${item.id}`;
    if (!window.confirm(t('adminAudit.confirmInvalidate', { id: item.id, target: item.target_name }))) return;
    setInvalidatingId(key);
    setActionMessage(null);
    try {
      const res = await adminService.invalidateQuestionFallback(item.mode, item.id);
      setActionMessage({ type: 'success', text: res.message || t('adminAudit.invalidated') });
      await fetchQuestions();
    } catch (err: unknown) {
      const errMsg = isAxiosError(err) && typeof err.response?.data?.detail === 'string' ? err.response.data.detail : t('adminAudit.invalidateError');
      setActionMessage({ type: 'error', text: errMsg });
    } finally {
      setInvalidatingId(null);
    }
  };

  const clearFilters = () => {
    setMode(initialMode);
    setSearch(initialSearch);
    setDebouncedSearch(initialSearch);
    setDate('');
    setSource('all');
    setAnswer('all');
    setHasReport(false);
    setPage(1);
  };
  const recordKey = (item: AdminQuestionItem) => `${item.mode}:${item.id}`;
  const timestamp = (value?: string | null) => value ? new Date(value).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  const queryPending = search !== debouncedSearch;
  const resultsCurrent = resultQueryKey === queryKey && !queryPending;
  const visibleItems = resultsCurrent ? items : [];
  const visibleTotal = resultsCurrent ? total : 0;
  const visibleError = resultsCurrent ? error : null;
  const queryIsLoading = isLoading || !resultsCurrent;
  const totalPages = Math.ceil(visibleTotal / PAGE_LIMIT) || 1;

  const renderDetails = (item: AdminQuestionItem, contextId: string) => <div className="mt-3 space-y-3 border-t border-app-border pt-3 text-sm leading-6">
    <div><h4 className="font-semibold text-app-text">{t('adminAudit.originalQuestion')}</h4><p className="whitespace-pre-wrap break-words text-app-text-secondary">{item.original_question}</p></div>
    {item.question && item.question !== item.original_question && <div><h4 className="font-semibold text-app-text">{t('adminAudit.rephrasedQuestion')}</h4><p className="whitespace-pre-wrap break-words text-app-text-secondary">{item.question}</p></div>}
    {item.clarification && <div><h4 className="font-semibold text-emerald-900">{t('adminAudit.playerClarification')}</h4><p className="whitespace-pre-wrap break-words font-medium text-emerald-800">{item.clarification}</p></div>}
    <div><h4 className="font-semibold text-app-text">{t('adminAudit.explanation')}</h4><p className="whitespace-pre-wrap break-words text-app-text-secondary">{item.explanation || t('adminAudit.noExplanation')}</p></div>
    <dl className={`${metaClass} grid gap-2 sm:grid-cols-2`}>
      <div><dt>{t('adminAudit.relation')}</dt><dd className="break-words text-app-text">{item.relation || '—'}</dd></div>
      <div><dt>{t('adminAudit.reported')}</dt><dd className="text-app-text">{item.has_report ? t('adminAudit.reportId', { id: item.report_id ?? '—' }) : t('adminCommon.no')}</dd></div>
      <div><dt>{t('adminAudit.gameDate')}</dt><dd className="text-app-text">{item.game_date} · #{item.day_id}</dd></div>
      <div><dt>{t('adminAudit.askedAt')}</dt><dd className="text-app-text">{timestamp(item.asked_at)} · #{item.id}</dd></div>
    </dl>
    {item.context && <details id={contextId} className={panelClass}>
      <summary className={`${buttonClass} w-full cursor-pointer justify-start text-left`}>{t('adminAudit.rawContext')}</summary>
      <pre id={`${contextId}-panel`} tabIndex={0} aria-label={t('adminAudit.rawContext')} className={`${diagnosticsClass} mt-2 max-h-48`}>{item.context}</pre>
    </details>}
  </div>;

  const renderTestAction = (item: AdminQuestionItem) => onTestInQA && <button type="button" onClick={() => onTestInQA({ mode: item.mode, targetName: item.target_name, questionText: item.original_question || item.question || '' })} className={`${buttonClass} inline-flex items-center gap-2`}><Sparkles aria-hidden="true" size={16} /><span>{t('adminAudit.testInQA')}</span></button>;
  const renderInvalidationAction = (item: AdminQuestionItem) => item.source === 'fallback' && <button type="button" disabled={invalidatingId === recordKey(item)} onClick={() => void handleInvalidate(item)} className={`${dangerButtonClass} inline-flex items-center gap-2`}><Trash2 aria-hidden="true" size={16} />{invalidatingId === recordKey(item) ? t('adminCommon.updating') : t('adminAudit.invalidate')}</button>;

  const renderRecordDetails = (item: AdminQuestionItem) => {
    const key = recordKey(item);
    const open = !!expanded[key];
    const detailsId = `${generatedId}-details-${encodeURIComponent(key)}`;
    return <button type="button" aria-expanded={open} aria-controls={detailsId} onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))} className={`${buttonClass} inline-flex items-center gap-2`}>
      {open ? <ChevronDown aria-hidden="true" size={16} /> : <ChevronRight aria-hidden="true" size={16} />}{open ? t('adminAudit.hideDetails') : t('adminAudit.details')}
    </button>;
  };

  const renderAnswer = (item: AdminQuestionItem) => <span className={!item.valid ? warningBadgeClass : item.answer === true ? successBadgeClass : badgeClass}>
    {!item.valid ? t('adminAudit.invalid') : item.answer === true ? t('adminAudit.yes') : item.answer === false ? t('adminAudit.no') : t('adminCommon.noAnswer')}
  </span>;
  const renderSource = (item: AdminQuestionItem) => <div className="space-y-1"><span className={badgeClass}>{item.source === 'local_kb' ? t('adminAudit.sourceLocalLong') : item.source === 'fallback' ? t('adminAudit.sourceFallbackLong') : t('adminAudit.sourceInvalidLong')}</span>{item.has_report && <span className={`${errorBadgeClass} inline-flex items-center gap-1`}><ShieldAlert aria-hidden="true" size={14} />{t('adminAudit.reportId', { id: item.report_id ?? '—' })}</span>}</div>;
  const renderQuestionSummary = (item: AdminQuestionItem) => <div className="space-y-1">
    <p className={`${questionClass} line-clamp-3`}>{item.original_question}</p>
    {item.clarification && <p className="line-clamp-2 break-words text-xs font-medium text-emerald-800">{item.clarification}</p>}
  </div>;
  return <div className="space-y-4 text-app-text">

    {actionMessage && <div role={actionMessage.type === 'error' ? 'alert' : 'status'} className={`${panelBaseClass} flex items-start justify-between gap-3 ${actionMessage.type === 'success' ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : 'border-rose-300 bg-rose-50 text-rose-800'}`}>
      <div className="flex items-center gap-2">{actionMessage.type === 'success' ? <CheckCircle2 aria-hidden="true" size={18} /> : <AlertTriangle aria-hidden="true" size={18} />}{actionMessage.text}</div>
      <button type="button" aria-label={t('adminAudit.invalidationDismiss')} onClick={() => setActionMessage(null)} className={`${buttonClass} px-2`}><X aria-hidden="true" size={16} /></button>
    </div>}

    <section className={panelClass} aria-label={t('adminAudit.search')}>
      <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 lg:grid-cols-4">
        <label className="min-w-0 min-[360px]:col-span-2 lg:col-span-4"><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.search')}</span><span className={`${metaClass} block`}>{t('adminAudit.searchHint')}</span><span className="relative mt-1 block"><Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" size={18} /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('adminAudit.searchHint')} className={`${controlClass} pl-10`} /></span></label>
        <label><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.mode')}</span><select value={mode} onChange={event => { setMode(event.target.value); setPage(1); }} className={controlClass}>{MODES.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
        <label><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.date')}</span><input type="date" value={date} onChange={event => { setDate(event.target.value); setPage(1); }} className={controlClass} /></label>
        <label><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.source')}</span><select value={source} onChange={event => { setSource(event.target.value); setPage(1); }} className={controlClass}>{SOURCES.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
        <label><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.answer')}</span><select value={answer} onChange={event => { setAnswer(event.target.value); setPage(1); }} className={controlClass}>{ANSWERS.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm text-app-text-secondary"><input type="checkbox" checked={hasReport} onChange={event => { setHasReport(event.target.checked); setPage(1); }} className="h-4 w-4 accent-app-accent" />{t('adminAudit.reportedOnly')}</label>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => void fetchQuestions()} disabled={queryIsLoading} className={`${buttonClass} inline-flex items-center gap-2`}><RefreshCw aria-hidden="true" size={16} />{t('adminAudit.refresh')}</button><button type="button" onClick={clearFilters} className={buttonClass}>{t('adminAudit.clearFilters')}</button></div>
      </div>
    </section>
    <section className={`${panelClass} overflow-hidden`} aria-label={t('adminAudit.auditLog')}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-border p-4">
        <h2 className="text-lg font-semibold text-app-text">{t('adminAudit.auditLog')}</h2>
        {!queryIsLoading && !visibleError && <p className={metaClass}>{visibleTotal === 1 ? t('adminAudit.recordSingular', { count: visibleTotal }) : t('adminAudit.records', { count: visibleTotal })}</p>}
        {queryIsLoading && <p role="status" className={`${metaClass} inline-flex items-center gap-2`}><Loader2 aria-hidden="true" size={16} className="animate-spin" />{t('adminAudit.querying')}</p>}
      </div>
      {visibleError ? <div role="alert" className="p-5 text-rose-800"><p>{visibleError}</p><button type="button" onClick={() => setRetryVersion(value => value + 1)} disabled={queryIsLoading} className={`${buttonClass} mt-3`}>{t('adminAudit.retry')}</button></div>
        : queryIsLoading ? <p role="status" className="p-8 text-center text-app-text-secondary"><Loader2 aria-hidden="true" size={20} className="mx-auto mb-2 animate-spin text-app-accent" />{t('adminAudit.loading')}</p>
        : visibleItems.length === 0 ? <p className="p-8 text-center text-app-text-secondary">{t('adminAudit.empty')}</p>
        : isWide ? <div className="overflow-x-auto"><table className={tableClass}><thead><tr><th className="w-[25%]">{t('adminAudit.question')}</th><th className="w-[12%]">{t('adminAudit.answer')}</th><th className="w-[18%]">{t('adminAudit.source')}</th><th className="w-[15%]">{t('adminAudit.target')}</th><th className="w-[15%]">{t('adminAudit.player')}</th><th className="w-[15%]">{t('adminAudit.actions')}</th></tr></thead><tbody>{visibleItems.map(item => <React.Fragment key={recordKey(item)}><tr>
          <td className="align-top"><div className="space-y-2">{renderQuestionSummary(item)}</div></td>
          <td className="align-top">{renderAnswer(item)}</td><td className="align-top">{renderSource(item)}</td>
          <td className="align-top"><strong className="block break-words text-app-text">{item.target_name}</strong><span className={metaClass}>{item.target_subtitle || item.mode}</span></td>
          <td className="align-top"><span className="flex min-w-0 items-start gap-1">{item.is_guest ? <UserX aria-hidden="true" size={16} className="shrink-0 text-app-text-muted" /> : <UserIcon aria-hidden="true" size={16} className="shrink-0 text-app-text-muted" />}<span className="min-w-0 break-words">{item.username}</span></span><span className={`${metaClass} block`}>{timestamp(item.asked_at)}</span></td>
          <td className="align-top"><div className="flex flex-col items-start gap-2">{renderRecordDetails(item)}{renderTestAction(item)}</div></td>
        </tr><tr key={`${recordKey(item)}:details`} hidden={!expanded[recordKey(item)]}><td id={`${generatedId}-details-${encodeURIComponent(recordKey(item))}`} colSpan={6} className="bg-app-surface-muted">{renderDetails(item, `${generatedId}-context-${encodeURIComponent(recordKey(item))}`)}<div className="mt-3">{renderInvalidationAction(item)}</div></td></tr></React.Fragment>)}</tbody></table></div>
        : <div className="divide-y divide-app-border">{visibleItems.map(item => <article key={recordKey(item)} className="space-y-3 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">{renderQuestionSummary(item)}</div>{renderAnswer(item)}</div>
          <div className="grid gap-3 sm:grid-cols-2"><div><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.source')}</span>{renderSource(item)}</div><div><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.target')}</span><strong className="block break-words text-app-text">{item.target_name}</strong><span className={metaClass}>{item.target_subtitle || item.mode}</span></div><div><span className="block text-sm font-medium text-app-text-secondary">{t('adminAudit.player')}</span><span className="flex min-w-0 items-start gap-1">{item.is_guest ? <UserX aria-hidden="true" size={16} className="shrink-0 text-app-text-muted" /> : <UserIcon aria-hidden="true" size={16} className="shrink-0 text-app-text-muted" />}<span className="min-w-0 break-words">{item.username}</span></span><span className={metaClass}>{timestamp(item.asked_at)}</span></div><div className="flex items-center">{renderRecordDetails(item)}</div></div>
          <div id={`${generatedId}-details-${encodeURIComponent(recordKey(item))}`} hidden={!expanded[recordKey(item)]}>{renderDetails(item, `${generatedId}-context-${encodeURIComponent(recordKey(item))}`)}<div className="mt-3">{renderInvalidationAction(item)}</div></div>
          {renderTestAction(item)}
        </article>)}</div>}
      {!visibleError && !queryIsLoading && totalPages > 1 && <div className={`${pagerClass} border-t border-app-border px-4 py-3`}><span className={metaClass}>{t('adminAudit.page', { page, pages: totalPages })}</span><div className="flex gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))} className={buttonClass}>{t('adminAudit.previous')}</button><button type="button" disabled={page >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))} className={buttonClass}>{t('adminAudit.next')}</button></div></div>}
    </section>
  </div>;
};

export default AdminQuestionsTab;
