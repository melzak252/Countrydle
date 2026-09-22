import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import GamePage from './pages/GamePage';
import LeaderboardPage from './pages/LeaderboardPage';
import ProfilePage from './pages/ProfilePage';
import SetupProfilePage from './pages/SetupProfilePage';
import PowiatyGamePage from './pages/PowiatyGamePage';
import USStatesGamePage from './pages/USStatesGamePage';
import WojewodztwaGamePage from './pages/WojewodztwaGamePage';
import ContinentalGamePage from './pages/ContinentalGamePage';
import FlagdlePage from './pages/FlagdlePage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import TermsOfServicePage from './pages/TermsOfServicePage';
import CookiePolicyPage from './pages/CookiePolicyPage';
import ArchivePage from './pages/ArchivePage';
import AdminDashboard from './pages/AdminDashboard';
import AboutPage from './pages/AboutPage';
import ContactPage from './pages/ContactPage';
import FAQPage from './pages/FAQPage';
import BlogListPage from './pages/BlogListPage';
import BlogPostPage from './pages/BlogPostPage';
import { useAuthStore } from './stores/authStore';
import {
  useCountryGameStore,
  usePowiatyGameStore,
  useUSStatesGameStore,
  useWojewodztwaGameStore,
  useEuropeGameStore,
  useAsiaGameStore,
  useAfricaGameStore,
  useAmericasGameStore,
  useFlagdleGameStore,
} from './stores/gameStore';
import { useEffect } from 'react';

function App() {
  const { user, setUser, isAuthenticated } = useAuthStore();

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
        setUser(JSON.parse(storedUser));
    } else {
        setUser(null);
    }
  }, [setUser]);

  // Global sync trigger when user logs in
  useEffect(() => {
    if (isAuthenticated) {
      const timer = setTimeout(() => {
        useCountryGameStore.getState().syncGuestData();
        usePowiatyGameStore.getState().syncGuestData();
        useUSStatesGameStore.getState().syncGuestData();
        useWojewodztwaGameStore.getState().syncGuestData();
        useEuropeGameStore.getState().syncGuestData();
        useAsiaGameStore.getState().syncGuestData();
        useAfricaGameStore.getState().syncGuestData();
        useAmericasGameStore.getState().syncGuestData();
        useFlagdleGameStore.getState().syncGuestData();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated]);

  // Global reset trigger when user logs out
  useEffect(() => {
    const handleLogout = () => {
      useCountryGameStore.getState().resetGame();
      usePowiatyGameStore.getState().resetGame();
      useUSStatesGameStore.getState().resetGame();
      useWojewodztwaGameStore.getState().resetGame();
      useEuropeGameStore.getState().resetGame();
      useAsiaGameStore.getState().resetGame();
      useAfricaGameStore.getState().resetGame();
      useAmericasGameStore.getState().resetGame();
      useFlagdleGameStore.getState().resetGame();
      
      // After reset, fetch guest state (if any)
      useCountryGameStore.getState().fetchGameState();
      usePowiatyGameStore.getState().fetchGameState();
      useUSStatesGameStore.getState().fetchGameState();
      useWojewodztwaGameStore.getState().fetchGameState();
      useEuropeGameStore.getState().fetchGameState();
      useAsiaGameStore.getState().fetchGameState();
      useAfricaGameStore.getState().fetchGameState();
      useAmericasGameStore.getState().fetchGameState();
      useFlagdleGameStore.getState().fetchGameState();
    };

    window.addEventListener('auth-logout', handleLogout);
    return () => window.removeEventListener('auth-logout', handleLogout);
  }, []);

  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{
        style: {
          background: '#333',
          color: '#fff',
        },
      }} />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="game" element={<GamePage />} />
          <Route path="leaderboard" element={<LeaderboardPage />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="profile/:username" element={<ProfilePage />} />
          <Route path="setup-profile" element={<SetupProfilePage />} />
          <Route path="powiaty" element={<PowiatyGamePage />} />
          <Route path="us-states" element={<USStatesGamePage />} />
          <Route path="wojewodztwa" element={<WojewodztwaGamePage />} />
          <Route path="europe" element={<ContinentalGamePage continent="europe" />} />
          <Route path="asia" element={<ContinentalGamePage continent="asia" />} />
          <Route path="africa" element={<ContinentalGamePage continent="africa" />} />
          <Route path="americas" element={<ContinentalGamePage continent="americas" />} />
          <Route path="flagdle" element={<FlagdlePage />} />
          <Route path="privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="terms" element={<TermsOfServicePage />} />
          <Route path="cookie-policy" element={<CookiePolicyPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="contact" element={<ContactPage />} />
          <Route path="faq" element={<FAQPage />} />
          <Route path="blog" element={<BlogListPage />} />
          <Route path="blog/:slug" element={<BlogPostPage />} />
          <Route path="admin" element={user?.is_admin ? <AdminDashboard /> : <Navigate to="/" replace />} />
          
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
