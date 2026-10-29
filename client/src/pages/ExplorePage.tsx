import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, 
  Globe, 
  Play, 
  ChevronRight, 
  X,
  Compass,
  BookOpen,
  Shield,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Sun,
  Moon,
  MapPin,
  Layers
} from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';
import { exploreService } from '../services/api';
import { setPageEditorialEligibility } from '../advertising';

type TabType = 'modes' | 'powiats' | 'voivodeships' | 'countries' | 'us_states';
type CountyTypeFilter = 'all' | 'land' | 'city';

type LoadStatus = 'idle' | 'loading' | 'success' | 'error';
const GUIDE_IDS: Record<string, string> = { countrydle: 'countrydle', us_statedle: 'us-states', wojewodztwodle: 'wojewodztwa', powiatdle: 'powiaty', flagdle: 'flagdle', europe: 'europe', asia: 'asia', africa: 'africa', americas: 'americas' };
const regionalDisplay: Record<string, string> = {
  centrum: 'Central', południe: 'South', 'południowe centrum': 'South central',
  'południowy wschód': 'Southeast', 'południowy zachód': 'Southwest', północ: 'North',
  'północne centrum': 'North central', 'północny wschód': 'Northeast',
  'północny zachód': 'Northwest', wschód: 'East', 'zachodnie centrum': 'West central', zachód: 'West',
  Białoruś: 'Belarus', Czechy: 'Czechia', Litwa: 'Lithuania', Niemcy: 'Germany',
  Rosja: 'Russia', Słowacja: 'Slovakia', Ukraina: 'Ukraine',
};

function foldPolish(str: string): string {
  return str
    .toLowerCase()
    .replace(/ą/g, 'a')
    .replace(/ć/g, 'c')
    .replace(/ę/g, 'e')
    .replace(/ł/g, 'l')
    .replace(/ń/g, 'n')
    .replace(/ó/g, 'o')
    .replace(/ś/g, 's')
    .replace(/ź/g, 'z')
    .replace(/ż/g, 'z');
}

function MiniLicensePlate({ plates }: { plates: string[] }) {
  if (!plates || plates.length === 0) return null;
  return (
    <div className="inline-flex flex-wrap items-center gap-1">
      {plates.map((plate) => (
        <span
          key={plate}
          className="inline-flex items-stretch overflow-hidden rounded-[3px] border border-zinc-400 bg-white text-obsidian-950 shadow-xs font-mono"
          title={`Registration plate: ${plate}`}
        >
          <span className="flex flex-col items-center justify-center bg-[#003399] px-1 py-0.5 text-[7px] font-bold leading-none text-white">
            PL
          </span>
          <span className="px-1.5 py-0.5 text-[11px] font-extrabold tracking-wider text-zinc-950">
            {plate}
          </span>
        </span>
      ))}
    </div>
  );
}
function initialView() {
  return new URLSearchParams(window.__COUNTRYDLE_PRERENDER__ ? '' : window.location.hash.slice(1));
}

// Keep the requested view across the clean-document boundary used to unload ads.
function rememberView(key: string, value: string) {
  const view = new URLSearchParams(window.location.hash.slice(1));
  if (value) view.set(key, value);
  else view.delete(key);
  const hash = view.toString();
  window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search + (hash ? `#${hash}` : ''));
}

