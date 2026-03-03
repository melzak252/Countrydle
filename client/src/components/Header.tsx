import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { LogOut, User as UserIcon, ChevronDown, Menu, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import CountdownTimer from './CountdownTimer';
import LanguageSelector from './LanguageSelector';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const toggleMenu = () => setIsMenuOpen(!isMenuOpen);

  const handleLogout = async () => {
    setIsMenuOpen(false);
    await logout();
  };

  return (
    <header className="bg-zinc-900 border-b border-zinc-800 text-white sticky top-0 z-[1001]">
      <div className="container mx-auto px-4 py-3 md:py-4 flex justify-between items-center">
        <Link to="/" className="text-xl md:text-2xl font-bold bg-gradient-to-r from-blue-400 to-teal-400 text-transparent bg-clip-text">
          Countrydle
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-center gap-6 text-sm md:text-base">
          <LanguageSelector />
          <CountdownTimer />
          
          <div className="relative group">
            <button className="flex items-center gap-1 hover:text-blue-400 transition-colors py-2">
              {t('header.games')} <ChevronDown size={16} />
            </button>
            <div className="absolute top-full left-0 w-48 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-2 hidden group-hover:block z-50">
              <Link to="/game" className="block px-4 py-2 hover:bg-zinc-800 hover:text-blue-400 transition-colors">{t('header.worldMap')}</Link>
              <Link to="/us-states" className="block px-4 py-2 hover:bg-zinc-800 hover:text-indigo-400 transition-colors">{t('header.usStates')}</Link>
              <Link to="/powiaty" className="block px-4 py-2 hover:bg-zinc-800 hover:text-red-400 transition-colors">{t('header.powiaty')}</Link>
              <Link to="/wojewodztwa" className="block px-4 py-2 hover:bg-zinc-800 hover:text-green-400 transition-colors">{t('header.wojewodztwa')}</Link>
            </div>
          </div>
          
          <Link to="/leaderboard" className="hover:text-blue-400 transition-colors">{t('header.leaderboard')}</Link>
          <Link to="/archive" className="hover:text-blue-400 transition-colors">{t('header.archive')}</Link>
          
          {isAuthenticated ? (
            <div className="flex items-center gap-4">
              <Link 
                to={`/profile/${user?.username}`} 
                className="flex items-center gap-2 hover:text-blue-400 transition-colors"
                title={t('header.viewProfile')}
              >
                <UserIcon size={18} />
                <span className="font-medium">{user?.username}</span>
              </Link>
              <button 
                onClick={handleLogout}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-800 hover:bg-zinc-700 transition-colors text-sm"
              >
                <LogOut size={16} />
                {t('header.logout')}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <Link to="/login" className="hover:text-blue-400 transition-colors">{t('header.login')}</Link>
              <Link 
                to="/register" 
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md font-medium transition-colors"
              >
                {t('header.signUp')}
              </Link>
            </div>
          )}
        </nav>

        {/* Mobile menu toggle and essential icons */}
        <div className="flex lg:hidden items-center gap-3">
          <CountdownTimer />
          <button 
            onClick={toggleMenu}
            className="p-2 text-zinc-400 hover:text-white transition-colors"
            aria-label="Toggle menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation Menu */}
      {isMenuOpen && (
        <div className="lg:hidden bg-zinc-900 border-t border-zinc-800 absolute w-full left-0 animate-in fade-in slide-in-from-top-4 duration-200 shadow-2xl">
          <div className="flex flex-col p-4 space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-zinc-800">
               <LanguageSelector />
               {isAuthenticated && (
                  <Link 
                    to={`/profile/${user?.username}`} 
                    className="flex items-center gap-2 text-blue-400"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    <UserIcon size={18} />
                    <span className="font-medium">{user?.username}</span>
                  </Link>
               )}
            </div>

            <div className="space-y-2">
              <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest">{t('header.games')}</p>
              <div className="grid grid-cols-2 gap-2">
                <Link to="/game" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">{t('header.worldMap')}</Link>
                <Link to="/us-states" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">{t('header.usStates')}</Link>
                <Link to="/powiaty" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">{t('header.powiaty')}</Link>
                <Link to="/wojewodztwa" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">{t('header.wojewodztwa')}</Link>
              </div>
            </div>

            <div className="flex flex-col space-y-2">
              <Link to="/leaderboard" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 hover:bg-zinc-800 rounded-lg transition-colors">{t('header.leaderboard')}</Link>
              <Link to="/archive" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 hover:bg-zinc-800 rounded-lg transition-colors">{t('header.archive')}</Link>
            </div>

            <div className="pt-4 border-t border-zinc-800 flex flex-col space-y-3">
              {isAuthenticated ? (
                <button 
                  onClick={() => {
                    handleLogout();
                    setIsMenuOpen(false);
                  }}
                  className="flex items-center justify-center gap-2 w-full py-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors text-red-400"
                >
                  <LogOut size={18} />
                  {t('header.logout')}
                </button>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <Link 
                    to="/login" 
                    onClick={() => setIsMenuOpen(false)}
                    className="flex items-center justify-center py-3 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
                  >
                    {t('header.login')}
                  </Link>
                  <Link 
                    to="/register" 
                    onClick={() => setIsMenuOpen(false)}
                    className="flex items-center justify-center py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
                  >
                    {t('header.signUp')}
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

