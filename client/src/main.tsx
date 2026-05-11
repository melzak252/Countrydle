import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google';
import './index.css'
import './i18n';
import App from './App.tsx'

const GOOGLE_CLIENT_ID = "624396927539-luhujtnrft1igdoug3bim8ac9nmvf3sk.apps.googleusercontent.com";

const loadOptionalScripts = () => {
  const adsenseId = import.meta.env.VITE_GOOGLE_ADSENSE_ID;
  if (adsenseId) {
    const meta = document.createElement('meta');
    meta.name = 'google-adsense-account';
    meta.content = adsenseId;
    document.head.appendChild(meta);

    const script = document.createElement('script');
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsenseId}`;
    document.head.appendChild(script);
  }

  const rybbitScriptUrl = import.meta.env.VITE_RYBBIT_SCRIPT_URL;
  const rybbitSiteId = import.meta.env.VITE_RYBBIT_SITE_ID;
  if (rybbitScriptUrl && rybbitSiteId) {
    const script = document.createElement('script');
    script.src = rybbitScriptUrl;
    script.dataset.siteId = rybbitSiteId;
    script.defer = true;
    document.head.appendChild(script);
  }
};

loadOptionalScripts();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <App />
    </GoogleOAuthProvider>
  </StrictMode>,
)
