import { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import Header from './Header';
import Footer from './Footer';
import VersionDisplay from './VersionDisplay';

export default function Layout() {
  const { user, isAuthenticated } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (isAuthenticated && user && !user.username && location.pathname !== '/setup-profile') {
      navigate('/setup-profile');
    }
  }, [isAuthenticated, user, navigate, location.pathname]);

  useEffect(() => {
    const viewport = window.visualViewport;
    const updateAppHeight = () => {
      const height = (viewport?.height ?? window.innerHeight) + (viewport?.offsetTop ?? 0);
      if (window.matchMedia('(max-width: 767px)').matches) {
        document.documentElement.style.setProperty('--app-height', `${height}px`);
      } else {
        document.documentElement.style.removeProperty('--app-height');
      }
    };
    updateAppHeight();
    viewport?.addEventListener('resize', updateAppHeight);
    viewport?.addEventListener('scroll', updateAppHeight);
    window.addEventListener('resize', updateAppHeight);
    return () => {
      viewport?.removeEventListener('resize', updateAppHeight);
      viewport?.removeEventListener('scroll', updateAppHeight);
      window.removeEventListener('resize', updateAppHeight);
      document.documentElement.style.removeProperty('--app-height');
    };
  }, []);

  const isGameFullscreen = [
    '/game',
    '/europe',
    '/asia',
    '/africa',
    '/americas',
    '/us-states',
    '/wojewodztwa',
    '/powiaty',
    '/friends',
    '/duel',
  ].some((path) => location.pathname === path || location.pathname.startsWith(`${path}/`));
  return (
    <div className={`flex min-h-screen flex-col bg-obsidian-950 font-sans text-sand-100 ${isGameFullscreen ? 'max-md:min-h-0 max-md:h-[var(--app-height,100dvh)] md:h-screen overflow-hidden' : ''}`}>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[2000] focus:bg-sand-100 focus:px-4 focus:py-3 focus:text-obsidian-950">Skip to content</a>
      <Header />
      <main id="main-content" className={isGameFullscreen ? "relative flex min-h-0 w-full flex-1 flex-col overflow-hidden p-0" : location.pathname === '/admin' ? "mx-auto min-w-0 w-full max-w-[1600px] flex-1 px-4 py-4 lg:px-6" : "mx-auto min-w-0 w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 md:py-10"}>
        <Outlet />
      </main>
      {!isGameFullscreen && <Footer />}
      <VersionDisplay />
    </div>
  );
}
