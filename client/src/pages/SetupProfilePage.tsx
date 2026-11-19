import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { Loader2 } from 'lucide-react';
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
      toast.success('Username set successfully');
      
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
      <div className="w-full max-w-md rounded-sm border border-app-border bg-app-surface p-4 shadow-xl sm:p-8">
        
        <h2 className="text-2xl font-semibold mb-2 text-center text-app-text">Set up your profile</h2>
        <p className="text-app-text-secondary text-center mb-8">Please choose a nickname to get started.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-app-text-secondary mb-1">Nickname</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your nickname"
              className="min-h-11 w-full rounded-sm border border-app-border bg-app-surface-muted px-4 py-2 text-base text-app-text focus:border-app-accent focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-app-focus transition-colors"
              required
              minLength={3}
              maxLength={30}
              autoFocus
            />
          </div>
          
          <button
            type="submit"
            disabled={loading || !username.trim()}
            className="flex min-h-11 w-full items-center justify-center rounded-sm bg-app-accent py-2 font-medium text-app-canvas transition-colors hover:bg-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : 'Start Playing'}
          </button>
        </form>
      </div>
    </div>
  );
}
