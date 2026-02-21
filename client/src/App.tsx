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
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import TermsOfServicePage from './pages/TermsOfServicePage';
import CookiePolicyPage from './pages/CookiePolicyPage';
import ArchivePage from './pages/ArchivePage';
import { useAuthStore } from './stores/authStore';
import { useEffect } from 'react';

function App() {
  const { setUser } = useAuthStore();

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
        setUser(JSON.parse(storedUser));
    } else {
        setUser(null);
    }
  }, [setUser]);

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
          <Route path="privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="terms" element={<TermsOfServicePage />} />
          <Route path="cookie-policy" element={<CookiePolicyPage />} />
          
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
