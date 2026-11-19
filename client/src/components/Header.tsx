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
import { isPrerenderCapture } from '../lib/pageMetadata'
import { primaryGames } from '../lib/gameCatalog';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuthStore();
  const { t } = useTranslation();
  const location = useLocation();
  
  const showAccount = isAuthenticated && !isPrerenderCapture();
  const [menuLocation, setMenuLocation] = useState<typeof location | null>(null);
  const isMenuOpen = menuLocation === location;
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const desktopNavRef = useRef<HTMLElement>(null);
  const mobileGamesRef = useRef<HTMLDetailsElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const homeLinkRef = useRef<HTMLAnchorElement>(null);
  const restoreMenuFocusRef = useRef(true);
  const skipMenuFocusRef = useRef(false);

  const exploreItems = [
    { path: '/archive', name: t('header.archive', 'Archive'), icon: Archive },
    { path: '/how-it-works', name: t('header.howItWorks', 'How Questions Work'), icon: Cpu },
    { path: '/explore', name: 'Geography Guides', icon: BookOpen },
    { path: '/patch-notes', name: t('header.patchNotes', 'Patch notes'), icon: Sparkles },
    ...(showAccount && user?.is_admin ? [{ path: '/admin', name: 'Admin Dashboard', icon: ShieldCheck }] : []),
  ];

  const aboutItems = [
    { path: '/about', name: t('header.about', 'About'), icon: Info },
    { path: '/faq', name: t('header.faq', 'FAQ'), icon: HelpCircle },
    { path: '/contact', name: t('header.suggestions', 'Suggestions'), icon: Mail },
    { path: '/privacy-policy', name: t('footer.privacyPolicy', 'Privacy Policy'), icon: ShieldCheck },
    { path: '/terms', name: t('footer.termsOfService', 'Terms of Service'), icon: FileText },
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
      const desktopMenu = target?.closest('details');
      desktopNavRef.current?.querySelectorAll('details[open]').forEach((details) => {
        if (details !== desktopMenu) details.removeAttribute('open');
      });
      if (mobileGamesRef.current && !mobileGamesRef.current.contains(target)) {
        mobileGamesRef.current.open = false;
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
      } else {
        const nav = desktopNavRef.current;
        const hadFocus = nav?.contains(document.activeElement);
        nav?.querySelectorAll('details[open]').forEach((details) => details.removeAttribute('open'));
        if (hadFocus) menuButtonRef.current?.focus();
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
      if (!skipMenuFocusRef.current && focusTarget?.isConnected) focusTarget.focus();
      skipMenuFocusRef.current = false;
    };
  }, [isMenuOpen]);


  const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-11 w-full min-w-0 items-center rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed [overflow-wrap:anywhere] transition-colors ${
      isActive ? 'text-app-accent bg-app-accent/10 font-medium' : 'text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted'
    }`;

  return (
    <header className="sticky top-0 z-[1001] shrink-0 border-b border-app-border/10 bg-app-surface text-app-text">
      <div className="mx-auto flex h-14 xl:h-20 max-w-7xl items-center justify-between gap-2 px-3 sm:gap-4 sm:px-6">

        {/* Brand */}
        <Link ref={homeLinkRef} to="/" onClick={() => closeMenu()} className="flex min-h-11 shrink-0 items-center gap-2.5" aria-label="Countrydle">
          <CountrydleLogo size={32} />
          <span className="text-xl font-semibold tracking-tight text-app-text">
            Countrydle<span className="text-app-accent">.</span>
          </span>
        </Link>

        {/* Desktop navigation */}
        <nav ref={desktopNavRef} aria-label="Main navigation" className="hidden items-center gap-3 xl:flex">
          <div className="flex items-stretch rounded-md bg-app-accent text-white">
            <NavLink to="/game" className="rounded-l-md px-5 py-2 text-sm font-semibold transition-colors hover:bg-app-accent-hover">Play</NavLink>
            <details
              name="desktop-navigation"
              className="group relative"
              onKeyDown={(event) => {
                if (event.key === 'Escape' && event.currentTarget.open) {
                  event.preventDefault();
                  event.stopPropagation();
                  event.currentTarget.open = false;
                  event.currentTarget.querySelector('summary')?.focus();
                }
              }}
            >
              <summary aria-label="Choose a game" className="flex h-full cursor-pointer list-none items-center rounded-r-md border-l border-white/20 px-3 hover:bg-app-accent-hover [&::-webkit-details-marker]:hidden">
                <ChevronDown size={16} className="transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div
                className="absolute left-0 top-full z-50 max-h-[calc(100dvh-6rem)] w-56 overflow-y-auto rounded-md border border-app-border/15 bg-app-surface-raised p-1.5 text-app-text shadow-md"
                onClick={(event) => {
                  if ((event.target as HTMLElement).closest('a')) event.currentTarget.closest('details')?.removeAttribute('open');
                }}
              >
                {primaryGames.map((game) => (
                  <NavLink key={game.path} to={game.path} className={({ isActive }) =>
                    `block rounded px-3 py-2 text-sm ${isActive ? 'bg-app-accent/10 text-app-accent' : 'text-app-text hover:bg-app-surface-muted'}`
                  }>{game.name}</NavLink>
                ))}
                <NavLink to="/friends" className="block rounded px-3 py-2 text-sm font-medium text-app-accent transition-colors hover:bg-app-surface-muted hover:text-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">Play with friend</NavLink>
                <Link to="/explore" className="mt-1 block border-t border-app-border/10 px-3 py-2.5 text-sm font-medium text-app-accent hover:text-app-accent-hover">Explore more…</Link>
              </div>
            </details>
          </div>
          {([
            { id: 'explore', label: 'Explore', items: exploreItems },
            { id: 'about', label: 'About', items: aboutItems },
          ]).map(({ id, label, items }) => (
            <details
              key={id}
              name="desktop-navigation"
              className="group relative"
              onKeyDown={(event) => {
                if (event.key === 'Escape' && event.currentTarget.open) {
                  event.preventDefault();
                  event.stopPropagation();
                  event.currentTarget.open = false;
                  event.currentTarget.querySelector('summary')?.focus();
                }
              }}
            >
              <summary className="flex cursor-pointer list-none items-center gap-1 px-2 py-2 text-sm text-app-text-secondary hover:text-app-text [&::-webkit-details-marker]:hidden">
                {label} <ChevronDown size={13} className="transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div
                className="absolute right-0 top-full z-50 max-h-[calc(100dvh-6rem)] w-56 overflow-y-auto rounded-md border border-app-border/15 bg-app-surface-raised p-1.5 shadow-md"
                onClick={(event) => {
                  if ((event.target as HTMLElement).closest('a, button')) event.currentTarget.closest('details')?.removeAttribute('open');
                }}
              >
                {id === 'explore' && <NavLink to="/leaderboard" className={({ isActive }) => `block rounded px-2 py-2 text-sm ${isActive ? 'bg-app-accent/10 text-app-accent' : 'text-app-text hover:bg-app-surface-muted'}`}>{t('header.leaderboard', 'Leaderboard')}</NavLink>}
                {items.map((item) => {
                  const Icon = item.icon;
                  return <NavLink key={item.path} to={item.path} className={({ isActive }) =>
                    `flex items-center gap-2 rounded px-2 py-2 text-sm ${isActive ? 'bg-app-accent/10 text-app-accent' : 'text-app-text hover:bg-app-surface-muted'}`
                  }><Icon size={14} className="shrink-0 text-app-text-muted" aria-hidden="true" />{item.name}</NavLink>;
                })}
                {id === 'about' && <div className="border-t border-app-border/10 pt-1">
                  <PrivacySettingsButton className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text" />
                </div>}
              </div>
            </details>
          ))}
          <NavLink to="/blog" className={({ isActive }) => `px-2 py-2 text-sm ${isActive ? 'text-app-accent' : 'text-app-text-secondary hover:text-app-text'}`}>{t('header.blog', 'Blog')}</NavLink>
        </nav>

        {/* Right Section: Bigger Clock & Auth Controls (Desktop) */}
        <div className="hidden shrink-0 items-center gap-2 xl:flex">
          {/* Prominent Next Puzzle / Country Countdown Clock */}
          <CountdownTimer />

          {/* User Profile or Login/Register CTAs */}
          {showAccount ? (
            <div className="flex items-center gap-2 border-l border-app-border/15 pl-2">
              <Link
                to={`/profile/${user?.username}`}
                className="max-w-28 truncate text-sm text-app-text-secondary hover:text-app-accent transition-colors"
                title={t('header.viewProfile', 'View Profile')}
              >
                {user?.username}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                aria-label={t('header.logout', 'Logout')}
                className="p-1.5 text-app-text-muted hover:text-app-text transition-colors"
                title={t('header.logout', 'Logout')}
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 border-l border-app-border/15 pl-2">
              <Link
                to="/login"
                className="text-sm text-app-text-secondary hover:text-app-text transition-colors"
              >
                {t('header.login', 'Login')}
              </Link>
              <Link
                to="/register"
                className="border border-app-border/25 px-3 py-1.5 text-sm rounded text-app-text hover:bg-app-surface-muted font-medium transition-colors"
              >
                {t('header.signUp', 'Sign Up')}
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
            aria-label={'Navigation menu'}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded text-app-text-secondary hover:bg-app-surface-muted transition-colors"
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
          className="fixed bottom-0 left-auto right-0 top-14 m-0 h-[calc(100dvh-3.5rem)] max-h-none w-full max-w-md flex-col border-0 border-l border-app-border/10 bg-app-surface p-0 text-app-text shadow-xl open:flex backdrop:bg-black/25"
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
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-app-border/10 px-4 pb-2 pt-[calc(0.5rem+env(safe-area-inset-top))]">
            <h2 id="mobile-navigation-title" className="text-base font-semibold">
              Menu
            </h2>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={() => closeMenu()}
              aria-label={'Close menu'}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-app-text-secondary transition-colors hover:bg-app-surface-muted"
            >
              <X size={22} aria-hidden="true" />
            </button>
          </div>
          <nav
            aria-label={'Mobile navigation'}
            className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4"
            onClick={(event) => {
              if ((event.target as HTMLElement).closest('a')) closeMenu();
            }}
          >
            <div className="flex rounded-lg bg-app-accent text-white">
              <NavLink to="/game" className="flex min-h-12 flex-1 items-center justify-center rounded-l-lg px-4 py-3 text-base font-semibold hover:bg-app-accent-hover">Play</NavLink>
              <details
                ref={mobileGamesRef}
                className="group relative"
                onKeyDown={(event) => {
                  if (event.key === 'Escape' && event.currentTarget.open) {
                    event.preventDefault();
                    event.stopPropagation();
                    event.currentTarget.open = false;
                    event.currentTarget.querySelector('summary')?.focus();
                  }
                }}
              >
                <summary aria-label="Choose a game" className="flex h-12 w-12 cursor-pointer list-none items-center justify-center rounded-r-lg border-l border-white/20 hover:bg-app-accent-hover [&::-webkit-details-marker]:hidden">
                  <ChevronDown size={18} className="transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <div className="absolute right-0 top-full z-10 max-h-[calc(100dvh-12rem-env(safe-area-inset-top)-env(safe-area-inset-bottom))] w-[min(18rem,calc(100vw-2rem))] overflow-y-auto rounded-lg border border-app-border/15 bg-app-surface-raised p-2 text-app-text shadow-md">
                  {primaryGames.map((game) => <NavLink key={game.path} to={game.path} className={mobileLinkClass}>{game.name}</NavLink>)}
                  <NavLink to="/friends" className="flex min-h-11 w-full items-center rounded-lg px-3 py-2.5 text-sm font-medium text-app-accent transition-colors hover:bg-app-surface-muted hover:text-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">Play with friend</NavLink>
                  <Link to="/explore" onClick={() => {
                    skipMenuFocusRef.current = true;
                    dialogRef.current?.close();
                  }} className="mt-1 flex min-h-11 items-center border-t border-app-border/10 px-3 py-2 text-sm font-medium text-app-accent hover:text-app-accent-hover">Explore more…</Link>
                </div>
              </details>
            </div>
            <div className="space-y-1">
              <NavLink to="/blog" className={mobileLinkClass}>
                {t('header.blog', 'Blog')}
              </NavLink>
              <NavLink to="/leaderboard" className={mobileLinkClass}>
                {t('header.leaderboard', 'Leaderboard')}
              </NavLink>
            </div>

            <div className="divide-y divide-app-border/10 border-y border-app-border/10">
              <details className="group">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-medium leading-relaxed [&::-webkit-details-marker]:hidden">
                  <span>{'Guides & archive'}</span>
                  <ChevronDown size={18} className="shrink-0 text-app-text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
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
                  <span>{'Help & privacy'}</span>
                  <ChevronDown size={18} className="shrink-0 text-app-text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
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
                    <PrivacySettingsButton className="min-h-11 w-full rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed text-app-text-secondary transition-colors hover:bg-app-surface-muted [overflow-wrap:anywhere]" />
                  </div>
                </div>
              </details>
            </div>

            <div className="space-y-1">
              {showAccount ? (
                <>
                  <Link
                    to={`/profile/${user?.username}`}
                    className="flex min-h-11 w-full min-w-0 flex-col justify-center rounded-lg px-3 py-2.5 text-sm leading-relaxed text-app-accent transition-colors hover:bg-app-surface-muted"
                  >
                    <span className="text-xs text-app-text-muted">{'Your profile'}</span>
                    <span className="w-full [overflow-wrap:anywhere]">{user?.username}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm leading-relaxed text-app-text-secondary transition-colors hover:bg-app-surface-muted"
                  >
                    <LogOut size={16} className="shrink-0" aria-hidden="true" />
                    {t('header.logout', 'Logout')}
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" className="flex min-h-11 w-full items-center rounded-lg px-3 py-2.5 text-sm leading-relaxed text-app-text-secondary transition-colors hover:bg-app-surface-muted">
                    {t('header.login', 'Login')}
                  </Link>
                  <Link to="/register" className="flex min-h-11 w-full items-center rounded-lg border border-app-border/25 px-3 py-2.5 text-sm font-medium leading-relaxed text-app-text transition-colors hover:bg-app-surface-muted">
                    {t('header.signUp', 'Sign Up')}
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
