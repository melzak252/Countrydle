import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, Compass, Play } from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';

interface ModeData {
  name: string;
  path: string;
  pool: string;
  questions: string;
  guesses: number;
  description: string;
  tips: string[];
  example: { title: string; steps: string[]; lesson: string };
}

const CONTINENTAL_MODES: Record<string, ModeData> = {
  europe: {
    name: 'Europedle — Europe', path: '/europe', pool: 'Eligible Europe-associated countries', questions: '8', guesses: 3,
    description: 'Identify a country from the European game pool. Stored physical-continent associations and game eligibility, not every possible cultural definition of Europe, determine the candidates.',
    tips: ['Start with a distinction inside Europe rather than asking whether the target is in Europe again.', 'Use a named neighbor, island status or marine access to separate nearby candidates.', 'Europedle excludes Azerbaijan, Kazakhstan and Georgia, as well as the global exclusion of Israel. These exclusions do not remove the countries from factual geography tables.'],
    example: {
      title: 'Kosovo: eligibility is not UN membership',
      steps: ['Kosovo is included in the Europe pool, despite its partial international recognition.', 'For this illustrative target, "Is it landlocked?" is yes; rivers draining toward a sea do not create coastal access.', '"Does it border Albania?" is yes. Combine this with other clues rather than treating one shared neighbor as a unique identification.'],
      lesson: 'Do not eliminate Kosovo just because it is not a UN member. Submit an eligible country from the suggestions when you are ready to guess.',
    },
  },
  asia: {
    name: 'Asiadle — Asia', path: '/asia', pool: 'Eligible Asia-associated countries', questions: '8', guesses: 3,
    description: 'Use borders, regional classifications and water access within the Asian game pool. A country may have more than one stored physical-continent association.',
    tips: ['Asiadle excludes Egypt and the globally excluded Israel; do not assume every country with territory in Asia is a valid guess.', 'Name the sea or ocean you mean. An inland-sea coastline is not the same as access to the open sea.', 'Use a precise population or area threshold rather than an undefined category such as a large country. Stored values may be dated.'],
    example: {
      title: 'Azerbaijan: pool membership and marine access',
      steps: ['Azerbaijan is excluded by the Europe eligibility rule, but is not excluded by the Asia rule.', 'A recorded Caspian Sea water-access relationship does not make it non-landlocked: the country engine excludes the Caspian Sea from marine access.', 'Ask "Does it have access to the Caspian Sea?" separately from "Is it landlocked?"; these predicates need not be opposites.'],
      lesson: 'A continent answer describes stored geography; an eligible guess additionally has to satisfy this mode’s game policy.',
    },
  },
  africa: {
    name: 'Africadle — Africa', path: '/africa', pool: 'Eligible Africa-associated countries', questions: '8', guesses: 3,
    description: 'Deduce a country in the African game pool using regional categories, borders and coastlines without spending questions on facts already implied by the mode.',
    tips: ['Distinguish Northern, Eastern, Western, Middle or Southern Africa using the stored regional classifications; "South Africa" names a country, not the whole Southern Africa region.', 'Named land borders are more precise than asking whether a target is close to another country.', 'A country crossing the equator can have both Northern and Southern Hemisphere associations. Hemisphere questions do not guarantee equal splits.'],
    example: {
      title: 'Egypt: different continental pools',
      steps: ['The Asia rule explicitly excludes Egypt; the Africa rule does not.', 'For an Egypt example, a Mediterranean coastline clue and a Red Sea coastline clue describe different named waters, not a single generic ocean boolean.', 'The country engine does not automatically infer a direct ocean coastline from a coast on a connected sea. Ask for the named water body you intend.'],
      lesson: 'Keep eligibility, physical geography and the wording of a water question separate; they answer different things.',
    },
  },
  americas: {
    name: 'Americadle — The Americas', path: '/americas', pool: 'Eligible North- or South-America-associated countries', questions: '8', guesses: 3,
    description: 'Play one combined pool covering North America and South America, including eligible Central American and Caribbean countries through their stored continent associations.',
    tips: ['An unqualified country question about America or the Americas covers North America OR South America. Specify North or South when that is your intended distinction.', 'Do not confuse a country’s broad region field, such as Americas, with its physical-continent associations.', 'Use island status and named neighbors together: sharing an island does not prevent a country from having a land border.'],
    example: {
      title: 'A border through French Guiana',
      steps: ['The country fact builder maps the French Guiana border code to France rather than treating the territory as an independent country neighbor.', 'A Brazil–France border clue therefore need not refer to metropolitan France.', 'That border convention does not itself add France to Americadle: the pool is selected from stored continent associations and eligibility rules.'],
      lesson: 'A territory’s presence on a map, a normalized country-border relation and a playable candidate are three separate concepts.',
    },
  },
};

