import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { Loader2, User as UserIcon } from 'lucide-react';
import { toast } from 'react-hot-toast';

export default function SetupProfilePage() {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, setUser } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !user?.email) return;

    setLoading(true);
    try {
      await authService.updateProfile({ 
        username: username.trim(),
        email: user.email
      });
      toast.success('Username set successfully!');
      
      if (user) {
        setUser({ ...user, username: username.trim() });
      }
      
      navigate('/game');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to set username.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-900 p-4 shadow-xl sm:p-8">
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-blue-500/20 text-blue-500 rounded-full">
            <UserIcon size={48} />
          </div>
        </div>
        
        <h2 className="text-2xl font-bold mb-2 text-center">Welcome to Countrydle!</h2>
        <p className="text-zinc-400 text-center mb-8">Please choose a nickname to get started.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Nickname</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your nickname"
              className="min-h-11 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-base focus:border-blue-500 focus:outline-none transition-colors"
              required
              minLength={3}
              maxLength={30}
              autoFocus
            />
          </div>
          
          <button
            type="submit"
            disabled={loading || !username.trim()}
            className="flex min-h-11 w-full items-center justify-center rounded-lg bg-blue-600 py-2 font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : 'Start Playing'}
          </button>
        </form>
      </div>
    </div>
  );
}
