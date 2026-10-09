import { useEffect, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';

type ConsentState = 'unknown' | 'granted' | 'denied';
interface TCData {
  cmpStatus?: string;
  eventStatus?: string;
  gdprApplies?: boolean;
  tcString?: string;
  purpose?: { consents?: Record<number, boolean>; legitimateInterests?: Record<number, boolean> };
  vendor?: { consents?: Record<number, boolean>; legitimateInterests?: Record<number, boolean> };
}
interface GooglePrivacyMessaging {
  callbackQueue: Array<{ CONSENT_API_READY: () => void }>;
  showRevocationMessage?: () => void;
}
declare global {
  interface Window {
    __COUNTRYDLE_PRERENDER__?: boolean;
    adsbygoogle?: { push: (request: Record<string, never>) => unknown };
    googlefc?: GooglePrivacyMessaging;
    __tcfapi?: (command: 'addEventListener', version: 2, callback: (data: TCData, success: boolean) => void) => void;
  }
}

export const isPublisherCapture = () => window.__COUNTRYDLE_PRERENDER__ === true;
const publisherPattern = /^ca-pub-\d{16}$/;
const verifiedPublisher = document.querySelector<HTMLMetaElement>('meta[name="google-adsense-account"]')?.content || '';
const requestedPublisher = import.meta.env.VITE_GOOGLE_ADSENSE_ID || verifiedPublisher;
const publisher = publisherPattern.test(requestedPublisher) && requestedPublisher === verifiedPublisher ? requestedPublisher : '';
const placements: Record<string, string> = Object.create(null);
try {
  const configured: unknown = JSON.parse(import.meta.env.VITE_ADSENSE_SLOTS || '{}');
  if (configured && typeof configured === 'object' && !Array.isArray(configured)) {
    for (const [key, value] of Object.entries(configured)) {
      // Account-generated identifiers must be supplied as strings, never placement labels.
      if (typeof value === 'string' && /^\d{10}$/.test(value) && !/^0+$/.test(value)) placements[key] = value;
    }
  }
} catch {
  // An invalid or absent inventory configuration cannot authorize serving.
}
const configured = import.meta.env.VITE_ADSENSE_ENABLED === 'true' && Boolean(publisher) && Object.keys(placements).length > 0;
const publicRoutes: Record<string, true> = { '/': true, '/about': true, '/how-it-works': true, '/faq': true };
const guideModes: Record<string, true> = { countrydle: true, flagdle: true, europe: true, asia: true, africa: true, americas: true, 'us-states': true, us_statedle: true, wojewodztwa: true, powiaty: true };
const routePath = (path: string) => path === '/' ? path : path.replace(/\/$/, '');
const pageKey = () => window.location.pathname + window.location.search;
function requiresLoadedContent(path: string) {
  return path === '/explore' || path === '/blog' || /^\/blog\/[^/]+$/.test(path);
}
function isPublicRoute(pathname: string) {
  const path = routePath(pathname);
  return Object.hasOwn(publicRoutes, path) || (path.startsWith('/explore/modes/') && Object.hasOwn(guideModes, path.slice('/explore/modes/'.length)));
}

let editorialPage = '';
let editorialEligible = false;
let consent: ConsentState = 'unknown';
let scriptReady = false;
let adsStarted = false;
let adsDocument = '';
let navigationPending = false;
let initialized = false;
let cmpPromise: Promise<void> | null = null;
let listenerRegistered = false;
let revision = 0;
const subscribers = new Set<() => void>();
const publish = () => { revision += 1; subscribers.forEach(notify => notify()); };
const subscribe = (notify: () => void) => { subscribers.add(notify); return () => { subscribers.delete(notify); }; };
function eligible(pathname = window.location.pathname, key = pageKey()) {
  const path = routePath(pathname);
  return !isPublisherCapture() && !navigationPending && configured && consent === 'granted'
    && (isPublicRoute(path) || (requiresLoadedContent(path) && editorialEligible && editorialPage === key));
}

function removeAdArtifacts() {
  // Removing the script alone does not unload Google's runtime. A document boundary below does.
  document.querySelectorAll<HTMLElement>('[data-countrydle-ad="unit"]').forEach(node => { node.style.display = 'none'; });
  document.querySelectorAll('ins.adsbygoogle').forEach(node => node.replaceChildren());
  document.querySelectorAll('script[data-countrydle-ad], iframe[id^="google_ads"], iframe[id^="aswift"], .google-auto-placed').forEach(node => node.remove());
  if (Array.isArray(window.adsbygoogle)) window.adsbygoogle.length = 0;
  scriptReady = false;
}
function leaveAdDocument(url: string, replace = false) {
  navigationPending = true;
  editorialEligible = false;
  removeAdArtifacts();
  publish();
  if (replace) window.location.replace(url);
  else window.location.assign(url);
}

export function setPageEditorialEligibility(value: boolean) {
  editorialPage = pageKey();
  editorialEligible = value;
  publish();
  if (!value && adsStarted && adsDocument === pageKey() && !navigationPending) leaveAdDocument(window.location.href, true);
}

function consentFromTCData(data: TCData, success: boolean): ConsentState {
  if (!success || data.cmpStatus !== 'loaded' || !['tcloaded', 'useractioncomplete'].includes(data.eventStatus || '')) return 'unknown';
  if (data.gdprApplies === false) return 'granted';
  if (data.gdprApplies !== true || !data.tcString) return 'unknown';
  const purposes = data.purpose;
  const vendors = data.vendor;
  // Google vendor 755: storage and personalized advertising require affirmative consent.
  const personalized = [1, 3, 4].every(id => purposes?.consents?.[id] === true) && vendors?.consents?.[755] === true;
  const supporting = [2, 7, 9, 10].every(id => purposes?.consents?.[id] === true || purposes?.legitimateInterests?.[id] === true);
  const vendorBasis = vendors?.consents?.[755] === true || vendors?.legitimateInterests?.[755] === true;
  return personalized && supporting && vendorBasis ? 'granted' : 'denied';
}
function registerConsentListener() {
  if (listenerRegistered || !window.__tcfapi || isPublisherCapture()) return;
  listenerRegistered = true;
  try {
    window.__tcfapi('addEventListener', 2, (data, success) => {
      consent = consentFromTCData(data || {}, success);
      publish();
      if (consent !== 'granted' && adsStarted && !navigationPending) {
        leaveAdDocument(data?.eventStatus === 'cmpuishown' ? '/cookie-policy#privacy-settings' : window.location.href, true);
      }
    });
  } catch {
    listenerRegistered = false;
    consent = 'unknown';
    publish();
  }
}
function loadPrivacyMessaging(): Promise<void> {
  if (isPublisherCapture() || !publisher) return Promise.reject(new Error('Google privacy messaging is unavailable.'));
  if (window.googlefc?.showRevocationMessage && window.__tcfapi) {
    registerConsentListener();
    return Promise.resolve();
  }
  if (cmpPromise) return cmpPromise;
  cmpPromise = new Promise<void>((resolve, reject) => {
    let settled = false;
    const timeout = window.setTimeout(() => finish(new Error('Google privacy messaging did not become ready.')), 10000);
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      if (error) reject(error);
      else { registerConsentListener(); resolve(); }
    };
    window.googlefc = window.googlefc || { callbackQueue: [] };
    window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
    window.googlefc.callbackQueue.push({ CONSENT_API_READY: () => { registerConsentListener(); finish(); } });
    if (!document.getElementById('countrydle-funding-choices')) {
      const script = document.createElement('script');
      script.id = 'countrydle-funding-choices';
      script.async = true;
      script.src = `https://fundingchoicesmessages.google.com/i/${publisher.slice(3)}?ers=1`;
      script.onerror = () => { script.remove(); finish(new Error('Google privacy messaging could not load.')); };
      document.head.appendChild(script);
    }
  }).catch(error => { cmpPromise = null; throw error; });
  return cmpPromise;
}