const MODES: Record<string, ModeData> = {
  countrydle: {
    name: 'Countrydle — World Countries', path: '/game', pool: '195 playable countries', questions: '10', guesses: 3,
    description: 'Deduce a country from the game’s worldwide catalog. The catalog is not a list of only UN member states and does not make a claim about every disputed territory’s sovereignty.',
    tips: ['Choose questions that distinguish your remaining candidates. Northern/Southern and Eastern/Western Hemisphere categories can overlap and are not balanced halves.', 'Separate a named coastline from landlocked status. Inland-sea access is not open-sea-connected marine access.', 'Use named neighbors and explicit numeric thresholds. For area, the stored unit is square kilometres.', 'A yes to "Is it Poland?" uses a question and does not finish the puzzle. Submit Poland in the guess field to win.'],
    example: {
      title: 'Poland: combine two concrete relations',
      steps: ['For the illustrative target Poland, "Does it border Germany?" is yes. That clue alone does not identify a unique country.', '"Is it landlocked?" is no because Poland has Baltic Sea coastline.', 'A Baltic Sea clue describes that sea, not direct Atlantic Ocean coastline. Once your other clues isolate Poland, submit a guess instead of another identity question.'],
      lesson: 'Each resolved yes or no uses one question. Invalid or undetermined requests do not use a question, and remaining guesses can still be used after the question budget is exhausted.',
    },
  },
  flagdle: {
    name: 'Flagdle — Daily Flag Reveal', path: '/flagdle', pool: 'Flags from the playable country catalog', questions: 'No total helper-question budget', guesses: 12,
    description: 'Identify a country from a progressively revealed flag. Each guess advances the reveal; optional yes/no helper questions do not spend guesses, although request-rate limits still apply.',
    tips: ['A hidden part of the flag is not evidence that a color or symbol is absent.', 'Read feedback about colors and symbols together with the revealed image. Shared attributes do not imply the same flag.', 'Use specific helper questions about stars, stripes or colors instead of treating a single color as a unique identifier.'],
    example: {
      title: 'Kosovo: a partially visible symbol',
      steps: ['The Kosovo seed records a blue field, a gold country silhouette and six white stars.', 'A reveal showing only blue does not yet distinguish Kosovo from other blue-containing flags.', 'A precise question about stars or a country silhouette can help; the result is still generated by the answer system and can be mistaken. Submit the country name as a guess when ready.'],
      lesson: 'Flagdle has its own scoring formula and no question-efficiency component. Helper questions are not extra country guesses.',
    },
  },
  ...CONTINENTAL_MODES,
  'us-states': {
    name: 'US Statedle — 50 States', path: '/us-states', pool: '50 US states', questions: '8', guesses: 3,
    description: 'Find one of the 50 states using stored Census-region classifications, neighbors, water access and statehood facts. Washington, DC and US territories are not additional states in this pool.',
    tips: ['Use the stored Northeast, Midwest, South or West classification; Northeast is not identical to New England or Mid-Atlantic.', 'Broad Atlantic access includes Gulf of Mexico coastline. Direct Atlantic coastline, Gulf coastline and the East Coast label are distinct predicates.', 'Great Lakes water access is recorded by named lake; it does not establish an ocean coastline.', 'Avoid assuming that an east/west or river question bisects the state pool equally.'],
    example: {
      title: 'A Gulf-only state: broad access versus direct coastline',
      steps: ['Consider an illustrative state whose recorded water access includes Gulf of Mexico but not Atlantic Ocean.', '"Does it have access to the Atlantic Ocean?" can be yes under the broad-access rule via the Gulf.', '"Does it directly border the Atlantic Ocean?" is no for those records. The Gulf entry does not automatically assign the East Coast label.'],
      lesson: 'This example describes the evaluator’s recorded-data rule, not a live response. Add "directly" when you mean literal coastline rather than broad connected access.',
    },
  },
  wojewodztwa: {
    name: 'Województwodle — 16 Voivodeships', path: '/wojewodztwa', pool: '16 Polish voivodeships', questions: '5', guesses: 2,
    description: 'Identify a Polish administrative region with a small question budget. Internal neighbors, international borders, regional labels and named rivers are different stored relationships.',
    tips: ['The base builder records Baltic Sea access for Pomorskie and Zachodniopomorskie. It does not record Warmińsko-Mazurskie as a third Baltic-access region; lagoon access is not a reason to assume the same answer.', 'Distinguish a border with another voivodeship from a border with a foreign country.', 'A regional label is a stored classification, not necessarily an official statistical macroregion.', 'A river crossing a region is different from the region having maritime access.'],
    example: {
      title: 'Separating the two base Baltic-access entries',
      steps: ['A yes to a Baltic Sea access question leaves Pomorskie and Zachodniopomorskie in the base water-access list.', 'The international-border list records Germany for Zachodniopomorskie but not Pomorskie.', 'For the illustrative target Zachodniopomorskie, a Germany-border clue separates those two candidates. Do not infer that every northern voivodeship has Baltic access.'],
      lesson: 'These examples reflect the repository’s base classification tables. Data corrections can change records; report a mismatch with a source rather than assuming an unsupported third entry.',
    },
  },
  powiaty: {
    name: 'Powiatdle — 380 Counties', path: '/powiaty', pool: '380 Polish counties', questions: '15', guesses: 3,
    description: 'Find a Polish county using its parent voivodeship, city-county status, registration identifiers and recorded geographic relationships.',
    tips: ['Identify a likely parent voivodeship before relying on a town name that may also name a neighboring county.', 'A city with county rights and the surrounding land county are separate administrative entities, even when their names or seats are similar.', 'Registration-code, road and river questions depend on the stored entries. A road near a county is not necessarily a road recorded as crossing it.', 'County-border lists and international-border lists are different relations. Name the kind of neighbor you mean.'],
    example: {
      title: 'Kraków and powiat krakowski are not the same candidate',
      steps: ['The county-border snapshot contains separate Kraków (1261) and powiat krakowski (1206) entries, and records a border between them.', 'The fact builder reads city-county status from the article text into is_city_county. A city-county question tests that stored flag, not whether a county has Kraków as a seat or contains a large city.', 'A border with powiat krakowski can therefore help identify the city county of Kraków rather than the land county itself. Use the full candidate from the suggestions; the shared place name alone is not a unique administrative identifier.'],
      lesson: 'Administrative status is a direct recorded classification, not a conclusion based on population size or whether the county contains a city.',
    },
  },
};

