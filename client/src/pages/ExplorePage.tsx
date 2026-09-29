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

type TabType = 'modes' | 'countries' | 'us_states' | 'voivodeships';

export default function ExplorePage() {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const [activeTab, setActiveTab] = useState<TabType>('modes');
  const [search, setSearch] = useState('');
  const [selectedRegion, setSelectedRegion] = useState<string>('all');

  const [modes, setModes] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [usStates, setUsStates] = useState<any[]>([]);
  const [voivodeships, setVoivodeships] = useState<any[]>([]);
  const [, setLoading] = useState(false);

  // Selected Entity Modal
  const [selectedCountry, setSelectedCountry] = useState<any | null>(null);
  const [selectedState, setSelectedState] = useState<any | null>(null);
  const [selectedVoivodeship, setSelectedVoivodeship] = useState<any | null>(null);
  const [, setModalLoading] = useState(false);

  // Fetch Modes on mount
  useEffect(() => {
    exploreService.getModes().then(setModes).catch(console.error);
  }, []);

  // Fetch tab data when activeTab changes
  useEffect(() => {
    if (activeTab === 'countries' && countries.length === 0) {
      setLoading(true);
      exploreService.getCountries({ limit: 250 })
        .then(setCountries)
        .catch(console.error)
        .finally(() => setLoading(false));
    } else if (activeTab === 'us_states' && usStates.length === 0) {
      setLoading(true);
      exploreService.getUSStates()
        .then(setUsStates)
        .catch(console.error)
        .finally(() => setLoading(false));
    } else if (activeTab === 'voivodeships' && voivodeships.length === 0) {
      setLoading(true);
      exploreService.getVoivodeships()
        .then(setVoivodeships)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [activeTab, countries.length, usStates.length, voivodeships.length]);

  // Load detailed entity for modal
  const openCountryModal = async (cca3: string) => {
    setModalLoading(true);
    try {
      const data = await exploreService.getCountryDetail(cca3);
      setSelectedCountry(data);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  };

  const openStateModal = async (name: string) => {
    setModalLoading(true);
    try {
      const data = await exploreService.getUSStateDetail(name);
      setSelectedState(data);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  };

  const openVoivodeshipModal = async (name: string) => {
    setModalLoading(true);
    try {
      const data = await exploreService.getVoivodeshipDetail(name);
      setSelectedVoivodeship(data);
    } catch (err) {
      console.error(err);
    } finally {
      setModalLoading(false);
    }
  };

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

  return (
    <div className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6 md:py-12">
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
            ? 'Przeglądaj zweryfikowane fakty o 195 państwach świata, 50 stanach USA i 16 województwach Polski. Poznaj strategie dedukcji, granice, rzeki i flagi wykorzystywane w grze.'
            : 'Explore verified geographic facts across 195 sovereign nations, 50 US states, and 16 Polish voivodeships. Master deduction strategies, borders, rivers, and symbols used across all daily challenges.'}
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
            {isPl ? 'Przewodniki po trybach (4)' : 'Mode Guides (4)'}
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

      {/* TAB 1: Mode Guides */}
      {activeTab === 'modes' && (
        <section className="space-y-6">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {(modes.length > 0 ? modes : [
              { id: 'countrydle', name: 'Countrydle (World Countries)', path: '/game', entity_count: 195, question_limit: 10, guess_limit: 3, description: 'Deduce one of 195 sovereign nations across all seven continents using natural-language questions.' },
              { id: 'us_statedle', name: 'US Statedle (50 States)', path: '/us-states', entity_count: 50, question_limit: 8, guess_limit: 3, description: 'Identify the mystery American state using geographic regions, coastline access, and admission order.' },
              { id: 'wojewodztwodle', name: 'Województwodle (16 Voivodeships)', path: '/wojewodztwa', entity_count: 16, question_limit: 5, guess_limit: 2, description: 'Master Poland\'s 16 administrative regions through spatial bounds, Baltic access, and borders.' },
              { id: 'powiatdle', name: 'Powiatdle (380 Counties)', path: '/powiaty', entity_count: 380, question_limit: 15, guess_limit: 3, description: 'The ultimate test of Polish local geography tested via vehicle registration plates, rivers, and roads.' },
            ]).map((mode) => (
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
                    {mode.description}
                  </p>
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
                  <Link
                    to={`/explore/modes/${mode.id === 'us_statedle' ? 'us-states' : mode.id}`}
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
                  <p className="text-xs text-zinc-400 truncate">
                    {c.official_name || c.app_country_name}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Capital</span>
                    <span className="text-sand-100 truncate block">{c.capital || 'N/A'}</span>
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
                  <p className="text-xs text-zinc-400 italic truncate">
                    {s.nickname || 'The State of ' + s.name}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-2 text-[11px] text-zinc-400 font-mono">
                  <div>
                    <span className="text-zinc-600 block">Division</span>
                    <span className="text-sand-100 truncate block">{s.division || 'N/A'}</span>
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
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-6 sm:p-8 space-y-6 text-sand-100 shadow-2xl"
          >
            <button 
              type="button" 
              onClick={() => setSelectedCountry(null)}
              className="absolute right-4 top-4 text-zinc-400 hover:text-white"
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
                <span className="font-bold text-sand-100 capitalize">{selectedCountry.driving_side || 'Right'}</span>
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
                  <span className="font-bold text-zinc-300 block mb-1.5 uppercase font-mono">Languages Spoken:</span>
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
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-6 sm:p-8 space-y-6 text-sand-100 shadow-2xl"
          >
            <button 
              type="button" 
              onClick={() => setSelectedState(null)}
              className="absolute right-4 top-4 text-zinc-400 hover:text-white"
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
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg border border-white/15 bg-obsidian-900 p-6 sm:p-8 space-y-6 text-sand-100 shadow-2xl"
          >
            <button 
              type="button" 
              onClick={() => setSelectedVoivodeship(null)}
              className="absolute right-4 top-4 text-zinc-400 hover:text-white"
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
      <AdSenseUnit slot="explore-hub-footer" className="max-w-2xl mx-auto pt-6" />
    </div>
  );
}