export async function openPrivacySettings(): Promise<void> {
  if (isPublisherCapture()) throw new Error('Privacy messaging is disabled during publisher capture.');
  if (adsStarted) {
    leaveAdDocument('/cookie-policy#privacy-settings');
    return;
  }
  await loadPrivacyMessaging();
  if (!window.googlefc?.showRevocationMessage) throw new Error('Google privacy settings are unavailable.');
  window.googlefc.showRevocationMessage();
}

export function initializeAdvertisingPolicy() {
  if (initialized || isPublisherCapture()) return;
  initialized = true;
  // History interception runs before React Router. Once ads are active, every page change
  // uses a fresh document, including reviewed -> loading/unreviewed blog transitions.
  for (const method of ['pushState', 'replaceState'] as const) {
    const original = window.history[method].bind(window.history);
    window.history[method] = (state: unknown, unused: string, url?: string | URL | null) => {
      const target = url == null ? new URL(window.location.href) : new URL(url, window.location.href);
      if (adsStarted && (target.pathname + target.search !== adsDocument)) {
        leaveAdDocument(target.href, method === 'replaceState');
        return;
      }
      original(state, unused, url);
      if (target.pathname + target.search !== editorialPage) editorialEligible = false;
      publish();
    };
  }
  window.addEventListener('popstate', () => {
    if (adsStarted && pageKey() !== adsDocument) leaveAdDocument(window.location.href, true);
    else { editorialEligible = false; publish(); }
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted && adsStarted) leaveAdDocument(window.location.href, true);
  });
  if (routePath(window.location.pathname) === '/cookie-policy' && window.location.hash === '#privacy-settings') {
    // The button surfaces this event rather than pretending the message opened.
    void openPrivacySettings().catch(() => window.dispatchEvent(new Event('countrydle:privacy-unavailable')));
  }
}

