import { useState, useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useGoogleLogin } from '@react-oauth/google';
import { toast } from 'react-hot-toast';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    const sessionExpired = localStorage.getItem('session_expired');
    if (sessionExpired === 'true') {
      toast.error('Your session has expired. Please log in again.', {
        duration: 5000,
        icon: '🔒',
      });
      localStorage.removeItem('session_expired');
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {

    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      formData.append('remember_me', String(rememberMe));
      
      const user = await authService.login(formData);
      login(user);
      navigate('/game');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
        try {
            setLoading(true);
            // Use access_token instead of credential (id_token)
            const user = await authService.googleLogin(tokenResponse.access_token, rememberMe);
            login(user);
            navigate('/game');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Google Login failed.');
        } finally {
            setLoading(false);
        }
    },
    onError: () => setError('Google Login Failed'),
  });

  return (
    <div className="mx-auto w-full max-w-md py-4 sm:py-8">
      <div className="w-full">
        <header className="mb-8 border-b border-white/10 pb-7">
          <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">Welcome back</p>
          <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">Login to Countrydle</h1>
          <p className="mt-4 text-base leading-7 text-zinc-400">Continue your daily discoveries and keep your streak going.</p>
        </header>
        
        {error && (
          <div role="alert" className="mb-5 rounded-sm border border-red-400/30 bg-red-400/10 p-4 text-sm leading-6 text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="login-username" className="mb-2 block text-sm font-medium text-sand-100">Username</label>
            <input
              id="login-username"
              autoComplete="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-sm border border-white/15 bg-obsidian-900 px-3 py-3 text-base text-sand-100 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
              required
            />
          </div>
          <div>
            <label htmlFor="login-password" className="mb-2 block text-sm font-medium text-sand-100">Password</label>
            <input
              id="login-password"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border border-white/15 bg-obsidian-900 px-3 py-3 text-base text-sand-100 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
              required
            />
          </div>

          <div>
            <label htmlFor="login-remember-me" className="flex cursor-pointer items-center gap-3 text-sm font-medium text-sand-100">
              <input
                id="login-remember-me"
                name="remember_me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                disabled={loading}
                aria-describedby="login-remember-me-help"
                className="h-4 w-4 accent-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400"
              />
              Remember me
            </label>
            <p id="login-remember-me-help" className="mt-2 text-sm leading-6 text-zinc-400">
              Stay signed in between visits, including with Google. Only use this on a private device.
            </p>
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <><Loader2 aria-hidden="true" className="animate-spin" size={18} /><span>Logging in…</span></> : 'Login'}
          </button>
        </form>

        <div className="my-6 flex items-center">
            <div className="flex-1 border-t border-white/10"></div>
            <span className="px-4 text-zinc-500 text-sm">OR</span>
            <div className="flex-1 border-t border-white/10"></div>
        </div>

        <div className="flex justify-center">
             <button
                onClick={() => googleLogin()}
                disabled={loading}
                className="flex w-full items-center justify-center gap-3 rounded-sm border border-white/15 bg-obsidian-900 px-5 py-3 text-sm font-medium text-sand-100 transition-colors hover:border-white/30 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
             >
                <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24">
                    <path
                        fill="#EA4335"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.24-1.19-.6z"
                    />
                    <path
                        fill="#4285F4"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                </svg>
                Sign in with Google
             </button>
        </div>

        <p className="mt-7 border-t border-white/10 pt-6 text-center text-sm text-zinc-400">
          Don't have an account?{' '}
          <Link to="/register" className="text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 hover:text-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
