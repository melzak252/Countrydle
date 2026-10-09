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
import { createPortal } from 'react-dom';
import CountdownTimer from './CountdownTimer';
import CountrydleLogo from './CountrydleLogo';
import { PrivacySettingsButton } from './PrivacySettingsButton';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const isPl = i18n?.language?.startsWith('pl');
  const [menuLocation, setMenuLocation] = useState<typeof location | null>(null);
  const isMenuOpen = menuLocation === location;
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const homeLinkRef = useRef<HTMLAnchorElement>(null);
  const restoreMenuFocusRef = useRef(true);

  const gameCategories = [
    {
      category: isPl ? 'Świat i gra wieloosobowa' : 'World & multiplayer',
      items: [
        { path: '/game', name: isPl ? 'Mapa świata' : t('header.worldMap', 'World Map'), badge: 'Countrydle' },
        { path: '/flagdle', name: 'Flagdle', badge: isPl ? '12 kart' : '12 Cards' },
        { path: '/friends', name: isPl ? 'Graj ze znajomym' : 'Play with a Friend', badge: '1v1' },
        { path: '/border-hop', name: 'Border Hop', badge: isPl ? 'Nowość' : 'New' },
      ],
    },
    {
      category: isPl ? 'Kontynenty' : 'Continents',
      items: [
        { path: '/europe', name: t('header.europe', 'Europedle'), badge: '47' },
        { path: '/asia', name: t('header.asia', 'Asiadle'), badge: '46' },
        { path: '/africa', name: t('header.africa', 'Africadle'), badge: '54' },
        { path: '/americas', name: t('header.americas', 'Americadle'), badge: '35' },
      ],
    },
    {
      category: isPl ? 'Mapy regionalne' : 'Regional maps',
      items: [
        { path: '/us-states', name: isPl ? 'Stany USA' : t('header.usStates', 'US States'), badge: '50' },
        { path: '/wojewodztwa', name: isPl ? 'Województwa' : t('header.wojewodztwa', 'Voivodeships'), badge: '16' },
        { path: '/powiaty', name: isPl ? 'Powiaty' : t('header.powiaty', 'Counties'), badge: '380' },
      ],
    },
  ];

  const exploreItems = [
    { path: '/archive', name: isPl ? 'Archiwum' : t('header.archive', 'Archive'), icon: Archive },
    { path: '/how-it-works', name: isPl ? 'Jak działają pytania' : t('header.howItWorks', 'How Questions Work'), icon: Cpu },
    { path: '/explore', name: isPl ? 'Przewodnik geograficzny' : 'Geography Guides', icon: BookOpen },
    { path: '/patch-notes', name: isPl ? 'Historia zmian' : t('header.patchNotes', 'Patch notes'), icon: Sparkles },
    ...(user?.is_admin ? [{ path: '/admin', name: isPl ? 'Panel administratora' : 'Admin Dashboard', icon: ShieldCheck }] : []),
  ];

  const aboutItems = [
    { path: '/about', name: isPl ? 'O nas' : t('header.about', 'About'), icon: Info },
    { path: '/faq', name: isPl ? 'Najczęstsze pytania' : t('header.faq', 'FAQ'), icon: HelpCircle },
    { path: '/contact', name: isPl ? 'Sugestie' : t('header.suggestions', 'Suggestions'), icon: Mail },
    { path: '/privacy-policy', name: isPl ? 'Polityka prywatności' : t('footer.privacyPolicy', 'Privacy Policy'), icon: ShieldCheck },
    { path: '/terms', name: isPl ? 'Regulamin' : t('footer.termsOfService', 'Terms of Service'), icon: FileText },
  ];

  const closeMenu = (restoreFocus = true) => {
    restoreMenuFocusRef.current = restoreFocus;
    setMenuLocation(null);
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
    const desktop = window.matchMedia('(min-width: 1280px)');
    const handleDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) {
        restoreMenuFocusRef.current = false;
        setMenuLocation(null);
      }
    };
    desktop.addEventListener('change', handleDesktop);
    return () => desktop.removeEventListener('change', handleDesktop);
  }, []);

  useEffect(() => {
    if (!isMenuOpen) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    const menuButton = menuButtonRef.current;
    const homeLink = homeLinkRef.current;
    if (window.matchMedia('(min-width: 1280px)').matches) {
      homeLink?.focus();
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    closeButtonRef.current?.focus();

    return () => {
      dialog.close();
      dialog.querySelectorAll('details[open]').forEach((details) => details.removeAttribute('open'));
      document.body.style.overflow = previousOverflow;
      const focusTarget = restoreMenuFocusRef.current ? menuButton : homeLink;
      if (focusTarget?.isConnected) focusTarget.focus();
    };
  }, [isMenuOpen]);

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 text-sm transition-colors ${
      isActive ? 'text-emerald-300 font-medium' : 'text-zinc-300 hover:text-white'
    }`;

  const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-11 w-full min-w-0 items-center rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed [overflow-wrap:anywhere] transition-colors ${
      isActive ? 'text-emerald-300 bg-emerald-500/10 font-medium' : 'text-zinc-200 hover:text-sand-50 hover:bg-white/5'
    }`;

  return (
    <header className="sticky top-0 z-[1001] shrink-0 border-b border-white/10 bg-obsidian-950 text-sand-100">
      <div className="mx-auto flex h-14 xl:h-20 max-w-7xl items-center justify-between gap-2 px-3 sm:gap-4 sm:px-6">

        {/* Brand */}
        <Link ref={homeLinkRef} to="/" onClick={() => closeMenu()} className="flex min-h-11 shrink-0 items-center gap-2.5" aria-label="Countrydle">
          <CountrydleLogo size={32} />
          <span className="text-xl font-semibold tracking-tight text-sand-100">
            Countrydle<span className="text-emerald-400">.</span>
          </span>
          <span
            className="hidden xl:inline text-[10px] font-mono tracking-wider uppercase text-zinc-400 border border-zinc-700/60 rounded px-1.5 py-0.5 ml-0.5 select-none"
            title={isPl ? 'Strona w fazie aktywnego rozwoju' : 'Site is in active development'}
          >
            {isPl ? 'W rozwoju' : 'In Dev'}
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav aria-label={isPl ? 'Nawigacja główna' : 'Main navigation'} className="hidden items-center gap-1 xl:flex">
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
              <span>{isPl ? 'Gry' : t('header.games', 'Games')}</span>
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
              <span>{isPl ? 'Odkrywaj' : t('header.explore', 'Explore')}</span>
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
            {isPl ? 'Ranking' : t('header.leaderboard', 'Leaderboard')}
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
              <span>{isPl ? 'O nas' : t('header.about', 'About')}</span>
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
                title={isPl ? 'Zobacz profil' : t('header.viewProfile', 'View Profile')}
              >
                {user?.username}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                aria-label={isPl ? 'Wyloguj się' : t('header.logout', 'Logout')}
                className="p-1.5 text-zinc-400 hover:text-sand-100 transition-colors"
                title={isPl ? 'Wyloguj się' : t('header.logout', 'Logout')}
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
                {isPl ? 'Zaloguj się' : t('header.login', 'Login')}
              </Link>
              <Link
                to="/register"
                className="border border-sand-200/40 px-3 py-1.5 text-sm rounded hover:bg-sand-100 hover:text-obsidian-950 font-medium transition-colors"
              >
                {isPl ? 'Zarejestruj się' : t('header.signUp', 'Sign Up')}
              </Link>
            </div>
          )}
        </div>

        {/* Compact mobile header */}
        <div className="flex shrink-0 items-center xl:hidden">
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => {
              if (window.matchMedia('(min-width: 1280px)').matches) return;
              restoreMenuFocusRef.current = true;
              setMenuLocation(location);
            }}
            aria-expanded={isMenuOpen}
            aria-controls="mobile-navigation"
            aria-haspopup="dialog"
            aria-label={isPl ? 'Menu nawigacyjne' : 'Navigation menu'}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded text-sand-100 hover:bg-white/5 transition-colors"
          >
            <Menu size={22} aria-hidden="true" />
          </button>
        </div>
      </div>

      {createPortal(
        <dialog
          ref={dialogRef}
          id="mobile-navigation"
          aria-labelledby="mobile-navigation-title"
          className="fixed bottom-0 left-auto right-0 top-14 m-0 h-[calc(100dvh-3.5rem)] max-h-none w-full max-w-md flex-col border-0 border-l border-white/10 bg-obsidian-950 p-0 text-sand-100 shadow-2xl open:flex backdrop:bg-black/65"
          onCancel={(event) => {
            event.preventDefault();
            closeMenu();
          }}
          onClose={() => {
            if (!dialogRef.current?.open) setMenuLocation(null);
          }}
          onClick={(event) => {
            if (event.target !== event.currentTarget) return;
            const bounds = event.currentTarget.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
              closeMenu();
            }
          }}
        >
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 px-4 pb-2 pt-[calc(0.5rem+env(safe-area-inset-top))]">
            <h2 id="mobile-navigation-title" className="text-base font-semibold">
              Menu
            </h2>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={() => closeMenu()}
              aria-label={isPl ? 'Zamknij menu' : 'Close menu'}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-zinc-200 transition-colors hover:bg-white/10"
            >
              <X size={22} aria-hidden="true" />
            </button>
          </div>
          <nav
            aria-label={isPl ? 'Nawigacja mobilna' : 'Mobile navigation'}
            className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4"
            onClick={(event) => {
              if ((event.target as HTMLElement).closest('a')) closeMenu();
            }}
          >
            <div className="space-y-1">
              <NavLink
                to="/game"
                className="flex min-h-12 w-full items-center justify-center rounded-lg bg-emerald-400 px-4 py-3 text-center text-base font-semibold leading-snug text-obsidian-950 transition-colors hover:bg-emerald-300"
              >
                {isPl ? 'Zagraj dzisiaj' : 'Play today'}
              </NavLink>
              <NavLink to="/blog" className={mobileLinkClass}>
                {t('header.blog', 'Blog')}
              </NavLink>
              <NavLink to="/leaderboard" className={mobileLinkClass}>
                {isPl ? 'Ranking' : t('header.leaderboard', 'Leaderboard')}
              </NavLink>
            </div>

            <div className="divide-y divide-white/10 border-y border-white/10">
              {gameCategories.map((group) => (
                <details key={group.category} className="group">
                  <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-medium leading-relaxed [&::-webkit-details-marker]:hidden">
                    <span className="min-w-0 [overflow-wrap:anywhere]">{group.category}</span>
                    <ChevronDown size={18} className="shrink-0 text-zinc-400 transition-transform group-open:rotate-180" aria-hidden="true" />
                  </summary>
                  <div className="space-y-1 pb-3">
                    {group.items.map((item) => (
                      <NavLink key={item.path} to={item.path} className={mobileLinkClass}>
                        {item.name}
                      </NavLink>
                    ))}
                  </div>
                </details>
              ))}
              <details className="group">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-medium leading-relaxed [&::-webkit-details-marker]:hidden">
                  <span>{isPl ? 'Przewodniki i archiwum' : 'Guides & archive'}</span>
                  <ChevronDown size={18} className="shrink-0 text-zinc-400 transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <div className="space-y-1 pb-3">
                  {exploreItems.map((item) => (
                    <NavLink key={item.path} to={item.path} className={mobileLinkClass}>
                      {item.name}
                    </NavLink>
                  ))}
                </div>
              </details>
              <details className="group">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-medium leading-relaxed [&::-webkit-details-marker]:hidden">
                  <span>{isPl ? 'Pomoc i prywatność' : 'Help & privacy'}</span>
                  <ChevronDown size={18} className="shrink-0 text-zinc-400 transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <div className="space-y-1 pb-3">
                  {aboutItems.map((item) => (
                    <NavLink key={item.path} to={item.path} className={mobileLinkClass}>
                      {item.name}
                    </NavLink>
                  ))}
                  <div onClickCapture={() => {
                    dialogRef.current?.close();
                    closeMenu();
                  }}>
                    <PrivacySettingsButton className="min-h-11 w-full rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed text-zinc-200 transition-colors hover:bg-white/5 [overflow-wrap:anywhere]" />
                  </div>
                </div>
              </details>
            </div>

            <div className="space-y-1">
              {isAuthenticated ? (
                <>
                  <Link
                    to={`/profile/${user?.username}`}
                    className="flex min-h-11 w-full min-w-0 flex-col justify-center rounded-lg px-3 py-2.5 text-sm leading-relaxed text-emerald-300 transition-colors hover:bg-white/5"
                  >
                    <span className="text-xs text-zinc-400">{isPl ? 'Twój profil' : 'Your profile'}</span>
                    <span className="w-full [overflow-wrap:anywhere]">{user?.username}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed text-zinc-300 transition-colors hover:bg-white/5"
                  >
                    <LogOut size={16} className="shrink-0" aria-hidden="true" />
                    {isPl ? 'Wyloguj się' : t('header.logout', 'Logout')}
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" className="flex min-h-11 w-full items-center rounded-lg px-3 py-2.5 text-sm leading-relaxed text-zinc-200 transition-colors hover:bg-white/5">
                    {isPl ? 'Zaloguj się' : t('header.login', 'Login')}
                  </Link>
                  <Link to="/register" className="flex min-h-11 w-full items-center rounded-lg border border-white/25 px-3 py-2.5 text-sm font-medium leading-relaxed text-sand-100 transition-colors hover:bg-white/5">
                    {isPl ? 'Zarejestruj się' : t('header.signUp', 'Sign Up')}
                  </Link>
                </>
              )}
            </div>
          </nav>
        </dialog>,
        document.body,
      )}
    </header>
  );
}
