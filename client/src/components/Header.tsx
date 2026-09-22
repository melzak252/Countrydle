import { Link, NavLink } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { Compass, ChevronDown, Menu, X, LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import CountdownTimer from './CountdownTimer';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t } = useTranslation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const games = [
    ['/game', t('header.worldMap', 'World Map (Countrydle)')],
    ['/europe', t('header.europe', 'Europedle')],
    ['/asia', t('header.asia', 'Asiadle')],
    ['/africa', t('header.africa', 'Africadle')],
    ['/americas', t('header.americas', 'Americadle')],
    ['/us-states', t('header.usStates')],
    ['/powiaty', t('header.powiaty')],
    ['/wojewodztwa', t('header.wojewodztwa')],
  ];
  const more = [
    ['/archive', t('header.archive')],
    ['/about', t('header.about')],
    ['/faq', t('header.faq')],
    ['/contact', t('header.contact')],
    ...(user?.is_admin ? [['/admin', 'Admin']] : []),
  ];
  const closeMenu = () => setIsMenuOpen(false);
  const handleLogout = async () => {
    closeMenu();
    await logout();
  };
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2.5 text-sm transition-colors ${isActive ? 'text-emerald-300 bg-white/5' : 'text-zinc-300 hover:text-sand-50 hover:bg-white/5'}`;

  return (
    <header className="sticky top-0 z-[1001] border-b border-white/10 bg-obsidian-950 text-sand-100">
      <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link to="/" onClick={closeMenu} className="flex shrink-0 items-center gap-2.5" aria-label="Countrydle">
          <Compass size={25} strokeWidth={1.4} className="text-emerald-300" aria-hidden="true" />
          <span className="text-xl font-semibold tracking-tight">Countrydle<span className="text-emerald-300">.</span></span>
        </Link>
        <nav aria-label="Main navigation" className="hidden items-center gap-1 xl:flex">
          {[{ label: t('header.games'), links: games }, { label: t('header.more', 'More'), links: more }].map(({ label, links }) => (
            <details key={label} className="group relative" onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.currentTarget.open = false;
                event.currentTarget.querySelector('summary')?.focus();
              }
            }}>
              <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-3 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
                {label}<ChevronDown size={13} className="group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div className="absolute left-0 top-full w-56 border border-white/15 bg-obsidian-900 p-1 shadow-xl" onClick={(event) => {
                if ((event.target as HTMLElement).closest('a')) event.currentTarget.closest('details')?.removeAttribute('open');
              }}>
                {links.map(([path, title]) => <NavLink key={path} to={path} className={linkClass}>{title}</NavLink>)}
              </div>
            </details>
          ))}
          <NavLink to="/leaderboard" className={linkClass}>{t('header.leaderboard')}</NavLink>
          <NavLink to="/blog" className={linkClass}>{t('header.blog', 'Blog')}</NavLink>
        </nav>
        <div className="hidden items-center gap-3 xl:flex">
          <CountdownTimer />
          {isAuthenticated ? <>
            <Link to={`/profile/${user?.username}`} className="max-w-28 truncate border-l border-white/15 pl-3 text-sm" title={t('header.viewProfile')}>{user?.username}</Link>
            <button type="button" onClick={handleLogout} aria-label={t('header.logout')} className="p-2 text-zinc-400 hover:text-sand-100"><LogOut size={17} /></button>
          </> : <>
            <Link to="/login" className="px-2 py-2 text-sm text-zinc-300 hover:text-white">{t('header.login')}</Link>
            <Link to="/register" className="border border-sand-200/40 px-3 py-2 text-sm hover:bg-sand-100 hover:text-obsidian-950">{t('header.signUp')}</Link>
          </>}
        </div>
        <div className="flex items-center gap-2 xl:hidden">
          <CountdownTimer />
          <button type="button" onClick={() => setIsMenuOpen(!isMenuOpen)} aria-expanded={isMenuOpen} aria-controls="mobile-navigation" aria-label="Navigation menu" className="p-2.5 text-sand-100">
            {isMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>
      {isMenuOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className="max-h-[calc(100dvh-5rem)] overflow-y-auto border-t border-white/10 px-4 pb-5 pt-4 xl:hidden" onKeyDown={(event) => { if (event.key === 'Escape') closeMenu(); }}>
        <div className="mb-4 flex items-center justify-between gap-4">
          <span className="font-mono text-xs uppercase tracking-widest text-zinc-400">{t('header.games')}</span>
        </div>
        <div className="grid grid-cols-2 border-y border-white/10 py-2" onClick={closeMenu}>
          {games.map(([path, label]) => <NavLink key={path} to={path} className={linkClass}>{label}</NavLink>)}
        </div>
        <div className="grid grid-cols-2 py-3" onClick={closeMenu}>
          {[[ '/leaderboard', t('header.leaderboard') ], ['/blog', t('header.blog', 'Blog')], ...more].map(([path, label]) => <NavLink key={path} to={path} className={linkClass}>{label}</NavLink>)}
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-white/10 pt-4">
          {isAuthenticated ? <>
            <Link onClick={closeMenu} to={`/profile/${user?.username}`} className="min-w-0 truncate text-sm text-emerald-300">{user?.username}</Link>
            <button type="button" onClick={handleLogout} className="px-3 py-2 text-sm">{t('header.logout')}</button>
          </> : <>
            <Link onClick={closeMenu} to="/login" className="px-3 py-2 text-sm">{t('header.login')}</Link>
            <Link onClick={closeMenu} to="/register" className="border border-sand-200/40 px-4 py-2 text-sm">{t('header.signUp')}</Link>
          </>}
        </div>
      </nav>}
    </header>
  );
}
