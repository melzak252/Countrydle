import { Link, NavLink } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { Compass, ChevronDown, Menu, X, LogOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import CountdownTimer from './CountdownTimer';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t, i18n } = useTranslation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const gameCategories = [
    {
      category: t('header.groupGlobal', 'Global & Multiplayer'),
      items: [
        { path: '/game', name: t('header.worldMap', 'World Map'), badge: 'Countrydle' },
        { path: '/flagdle', name: 'Flagdle', badge: '12 Cards' },
        { path: '/friends', name: i18n.language.startsWith('pl') ? 'Graj ze znajomym' : 'Play with a Friend', badge: '1v1' },
      ],
    },
    {
      category: t('header.groupContinents', 'Continents (8 Qs)'),
      items: [
        { path: '/europe', name: t('header.europe', 'Europedle'), badge: '47' },
        { path: '/asia', name: t('header.asia', 'Asiadle'), badge: '47' },
        { path: '/africa', name: t('header.africa', 'Africadle'), badge: '54' },
        { path: '/americas', name: t('header.americas', 'Americadle'), badge: '35' },
      ],
    },
    {
      category: t('header.groupRegional', 'Regional Maps'),
      items: [
        { path: '/us-states', name: t('header.usStates', 'US States'), badge: '50' },
        { path: '/wojewodztwa', name: t('header.wojewodztwa', 'Voivodeships'), badge: '16' },
        { path: '/powiaty', name: t('header.powiaty', 'Counties'), badge: '380' },
      ],
    },
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
          <details className="group relative" onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.currentTarget.open = false;
              event.currentTarget.querySelector('summary')?.focus();
            }
          }}>
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-3 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
              {t('header.games')}<ChevronDown size={13} className="group-open:rotate-180 transition-transform" aria-hidden="true" />
            </summary>
            <div
              className="absolute left-0 top-full w-80 divide-y divide-white/10 border border-white/15 bg-obsidian-900 shadow-2xl z-50 rounded-sm"
              onClick={(event) => {
                if ((event.target as HTMLElement).closest('a')) event.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              {gameCategories.map((group) => (
                <div key={group.category} className="p-2">
                  <span className="block px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                    {group.category}
                  </span>
                  <div className={group.items.length > 2 ? 'grid grid-cols-2 gap-1' : 'flex flex-col gap-1'}>
                    {group.items.map((item) => (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                          `flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs transition-colors ${
                            isActive
                              ? 'bg-emerald-500/10 text-emerald-300 font-medium'
                              : 'text-sand-100 hover:bg-white/5 hover:text-white'
                          }`
                        }
                      >
                        <span className="truncate">{item.name}</span>
                        {item.badge && (
                          <span className="shrink-0 text-[10px] text-zinc-400 font-mono">
                            {item.badge}
                          </span>
                        )}
                      </NavLink>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </details>

          <details className="group relative" onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.currentTarget.open = false;
              event.currentTarget.querySelector('summary')?.focus();
            }
          }}>
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-3 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
              {t('header.more', 'More')}<ChevronDown size={13} className="group-open:rotate-180 transition-transform" aria-hidden="true" />
            </summary>
            <div className="absolute left-0 top-full w-48 border border-white/15 bg-obsidian-900 p-1 shadow-xl z-50 rounded-sm" onClick={(event) => {
              if ((event.target as HTMLElement).closest('a')) event.currentTarget.closest('details')?.removeAttribute('open');
            }}>
              {more.map(([path, title]) => <NavLink key={path} to={path} className={linkClass}>{title}</NavLink>)}
            </div>
          </details>
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
        <div className="space-y-4 border-y border-white/10 py-3" onClick={closeMenu}>
          {gameCategories.map((group) => (
            <div key={group.category}>
              <span className="block mb-1.5 font-mono text-[10px] uppercase tracking-widest text-zinc-400">
                {group.category}
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                      `flex items-center justify-between gap-1 rounded-sm px-2.5 py-2 text-xs transition-colors ${
                        isActive ? 'bg-emerald-500/10 text-emerald-300 font-medium' : 'text-zinc-200 hover:bg-white/5 bg-white/[0.02]'
                      }`
                    }
                  >
                    <span className="truncate">{item.name}</span>
                    {item.badge && <span className="text-[10px] text-zinc-400 font-mono">{item.badge}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
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
