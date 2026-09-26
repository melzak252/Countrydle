import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { patchNotesService } from '../services/api';
import type { PatchNotesResponse } from '../types';

const PAGE_SIZE = 10;
const publicationDateFormat = new Intl.DateTimeFormat('en-US', { dateStyle: 'long', timeZone: 'UTC' });

export default function PatchNotesPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [response, setResponse] = useState<{
    page: number;
    retry: number;
    data: PatchNotesResponse | null;
    error: boolean;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  const loading = response?.page !== page || response?.retry !== retry;
  const request = loading ? null : response?.data;
  const error = !loading && response?.error;

  useEffect(() => {
    const controller = new AbortController();
    let current = true;

    patchNotesService.getPatchNotes(page, PAGE_SIZE, controller.signal)
      .then((result) => {
        if (current) setResponse({ page, retry, data: result, error: false });
      })
      .catch(() => {
        if (current) setResponse({ page, retry, data: null, error: true });
      });

    return () => {
      current = false;
      controller.abort();
    };
  }, [page, retry]);

  const totalPages = request ? Math.max(1, Math.ceil(request.total / request.limit)) : 1;

  return (
    <div className="mx-auto max-w-5xl pb-8 text-zinc-300">
      <header className="border-b border-white/10 pb-8 md:pb-10">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
          {t('patchNotes.badge')}
        </p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {t('patchNotes.title')}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          {t('patchNotes.subtitle')}
        </p>
      </header>

      <section aria-labelledby="patch-notes-heading" className="py-8 md:py-10">
        <h2 id="patch-notes-heading" className="sr-only">{t('patchNotes.entries')}</h2>
        {loading && <p role="status" aria-live="polite" className="py-8 text-center text-zinc-400">{t('patchNotes.loading')}</p>}
        {!loading && error && (
          <div role="alert" className="border border-red-400/30 bg-red-950/20 px-5 py-6 text-center">
            <p className="text-sand-100">{t('patchNotes.error')}</p>
            <button
              type="button"
              onClick={() => setRetry((value) => value + 1)}
              className="mt-4 border border-emerald-400/50 px-4 py-2 text-sm font-medium text-emerald-300 transition-colors hover:bg-emerald-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
            >
              {t('patchNotes.retry')}
            </button>
          </div>
        )}
        {!loading && !error && request && request.items.length === 0 && (
          <p role="status" className="border border-white/10 px-5 py-10 text-center text-zinc-400">{t('patchNotes.empty')}</p>
        )}
        {!loading && !error && request && request.items.length > 0 && (
          <>
            <ol className="space-y-5">
              {request.items.map((item) => (
                <li key={item.id}>
                  <article className="min-w-0 border border-white/10 bg-obsidian-900/70 p-5 sm:p-7">
                    <div className="flex min-w-0 flex-col gap-2 border-b border-white/10 pb-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                      <div className="min-w-0">
                        <p className="mb-2 font-mono text-xs font-semibold tracking-wide text-emerald-300">{item.version}</p>
                        <h3 className="break-words text-xl font-semibold leading-snug text-sand-100 sm:text-2xl">{item.title}</h3>
                      </div>
                      <time dateTime={item.published_at} className="shrink-0 text-sm text-zinc-400">
                        {publicationDateFormat.format(new Date(item.published_at))}
                      </time>
                    </div>
                    <p className="mt-4 break-words whitespace-pre-wrap text-sm leading-7 text-zinc-300 sm:text-base">{item.body}</p>
                  </article>
                </li>
              ))}
            </ol>
            {totalPages > 1 && (
              <nav aria-label={t('patchNotes.pagination')} className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  className="border border-white/15 px-4 py-2 text-sm text-sand-100 transition-colors hover:border-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {t('patchNotes.previous')}
                </button>
                <span aria-live="polite" className="text-sm text-zinc-400">{t('patchNotes.page', { page, totalPages })}</span>
                <button
                  type="button"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  className="border border-white/15 px-4 py-2 text-sm text-sand-100 transition-colors hover:border-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {t('patchNotes.next')}
                </button>
              </nav>
            )}
          </>
        )}
      </section>
    </div>
  );
}