function loadAds() {
  if (!eligible() || adsStarted) return;
  adsStarted = true;
  adsDocument = pageKey();
  const script = document.createElement('script');
  script.id = 'countrydle-adsense';
  script.dataset.countrydleAd = 'script';
  script.async = true;
  script.crossOrigin = 'anonymous';
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${publisher}`;
  script.onload = () => { if (eligible() && adsDocument === pageKey()) { scriptReady = true; publish(); } };
  script.onerror = () => { scriptReady = false; publish(); };
  document.head.appendChild(script);
}

export function useAdvertisingPolicy() {
  useSyncExternalStore(subscribe, () => revision, () => 0);
  const location = useLocation();
  const capture = isPublisherCapture();
  const contentRoute = isPublicRoute(location.pathname) || (requiresLoadedContent(routePath(location.pathname)) && editorialEligible && editorialPage === location.pathname + location.search);
  const allowed = eligible(location.pathname, location.pathname + location.search);
  useEffect(() => {
    if (!capture && configured && contentRoute) void loadPrivacyMessaging().catch(() => { consent = 'unknown'; publish(); });
    if (allowed) loadAds();
  }, [capture, contentRoute, allowed]);
  return { eligible: allowed, configured, consent, scriptReady, capture };
}
export function useAdvertisingEligibility(): boolean {
  return useAdvertisingPolicy().eligible;
}
export function getAdvertisingUnit(placement: string): { client: string; slot: string } | null {
  if (!configured || !Object.hasOwn(placements, placement)) return null;
  return { client: publisher, slot: placements[placement] };
}
export function requestAdvertisingUnit(element: HTMLElement, placement: string): boolean {
  if (!eligible() || !scriptReady || !getAdvertisingUnit(placement) || !element.isConnected || element.dataset.adsbygoogleStatus) return false;
  try {
    (window.adsbygoogle ||= [] as Record<string, never>[]).push({});
    return true;
  } catch {
    return false;
  }
}
