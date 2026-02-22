import { useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useGoogleLogin } from '@react-oauth/google';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      
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
            const user = await authService.googleLogin(tokenResponse.access_token);
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
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 p-8 rounded-xl shadow-xl">
        <h2 className="text-2xl font-bold mb-6 text-center">Login to Countrydle</h2>
        
        {error && (
          <div className="bg-red-900/20 border border-red-500/50 text-red-500 p-3 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-lg transition-colors flex justify-center items-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : 'Login'}
          </button>
        </form>

        <div className="my-6 flex items-center">
            <div className="flex-1 border-t border-zinc-700"></div>
            <span className="px-4 text-zinc-500 text-sm">OR</span>
            <div className="flex-1 border-t border-zinc-700"></div>
        </div>

        <div className="flex justify-center">
             <button
                onClick={() => googleLogin()}
                disabled={loading}
                className="w-full bg-white hover:bg-zinc-200 text-black font-medium py-2 rounded-lg transition-colors flex justify-center items-center disabled:opacity-50 disabled:cursor-not-allowed gap-2"
             >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
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

        <p className="mt-6 text-center text-sm text-zinc-500">
          Don't have an account?{' '}
          <Link to="/register" className="text-blue-500 hover:text-blue-400">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
