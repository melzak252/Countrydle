import { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import Header from './Header';
import Footer from './Footer';
import CookieConsent from './CookieConsent';

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
    <div className="flex flex-col min-h-screen bg-zinc-950 text-white font-sans">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8">
        <Outlet />
      </main>
      <Footer />
      <CookieConsent />
    </div>
  );
}
