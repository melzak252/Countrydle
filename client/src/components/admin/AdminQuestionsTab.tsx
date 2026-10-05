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

export const AdminQuestionsTab: React.FC<AdminQuestionsTabProps> = ({ onTestInQA, initialMode = 'all', initialSearch = '' }) => {
  const { t, i18n } = useTranslation();
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
  const locale = i18n.language?.toLowerCase().startsWith('pl') ? 'pl-PL' : 'en-US';
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
  const controlClass = 'admin-control min-w-0';
  const recordKey = (item: AdminQuestionItem) => `${item.mode}:${item.id}`;
  const timestamp = (value?: string | null) => value ? new Date(value).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  const queryPending = search !== debouncedSearch;
  const resultsCurrent = resultQueryKey === queryKey && !queryPending;
  const visibleItems = resultsCurrent ? items : [];
  const visibleTotal = resultsCurrent ? total : 0;
  const visibleError = resultsCurrent ? error : null;
  const queryIsLoading = isLoading || !resultsCurrent;
  const totalPages = Math.ceil(visibleTotal / PAGE_LIMIT) || 1;

  const renderDetails = (item: AdminQuestionItem, contextId: string) => <div className="mt-3 border-t border-white/10 pt-3 space-y-3 text-sm leading-6">
    <div><h4 className="font-semibold text-sand-200">{t('adminAudit.originalQuestion')}</h4><p className="whitespace-pre-wrap break-words">{item.original_question}</p></div>
    {item.question && item.question !== item.original_question && <div><h4 className="font-semibold text-sand-200">{t('adminAudit.rephrasedQuestion')}</h4><p className="whitespace-pre-wrap break-words">{item.question}</p></div>}
    <div><h4 className="font-semibold text-sand-200">{t('adminAudit.explanation')}</h4><p className="whitespace-pre-wrap break-words">{item.explanation || t('adminAudit.noExplanation')}</p></div>
    <dl className="admin-meta grid gap-2 sm:grid-cols-2">
      <div><dt>{t('adminAudit.relation')}</dt><dd className="break-words text-sand-200">{item.relation || '—'}</dd></div>
      <div><dt>{t('adminAudit.reported')}</dt><dd className="text-sand-200">{item.has_report ? t('adminAudit.reportId', { id: item.report_id ?? '—' }) : t('adminCommon.no')}</dd></div>
      <div><dt>{t('adminAudit.gameDate')}</dt><dd className="text-sand-200">{item.game_date} · #{item.day_id}</dd></div>
      <div><dt>{t('adminAudit.askedAt')}</dt><dd className="text-sand-200">{timestamp(item.asked_at)} · #{item.id}</dd></div>
    </dl>
    {item.context && <details id={contextId} className="admin-panel">
      <summary className="admin-button admin-row-button cursor-pointer font-medium text-sand-200">{t('adminAudit.rawContext')}</summary>
      <pre id={`${contextId}-panel`} tabIndex={0} aria-label={t('adminAudit.rawContext')} className="admin-diagnostics mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words">{item.context}</pre>
    </details>}
  </div>;

  const renderTestAction = (item: AdminQuestionItem) => onTestInQA && <button type="button" onClick={() => onTestInQA({ mode: item.mode, targetName: item.target_name, questionText: item.original_question || item.question || '' })} className="admin-button inline-flex items-center gap-2"><Sparkles aria-hidden="true" size={16} /><span>{t('adminAudit.testInQA')}</span></button>;
  const renderInvalidationAction = (item: AdminQuestionItem) => item.source === 'fallback' && <button type="button" disabled={invalidatingId === recordKey(item)} onClick={() => void handleInvalidate(item)} className="admin-button admin-button-danger inline-flex items-center gap-2"><Trash2 aria-hidden="true" size={16} />{invalidatingId === recordKey(item) ? t('adminCommon.updating') : t('adminAudit.invalidate')}</button>;

  const renderRecordDetails = (item: AdminQuestionItem) => {
    const key = recordKey(item);
    const open = !!expanded[key];
    const detailsId = `${generatedId}-details-${encodeURIComponent(key)}`;
    return <button type="button" aria-expanded={open} aria-controls={detailsId} onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))} className="admin-button admin-row-button inline-flex items-center gap-2">
      {open ? <ChevronDown aria-hidden="true" size={16} /> : <ChevronRight aria-hidden="true" size={16} />}{open ? t('adminAudit.hideDetails') : t('adminAudit.details')}
    </button>;
  };

  const renderAnswer = (item: AdminQuestionItem) => <span className={`admin-badge ${!item.valid ? 'admin-answer-invalid' : item.answer === true ? 'admin-answer-yes' : 'admin-muted'}`}>
    {!item.valid ? t('adminAudit.invalid') : item.answer === true ? t('adminAudit.yes') : item.answer === false ? t('adminAudit.no') : t('adminCommon.noAnswer')}
  </span>;
  const renderSource = (item: AdminQuestionItem) => <div className="space-y-1"><span className="admin-badge">{item.source === 'local_kb' ? t('adminAudit.sourceLocalLong') : item.source === 'fallback' ? t('adminAudit.sourceFallbackLong') : t('adminAudit.sourceInvalidLong')}</span>{item.has_report && <span className="admin-badge admin-outcome-error inline-flex items-center gap-1"><ShieldAlert aria-hidden="true" size={14} />{t('adminAudit.reportId', { id: item.report_id ?? '—' })}</span>}</div>;
  const renderQuestionSummary = (item: AdminQuestionItem) => <p className="admin-question line-clamp-3 break-words">{item.original_question}</p>;

  return <div className="space-y-4">
    {actionMessage && <div role={actionMessage.type === 'error' ? 'alert' : 'status'} className={`admin-panel flex items-start justify-between gap-3 ${actionMessage.type === 'success' ? 'border-emerald-700 text-emerald-200' : 'border-rose-700 text-rose-200'}`}>
      <div className="flex items-center gap-2">{actionMessage.type === 'success' ? <CheckCircle2 aria-hidden="true" size={18} /> : <AlertTriangle aria-hidden="true" size={18} />}{actionMessage.text}</div>
      <button type="button" aria-label={t('adminAudit.invalidationDismiss')} onClick={() => setActionMessage(null)} className="admin-button admin-row-button"><X aria-hidden="true" size={16} /></button>
    </div>}

    <section className="admin-panel" aria-label={t('adminAudit.search')}>
      <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 lg:grid-cols-4">
        <label className="min-w-0 min-[360px]:col-span-2 lg:col-span-4"><span className="block text-sm font-medium text-slate-200">{t('adminAudit.search')}</span><span className="admin-meta block">{t('adminAudit.searchHint')}</span><span className="relative block mt-1"><Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('adminAudit.searchHint')} className={`${controlClass} admin-control-with-icon`} /></span></label>
        <label><span className="block text-sm font-medium text-slate-200">{t('adminAudit.mode')}</span><select value={mode} onChange={event => { setMode(event.target.value); setPage(1); }} className={controlClass}>{MODES.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
        <label><span className="block text-sm font-medium text-slate-200">{t('adminAudit.date')}</span><input type="date" value={date} onChange={event => { setDate(event.target.value); setPage(1); }} className={controlClass} /></label>
        <label><span className="block text-sm font-medium text-slate-200">{t('adminAudit.source')}</span><select value={source} onChange={event => { setSource(event.target.value); setPage(1); }} className={controlClass}>{SOURCES.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
        <label><span className="block text-sm font-medium text-slate-200">{t('adminAudit.answer')}</span><select value={answer} onChange={event => { setAnswer(event.target.value); setPage(1); }} className={controlClass}>{ANSWERS.map(([value, key]) => <option key={value} value={value}>{t(`adminAudit.${key}`)}</option>)}</select></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="inline-flex min-h-11 items-center gap-2 text-sm text-slate-200"><input type="checkbox" checked={hasReport} onChange={event => { setHasReport(event.target.checked); setPage(1); }} className="h-4 w-4 accent-rose-500" />{t('adminAudit.reportedOnly')}</label>
        <div className="flex flex-wrap gap-2"><button type="button" onClick={() => void fetchQuestions()} disabled={queryIsLoading} className="admin-button inline-flex items-center gap-2"><RefreshCw aria-hidden="true" size={16} />{t('adminAudit.refresh')}</button><button type="button" onClick={clearFilters} className="admin-button">{t('adminAudit.clearFilters')}</button></div>
      </div>
    </section>
    <section className="admin-panel overflow-hidden" aria-label={t('adminAudit.auditLog')}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 p-4">
        <h2 className="text-lg font-semibold text-sand-100">{t('adminAudit.auditLog')}</h2>
        {!queryIsLoading && !visibleError && <p className="admin-meta">{visibleTotal === 1 ? t('adminAudit.recordSingular', { count: visibleTotal }) : t('adminAudit.records', { count: visibleTotal })}</p>}
        {queryIsLoading && <p role="status" className="admin-meta inline-flex items-center gap-2"><Loader2 aria-hidden="true" size={16} className="animate-spin" />{t('adminAudit.querying')}</p>}
      </div>
      {visibleError ? <div role="alert" className="p-5 text-rose-200"><p>{visibleError}</p><button type="button" onClick={() => setRetryVersion(value => value + 1)} disabled={queryIsLoading} className="admin-button mt-3">{t('adminAudit.retry')}</button></div>
        : queryIsLoading ? <p role="status" className="p-8 text-center text-slate-300"><Loader2 aria-hidden="true" size={20} className="mx-auto mb-2 animate-spin" />{t('adminAudit.loading')}</p>
        : visibleItems.length === 0 ? <p className="p-8 text-center text-slate-300">{t('adminAudit.empty')}</p>
        : isWide ? <div className="overflow-x-auto"><table className="admin-table w-full table-fixed text-left"><thead><tr><th className="w-[25%]">{t('adminAudit.question')}</th><th className="w-[12%]">{t('adminAudit.answer')}</th><th className="w-[18%]">{t('adminAudit.source')}</th><th className="w-[15%]">{t('adminAudit.target')}</th><th className="w-[15%]">{t('adminAudit.player')}</th><th className="w-[15%]">{t('adminAudit.actions')}</th></tr></thead><tbody>{visibleItems.map(item => <React.Fragment key={recordKey(item)}><tr>
          <td className="align-top"><div className="space-y-2">{renderQuestionSummary(item)}</div></td>
          <td className="align-top">{renderAnswer(item)}</td><td className="align-top">{renderSource(item)}</td>
          <td className="align-top"><strong className="block break-words text-sand-100">{item.target_name}</strong><span className="admin-meta">{item.target_subtitle || item.mode}</span></td>
          <td className="align-top"><span className="flex min-w-0 items-start gap-1">{item.is_guest ? <UserX aria-hidden="true" size={16} className="shrink-0" /> : <UserIcon aria-hidden="true" size={16} className="shrink-0" />}<span className="min-w-0 break-words">{item.username}</span></span><span className="admin-meta block">{timestamp(item.asked_at)}</span></td>
          <td className="align-top"><div className="flex flex-col items-start gap-2">{renderRecordDetails(item)}{renderTestAction(item)}</div></td>
        </tr><tr key={`${recordKey(item)}:details`} hidden={!expanded[recordKey(item)]}><td id={`${generatedId}-details-${encodeURIComponent(recordKey(item))}`} colSpan={6} className="bg-obsidian-950/50">{renderDetails(item, `${generatedId}-context-${encodeURIComponent(recordKey(item))}`)}<div className="mt-3">{renderInvalidationAction(item)}</div></td></tr></React.Fragment>)}</tbody></table></div>
        : <div className="divide-y divide-white/10">{visibleItems.map(item => <article key={recordKey(item)} className="space-y-3 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">{renderQuestionSummary(item)}</div>{renderAnswer(item)}</div>
          <div className="grid gap-3 sm:grid-cols-2"><div><span className="block text-sm font-medium text-slate-200">{t('adminAudit.source')}</span>{renderSource(item)}</div><div><span className="block text-sm font-medium text-slate-200">{t('adminAudit.target')}</span><strong className="block break-words text-sand-100">{item.target_name}</strong><span className="admin-meta">{item.target_subtitle || item.mode}</span></div><div><span className="block text-sm font-medium text-slate-200">{t('adminAudit.player')}</span><span className="flex min-w-0 items-start gap-1">{item.is_guest ? <UserX aria-hidden="true" size={16} className="shrink-0" /> : <UserIcon aria-hidden="true" size={16} className="shrink-0" />}<span className="min-w-0 break-words">{item.username}</span></span><span className="admin-meta">{timestamp(item.asked_at)}</span></div><div className="flex items-center">{renderRecordDetails(item)}</div></div>
          <div id={`${generatedId}-details-${encodeURIComponent(recordKey(item))}`} hidden={!expanded[recordKey(item)]}>{renderDetails(item, `${generatedId}-context-${encodeURIComponent(recordKey(item))}`)}<div className="mt-3">{renderInvalidationAction(item)}</div></div>
          {renderTestAction(item)}
        </article>)}</div>}
      {!visibleError && !queryIsLoading && totalPages > 1 && <div className="admin-pager border-t border-white/10"><span className="admin-meta">{t('adminAudit.page', { page, pages: totalPages })}</span><div className="flex gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))} className="admin-button">{t('adminAudit.previous')}</button><button type="button" disabled={page >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))} className="admin-button">{t('adminAudit.next')}</button></div></div>}
    </section>
  </div>;
};

export default AdminQuestionsTab;
