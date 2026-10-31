import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google';
import './index.css'
import './i18n';
import App from './App.tsx'
import { initializeAdvertisingPolicy, isPublisherCapture } from './advertising';

const GOOGLE_CLIENT_ID = "624396927539-luhujtnrft1igdoug3bim8ac9nmvf3sk.apps.googleusercontent.com";

initializeAdvertisingPolicy();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isPublisherCapture() ? <App /> : (
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <App />
      </GoogleOAuthProvider>
    )}
  </StrictMode>,
)
