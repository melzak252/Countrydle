import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import {
  ChevronDown,
  Menu,
  X,
  LogOut,
  Archive,
  Cpu,
  BookOpen,
  Sparkles,
  ShieldCheck,
  Info,
  HelpCircle,
  Mail,
  FileText,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState, useEffect, useRef } from 'react';
import CountdownTimer from './CountdownTimer';
import CountrydleLogo from './CountrydleLogo';
import { PrivacySettingsButton } from './PrivacySettingsButton';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const isPl = i18n?.language?.startsWith('pl');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  const gameCategories = [
    {
      category: t('header.groupGlobal', 'Global & Multiplayer'),
      items: [
        { path: '/game', name: t('header.worldMap', 'World Map'), badge: 'Countrydle' },
        { path: '/flagdle', name: 'Flagdle', badge: '12 Cards' },
        { path: '/friends', name: isPl ? 'Graj ze znajomym' : 'Play with a Friend', badge: '1v1' },
        { path: '/border-hop', name: isPl ? 'Border Hop' : 'Border Hop', badge: 'New' },
      ],
    },
    {
      category: t('header.groupContinents', 'Continents (8 Qs)'),
      items: [
        { path: '/europe', name: t('header.europe', 'Europedle'), badge: '47' },
        { path: '/asia', name: t('header.asia', 'Asiadle'), badge: '46' },
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
    ['/archive', t('header.archive', 'Archive')],
    ['/how-it-works', t('header.howItWorks', 'How Questions Work')],
    ['/explore', isPl ? 'Przewodnik geograficzny' : 'Geography Guides'],
    ['/patch-notes', t('header.patchNotes', 'Patch notes')],
    ['/about', t('header.about', 'About')],
    ['/faq', t('header.faq', 'FAQ')],
    ['/contact', t('header.suggestions', 'Suggestions')],
    ['/privacy-policy', t('footer.privacyPolicy', 'Privacy Policy')],
    ['/terms', t('footer.termsOfService', 'Terms of Service')],
    ...(user?.is_admin ? [['/admin', 'Admin']] : []),
  ];

  const exploreItems = [
    { path: '/archive', name: t('header.archive', 'Archive'), icon: Archive },
    { path: '/how-it-works', name: t('header.howItWorks', 'How Questions Work'), icon: Cpu },
    { path: '/explore', name: isPl ? 'Przewodnik geograficzny' : 'Geography Guides', icon: BookOpen },
    { path: '/patch-notes', name: t('header.patchNotes', 'Patch notes'), icon: Sparkles },
    ...(user?.is_admin ? [{ path: '/admin', name: 'Admin Dashboard', icon: ShieldCheck }] : []),
  ];

  const aboutItems = [
    { path: '/about', name: t('header.about', 'About'), icon: Info },
    { path: '/faq', name: t('header.faq', 'FAQ'), icon: HelpCircle },
    { path: '/contact', name: t('header.suggestions', 'Suggestions'), icon: Mail },
    { path: '/privacy-policy', name: t('footer.privacyPolicy', 'Privacy Policy'), icon: ShieldCheck },
    { path: '/terms', name: t('footer.termsOfService', 'Terms of Service'), icon: FileText },
  ];

  const closeMenu = (restoreFocus = false) => {
    setIsMenuOpen(false);
    if (restoreFocus) menuButtonRef.current?.focus();
  };

  const handleLogout = async () => {
    closeMenu();
    await logout();
  };

  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target?.closest('details')) {
        document.querySelectorAll('header details[open]').forEach((el) => {
          el.removeAttribute('open');
        });
      }
    };
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  useEffect(() => {
    if (!isMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenu(true);
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isMenuOpen]);

  useEffect(() => {
    setIsMenuOpen(false);
  }, [location.pathname]);

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 text-sm transition-colors ${
      isActive ? 'text-emerald-300 font-medium' : 'text-zinc-300 hover:text-white'
    }`;

  const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2.5 text-sm transition-colors ${
      isActive ? 'text-emerald-300 bg-white/5 font-medium' : 'text-zinc-300 hover:text-sand-50 hover:bg-white/5'
    }`;

  return (
    <header className="sticky top-0 z-[1001] shrink-0 border-b border-white/10 bg-obsidian-950 text-sand-100">
      <div className="mx-auto flex h-14 sm:h-20 max-w-7xl items-center justify-between gap-2 px-3 sm:gap-4 sm:px-6">
        
        {/* Brand with single subtle In Development indicator */}
        <Link to="/" onClick={() => closeMenu()} className="flex shrink-0 items-center gap-2.5" aria-label="Countrydle">
          <CountrydleLogo size={32} />
          <span className="text-xl font-semibold tracking-tight text-sand-100">
            Countrydle<span className="text-emerald-400">.</span>
          </span>
          <span
            className="hidden sm:inline text-[10px] font-mono tracking-wider uppercase text-zinc-400 border border-zinc-700/60 rounded px-1.5 py-0.5 ml-0.5 select-none"
            title={isPl ? 'Strona w fazie aktywnego rozwoju' : 'Site is in active development'}
          >
            {isPl ? 'W rozwoju' : 'In Dev'}
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav aria-label="Main navigation" className="hidden items-center gap-1 xl:flex">
          {/* Games Dropdown */}
          <details
            className="group relative"
            onMouseLeave={(event) => {
              event.currentTarget.open = false;
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.currentTarget.open = false;
                event.currentTarget.querySelector('summary')?.focus();
              }
            }}
          >
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
              <span>{t('header.games', 'Games')}</span>
              <ChevronDown size={13} className="text-zinc-400 group-open:rotate-180 transition-transform duration-150" aria-hidden="true" />
            </summary>
            <div
              className="absolute left-0 top-full mt-1 w-80 divide-y divide-white/10 border border-white/15 bg-obsidian-900 shadow-2xl z-50 rounded-md p-1.5 before:absolute before:-top-3 before:left-0 before:right-0 before:h-3 before:content-['']"
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
                          `flex items-center justify-between gap-1.5 rounded px-2.5 py-1.5 text-xs transition-colors ${
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

          {/* Explore Dropdown */}
          <details
            className="group relative"
            onMouseLeave={(event) => {
              event.currentTarget.open = false;
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.currentTarget.open = false;
                event.currentTarget.querySelector('summary')?.focus();
              }
            }}
          >
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
              <span>{t('header.explore', 'Explore')}</span>
              <ChevronDown size={13} className="text-zinc-400 group-open:rotate-180 transition-transform duration-150" aria-hidden="true" />
            </summary>
            <div
              className="absolute left-0 top-full mt-1 w-52 border border-white/15 bg-obsidian-900 p-1.5 shadow-2xl z-50 rounded-md before:absolute before:-top-3 before:left-0 before:right-0 before:h-3 before:content-['']"
              onClick={(event) => {
                if ((event.target as HTMLElement).closest('a, button')) event.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              <div className="flex flex-col gap-0.5">
                {exploreItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      className={({ isActive }) =>
                        `flex items-center gap-2 rounded px-2.5 py-2 text-xs transition-colors ${
                          isActive
                            ? 'bg-emerald-500/10 text-emerald-300 font-medium'
                            : 'text-sand-100 hover:bg-white/5 hover:text-white'
                        }`
                      }
                    >
                      <Icon size={14} className="text-zinc-400 shrink-0" aria-hidden="true" />
                      <span className="truncate">{item.name}</span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          </details>

          <NavLink to="/leaderboard" className={navLinkClass}>
            {t('header.leaderboard', 'Leaderboard')}
          </NavLink>
          
          <NavLink to="/blog" className={navLinkClass}>
            {t('header.blog', 'Blog')}
          </NavLink>

          {/* About Dropdown */}
          <details
            className="group relative"
            onMouseLeave={(event) => {
              event.currentTarget.open = false;
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.currentTarget.open = false;
                event.currentTarget.querySelector('summary')?.focus();
              }
            }}
          >
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm text-zinc-300 hover:text-white [&::-webkit-details-marker]:hidden">
              <span>{t('header.about', 'About')}</span>
              <ChevronDown size={13} className="text-zinc-400 group-open:rotate-180 transition-transform duration-150" aria-hidden="true" />
            </summary>
            <div
              className="absolute left-0 top-full mt-1 w-52 divide-y divide-white/10 border border-white/15 bg-obsidian-900 shadow-2xl z-50 rounded-md p-1.5 before:absolute before:-top-3 before:left-0 before:right-0 before:h-3 before:content-['']"
              onClick={(event) => {
                if ((event.target as HTMLElement).closest('a, button')) event.currentTarget.closest('details')?.removeAttribute('open');
              }}
            >
              <div className="flex flex-col gap-0.5 pb-1">
                {aboutItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      className={({ isActive }) =>
                        `flex items-center gap-2 rounded px-2.5 py-2 text-xs transition-colors ${
                          isActive
                            ? 'bg-emerald-500/10 text-emerald-300 font-medium'
                            : 'text-sand-100 hover:bg-white/5 hover:text-white'
                        }`
                      }
                    >
                      <Icon size={14} className="text-zinc-400 shrink-0" aria-hidden="true" />
                      <span className="truncate">{item.name}</span>
                    </NavLink>
                  );
                })}
              </div>
              <div className="pt-1 bg-white/[0.02]">
                <PrivacySettingsButton className="flex items-center gap-2 w-full px-2.5 py-1.5 text-left text-xs text-zinc-400 hover:text-sand-50 hover:bg-white/5 transition-colors rounded" />
              </div>
            </div>
          </details>
        </nav>

        {/* Right Section: Bigger Clock & Auth Controls (Desktop) */}
        <div className="hidden items-center gap-4 xl:flex">
          {/* Prominent Next Puzzle / Country Countdown Clock */}
          <CountdownTimer />

          {/* User Profile or Login/Register CTAs */}
          {isAuthenticated ? (
            <div className="flex items-center gap-2 border-l border-white/15 pl-4">
              <Link
                to={`/profile/${user?.username}`}
                className="max-w-28 truncate text-sm text-sand-100 hover:text-emerald-300 transition-colors"
                title={t('header.viewProfile', 'View Profile')}
              >
                {user?.username}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                aria-label={t('header.logout', 'Logout')}
                className="p-1.5 text-zinc-400 hover:text-sand-100 transition-colors"
                title={t('header.logout', 'Logout')}
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3 border-l border-white/15 pl-4">
              <Link
                to="/login"
                className="text-sm text-zinc-300 hover:text-white transition-colors"
              >
                {t('header.login', 'Login')}
              </Link>
              <Link
                to="/register"
                className="border border-sand-200/40 px-3 py-1.5 text-sm rounded hover:bg-sand-100 hover:text-obsidian-950 font-medium transition-colors"
              >
                {t('header.signUp', 'Sign Up')}
              </Link>
            </div>
          )}
        </div>

        {/* Mobile Header: Compact Clock & Hamburger Menu Button */}
        <div className="flex shrink-0 items-center gap-2 xl:hidden">
          <CountdownTimer className="hidden sm:flex text-[11px] px-2 py-1" />
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-expanded={isMenuOpen}
            aria-controls="mobile-navigation"
            aria-label={isPl ? 'Menu nawigacyjne' : 'Navigation menu'}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded text-sand-100 hover:bg-white/5 transition-colors"
          >
            {isMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {isMenuOpen && (
        <nav
          id="mobile-navigation"
          aria-label="Mobile navigation"
          className="max-h-[calc(var(--app-height,100dvh)-3.5rem)] overflow-y-auto overscroll-contain border-t border-white/10 bg-obsidian-950 px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4 xl:hidden"
          onKeyDown={(event) => {
            if (event.key === 'Escape') closeMenu(true);
          }}
        >
          {/* Game Modes Section */}
          <div className="space-y-4 border-b border-white/10 pb-4" onClick={() => closeMenu()}>
            {gameCategories.map((group) => (
              <div key={group.category}>
                <span className="block mb-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                  {group.category}
                </span>
                <div className="grid grid-cols-2 gap-1.5">
                  {group.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      className={({ isActive }) =>
                        `flex min-h-11 items-center justify-between gap-1 rounded px-2.5 py-2 text-sm transition-colors ${
                          isActive
                            ? 'bg-emerald-500/10 text-emerald-300 font-medium'
                            : 'text-zinc-200 hover:bg-white/5 bg-white/[0.02]'
                        }`
                      }
                    >
                      <span className="min-w-0 break-words sm:truncate">{item.name}</span>
                      {item.badge && <span className="hidden text-[10px] text-zinc-400 font-mono sm:inline">{item.badge}</span>}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Secondary Links Grid */}
          <div className="grid grid-cols-2 py-3" onClick={() => closeMenu()}>
            {[
              ['/leaderboard', t('header.leaderboard', 'Leaderboard')],
              ['/blog', t('header.blog', 'Blog')],
              ...more,
            ].map(([path, label]) => (
              <NavLink key={path} to={path} className={({ isActive }) => `${mobileLinkClass({ isActive })} min-h-11`}>
                {label}
              </NavLink>
            ))}
            <PrivacySettingsButton className="min-h-11 px-3 py-2.5 text-left text-sm text-zinc-300 hover:text-sand-50 hover:bg-white/5 transition-colors" />
          </div>

          {/* User Auth Section (Mobile) */}
          <div className="flex items-center justify-between gap-4 border-t border-white/10 pt-4 mt-2">
            {isAuthenticated ? (
              <>
                <Link
                  onClick={() => closeMenu()}
                  to={`/profile/${user?.username}`}
                  className="flex min-h-11 min-w-0 items-center truncate text-sm text-emerald-300 font-medium"
                >
                  {user?.username}
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="min-h-11 px-3 py-2 text-sm text-zinc-400 hover:text-sand-100"
                >
                  {t('header.logout', 'Logout')}
                </button>
              </>
            ) : (
              <>
                <Link
                  onClick={() => closeMenu()}
                  to="/login"
                  className="flex min-h-11 items-center px-3 py-2 text-sm text-zinc-300 hover:text-white"
                >
                  {t('header.login', 'Login')}
                </Link>
                <Link
                  onClick={() => closeMenu()}
                  to="/register"
                  className="flex min-h-11 items-center border border-sand-200/40 px-4 py-2 text-sm hover:bg-sand-100 hover:text-obsidian-950 font-medium rounded transition-colors"
                >
                  {t('header.signUp', 'Sign Up')}
                </Link>
              </>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