export default function ExplorePage() {

  const [activeTab, updateActiveTab] = useState<TabType>(() => {
    const tab = initialView().get('tab');
    return tab === 'powiats' || tab === 'countries' || tab === 'us_states' || tab === 'voivodeships' ? tab : 'modes';
  });
  const [search, updateSearch] = useState(() => initialView().get('q') || '');
  const [selectedRegion, updateSelectedRegion] = useState(() => initialView().get('region') || 'all');
  const [countyTypeFilter, setCountyTypeFilter] = useState<CountyTypeFilter>('all');
  const [powiatPage, setPowiatPage] = useState<number>(1);
  const [lightCoatsBackdrop, setLightCoatsBackdrop] = useState<boolean>(false);

  const setActiveTab = (tab: TabType) => { rememberView('tab', tab === 'modes' ? '' : tab); updateActiveTab(tab); setPowiatPage(1); };
  const setSearch = (value: string) => { rememberView('q', value); updateSearch(value); setPowiatPage(1); };
  const setSelectedRegion = (value: string) => { rememberView('region', value === 'all' ? '' : value); updateSelectedRegion(value); setPowiatPage(1); };

  const [modes, setModes] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [usStates, setUsStates] = useState<any[]>([]);
  const [voivodeships, setVoivodeships] = useState<any[]>([]);
  const [powiats, setPowiats] = useState<any[]>([]);
  const [loadStatus, setLoadStatus] = useState<Record<TabType, LoadStatus>>({
    modes: 'idle',
    powiats: 'idle',
    voivodeships: 'idle',
    countries: 'idle',
    us_states: 'idle',
  });

  // Selected Entity Modal
  const [selectedCountry, updateSelectedCountry] = useState<any | null>(null);
  const [selectedState, updateSelectedState] = useState<any | null>(null);
  const [selectedVoivodeship, updateSelectedVoivodeship] = useState<any | null>(null);
  const [selectedPowiat, updateSelectedPowiat] = useState<any | null>(null);

  // Fullscreen Coat of Arms / Flag Lightbox
  const [inspectedAsset, setInspectedAsset] = useState<{
    url: string;
    title: string;
    subtitle?: string;
  } | null>(null);
  const [inspectZoom, setInspectZoom] = useState<number>(1);

  const setSelectedCountry = (value: typeof selectedCountry) => { if (!value) rememberView('detail', ''); updateSelectedCountry(value); };
  const setSelectedState = (value: typeof selectedState) => { if (!value) rememberView('detail', ''); updateSelectedState(value); };
  const setSelectedVoivodeship = (value: typeof selectedVoivodeship) => { if (!value) rememberView('detail', ''); updateSelectedVoivodeship(value); };
  const setSelectedPowiat = (value: typeof selectedPowiat) => { if (!value) rememberView('detail', ''); updateSelectedPowiat(value); };
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState('');
  useEffect(() => {
    let cancelled = false;
    setLoadStatus(prev => ({ ...prev, modes: 'loading' }));
    exploreService.getModes().then(data => {
      if (!Array.isArray(data) || data.some(mode => !mode || !GUIDE_IDS[mode.id] || typeof mode.name !== 'string' || !mode.name.trim() || typeof mode.description !== 'string' || !mode.description.trim() || typeof mode.path !== 'string' || !mode.path.startsWith('/') || mode.path.startsWith('//') || !Number.isFinite(mode.entity_count) || !Number.isFinite(mode.question_limit) || !Number.isFinite(mode.guess_limit))) throw new Error('Invalid guide response');
      if (cancelled) return;
      setModes(data);
      setLoadStatus(prev => ({ ...prev, modes: 'success' }));
    }).catch(() => {
      if (!cancelled) setLoadStatus(prev => ({ ...prev, modes: 'error' }));
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (activeTab === 'modes') return;
    const existingCount =
      activeTab === 'countries'
        ? countries.length
        : activeTab === 'us_states'
        ? usStates.length
        : activeTab === 'voivodeships'
        ? voivodeships.length
        : powiats.length;
    if (existingCount > 0) return;
    let cancelled = false;
    const tab = activeTab;
    setLoadStatus(prev => ({ ...prev, [tab]: 'loading' }));
    const request =
      tab === 'countries'
        ? exploreService.getCountries({ limit: 250 })
        : tab === 'us_states'
        ? exploreService.getUSStates()
        : tab === 'voivodeships'
        ? exploreService.getVoivodeships()
        : exploreService.getPowiats();
    request.then(data => {
      if (!Array.isArray(data) || data.some(item => !item || typeof (tab === 'countries' ? item.app_country_name : item.name) !== 'string')) throw new Error('Invalid fact response');
      if (cancelled) return;
      if (tab === 'countries') setCountries(data);
      else if (tab === 'us_states') setUsStates(data);
      else if (tab === 'voivodeships') setVoivodeships(data);
      else setPowiats(data);
      setLoadStatus(prev => ({ ...prev, [tab]: 'success' }));
    }).catch(() => {
      if (!cancelled) setLoadStatus(prev => ({ ...prev, [tab]: 'error' }));
    });
    return () => { cancelled = true; };
  }, [activeTab, countries.length, usStates.length, voivodeships.length, powiats.length]);
  // Load detailed entity for modal
  const openCountryModal = async (cca3: string) => {
    rememberView('detail', `country:${cca3}`);
    setModalError('');
    setModalLoading(true);
    try {
      const data = await exploreService.getCountryDetail(cca3);
      setSelectedCountry(data);
    } catch {
      setModalError('The country fact sheet could not be loaded. Close it and try again.');
    } finally {
      setModalLoading(false);
    }
  };

  const openStateModal = async (name: string) => {
    rememberView('detail', `state:${name}`);
    setModalError('');
    setModalLoading(true);
    try {
      const data = await exploreService.getUSStateDetail(name);
      setSelectedState(data);
    } catch {
      setModalError('The state fact sheet could not be loaded. Close it and try again.');
    } finally {
      setModalLoading(false);
    }
  };

  const openVoivodeshipModal = async (name: string) => {
    rememberView('detail', `voivodeship:${name}`);
    setModalError('');
    setModalLoading(true);
    try {
      const data = await exploreService.getVoivodeshipDetail(name);
      setSelectedVoivodeship(data);
    } catch {
      setModalError('The voivodeship fact sheet could not be loaded. Close it and try again.');
    } finally {
      setModalLoading(false);
    }
  };
  const openPowiatModal = async (nameOrId: string | number) => {
    rememberView('detail', `powiat:${nameOrId}`);
    setModalError('');
    setModalLoading(true);
    try {
      const data = await exploreService.getPowiatDetail(nameOrId);
      setSelectedPowiat(data);
    } catch {
      setModalError('The county fact sheet could not be loaded. Close it and try again.');
    } finally {
      setModalLoading(false);
    }
  };

  useEffect(() => {
    const detail = initialView().get('detail');
    if (!detail) return;
    const separator = detail.indexOf(':');
    const kind = detail.slice(0, separator);
    const identifier = detail.slice(separator + 1);
    if (!identifier || !['country', 'state', 'voivodeship', 'powiat'].includes(kind)) {
      setModalError('This fact sheet address is not recognized. Close it to return to the explorer.');
      return;
    }
    let cancelled = false;
    setModalLoading(true);
    const request =
      kind === 'country'
        ? exploreService.getCountryDetail(identifier)
        : kind === 'state'
        ? exploreService.getUSStateDetail(identifier)
        : kind === 'voivodeship'
        ? exploreService.getVoivodeshipDetail(identifier)
        : exploreService.getPowiatDetail(identifier);
    request.then(data => {
      if (!data || typeof data !== 'object') throw new Error('Invalid fact sheet');
      if (cancelled) return;
      if (kind === 'country') updateSelectedCountry(data);
      else if (kind === 'state') updateSelectedState(data);
      else if (kind === 'voivodeship') updateSelectedVoivodeship(data);
      else updateSelectedPowiat(data);
    }).catch(() => {
      if (!cancelled) setModalError('The requested fact sheet could not be loaded. Close it and try again.');
    }).finally(() => {
      if (!cancelled) setModalLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!inspectedAsset) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setInspectedAsset(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [inspectedAsset]);
  // Filtered lists
  const filteredCountries = useMemo(() => {
    return countries.filter((c) => {
      const matchesSearch = !search || 
        c.app_country_name.toLowerCase().includes(search.toLowerCase()) ||
        (c.capital && c.capital.toLowerCase().includes(search.toLowerCase())) ||
        (c.official_name && c.official_name.toLowerCase().includes(search.toLowerCase()));
      const matchesRegion = selectedRegion === 'all' || c.region === selectedRegion;
      return matchesSearch && matchesRegion;
    });
  }, [countries, search, selectedRegion]);

  const filteredUSStates = useMemo(() => {
    return usStates.filter((s) => {
      const matchesSearch = !search || 
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        (s.nickname && s.nickname.toLowerCase().includes(search.toLowerCase()));
      const matchesRegion = selectedRegion === 'all' || s.region === selectedRegion;
      return matchesSearch && matchesRegion;
    });
  }, [usStates, search, selectedRegion]);

  const filteredVoivodeships = useMemo(() => {
    return voivodeships.filter((v) => {
      return !search || 
        v.name.toLowerCase().includes(search.toLowerCase()) ||
        (v.seat && v.seat.toLowerCase().includes(search.toLowerCase()));
    });
  }, [voivodeships, search]);
  const filteredPowiats = useMemo(() => {
    const q = foldPolish(search.trim());
    return powiats.filter((p) => {
      if (selectedRegion !== 'all' && p.voivodeship.toLowerCase() !== selectedRegion.toLowerCase()) {
        return false;
      }
      if (countyTypeFilter === 'city' && !p.is_city_county) return false;
      if (countyTypeFilter === 'land' && p.is_city_county) return false;
      if (!q) return true;
      const nameMatch = foldPolish(p.name).includes(q);
      const seatMatch = p.seat ? foldPolish(p.seat).includes(q) : false;
      const voivMatch = foldPolish(p.voivodeship).includes(q);
      const plateMatch = Array.isArray(p.registration_plates)
        ? p.registration_plates.some((code: string) => code.toLowerCase().includes(q))
        : false;
      return nameMatch || seatMatch || voivMatch || plateMatch;
    });
  }, [powiats, search, selectedRegion, countyTypeFilter]);

  const POWIATS_PER_PAGE = 48;
  const totalPowiatPages = Math.max(1, Math.ceil(filteredPowiats.length / POWIATS_PER_PAGE));
  const pagedPowiats = useMemo(() => {
    const start = (powiatPage - 1) * POWIATS_PER_PAGE;
    return filteredPowiats.slice(start, start + POWIATS_PER_PAGE);
  }, [filteredPowiats, powiatPage]);

  const regions = useMemo(() => {
    if (activeTab === 'countries') {
      return ['all', 'Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];
    }
    if (activeTab === 'us_states') {
      return ['all', 'Northeast', 'Midwest', 'South', 'West'];
    }
    if (activeTab === 'powiats') {
      return [
        'all',
        'dolnośląskie',
        'kujawsko-pomorskie',
        'lubelskie',
        'lubuskie',
        'łódzkie',
        'małopolskie',
        'mazowieckie',
        'opolskie',
        'podkarpackie',
        'podlaskie',
        'pomorskie',
        'śląskie',
        'świętokrzyskie',
        'warmińsko-mazurskie',
        'wielkopolskie',
        'zachodniopomorskie',
      ];
    }
    return ['all'];
  }, [activeTab]);

  const status = loadStatus[activeTab];
  const loading = status === 'idle' || status === 'loading';
  const visibleCount =
    activeTab === 'modes'
      ? modes.length
      : activeTab === 'countries'
      ? filteredCountries.length
      : activeTab === 'us_states'
      ? filteredUSStates.length
      : activeTab === 'voivodeships'
      ? filteredVoivodeships.length
      : filteredPowiats.length;
  const detailOpen =
    modalLoading ||
    Boolean(
      modalError ||
        selectedCountry ||
        selectedState ||
        selectedVoivodeship ||
        selectedPowiat ||
        initialView().get('detail')
    );
  const publisherReady = status === 'success' && visibleCount > 0 && !detailOpen;
  const publisherError = status === 'error' || Boolean(modalError) || (status === 'success' && visibleCount === 0);

  useEffect(() => {
    setPageEditorialEligibility(publisherReady);
  }, [publisherReady]);

  useEffect(() => () => setPageEditorialEligibility(false), []);

  const resolvePowiatCoatUrl = (powiatId: number) => `/api/explore/powiats/${powiatId}/coat?v=2`;
  const resolvePowiatCoatThumbUrl = (powiatId: number) => `/coats/${powiatId}.png`;

  return (
    <div data-publisher-ready={publisherReady ? 'true' : undefined} data-publisher-error={publisherError ? 'true' : undefined} className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 md:py-12">
      {/* Header & Interactive Atlas Switcher */}
      <header className="border-b border-white/10 pb-6 text-center sm:text-left">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 font-mono text-xs uppercase tracking-widest text-emerald-400">
          <Globe size={13} />
          <span>{'Geographic & Heraldic Knowledge Base'}</span>
        </div>
        <h1 className="font-serif text-3xl font-bold tracking-tight text-sand-100 sm:text-5xl">
          {'Geography Atlas, County Coats of Arms & Guides'}
        </h1>
        <p className="mt-3 max-w-3xl text-sm sm:text-base leading-7 text-zinc-300">
          {'Explore all 380 Polish counties with official coats of arms, registration plate codes and basic facts, 16 Polish voivodeships, 195 world countries with flags, 50 US states, and deduction strategy guides.'}
        </p>

        {/* Redesigned Category Cards Switcher */}
        <div className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
          <button
            type="button"
            onClick={() => { setActiveTab('powiats'); setSearch(''); setSelectedRegion('all'); }}
            className={`group flex flex-col items-start justify-between rounded-md border p-3.5 text-left transition-all cursor-pointer ${
              activeTab === 'powiats'
                ? 'border-emerald-400 bg-emerald-500/15 text-sand-100 shadow-lg shadow-emerald-950/30'
                : 'border-white/10 bg-obsidian-900/70 text-zinc-300 hover:border-emerald-500/40 hover:bg-obsidian-900'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <Shield size={16} className={activeTab === 'powiats' ? 'text-emerald-300' : 'text-emerald-400/80'} />
              <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                380
              </span>
            </div>
            <div className="mt-2.5">
              <div className="font-serif text-sm font-bold text-sand-100">
                {'Polish Counties'}
              </div>
              <div className="mt-0.5 text-[11px] text-zinc-400">
                {'Coats of arms & facts'}
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab('voivodeships'); setSearch(''); setSelectedRegion('all'); }}
            className={`group flex flex-col items-start justify-between rounded-md border p-3.5 text-left transition-all cursor-pointer ${
              activeTab === 'voivodeships'
                ? 'border-emerald-400 bg-emerald-500/15 text-sand-100 shadow-lg shadow-emerald-950/30'
                : 'border-white/10 bg-obsidian-900/70 text-zinc-300 hover:border-emerald-500/40 hover:bg-obsidian-900'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <Layers size={16} className={activeTab === 'voivodeships' ? 'text-emerald-300' : 'text-emerald-400/80'} />
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-sand-200">
                16
              </span>
            </div>
            <div className="mt-2.5">
              <div className="font-serif text-sm font-bold text-sand-100">
                {'Voivodeships'}
              </div>
              <div className="mt-0.5 text-[11px] text-zinc-400">
                {'Polish provinces'}
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab('countries'); setSearch(''); setSelectedRegion('all'); }}
            className={`group flex flex-col items-start justify-between rounded-md border p-3.5 text-left transition-all cursor-pointer ${
              activeTab === 'countries'
                ? 'border-emerald-400 bg-emerald-500/15 text-sand-100 shadow-lg shadow-emerald-950/30'
                : 'border-white/10 bg-obsidian-900/70 text-zinc-300 hover:border-emerald-500/40 hover:bg-obsidian-900'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <Globe size={16} className={activeTab === 'countries' ? 'text-emerald-300' : 'text-emerald-400/80'} />
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-sand-200">
                195
              </span>
            </div>
            <div className="mt-2.5">
              <div className="font-serif text-sm font-bold text-sand-100">
                {'World Countries'}
              </div>
              <div className="mt-0.5 text-[11px] text-zinc-400">
                {'Flags, capitals & borders'}
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab('us_states'); setSearch(''); setSelectedRegion('all'); }}
            className={`group flex flex-col items-start justify-between rounded-md border p-3.5 text-left transition-all cursor-pointer ${
              activeTab === 'us_states'
                ? 'border-emerald-400 bg-emerald-500/15 text-sand-100 shadow-lg shadow-emerald-950/30'
                : 'border-white/10 bg-obsidian-900/70 text-zinc-300 hover:border-emerald-500/40 hover:bg-obsidian-900'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <MapPin size={16} className={activeTab === 'us_states' ? 'text-emerald-300' : 'text-emerald-400/80'} />
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-sand-200">
                50
              </span>
            </div>
            <div className="mt-2.5">
              <div className="font-serif text-sm font-bold text-sand-100">
                {'US States'}
              </div>
              <div className="mt-0.5 text-[11px] text-zinc-400">
                {'Regions & state facts'}
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab('modes'); setSearch(''); }}
            className={`col-span-2 sm:col-span-1 group flex flex-col items-start justify-between rounded-md border p-3.5 text-left transition-all cursor-pointer ${
              activeTab === 'modes'
                ? 'border-emerald-400 bg-emerald-500/15 text-sand-100 shadow-lg shadow-emerald-950/30'
                : 'border-white/10 bg-obsidian-900/70 text-zinc-300 hover:border-emerald-500/40 hover:bg-obsidian-900'
            }`}
          >
            <div className="flex w-full items-center justify-between">
              <Compass size={16} className={activeTab === 'modes' ? 'text-emerald-300' : 'text-emerald-400/80'} />
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-sand-200">
                {'Guides'}
              </span>
            </div>
            <div className="mt-2.5">
              <div className="font-serif text-sm font-bold text-sand-100">
                {'Mode Guides'}
              </div>
              <div className="mt-0.5 text-[11px] text-zinc-400">
                {'Rules & deduction axes'}
              </div>
            </div>
          </button>
        </div>
      </header>

      {loading && <p role="status" className="text-base leading-7 text-zinc-400">Loading {activeTab === 'modes' ? 'mode guides' : 'geography facts'}…</p>}
      {status === 'error' && <p role="alert" className="text-base leading-7 text-amber-300">This content could not be loaded. Reload the page to try again; no substitute data is shown.</p>}
      {status === 'success' && visibleCount === 0 && <p role="status" className="text-base leading-7 text-zinc-400">No entries match this view. Clear the search or choose another region; an empty response is not evidence that a place is absent from the game.</p>}
      {modalLoading && <p role="status" className="text-base leading-7 text-zinc-400">Loading fact sheet…</p>}
      {modalError && <div role="alert" className="space-y-3 text-amber-300"><p>{modalError}</p><button type="button" onClick={() => { rememberView('detail', ''); setModalError(''); }} className="underline underline-offset-4">Close fact sheet error</button></div>}
      {activeTab === 'modes' && (
        <section className="space-y-6">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {modes.map((mode) => (
              <div
                key={mode.id}
                className="flex flex-col justify-between rounded-md border border-white/10 bg-obsidian-900/60 p-6 transition-colors hover:border-emerald-500/30"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-bold">
                      {mode.entity_count} Entities
                    </span>
                    <span className="font-mono text-[11px] text-zinc-500">
                      {mode.question_limit} Qs · {mode.guess_limit} Guesses
                    </span>
                  </div>
                  <h3 className="font-serif text-2xl font-semibold text-sand-100">
                    {mode.name}
                  </h3>
                  <p className="text-sm leading-6 text-zinc-400">
                    {mode.id === 'countrydle' ? 'Deduce a playable country using factual yes/no questions. The game catalog is distinct from a UN membership list and from map-boundary data.' : mode.description}
                  </p>
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
                  <Link
                    to={`/explore/modes/${GUIDE_IDS[mode.id]}`}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    <span>{'Read Strategy Guide'}</span>
                    <ChevronRight size={14} />
                  </Link>
                  <Link
                    to={mode.path}
                    className="inline-flex items-center gap-1.5 rounded-sm bg-white/10 px-3 py-1.5 text-xs font-medium text-sand-100 hover:bg-emerald-400 hover:text-obsidian-950 transition-colors"
                  >
                    <Play size={12} />
                    <span>{'Play Mode'}</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>

          {/* Section A — Comparative Overview of All 9 Daily Geography Modes */}
          <article aria-labelledby="modes-comparative-overview" className="mt-12 space-y-6 rounded-lg border border-white/10 bg-obsidian-900/40 p-6 md:p-8">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-emerald-400">
                <Compass size={14} aria-hidden="true" />
                <span>{'Daily Game Mechanics'}</span>
              </div>
              <h2 id="modes-comparative-overview" className="font-serif text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">
                {'Section A — Comparative Overview of All 9 Daily Geography Modes'}
              </h2>
              <p className="max-w-4xl text-sm leading-relaxed text-zinc-300 md:text-base">
                {'Countrydle offers 9 specialized daily deductive challenges spanning diverse spatial scales — from global sovereign states down to subnational counties and flags. Each mode balances a tailored question budget against a strict guess limit, rewarding systematic elimination over unstructured guessing. The comparative reference table below summarizes pool dimensions, question constraints, guess allowances, primary geographic axes, and direct links to comprehensive strategy guides.'}
              </p>
            </div>

            <div className="overflow-x-auto rounded-md border border-white/10 bg-obsidian-950/80">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-white/10 bg-white/5 font-mono text-xs uppercase tracking-wider text-sand-100">
                  <tr>
                    <th scope="col" className="px-4 py-3.5">Mode & Guide</th>
                    <th scope="col" className="px-4 py-3.5">Pool Size</th>
                    <th scope="col" className="px-4 py-3.5">Questions</th>
                    <th scope="col" className="px-4 py-3.5">Guesses</th>
                    <th scope="col" className="px-4 py-3.5">Primary Geographic Axes & Invariants</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-zinc-300">
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/countrydle" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Countrydle — World Countries
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">195 playable countries</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">10 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Global physical continents (Africa, Asia, Europe, North America, South America, Oceania) and UN statistical regions; 4 global coordinate quadrants relative to the Equator (0°) and Prime Meridian (0°); open marine coastlines versus landlocked enclaves; direct land border topologies; population and surface area (km²) thresholds. Includes Kosovo; excludes Israel from playable targets.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/flagdle" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Flagdle — Daily Flag Reveal
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">195 national flags</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-zinc-400">Unlimited helper Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">12 tiles / guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Vexillological geometry (horizontal/vertical bicolors, tricolors, Nordic crosses, saltires, cantons, triangles); primary heraldic tinctures (red, white, blue, yellow, green, black); national emblems (stars, crescents, suns, coats of arms); regional cultural color schemes (Pan-African, Pan-Arab, Pan-Slavic). Progressive 12-tile visual unmasking.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/europe" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Europedle — Europe
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">44 European countries</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">8 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      European macroregions (Nordic Fennoscandia, Western Europe, Central Europe, Eastern European Plain, Mediterranean/Southern Europe, Balkans); marginal and connected seas (Baltic, North, Mediterranean, Adriatic, Black Sea); 16 landlocked European states; Schengen Area and EU boundaries; Alpine and Carpathian mountain chains. Excludes transcontinental Kazakhstan, Azerbaijan, and Georgia.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/asia" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Asiadle — Asia
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">48 Asian countries</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">8 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Asian geographic realms (West Asia/Middle East, Central Asia, South Asia, East Asia, Southeast Asia); oceanic drainage (Indian, Pacific, Arctic) vs. major endorheic terminal basins (Caspian Sea, Aral Sea); archipelagic maritime nations (Indonesia, Philippines, Japan) vs. landlocked Central Asian republics; Himalayan and Hindu Kush topographic barriers. Excludes Egypt.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/africa" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Africadle — Africa
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">54 African nations</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">8 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      UN subregions (North Africa/Maghreb, West Africa, Central Africa, East Africa, Southern Africa); oceanic and marginal water bodies (Atlantic Ocean, Indian Ocean, Mediterranean Sea, Red Sea); Great East African Rift Valley; Sahel transition belt; 7 Equator-straddling countries; 16 landlocked African states.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/americas" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Americadle — The Americas
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">35 American nations</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">8 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Continental realms (North America, Central American isthmus, Caribbean island nations, South America); dual-ocean interfaces (Atlantic/Caribbean vs. Pacific); continuous Andean cordillera and Amazonian river basin; 2 landlocked South American nations (Bolivia, Paraguay); normalized borders (French Guiana mapped as a land border with France).
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/us-states" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        US Statedle — 50 States
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">50 US states</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">8 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      US Census Bureau 4 official regions (Northeast, Midwest, South, West) and 9 divisions; marine coastlines (Atlantic Ocean direct, Gulf of Mexico, Pacific Ocean) vs. freshwater Great Lakes shorelines; Mississippi-Missouri river drainage; Appalachian and Rocky Mountain orographic divides; statehood admission chronology (1787–1959). Excludes Washington, D.C. and US territories.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/wojewodztwa" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Województwodle — 16 Voivodeships
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">16 Polish voivodeships</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">5 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-amber-300 font-bold">2 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Historical Polish lands (Wielkopolska, Małopolska, Mazowsze, Śląsk, Pomorze, Warmia i Mazury); Baltic Sea open maritime coastline (Pomorskie, Zachodniopomorskie); foreign international frontiers with 7 neighboring sovereign nations; Wisła and Odra river drainage basins; mutual voivodeship adjacency graphs. Tight 5-question / 2-guess budget.
                    </td>
                  </tr>
                  <tr className="hover:bg-white/[0.02] transition-colors">
                    <th scope="row" className="px-4 py-4 font-medium text-sand-100 whitespace-nowrap">
                      <Link to="/explore/modes/powiaty" className="group inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
                        Powiatdle — 380 Counties
                        <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </th>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">380 Polish powiaty</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-emerald-300 font-bold">15 Qs</td>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs text-sand-200">3 guesses</td>
                    <td className="px-4 py-4 text-xs leading-relaxed text-zinc-300">
                      Parent voivodeship jurisdiction (16 clusters); administrative legal status (314 land counties / powiaty ziemskie vs. 66 cities with county rights / miasta na prawach powiatu); vehicle registration plate prefixes (tablice rejestracyjne, 2-letter municipal vs. 3-letter land county); highway networks (A1, A2, A4, S3, S7, S8) and river arteries.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          {/* Section B — Core Geographic Taxonomies & Deductive Principles */}
          <article aria-labelledby="modes-deductive-taxonomies" className="mt-12 space-y-10 rounded-lg border border-white/10 bg-obsidian-900/40 p-6 md:p-8">
            <div className="space-y-2 border-b border-white/10 pb-6">
              <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-emerald-400">
                <BookOpen size={14} aria-hidden="true" />
                <span>{'Geographic Methodology & Theory'}</span>
              </div>
              <h2 id="modes-deductive-taxonomies" className="font-serif text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">
                {'Section B — Core Geographic Taxonomies & Deductive Principles'}
              </h2>
              <p className="max-w-4xl text-sm leading-relaxed text-zinc-300 md:text-base">
                {'Mastering Countrydle requires treating the globe as an interconnected mathematical coordinate system and political-geographic hierarchy. Rather than expending precious questions on subjective traits ("Is it a major power?"), experienced players query well-defined taxonomic boundaries. The educational guides below elucidate three fundamental geographical principles that underpin Countrydle’s deductive engine.'}
              </p>
            </div>

            {/* Subsection 1 */}
            <section aria-labelledby="taxonomy-hemispheres" className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 font-mono text-sm font-bold text-emerald-400">
                  1
                </div>
                <h3 id="taxonomy-hemispheres" className="font-serif text-xl font-semibold text-sand-100 sm:text-2xl">
                  Hemispheres, Equator & Prime Meridian Crossings
                </h3>
              </div>
              <div className="space-y-3 text-sm leading-relaxed text-zinc-300 sm:text-base">
                <p>
                  Earth’s spherical coordinate system partitions the planetary surface into four geometric quadrants through two principal great circles: the <strong>Equator</strong> (0° latitude), which separates the Northern and Southern Hemispheres, and the <strong>Prime Meridian</strong> (0° longitude) paired with the 180° antimeridian, which separates the Eastern and Western Hemispheres. In deductive geography puzzles, players often begin by asking hemisphere questions to bisect the search space. However, a common pitfall is treating sovereign nations as dimensionless mathematical points rather than expansive, two-dimensional spatial polygons.
                </p>
                <p>
                  Sovereign states whose territorial boundaries cross 0° latitude belong physically to <em>both the Northern and Southern Hemispheres simultaneously</em>. When querying territorial attributes in Countrydle, a country straddling the Equator will return an affirmative response for Northern Hemisphere inclusion as well as Southern Hemisphere inclusion. In South America, <strong>Ecuador</strong> (eponymously named after the line), <strong>Colombia</strong>, and <strong>Brazil</strong> have land in both hemispheres, with Brazil extending from +5°N down to −33°S. In Africa, seven sovereign states cross the Equator: <strong>Gabon</strong>, the <strong>Republic of the Congo</strong>, the <strong>Democratic Republic of the Congo</strong>, <strong>Uganda</strong>, <strong>Kenya</strong>, <strong>Somalia</strong>, and the island nation of <strong>São Tomé and Príncipe</strong>. In Southeast Asia, <strong>Indonesia</strong> spans the Equator across major islands including Sumatra, Borneo (Kalimantan), Sulawesi, and Halmahera, while the Pacific island nation of <strong>Kiribati</strong> uniquely straddles both the Equator and the 180° meridian.
                </p>
                <div className="rounded-md border border-white/10 bg-obsidian-950/60 p-4">
                  <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold mb-2">Prime Meridian (0° Longitude) Crossings</h4>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    The Prime Meridian, standardized at the Royal Observatory in Greenwich, London, bisects both Europe and Africa. Three European states cross 0° longitude: the <strong>United Kingdom</strong>, <strong>France</strong>, and <strong>Spain</strong>. In Africa, the Prime Meridian passes through five countries: <strong>Algeria</strong>, <strong>Mali</strong>, <strong>Burkina Faso</strong>, <strong>Ghana</strong>, and <strong>Togo</strong>. Consequently, questions such as <em>"Is it in the Western Hemisphere?"</em> or <em>"Is it in the Eastern Hemisphere?"</em> will both evaluate to true for these trans-meridian countries.
                  </p>
                </div>
                <p>
                  <strong>Strategic Deductive Heuristic:</strong> Querying <em>"Is the country in the Northern Hemisphere?"</em> immediately eliminates approximately 70% of the Earth’s total landmass if the answer is negative, because over two-thirds of all sovereign states lie entirely north of the Equator. Conversely, when an answer confirms Northern Hemisphere presence, a player must not hastily eliminate equatorial states like Brazil, Indonesia, or Kenya without secondary verification of their latitude bounds or centroid.
                </p>
              </div>
            </section>

            {/* Subsection 2 */}
            <section aria-labelledby="taxonomy-marine-endorheic" className="space-y-4 border-t border-white/10 pt-8">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 font-mono text-sm font-bold text-emerald-400">
                  2
                </div>
                <h3 id="taxonomy-marine-endorheic" className="font-serif text-xl font-semibold text-sand-100 sm:text-2xl">
                  Marine Access vs. Endorheic Basins & Inland Lakes
                </h3>
              </div>
              <div className="space-y-3 text-sm leading-relaxed text-zinc-300 sm:text-base">
                <p>
                  A fundamental distinction in physical geography and Countrydle deduction is the hydrological separation between <strong>open marine access</strong> and <strong>endorheic (closed) basins</strong> or inland freshwater lakes. While everyday speech often equates any large body of water with a "coast," international maritime law and geomorphology maintain strict boundary criteria.
                </p>
                <p>
                  <strong>Open Marine Access:</strong> A sovereign country or subnational entity is classified as having marine coastal access if its coastline borders the contiguous World Ocean (Pacific, Atlantic, Indian, Arctic, or Southern Oceans) or marginal and mediterranean seas connected to the global ocean via natural navigable straits. Examples include the <em>Baltic Sea</em> (connected to the Atlantic via the Danish Straits / Kattegat and Skagerrak), the <em>Mediterranean Sea</em> (connected via the Strait of Gibraltar), the <em>Black Sea</em> (connected through the Bosporus, Sea of Marmara, and Dardanelles), the <em>Red Sea</em> (connected via the Bab-el-Mandeb), and the <em>Gulf of Mexico</em> (connected via the Straits of Florida). These marginal water bodies participate in global oceanic circulation, tidal regimes, and saline interchange.
                </p>
                <div className="rounded-md border border-white/10 bg-obsidian-950/60 p-4 space-y-2">
                  <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">The Caspian Sea Endorheic Anomaly</h4>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    Covering roughly 371,000 $km^2$, the <strong>Caspian Sea</strong> is the largest enclosed inland body of water on Earth. Despite its historical name and brackish salinity, it possesses no natural hydrological outlet to the World Ocean; it sits in a continental depression with its surface approximately 28 meters below global sea level. Consequently, the Caspian is an <em>endorheic lake basin</em>.
                  </p>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    In physical geography and Countrydle game rules, countries bordering solely the Caspian Sea — notably <strong>Azerbaijan</strong> and <strong>Turkmenistan</strong> — are classified as <strong>landlocked states</strong> (<em>państwa śródlądowe</em>). A query asking <em>"Is it landlocked?"</em> evaluates to affirmative for Azerbaijan, while asking <em>"Does it border the Caspian Sea?"</em> evaluates separately to affirmative. Shoreline on the Caspian Sea does not confer open marine access.
                  </p>
                </div>
                <p>
                  <strong>Freshwater Great Lakes vs. Marine Coastlines (US Statedle):</strong> The Laurentian Great Lakes (Superior, Michigan, Huron, Erie, Ontario) contain 21% of the world’s surface freshwater. States such as Michigan, Wisconsin, Illinois, Indiana, and Ohio possess thousands of miles of deepwater lacustrine shoreline and commercial shipping channels linked artificially to the Atlantic via the St. Lawrence Seaway. However, in geographic taxonomy, Great Lakes shoreline is freshwater lacustrine frontage, not oceanic coastline. In US Statedle, only states bordering the Atlantic Ocean, Pacific Ocean, Arctic Ocean, or Gulf of Mexico are recognized as coastal states; Great Lakes states are categorized as interior states unless they possess true marine frontage.
                </p>
                <p>
                  <strong>Strategic Deductive Heuristic:</strong> When isolating nations in Eurasia or North America, querying <em>"Is it landlocked?"</em> eliminates 151 coastal nations worldwide while preserving all 44 landlocked states (including Caspian-littoral states). Only expend questions on specific water bodies (e.g., <em>"Does it border the Baltic Sea?"</em> or <em>"Does it border the Gulf of Mexico?"</em>) once the broader marine or continental cluster has been established.
                </p>
              </div>
            </section>

            {/* Subsection 3 */}
            <section aria-labelledby="taxonomy-subnational-hierarchies" className="space-y-4 border-t border-white/10 pt-8">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 font-mono text-sm font-bold text-emerald-400">
                  3
                </div>
                <h3 id="taxonomy-subnational-hierarchies" className="font-serif text-xl font-semibold text-sand-100 sm:text-2xl">
                  Subnational Administrative Hierarchies (US States & Polish Regions)
                </h3>
              </div>
              <div className="space-y-3 text-sm leading-relaxed text-zinc-300 sm:text-base">
                <p>
                  Subnational puzzle modes (US Statedle, Województwodle, Powiatdle) demand mastery of formal administrative subdivisions. Rather than memorizing hundreds of standalone entities in isolation, top players navigate these pools through their standardized hierarchical tiers, statistical regional partitions, and legal administrative classifications.
                </p>
                
                <div className="space-y-3 rounded-md border border-white/10 bg-obsidian-950/60 p-4">
                  <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">US Census Bureau Regional Taxonomy (50 States)</h4>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    The US Census Bureau partitions the 50 states into four official regions, which further subdivide into nine geographic divisions:
                  </p>
                  <ul className="list-disc space-y-1.5 pl-5 text-xs text-zinc-300 sm:text-sm">
                    <li><strong>Northeast Region (9 states):</strong> <em>New England Division</em> (Maine, New Hampshire, Vermont, Massachusetts, Rhode Island, Connecticut) and <em>Middle Atlantic Division</em> (New York, New Jersey, Pennsylvania).</li>
                    <li><strong>Midwest Region (12 states):</strong> <em>East North Central Division</em> (Ohio, Indiana, Illinois, Michigan, Wisconsin) and <em>West North Central Division</em> (Minnesota, Iowa, Missouri, North Dakota, South Dakota, Nebraska, Kansas).</li>
                    <li><strong>South Region (16 states):</strong> <em>South Atlantic Division</em> (Delaware, Maryland, Virginia, West Virginia, North Carolina, South Carolina, Georgia, Florida), <em>East South Central Division</em> (Kentucky, Tennessee, Alabama, Mississippi), and <em>West South Central Division</em> (Arkansas, Louisiana, Oklahoma, Texas).</li>
                    <li><strong>West Region (13 states):</strong> <em>Mountain Division</em> (Montana, Idaho, Wyoming, Colorado, New Mexico, Arizona, Utah, Nevada) and <em>Pacific Division</em> (Washington, Oregon, California, Alaska, Hawaii).</li>
                  </ul>
                  <p className="text-xs text-zinc-400">
                    *Note: Washington, D.C. and US territories (Puerto Rico, Guam, US Virgin Islands, American Samoa, Northern Mariana Islands) are excluded from the 50-state game pool.
                  </p>
                </div>

                <div className="space-y-3 rounded-md border border-white/10 bg-obsidian-950/60 p-4">
                  <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">Poland’s Three-Tier Administrative Structure (16 Voivodeships & 380 Powiaty)</h4>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    Poland’s territorial division, enacted on January 1, 1999 (<em>zasadniczy trójstopniowy podział terytorialny państwa</em>), establishes three hierarchical tiers:
                  </p>
                  <ul className="list-disc space-y-2 pl-5 text-xs text-zinc-300 sm:text-sm">
                    <li>
                      <strong>Tier 1 — 16 Województwa (Voivodeships):</strong> First-order regional administrative units governed by a dual executive: the state-appointed <em>wojewoda</em> (representing the central Council of Ministers) and the regional self-government headed by the <em>marszałek województwa</em> and provincial assembly (<em>sejmik województwa</em>).
                    </li>
                    <li>
                      <strong>Tier 2 — 380 Powiaty (Counties):</strong> The county level is strictly partitioned into two legal categories:
                      <ul className="list-circle space-y-1 pl-5 pt-1 text-zinc-300">
                        <li><strong>314 Powiaty Ziemskie (Land Counties):</strong> Multi-communal districts comprising several urban and rural gminas, administered by a county council (<em>rada powiatu</em>) and an executive board headed by a <em>starosta</em>.</li>
                        <li><strong>66 Miasta na Prawach Powiatu (Cities with County Rights):</strong> Also known historically as <em>powiaty grodzkie</em>. Autonomous municipalities where the city president (<em>prezydent miasta</em>) and city council perform both municipal and county functions simultaneously (e.g., Warszawa, Kraków, Łódź, Wrocław, Poznań, Gdańsk, Szczecin, Katowice).</li>
                      </ul>
                    </li>
                    <li>
                      <strong>Tier 3 — 2,477 Gminy:</strong> The primary local communal level, divided into urban (<em>gminy miejskie</em>), urban-rural (<em>gminy miejsko-wiejskie</em>), and rural (<em>gminy wiejskie</em>) units.
                    </li>
                  </ul>
                </div>

                <div className="rounded-md border border-white/10 bg-obsidian-950/60 p-4">
                  <h4 className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold mb-2">Polish Vehicle Registration Codes (Wyróżniki Tablic Rejestracyjnych)</h4>
                  <p className="text-sm leading-relaxed text-zinc-300">
                    In Powiatdle, vehicle registration plate prefixes provide an authoritative deductive axis. The initial letter designates the parent voivodeship (e.g., <strong>W</strong> for Mazowieckie, <strong>K</strong> for Małopolskie, <strong>D</strong> for Dolnośląskie, <strong>P</strong> for Wielkopolskie, <strong>G</strong> for Pomorskie, <strong>Z</strong> for Zachodniopomorskie, <strong>S</strong> for Śląskie, <strong>E</strong> for Łódzkie, <strong>B</strong> for Podlaskie, <strong>L</strong> for Lubelskie, <strong>R</strong> for Podkarpackie, <strong>T</strong> for Świętokrzyskie, <strong>O</strong> for Opolskie, <strong>C</strong> for Kujawsko-Pomorskie, <strong>F</strong> for Lubuskie, <strong>N</strong> for Warmińsko-Mazurskie). Furthermore, <strong>two-letter prefixes</strong> almost universally denote cities with county rights (e.g., <em>KR</em> for Kraków, <em>PO</em> for Poznań, <em>DW</em> for Wrocław, <em>GD</em> for Gdańsk), whereas <strong>three-letter prefixes</strong> denote land counties (e.g., <em>KRA</em> for powiat krakowski, <em>PZ</em> for powiat poznański, <em>DWR</em> for powiat wrocławski).
                  </p>
                </div>

                <p>
                  <strong>Strategic Deductive Heuristic:</strong> In Powiatdle, discovering whether the secret entity is a city with county rights (<em>miasto na prawach powiatu</em>) immediately tests a 66-versus-314 split, eliminating over 82% of the candidate set if negative. Following up by isolating the parent voivodeship reduces the candidate pool to an average of just 20 to 25 local counties.
                </p>
              </div>
            </section>
          </article>
        </section>
      )}

      {/* Search & Filters Toolbar for Atlas Tabs */}
      {activeTab !== 'modes' && (
        <div className="space-y-4 rounded-lg border border-white/10 bg-obsidian-900/50 p-4">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={
                  activeTab === 'powiats'
                    ? 'Search county name, seat, or license plate prefix (e.g. KRA, PO, BI, krakowski)...'
                    : 'Search by name, capital, or code...'
                }
                className="w-full rounded-sm border border-white/15 bg-obsidian-950 py-2.5 pl-10 pr-9 text-sm text-sand-100 placeholder-zinc-500 focus:border-emerald-400 focus:outline-none"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white cursor-pointer"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {activeTab === 'powiats' && (
              <div className="flex flex-wrap items-center gap-2">
                <div className="inline-flex rounded-sm border border-white/10 bg-obsidian-950 p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('all'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer ${
                      countyTypeFilter === 'all'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'text-zinc-400 hover:text-sand-100'
                    }`}
                  >
                    {'All (380)'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('land'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer ${
                      countyTypeFilter === 'land'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'text-zinc-400 hover:text-sand-100'
                    }`}
                  >
                    {'Land (314)'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('city'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer ${
                      countyTypeFilter === 'city'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'text-zinc-400 hover:text-sand-100'
                    }`}
                  >
                    {'Cities (66)'}
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => setLightCoatsBackdrop((v) => !v)}
                  title={'Toggle light/dark backdrop behind coats of arms'}
                  className={`inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1.5 text-xs font-mono transition-colors cursor-pointer ${
                    lightCoatsBackdrop
                      ? 'border-amber-400/50 bg-sand-100 text-obsidian-950 font-semibold'
                      : 'border-white/15 bg-obsidian-950 text-zinc-300 hover:border-white/30'
                  }`}
                >
                  {lightCoatsBackdrop ? <Sun size={13} /> : <Moon size={13} />}
                  <span>{lightCoatsBackdrop ? ('Light shield bg') : ('Dark shield bg')}</span>
                </button>
              </div>
            )}
          </div>

          {regions.length > 1 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] text-zinc-500 mr-1 font-mono uppercase">
                {activeTab === 'powiats' ? ('Voivodeship:') : 'Region:'}
              </span>
              {regions.map((reg) => (
                <button
                  key={reg}
                  type="button"
                  onClick={() => setSelectedRegion(reg)}
                  className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                    selectedRegion === reg
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
                  }`}
                >
                  {reg === 'all' ? ('All') : reg}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB: Polish Counties & Coats of Arms (380) */}
      {activeTab === 'powiats' && (
        <section className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400 font-mono">
            <span>
              {`Showing ${filteredPowiats.length} of ${powiats.length || 380} Polish counties`}
            </span>
            <div className="flex items-center gap-3">
              <span>{'Click shield to zoom • Click card for full facts'}</span>
              <Link
                to="/herby-powiatow"
                className="inline-flex items-center gap-1 rounded-sm bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-emerald-300 hover:bg-emerald-500/25 font-sans font-semibold"
              >
                <Play size={11} />
                <span>{'Play County Coats of Arms'}</span>
              </Link>
              <Link
                to="/quiz-herbow"
                className="inline-flex items-center gap-1 rounded-sm bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 text-amber-300 hover:bg-amber-500/25 font-sans font-semibold"
              >
                <Shield size={11} />
                <span>{'380 Coats Quiz (JetPunk)'}</span>
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {pagedPowiats.map((p) => {
              const fullCoatUrl = resolvePowiatCoatUrl(p.id);
              const thumbCoatUrl = resolvePowiatCoatThumbUrl(p.id);
              return (
                <div
                  key={p.id}
                  onClick={() => openPowiatModal(p.id)}
                  className="group cursor-pointer rounded-md border border-white/10 bg-obsidian-900/60 p-3.5 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between gap-3"
                >
                  <div className="flex items-start gap-3">
                    {/* Compact Low-Res Coat of Arms Thumbnail with 1-click Fullscreen SVG Icon */}
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setInspectZoom(1);
                        setInspectedAsset({
                          url: fullCoatUrl,
                          title: p.name,
                          subtitle: `Voivodeship ${p.voivodeship} • ${p.is_city_county ? ('City county') : (`Seat: ${p.seat || '—'}`)}`,
                        });
                      }}
                      title={'Inspect coat of arms (full SVG)'}
                      className={`relative h-15 w-13.5 shrink-0 rounded-md border p-1.5 flex items-center justify-center transition-all ${
                        lightCoatsBackdrop
                          ? 'bg-sand-100 border-sand-300 shadow-inner'
                          : 'bg-obsidian-950/90 border-white/10 group-hover:border-emerald-500/30'
                      }`}
                    >
                      <img
                        src={thumbCoatUrl}
                        alt={`Herb: ${p.name}`}
                        width={42}
                        height={48}
                        loading="lazy"
                        decoding="async"
                        className="max-h-11 max-w-10 w-auto h-auto object-contain select-none drop-shadow-xs transition-transform duration-150 group-hover:scale-105"
                      />
                      <span
                        aria-hidden="true"
                        className="absolute bottom-0.5 right-0.5 inline-flex h-4.5 w-4.5 items-center justify-center rounded bg-obsidian-950/85 border border-white/15 text-zinc-300 opacity-75 hover:opacity-100 hover:text-emerald-300 transition-opacity"
                      >
                        <Maximize2 size={10} />
                      </span>
                    </div>
                    {/* County Identity & License Plates */}
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <span className="font-mono text-[10px] uppercase tracking-wider text-emerald-400 font-semibold">
                          Voivodeship {p.voivodeship}
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono text-[9px] uppercase ${
                            p.is_city_county
                              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/25'
                              : 'bg-white/5 text-zinc-400 border border-white/10'
                          }`}
                        >
                          {p.is_city_county
                            ? 'City county'
                            : 'Land county'}
                        </span>
                      </div>

                      <h4 className="font-serif text-base font-bold text-sand-100 group-hover:text-emerald-300 transition-colors leading-snug">
                        {p.name}
                      </h4>

                      <div className="pt-0.5">
                        <MiniLicensePlate plates={p.registration_plates} />
                      </div>
                    </div>
                  </div>

                  <div className="pt-2.5 border-t border-white/5 grid grid-cols-3 gap-2 text-[11px] text-zinc-400 font-mono">
                    <div className="truncate">
                      <span className="text-zinc-500 block text-[10px]">{'Seat'}</span>
                      <span className="text-sand-100 truncate block" title={p.seat || '—'}>
                        {p.seat || '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">{'Pop.'}</span>
                      <span className="text-sand-100 block">
                        {p.population ? Number(p.population).toLocaleString('en-US') : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">{'Area'}</span>
                      <span className="text-sand-100 block">
                        {p.area_km2 ? `${Number(p.area_km2).toLocaleString('en-US')} km²` : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {totalPowiatPages > 1 && (
            <div className="flex items-center justify-between border-t border-white/10 pt-4 font-mono text-xs text-zinc-400">
              <span>
                {`Page ${powiatPage} of ${totalPowiatPages} (${filteredPowiats.length} counties)`}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={powiatPage <= 1}
                  onClick={() => setPowiatPage((p) => Math.max(1, p - 1))}
                  className="rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-sand-100 hover:border-emerald-400 disabled:opacity-40 cursor-pointer"
                >
                  {'Previous'}
                </button>
                <button
                  type="button"
                  disabled={powiatPage >= totalPowiatPages}
                  onClick={() => setPowiatPage((p) => Math.min(totalPowiatPages, p + 1))}
                  className="rounded-sm border border-white/15 bg-obsidian-900 px-3 py-1.5 text-sand-100 hover:border-emerald-400 disabled:opacity-40 cursor-pointer"
                >
                  {'Next'}
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* TAB 2: Countries Grid */}
      {activeTab === 'countries' && (
        <section className="space-y-4">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
            <span>Showing {filteredCountries.length} countries</span>
            <span>Click any card for full fact sheet</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredCountries.map((c) => (
              <div
                key={c.id}
                onClick={() => openCountryModal(c.cca3 || c.app_country_name)}
                className="group cursor-pointer rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-emerald-400">
                        {c.cca3 || c.cca2}
                      </span>
                      <span className="text-[11px] text-zinc-500">{c.region}</span>
                    </div>
                    <h4 className="font-serif text-lg font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
                      {c.app_country_name}
                    </h4>
                    <p className="text-xs text-zinc-400 break-words">
                      {c.official_name || c.app_country_name}
                    </p>
                  </div>
                  {c.cca2 && (
                    <img
                      src={`https://flagcdn.com/w80/${String(c.cca2).toLowerCase()}.png`}
                      alt={`${c.app_country_name} flag`}
                      loading="lazy"
                      className="h-10 w-15 shrink-0 rounded-xs border border-white/15 object-cover shadow-xs"
                    />
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Capital</span>
                    <span className="text-sand-100 block break-words">{c.capital || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">Population</span>
                    <span className="text-sand-100 block">{c.population ? Number(c.population).toLocaleString('en-US') : 'N/A'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      {/* TAB 3: US States Grid */}
      {activeTab === 'us_states' && (
        <section className="space-y-4">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
            <span>Showing {filteredUSStates.length} states</span>
            <span>Click any card for state facts & borders</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredUSStates.map((s) => (
              <div
                key={s.id}
                onClick={() => openStateModal(s.name)}
                className="group cursor-pointer rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-emerald-400">
                      #{s.admission_order} admitted ({s.admission_year})
                    </span>
                    <span className="text-[11px] text-zinc-500">{s.region}</span>
                  </div>
                  <h4 className="font-serif text-lg font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
                    {s.name}
                  </h4>
                  <p className="text-xs text-zinc-400 italic break-words">
                    {s.nickname || 'The State of ' + s.name}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Division</span>
                    <span className="text-sand-100 block break-words">{s.division || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">Population</span>
                    <span className="text-sand-100 block">{s.population ? Number(s.population).toLocaleString('en-US') : 'N/A'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB 4: Voivodeships Grid */}
      {activeTab === 'voivodeships' && (
        <section className="space-y-4">
          <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
            <span>Showing {filteredVoivodeships.length} voivodeships</span>
            <span>Click any card for regional stats</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredVoivodeships.map((v) => (
              <div
                key={v.id}
                onClick={() => openVoivodeshipModal(v.name)}
                className="group cursor-pointer rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-emerald-400">
                      TERYT {v.teryt}
                    </span>
                    <span className="text-[11px] text-zinc-500">{regionalDisplay[v.macroregion] ?? v.macroregion}</span>
                  </div>
                  <h4 className="font-serif text-lg font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
                    {v.name}
                  </h4>
                  <p className="text-xs text-zinc-400">
                    Administrative seat: <strong className="text-sand-100">{v.seat}</strong>
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Counties</span>
                    <span className="text-sand-100 block">{v.powiat_count}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">Urbanization</span>
                    <span className="text-sand-100 block">{v.urbanization_percent}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Modal: Country Details */}
      {selectedCountry && (
        <div 
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedCountry(null)}
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-black/80 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-sand-100 shadow-2xl md:max-h-[90vh] md:p-8"
          >
            <button 
              type="button" 
              onClick={() => setSelectedCountry(null)}
              aria-label={'Close country details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-zinc-400 hover:text-white"
            >
              <X size={20} />
            </button>

            <header className="border-b border-white/10 pb-4">
              <span className="font-mono text-xs uppercase tracking-widest text-emerald-400">
                {selectedCountry.cca3} &bull; {selectedCountry.region}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-sand-100">
                {selectedCountry.app_country_name}
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Official: {selectedCountry.official_name}
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Capital</span>
                <span className="font-bold text-sand-100">{selectedCountry.capital || 'N/A'}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Population</span>
                <span className="font-bold text-sand-100">{Number(selectedCountry.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Area (km²)</span>
                <span className="font-bold text-sand-100">{Number(selectedCountry.area_km2).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Driving Side</span>
                <span className="font-bold text-sand-100 capitalize">{selectedCountry.driving_side || 'N/A'}</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedCountry.borders && selectedCountry.borders.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Neighboring Borders ({selectedCountry.borders.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.borders.map((b: string) => (
                      <span key={b} className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-zinc-300">
                        {b}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedCountry.water_access && selectedCountry.water_access.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Water & Coastline Access:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.water_access.map((w: string) => (
                      <span key={w} className="px-2 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 rounded">
                        {w}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedCountry.languages && selectedCountry.languages.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Recorded Languages:</span>
                  <span className="text-zinc-400">{selectedCountry.languages.join(', ')}</span>
                </div>
              )}

              {selectedCountry.flag_colors && selectedCountry.flag_colors.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">National Flag Colors:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.flag_colors.map((fc: string) => (
                      <span key={fc} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded capitalize">
                        {fc}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/10 pt-4 flex justify-between items-center">
              <Link 
                to="/game"
                className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors"
              >
                <Play size={13} />
                <span>Play World Countrydle</span>
              </Link>
              <button 
                type="button" 
                onClick={() => setSelectedCountry(null)}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Close Fact Sheet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: State Details */}
      {selectedState && (
        <div 
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedState(null)}
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-black/80 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-sand-100 shadow-2xl md:max-h-[90vh] md:p-8"
          >
            <button 
              type="button" 
              onClick={() => setSelectedState(null)}
              aria-label={'Close state details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-zinc-400 hover:text-white"
            >
              <X size={20} />
            </button>

            <header className="border-b border-white/10 pb-4">
              <span className="font-mono text-xs uppercase tracking-widest text-emerald-400">
                #{selectedState.admission_order} Admitted &bull; {selectedState.region}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-sand-100">
                {selectedState.name}
              </h2>
              <p className="text-xs text-zinc-400 mt-1 italic">
                {selectedState.nickname}
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Division</span>
                <span className="font-bold text-sand-100">{selectedState.division || 'N/A'}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Population</span>
                <span className="font-bold text-sand-100">{Number(selectedState.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Area (sq mi)</span>
                <span className="font-bold text-sand-100">{Number(selectedState.area_sq_mi).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Admission Year</span>
                <span className="font-bold text-sand-100">{selectedState.admission_year}</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedState.neighboring_states && selectedState.neighboring_states.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Neighboring US States ({selectedState.neighboring_states.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedState.neighboring_states.map((st: string) => (
                      <span key={st} className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-zinc-300">
                        {st}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedState.water_access && selectedState.water_access.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Water Bodies & Ocean Access:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedState.water_access.map((w: string) => (
                      <span key={w} className="px-2 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 rounded">
                        {w}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/10 pt-4 flex justify-between items-center">
              <Link 
                to="/us-states"
                className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors"
              >
                <Play size={13} />
                <span>Play US Statedle</span>
              </Link>
              <button 
                type="button" 
                onClick={() => setSelectedState(null)}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Close Fact Sheet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Voivodeship Details */}
      {selectedVoivodeship && (
        <div 
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedVoivodeship(null)}
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-black/80 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-sand-100 shadow-2xl md:max-h-[90vh] md:p-8"
          >
            <button 
              type="button" 
              onClick={() => setSelectedVoivodeship(null)}
              aria-label={'Close voivodeship details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-zinc-400 hover:text-white"
            >
              <X size={20} />
            </button>

            <header className="border-b border-white/10 pb-4">
              <span className="font-mono text-xs uppercase tracking-widest text-emerald-400">
                TERYT {selectedVoivodeship.teryt} &bull; Macroregion {regionalDisplay[selectedVoivodeship.macroregion] ?? selectedVoivodeship.macroregion}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-sand-100">
                {selectedVoivodeship.name} Voivodeship
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Administrative seat: <strong className="text-sand-100">{selectedVoivodeship.seat}</strong>
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Population</span>
                <span className="font-bold text-sand-100">{Number(selectedVoivodeship.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Area</span>
                <span className="font-bold text-sand-100">{Number(selectedVoivodeship.area_km2).toLocaleString('en-US')} km²</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Counties</span>
                <span className="font-bold text-sand-100">{selectedVoivodeship.powiat_count}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Urbanization</span>
                <span className="font-bold text-sand-100">{selectedVoivodeship.urbanization_percent}%</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedVoivodeship.neighboring_voivodeships && selectedVoivodeship.neighboring_voivodeships.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Neighboring voivodeships ({selectedVoivodeship.neighboring_voivodeships.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVoivodeship.neighboring_voivodeships.map((v: string) => (
                      <span key={v} className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-zinc-300">
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedVoivodeship.neighboring_countries && selectedVoivodeship.neighboring_countries.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Bordering countries:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVoivodeship.neighboring_countries.map((c: string) => (
                      <span key={c} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded">
                        {regionalDisplay[c] ?? c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/10 pt-4 flex justify-between items-center">
              <Link 
                to="/wojewodztwa"
                className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors"
              >
                <Play size={13} />
                <span>Play Województwodle</span>
              </Link>
              <button 
                type="button" 
                onClick={() => setSelectedVoivodeship(null)}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Close fact sheet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Polish County (Powiat) & Coat of Arms Details */}
      {selectedPowiat && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedPowiat(null)}
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-black/80 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-3xl max-h-full overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-4 pt-12 sm:p-7 sm:pt-12 space-y-6 text-sand-100 shadow-2xl md:max-h-[90vh]"
          >
            <button
              type="button"
              onClick={() => setSelectedPowiat(null)}
              aria-label={'Close county details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-zinc-400 hover:text-white cursor-pointer"
            >
              <X size={20} />
            </button>

            <header className="flex flex-col sm:flex-row items-center sm:items-start gap-5 border-b border-white/10 pb-5">
              {/* Coat of Arms Pedestal with Fullscreen Trigger */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => {
                  setInspectZoom(1);
                  setInspectedAsset({
                    url: resolvePowiatCoatUrl(selectedPowiat.id),
                    title: selectedPowiat.name,
                    subtitle: `Voivodeship ${selectedPowiat.voivodeship}`,
                  });
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setInspectZoom(1);
                    setInspectedAsset({
                      url: resolvePowiatCoatUrl(selectedPowiat.id),
                      title: selectedPowiat.name,
                      subtitle: `Voivodeship ${selectedPowiat.voivodeship}`,
                    });
                  }
                }}
                aria-label={'Inspect county coat of arms'}
                className={`group relative h-32 w-28 shrink-0 rounded-lg border p-3 flex items-center justify-center cursor-zoom-in transition-all ${
                  lightCoatsBackdrop
                    ? 'bg-sand-100 border-sand-300 shadow-md'
                    : 'bg-obsidian-950 border-white/15 hover:border-emerald-400/50 shadow-inner'
                }`}
              >
                <img
                  src={resolvePowiatCoatUrl(selectedPowiat.id)}
                  alt={`Herb: ${selectedPowiat.name}`}
                  className="max-h-26 max-w-22 w-auto h-auto object-contain select-none drop-shadow-md transition-transform group-hover:scale-105"
                />
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute bottom-1.5 right-1.5 inline-flex h-6 w-6 items-center justify-center rounded bg-obsidian-950/85 border border-white/15 text-zinc-300 group-hover:border-emerald-400/50 group-hover:text-emerald-300"
                >
                  <Maximize2 size={13} />
                </span>
              </div>

              <div className="flex-1 text-center sm:text-left space-y-2">
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                  <span className="font-mono text-xs uppercase tracking-widest text-emerald-400 font-bold">
                    {selectedPowiat.voivodeship} Voivodeship
                  </span>
                  {selectedPowiat.terc && (
                    <span className="rounded bg-white/5 border border-white/10 px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                      TERYT {selectedPowiat.terc}
                    </span>
                  )}
                  <span
                    className={`rounded px-2 py-0.5 font-mono text-[11px] ${
                      selectedPowiat.is_city_county
                        ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                        : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                    }`}
                  >
                    {selectedPowiat.is_city_county ? 'City with county rights' : 'Land county'}
                  </span>
                </div>

                <h2 className="font-serif text-2xl sm:text-3xl font-bold text-sand-100">
                  {selectedPowiat.name}
                </h2>

                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3 pt-1">
                  {selectedPowiat.seat && (
                    <span className="text-xs text-zinc-300">
                      {'County Seat:'}{' '}
                      <strong className="text-sand-100">{selectedPowiat.seat}</strong>
                    </span>
                  )}
                  {selectedPowiat.registration_plates && selectedPowiat.registration_plates.length > 0 && (
                    <div className="inline-flex items-center gap-1.5">
                      <span className="text-xs text-zinc-400 font-mono">
                        {'Plates:'}
                      </span>
                      <MiniLicensePlate plates={selectedPowiat.registration_plates} />
                    </div>
                  )}
                </div>
              </div>
            </header>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-3 bg-white/5 border border-white/5 rounded">
                <span className="text-zinc-500 block">{'Population'}</span>
                <span className="font-bold text-sand-100 text-sm">
                  {selectedPowiat.population ? Number(selectedPowiat.population).toLocaleString('en-US') : '—'}
                </span>
              </div>
              <div className="p-3 bg-white/5 border border-white/5 rounded">
                <span className="text-zinc-500 block">{'Area'}</span>
                <span className="font-bold text-sand-100 text-sm">
                  {selectedPowiat.area_km2 ? `${Number(selectedPowiat.area_km2).toLocaleString('en-US')} km²` : '—'}
                </span>
              </div>
              <div className="p-3 bg-white/5 border border-white/5 rounded">
                <span className="text-zinc-500 block">{'Density'}</span>
                <span className="font-bold text-sand-100 text-sm">
                  {selectedPowiat.population_density
                    ? `${Math.round(Number(selectedPowiat.population_density)).toLocaleString('en-US')} people/km²`
                    : '—'}
                </span>
              </div>
              <div className="p-3 bg-white/5 border border-white/5 rounded">
                <span className="text-zinc-500 block">{'Municipalities'}</span>
                <span className="font-bold text-sand-100 text-sm">
                  {selectedPowiat.gmina_count ?? '—'}
                  {selectedPowiat.urbanization_percent != null
                    ? ` • Urb. ${selectedPowiat.urbanization_percent}%`
                    : ''}
                </span>
              </div>
            </div>

            {/* Relational Geography & Borders */}
            <div className="space-y-4 text-xs">
              {selectedPowiat.neighboring_powiats && selectedPowiat.neighboring_powiats.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {`Neighboring Counties (${selectedPowiat.neighboring_powiats.length}) — click to inspect:`}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_powiats.map((np: string) => (
                      <button
                        key={np}
                        type="button"
                        onClick={() => openPowiatModal(np)}
                        className="px-2.5 py-1 bg-white/5 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/40 rounded text-zinc-200 hover:text-emerald-300 transition-colors cursor-pointer"
                      >
                        {np}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.neighboring_voivodeships && selectedPowiat.neighboring_voivodeships.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'Borders with other Voivodeships:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_voivodeships.map((nv: string) => (
                      <span key={nv} className="px-2 py-0.5 bg-purple-500/10 border border-purple-500/25 text-purple-300 rounded">
                        Voivodeship {nv}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.neighboring_countries && selectedPowiat.neighboring_countries.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'International Border:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_countries.map((nc: string) => (
                      <span key={nc} className="px-2 py-0.5 bg-amber-500/15 border border-amber-500/30 text-amber-300 rounded font-semibold">
                        {regionalDisplay[nc] ?? nc}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {((selectedPowiat.major_rivers && selectedPowiat.major_rivers.length > 0) ||
                (selectedPowiat.water_access && selectedPowiat.water_access.length > 0) ||
                (selectedPowiat.lakes && selectedPowiat.lakes.length > 0)) && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'Rivers, Lakes & Water Bodies:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.water_access || []).map((w: string) => (
                      <span key={`w-${w}`} className="px-2 py-0.5 bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 rounded">
                        {w}
                      </span>
                    ))}
                    {(selectedPowiat.major_rivers || []).map((r: string) => (
                      <span key={`r-${r}`} className="px-2 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 rounded">
                        River {r}
                      </span>
                    ))}
                    {(selectedPowiat.lakes || []).map((l: string) => (
                      <span key={`l-${l}`} className="px-2 py-0.5 bg-sky-500/10 border border-sky-500/20 text-sky-300 rounded">
                        Lake {l}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.major_roads && selectedPowiat.major_roads.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'Major Highways & National Roads:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.major_roads.map((rd: string) => (
                      <span key={rd} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 rounded font-mono">
                        {rd}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {((selectedPowiat.landform_regions && selectedPowiat.landform_regions.length > 0) ||
                (selectedPowiat.historical_regions && selectedPowiat.historical_regions.length > 0)) && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'Geographic & Historical Regions:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.landform_regions || []).map((reg: string) => (
                      <span key={`lf-${reg}`} className="px-2 py-0.5 bg-white/5 border border-white/10 text-zinc-300 rounded">
                        {reg}
                      </span>
                    ))}
                    {(selectedPowiat.historical_regions || []).map((hr: string) => (
                      <span key={`hr-${hr}`} className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-200 rounded">
                        {hr}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {((selectedPowiat.national_parks && selectedPowiat.national_parks.length > 0) ||
                (selectedPowiat.health_resorts && selectedPowiat.health_resorts.length > 0) ||
                (selectedPowiat.unesco_sites && selectedPowiat.unesco_sites.length > 0)) && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">
                    {'National Parks, Health Resorts & UNESCO:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.national_parks || []).map((np: string) => (
                      <span key={`np-${np}`} className="px-2 py-0.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded">
                        {np}
                      </span>
                    ))}
                    {(selectedPowiat.health_resorts || []).map((hr: string) => (
                      <span key={`res-${hr}`} className="px-2 py-0.5 bg-teal-500/15 border border-teal-500/30 text-teal-300 rounded">
                        Health resort: {hr}
                      </span>
                    ))}
                    {(selectedPowiat.unesco_sites || []).map((u: string) => (
                      <span key={`un-${u}`} className="px-2 py-0.5 bg-amber-500/20 border border-amber-500/40 text-amber-200 rounded font-semibold">
                        UNESCO: {u}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/10 pt-4 flex flex-wrap justify-between items-center gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/herby-powiatow"
                  className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors"
                >
                  <Shield size={13} />
                  <span>{'Play County Coats of Arms'}</span>
                </Link>
                <Link
                  to="/powiaty"
                  className="inline-flex items-center gap-2 rounded-sm border border-white/15 bg-white/5 px-4 py-2 text-xs font-semibold text-sand-100 hover:bg-white/10 transition-colors"
                >
                  <Play size={13} />
                  <span>{'Play Powiatdle'}</span>
                </Link>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPowiat(null)}
                className="text-xs text-zinc-400 hover:text-white cursor-pointer"
              >
                {'Close Fact Sheet'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Coat of Arms Inspector Lightbox */}
      {inspectedAsset && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={inspectedAsset.title}
          onClick={() => setInspectedAsset(null)}
          className="fixed inset-0 z-[2200] flex flex-col bg-obsidian-950/95 backdrop-blur-md select-none"
        >
          {/* Top Toolbar */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-obsidian-900/90 px-4 py-3 sm:px-6 shrink-0"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Shield size={16} className="text-emerald-400 shrink-0" />
              <span className="font-serif text-sm font-bold text-sand-100 truncate">
                {inspectedAsset.title}
              </span>
              {inspectedAsset.subtitle && (
                <span className="hidden sm:inline font-mono text-xs text-zinc-400">
                  • {inspectedAsset.subtitle}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                disabled={inspectZoom <= 1}
                className="inline-flex items-center justify-center rounded border border-white/15 bg-obsidian-950 p-1.5 text-zinc-300 hover:text-white hover:border-white/30 disabled:opacity-40 cursor-pointer"
              >
                <ZoomOut size={15} />
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom(1)}
                className="rounded border border-white/15 bg-obsidian-950 px-2 py-1 font-mono text-xs text-sand-200 hover:border-emerald-400/50 cursor-pointer"
              >
                {Math.round(inspectZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                disabled={inspectZoom >= 3}
                className="inline-flex items-center justify-center rounded border border-white/15 bg-obsidian-950 p-1.5 text-zinc-300 hover:text-white hover:border-white/30 disabled:opacity-40 cursor-pointer"
              >
                <ZoomIn size={15} />
              </button>
              <button
                type="button"
                onClick={() => setLightCoatsBackdrop((b) => !b)}
                className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer ${
                  lightCoatsBackdrop
                    ? 'border-amber-400/60 bg-sand-100 text-obsidian-950 font-semibold'
                    : 'border-white/15 bg-obsidian-950 text-zinc-300 hover:text-white'
                }`}
              >
                {lightCoatsBackdrop ? <Sun size={14} /> : <Moon size={14} />}
                <span className="hidden sm:inline">
                  {lightCoatsBackdrop ? ('Light bg') : ('Dark bg')}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setInspectedAsset(null)}
                className="inline-flex items-center gap-1 rounded border border-white/20 bg-white/10 px-2.5 py-1 text-xs font-semibold text-sand-100 hover:bg-rose-500/20 hover:border-rose-400/40 hover:text-rose-200 transition-colors cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Centered Canvas */}
          <div
            onClick={() => setInspectedAsset(null)}
            className="flex-1 overflow-auto flex items-center justify-center p-4 sm:p-8"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className={`relative flex items-center justify-center rounded-2xl border p-6 sm:p-10 shadow-2xl transition-colors duration-200 ${
                lightCoatsBackdrop
                  ? 'border-zinc-300 bg-stone-100 shadow-black/50'
                  : 'border-white/15 bg-obsidian-900/95 shadow-black/80'
              }`}
            >
              <img
                src={inspectedAsset.url}
                alt={inspectedAsset.title}
                style={{
                  height: `${Math.round(68 * inspectZoom)}vh`,
                  maxHeight: `${Math.round(68 * inspectZoom)}vh`,
                  width: 'auto',
                }}
                className="max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-all duration-150"
              />
            </div>
          </div>
        </div>
      )}

      {/* AdSense Unit */}
      {publisherReady && <AdSenseUnit slot="explore-hub-footer" className="max-w-2xl mx-auto pt-6" />}
    </div>
  );
}
