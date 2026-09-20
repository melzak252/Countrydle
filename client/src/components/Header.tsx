import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { 
  LogOut, 
  User as UserIcon,
  ChevronDown, 
  Menu, 
  X,
  Globe,
  Flag,
  MapPin,
  Map,
  Trophy,
  BookOpen,
  Archive,
  Info,
  HelpCircle,
  Mail,
  ShieldAlert
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import CountdownTimer from './CountdownTimer';
import LanguageSelector from './LanguageSelector';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t } = useTranslation();
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
        <nav className="hidden lg:flex items-center justify-between flex-1 ml-10">
          {/* Left/Center Links */}
          <div className="flex items-center gap-7 text-sm font-medium">
            {/* Games Dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors py-2">
                <Globe size={16} className="text-blue-400" />
                <span>{t('header.games')}</span>
                <ChevronDown size={14} className="text-zinc-500 group-hover:text-zinc-300 transition-transform group-hover:rotate-180 duration-200" />
              </button>
              <div className="absolute top-full left-0 w-60 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl py-2 hidden group-hover:block z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <Link to="/game" className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/80 transition-colors">
                  <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 shrink-0">
                    <Globe size={16} />
                  </div>
                  <div>
                    <div className="font-semibold text-xs text-white">{t('header.worldMap')}</div>
                    <div className="text-[10px] text-zinc-400">195 Sovereign Nations</div>
                  </div>
                </Link>
                <Link to="/us-states" className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/80 transition-colors">
                  <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 shrink-0">
                    <Flag size={16} />
                  </div>
                  <div>
                    <div className="font-semibold text-xs text-white">{t('header.usStates')}</div>
                    <div className="text-[10px] text-zinc-400">50 American States</div>
                  </div>
                </Link>
                <Link to="/powiaty" className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/80 transition-colors">
                  <div className="p-1.5 rounded-lg bg-red-500/10 text-red-400 shrink-0">
                    <MapPin size={16} />
                  </div>
                  <div>
                    <div className="font-semibold text-xs text-white">{t('header.powiaty')}</div>
                    <div className="text-[10px] text-zinc-400">380 Polish Counties</div>
                  </div>
                </Link>
                <Link to="/wojewodztwa" className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/80 transition-colors">
                  <div className="p-1.5 rounded-lg bg-green-500/10 text-green-400 shrink-0">
                    <Map size={16} />
                  </div>
                  <div>
                    <div className="font-semibold text-xs text-white">{t('header.wojewodztwa')}</div>
                    <div className="text-[10px] text-zinc-400">16 Voivodeships</div>
                  </div>
                </Link>
              </div>
            </div>

            {/* Leaderboard */}
            <Link to="/leaderboard" className="flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors">
              <Trophy size={16} className="text-yellow-500" />
              <span>{t('header.leaderboard')}</span>
            </Link>

            {/* Daily Blog */}
            <Link to="/blog" className="flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors">
              <BookOpen size={16} className="text-teal-400" />
              <span>{t('header.blog', 'Blog')}</span>
            </Link>

            {/* More Dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors py-2">
                <span>{t('header.more', 'More')}</span>
                <ChevronDown size={14} className="text-zinc-500 group-hover:text-zinc-300 transition-transform group-hover:rotate-180 duration-200" />
              </button>
              <div className="absolute top-full left-0 w-48 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl py-2 hidden group-hover:block z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <Link to="/archive" className="flex items-center gap-2.5 px-4 py-2 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors">
                  <Archive size={14} className="text-zinc-400" />
                  <span>{t('header.archive')}</span>
                </Link>
                <Link to="/about" className="flex items-center gap-2.5 px-4 py-2 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors">
                  <Info size={14} className="text-zinc-400" />
                  <span>{t('header.about', 'About')}</span>
                </Link>
                <Link to="/faq" className="flex items-center gap-2.5 px-4 py-2 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors">
                  <HelpCircle size={14} className="text-zinc-400" />
                  <span>{t('header.faq', 'FAQ')}</span>
                </Link>
                <Link to="/contact" className="flex items-center gap-2.5 px-4 py-2 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors">
                  <Mail size={14} className="text-zinc-400" />
                  <span>{t('header.contact', 'Contact')}</span>
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className="flex items-center gap-2.5 px-4 py-2 text-xs text-red-400 font-bold hover:bg-red-950/40 transition-colors border-t border-zinc-800 mt-1 pt-2">
                    <ShieldAlert size={14} />
                    <span>Admin Dashboard</span>
                  </Link>
                )}
              </div>
            </div>
          </div>

          {/* Right Utility & Auth Area */}
          <div className="flex items-center gap-3">
            <CountdownTimer />
            <LanguageSelector />

            <div className="h-4 w-px bg-zinc-800 mx-1" />

            {isAuthenticated ? (
              <div className="flex items-center gap-2">
                <Link 
                  to={`/profile/${user?.username}`} 
                  className="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-zinc-800/80 hover:bg-zinc-800 border border-zinc-700/60 hover:border-zinc-600 transition-all text-xs font-semibold text-white"
                  title={t('header.viewProfile')}
                >
                  <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-blue-500 to-teal-500 flex items-center justify-center text-[10px] font-bold text-white shrink-0">
                    {user?.username ? user.username.substring(0, 2).toUpperCase() : 'U'}
                  </div>
                  <span className="max-w-[110px] truncate">{user?.username}</span>
                </Link>
                <button 
                  onClick={handleLogout}
                  className="p-1.5 rounded-lg bg-zinc-800/50 hover:bg-zinc-800 text-zinc-400 hover:text-red-400 transition-colors"
                  title={t('header.logout')}
                >
                  <LogOut size={16} />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link to="/login" className="px-3 py-1.5 text-zinc-300 hover:text-white transition-colors text-xs font-medium">
                  {t('header.login')}
                </Link>
                <Link 
                  to="/register" 
                  className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold text-xs transition-colors shadow-sm"
                >
                  {t('header.signUp')}
                </Link>
              </div>
            )}
          </div>
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
              <Link to="/blog" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 hover:bg-zinc-800 rounded-lg transition-colors">{t('header.blog', 'Blog')}</Link>
              <Link to="/about" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 hover:bg-zinc-800 rounded-lg transition-colors">{t('header.about', 'About')}</Link>
              <Link to="/faq" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 hover:bg-zinc-800 rounded-lg transition-colors">{t('header.faq', 'FAQ')}</Link>
              {user?.is_admin && (
                <Link to="/admin" onClick={() => setIsMenuOpen(false)} className="px-3 py-2 text-red-400 font-bold hover:bg-zinc-800 rounded-lg transition-colors">
                  ADMIN DASHBOARD
                </Link>
              )}
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

