import { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import Header from './Header';
import Footer from './Footer';
import CookieConsent from './CookieConsent';
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

  return (
    <div className="flex min-h-screen flex-col bg-obsidian-950 font-sans text-sand-100">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[2000] focus:bg-sand-100 focus:px-4 focus:py-3 focus:text-obsidian-950">Skip to content</a>
      <Header />
      <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 md:py-10">
        <Outlet />
      </main>
      <Footer />
      <CookieConsent />
      <VersionDisplay />
    </div>
  );
}