export default function ModeGuidePage() {
  const { modeId } = useParams<{ modeId: string }>();
  const normalizedId = modeId === 'us_statedle' ? 'us-states' : modeId;
  const mode = normalizedId ? MODES[normalizedId] : undefined;

  if (!mode) {
    return (
      <div className="mx-auto max-w-4xl space-y-5 py-8">
        <h1 className="font-serif text-4xl text-sand-100">Mode guide not found</h1>
        <p className="text-base leading-7 text-zinc-400">This address does not match an available daily-mode guide.</p>
        <Link to="/explore" className="text-emerald-300 underline underline-offset-4">Return to Geography Explorer</Link>
      </div>
    );
  }

  const isCountryMode = normalizedId === 'countrydle' || normalizedId === 'flagdle' || (normalizedId !== undefined && normalizedId in CONTINENTAL_MODES);

  return (
    <div className="mx-auto max-w-4xl space-y-8 py-5 text-zinc-300 md:space-y-10 md:py-10">
      <Link to="/explore" className="inline-flex items-center gap-2 text-sm text-emerald-300 underline underline-offset-4"><ArrowLeft size={16} aria-hidden="true" />Back to Geography Explorer</Link>
      <header className="border-b border-white/10 pb-8">
        <p className="mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400"><BookOpen size={14} aria-hidden="true" />Mode deduction guide</p>
        <h1 className="font-serif text-4xl leading-tight text-sand-100 sm:text-5xl">{mode.name}</h1>
        <p className="mt-4 text-base leading-7">{mode.description}</p>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4"><dt className="text-zinc-400">Candidate pool</dt><dd className="mt-2 text-sand-100">{mode.pool}</dd></div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4"><dt className="text-zinc-400">Questions</dt><dd className="mt-2 text-emerald-300">{mode.questions}</dd></div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4"><dt className="text-zinc-400">Guesses</dt><dd className="mt-2 text-sand-100">{mode.guesses}</dd></div>
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4"><dt className="text-zinc-400">Daily reset</dt><dd className="mt-2 text-sand-100">00:00 UTC</dd></div>
        </dl>
      </header>

      <nav aria-label="Daily mode guides" className="flex flex-wrap gap-x-5 gap-y-3 text-sm">
        {Object.entries(MODES).map(([id, item]) => <Link key={id} to={`/explore/modes/${id}`} aria-current={id === normalizedId ? 'page' : undefined} className="text-emerald-300 underline underline-offset-4">{item.name.split(' — ')[0]}</Link>)}
      </nav>

      <section aria-labelledby="mode-strategy" className="space-y-4">
        <h2 id="mode-strategy" className="flex items-center gap-2 font-serif text-2xl text-sand-100"><Compass size={22} aria-hidden="true" />Questions that make useful distinctions</h2>
        <p className="text-base leading-7">Choose a question for the candidates you actually have left. A balanced yes/no split can be useful, but neither answer is guaranteed to eliminate half the pool; overlapping categories and missing facts matter. Prefer explicit predicates to vague terms such as nearby or large.</p>
        <ol className="list-decimal space-y-4 pl-6 marker:text-emerald-400">{mode.tips.map(tip => <li key={tip} className="pl-2 text-base leading-7">{tip}</li>)}</ol>
      </section>

      <section aria-labelledby="mode-example" className="space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-5 sm:p-6">
        <h2 id="mode-example" className="font-serif text-2xl text-sand-100">Worked example: {mode.example.title}</h2>
        <p className="text-sm leading-6 text-zinc-400">Illustrative examples explain current fact and eligibility logic. They are not today’s hidden target, measured player results or recorded provider responses.</p>
        <ol className="list-decimal space-y-3 pl-6 marker:text-emerald-400">{mode.example.steps.map(step => <li key={step} className="pl-2 text-base leading-7">{step}</li>)}</ol>
        <p className="border-t border-white/10 pt-4 text-base leading-7">{mode.example.lesson}</p>
      </section>

      {isCountryMode && (
        <section aria-labelledby="country-conventions" className="space-y-5">
          <h2 id="country-conventions" className="font-serif text-2xl text-sand-100">Catalog, continent and disputed-region conventions</h2>
          <p className="text-base leading-7">The current worldwide pool has 195 playable countries. Kosovo is included; Israel is excluded from playable targets and guesses without removing its canonical geography or historical facts. This is a game eligibility policy, not a diplomatic recognition rule. Use the current game suggestions as the candidate list; dependencies and disputed regions shown on a map are not automatically separate guesses.</p>
          <p className="text-base leading-7">Continental candidates come from stored physical-continent associations and per-mode exclusions. Europedle additionally excludes Azerbaijan, Kazakhstan and Georgia; Asiadle additionally excludes Egypt. Americadle combines North America and South America. A country can have multiple associations, so membership in a continental pool is not proof that all of its territory lies there.</p>
          <p className="text-base leading-7">The country-border builder normalizes Western Sahara to Morocco, Gibraltar to the United Kingdom, and French Guiana to France. These simplified database conventions can differ from a map’s boundary labels or a geopolitical source. They do not settle sovereignty disputes or automatically change continental eligibility.</p>
          <p className="text-base leading-7">Hemisphere associations describe stored territorial bounds, with some mainland overrides. France, for example, has both Eastern and Western associations. Island status is a sourced classification rather than simply an absence of land borders: countries sharing an island can border each other, while Australia is treated as a continent.</p>
          <p className="text-base leading-7">Country water access can include inland seas, but landlocked status uses marine access and excludes the Caspian, Aral and Dead Seas. Named direct coastlines are distinct from access through connected seas; only configured parent-water relationships are expanded, not every connection in the world’s oceans. River drainage is not coastal access.</p>
        </section>
      )}

      <section aria-labelledby="mode-scoring" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="mode-scoring" className="font-serif text-2xl text-sand-100">Budgets and scoring</h2>
        <p className="text-base leading-7">{normalizedId === 'flagdle' ? 'Flagdle uses 12 guesses with unlimited optional helper questions. Its win score combines +500 base points, a guess bonus from +1,500 on the first guess to +50 on the twelfth, up to +300 speed points over 3 minutes, and up to +500 streak points. It has no question-efficiency bonus.' : 'Question-based daily wins use +500 base points, up to +1,500 for question efficiency, up to +500 for guess efficiency, up to +300 for speed over 5 minutes, and +50 per consecutive day solved in that mode up to +500. US Statedle adds +200 and Powiatdle adds +500. Guest scores are previews; saved account results determine streak bonuses. Running out of questions does not end the game while guesses remain.'}</p>
        <p className="text-base leading-7">Friend duels are separate from these nine daily modes. Players answer each other’s questions; there is no total question or guess cap, but each action takes a turn, timers apply, and the final reply after a starting-player solve permits a guess or pass, not another question.</p>
      </section>

      <section aria-labelledby="mode-sources" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="mode-sources" className="font-serif text-2xl text-sand-100">Sources, limits and corrections</h2>
        <p className="text-base leading-7">{isCountryMode ? 'Country facts combine REST Countries, CIA World Factbook profiles distributed through factbook.json, and curated additions. Some facts are extracted from Wikipedia text using AI.' : 'Regional facts use local article text and infoboxes, geographic classification tables, static lists and manual corrections. They are not exclusively direct official-statistics feeds.'} Map boundary assets and Natural Earth-derived globe data are separate from the answer tables.</p>
        <p className="text-base leading-7">Supported templates and local facts reduce dependence on AI-generated answers, but data and interpretation can be wrong or outdated. Questions outside local coverage may use retrieved article text or general knowledge through AI fallback. An explanation is not proof of human verification.</p>
        <p className="text-base leading-7">Read the <Link to="/about" className="text-emerald-300 underline underline-offset-4">source inventory</Link>, <Link to="/how-it-works" className="text-emerald-300 underline underline-offset-4">answer-engine explanation</Link> and <Link to="/faq" className="text-emerald-300 underline underline-offset-4">FAQ</Link>. To request a correction, <Link to="/contact" className="text-emerald-300 underline underline-offset-4">contact us</Link> with the mode, date, exact question, answer, explanation and supporting source. Avoid posting today’s target publicly.</p>
      </section>

      <Link to={mode.path} className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-emerald-400 px-5 py-3 font-semibold text-obsidian-950 hover:bg-emerald-300"><Play size={16} aria-hidden="true" />Play {mode.name.split(' — ')[0]}</Link>
      <AdSenseUnit slot="mode-guide-footer" className="mx-auto max-w-2xl pt-6" />
    </div>
  );
}
