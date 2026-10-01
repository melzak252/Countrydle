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

  const refresh = useCallback(() => setRefreshVersion((version) => version + 1), []);
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const dateLocale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';

  return (
    <section className="space-y-5 animate-message" aria-labelledby="admin-suggestions-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="admin-suggestions-heading" className="font-serif text-xl text-sand-100">{t('adminSuggestions.title')}</h2>
          <p className="mt-1 text-sm text-sand-100/60">{t('adminSuggestions.total', { count: total })}</p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={isLoading}
          className="flex items-center justify-center gap-2 self-start rounded-sm border border-white/10 bg-obsidian-900 px-3 py-2 text-xs font-semibold text-sand-100 transition-colors hover:bg-white/5 disabled:cursor-wait disabled:opacity-60"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
          {t('adminSuggestions.refresh')}
        </button>
      </div>

      {isLoading ? (
        <p role="status" className="rounded-sm border border-white/10 bg-obsidian-900 p-6 text-sm text-sand-100/65">{t('adminSuggestions.loading')}</p>
      ) : error ? (
        <div role="alert" className="rounded-sm border border-red-400/20 bg-red-400/5 p-6 text-sm text-red-200">
          <p>{t('adminSuggestions.error')}</p>
          <button type="button" onClick={refresh} className="mt-3 rounded-sm border border-red-300/30 px-3 py-2 font-medium hover:bg-red-300/10">{t('adminSuggestions.retry')}</button>
        </div>
      ) : total === 0 ? (
        <p className="rounded-sm border border-white/10 bg-obsidian-900 p-6 text-sm text-sand-100/65">{t('adminSuggestions.empty')}</p>
      ) : (
        <div className="space-y-3">
          {items.map((suggestion) => {
            const createdAt = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(suggestion.created_at)
              ? suggestion.created_at
              : `${suggestion.created_at}Z`;
            return (
              <article key={suggestion.id} className="min-w-0 space-y-3 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="rounded-sm border border-emerald-400/25 bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-300">{t(`suggestion.topics.${suggestion.topic}`)}</span>
                    <span className="text-xs text-sand-100/60">{suggestion.reporter_username || t('adminSuggestions.guest')}</span>
                  </div>
                  <time dateTime={createdAt} className="shrink-0 text-xs text-sand-100/55">
                    {new Intl.DateTimeFormat(dateLocale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(createdAt))}
                  </time>
                </div>
                {(suggestion.name || suggestion.email) && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-sand-100/60">
                    {suggestion.name && <span>{t('adminSuggestions.name')}: <span className="text-sand-100/85">{suggestion.name}</span></span>}
                    {suggestion.email && <span>{t('adminSuggestions.email')}: <a href={`mailto:${suggestion.email}`} className="break-all text-emerald-300 underline underline-offset-2">{suggestion.email}</a></span>}
                  </div>
                )}
                <p className="whitespace-pre-wrap break-words text-sm leading-6 text-sand-100/85">{suggestion.message}</p>
              </article>
            );
          })}

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 text-xs text-sand-100/65">
            <span>{t('adminSuggestions.page', { page, pageCount })}</span>
            <div className="flex gap-2">
              <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1 || isLoading} className="rounded-sm border border-white/10 px-3 py-2 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40">{t('adminSuggestions.previous')}</button>
              <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page >= pageCount || isLoading} className="rounded-sm border border-white/10 px-3 py-2 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40">{t('adminSuggestions.next')}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
