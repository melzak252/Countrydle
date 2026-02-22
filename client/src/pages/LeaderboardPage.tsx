import { useState, useEffect } from 'react';
import { gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
import { Loader2, Medal, Globe, Map, Flag, MapPin } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/utils';

type GameType = 'country' | 'powiat' | 'us_state' | 'wojewodztwo';

export default function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [gameType, setGameType] = useState<GameType>('country');
  const { t } = useTranslation();

  useEffect(() => {
    setLoading(true);
    const fetchLeaderboard = async () => {
        try {
            let data = [];
            if (gameType === 'country') data = await gameService.getLeaderboard();
            else if (gameType === 'powiat') data = await powiatService.getLeaderboard();
            else if (gameType === 'us_state') data = await usStateService.getLeaderboard();
            else if (gameType === 'wojewodztwo') data = await wojewodztwoService.getLeaderboard();
            setLeaderboard(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };
    fetchLeaderboard();
  }, [gameType]);

  const tabs = [
    { id: 'country', label: t('tabs.countries'), icon: Globe },
    { id: 'powiat', label: 'Powiaty', icon: Map },
    { id: 'us_state', label: t('tabs.usStates'), icon: Flag },
    { id: 'wojewodztwo', label: t('tabs.wojewodztwa'), icon: MapPin },
  ];

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-center gap-3 mb-8">
        <Medal className="text-yellow-500" size={40} />
        <h2 className="text-3xl font-bold">{t('leaderboard.title')}</h2>
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
                <th className="px-6 py-4 font-medium w-16 text-center">#</th>
                <th className="px-6 py-4 font-medium">{t('leaderboard.player')}</th>
                <th className="px-6 py-4 font-medium text-right">{t('leaderboard.points')}</th>
                <th className="px-6 py-4 font-medium text-right">{t('leaderboard.wins')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {leaderboard.map((entry: any, index: number) => (
                <tr key={entry.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-6 py-4 text-center text-zinc-500 font-mono">
                    {index + 1}
                  </td>
                  <td className="px-6 py-4">
                    <Link to={`/profile/${entry.username}`} className="flex items-center gap-3 font-medium hover:text-blue-400 transition-colors">
                      {/* Placeholder Avatar */}
                      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-teal-500 flex items-center justify-center text-xs font-bold text-white">
                        {entry.username.substring(0, 2).toUpperCase()}
                      </div>
                      {entry.username}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-right font-mono text-yellow-500 font-bold">
                    {entry.points}
                  </td>
                  <td className="px-6 py-4 text-right font-mono text-green-500">
                    {entry.wins}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {leaderboard.length === 0 && (
              <div className="p-8 text-center text-zinc-500">
              {t('leaderboard.empty')}
             </div>
          )}
        </div>
      )}
    </div>
  );
}
