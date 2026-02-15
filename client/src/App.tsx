import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import GamePage from './pages/GamePage';
import LeaderboardPage from './pages/LeaderboardPage';
import ProfilePage from './pages/ProfilePage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import TermsOfServicePage from './pages/TermsOfServicePage';
import CookiePolicyPage from './pages/CookiePolicyPage';
import { useAuthStore } from './stores/authStore';
import { useEffect } from 'react';

function App() {
  const { setUser } = useAuthStore();

  useEffect(() => {
    // Check if there is an access token in cookies
    // Note: HttpOnly cookies are not accessible via JS, but if the backend sets a flag or 
    // we can try to hit a protected endpoint to verify session.
    // The current backend implementation sets 'access_token' cookie.
    // Since it's not HttpOnly in local dev (secure=False), we might be able to read it?
    // Wait, the backend code says:
    // response.set_cookie(key="access_token", value=access_token, httponly=True, ...)
    // So we CANNOT read it. 
    // We should try to fetch the user state or a 'me' endpoint.
    // However, the backend doesn't have a dedicated 'me' endpoint other than login response.
    // But /countrydle/state returns the user object!
    
    // Actually, let's just assume if we are on a protected route, the game page will fetch state.
    // If it fails with 401, we logout.
    
    // A better approach for now: Since we don't have a persistent client-side session storage 
    // (except what we might implement), and cookies are HttpOnly, we rely on API calls succeeding.
    
    // But for the UI to know if we are logged in, we need to persist the user object in localStorage 
    // or fetch it on app load. 
    
    // Let's add a `checkAuth` method to authStore or just try to fetch game state to validate session.
    // Or we can modify the backend to return user info on a separate endpoint.
    // Given I can't modify backend easily, I will try to fetch game state. If it works, we are logged in.
    // But game state fetches 'user' in response.
    
    // Actually, `GamePage` fetches game state.
    // If we want global auth state, we should probably try to recover it.
    
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
          <Route path="profile/:username" element={<ProfilePage />} />
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
