import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminSuggestionService } from '../../services/api';
import type { Suggestion } from '../../types';

const PAGE_SIZE = 25;

export default function AdminSuggestionsTab() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);
    setError(false);

    adminSuggestionService.getSuggestions(page, PAGE_SIZE, controller.signal)
      .then((result) => {
        if (!active) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [page, refreshVersion]);

  const dateLocale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';
  const refresh = useCallback(() => setRefreshVersion((version) => version + 1), []);
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const numberFormat = new Intl.NumberFormat(dateLocale);

  return (
    <section className="min-w-0 space-y-5 animate-message" aria-labelledby="admin-page-title">
      <div className="admin-toolbar flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="admin-meta mt-1">{t('adminSuggestions.total', { count: total })}</p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={isLoading}
          className="admin-button self-start"
        >
          <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
          {t('adminSuggestions.refresh')}
        </button>
      </div>

      {isLoading ? (
        <p role="status" className="admin-panel">{t('adminSuggestions.loading')}</p>
      ) : error ? (
        <div role="alert" className="admin-panel border-rose-400/40 text-rose-200">
          <p>{t('adminSuggestions.error')}</p>
          <button type="button" onClick={refresh} className="admin-button admin-button-danger mt-3">{t('adminSuggestions.retry')}</button>
        </div>
      ) : total === 0 ? (
        <p className="admin-panel admin-muted">{t('adminSuggestions.empty')}</p>
      ) : (
        <div className="space-y-3">
          {items.map((suggestion) => {
            const createdAt = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(suggestion.created_at)
              ? suggestion.created_at
              : `${suggestion.created_at}Z`;
            return (
              <article key={suggestion.id} className="admin-panel min-w-0 space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="admin-badge">{t(`suggestion.topics.${suggestion.topic}`)}</span>
                    <span className="text-sm text-slate-300">{suggestion.reporter_username || t('adminSuggestions.guest')}</span>
                  </div>
                  <time dateTime={createdAt} className="admin-meta shrink-0">
                    {new Intl.DateTimeFormat(dateLocale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(createdAt))}
                  </time>
                </div>
                {(suggestion.name || suggestion.email) && (
                  <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-300">
                    {suggestion.name && <span>{t('adminSuggestions.name')}: <span className="break-words text-sand-100">{suggestion.name}</span></span>}
                    {suggestion.email && <span>{t('adminSuggestions.email')}: <a href={`mailto:${suggestion.email}`} className="break-all text-emerald-300 underline underline-offset-2">{suggestion.email}</a></span>}
                  </div>
                )}
                <p className="whitespace-pre-wrap break-words text-sm leading-6 text-sand-100">{suggestion.message}</p>
              </article>
            );
          })}

          <div className="admin-pager flex flex-wrap items-center justify-between gap-3">
            <span className="admin-meta">{t('adminSuggestions.page', { page: numberFormat.format(page), pageCount: numberFormat.format(pageCount) })}</span>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1 || isLoading} className="admin-button">{t('adminSuggestions.previous')}</button>
              <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount || isLoading} className="admin-button">{t('adminSuggestions.next')}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
