import { useParams, Link } from 'react-router-dom';
import { 
  Compass, 
  ArrowLeft, 
  Play, 
  ShieldCheck, 
  Award,
  BookOpen
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import AdSenseUnit from '../components/AdSenseUnit';

interface ModeData {
  id: string;
  name: string;
  path: string;
  entity_type: string;
  entity_count: number;
  question_limit: number;
  guess_limit: number;
  description: string;
  strategy_tips: string[];
  data_sources: string[];
}

const STATIC_MODES: Record<string, ModeData> = {
  countrydle: {
    id: 'countrydle',
    name: 'Countrydle — World Countries',
    path: '/game',
    entity_type: 'Sovereign Nations & UN States',
    entity_count: 195,
    question_limit: 10,
    guess_limit: 3,
    description: 'Deduce one of 195 sovereign nations across all seven continents using natural-language questions and deductive elimination.',
    strategy_tips: [
      'Hemisphere Triangulation: Always begin by verifying if the mystery nation lies in the Northern or Southern Hemisphere, and Eastern or Western of the Prime Meridian. This immediately reduces the world into quadrants.',
      'Maritime & Coastline Filter: Inquire whether the nation has access to the open ocean or sea. Over 44 nations worldwide are completely landlocked.',
      'Demographic & Population Thresholds: Use questions like "Is the population greater than 20 million?" to isolate populous powerhouses from microstates.',
      'Shared Border Anchors: Ask whether it borders a regional anchor nation (e.g. "Does it border Brazil?" in South America, or "Does it border Germany?" in Europe).',
      'Flag Visual Attributes: National flags provide definitive confirmation clues: star emblems, cross patterns, stripes, and primary background colors.'
    ],
    data_sources: ['Natural Earth (Boundary Vectors)', 'CIA World Factbook (Maritime Coastlines)', 'REST Countries API', 'OpenStreetMap']
  },
  'us-states': {
    id: 'us-states',
    name: 'US Statedle — 50 American States',
    path: '/us-states',
    entity_type: 'US States',
    entity_count: 50,
    question_limit: 8,
    guess_limit: 3,
    description: 'Identify the mystery American state using geographic regions, coastline access, historical admission order, and demographics.',
    strategy_tips: [
      'US Census Region Division: Query whether the state is located in the West, Midwest, South, or Northeast.',
      'Ocean & Gulf Coastlines: Confirm whether the state borders the Atlantic Ocean, Pacific Ocean, Gulf of Mexico, or Great Lakes.',
      'The Mississippi River Divide: Asking if the state is located west or east of the Mississippi River cleanly bisects the country.',
      'Statehood & Colonial History: Inquire if the state was one of the original 13 colonies, admitted before 1800, or joined during 19th-century westward expansion.',
      'Mountain Ranges & Interstate Highways: Major ranges (Rocky Mountains, Appalachian Mountains, Sierra Nevada) provide high-confidence signals.'
    ],
    data_sources: ['US Census Bureau (Demographics & Divisions)', 'US Geological Survey (USGS)', 'Natural Earth']
  },
  wojewodztwa: {
    id: 'wojewodztwa',
    name: 'Województwodle — 16 Polish Voivodeships',
    path: '/wojewodztwa',
    entity_type: 'Polish Voivodeships (Województwa)',
    entity_count: 16,
    question_limit: 5,
    guess_limit: 2,
    description: 'Master Poland\'s 16 administrative regions through spatial bounds, Baltic access, macroregions, and international borders.',
    strategy_tips: [
      'Baltic Sea Access: Testing for maritime access immediately identifies or eliminates the 3 northern coastal voivodeships (Pomorskie, Zachodniopomorskie, Warmińsko-Mazurskie).',
      'International Border Neighbors: Ask whether the voivodeship borders Germany (west), the Czech Republic/Slovakia (south), or Ukraine/Belarus/Lithuania/Russia (east/northeast).',
      'Macroregion Quadrants: Inquire whether it belongs to the southern macroregion (Małopolska, Śląsk), central belt (Mazowsze, Łódzkie), or western Poland.',
      'Major River Basins: The Vistula (Wisła) and Oder (Odra) river basins divide the administrative landscape of Poland.'
    ],
    data_sources: ['Główny Urząd Statystyczny (GUS)', 'Państwowy Rejestr Granic (PRG)']
  },
  powiaty: {
    id: 'powiaty',
    name: 'Powiatdle — 380 Polish Counties',
    path: '/powiaty',
    entity_type: 'Polish Counties (Powiaty)',
    entity_count: 380,
    question_limit: 15,
    guess_limit: 3,
    description: 'The ultimate test of Polish local geography across 380 counties, tested via vehicle registration plates, rivers, and expressways.',
    strategy_tips: [
      'Parent Voivodeship First: Always identify the containing voivodeship early to shrink candidate space from 380 down to 12–36.',
      'County Status: Differentiate between a city with county rights (miasto na prawach powiatu) and a land county (powiat ziemski).',
      'Territorial Vehicle Registration Codes: Letters (e.g. KR, WZ, PO, DW, GD) directly isolate individual administrative units.',
      'Expressway & Motorway Networks: Proximity to major corridors (A1, A2, A4 motorways; S7, S8 expressways) helps pinpoint spatial coordinates.'
    ],
    data_sources: ['GUS TERYT Registry', 'Generalna Dyrekcja Dróg Krajowych i Autostrad (GDDKiA)']
  }
};

export default function ModeGuidePage() {
  const { modeId } = useParams<{ modeId: string }>();
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const normalizedId = modeId === 'us_statedle' ? 'us-states' : (modeId || 'countrydle');
  const mode = STATIC_MODES[normalizedId] || STATIC_MODES.countrydle;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-5 sm:px-6 md:space-y-12 md:py-12">
      {/* Back button */}
      <div>
        <Link
          to="/explore"
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-zinc-400 hover:text-sand-100 transition-colors"
        >
          <ArrowLeft size={14} />
          <span>{isPl ? 'Powrót do przewodnika' : 'Back to Geography Explorer'}</span>
        </Link>
      </div>

      {/* Header */}
      <header className="border-b border-white/10 pb-8">
        <div className="mb-3 flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400">
          <BookOpen size={14} />
          <span>{isPl ? 'Oficjalny przewodnik dedukcyjny' : 'Official Mode Deduction Guide'}</span>
        </div>
        <h1 className="font-serif text-3xl font-bold tracking-tight text-sand-100 sm:text-5xl">
          {mode.name}
        </h1>
        <p className="mt-4 text-base leading-7 text-zinc-300 max-w-2xl">
          {mode.description}
        </p>

        {/* Quick Stats Grid */}
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-md border border-white/10 bg-obsidian-900/60 p-4">
            <span className="block text-[11px] uppercase tracking-wider text-zinc-500 font-mono">
              {isPl ? 'Podmiotów w puli' : 'Total Entities'}
            </span>
            <span className="mt-1 block font-mono text-2xl font-bold text-sand-100">
              {mode.entity_count}
            </span>
            <span className="text-[11px] text-zinc-400">{mode.entity_type}</span>
          </div>

          <div className="rounded-md border border-white/10 bg-obsidian-900/60 p-4">
            <span className="block text-[11px] uppercase tracking-wider text-zinc-500 font-mono">
              {isPl ? 'Budżet pytań' : 'Question Limit'}
            </span>
            <span className="mt-1 block font-mono text-2xl font-bold text-emerald-400">
              {mode.question_limit}
            </span>
            <span className="text-[11px] text-zinc-400">{isPl ? 'Pytań tak/nie' : 'Yes/no queries'}</span>
          </div>

          <div className="rounded-md border border-white/10 bg-obsidian-900/60 p-4">
            <span className="block text-[11px] uppercase tracking-wider text-zinc-500 font-mono">
              {isPl ? 'Próby odgadnięcia' : 'Guess Limit'}
            </span>
            <span className="mt-1 block font-mono text-2xl font-bold text-amber-400">
              {mode.guess_limit}
            </span>
            <span className="text-[11px] text-zinc-400">{isPl ? 'Próby zgadnięcia' : 'Final guesses'}</span>
          </div>

          <div className="rounded-md border border-white/10 bg-obsidian-900/60 p-4">
            <span className="block text-[11px] uppercase tracking-wider text-zinc-500 font-mono">
              {isPl ? 'Rotacja zagadki' : 'Daily Rotation'}
            </span>
            <span className="mt-1 block font-mono text-2xl font-bold text-sand-100">
              00:00
            </span>
            <span className="text-[11px] text-zinc-400">UTC Daily Midnight</span>
          </div>
        </div>
      </header>

      {/* Strategic Gameplay Walkthrough */}
      <section className="space-y-6">
        <h2 className="flex items-center gap-2.5 font-serif text-2xl font-semibold text-sand-100">
          <Compass size={22} className="text-emerald-400" />
          <span>{isPl ? 'Optymalna strategia dedukcyjna' : 'Optimal Deduction Strategy & Methodology'}</span>
        </h2>
        <p className="text-sm leading-7 text-zinc-300">
          {isPl
            ? 'Aby osiągnąć maksymalną liczbę punktów (do 3300+ pkt), gracze powinni minimalizować liczbę zadanych pytań poprzez binarne dzielenie przestrzeni poszukiwań. Poniższe kroki prezentują sprawdzoną metodologię:'
            : 'To achieve peak scoring efficiency (up to 3,300+ points), deduce the target using binary space partitioning. Each question should ideally eliminate 50% or more of remaining candidates:'}
        </p>

        <div className="space-y-4">
          {mode.strategy_tips.map((tip, idx) => (
            <div key={idx} className="flex items-start gap-4 rounded-md border border-white/10 bg-obsidian-900 p-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 font-mono text-xs font-bold text-emerald-400 border border-emerald-500/20">
                {idx + 1}
              </span>
              <p className="text-sm leading-6 text-zinc-300 pt-0.5">
                {tip}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Scoring Architecture */}
      <section className="rounded-md border border-white/10 bg-obsidian-900/70 p-6 sm:p-8 space-y-5">
        <h2 className="flex items-center gap-2 font-serif text-xl font-semibold text-sand-100">
          <Award size={20} className="text-amber-400" />
          <span>{isPl ? 'Model punktacji Countrydle' : 'Countrydle 5-Factor Scoring System'}</span>
        </h2>
        <p className="text-xs leading-6 text-zinc-300">
          {isPl
            ? 'Punkty są przyznawane w oparciu o precyzję, szybkość i odwagę dedukcji:'
            : 'Scores are computed transparently across five performance metrics upon solving the puzzle:'}
        </p>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-zinc-300">
          <li className="flex items-center gap-2 border-l-2 border-emerald-500 pl-3 py-1">
            <strong>Base Win:</strong> +500 pts guaranteed for a correct deduction.
          </li>
          <li className="flex items-center gap-2 border-l-2 border-emerald-500 pl-3 py-1">
            <strong>Question Efficiency:</strong> Up to +1,500 pts for using fewer questions.
          </li>
          <li className="flex items-center gap-2 border-l-2 border-amber-500 pl-3 py-1">
            <strong>Guess Precision:</strong> +500 pts for 1st-try guess accuracy.
          </li>
          <li className="flex items-center gap-2 border-l-2 border-blue-500 pl-3 py-1">
            <strong>Speed Bonus:</strong> Up to +300 pts decaying over 5 minutes.
          </li>
        </ul>
      </section>

      {/* Data Provenance & Authoritative Sources */}
      <section className="border-t border-white/10 pt-8 space-y-4">
        <h2 className="flex items-center gap-2 font-serif text-xl font-semibold text-sand-100">
          <ShieldCheck size={20} className="text-emerald-400" />
          <span>{isPl ? 'Źródła danych i weryfikacja faktów' : 'Verified Data Provenance & Ground Truth'}</span>
        </h2>
        <p className="text-sm leading-6 text-zinc-400">
          {isPl
            ? 'Wszystkie odpowiedzi w Countrydle są ewaluowane deterministycznie na lokalnych relacyjnych bazach SQLite bez generatywnych halucynacji AI. Dane geograficzne pochodzą z publicznych instytucji:'
            : 'All question evaluations execute deterministically against curated relational SQLite tables with zero LLM hallucination. Geographic facts are compiled from official institutions:'}
        </p>
        <div className="flex flex-wrap gap-2 pt-2">
          {mode.data_sources.map((source, i) => (
            <span
              key={i}
              className="rounded-sm border border-white/15 bg-white/5 px-3 py-1 text-xs text-zinc-300 font-mono"
            >
              {source}
            </span>
          ))}
        </div>
      </section>

      {/* Compliant Ad Placement */}
      <AdSenseUnit slot="mode-guide-footer" className="max-w-xl mx-auto" />

      {/* CTA Section */}
      <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-5 text-center space-y-4 sm:p-8">
        <h3 className="font-serif text-2xl font-bold text-sand-100">
          {isPl ? 'Gotowy do podjęcia dzisiejszego wyzwania?' : 'Ready to Test Your Geography Skills?'}
        </h3>
        <p className="text-sm text-zinc-400 max-w-md mx-auto">
          {isPl
            ? 'Dzisiejsza zagadka czeka. Sprawdź, czy potrafisz odgadnąć lokalizację przed upływem limitu pytań.'
            : 'Today’s secret puzzle is live. Apply these deduction strategies to solve the mystery location.'}
        </p>
        <div className="pt-2">
          <Link
            to={mode.path}
            className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-emerald-400 px-6 py-3 text-sm font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors shadow-lg"
          >
            <Play size={16} />
            <span>{isPl ? `Zagraj w ${mode.name}` : `Play ${mode.name}`}</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
