import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, 
  Globe, 
  Play, 
  ChevronRight, 
  X,
  Compass,
  BookOpen
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import AdSenseUnit from '../components/AdSenseUnit';
import { exploreService } from '../services/api';
import { setPageEditorialEligibility } from '../advertising';

type TabType = 'modes' | 'countries' | 'us_states' | 'voivodeships';

type LoadStatus = 'idle' | 'loading' | 'success' | 'error';
const GUIDE_IDS: Record<string, string> = { countrydle: 'countrydle', us_statedle: 'us-states', wojewodztwodle: 'wojewodztwa', powiatdle: 'powiaty', flagdle: 'flagdle', europe: 'europe', asia: 'asia', africa: 'africa', americas: 'americas' };

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
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const [activeTab, updateActiveTab] = useState<TabType>(() => {
    const tab = initialView().get('tab');
    return tab === 'countries' || tab === 'us_states' || tab === 'voivodeships' ? tab : 'modes';
  });
  const [search, updateSearch] = useState(() => initialView().get('q') || '');
  const [selectedRegion, updateSelectedRegion] = useState(() => initialView().get('region') || 'all');
  const setActiveTab = (tab: TabType) => { rememberView('tab', tab === 'modes' ? '' : tab); updateActiveTab(tab); };
  const setSearch = (value: string) => { rememberView('q', value); updateSearch(value); };
  const setSelectedRegion = (value: string) => { rememberView('region', value === 'all' ? '' : value); updateSelectedRegion(value); };

  const [modes, setModes] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [usStates, setUsStates] = useState<any[]>([]);
  const [voivodeships, setVoivodeships] = useState<any[]>([]);
  const [loadStatus, setLoadStatus] = useState<Record<TabType, LoadStatus>>({ modes: 'idle', countries: 'idle', us_states: 'idle', voivodeships: 'idle' });

  // Selected Entity Modal
  const [selectedCountry, updateSelectedCountry] = useState<any | null>(null);
  const [selectedState, updateSelectedState] = useState<any | null>(null);
  const [selectedVoivodeship, updateSelectedVoivodeship] = useState<any | null>(null);
  const setSelectedCountry = (value: typeof selectedCountry) => { if (!value) rememberView('detail', ''); updateSelectedCountry(value); };
  const setSelectedState = (value: typeof selectedState) => { if (!value) rememberView('detail', ''); updateSelectedState(value); };
  const setSelectedVoivodeship = (value: typeof selectedVoivodeship) => { if (!value) rememberView('detail', ''); updateSelectedVoivodeship(value); };
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
    const existingCount = activeTab === 'countries' ? countries.length : activeTab === 'us_states' ? usStates.length : voivodeships.length;
    if (existingCount > 0) return;
    let cancelled = false;
    const tab = activeTab;
    setLoadStatus(prev => ({ ...prev, [tab]: 'loading' }));
    const request = tab === 'countries' ? exploreService.getCountries({ limit: 250 }) : tab === 'us_states' ? exploreService.getUSStates() : exploreService.getVoivodeships();
    request.then(data => {
      if (!Array.isArray(data) || data.some(item => !item || typeof (tab === 'countries' ? item.app_country_name : item.name) !== 'string')) throw new Error('Invalid fact response');
      if (cancelled) return;
      if (tab === 'countries') setCountries(data);
      else if (tab === 'us_states') setUsStates(data);
      else setVoivodeships(data);
      setLoadStatus(prev => ({ ...prev, [tab]: 'success' }));
    }).catch(() => {
      if (!cancelled) setLoadStatus(prev => ({ ...prev, [tab]: 'error' }));
    });
    return () => { cancelled = true; };
  }, [activeTab, countries.length, usStates.length, voivodeships.length]);

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

  useEffect(() => {
    const detail = initialView().get('detail');
    if (!detail) return;
    const separator = detail.indexOf(':');
    const kind = detail.slice(0, separator);
    const identifier = detail.slice(separator + 1);
    if (!identifier || !['country', 'state', 'voivodeship'].includes(kind)) {
      setModalError('This fact sheet address is not recognized. Close it to return to the explorer.');
      return;
    }
    let cancelled = false;
    setModalLoading(true);
    const request = kind === 'country' ? exploreService.getCountryDetail(identifier) : kind === 'state' ? exploreService.getUSStateDetail(identifier) : exploreService.getVoivodeshipDetail(identifier);
    request.then(data => {
      if (!data || typeof data !== 'object') throw new Error('Invalid fact sheet');
      if (cancelled) return;
      if (kind === 'country') updateSelectedCountry(data);
      else if (kind === 'state') updateSelectedState(data);
      else updateSelectedVoivodeship(data);
    }).catch(() => {
      if (!cancelled) setModalError('The requested fact sheet could not be loaded. Close it and try again.');
    }).finally(() => {
      if (!cancelled) setModalLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

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

  const regions = useMemo(() => {
    if (activeTab === 'countries') {
      return ['all', 'Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];
    }
    if (activeTab === 'us_states') {
      return ['all', 'Northeast', 'Midwest', 'South', 'West'];
    }
    return ['all'];
  }, [activeTab]);

  const status = loadStatus[activeTab];
  const loading = status === 'idle' || status === 'loading';
  const visibleCount = activeTab === 'modes' ? modes.length : activeTab === 'countries' ? filteredCountries.length : activeTab === 'us_states' ? filteredUSStates.length : filteredVoivodeships.length;
  const detailOpen = modalLoading || Boolean(modalError || selectedCountry || selectedState || selectedVoivodeship || initialView().get('detail'));
  const publisherReady = status === 'success' && visibleCount > 0 && !detailOpen;
  const publisherError = status === 'error' || Boolean(modalError) || (status === 'success' && visibleCount === 0);

  useEffect(() => {
    setPageEditorialEligibility(publisherReady);
  }, [publisherReady]);

  useEffect(() => () => setPageEditorialEligibility(false), []);

  return (
    <div data-publisher-ready={publisherReady ? 'true' : undefined} data-publisher-error={publisherError ? 'true' : undefined} className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6 md:py-12">
      {/* Header */}
      <header className="border-b border-white/10 pb-8 text-center sm:text-left">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 font-mono text-xs uppercase tracking-widest text-emerald-400">
          <Globe size={13} />
          <span>{isPl ? 'Baza wiedzy geograficznej' : 'Geographic Knowledge Base & Guides'}</span>
        </div>
        <h1 className="font-serif text-3xl font-bold tracking-tight text-sand-100 sm:text-5xl">
          {isPl ? 'Przewodnik i eksplorator Countrydle' : 'Geography Explorer & Mode Guides'}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-300">
          {isPl
            ? 'Przeglądaj aktualną bazę faktów o krajach, stanach USA i województwach Polski. Poznaj zasady i przykłady dedukcji; dane i interpretacje mogą być niepełne lub nieaktualne.'
            : 'Explore the current knowledge base for countries, US states and Polish voivodeships. Read game-specific conventions and worked deduction examples; stored facts and interpretations may be incomplete or outdated.'}
        </p>

        {/* Tab Switcher */}
        <div className="mt-8 flex flex-wrap gap-2 border-b border-white/10 pb-4">
          <button
            type="button"
            onClick={() => { setActiveTab('modes'); setSearch(''); }}
            className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === 'modes'
                ? 'bg-emerald-400 text-obsidian-950 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {isPl ? 'Przewodniki po trybach' : 'Mode Guides'}
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('countries'); setSearch(''); setSelectedRegion('all'); }}
            className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === 'countries'
                ? 'bg-emerald-400 text-obsidian-950 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {isPl ? 'Państwa świata (195)' : 'World Countries (195)'}
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('us_states'); setSearch(''); setSelectedRegion('all'); }}
            className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === 'us_states'
                ? 'bg-emerald-400 text-obsidian-950 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {isPl ? 'Stany USA (50)' : 'US States (50)'}
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('voivodeships'); setSearch(''); setSelectedRegion('all'); }}
            className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === 'voivodeships'
                ? 'bg-emerald-400 text-obsidian-950 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {isPl ? 'Województwa (16)' : 'Voivodeships (16)'}
          </button>
        </div>
      </header>

      {loading && <p role="status" className="text-base leading-7 text-zinc-400">Loading {activeTab === 'modes' ? 'mode guides' : 'geography facts'}…</p>}
      {status === 'error' && <p role="alert" className="text-base leading-7 text-amber-300">This content could not be loaded. Reload the page to try again; no substitute data is shown.</p>}
      {status === 'success' && visibleCount === 0 && <p role="status" className="text-base leading-7 text-zinc-400">No entries match this view. Clear the search or choose another region; an empty response is not evidence that a place is absent from the game.</p>}
      {modalLoading && <p role="status" className="text-base leading-7 text-zinc-400">Loading fact sheet…</p>}
      {modalError && <div role="alert" className="space-y-3 text-amber-300"><p>{modalError}</p><button type="button" onClick={() => { rememberView('detail', ''); setModalError(''); }} className="underline underline-offset-4">Close fact sheet error</button></div>}

      {/* TAB 1: Mode Guides */}
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
                    <span>{isPl ? 'Czytaj przewodnik i strategię' : 'Read Strategy Guide'}</span>
                    <ChevronRight size={14} />
                  </Link>
                  <Link
                    to={mode.path}
                    className="inline-flex items-center gap-1.5 rounded-sm bg-white/10 px-3 py-1.5 text-xs font-medium text-sand-100 hover:bg-emerald-400 hover:text-obsidian-950 transition-colors"
                  >
                    <Play size={12} />
                    <span>{isPl ? 'Graj teraz' : 'Play Mode'}</span>
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
                <span>{isPl ? 'Porównanie reguł gry' : 'Daily Game Mechanics'}</span>
              </div>
              <h2 id="modes-comparative-overview" className="font-serif text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">
                {isPl ? 'Sekcja A — Zestawienie porównawcze 9 codziennych trybów geograficznych' : 'Section A — Comparative Overview of All 9 Daily Geography Modes'}
              </h2>
              <p className="max-w-4xl text-sm leading-relaxed text-zinc-300 md:text-base">
                {isPl
                  ? 'Countrydle oferuje 9 wyspecjalizowanych wyzwań geograficznych o zróżnicowanej skali przestrzennej — od globalnej dedukcji 195 suwerennych państw, poprzez kontynentalne podzbiory i heraldykę flagową, aż po jednostki subnarodowe: 50 stanów USA, 16 polskich województw oraz 380 powiatów. Poniższa tabela porządkuje wielkości puli, limity pytań i prób oraz nadrzędne osie dedukcyjne obowiązujące w każdym trybie.'
                  : 'Countrydle offers 9 specialized daily deductive challenges spanning diverse spatial scales — from global sovereign states down to subnational counties and flags. Each mode balances a tailored question budget against a strict guess limit, rewarding systematic elimination over unstructured guessing. The comparative reference table below summarizes pool dimensions, question constraints, guess allowances, primary geographic axes, and direct links to comprehensive strategy guides.'}
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
                <span>{isPl ? 'Zasady dedukcji i taksonomii' : 'Geographic Methodology & Theory'}</span>
              </div>
              <h2 id="modes-deductive-taxonomies" className="font-serif text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">
                {isPl ? 'Sekcja B — Podstawowe taksonomie geograficzne i zasady dedukcji' : 'Section B — Core Geographic Taxonomies & Deductive Principles'}
              </h2>
              <p className="max-w-4xl text-sm leading-relaxed text-zinc-300 md:text-base">
                {isPl
                  ? 'Skuteczna dedukcja w Countrydle nie opiera się na przypadkowych strzałach, lecz na rygorystycznym podziale zbioru kandydatów przy pomocy jednoznacznych właściwości przestrzennych. Zrozumienie współrzędnych sferycznych, hydrografii morskiej i śródlądowej oraz wielopoziomowych hierarchii administracyjnych pozwala optymalnie wykorzystać skromny budżet pytań.'
                  : 'Mastering Countrydle requires treating the globe as an interconnected mathematical coordinate system and political-geographic hierarchy. Rather than expending precious questions on subjective traits ("Is it a major power?"), experienced players query well-defined taxonomic boundaries. The educational guides below elucidate three fundamental geographical principles that underpin Countrydle’s deductive engine.'}
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

      {/* TAB 2, 3, 4: Search & Filters Toolbar */}
      {activeTab !== 'modes' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:max-w-md">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={isPl ? 'Szukaj po nazwie, stolicy lub kodzie...' : 'Search by name, capital, or code...'}
                className="w-full rounded-sm border border-white/15 bg-obsidian-900 py-2.5 pl-10 pr-4 text-sm text-sand-100 placeholder-zinc-500 focus:border-emerald-400 focus:outline-none"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {regions.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
                <span className="text-xs text-zinc-500 mr-1 font-mono uppercase">Region:</span>
                {regions.map((reg) => (
                  <button
                    key={reg}
                    type="button"
                    onClick={() => setSelectedRegion(reg)}
                    className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors ${
                      selectedRegion === reg
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
                    }`}
                  >
                    {reg}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
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
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
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

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Capital</span>
                    <span className="text-sand-100 block break-words">{c.capital || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">Population</span>
                    <span className="text-sand-100 block">{c.population ? Number(c.population).toLocaleString() : 'N/A'}</span>
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
                    <span className="text-sand-100 block">{s.population ? Number(s.population).toLocaleString() : 'N/A'}</span>
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
                    <span className="text-[11px] text-zinc-500">{v.macroregion}</span>
                  </div>
                  <h4 className="font-serif text-lg font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
                    {v.name}
                  </h4>
                  <p className="text-xs text-zinc-400">
                    Siedziba: <strong className="text-sand-100">{v.seat}</strong>
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Powiaty</span>
                    <span className="text-sand-100 block">{v.powiat_count}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">Urbanizacja</span>
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
              aria-label={isPl ? 'Zamknij szczegóły kraju' : 'Close country details'}
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
                <span className="font-bold text-sand-100">{Number(selectedCountry.population).toLocaleString()}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Area (km²)</span>
                <span className="font-bold text-sand-100">{Number(selectedCountry.area_km2).toLocaleString()}</span>
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
              aria-label={isPl ? 'Zamknij szczegóły stanu' : 'Close state details'}
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
                <span className="font-bold text-sand-100">{Number(selectedState.population).toLocaleString()}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Area (sq mi)</span>
                <span className="font-bold text-sand-100">{Number(selectedState.area_sq_mi).toLocaleString()}</span>
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
              aria-label={isPl ? 'Zamknij szczegóły województwa' : 'Close voivodeship details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-zinc-400 hover:text-white"
            >
              <X size={20} />
            </button>

            <header className="border-b border-white/10 pb-4">
              <span className="font-mono text-xs uppercase tracking-widest text-emerald-400">
                TERYT {selectedVoivodeship.teryt} &bull; Makroregion {selectedVoivodeship.macroregion}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-sand-100">
                Województwo {selectedVoivodeship.name}
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Siedziba władz: <strong className="text-sand-100">{selectedVoivodeship.seat}</strong>
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Liczba ludności</span>
                <span className="font-bold text-sand-100">{Number(selectedVoivodeship.population).toLocaleString()}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Powierzchnia</span>
                <span className="font-bold text-sand-100">{Number(selectedVoivodeship.area_km2).toLocaleString()} km²</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Liczba powiatów</span>
                <span className="font-bold text-sand-100">{selectedVoivodeship.powiat_count}</span>
              </div>
              <div className="p-3 bg-white/5 rounded">
                <span className="text-zinc-500 block">Urbanizacja</span>
                <span className="font-bold text-sand-100">{selectedVoivodeship.urbanization_percent}%</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedVoivodeship.neighboring_voivodeships && selectedVoivodeship.neighboring_voivodeships.length > 0 && (
                <div>
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Sąsiadujące województwa ({selectedVoivodeship.neighboring_voivodeships.length}):</span>
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
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Granica z państwami:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVoivodeship.neighboring_countries.map((c: string) => (
                      <span key={c} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded">
                        {c}
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
                <span>Zagraj w Województwodle</span>
              </Link>
              <button 
                type="button" 
                onClick={() => setSelectedVoivodeship(null)}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Zamknij kartę
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AdSense Unit */}
      {publisherReady && <AdSenseUnit slot="explore-hub-footer" className="max-w-2xl mx-auto pt-6" />}
    </div>
  );
}
