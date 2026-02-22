import { useState, useEffect } from 'react';
import { gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
import { Loader2, Calendar, Globe, Map, Flag, MapPin } from 'lucide-react';
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
    { id: 'powiat', label: 'Powiaty', icon: Map },
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
    <div className="max-w-2xl mx-auto pb-20 px-4">
      <div className="flex items-center justify-center gap-3 mb-8">
        <Calendar className="text-blue-500" size={40} />
        <h2 className="text-3xl font-bold">{t('archive.title')}</h2>
      </div>

      <div className="flex justify-center gap-2 mb-8 flex-wrap">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setGameType(tab.id as GameType)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-full transition-all border",
              gameType === tab.id 
                ? "bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-900/20" 
                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            )}
          >
            <tab.icon size={16} />
            <span className="font-medium">{tab.label}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center p-20"><Loader2 className="animate-spin text-blue-500" size={48} /></div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
          <table className="w-full text-left">
            <thead className="bg-zinc-800/50 text-zinc-400 border-b border-zinc-800">
              <tr>
                 <th className="px-6 py-4 font-medium">{t('archive.date')}</th>
                 <th className="px-6 py-4 font-medium text-right">{t('archive.answer')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {history.map((entry: any, index: number) => (
                <tr key={index} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-6 py-4 text-zinc-300 font-mono">
                    {entry.date}
                  </td>
                  <td className="px-6 py-4 text-right font-bold text-white">
                    {getEntityName(entry)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {history.length === 0 && (
              <div className="p-8 text-center text-zinc-500">
               {t('archive.empty')}
             </div>
          )}
        </div>
      )}
    </div>
  );
}
