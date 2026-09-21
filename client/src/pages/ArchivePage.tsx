import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
import { Loader2, Calendar, Globe, Map, Flag, MapPin, ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/utils';

type GameType = 'country' | 'powiat' | 'us_state' | 'wojewodztwo';

export default function ArchivePage() {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [gameType, setGameType] = useState<GameType>('country');
  const { t } = useTranslation();

  useEffect(() => {
    setLoading(true);
    const fetchHistory = async () => {
        try {
            let data: any = [];
            if (gameType === 'country') {
                const res = await gameService.getHistory();
                data = res.daily_countries || [];
            }
            else if (gameType === 'powiat') data = await powiatService.getHistory();
            else if (gameType === 'us_state') data = await usStateService.getHistory();
            else if (gameType === 'wojewodztwo') data = await wojewodztwoService.getHistory();
            setHistory(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };
    fetchHistory();
  }, [gameType]);

  const tabs = [
    { id: 'country', label: t('tabs.countries'), icon: Globe },
    { id: 'powiat', label: t('tabs.powiaty'), icon: Map },
    { id: 'us_state', label: t('tabs.usStates'), icon: Flag },
    { id: 'wojewodztwo', label: t('tabs.wojewodztwa'), icon: MapPin },
  ];

  const getEntityName = (entry: any) => {
      if (gameType === 'country') return entry.country?.name;
      if (gameType === 'powiat') return entry.powiat?.nazwa;
      if (gameType === 'us_state') return entry.us_state?.name;
      if (gameType === 'wojewodztwo') return entry.wojewodztwo?.nazwa;
      return t('archive.unknown');
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

      <div role="group" aria-label="Game mode" className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            aria-pressed={gameType === tab.id}
            onClick={() => setGameType(tab.id as GameType)}
            className={cn(
              "flex items-center gap-2 rounded-sm border px-3 py-2.5 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400",
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

      {loading ? (
        <div role="status" aria-label="Loading past answers" className="flex justify-center py-20">
          <Loader2 className="animate-spin text-emerald-400" size={28} aria-hidden="true" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-white/10 bg-obsidian-900">
          <div role="region" aria-label="Past answers" tabIndex={0} className="overflow-x-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
            <table className="w-full table-fixed text-left text-sm">
              <caption className="sr-only">Past answers — {tabs.find((tab) => tab.id === gameType)?.label}</caption>
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
