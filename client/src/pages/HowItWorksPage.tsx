import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Cpu, Database, GitBranch, Search, Zap } from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';
import { cn } from '../lib/utils';

const PIPELINE_STEPS = [
  {
    title: 'Supported templates',
    icon: Zap,
    description: 'Strict English Countrydle templates recognize supported whole-question forms, including borders, hemispheres, landlocked status, and population or area thresholds. A matched template produces a structured plan without calling the AI planner. Other modes have their own template coverage; not every language or paraphrase takes this route.',
    limitation: 'A template is a wording rule, not independent fact verification. Extra clauses, unsupported units or ambiguous wording may need the planner instead.',
  },
  {
    title: 'Interpretation cache and AI planning',
    icon: Cpu,
    description: 'If no template applies, the engine can reuse an interpretation cached for its current planning contract or ask an AI planner to interpret the question. A local plan describes a fact, reference entity and operation; it does not itself establish whether the answer is yes or no.',
    limitation: 'The planner can misunderstand negation, a reference location or a time period. Reusing an interpretation avoids another planning request, but does not prove that interpretation correct.',
  },
  {
    title: 'Local fact evaluation',
    icon: Database,
    description: 'Supported plans are evaluated against local SQLite fact tables. Operations compare values, check list membership, combine predicates and compare coordinates. A border question reads recorded neighbors; a population threshold compares the stored population with the requested number.',
    limitation: 'Execution is deterministic for the same plan and stored facts. Sources can still be incomplete or outdated, and game conventions can differ from what a player intended.',
  },
  {
    title: 'Retrieval and AI fallback',
    icon: Search,
    description: 'Valid questions outside local coverage can use target-filtered retrieval from indexed article fragments and an AI answer stage. The fallback can reuse an answer only when its target, question, model, date and freshly retrieved evidence match the cache requirements. When retrieved text is irrelevant, the answer stage may use general knowledge.',
    limitation: 'Retrieved text is not a human review and does not guarantee a supporting citation. AI fallback can make mistakes or be unable to resolve the question. Missing local facts are not evidence that the answer is no.',
  },
  {
    title: 'Resolved answers and corrections',
    icon: GitBranch,
    description: 'An accepted yes or no answer enters question history and spends one question in modes with a question budget. Invalid, undetermined and failed requests do not spend a question. Explanations help you understand an answer; question reports and the Contact page provide a route to request corrections.',
    limitation: 'An explanation or internal evidence label is not a certification of accuracy. Check a reliable source when the distinction matters, and send the exact question and explanation when reporting a problem.',
  },
];

const EXAMPLES = [
  {
    id: 'borders',
    question: 'Does it border Germany?',
    target: 'Poland',
    route: 'Supported English template → local border relation',
    operation: 'contains(borders_country, Germany)',
    result: 'Yes: Poland shares a land border with Germany.',
    lesson: 'A named land-border test is more precise than asking whether two countries are nearby. The result relies on the recorded border relation, including the catalog’s territory conventions.',
  },
  {
    id: 'landlocked',
    question: 'Is it landlocked?',
    target: 'Kosovo',
    route: 'Supported English template → local marine-access relation',
    operation: 'not(exists(marine_access))',
    result: 'Yes: Kosovo has no sea or ocean coastline.',
    lesson: 'The country engine distinguishes marine access from water-access entries for inland seas. A river that drains to a sea does not give a country coastline access.',
  },
  {
    id: 'hemisphere',
    question: 'Is it in the Eastern Hemisphere?',
    target: 'France',
    route: 'Supported English template → stored hemisphere association',
    operation: 'contains(hemisphere, Eastern)',
    result: 'Yes under the stored classification. France also has a Western Hemisphere association.',
    lesson: 'Hemisphere categories can overlap. The bounding-box enrichment uses a mainland France override, so do not read this as an exhaustive classification of every overseas territory or expect a hemisphere question to halve the candidates.',
  },
  {
    id: 'fallback',
    question: 'Did this country win the 1998 FIFA World Cup?',
    target: 'France',
    route: 'Outside the local geography relations → retrieval and AI fallback',
    operation: 'Retrieve target-related article fragments, then interpret the historical question',
    result: 'The historical answer is yes; this example does not represent a recorded gameplay response or a live provider call.',
    lesson: 'A question can be factual and valid without being covered by a local relation. Retrieval may lack the relevant passage; AI generation remains fallible and can return an undetermined answer.',
  },
];

