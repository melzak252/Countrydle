import { useState } from 'react';
import { authService } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { toast } from 'react-hot-toast';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await authService.register({ username, email, password });
      toast.success('Registration successful! Please login.');
      navigate('/login');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 p-8 rounded-xl shadow-xl">
        <h2 className="text-2xl font-bold mb-6 text-center">Create Account</h2>
        
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
            <label className="block text-sm font-medium text-zinc-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
            {loading ? <Loader2 className="animate-spin" size={20} /> : 'Sign Up'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-zinc-600">
          By signing up, you agree to our{' '}
          <Link to="/terms" className="underline hover:text-zinc-400 transition-colors">Terms of Service</Link>
          {' '}and{' '}
          <Link to="/privacy-policy" className="underline hover:text-zinc-400 transition-colors">Privacy Policy</Link>.
        </p>

        <p className="mt-6 text-center text-sm text-zinc-500">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-500 hover:text-blue-400">
            Login
          </Link>
        </p>
      </div>
    </div>
  );
}
