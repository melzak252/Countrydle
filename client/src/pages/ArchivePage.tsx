import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  gameService,
  flagdleService,
  europeService,
  asiaService,
  africaService,
  americasService,
  powiatService,
  usStateService,
  wojewodztwoService,
} from '../services/api';
import { Loader2, Calendar, Globe, Map, Flag, MapPin, ArrowRight, Compass } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/utils';

type GameType =
  | 'country'
  | 'flagdle'
  | 'europe'
  | 'asia'
  | 'africa'
  | 'americas'
  | 'us_state'
  | 'wojewodztwo'
  | 'powiat';

interface TabItem {
  id: GameType;
  label: string;
  icon: typeof Globe;
}

interface TabGroup {
  name: string;
  items: TabItem[];
}

interface HistoryEntry {
  id: number;
  date: string;
  country?: { name?: string };
  powiat?: { nazwa?: string };
  us_state?: { name?: string };
  wojewodztwo?: { nazwa?: string };
  name?: string;
  nazwa?: string;
}

export default function ArchivePage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [gameType, setGameType] = useState<GameType>('country');
  const { t } = useTranslation();

  useEffect(() => {
    setLoading(true);
    const fetchHistory = async () => {
      try {
        let data: unknown = [];
        if (gameType === 'country') {
          const res = (await gameService.getHistory()) as { daily_countries?: HistoryEntry[] };
          data = res?.daily_countries || [];
        } else if (gameType === 'flagdle') {
          data = await flagdleService.getHistory();
        } else if (gameType === 'europe') {
          data = await europeService.getHistory();
        } else if (gameType === 'asia') {
          data = await asiaService.getHistory();
        } else if (gameType === 'africa') {
          data = await africaService.getHistory();
        } else if (gameType === 'americas') {
          data = await americasService.getHistory();
        } else if (gameType === 'powiat') {
          data = await powiatService.getHistory();
        } else if (gameType === 'us_state') {
          data = await usStateService.getHistory();
        } else if (gameType === 'wojewodztwo') {
          data = await wojewodztwoService.getHistory();
        }
        setHistory(Array.isArray(data) ? (data as HistoryEntry[]) : []);
      } catch (e) {
        console.error(e);
        setHistory([]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [gameType]);

  const groups: TabGroup[] = [
    {
      name: t('archive.groupGlobal', 'Global'),
      items: [
        { id: 'country', label: t('tabs.countries', 'Countries'), icon: Globe },
        { id: 'flagdle', label: t('tabs.flagdle', 'Flagdle'), icon: Flag },
      ],
    },
    {
      name: t('archive.groupContinents', 'Continents'),
      items: [
        { id: 'europe', label: t('tabs.europe', 'Europe'), icon: Compass },
        { id: 'asia', label: t('tabs.asia', 'Asia'), icon: Compass },
        { id: 'africa', label: t('tabs.africa', 'Africa'), icon: Compass },
        { id: 'americas', label: t('tabs.americas', 'Americas'), icon: Compass },
      ],
    },
    {
      name: t('archive.groupRegional', 'Regional'),
      items: [
        { id: 'us_state', label: t('tabs.usStates', 'US States'), icon: Flag },
        { id: 'wojewodztwo', label: t('tabs.wojewodztwa', 'Polish Voivodeships'), icon: MapPin },
        { id: 'powiat', label: t('tabs.powiaty', 'Polish Counties'), icon: Map },
      ],
    },
  ];

  const allTabs = groups.flatMap((g) => g.items);

  const getEntityName = (entry: HistoryEntry) => {
    if (gameType === 'powiat') return entry.powiat?.nazwa || entry.nazwa || t('archive.unknown');
    if (gameType === 'wojewodztwo') return entry.wojewodztwo?.nazwa || entry.nazwa || t('archive.unknown');
    if (gameType === 'us_state') return entry.us_state?.name || entry.name || t('archive.unknown');
    return entry.country?.name || entry.name || t('archive.unknown');
  };

  return (
    <div className="mx-auto min-w-0 max-w-4xl space-y-8 bg-obsidian-950 pb-8">
      <header className="border-b border-white/10 pb-8">
        <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-400">
          <Calendar size={15} aria-hidden="true" />
          Past discoveries
        </div>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">{t('archive.title')}</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          Revisit past answers across every game mode. Open a country to explore its daily recap.
        </p>
      </header>

      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.name} className="space-y-1.5">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              {group.name}
            </span>
            <div role="group" aria-label={group.name} className="flex flex-wrap gap-2">
              {group.items.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  aria-pressed={gameType === tab.id}
                  onClick={() => setGameType(tab.id)}
                  className={cn(
                    "flex items-center gap-2 rounded-sm border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400",
                    gameType === tab.id
                      ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                      : "border-white/10 bg-obsidian-900 text-zinc-400 hover:border-white/20 hover:text-sand-100"
                  )}
                >
                  <tab.icon size={16} aria-hidden="true" />
                  <span className="font-medium">{tab.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {loading ? (
        <div role="status" aria-label="Loading past answers" className="flex justify-center py-20">
          <Loader2 className="animate-spin text-emerald-400" size={28} aria-hidden="true" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-white/10 bg-obsidian-900">
          <div role="region" aria-label="Past answers" tabIndex={0} className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
            <table className="w-full table-fixed text-left text-sm">
              <caption className="sr-only">Past answers — {allTabs.find((tab) => tab.id === gameType)?.label}</caption>
              <thead className="border-b border-white/10 text-xs uppercase tracking-[0.12em] text-zinc-400">
                <tr>
                  <th scope="col" className="w-32 px-4 py-4 font-medium sm:w-44 sm:px-6">{t('archive.date')}</th>
                  <th scope="col" className="px-4 py-4 text-right font-medium sm:px-6">{t('archive.answer')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {history.map((entry, index) => (
                  <tr key={index} className="transition-colors hover:bg-white/[0.02]">
                    <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-zinc-400 sm:px-6">
                      {entry.date}
                    </td>
                    <td className="break-words px-4 py-3.5 text-right font-medium text-sand-100 sm:px-6">
                      {gameType === 'country' ? (
                        <Link
                          to={`/blog/${entry.date}`}
                          className="inline-flex max-w-full items-center gap-2 text-emerald-300 transition-colors hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
                          title="Read Wikipedia trivia and daily recap"
                        >
                          <span className="min-w-0 break-words">{getEntityName(entry)}</span>
                          <ArrowRight size={14} className="shrink-0" aria-hidden="true" />
                        </Link>
                      ) : (
                        getEntityName(entry)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {history.length === 0 && (
            <div className="p-8 text-center text-sm text-zinc-400">
              {t('archive.empty')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
