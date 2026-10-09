import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, 
  Globe, 
  Play, 
  ChevronRight, 
  X 
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
