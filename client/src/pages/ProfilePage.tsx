import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { gameService, authService } from '../services/api';
import { Loader2, Trophy, Target, Edit2, Check, X } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/utils';

export default function ProfilePage() {
  const { username } = useParams();
  const { user: currentUser, setUser } = useAuthStore();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'countrydle' | 'powiatdle' | 'us_statedle' | 'wojewodztwodle'>('countrydle');
  
  const [isEditing, setIsEditing] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [updateLoading, setUpdateLoading] = useState(false);
  const { t } = useTranslation();

  const isOwnProfile = currentUser?.username === username;

  useEffect(() => {
    if (username) {
      setLoading(true);
      gameService.getUserProfileStats(username)
        .then(data => {
          setStats(data);
          setNewUsername(data.user.username);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [username]);

  const handleUpdateUsername = async () => {
    if (!newUsername.trim() || newUsername === stats.user.username) {
      setIsEditing(false);
      return;
    }

    try {
      setUpdateLoading(true);
      // We need to send both username and email as per the mandatory schema
      await authService.updateProfile({
        username: newUsername.trim(),
        email: currentUser?.email || stats.user.email
      });
      
      toast.success(t('profile.updateSuccess'));
      
      // Update local state
      const updatedUser = { ...stats.user, username: newUsername.trim() };
      setStats({ ...stats, user: updatedUser });
      
      // Update auth store if it's the current user
      if (isOwnProfile && currentUser) {
        setUser({ ...currentUser, username: newUsername.trim() });
      }
      
      setIsEditing(false);
      
      // If username changed, we might want to redirect to the new profile URL
      // but for now just updating the state is enough.
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('profile.updateError'));
    } finally {
      setUpdateLoading(false);
    }
  };

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="animate-spin text-blue-500" size={48} /></div>;

  if (!stats) return <div className="text-center p-20 text-red-500">{t('profile.userNotFound')}</div>;

  const currentStats = stats[activeTab];
  const modeLabels = {
    countrydle: t('tabs.countries'),
    powiatdle: 'Powiaty',
    us_statedle: t('tabs.usStates'),
    wojewodztwodle: t('tabs.wojewodztwa'),
  };

  return (
    <div className="max-w-4xl mx-auto px-4 pb-20">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 mb-8 flex flex-col md:flex-row items-center gap-8 shadow-xl">
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-blue-500 to-teal-500 flex items-center justify-center text-4xl font-bold text-white shadow-lg shrink-0">
          {stats.user.username ? stats.user.username.substring(0, 2).toUpperCase() : '??'}
        </div>
        
        <div className="text-center md:text-left flex-1">
            {isEditing ? (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1 text-xl font-bold focus:outline-none focus:border-blue-500 w-full max-w-xs"
                    autoFocus
                  />
                  <button 
                    onClick={handleUpdateUsername}
                    disabled={updateLoading}
                    className="p-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {updateLoading ? <Loader2 size={20} className="animate-spin" /> : <Check size={20} />}
                  </button>
                  <button 
                    onClick={() => {
                      setIsEditing(false);
                      setNewUsername(stats.user.username);
                    }}
                    className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                  >
                    <X size={20} />
                  </button>
                </div>
                <p className="text-xs text-zinc-500">{t('profile.usernameChangeInfo')}</p>
              </div>
            ) : (
              <div className="flex items-center justify-center md:justify-start gap-3">
                <h2 className="text-3xl font-bold">{stats.user.username || t('profile.anonymous')}</h2>
                {isOwnProfile && (
                  <button 
                    onClick={() => setIsEditing(true)}
                    className="p-1.5 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-lg transition-all"
                    title={t('profile.editNickname')}
                  >
                    <Edit2 size={18} />
                  </button>
                )}
              </div>
            )}
            <p className="text-zinc-400 text-sm mt-1">{t('profile.memberSince', { date: new Date(stats.user.created_at).toLocaleDateString() })}</p>
        </div>
      </div>

      {/* Game Tabs */}
      <div className="flex overflow-x-auto gap-2 mb-6 pb-2">
        {[
          { id: 'countrydle', label: t('tabs.countries') },
          { id: 'powiatdle', label: 'Powiaty' },
          { id: 'us_statedle', label: t('tabs.usStates') },
          { id: 'wojewodztwodle', label: t('tabs.wojewodztwa') }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap",
              activeTab === tab.id 
                ? "bg-blue-600 text-white" 
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-blue-500/20 text-blue-500 rounded-lg">
                <Trophy size={24} />
            </div>
            <div>
                <div className="text-2xl font-bold">{currentStats.points}</div>
                <div className="text-sm text-zinc-500">{t('profile.totalPoints')}</div>
            </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-green-500/20 text-green-500 rounded-lg">
                <Check size={24} />
            </div>
            <div>
                <div className="text-2xl font-bold">{currentStats.wins}</div>
                <div className="text-sm text-zinc-500">{t('profile.totalWins')}</div>
            </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-xl flex items-center gap-4">
            <div className="p-3 bg-purple-500/20 text-purple-500 rounded-lg">
                <Target size={24} />
            </div>
            <div>
                <div className="text-2xl font-bold">{currentStats.games_played}</div>
                <div className="text-sm text-zinc-500">{t('profile.gamesPlayed')}</div>
            </div>
        </div>
      </div>

      <h3 className="text-xl font-bold mb-4">{t('profile.recentGames', { mode: modeLabels[activeTab] })}</h3>
      <div className="space-y-4">
        {currentStats.history && currentStats.history.length > 0 ? (
            currentStats.history.map((game: any, index: number) => (
                <div key={index} className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl flex justify-between items-center">
                    <div>
                        <div className="font-bold">{game.date}</div>
                        <div className="text-sm text-zinc-400">
                             {game.won ? t('profile.won') : t('profile.lost')} - {game.target_name}
                        </div>
                        <div className="text-xs text-zinc-500 mt-1">
                            {t('profile.attempts', { count: game.attempts })}
                        </div>
                    </div>
                    <div className={`text-xl font-bold ${game.won ? 'text-green-500' : 'text-red-500'}`}>
                        {t('profile.points', { points: game.points })}
                    </div>
                </div>
            ))
        ) : (
            <div className="text-center text-zinc-500 py-8">{t('profile.noGames')}</div>
        )}
      </div>
    </div>
  );
}
