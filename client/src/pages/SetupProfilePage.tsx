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
    <div className="flex min-h-[60vh] flex-col items-center justify-center bg-app-canvas text-app-text">
      <div className="w-full max-w-md rounded-md border border-app-border bg-app-surface p-4 sm:p-8">
        
        <h2 className="mb-2 text-center font-serif text-2xl font-semibold text-app-text">Set up your profile</h2>
        <p className="mb-8 text-center text-app-text-secondary">Please choose a nickname to get started.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-app-text-secondary">Nickname</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your nickname"
              className="min-h-11 w-full rounded-sm border border-app-border bg-app-surface-muted px-4 py-2 text-base text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-1 focus:ring-app-focus transition-colors"
              required
              minLength={3}
              maxLength={30}
              autoFocus
            />
          </div>
          
          <button
            type="submit"
            disabled={loading || !username.trim()}
            className="flex min-h-11 w-full items-center justify-center rounded-sm bg-app-accent py-2 font-medium text-app-canvas transition-colors hover:bg-app-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : 'Start Playing'}
          </button>
        </form>
      </div>
    </div>
  );
}
