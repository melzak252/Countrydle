import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BookOpen, Route, ArrowRight, ExternalLink, Globe, MapPin } from 'lucide-react';
import { exploreService, type BorderHopChallenge } from '../services/api';
import type { AnswerReportMode } from '../types';

interface LocationFacts {
  capital?: string;
  seat?: string;
  population?: number;
  area_km2?: number;
  area_sq_mi?: number;
  region?: string;
  subregion?: string;
  voivodeship?: string;
  admission_year?: number;
  registration_plates?: string[];
  languages?: string[];
  currencies?: string[];
  water_access?: string[];
  is_island?: boolean | number;
  borders?: string[];
  neighboring_states?: string[];
  neighboring_voivodeships?: string[];
  neighboring_powiats?: string[];
}

interface LocationFieldNotesProps {
  targetName?: string;
  mode: AnswerReportMode;
  gamePath: string;
  targetCountryCode?: string;
}

export default function LocationFieldNotes({
  targetName,
  mode,
  gamePath: _gamePath,
  targetCountryCode: _targetCountryCode,
}: LocationFieldNotesProps) {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const [facts, setFacts] = useState<LocationFacts | null>(null);
  const [challenge, setChallenge] = useState<BorderHopChallenge | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!targetName) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);

    const fetchData = async () => {
      try {
        // 1. Fetch entity factual details
        let detailPromise: Promise<LocationFacts>;
        if (mode === 'us_statedle') {
          detailPromise = exploreService.getUSStateDetail(targetName);
        } else if (mode === 'wojewodztwodle') {
          detailPromise = exploreService.getVoivodeshipDetail(targetName);
        } else if (mode === 'powiatdle') {
          detailPromise = exploreService.getPowiatDetail(targetName);
        } else {
          detailPromise = exploreService.getCountryDetail(targetName);
        }

        // 2. Fetch border hop challenge
        const hopMode = mode === 'us_statedle' ? 'us_states' : 'countries';
        const challengePromise = (mode === 'us_statedle' || mode === 'countrydle' || mode === 'continental')
          ? exploreService.getBorderHopChallenge({ mode: hopMode, target: targetName })
          : exploreService.getBorderHopChallenge({ mode: 'countries' });

        const [factsRes, challengeRes] = await Promise.allSettled([detailPromise, challengePromise]);

        if (!isMounted) return;

        if (factsRes.status === 'fulfilled') {
          setFacts(factsRes.value);
        } else {
          setFacts(null);
        }

        if (challengeRes.status === 'fulfilled') {
          setChallenge(challengeRes.value);
        } else {
          setChallenge(null);
        }
      } catch {
        if (!isMounted) return;
        setFacts(null);
        setChallenge(null);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [targetName, mode]);

  if (!targetName) return null;

  // Extract borders list depending on entity schema
  const rawBorders: string[] = facts
    ? (facts.borders || facts.neighboring_states || facts.neighboring_voivodeships || facts.neighboring_powiats || [])
    : [];

  const hopMode = mode === 'us_statedle' ? 'us_states' : 'countries';

  return (
    <div className="rounded-sm border border-white/10 bg-obsidian-900/50 p-4 sm:p-5 text-left space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div className="flex items-center gap-2">
          <BookOpen size={18} className="text-emerald-400" />
          <h3 className="font-mono text-sm font-semibold tracking-wide text-sand-100 uppercase">
            {isPl ? 'Notatki Terenowe' : 'Location Field Notes'}
          </h3>
        </div>
        <Link
          to="/explore"
          className="text-xs text-zinc-400 hover:text-emerald-400 transition-colors flex items-center gap-1"
        >
          <span>{isPl ? 'Przewodnik' : 'Atlas Guide'}</span>
          <ExternalLink size={12} />
        </Link>
      </div>

      {loading ? (
        <div className="py-4 text-center text-xs text-zinc-400 font-mono animate-pulse">
          {isPl ? 'Ładowanie faktów geograficznych...' : 'Loading geographic field notes...'}
        </div>
      ) : (
        <>
          {/* Key Metrics Grid */}
          {facts && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3 text-xs">
              {/* Capital or Seat */}
              {(facts.capital || facts.seat) && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {facts.capital ? (isPl ? 'Stolica' : 'Capital') : (isPl ? 'Siedziba' : 'Seat')}
                  </span>
                  <span className="font-semibold text-sand-100 truncate block mt-0.5">
                    {facts.capital || facts.seat}
                  </span>
                </div>
              )}

              {/* Population */}
              {facts.population !== undefined && facts.population !== null && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Populacja' : 'Population'}
                  </span>
                  <span className="font-semibold font-mono text-sand-100 truncate block mt-0.5">
                    {Number(facts.population).toLocaleString()}
                  </span>
                </div>
              )}

              {/* Area */}
              {(facts.area_km2 || facts.area_sq_mi) && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Powierzchnia' : 'Area'}
                  </span>
                  <span className="font-semibold font-mono text-sand-100 truncate block mt-0.5">
                    {facts.area_km2
                      ? `${Number(facts.area_km2).toLocaleString()} km²`
                      : `${Number(facts.area_sq_mi).toLocaleString()} sq mi`}
                  </span>
                </div>
              )}

              {/* Region or Voivodeship or Admission Year */}
              {(facts.subregion || facts.region || facts.voivodeship || facts.admission_year) && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {facts.voivodeship
                      ? (isPl ? 'Województwo' : 'Voivodeship')
                      : facts.admission_year
                      ? (isPl ? 'Rok przyjęcia' : 'Admission')
                      : (isPl ? 'Region' : 'Region')}
                  </span>
                  <span className="font-semibold text-sand-100 truncate block mt-0.5">
                    {facts.voivodeship || facts.admission_year || facts.subregion || facts.region}
                  </span>
                </div>
              )}

              {/* Plates for Powiaty */}
              {facts.registration_plates && facts.registration_plates.length > 0 && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Tablice' : 'Plates'}
                  </span>
                  <span className="font-semibold font-mono text-sand-100 truncate block mt-0.5">
                    {facts.registration_plates.join(', ')}
                  </span>
                </div>
              )}

              {/* Languages for Countries */}
              {facts.languages && facts.languages.length > 0 && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Języki' : 'Languages'}
                  </span>
                  <span className="font-semibold text-sand-100 truncate block mt-0.5">
                    {facts.languages.slice(0, 2).join(', ')}
                  </span>
                </div>
              )}

              {/* Water Access */}
              {facts.water_access !== undefined && (
                <div className="p-2.5 rounded-sm bg-obsidian-950/40 border border-white/5">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Dostęp do wody' : 'Water Access'}
                  </span>
                  <span className="font-semibold text-sand-100 truncate block mt-0.5">
                    {facts.is_island
                      ? (isPl ? 'Wyspa' : 'Island')
                      : facts.water_access && facts.water_access.length > 0
                      ? (isPl ? 'Wybrzeże' : 'Coastal')
                      : (isPl ? 'Śródlądowe' : 'Landlocked')}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Bordering Neighbors Badges */}
          {rawBorders.length > 0 && (
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
                {isPl ? `Graniczące jednostki (${rawBorders.length})` : `Bordering Neighbors (${rawBorders.length})`}
              </span>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto custom-scrollbar pr-1">
                {rawBorders.map((nbr) => (
                  <span
                    key={nbr}
                    className="inline-flex items-center gap-1 rounded-xs bg-white/5 border border-white/10 px-2 py-0.5 text-[11px] text-zinc-300 font-medium"
                  >
                    <MapPin size={10} className="text-zinc-500" />
                    {nbr}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Border Hop Bridge Card */}
          <div className="rounded-sm border border-emerald-500/20 bg-emerald-950/20 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Route size={16} className="text-emerald-400" />
                <span className="font-mono text-xs font-semibold uppercase tracking-wider text-emerald-300">
                  {isPl ? 'Wyzwanie Border Hop' : 'Border Hop Challenge'}
                </span>
              </div>
              {challenge?.optimal_hops !== null && challenge?.optimal_hops !== undefined && (
                <span className="font-mono text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-xs">
                  {isPl ? `${challenge.optimal_hops} przeskoków` : `${challenge.optimal_hops} hops`}
                </span>
              )}
            </div>

            {challenge?.connected && challenge.start ? (
              <p className="text-xs text-zinc-300">
                {isPl ? (
                  <>
                    Czy potrafisz przejść z <strong className="text-sand-100">{challenge.start}</strong> do{' '}
                    <strong className="text-sand-100">{targetName}</strong> przez sąsiadujące granice w{' '}
                    <strong className="text-emerald-400">{challenge.optimal_hops} przeskokach</strong>?
                  </>
                ) : (
                  <>
                    Can you navigate from <strong className="text-sand-100">{challenge.start}</strong> to{' '}
                    <strong className="text-sand-100">{targetName}</strong> across bordering territories in{' '}
                    <strong className="text-emerald-400">{challenge.optimal_hops} hops</strong>?
                  </>
                )}
              </p>
            ) : challenge?.is_island ? (
              <p className="text-xs text-zinc-300">
                {isPl ? (
                  <>
                    <strong className="text-sand-100">{targetName}</strong> to wyspa bez lądowych granic! Wypróbuj
                    dzisiejsze polecane wyzwanie Border Hop.
                  </>
                ) : (
                  <>
                    <strong className="text-sand-100">{targetName}</strong> is an island with no land borders! Try
                    today's featured Daily Border Hop instead.
                  </>
                )}
              </p>
            ) : (
              <p className="text-xs text-zinc-300">
                {isPl
                  ? 'Zagraj w łamigłówkę poszukiwania ścieżki przez sąsiadujące kraje i stany!'
                  : 'Play the geographic path-finding puzzle across bordering countries and states!'}
              </p>
            )}

            <div className="pt-0.5">
              {challenge?.connected && challenge.start ? (
                <Link
                  to={`/border-hop?mode=${hopMode}&start=${encodeURIComponent(challenge.start)}&target=${encodeURIComponent(targetName)}`}
                  className="inline-flex min-h-9 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-3.5 py-1.5 text-xs font-bold text-obsidian-950 transition-colors hover:bg-emerald-300"
                >
                  <Route size={14} />
                  <span>
                    {isPl
                      ? `Rozpocznij Border Hop (${challenge.optimal_hops} przeskoków)`
                      : `Start Border Hop (${challenge.optimal_hops} Hops)`}
                  </span>
                  <ArrowRight size={14} />
                </Link>
              ) : (
                <Link
                  to="/border-hop"
                  className="inline-flex min-h-9 items-center justify-center gap-2 rounded-sm bg-emerald-400/90 px-3.5 py-1.5 text-xs font-bold text-obsidian-950 transition-colors hover:bg-emerald-300"
                >
                  <Globe size={14} />
                  <span>{isPl ? 'Zagraj w Daily Border Hop' : 'Play Daily Border Hop'}</span>
                  <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
