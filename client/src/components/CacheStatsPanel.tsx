import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle2, Database, RefreshCw, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../services/api';
import type { CacheStats } from '../types';

const REFRESH_INTERVAL_MS = 15_000;
const cardClass = 'admin-panel min-w-0 space-y-3';

export default function CacheStatsPanel() {
  const { t, i18n } = useTranslation('translation', { keyPrefix: 'adminCache' });
  const locale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-GB';
  const numberFormat = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const timeFormat = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const [snapshot, setSnapshot] = useState<{ stats: CacheStats; receivedAt: Date } | null>(null);
  const [error, setError] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback(() => {
    setIsRefreshing(true);
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    adminService.getCacheStats(controller.signal)
      .then((stats) => {
        if (cancelled) return;
        setSnapshot({ stats, receivedAt: new Date() });
        setError(false);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsRefreshing(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [requestVersion]);

  useEffect(() => {
    if (!autoRefresh || isRefreshing) return;
    const timer = window.setTimeout(refresh, REFRESH_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [autoRefresh, isRefreshing, refresh]);

  const stats = snapshot?.stats;
  const lookups = stats ? stats.hits + stats.misses : 0;
  const metrics = stats ? [
    { label: t('hitRate'), value: lookups ? `${numberFormat.format(stats.hit_ratio_percent)}%` : '—', detail: lookups ? t('lookups', { count: lookups }) : t('noLookups'), icon: Activity },
    { label: t('hits'), value: numberFormat.format(stats.hits), detail: t('hitsDetail'), icon: CheckCircle2 },
    { label: t('misses'), value: numberFormat.format(stats.misses), detail: t('missesDetail'), icon: Search },
    { label: t('storedPlans'), value: numberFormat.format(stats.size), detail: t('storedPlansDetail'), icon: Database },
  ] : [];

  return (
    <section aria-labelledby="admin-page-title" className="min-w-0 space-y-5">
      <div className="admin-toolbar">
        <label className="flex min-h-11 items-center gap-3 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(event) => setAutoRefresh(event.target.checked)}
            className="h-4 w-4 accent-emerald-400"
          />
          {t('autoRefresh')}
        </label>
        <button type="button" onClick={refresh} disabled={isRefreshing} className="admin-button">
          <RefreshCw aria-hidden="true" size={16} className={isRefreshing ? 'animate-spin' : ''} />
          {isRefreshing ? t('refreshing') : t('refresh')}
        </button>
      </div>

      <p className="admin-meta">
        {t('processScope')}
        {snapshot && <> {t('lastSuccessfulUpdate')} <time dateTime={snapshot.receivedAt.toISOString()}>{timeFormat.format(snapshot.receivedAt)}</time>.</>}
        {!autoRefresh && <> {t('autoRefreshPaused')}</>}
      </p>

      {error && (
        <div role="alert" className="space-y-3 rounded-sm border border-rose-400/40 bg-rose-950/30 p-4 text-sm text-rose-200">
          <p>{t('loadError')}</p>
          {snapshot && <p>{t('staleSnapshot')}</p>}
          <button type="button" className="admin-button" onClick={refresh} disabled={isRefreshing}>{t('retry')}</button>
        </div>
      )}

      {!snapshot && isRefreshing && <p role="status" className="text-sm text-slate-300">{t('loading')}</p>}

      {stats && (
        <div aria-busy={isRefreshing} className="space-y-5">
          <p className="text-sm leading-relaxed text-slate-300">{t('plansNotAnswers')}</p>
          <div className="grid grid-cols-1 gap-4 min-[640px]:grid-cols-2 min-[1280px]:grid-cols-4">
            {metrics.map(({ label, value, detail, icon: Icon }) => (
              <article key={label} className={cardClass}>
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-sm font-medium text-slate-300">{label}</h2>
                  <Icon aria-hidden="true" size={18} className="shrink-0 text-emerald-300" />
                </div>
                <p className="admin-metric break-words tabular-nums">{value}</p>
                <p className="admin-meta">{detail}</p>
              </article>
            ))}
          </div>

          <div className="admin-panel space-y-3">
            <h2 className="text-base font-semibold text-sand-100">{t('storage')}</h2>
            <p className="font-mono text-sm text-emerald-300">{stats.storage.toUpperCase()}</p>
            <p className="text-sm leading-relaxed text-slate-300">{t('storageSummary')}</p>
            {lookups === 0 && <p className="text-sm text-slate-300">{t('noRecordedLookups')}</p>}
          </div>
        </div>
      )}

      <details className="admin-panel text-sm leading-relaxed text-slate-300">
        <summary className="cursor-pointer rounded-sm text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">{t('helpTitle')}</summary>
        <div className="mt-3 max-w-prose space-y-3">
          <p>{t('counterScope')}</p>
          <p>{t('hitRateHelp')}</p>
        </div>
      </details>
    </section>
  );
}
