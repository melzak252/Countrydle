import { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Search, 
  Globe, 
  Play, 
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
  Flag,
} from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';
import ExploreGameArtwork from '../components/ExploreGameArtwork';
import { exploreService } from '../services/api';
import { setPageEditorialEligibility } from '../advertising';
import { gameCatalog as baseGameCatalog, useGameCatalog, type CatalogGeography } from '../lib/gameCatalog';
import { MAP_QUIZ_PATHS } from '../lib/mapGameMode';

type TabType = 'index' | 'powiats' | 'voivodeships' | 'countries' | 'us_states';
type FactTabType = Exclude<TabType, 'index'>;
type CountyTypeFilter = 'all' | 'land' | 'city';
type GameModeGroupId = (typeof baseGameCatalog)[number]['id'];
type ExploreGroupId = GameModeGroupId | 'typed-chain';
type CatalogMode = (typeof baseGameCatalog)[number]['games'][number];
type ExploreCatalogGroup = { id: ExploreGroupId; title: string; games: CatalogMode[] };

type LoadStatus = 'idle' | 'loading' | 'success' | 'error';
const geographyLabels: Record<CatalogGeography, string> = {
  worldwide: 'Worldwide',
  continents: 'Continents',
  poland: 'Poland',
  'united-states': 'United States',
  uk: 'England and London',
};
const gameGroupNotes: Record<ExploreGroupId, string> = {
  'true-false': 'Ask yes-or-no questions to identify a country or region.',
  daily: 'Identify a flag or regional symbol from visual clues.',
  quizzes: 'Answer a quiz about flags, heraldry, and regional symbols.',
  more: 'Invite a friend to a geography duel.',
  'map-quizzes': 'Click the current Powiat or State target on its map.',
  'typed-chain': 'Type neighboring places to continue a border chain.',
};
const gameGroupMarkers = {
  'true-false': { label: 'Countrydle', icon: Search },
  daily: { label: 'Visual puzzle', icon: Flag },
  quizzes: { label: 'Visual quiz', icon: BookOpen },
  more: { label: 'Play with friends', icon: Globe },
  'map-quizzes': { label: 'Click the map', icon: MapPin },
  'typed-chain': { label: 'Follow borders', icon: Compass },
} as const;
const gameIndexFacts: Record<string, { scope: string; rules?: string }> = {
  '/game': { scope: 'Worldwide · 195 playable countries', rules: '10 yes/no questions · 3 guesses' },
  '/europe': { scope: 'Europe · 44 countries', rules: '8 yes/no questions · 3 guesses' },
  '/asia': { scope: 'Asia · 48 countries', rules: '8 yes/no questions · 3 guesses' },
  '/africa': { scope: 'Africa · 54 nations', rules: '8 yes/no questions · 3 guesses' },
  '/americas': { scope: 'The Americas · 35 nations', rules: '8 yes/no questions · 3 guesses' },
  '/us-states': { scope: 'United States · 50 states', rules: '8 yes/no questions · 3 guesses' },
  '/wojewodztwa': { scope: 'Poland · 16 voivodeships', rules: '5 questions · 2 guesses' },
  '/powiaty': { scope: 'Poland · 380 counties', rules: '15 questions · 3 guesses' },
  '/flagdle': { scope: 'Worldwide · 195 national flags', rules: '12 tile guesses · unlimited helper questions' },
  '/flag-shades': { scope: 'Worldwide · flag colors' },
  '/herby-powiatow': { scope: 'Poland · 380 county coats of arms' },
  '/flagi-powiatow': { scope: 'Poland · county flags' },
  '/quiz-herbow': { scope: 'Poland · county coats of arms' },
  '/quiz-flag-powiatow': { scope: 'Poland · county flags' },
  '/border-hop': { scope: 'Worldwide · country-border routes' },
  '/border-hop?mode=powiaty': { scope: 'Poland · 380 counties', rules: 'Type a neighboring county to extend the chain' },
  [MAP_QUIZ_PATHS.powiaty]: { scope: 'Poland · 380 counties', rules: 'Daily · 10 Powiats · click the current target' },
  [MAP_QUIZ_PATHS.us_states]: { scope: 'United States · 50 states', rules: 'Repeatable · 10 States per run · click the current target' },
  '/map-border-hop?mode=powiaty': { scope: 'Poland · 380 counties', rules: 'Type a neighboring county to extend the chain' },
  '/map-border-hop?mode=us_states': { scope: 'United States · 50 states', rules: 'Type a neighboring state to extend the chain' },
  '/friends': { scope: 'Worldwide · friend duels' },
};
const confirmedMapGameGroups: ExploreCatalogGroup[] = [
  {
    id: 'typed-chain',
    title: 'Follow borders',
    games: [
      { path: '/border-hop', name: 'Border Hop · Countries', geography: 'worldwide' },
      { path: '/border-hop?mode=powiaty', name: 'Border Hop · Powiaty', geography: 'poland' },
      { path: '/map-border-hop?mode=powiaty', name: 'Map Border Hop · Powiaty', geography: 'poland' },
      { path: '/map-border-hop?mode=us_states', name: 'Map Border Hop · US States', geography: 'united-states' },
    ],
  },
];
const relocatedMapRoutes = new Set(confirmedMapGameGroups.flatMap((group) => group.games.map((game) => game.path)));
function gameRegionLabel(game: CatalogMode): string {
  const scope = gameIndexFacts[game.path]?.scope;
  return scope ? scope.split('·')[0].trim() : geographyLabels[game.geography];
}
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
  const gameCatalog = useGameCatalog();

  const [activeTab, updateActiveTab] = useState<TabType>(() => {
    const tab = initialView().get('tab');
    return tab === 'powiats' || tab === 'countries' || tab === 'us_states' || tab === 'voivodeships' ? tab : 'index';
  });
  const [search, updateSearch] = useState(() => initialView().get('q') || '');
  const [selectedRegion, updateSelectedRegion] = useState(() => initialView().get('region') || 'all');
  const [countyTypeFilter, setCountyTypeFilter] = useState<CountyTypeFilter>('all');
  const [powiatPage, setPowiatPage] = useState<number>(1);
  const [lightCoatsBackdrop, setLightCoatsBackdrop] = useState<boolean>(false);

  const setActiveTab = (tab: TabType) => { rememberView('tab', tab === 'index' ? '' : tab); updateActiveTab(tab); setPowiatPage(1); };
  const setSearch = (value: string) => { rememberView('q', value); updateSearch(value); setPowiatPage(1); };
  const setSelectedRegion = (value: string) => { rememberView('region', value === 'all' ? '' : value); updateSelectedRegion(value); setPowiatPage(1); };

  const [countries, setCountries] = useState<any[]>([]);
  const [usStates, setUsStates] = useState<any[]>([]);
  const [voivodeships, setVoivodeships] = useState<any[]>([]);
  const [powiats, setPowiats] = useState<any[]>([]);
  const [loadStatus, setLoadStatus] = useState<Record<FactTabType, LoadStatus>>({
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
  const inspectorRef = useRef<HTMLDivElement>(null);
  const inspectorOpenerRef = useRef<HTMLElement | null>(null);

  const setSelectedCountry = (value: typeof selectedCountry) => { if (!value) rememberView('detail', ''); updateSelectedCountry(value); };
  const setSelectedState = (value: typeof selectedState) => { if (!value) rememberView('detail', ''); updateSelectedState(value); };
  const setSelectedVoivodeship = (value: typeof selectedVoivodeship) => { if (!value) rememberView('detail', ''); updateSelectedVoivodeship(value); };
  const setSelectedPowiat = (value: typeof selectedPowiat) => { if (!value) rememberView('detail', ''); updateSelectedPowiat(value); };
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState('');

  useEffect(() => {
    if (activeTab === 'index') return;
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
    const dialog = inspectorRef.current;
    const opener = inspectorOpenerRef.current;
    const bodyOverflow = document.body.style.overflow;
    const rootOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), [href], [tabindex]:not([tabindex="-1"])') || [])
      .filter((element) => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        setInspectedAsset(null);
      } else if (e.key === 'Tab') {
        const items = focusable();
        if (!items.length) {
          e.preventDefault();
          return;
        }
        const index = items.indexOf(document.activeElement as HTMLElement);
        if (index === -1 || (e.shiftKey && index === 0) || (!e.shiftKey && index === items.length - 1)) {
          e.preventDefault();
          items[e.shiftKey ? items.length - 1 : 0].focus();
        }
      }
    };
    const onFocusIn = (e: FocusEvent) => {
      if (dialog && !dialog.contains(e.target as Node)) focusable()[0]?.focus();
    };
    window.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('focusin', onFocusIn);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('focusin', onFocusIn);
      document.body.style.overflow = bodyOverflow;
      document.documentElement.style.overflow = rootOverflow;
      opener?.focus();
    };
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

  const status: LoadStatus = activeTab === 'index' ? 'success' : loadStatus[activeTab];
  const loading = activeTab !== 'index' && (status === 'idle' || status === 'loading');
  const visibleCount =
    activeTab === 'index'
      ? 0
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
  const publisherReady = status === 'success' && !detailOpen && (
    activeTab === 'index' ? gameCatalog.some((group) => group.games.length > 0) : visibleCount > 0
  );
  const publisherError = status === 'error' || Boolean(modalError) || (
    activeTab !== 'index' && status === 'success' && visibleCount === 0
  );
  const resolvePowiatCoatUrl = (powiatId: number) => `/api/explore/powiats/${powiatId}/coat?v=2`;
  const resolvePowiatCoatThumbUrl = (powiatId: number) => `/coats/${powiatId}.png`;
  const baseGameGroups: ExploreCatalogGroup[] = gameCatalog
    .map((group) => ({ ...group, games: group.games.filter((game) => !relocatedMapRoutes.has(game.path)) }))
    .filter((group) => group.games.length > 0);
  const exploreGameGroups = [
    ...baseGameGroups.filter((group) => group.id === 'true-false'),
    ...confirmedMapGameGroups,
    ...baseGameGroups.filter((group) => group.id === 'daily').map((group) => ({ ...group, title: 'Daily games' })),
    ...baseGameGroups.filter((group) => group.id === 'quizzes').map((group) => ({ ...group, title: 'Full quizzes' })),
    ...baseGameGroups.filter((group) => group.id === 'more').map((group) => ({ ...group, title: 'Play with friends' })),
    ...baseGameGroups.filter((group) => !['true-false', 'daily', 'quizzes', 'more'].includes(group.id)),
  ];
const playStyleMeta: Record<ExploreGroupId, { index: string; badge: string; title: string; summary: string; cta: string }> = {
  'true-false': {
    index: 'I',
    badge: 'Yes / No Deduction',
    title: 'Question & Map Deduction',
    summary: 'Ask yes-or-no questions to narrow down a secret country, state, or county.',
    cta: 'Play Countrydle',
  },
  'map-quizzes': {
    index: 'II',
    badge: 'Map Pinpoint',
    title: 'Click the Map',
    summary: 'Locate and click the named county or state directly on the blank cartographic map.',
    cta: 'Play Map Quiz',
  },
  'typed-chain': {
    index: 'III',
    badge: 'Border Chain',
    title: 'Follow Borders',
    summary: 'Step from neighbor to neighbor across land borders to connect two places.',
    cta: 'Play Border Hop',
  },
  daily: {
    index: 'IV',
    badge: 'Visual Clues',
    title: 'Flags & Regional Symbols',
    summary: 'Uncover a daily flag or coat of arms tile by tile with optional clues.',
    cta: 'Play Flagdle',
  },
  quizzes: {
    index: 'V',
    badge: 'Heraldry & Flag Quiz',
    title: 'Symbol Recognition',
    summary: 'Test your knowledge of Polish county coats of arms and regional flags.',
    cta: 'Play Quiz',
  },
  more: {
    index: 'VI',
    badge: '1v1 Multiplayer',
    title: 'Friend Duels',
    summary: 'Create an invite link and race a friend to deduce the same secret place.',
    cta: 'Start a Duel',
  },
};

  const mechanicCards: { group: ExploreCatalogGroup; game: CatalogMode; meta: (typeof playStyleMeta)[ExploreGroupId] }[] = [];
  const seenStylePaths = new Set<string>();
  for (const group of exploreGameGroups) {
    const featuredGame = group.id === 'true-false'
      ? group.games.find((game) => game.primary === 1) ?? group.games[0]
      : group.games[0];
    if (featuredGame && !seenStylePaths.has(featuredGame.path)) {
      seenStylePaths.add(featuredGame.path);
      mechanicCards.push({
        group,
        game: featuredGame,
        meta: playStyleMeta[group.id],
      });
    }
  }
  const totalGameModeCount = exploreGameGroups.reduce((count, group) => count + group.games.length, 0);
  const gameRegionLabels = new Set<string>();
  for (const group of exploreGameGroups) {
    for (const game of group.games) gameRegionLabels.add(gameRegionLabel(game));
  }
  const gameRegionCount = gameRegionLabels.size;
  useEffect(() => {
    setPageEditorialEligibility(publisherReady);
  }, [publisherReady]);

  useEffect(() => () => setPageEditorialEligibility(false), []);

  return (
    <div data-publisher-ready={publisherReady ? 'true' : undefined} data-publisher-error={publisherError ? 'true' : undefined} className="mx-auto max-w-6xl space-y-8 px-4 py-8 text-app-text sm:px-6 md:py-12">
      <header className="relative border-b border-app-border pb-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-sm border border-app-border/70 bg-app-surface-muted/70 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-app-accent">
              <Compass size={13} aria-hidden="true" />
              <span>Atlas · games &amp; maps</span>
            </div>
            <h1 className="mt-3 font-serif text-3xl leading-tight tracking-tight text-app-text sm:text-5xl">
              Explore the atlas
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-app-text-secondary sm:text-base">
              Pick a unique play style below, browse the full catalog of {totalGameModeCount} modes, or open the geographic reference desk.
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2 font-mono text-xs">
            <span className="rounded-sm border border-app-border bg-app-surface px-3 py-2 text-app-text shadow-[0_1px_0_rgba(85,75,57,0.08)]">
              <strong className="text-app-accent">{mechanicCards.length}</strong> styles
            </span>
            <span className="rounded-sm border border-app-border bg-app-surface px-3 py-2 text-app-text shadow-[0_1px_0_rgba(85,75,57,0.08)]">
              <strong className="text-app-accent">{totalGameModeCount}</strong> modes
            </span>
            <span className="rounded-sm border border-app-border bg-app-surface px-3 py-2 text-app-text-secondary shadow-[0_1px_0_rgba(85,75,57,0.08)]">
              {gameRegionCount} regions
            </span>
          </div>
        </div>
      </header>

      <section aria-labelledby="quick-start-heading" className="space-y-4">
        <header className="flex flex-col gap-2 border-b border-app-border pb-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-app-accent">Unique mechanics</p>
            <h2 id="quick-start-heading" className="mt-1 font-serif text-2xl leading-tight text-app-text sm:text-3xl">Choose your style</h2>
            <p className="mt-1 text-sm leading-5 text-app-text-secondary">Six distinct ways to play — no duplicates.</p>
          </div>
          <span className="font-mono text-xs text-app-text-muted">{mechanicCards.length} unique styles</span>
        </header>
        <div className="grid grid-cols-1 items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {mechanicCards.map(({ game, meta }, idx) => (
            <motion.div
              key={game.path}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ y: -3 }}
              transition={{ duration: 0.28, delay: idx * 0.04, ease: [0.16, 1, 0.3, 1] }}
              className="h-full"
            >
              <Link
                to={game.path}
                aria-label={`${meta.title}: ${meta.cta}`}
                className="group relative flex h-full min-h-[216px] min-w-0 flex-col rounded-sm border border-app-border border-t-[3px] border-t-app-accent bg-app-surface p-4 text-app-text shadow-[1px_3px_12px_rgba(85,75,57,0.08)] transition-all duration-200 hover:border-app-accent hover:bg-app-surface-raised hover:shadow-[2px_8px_22px_rgba(85,75,57,0.14)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
              >
                {/* Subtle cartographic corner ticks */}
                <span aria-hidden="true" className="pointer-events-none absolute left-1.5 top-1.5 h-2 w-2 border-l border-t border-app-border/70 transition-colors group-hover:border-app-accent/70" />
                <span aria-hidden="true" className="pointer-events-none absolute right-1.5 top-1.5 h-2 w-2 border-r border-t border-app-border/70 transition-colors group-hover:border-app-accent/70" />
                <span aria-hidden="true" className="pointer-events-none absolute bottom-1.5 left-1.5 h-2 w-2 border-b border-l border-app-border/70 transition-colors group-hover:border-app-accent/70" />
                <span aria-hidden="true" className="pointer-events-none absolute bottom-1.5 right-1.5 h-2 w-2 border-b border-r border-app-border/70 transition-colors group-hover:border-app-accent/70" />

                <div className="mb-3 flex items-center justify-between gap-2 border-b border-app-border/50 pb-2">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-app-accent">{meta.badge}</span>
                  <span className="font-serif text-xs italic text-app-text-muted">Plate {meta.index}</span>
                </div>

                <span className="flex min-w-0 flex-1 items-start gap-4">
                  <ExploreGameArtwork game={game} featured />
                  <span className="min-w-0 flex-1">
                    <span data-game-title className="block break-words font-serif text-lg font-semibold leading-6 text-app-text">{meta.title}</span>
                    <span data-game-descriptor className="mt-1.5 block break-words text-xs leading-5 text-app-text-secondary">{meta.summary}</span>
                  </span>
                </span>
                <span className="mt-3 flex shrink-0 items-center justify-between border-t border-app-border/60 pt-2.5 text-xs font-semibold text-app-accent">
                  <span>{meta.cta}</span>
                  <Play size={12} className="transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden="true" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <nav aria-label="Explore games" className="border-y border-app-border py-2">
        <a href="#playable-modes" className="inline-flex min-h-9 items-center border border-app-accent bg-app-surface-muted px-3 text-sm font-semibold text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
          Browse all game modes
        </a>
      </nav>

      <section id="playable-modes" aria-labelledby="playable-modes-heading" className="scroll-mt-24 space-y-4">
        <header className="flex flex-col gap-2 border-b border-app-border pb-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-app-accent">Complete catalog</p>
            <h2 id="playable-modes-heading" className="mt-1 font-serif text-2xl leading-tight text-app-text sm:text-3xl">Browse every game mode</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-app-text-secondary">
              Every mode is shown below, grouped by how it plays. Each entry links to its existing game.
            </p>
          </div>
          <span className="shrink-0 font-mono text-xs text-app-text-muted">{totalGameModeCount} modes</span>
        </header>
        <div id="game-mode-results" className="space-y-7">
          {exploreGameGroups.map((group) => {
            const MarkerIcon = gameGroupMarkers[group.id].icon;
            return (
              <section key={group.id} id={`play-modes-${group.id}`} aria-labelledby={`play-modes-heading-${group.id}`} className="scroll-mt-24">
                <div className="flex items-start justify-between gap-4 border-b border-app-border pb-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span aria-hidden="true" className="grid h-8 w-8 shrink-0 place-items-center border border-app-border bg-app-surface-muted text-app-accent"><MarkerIcon size={16} /></span>
                    <div className="min-w-0">
                      <h3 id={`play-modes-heading-${group.id}`} className="text-lg font-semibold text-app-text">{group.title}</h3>
                      <p className="mt-1 text-sm leading-5 text-app-text-secondary">{gameGroupNotes[group.id]}</p>
                    </div>
                  </div>
                </div>
                <ul className="mt-4 grid grid-cols-1 items-stretch gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {group.games.map((game) => {
                    const details = gameIndexFacts[game.path];
                    const descriptor = details?.rules ?? gameGroupNotes[group.id];
                    const scope = details?.scope ?? geographyLabels[game.geography];
                    return (
                      <li key={game.path} className="min-w-0">
                        <Link to={game.path} className="group flex h-full min-h-[128px] min-w-0 flex-row items-center gap-3 rounded-sm border border-app-border bg-app-surface p-3 text-left text-app-text transition-colors hover:border-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
                          <ExploreGameArtwork game={game} />
                          <span className="min-w-0 flex-1">
                            <span data-game-title title={game.name} className="block line-clamp-2 max-w-full break-words font-serif text-base font-semibold leading-5">{game.name}</span>
                            <span data-game-descriptor title={descriptor} className="mt-2 block break-words text-sm leading-5 text-app-text-secondary">{descriptor}</span>
                            <span data-game-scope title={scope} className="mt-1 block break-words text-xs leading-4 text-app-text-muted">{scope}</span>
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      </section>
      <section aria-labelledby="atlas-facts-heading" className="space-y-3 border-t border-app-border pt-5">
        <header>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-app-accent">Reference desk</p>
          <h2 id="atlas-facts-heading" className="mt-1 font-serif text-2xl text-app-text">Atlas facts</h2>
          <p className="mt-1 text-sm leading-5 text-app-text-secondary">Look up countries and regional divisions separately from the games.</p>
        </header>
        <nav aria-label="Atlas fact collections" className="flex flex-wrap gap-2">
          <button type="button" aria-pressed={activeTab === 'powiats'} onClick={() => { setActiveTab('powiats'); setSearch(''); setSelectedRegion('all'); }} className={`min-h-10 border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${activeTab === 'powiats' ? 'border-app-accent bg-app-accent text-app-on-accent' : 'border-app-border bg-app-surface text-app-text-secondary hover:border-app-accent hover:text-app-text'}`}>
            Counties of Poland
          </button>
          <button type="button" aria-pressed={activeTab === 'voivodeships'} onClick={() => { setActiveTab('voivodeships'); setSearch(''); setSelectedRegion('all'); }} className={`min-h-10 border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${activeTab === 'voivodeships' ? 'border-app-accent bg-app-accent text-app-on-accent' : 'border-app-border bg-app-surface text-app-text-secondary hover:border-app-accent hover:text-app-text'}`}>
            Polish regions
          </button>
          <button type="button" aria-pressed={activeTab === 'countries'} onClick={() => { setActiveTab('countries'); setSearch(''); setSelectedRegion('all'); }} className={`min-h-10 border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${activeTab === 'countries' ? 'border-app-accent bg-app-accent text-app-on-accent' : 'border-app-border bg-app-surface text-app-text-secondary hover:border-app-accent hover:text-app-text'}`}>
            Countries
          </button>
          <button type="button" aria-pressed={activeTab === 'us_states'} onClick={() => { setActiveTab('us_states'); setSearch(''); setSelectedRegion('all'); }} className={`min-h-10 border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${activeTab === 'us_states' ? 'border-app-accent bg-app-accent text-app-on-accent' : 'border-app-border bg-app-surface text-app-text-secondary hover:border-app-accent hover:text-app-text'}`}>
            US states
          </button>
        </nav>
      </section>

      {loading && <p role="status" className="text-base leading-7 text-app-text-secondary">Loading atlas facts…</p>}
      {status === 'error' && <p role="alert" className="text-base leading-7 text-amber-800">This content could not be loaded. Reload the page to try again; no substitute data is shown.</p>}
      {activeTab !== 'index' && status === 'success' && visibleCount === 0 && <p role="status" className="text-base leading-7 text-app-text-secondary">No entries match this view. Clear the search or choose another region; an empty response is not evidence that a place is absent from the game.</p>}
      {modalLoading && <p role="status" className="text-base leading-7 text-app-text-secondary">Loading fact sheet…</p>}
      {modalError && <div role="alert" className="space-y-3 text-amber-800"><p>{modalError}</p><button type="button" onClick={() => { rememberView('detail', ''); setModalError(''); }} className="underline underline-offset-4">Close fact sheet error</button></div>}

      {/* Search & Filters Toolbar for Atlas Tabs */}
      {activeTab !== 'index' && (
        <div className="space-y-4 rounded-sm border border-app-border bg-app-surface p-4">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-app-text-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={
                  activeTab === 'powiats'
                    ? 'Search county, seat or plate prefix'
                    : 'Search name, capital or code'
                }
                className="w-full rounded-sm border border-app-border bg-app-surface-raised py-2.5 pl-10 pr-9 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-app-text-secondary hover:text-app-text cursor-pointer"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {activeTab === 'powiats' && (
              <div className="flex flex-wrap items-center gap-2">
                <div className="inline-flex rounded-sm border border-app-border bg-app-surface-raised p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('all'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus ${
                      countyTypeFilter === 'all'
                        ? 'bg-app-accent text-app-canvas border border-app-accent'
                        : 'text-app-text-secondary hover:text-app-text'
                  }`}
                  >
                    {'All (380)'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('land'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus ${
                      countyTypeFilter === 'land'
                        ? 'bg-app-accent text-app-canvas border border-app-accent'
                        : 'text-app-text-secondary hover:text-app-text'
                  }`}
                  >
                    {'Land (314)'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setCountyTypeFilter('city'); setPowiatPage(1); }}
                    className={`rounded-xs px-2.5 py-1 font-medium transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus ${
                      countyTypeFilter === 'city'
                        ? 'bg-app-accent text-app-canvas border border-app-accent'
                        : 'text-app-text-secondary hover:text-app-text'
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
                      ? 'border-amber-700/50 bg-amber-50 text-amber-950 font-semibold'
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
              <span className="text-xs text-app-text-muted mr-1 font-mono">
                {activeTab === 'powiats' ? ('Voivodeship:') : 'Region:'}
              </span>
              {regions.map((reg) => (
                <button
                  key={reg}
                  type="button"
                  onClick={() => setSelectedRegion(reg)}
                  className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus ${
                    selectedRegion === reg
                      ? 'bg-app-accent text-app-canvas border border-app-accent'
                      : 'bg-app-surface-muted text-app-text-secondary hover:bg-app-surface-raised hover:text-app-text'
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
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-app-text-secondary font-mono">
            <span>
              {`Showing ${filteredPowiats.length} of ${powiats.length || 380} Polish counties`}
            </span>
            <div className="flex flex-wrap items-center gap-3">
              <span>{'Click shield to zoom • Click card for full facts'}</span>
              <Link
                to="/herby-powiatow"
                className="inline-flex items-center gap-1 rounded-sm bg-app-accent px-2.5 py-1 text-app-canvas hover:bg-app-accent-hover font-sans font-semibold"
              >
                <Play size={11} />
                <span>{'Play County Coats of Arms'}</span>
              </Link>
              <Link
                to="/quiz-herbow"
                className="inline-flex items-center gap-1 rounded-sm border border-amber-700/30 bg-amber-50 px-2.5 py-1 text-amber-900 hover:bg-amber-100 font-sans font-semibold"
              >
                <Shield size={11} />
                <span>{'380 Coats Quiz (JetPunk)'}</span>
              </Link>
              <Link to="/flagi-powiatow" className="inline-flex items-center gap-1 rounded-sm border border-app-border px-2.5 py-1 text-app-accent hover:text-app-accent-hover font-sans font-semibold">County Flags</Link>
              <Link to="/quiz-flag-powiatow" className="inline-flex items-center gap-1 rounded-sm border border-app-border px-2.5 py-1 text-app-accent hover:text-app-accent-hover font-sans font-semibold">County Flags Quiz</Link>
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
                  className="group cursor-pointer rounded-sm border border-app-border bg-app-surface p-4 transition-colors hover:border-app-accent hover:bg-app-surface-muted flex flex-col justify-between gap-3"
                >
                  <div className="flex items-start gap-3">
                    {/* Compact Low-Res Coat of Arms Thumbnail with 1-click Fullscreen SVG Icon */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        inspectorOpenerRef.current = e.currentTarget;
                        setInspectZoom(1);
                        setInspectedAsset({
                          url: fullCoatUrl,
                          title: p.name,
                          subtitle: `Voivodeship ${p.voivodeship} • ${p.is_city_county ? ('City county') : (`Seat: ${p.seat || '—'}`)}`,
                        });
                      }}
                      title={'Inspect coat of arms (full SVG)'}
                      className={`relative h-15 w-13.5 shrink-0 rounded-sm border p-1.5 flex items-center justify-center transition-colors ${
                        lightCoatsBackdrop
                          ? 'bg-app-surface-raised border-app-border shadow-inner'
                          : 'bg-obsidian-950/90 border-white/10 group-hover:border-app-accent'
                      }`}
                    >
                      <img
                        src={thumbCoatUrl}
                        alt={`Herb: ${p.name}`}
                        width={42}
                        height={48}
                        loading="lazy"
                        decoding="async"
                        className="max-h-11 max-w-10 w-auto h-auto object-contain select-none drop-shadow-xs"
                      />
                      <span
                        aria-hidden="true"
                        className="absolute bottom-0.5 right-0.5 inline-flex h-4.5 w-4.5 items-center justify-center rounded bg-app-surface-raised border border-app-border text-app-text-secondary opacity-75 hover:opacity-100 hover:text-app-accent transition-opacity"
                      >
                        <Maximize2 size={10} />
                      </span>
                    </button>
                    {/* County Identity & License Plates */}
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-1">
                        <span className="font-mono text-xs text-app-accent font-semibold">
                          Voivodeship {p.voivodeship}
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono text-xs ${
                            p.is_city_county
                              ? 'bg-amber-50 text-amber-900 border border-amber-700/30'
                              : 'bg-app-surface-muted text-app-text-secondary border border-app-border'
                          }`}
                        >
                          {p.is_city_county
                            ? 'City county'
                            : 'Land county'}
                        </span>
                      </div>

                      <h4 className="font-serif text-base font-bold text-app-text group-hover:text-app-accent transition-colors leading-snug">
                        {p.name}
                      </h4>

                      <div className="pt-0.5">
                        <MiniLicensePlate plates={p.registration_plates} />
                      </div>
                    </div>
                  </div>

                  <div className="pt-2.5 border-t border-app-border grid grid-cols-3 gap-2 text-[11px] text-app-text-secondary font-mono">
                    <div className="truncate">
                      <span className="text-app-text-muted block text-[10px]">{'Seat'}</span>
                      <span className="text-app-text truncate block" title={p.seat || '—'}>
                        {p.seat || '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-app-text-muted block text-[10px]">{'Pop.'}</span>
                      <span className="text-app-text block">
                        {p.population ? Number(p.population).toLocaleString('en-US') : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-app-text-muted block text-[10px]">{'Area'}</span>
                      <span className="text-app-text block">
                        {p.area_km2 ? `${Number(p.area_km2).toLocaleString('en-US')} km²` : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {totalPowiatPages > 1 && (
            <div className="flex items-center justify-between border-t border-app-border pt-4 font-mono text-xs text-app-text-secondary">
              <span>
                {`Page ${powiatPage} of ${totalPowiatPages} (${filteredPowiats.length} counties)`}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={powiatPage <= 1}
                  onClick={() => setPowiatPage((p) => Math.max(1, p - 1))}
                  className="rounded-sm border border-app-border bg-app-surface px-3 py-1.5 text-app-text-secondary hover:border-app-accent hover:text-app-text disabled:opacity-40 cursor-pointer"
                >
                  {'Previous'}
                </button>
                <button
                  type="button"
                  disabled={powiatPage >= totalPowiatPages}
                  onClick={() => setPowiatPage((p) => Math.min(totalPowiatPages, p + 1))}
                  className="rounded-sm border border-app-border bg-app-surface px-3 py-1.5 text-app-text-secondary hover:border-app-accent hover:text-app-text disabled:opacity-40 cursor-pointer"
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
          <div className="flex items-center justify-between text-xs text-app-text-secondary font-mono">
            <span>Showing {filteredCountries.length} countries</span>
            <span>Click any card for full fact sheet</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredCountries.map((c) => (
              <div
                key={c.id}
                onClick={() => openCountryModal(c.cca3 || c.app_country_name)}
                className="group cursor-pointer rounded-sm border border-app-border bg-app-surface p-4 transition-colors hover:border-app-accent hover:bg-app-surface-muted flex flex-col justify-between"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-app-accent">
                        {c.cca3 || c.cca2}
                      </span>
                      <span className="text-[11px] text-app-text-muted">{c.region}</span>
                    </div>
                    <h4 className="font-serif text-lg font-semibold text-app-text group-hover:text-app-accent transition-colors">
                      {c.app_country_name}
                    </h4>
                    <p className="text-xs text-app-text-secondary break-words">
                      {c.official_name || c.app_country_name}
                    </p>
                  </div>
                  {c.cca2 && (
                    <img
                      src={`https://flagcdn.com/w80/${String(c.cca2).toLowerCase()}.png`}
                      alt={`${c.app_country_name} flag`}
                      loading="lazy"
                      className="h-10 w-15 shrink-0 rounded-xs border border-app-border object-cover shadow-xs"
                    />
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-app-border grid grid-cols-2 gap-2 text-[11px] text-app-text-secondary font-mono">
                  <div>
                    <span className="text-app-text-muted block">Capital</span>
                    <span className="text-app-text block break-words">{c.capital || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-app-text-muted block">Population</span>
                    <span className="text-app-text block">{c.population ? Number(c.population).toLocaleString('en-US') : 'N/A'}</span>
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
          <div className="flex items-center justify-between text-xs text-app-text-secondary font-mono">
            <span>Showing {filteredUSStates.length} states</span>
            <span>Click any card for state facts & borders</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredUSStates.map((s) => (
              <div
                key={s.id}
                onClick={() => openStateModal(s.name)}
                className="group cursor-pointer rounded-sm border border-app-border bg-app-surface p-4 transition-colors hover:border-app-accent hover:bg-app-surface-muted flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-app-accent">
                      #{s.admission_order} admitted ({s.admission_year})
                    </span>
                    <span className="text-[11px] text-app-text-muted">{s.region}</span>
                  </div>
                  <h4 className="font-serif text-lg font-semibold text-app-text group-hover:text-app-accent transition-colors">
                    {s.name}
                  </h4>
                  <p className="text-xs text-app-text-secondary break-words">
                    {s.nickname || 'The State of ' + s.name}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-app-border grid grid-cols-2 gap-2 text-[11px] text-app-text-secondary font-mono">
                  <div>
                    <span className="text-app-text-muted block">Division</span>
                    <span className="text-app-text block break-words">{s.division || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-app-text-muted block">Population</span>
                    <span className="text-app-text block">{s.population ? Number(s.population).toLocaleString('en-US') : 'N/A'}</span>
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
          <div className="flex items-center justify-between text-xs text-app-text-secondary font-mono">
            <span>Showing {filteredVoivodeships.length} voivodeships</span>
            <span>Click any card for regional stats</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredVoivodeships.map((v) => (
              <div
                key={v.id}
                onClick={() => openVoivodeshipModal(v.name)}
                className="group cursor-pointer rounded-sm border border-app-border bg-app-surface p-4 transition-colors hover:border-app-accent hover:bg-app-surface-muted flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-app-accent">
                      TERYT {v.teryt}
                    </span>
                    <span className="text-[11px] text-app-text-muted">{regionalDisplay[v.macroregion] ?? v.macroregion}</span>
                  </div>
                  <h4 className="font-serif text-lg font-semibold text-app-text group-hover:text-app-accent transition-colors">
                    {v.name}
                  </h4>
                  <p className="text-xs text-app-text-secondary">
                    Administrative seat: <strong className="text-app-text">{v.seat}</strong>
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-app-border grid grid-cols-2 gap-2 text-[11px] text-app-text-secondary font-mono">
                  <div>
                    <span className="text-app-text-muted block">Counties</span>
                    <span className="text-app-text block">{v.powiat_count}</span>
                  </div>
                  <div>
                    <span className="text-app-text-muted block">Urbanization</span>
                    <span className="text-app-text block">{v.urbanization_percent}%</span>
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
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-app-text/40 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-sm border border-app-border bg-app-surface-raised p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-app-text shadow-lg md:max-h-[90vh] md:p-8"
          >
            <button 
              type="button" 
              onClick={() => setSelectedCountry(null)}
              aria-label={'Close country details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-app-text-secondary hover:text-app-text"
            >
              <X size={20} />
            </button>

            <header className="border-b border-app-border pb-4">
              <span className="font-mono text-xs text-app-accent">
                {selectedCountry.cca3} &bull; {selectedCountry.region}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-app-text">
                {selectedCountry.app_country_name}
              </h2>
              <p className="text-xs text-app-text-muted mt-1">
                Official: {selectedCountry.official_name}
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Capital</span>
                <span className="font-bold text-app-text">{selectedCountry.capital || 'N/A'}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Population</span>
                <span className="font-bold text-app-text">{Number(selectedCountry.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Area (km²)</span>
                <span className="font-bold text-app-text">{Number(selectedCountry.area_km2).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Driving Side</span>
                <span className="font-bold text-app-text capitalize">{selectedCountry.driving_side || 'N/A'}</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedCountry.borders && selectedCountry.borders.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Neighboring Borders ({selectedCountry.borders.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.borders.map((b: string) => (
                      <span key={b} className="px-2 py-0.5 bg-app-surface-muted border border-app-border rounded text-app-text-secondary">
                        {b}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedCountry.water_access && selectedCountry.water_access.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Water &amp; Coastline Access:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.water_access.map((w: string) => (
                      <span key={w} className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded">
                        {w}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedCountry.languages && selectedCountry.languages.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Recorded Languages:</span>
                  <span className="text-app-text-secondary">{selectedCountry.languages.join(', ')}</span>
                </div>
              )}

              {selectedCountry.flag_colors && selectedCountry.flag_colors.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">National Flag Colors:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCountry.flag_colors.map((fc: string) => (
                      <span key={fc} className="px-2 py-0.5 bg-app-surface-muted border border-app-border text-app-text-secondary rounded capitalize">
                        {fc}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-app-border pt-4 flex justify-between items-center">
              <Link 
                to="/game"
                className="inline-flex items-center gap-2 rounded-sm bg-app-accent px-4 py-2 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors"
              >
                <Play size={13} />
                <span>Play World Countrydle</span>
              </Link>
              <button 
                type="button" 
                onClick={() => setSelectedCountry(null)}
                className="text-xs text-app-text-secondary hover:text-app-text"
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
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-app-text/40 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-sm border border-app-border bg-app-surface-raised p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-app-text shadow-lg md:max-h-[90vh] md:p-8"
          >
            <button
              type="button"
              onClick={() => setSelectedState(null)}
              aria-label={'Close state details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-app-text-secondary hover:text-app-text"
            >
              <X size={20} />
            </button>

            <header className="border-b border-app-border pb-4">
              <span className="font-mono text-xs text-app-accent">
                #{selectedState.admission_order} Admitted &bull; {selectedState.region}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-app-text">
                {selectedState.name}
              </h2>
              <p className="text-xs text-app-text-muted mt-1">
                {selectedState.nickname}
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Division</span>
                <span className="font-bold text-app-text">{selectedState.division || 'N/A'}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Population</span>
                <span className="font-bold text-app-text">{Number(selectedState.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Area (sq mi)</span>
                <span className="font-bold text-app-text">{Number(selectedState.area_sq_mi).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Admission Year</span>
                <span className="font-bold text-app-text">{selectedState.admission_year}</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedState.neighboring_states && selectedState.neighboring_states.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Neighboring US States ({selectedState.neighboring_states.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedState.neighboring_states.map((st: string) => (
                      <span key={st} className="px-2 py-0.5 bg-app-surface-muted border border-app-border rounded text-app-text-secondary">
                        {st}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedState.water_access && selectedState.water_access.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Water Bodies &amp; Ocean Access:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedState.water_access.map((w: string) => (
                      <span key={w} className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded">
                        {w}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-app-border pt-4 flex justify-between items-center">
              <Link
                to="/us-states"
                className="inline-flex items-center gap-2 rounded-sm bg-app-accent px-4 py-2 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors"
              >
                <Play size={13} />
                <span>Play US Statedle</span>
              </Link>
              <button
                type="button"
                onClick={() => setSelectedState(null)}
                className="text-xs text-app-text-secondary hover:text-app-text"
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
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-app-text/40 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl max-h-full overflow-y-auto rounded-sm border border-app-border bg-app-surface-raised p-4 pt-14 sm:p-8 sm:pt-14 space-y-6 text-app-text shadow-lg md:max-h-[90vh] md:p-8"
          >
            <button
              type="button"
              onClick={() => setSelectedVoivodeship(null)}
              aria-label={'Close voivodeship details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-app-text-secondary hover:text-app-text"
            >
              <X size={20} />
            </button>

            <header className="border-b border-app-border pb-4">
              <span className="font-mono text-xs text-app-accent">
                TERYT {selectedVoivodeship.teryt} &bull; Macroregion {regionalDisplay[selectedVoivodeship.macroregion] ?? selectedVoivodeship.macroregion}
              </span>
              <h2 className="font-serif text-3xl font-bold mt-1 text-app-text">
                {selectedVoivodeship.name} Voivodeship
              </h2>
              <p className="text-xs text-app-text-muted mt-1">
                Administrative seat: <strong className="text-app-text">{selectedVoivodeship.seat}</strong>
              </p>
            </header>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Population</span>
                <span className="font-bold text-app-text">{Number(selectedVoivodeship.population).toLocaleString('en-US')}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Area</span>
                <span className="font-bold text-app-text">{Number(selectedVoivodeship.area_km2).toLocaleString('en-US')} km²</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Counties</span>
                <span className="font-bold text-app-text">{selectedVoivodeship.powiat_count}</span>
              </div>
              <div className="p-3 bg-app-surface-muted rounded">
                <span className="text-app-text-muted block">Urbanization</span>
                <span className="font-bold text-app-text">{selectedVoivodeship.urbanization_percent}%</span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              {selectedVoivodeship.neighboring_voivodeships && selectedVoivodeship.neighboring_voivodeships.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Neighboring voivodeships ({selectedVoivodeship.neighboring_voivodeships.length}):</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVoivodeship.neighboring_voivodeships.map((v: string) => (
                      <span key={v} className="px-2 py-0.5 bg-app-surface-muted border border-app-border rounded text-app-text-secondary">
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedVoivodeship.neighboring_countries && selectedVoivodeship.neighboring_countries.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">Bordering countries:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVoivodeship.neighboring_countries.map((c: string) => (
                      <span key={c} className="px-2 py-0.5 bg-app-surface-muted border border-app-border text-app-accent rounded">
                        {regionalDisplay[c] ?? c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-app-border pt-4 flex justify-between items-center">
              <Link
                to="/wojewodztwa"
                className="inline-flex items-center gap-2 rounded-sm bg-app-accent px-4 py-2 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors"
              >
                <Play size={13} />
                <span>Play Województwodle</span>
              </Link>
              <button
                type="button"
                onClick={() => setSelectedVoivodeship(null)}
                className="text-xs text-app-text-secondary hover:text-app-text"
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
          className="fixed inset-0 z-[1200] flex max-h-[var(--app-height,100dvh)] items-center justify-center overflow-y-auto bg-app-text/40 p-2 backdrop-blur-sm md:max-h-none md:p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-3xl max-h-full overflow-y-auto rounded-sm border border-app-border bg-app-surface-raised p-4 pt-12 sm:p-7 sm:pt-12 space-y-6 text-app-text shadow-lg md:max-h-[90vh]"
          >
            <button
              type="button"
              onClick={() => setSelectedPowiat(null)}
              aria-label={'Close county details'}
              className="absolute right-2 top-2 inline-flex min-h-11 min-w-11 items-center justify-center text-app-text-secondary hover:text-app-text cursor-pointer"
            >
              <X size={20} />
            </button>

            <header className="flex flex-col sm:flex-row items-center sm:items-start gap-5 border-b border-app-border pb-5">
              {/* Coat of Arms Pedestal with Fullscreen Trigger */}
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  inspectorOpenerRef.current = e.currentTarget;
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
                    inspectorOpenerRef.current = e.currentTarget;
                    setInspectZoom(1);
                    setInspectedAsset({
                      url: resolvePowiatCoatUrl(selectedPowiat.id),
                      title: selectedPowiat.name,
                      subtitle: `Voivodeship ${selectedPowiat.voivodeship}`,
                    });
                  }
                }}
                aria-label={'Inspect county coat of arms'}
                className={`group relative h-32 w-28 shrink-0 rounded-sm border p-3 flex items-center justify-center cursor-zoom-in transition-colors ${
                  lightCoatsBackdrop
                    ? 'bg-app-surface-raised border-app-border shadow-md'
                    : 'bg-obsidian-950 border-white/15 hover:border-app-accent shadow-inner'
                }`}
              >
                <img
                  src={resolvePowiatCoatUrl(selectedPowiat.id)}
                  alt={`Herb: ${selectedPowiat.name}`}
                  className="max-h-26 max-w-22 w-auto h-auto object-contain select-none drop-shadow-md"
                />
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute bottom-1.5 right-1.5 inline-flex h-6 w-6 items-center justify-center rounded bg-app-surface-raised border border-app-border text-app-text-secondary group-hover:border-app-accent group-hover:text-app-accent"
                >
                  <Maximize2 size={13} />
                </span>
              </div>

              <div className="flex-1 text-center sm:text-left space-y-2">
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                  <span className="font-mono text-xs text-app-accent font-semibold">
                    {selectedPowiat.voivodeship} Voivodeship
                  </span>
                  {selectedPowiat.terc && (
                    <span className="rounded bg-app-surface-muted border border-app-border px-2 py-0.5 font-mono text-[11px] text-app-text-secondary">
                      TERYT {selectedPowiat.terc}
                    </span>
                  )}
                  <span
                    className={`rounded px-2 py-0.5 font-mono text-[11px] ${
                      selectedPowiat.is_city_county
                        ? 'bg-amber-50 text-amber-900 border border-amber-700/30'
                        : 'bg-app-surface-muted text-app-accent border border-app-border'
                    }`}
                  >
                    {selectedPowiat.is_city_county ? 'City with county rights' : 'Land county'}
                  </span>
                </div>

                <h2 className="font-serif text-2xl sm:text-3xl font-bold text-app-text">
                  {selectedPowiat.name}
                </h2>

                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3 pt-1">
                  {selectedPowiat.seat && (
                    <span className="text-xs text-app-text-secondary">
                      {'County Seat:'}{' '}
                      <strong className="text-app-text">{selectedPowiat.seat}</strong>
                    </span>
                  )}
                  {selectedPowiat.registration_plates && selectedPowiat.registration_plates.length > 0 && (
                    <div className="inline-flex items-center gap-1.5">
                      <span className="text-xs text-app-text-muted font-mono">
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
              <div className="p-3 bg-app-surface-muted border border-app-border rounded">
                <span className="text-app-text-muted block">{'Population'}</span>
                <span className="font-bold text-app-text text-sm">
                  {selectedPowiat.population ? Number(selectedPowiat.population).toLocaleString('en-US') : '—'}
                </span>
              </div>
              <div className="p-3 bg-app-surface-muted border border-app-border rounded">
                <span className="text-app-text-muted block">{'Area'}</span>
                <span className="font-bold text-app-text text-sm">
                  {selectedPowiat.area_km2 ? `${Number(selectedPowiat.area_km2).toLocaleString('en-US')} km²` : '—'}
                </span>
              </div>
              <div className="p-3 bg-app-surface-muted border border-app-border rounded">
                <span className="text-app-text-muted block">{'Density'}</span>
                <span className="font-bold text-app-text text-sm">
                  {selectedPowiat.population_density
                    ? `${Math.round(Number(selectedPowiat.population_density)).toLocaleString('en-US')} people/km²`
                    : '—'}
                </span>
              </div>
              <div className="p-3 bg-app-surface-muted border border-app-border rounded">
                <span className="text-app-text-muted block">{'Municipalities'}</span>
                <span className="font-bold text-app-text text-sm">
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
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {`Neighboring Counties (${selectedPowiat.neighboring_powiats.length}) — click to inspect:`}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_powiats.map((np: string) => (
                      <button
                        key={np}
                        type="button"
                        onClick={() => openPowiatModal(np)}
                        className="px-2.5 py-1 bg-app-surface-muted hover:bg-app-accent/10 border border-app-border hover:border-app-accent rounded text-app-text-secondary hover:text-app-accent transition-colors cursor-pointer"
                      >
                        {np}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.neighboring_voivodeships && selectedPowiat.neighboring_voivodeships.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'Borders with other Voivodeships:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_voivodeships.map((nv: string) => (
                      <span key={nv} className="px-2 py-0.5 bg-purple-50 border border-purple-200 text-purple-800 rounded">
                        Voivodeship {nv}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.neighboring_countries && selectedPowiat.neighboring_countries.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'International Border:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.neighboring_countries.map((nc: string) => (
                      <span key={nc} className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-900 rounded font-semibold">
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
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'Rivers, Lakes & Water Bodies:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.water_access || []).map((w: string) => (
                      <span key={`w-${w}`} className="px-2 py-0.5 bg-cyan-50 border border-cyan-200 text-cyan-800 rounded">
                        {w}
                      </span>
                    ))}
                    {(selectedPowiat.major_rivers || []).map((r: string) => (
                      <span key={`r-${r}`} className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded">
                        River {r}
                      </span>
                    ))}
                    {(selectedPowiat.lakes || []).map((l: string) => (
                      <span key={`l-${l}`} className="px-2 py-0.5 bg-sky-50 border border-sky-200 text-sky-800 rounded">
                        Lake {l}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedPowiat.major_roads && selectedPowiat.major_roads.length > 0 && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'Major Highways & National Roads:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPowiat.major_roads.map((rd: string) => (
                      <span key={rd} className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded font-mono">
                        {rd}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {((selectedPowiat.landform_regions && selectedPowiat.landform_regions.length > 0) ||
                (selectedPowiat.historical_regions && selectedPowiat.historical_regions.length > 0)) && (
                <div>
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'Geographic & Historical Regions:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.landform_regions || []).map((reg: string) => (
                      <span key={`lf-${reg}`} className="px-2 py-0.5 bg-app-surface-muted border border-app-border text-app-text-secondary rounded">
                        {reg}
                      </span>
                    ))}
                    {(selectedPowiat.historical_regions || []).map((hr: string) => (
                      <span key={`hr-${hr}`} className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-800 rounded">
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
                  <span className="font-semibold text-app-text-secondary block mb-1.5 font-mono">
                    {'National Parks, Health Resorts & UNESCO:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(selectedPowiat.national_parks || []).map((np: string) => (
                      <span key={`np-${np}`} className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded">
                        {np}
                      </span>
                    ))}
                    {(selectedPowiat.health_resorts || []).map((hr: string) => (
                      <span key={`res-${hr}`} className="px-2 py-0.5 bg-teal-50 border border-teal-200 text-teal-800 rounded">
                        Health resort: {hr}
                      </span>
                    ))}
                    {(selectedPowiat.unesco_sites || []).map((u: string) => (
                      <span key={`un-${u}`} className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-900 rounded font-semibold">
                        UNESCO: {u}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-app-border pt-4 flex flex-wrap justify-between items-center gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/herby-powiatow"
                  className="inline-flex items-center gap-2 rounded-sm bg-app-accent px-4 py-2 text-xs font-bold text-app-canvas hover:bg-app-accent-hover transition-colors"
                >
                  <Shield size={13} />
                  <span>{'Play County Coats of Arms'}</span>
                </Link>
                <Link to="/flagi-powiatow" className="inline-flex items-center gap-2 rounded-sm border border-app-border bg-app-surface px-4 py-2 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted transition-colors">Play County Flags</Link>
                <Link
                  to="/powiaty"
                  className="inline-flex items-center gap-2 rounded-sm border border-app-border bg-app-surface px-4 py-2 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted transition-colors"
                >
                  <Play size={13} />
                  <span>{'Play Powiatdle'}</span>
                </Link>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPowiat(null)}
                className="text-xs text-app-text-secondary hover:text-app-text cursor-pointer"
              >
                {'Close Fact Sheet'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Coat of Arms Inspector Lightbox */}
      {inspectedAsset && typeof document !== 'undefined' && createPortal(
        <div
          ref={inspectorRef}
          role="dialog"
          aria-modal="true"
          aria-label={inspectedAsset.title}
          onClick={() => setInspectedAsset(null)}
          className="image-inspector fixed inset-0 z-[2200] flex h-[100dvh] flex-col overflow-hidden bg-app-canvas text-app-text backdrop-blur-md select-none sm:h-auto"
        >
          <style>{`
            .explore-inspector-mobile { display: none; }
            @media (max-width: 767px), (max-width: 1023px) and (max-height: 500px) {
              .explore-inspector-mobile { display: flex; }
              .explore-inspector-desktop { display: none; }
            }
          `}</style>
          <button
            type="button"
            aria-label="Close image"
            onClick={(e) => { e.stopPropagation(); setInspectedAsset(null); }}
            className="explore-inspector-mobile absolute z-10 h-11 w-11 items-center justify-center rounded-sm bg-app-surface text-app-text shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            style={{ top: 'max(1rem, env(safe-area-inset-top))', right: 'max(1rem, env(safe-area-inset-right))' }}
          >
            <X size={22} aria-hidden="true" />
          </button>
          <div
            className="explore-inspector-mobile min-h-0 flex-1 items-center justify-center"
            style={{ padding: 'max(1rem, env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right)) max(1rem, env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left))' }}
          >
            <img src={inspectedAsset.url} alt={inspectedAsset.title} className="max-h-full max-w-full object-contain" />
          </div>
          {/* Top Toolbar */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="explore-inspector-desktop flex flex-wrap items-center justify-between gap-3 border-b border-app-border bg-app-surface-raised px-4 py-3 sm:px-6 shrink-0"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Shield size={16} className="text-app-accent shrink-0" />
              <span className="font-serif text-sm font-bold text-app-text truncate">
                {inspectedAsset.title}
              </span>
              {inspectedAsset.subtitle && (
                <span className="hidden sm:inline font-mono text-xs text-app-text-muted">
                  • {inspectedAsset.subtitle}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                disabled={inspectZoom <= 1}
                className="inline-flex items-center justify-center rounded border border-app-border bg-app-surface p-1.5 text-app-text-secondary hover:text-app-text hover:border-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:opacity-40 cursor-pointer"
              >
                <ZoomOut size={15} />
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom(1)}
                className="rounded border border-app-border bg-app-surface px-2 py-1 font-mono text-xs text-app-text-secondary hover:border-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus cursor-pointer"
              >
                {Math.round(inspectZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={() => setInspectZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                disabled={inspectZoom >= 3}
                className="inline-flex items-center justify-center rounded border border-app-border bg-app-surface p-1.5 text-app-text-secondary hover:text-app-text hover:border-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:opacity-40 cursor-pointer"
              >
                <ZoomIn size={15} />
              </button>
              <button
                type="button"
                onClick={() => setLightCoatsBackdrop((b) => !b)}
                className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer ${
                  lightCoatsBackdrop
                    ? 'border-app-border bg-app-surface-muted text-app-text font-semibold'
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
                aria-label="Close image"
                className="inline-flex items-center gap-1 rounded border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100 hover:border-rose-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus transition-colors cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Centered Canvas */}
          <div
            onClick={() => setInspectedAsset(null)}
            className="explore-inspector-desktop flex flex-1 overflow-auto items-center justify-center p-4 sm:p-8"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className={`relative flex items-center justify-center rounded-2xl border p-6 sm:p-10 shadow-2xl transition-colors duration-200 ${
                lightCoatsBackdrop
                  ? 'border-app-border bg-app-surface-raised shadow-black/20'
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
                className="max-w-[88vw] object-contain select-none filter drop-shadow-2xl"
              />
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* AdSense Unit */}
      {publisherReady && <AdSenseUnit slot="explore-hub-footer" className="max-w-2xl mx-auto pt-6" />}
    </div>
  );
}
