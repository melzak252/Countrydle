import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle2, Database, RefreshCw, Search } from 'lucide-react';
import { adminService } from '../services/api';
import type { CacheStats } from '../types';

const REFRESH_INTERVAL_MS = 15_000;
const numberFormat = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 });
const timeFormat = new Intl.DateTimeFormat('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const cardClass = 'min-w-0 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-6';

export default function CacheStatsPanel() {
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
  const occupancy = stats && stats.max_size > 0 ? stats.size / stats.max_size * 100 : 0;
  const metrics = stats ? [
    { label: 'Skuteczność (hit-rate)', value: lookups ? `${numberFormat.format(stats.hit_ratio_percent)}%` : '—', detail: lookups ? `${numberFormat.format(lookups)} odczytów cache` : 'Brak odczytów cache', icon: Activity },
    { label: 'Trafienia', value: numberFormat.format(stats.hits), detail: 'Znaleziono gotowy plan pytania.', icon: CheckCircle2 },
    { label: 'Pudła (misses)', value: numberFormat.format(stats.misses), detail: 'Nie znaleziono gotowego planu.', icon: Search },
    { label: 'Zapisane plany', value: numberFormat.format(stats.size), detail: `Limit: ${numberFormat.format(stats.max_size)} planów`, icon: Database },
  ] : [];

  return (
    <section aria-labelledby="cache-stats-title" className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <h2 id="cache-stats-title" className="font-serif text-2xl text-sand-100">Cache planów pytań</h2>
          <p className="max-w-2xl text-sm leading-relaxed text-sand-100/65">
            Cache planera współdzielony przez tryby gry. Przechowuje plany pytań, nie odpowiedzi dla konkretnego celu.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-sand-100/80">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
              className="h-4 w-4 accent-emerald-400"
            />
            Auto-odświeżanie co 15 s
          </label>
          <button
            type="button"
            onClick={refresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-sm border border-white/10 px-4 py-2 text-sm text-sand-100 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw aria-hidden="true" size={16} className={isRefreshing ? 'animate-spin' : ''} />
            {isRefreshing ? 'Odczytywanie…' : 'Odśwież'}
          </button>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-sand-100/60">
        Dane z jednego procesu backendu.
        {snapshot && <> Ostatni udany odczyt: <time dateTime={snapshot.receivedAt.toISOString()}>{timeFormat.format(snapshot.receivedAt)}</time>.</>}
        {!autoRefresh && ' Automatyczne odświeżanie jest zatrzymane.'}
      </p>

      {error && (
        <div role="alert" className="space-y-1 rounded-sm border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-200">
          <p>Nie udało się pobrać statystyk cache. Użyj przycisku „Odśwież”, aby spróbować ponownie.</p>
          {snapshot && <p>Widoczne wartości pochodzą z ostatniego udanego odczytu i mogą być nieaktualne.</p>}
        </div>
      )}

      {!snapshot && isRefreshing && <p role="status" className="text-sm text-sand-100/65">Pobieranie statystyk cache…</p>}

      {stats && (
        <div aria-busy={isRefreshing} className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {metrics.map(({ label, value, detail, icon: Icon }) => (
              <article key={label} className={`${cardClass} space-y-3`}>
                <div className="flex items-start justify-between gap-3 text-emerald-300">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-sand-100/65">{label}</h3>
                  <Icon aria-hidden="true" size={18} className="shrink-0" />
                </div>
                <p className="break-words text-3xl font-semibold tabular-nums text-sand-100">{value}</p>
                <p className="text-xs leading-relaxed text-sand-100/60">{detail}</p>
              </article>
            ))}
          </div>

          <div className={`${cardClass} space-y-3`}>
            <div className="flex items-center justify-between gap-3">
              <h3 id="cache-occupancy-label" className="text-sm font-semibold">Zapełnienie cache</h3>
              <span className="font-mono text-sm text-emerald-300">{numberFormat.format(occupancy)}%</span>
            </div>
            <div
              role="progressbar"
              aria-labelledby="cache-occupancy-label"
              aria-valuemin={0}
              aria-valuemax={stats.max_size}
              aria-valuenow={stats.size}
              aria-valuetext={`${numberFormat.format(stats.size)} z ${numberFormat.format(stats.max_size)} planów`}
              className="h-2 overflow-hidden rounded-full bg-white/10"
            >
              <div className="h-full rounded-full bg-emerald-400 transition-[width]" style={{ width: `${occupancy}%` }} />
            </div>
            <p className="text-xs leading-relaxed text-sand-100/65">
              Po osiągnięciu limitu nowe plany zastępują te najdawniej używane (LRU). Pełny cache nie oznacza awarii.
            </p>
            {lookups === 0 && <p className="text-sm text-sand-100/80">Nie zarejestrowano jeszcze odczytów cache w tym procesie.</p>}
          </div>
        </div>
      )}

      <div className="grid gap-5 text-sm leading-relaxed text-sand-100/65 md:grid-cols-2">
        <div className="space-y-2">
          <h3 className="font-semibold text-sand-100">Zakres liczników</h3>
          <p>
            Cache jest przechowywany w RAM, bez TTL i bez codziennego resetu. Liczniki obejmują okres od startu procesu lub wyczyszczenia cache.
            Restart zeruje dane. Przy wielu workerach kolejne odczyty mogą pochodzić z różnych procesów — to nie jest suma dla całej instalacji.
          </p>
        </div>
        <div className="space-y-2">
          <h3 className="font-semibold text-sand-100">Jak czytać skuteczność</h3>
          <p>
            Trafienie pomija wywołanie planera, ale dalszy fallback może nadal korzystać z AI. Pudło nie jest równoznaczne z płatnym wywołaniem modelu.
            Testy pytań w panelu admina i pytania w pojedynkach znajomych omijają ten cache. To cache aplikacji, nie cache tokenów Google.
          </p>
        </div>
      </div>
    </section>
  );
}