const MODE_BUDGETS = [
  ['Countrydle', 'countrydle', '10', '3'],
  ['Flagdle', 'flagdle', 'No total helper-question budget', '12'],
  ['Europedle', 'europe', '8', '3'],
  ['Asiadle', 'asia', '8', '3'],
  ['Africadle', 'africa', '8', '3'],
  ['Americadle', 'americas', '8', '3'],
  ['US Statedle', 'us-states', '8', '3'],
  ['Województwodle', 'wojewodztwa', '5', '2'],
  ['Powiatdle', 'powiaty', '15', '3'],
];

export default function HowItWorksPage() {
  const [exampleId, setExampleId] = useState(EXAMPLES[0].id);
  const example = EXAMPLES.find(item => item.id === exampleId) || EXAMPLES[0];

  return (
    <div className="mx-auto max-w-5xl space-y-10 bg-obsidian-950 pb-8 text-zinc-300">
      <header className="border-b border-white/10 pb-8">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">Templates, local facts and AI fallback</p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">How Countrydle Answers Questions</h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-zinc-400">Countrydle uses a hybrid answer engine, not an infallible geography oracle. Some questions use deterministic templates and local facts; others need AI interpretation or fallback. Both paths can produce incorrect answers.</p>
      </header>

      <section aria-labelledby="answer-pipeline" className="space-y-6">
        <h2 id="answer-pipeline" className="font-serif text-2xl text-sand-100">From your question to an answer</h2>
        <p className="text-base leading-7">These stages describe the question-based daily games. Flagdle has optional helper questions alongside its visual challenge. Friend duels are different: players answer each other’s questions rather than using this engine to judge their opponent’s secret location.</p>
        <ol className="space-y-4">
          {PIPELINE_STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <li key={step.title} className="rounded-sm border border-white/10 bg-obsidian-900 p-5 sm:p-6">
                <h3 className="flex items-center gap-3 text-lg font-semibold text-sand-100"><Icon size={20} aria-hidden="true" className="text-emerald-400" />{index + 1}. {step.title}</h3>
                <p className="mt-3 text-base leading-7">{step.description}</p>
                <p className="mt-3 text-sm leading-6 text-zinc-400"><strong className="text-sand-100">Limit:</strong> {step.limitation}</p>
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="worked-examples" className="space-y-5">
        <h2 id="worked-examples" className="font-serif text-2xl text-sand-100">Worked examples, not live game evidence</h2>
        <p className="text-base leading-7">The named targets below are illustrative teaching examples, not today’s answer. Operation notation is schematic, not a request payload or SQL trace. We do not publish invented response timings, routing percentages or accuracy rates; response time depends on the route, services and network.</p>
        <div role="group" aria-label="Choose an answer example" className="flex flex-wrap gap-2">
          {EXAMPLES.map(item => (
            <button key={item.id} type="button" aria-pressed={item.id === exampleId} onClick={() => setExampleId(item.id)} className={cn('rounded-sm border px-4 py-3 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400', item.id === exampleId ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300' : 'border-white/10 text-zinc-400 hover:text-sand-100')}>
              {item.question}
            </button>
          ))}
        </div>
        <div className="rounded-sm border border-white/10 bg-obsidian-900 p-5 sm:p-6">
          <h3 className="text-lg font-semibold text-sand-100">{example.question}</h3>
          <dl className="mt-4 space-y-3 text-base leading-7">
            <div><dt className="text-sm text-zinc-400">Example target</dt><dd>{example.target}</dd></div>
            <div><dt className="text-sm text-zinc-400">Route</dt><dd>{example.route}</dd></div>
            <div><dt className="text-sm text-zinc-400">Operation</dt><dd className="break-words font-mono text-sm text-emerald-300">{example.operation}</dd></div>
            <div><dt className="text-sm text-zinc-400">Illustrative result</dt><dd>{example.result}</dd></div>
          </dl>
          <p className="mt-5 border-t border-white/10 pt-4 text-base leading-7">{example.lesson}</p>
        </div>
      </section>

      <section aria-labelledby="data-limits" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="data-limits" className="font-serif text-2xl text-sand-100">What the facts do—and do not—represent</h2>
        <p className="text-base leading-7">Country facts combine REST Countries, CIA World Factbook profiles distributed through factbook.json, and curated additions. US and Polish regional facts combine local article text and infoboxes, classification tables, static lists and manual corrections. Some relationships are extracted from Wikipedia text using AI. They are not all direct government feeds.</p>
        <p className="text-base leading-7">Map boundaries and Natural Earth-derived globe data are separate from the answer tables. Seeing a boundary on the globe does not establish eligibility, a recorded border, or the answer to an ambiguous question. Population values are stored snapshots, not live counters; specify thresholds and units, and use square kilometres for area questions.</p>
        <p className="text-base leading-7">Ask about current membership separately from historical membership. Official language status is not the same as the most widely spoken language. Coordinate comparisons use stored reference coordinates, not a test of whether every point of one country lies east or north of another.</p>
        <p className="text-base leading-7">See the <Link to="/about" className="text-emerald-300 underline underline-offset-4">source inventory</Link> and the <Link to="/explore/modes/countrydle" className="text-emerald-300 underline underline-offset-4">country, continent and water-access conventions</Link> for practical distinctions.</p>
      </section>

      <section aria-labelledby="mode-budgets" className="space-y-4">
        <h2 id="mode-budgets" className="font-serif text-2xl text-sand-100">Nine daily modes and separate friend duels</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm leading-6">
            <caption className="mb-3 text-left text-zinc-400">Daily puzzles rotate at midnight UTC. Question and guess budgets are separate.</caption>
            <thead className="border-b border-white/10 text-sand-100"><tr><th scope="col" className="py-3 pr-4">Mode</th><th scope="col" className="py-3 pr-4">Questions</th><th scope="col" className="py-3">Guesses</th></tr></thead>
            <tbody>{MODE_BUDGETS.map(([name, id, questions, guesses]) => <tr key={id} className="border-b border-white/10"><th scope="row" className="py-3 pr-4 font-normal"><Link to={`/explore/modes/${id}`} className="text-emerald-300 underline underline-offset-4">{name}</Link></th><td className="py-3 pr-4">{questions}</td><td className="py-3">{guesses}</td></tr>)}</tbody>
          </table>
        </div>
        <p className="text-base leading-7">In question-budget games, running out of questions still leaves your remaining guesses. A yes to an identity question is not a win until you submit the guess. Flagdle’s helper questions do not spend guesses, and request-rate limits still apply. Friend duels have no total question or guess cap; each action spends a turn, with timers and a final-guess reply rule.</p>
      </section>

      <section aria-labelledby="report-answer" className="space-y-4 border-t border-white/10 pt-8">
        <h2 id="report-answer" className="font-serif text-2xl text-sand-100">Help correct a questionable answer</h2>
        <p className="text-base leading-7">Include the mode, puzzle date, exact question, returned answer and explanation, and a source supporting the correction. Use the question-report control where available or <Link to="/contact" className="text-emerald-300 underline underline-offset-4">contact us</Link>. Avoid sharing today’s hidden target publicly. Reports request a review; they do not mean a fact was already checked or changed.</p>
        <Link to="/faq" className="inline-block text-emerald-300 underline underline-offset-4">Read gameplay and account help</Link>
      </section>
      <AdSenseUnit slot="how-it-works-footer" className="mx-auto max-w-2xl pt-6" />
    </div>
  );
}
