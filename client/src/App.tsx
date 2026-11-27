import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import PageMetadata from './components/PageMetadata';
import { isPrerenderCapture } from './lib/pageMetadata';
import HomePage from './pages/HomePage';
import { MAP_QUIZ_PATHS } from './lib/mapGameMode';
import { useAuthStore } from './stores/authStore';
import { countyFlagsService, mapQuizScopes, mapQuizService, regionalSymbolGames, regionalSymbolPath, regionalSymbolsService } from './services/api';
import {
  useCountryGameStore,
  usePowiatyGameStore,
  useUSStatesGameStore,
  useWojewodztwaGameStore,
  useCountydleGameStore,
  useEuropeGameStore,
  useAsiaGameStore,
  useAfricaGameStore,
  useAmericasGameStore,
  useFlagdleGameStore,
} from './stores/gameStore';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const GamePage = lazy(() => import('./pages/GamePage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const SetupProfilePage = lazy(() => import('./pages/SetupProfilePage'));
const PowiatyGamePage = lazy(() => import('./pages/PowiatyGamePage'));
const USStatesGamePage = lazy(() => import('./pages/USStatesGamePage'));
const WojewodztwaGamePage = lazy(() => import('./pages/WojewodztwaGamePage'));
const CountydleGamePage = lazy(() => import('./pages/CountydleGamePage'));
const ContinentalGamePage = lazy(() => import('./pages/ContinentalGamePage'));
const FlagdlePage = lazy(() => import('./pages/FlagdlePage'));
const FlagShadesPage = lazy(() => import('./pages/FlagShadesPage'));
const PowiatHeraldryPage = lazy(() => import('./pages/PowiatHeraldryPage'));
const PowiatCoatsQuizPage = lazy(() => import('./pages/PowiatCoatsQuizPage'));
const PowiatPlatesQuizPage = lazy(() => import('./pages/PowiatPlatesQuizPage'));
const MapQuizPage = lazy(() => import('./pages/MapQuizPage'));
const BorderHopPage = lazy(() => import('./pages/BorderHopPage'));
const MapChallengePage = lazy(() => import('./pages/MapChallengePage'));
const MapBorderHopPage = lazy(() => import('./pages/MapBorderHopPage'));
const DuelPage = lazy(() => import('./pages/DuelPage'));
const PrivacyPolicyPage = lazy(() => import('./pages/PrivacyPolicyPage'));
const TermsOfServicePage = lazy(() => import('./pages/TermsOfServicePage'));
const CookiePolicyPage = lazy(() => import('./pages/CookiePolicyPage'));
const ArchivePage = lazy(() => import('./pages/ArchivePage'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));
const FAQPage = lazy(() => import('./pages/FAQPage'));
const BlogListPage = lazy(() => import('./pages/BlogListPage'));
const BlogPostPage = lazy(() => import('./pages/BlogPostPage'));
const PatchNotesPage = lazy(() => import('./pages/PatchNotesPage'));
const ExplorePage = lazy(() => import('./pages/ExplorePage'));
const ModeGuidePage = lazy(() => import('./pages/ModeGuidePage'));

function App() {
  const { user, setUser, isAuthenticated, isLoading: authLoading } = useAuthStore();

  useEffect(() => {
    if (isPrerenderCapture()) {
      setUser(null);
      return;
    }
    try {
      const storedUser = localStorage.getItem('user');
      setUser(storedUser ? JSON.parse(storedUser) : null);
    } catch {
      setUser(null);
    }
  }, [setUser]);

  // Global sync trigger when user logs in
  useEffect(() => {
    if (isAuthenticated && !isPrerenderCapture()) {
      const timer = setTimeout(() => {
        useCountryGameStore.getState().syncGuestData();
        usePowiatyGameStore.getState().syncGuestData();
        useUSStatesGameStore.getState().syncGuestData();
        useWojewodztwaGameStore.getState().syncGuestData();
        useCountydleGameStore.getState().syncGuestData();
        useEuropeGameStore.getState().syncGuestData();
        useAsiaGameStore.getState().syncGuestData();
        useAfricaGameStore.getState().syncGuestData();
        useAmericasGameStore.getState().syncGuestData();
        useFlagdleGameStore.getState().syncGuestData();
        try {
          const today = new Date().toISOString().slice(0, 10);
          if (localStorage.getItem(`county_flags_daily_token_${today}`)) {
            void countyFlagsService.sync().then((challenge) => {
              if (challenge.date && challenge.token) localStorage.setItem(`county_flags_daily_token_${challenge.date}`, challenge.token);
            }).catch((error) => console.error('Failed to claim county flag guest progress:', error));
          }
          for (const { scope, flags } of regionalSymbolGames) {
            const prefix = `regional_symbols_${scope}_${flags ? 'flag' : 'coat'}_daily_token_`;
            if (localStorage.getItem(`${prefix}${today}`)) {
              void regionalSymbolsService(scope, flags).sync().then((challenge) => {
                if (challenge.date && challenge.token) localStorage.setItem(`${prefix}${challenge.date}`, challenge.token);
              }).catch((error) => console.error('Failed to claim regional symbol guest progress:', error));
            }
          }
          for (const scope of mapQuizScopes) {
            const marker = `map_quiz_${scope}_daily_${today}`;
            if (localStorage.getItem(marker)) {
              void mapQuizService(scope).sync().catch((error) => console.error('Failed to claim map quiz guest progress:', error));
            }
          }
        } catch {
          // Storage may be unavailable; the game page can still use its cookie.
        }
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
      useCountydleGameStore.getState().resetGame();
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
      useCountydleGameStore.getState().fetchGameState();
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
          background: 'rgb(var(--app-surface-raised))',
          color: 'rgb(var(--app-text))',
          border: '1px solid rgb(var(--app-border) / 0.12)',
        },
      }} />
      <PageMetadata />
      <Suspense fallback={<div className="mx-auto max-w-5xl px-4 py-12 text-sm text-app-text-muted">Loading…</div>}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="game" element={<GamePage />} />
          <Route path="leaderboard" element={<Navigate to="/" replace />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="patch-notes" element={<PatchNotesPage />} />
          <Route path="profile/:username" element={<ProfilePage />} />
          <Route path="setup-profile" element={<SetupProfilePage />} />
          <Route path="powiaty" element={<PowiatyGamePage />} />
          <Route path="us-states" element={<USStatesGamePage />} />
          <Route path="wojewodztwa" element={<WojewodztwaGamePage />} />
          <Route path="countydle" element={<CountydleGamePage />} />
          <Route path="europe" element={<ContinentalGamePage continent="europe" />} />
          <Route path="asia" element={<ContinentalGamePage continent="asia" />} />
          <Route path="africa" element={<ContinentalGamePage continent="africa" />} />
          <Route path="americas" element={<ContinentalGamePage continent="americas" />} />
          <Route path="flagdle" element={<FlagdlePage />} />
          <Route path="flag-shades" element={<FlagShadesPage />} />
          <Route path="herby-powiatow" element={<PowiatHeraldryPage />} />
          <Route path="quiz-herbow" element={<PowiatCoatsQuizPage />} />
          <Route path="coats-of-arms-quiz" element={<PowiatCoatsQuizPage />} />
          <Route path="flagi-powiatow" element={<PowiatHeraldryPage key="flags" flags />} />
          <Route path="quiz-flag-powiatow" element={<PowiatCoatsQuizPage key="flags" flags />} />
          <Route path="quiz-tablic" element={<PowiatPlatesQuizPage />} />
          <Route path="license-plates-quiz" element={<PowiatPlatesQuizPage />} />
          {regionalSymbolGames.flatMap(({ scope, flags }) => {
            const path = regionalSymbolPath(scope, flags).slice(1);
            return [
              <Route key={path} path={path} element={<PowiatHeraldryPage scope={scope} flags={flags} />} />,
              <Route key={`${path}/quiz`} path={`${path}/quiz`} element={<PowiatCoatsQuizPage scope={scope} flags={flags} />} />,
            ];
          })}
          <Route path="map-quiz/london-boroughs" element={<MapQuizPage scope="london_boroughs" />} />
          <Route path="map-quiz/england-counties" element={<MapQuizPage scope="england_counties" />} />
          <Route path="border-hop" element={<BorderHopPage />} />
          <Route path={MAP_QUIZ_PATHS.powiaty.slice(1)} element={<MapChallengePage mode="powiaty" />} />
          <Route path={MAP_QUIZ_PATHS.us_states.slice(1)} element={<MapChallengePage mode="us_states" />} />
          <Route path="map-border-hop" element={<MapBorderHopPage />} />
          <Route path="friends" element={<DuelPage />} />
          <Route path="duel/:code" element={<DuelPage />} />
          <Route path="privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="terms" element={<TermsOfServicePage />} />
          <Route path="cookie-policy" element={<CookiePolicyPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="contact" element={<ContactPage />} />
          <Route path="faq" element={<FAQPage />} />
          <Route path="explore" element={<ExplorePage />} />
          <Route path="explore/modes/:modeId" element={<ModeGuidePage />} />
          <Route path="blog" element={<BlogListPage />} />
          <Route path="blog/:slug" element={<BlogPostPage />} />
          <Route path="admin" element={authLoading ? <p role="status">Loading account…</p> : user?.is_admin ? <AdminDashboard /> : <Navigate to="/" replace />} />
          
          {/* Fallback */}
          <Route path="*" element={
            <section className="mx-auto max-w-3xl px-4 py-12">
              <h1 className="text-3xl font-bold text-app-text">Page not found</h1>
              <p className="mt-4 text-app-text-secondary">This page does not exist. Explore the daily geography games or return to the homepage.</p>
              <Link to="/" className="mt-6 inline-block text-app-accent underline">Return to Countrydle</Link>
            </section>
          } />
        </Route>
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
