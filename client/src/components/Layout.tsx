import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import CookieConsent from './CookieConsent';

export default function Layout() {
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
