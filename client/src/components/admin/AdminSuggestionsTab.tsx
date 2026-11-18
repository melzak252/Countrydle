import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminSuggestionService } from '../../services/api';
import type { Suggestion } from '../../types';

const PAGE_SIZE = 25;

export default function AdminSuggestionsTab() {
  const { t } = useTranslation();
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

  const dateLocale = 'en-US';
  const refresh = useCallback(() => setRefreshVersion((version) => version + 1), []);
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const numberFormat = new Intl.NumberFormat(dateLocale);

  return (
    <section className="min-w-0 space-y-5 animate-message" aria-labelledby="admin-page-title">
      <div className="flex flex-col gap-3 border-b border-app-border pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mt-1 text-sm text-app-text-muted">{t('adminSuggestions.total', { count: total })}</p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={isLoading}
          className="inline-flex min-h-10 items-center gap-2 self-start rounded-sm border border-app-border bg-app-surface-muted px-3 text-sm text-app-text-secondary transition-colors hover:border-app-accent-hover hover:text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
          {t('adminSuggestions.refresh')}
        </button>
      </div>

      {isLoading ? (
        <p role="status" className="rounded-sm border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminSuggestions.loading')}</p>
      ) : error ? (
        <div role="alert" className="rounded-sm border border-rose-300 bg-rose-50 p-4 text-rose-800">
          <p>{t('adminSuggestions.error')}</p>
          <button type="button" onClick={refresh} className="mt-3 inline-flex min-h-10 items-center rounded-sm border border-rose-300 bg-rose-50 px-3 text-sm font-medium text-rose-800 transition-colors hover:bg-rose-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('adminSuggestions.retry')}</button>
        </div>
      ) : total === 0 ? (
        <p className="rounded-sm border border-app-border bg-app-surface p-4 text-app-text-muted">{t('adminSuggestions.empty')}</p>
      ) : (
        <div className="space-y-3">
          {items.map((suggestion) => {
            const createdAt = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(suggestion.created_at)
              ? suggestion.created_at
              : `${suggestion.created_at}Z`;
            return (
              <article key={suggestion.id} className="min-w-0 space-y-3 rounded-sm border border-app-border bg-app-surface p-4 text-app-text">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="rounded-sm border border-app-accent/30 bg-app-surface-raised px-2 py-1 text-xs font-medium text-app-accent">{t(`suggestion.topics.${suggestion.topic}`)}</span>
                    <span className="text-sm text-app-text-secondary">{suggestion.reporter_username || t('adminSuggestions.guest')}</span>
                  </div>
                  <time dateTime={createdAt} className="shrink-0 text-sm text-app-text-muted">
                    {new Intl.DateTimeFormat(dateLocale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(createdAt))}
                  </time>
                </div>
                {(suggestion.name || suggestion.email) && (
                  <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-app-text-secondary">
                    {suggestion.name && <span>{t('adminSuggestions.name')}: <span className="break-words text-app-text">{suggestion.name}</span></span>}
                    {suggestion.email && <span>{t('adminSuggestions.email')}: <a href={`mailto:${suggestion.email}`} className="break-all text-app-accent underline underline-offset-2 hover:text-app-accent-hover">{suggestion.email}</a></span>}
                  </div>
                )}
                <p className="whitespace-pre-wrap break-words text-sm leading-6 text-app-text">{suggestion.message}</p>
              </article>
            );
          })}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-app-border pt-4">
            <span className="text-sm text-app-text-muted">{t('adminSuggestions.page', { page: numberFormat.format(page), pageCount: numberFormat.format(pageCount) })}</span>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1 || isLoading} className="inline-flex min-h-10 items-center rounded-sm border border-app-border bg-app-surface-muted px-3 text-sm text-app-text-secondary transition-colors hover:border-app-accent-hover hover:text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50">{t('adminSuggestions.previous')}</button>
              <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount || isLoading} className="inline-flex min-h-10 items-center rounded-sm border border-app-border bg-app-surface-muted px-3 text-sm text-app-text-secondary transition-colors hover:border-app-accent-hover hover:text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50">{t('adminSuggestions.next')}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
