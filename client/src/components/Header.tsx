import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { LogOut, User as UserIcon, ChevronDown } from 'lucide-react';
import CountdownTimer from './CountdownTimer';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();

  return (
    <header className="bg-zinc-900 border-b border-zinc-800 text-white">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <Link to="/" className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-teal-400 text-transparent bg-clip-text">
          Countrydle
        </Link>

        <nav className="flex items-center gap-6 text-sm md:text-base">
          <CountdownTimer />
          
          <div className="relative group">
            <button className="flex items-center gap-1 hover:text-blue-400 transition-colors py-2">
              Games <ChevronDown size={16} />
            </button>
            <div className="absolute top-full left-0 w-48 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-2 hidden group-hover:block z-50">
              <Link to="/game" className="block px-4 py-2 hover:bg-zinc-800 hover:text-blue-400 transition-colors">World Map</Link>
              <Link to="/us-states" className="block px-4 py-2 hover:bg-zinc-800 hover:text-indigo-400 transition-colors">US States</Link>
              <Link to="/powiaty" className="block px-4 py-2 hover:bg-zinc-800 hover:text-red-400 transition-colors">Powiaty</Link>
              <Link to="/wojewodztwa" className="block px-4 py-2 hover:bg-zinc-800 hover:text-green-400 transition-colors">Województwa</Link>
            </div>
          </div>
          
          <Link to="/leaderboard" className="hidden sm:block hover:text-blue-400 transition-colors">Leaderboard</Link>
          <Link to="/archive" className="hidden sm:block hover:text-blue-400 transition-colors">Archive</Link>
          
          {isAuthenticated ? (
            <div className="flex items-center gap-4">
              <Link 
                to={`/profile/${user?.username}`} 
                className="flex items-center gap-2 hover:text-blue-400 transition-colors"
                title="View Profile"
              >
                <UserIcon size={18} />
                <span className="font-medium">{user?.username}</span>
              </Link>
              <button 
                onClick={() => logout()}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-800 hover:bg-zinc-700 transition-colors text-sm"
              >
                <LogOut size={16} />
                Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <Link to="/login" className="hover:text-blue-400 transition-colors">Login</Link>
              <Link 
                to="/register" 
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md font-medium transition-colors"
              >
                Sign Up
              </Link>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
