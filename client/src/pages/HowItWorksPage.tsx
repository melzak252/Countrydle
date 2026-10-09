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
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [exampleId, setExampleId] = useState(EXAMPLES[0].id);

  return (
    <div className="mx-auto min-w-0 max-w-5xl space-y-8 break-words bg-obsidian-950 pb-8 text-zinc-300">
      <header className="border-b border-white/10 pb-6">
        <p className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">Templates, local facts and AI fallback</p>
        <h1 className="font-serif text-3xl leading-tight tracking-tight text-sand-100 sm:text-4xl">How Countrydle Answers Questions</h1>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-zinc-400">Countrydle uses a hybrid answer engine, not an infallible geography oracle. Some questions use deterministic templates and local facts; others need AI interpretation or fallback. Both paths can produce incorrect answers.</p>
      </header>

      <section aria-labelledby="answer-pipeline" className="min-w-0 space-y-4">
        <h2 id="answer-pipeline" className="flex items-center gap-2.5 font-serif text-2xl text-sand-100">
          <GitBranch className="shrink-0 text-emerald-400" size={24} aria-hidden="true" />
          <span>From your question to an answer</span>
        </h2>
        <p className="text-sm leading-relaxed">These stages describe the question-based daily games. Flagdle has optional helper questions alongside its visual challenge. Friend duels are different: players answer each other’s questions rather than using this engine to judge their opponent’s secret location.</p>
        <p className="text-sm leading-relaxed text-zinc-400">Select a stage to read its role and limits. This is an explanation of the engine, not a live trace or a guarantee of accuracy.</p>
        <div className="min-w-0 rounded-md border border-white/10 bg-obsidian-900 p-4 sm:p-6">
          <div role="group" aria-label="Question pipeline stages" className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {PIPELINE_STEPS.map((step, index) => {
              const isCurrent = index === activeStepIndex;
              const Icon = step.icon;
              return (
                <button
                  key={step.title}
                  type="button"
                  aria-pressed={isCurrent}
                  aria-controls={`pipeline-stage-${index}`}
                  onClick={() => setActiveStepIndex(index)}
                  className={cn(
                    'group flex min-h-11 min-w-0 flex-col rounded-sm border p-4 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400',
                    isCurrent
                      ? 'border-emerald-400/60 bg-emerald-400/10 ring-1 ring-emerald-400/30'
                      : 'border-white/10 bg-obsidian-950/60 text-zinc-400 hover:border-white/20 hover:bg-obsidian-950/90'
                  )}
                >
                  <span className="flex w-full items-center justify-between gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider">Stage {index + 1}</span>
                    <Icon size={16} className="shrink-0 text-emerald-400" aria-hidden="true" />
                  </span>
                  <span className="mt-2.5 font-serif text-sm font-semibold leading-snug text-sand-100">{step.title}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-4 min-w-0 rounded-sm border border-emerald-500/30 bg-obsidian-950/80 p-4 sm:p-5">
            <div className="flex min-w-0 flex-col gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="font-mono text-xs text-emerald-400">Stage {activeStepIndex + 1} of {PIPELINE_STEPS.length}</span>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={activeStepIndex === 0}
                  onClick={() => setActiveStepIndex(index => Math.max(0, index - 1))}
                  className="min-h-11 rounded border border-white/10 bg-obsidian-900 px-3 py-2 text-xs text-zinc-300 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 disabled:opacity-30"
                >
                  &larr; Previous stage
                </button>
                <button
                  type="button"
                  disabled={activeStepIndex === PIPELINE_STEPS.length - 1}
                  onClick={() => setActiveStepIndex(index => Math.min(PIPELINE_STEPS.length - 1, index + 1))}
                  className="min-h-11 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300 hover:bg-emerald-500/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 disabled:opacity-30"
                >
                  Next stage &rarr;
                </button>
              </div>
            </div>
            {PIPELINE_STEPS.map((step, index) => (
              <div key={step.title} id={`pipeline-stage-${index}`} hidden={index !== activeStepIndex} aria-labelledby={`pipeline-stage-title-${index}`} className="min-w-0 pt-4">
                <h3 id={`pipeline-stage-title-${index}`} className="font-serif text-xl text-sand-100">{step.title}</h3>
                <div className="mt-3 grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="min-w-0">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">What happens at this stage?</p>
                    <p className="mt-1.5 text-sm leading-relaxed">{step.description}</p>
                  </div>
                  <div className="min-w-0 rounded-sm border border-emerald-500/20 bg-emerald-500/[0.03] p-3.5">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-emerald-400">Limit</p>
                    <p className="mt-1.5 text-sm leading-relaxed text-zinc-400">{step.limitation}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="worked-examples" className="min-w-0 space-y-4">
        <h2 id="worked-examples" className="font-serif text-2xl text-sand-100">Worked examples, not live game evidence</h2>
        <p className="text-sm leading-relaxed">The named targets below are illustrative teaching examples, not today’s answer. Operation notation is schematic, not a request payload or SQL trace. We do not publish invented response timings, routing percentages or accuracy rates; response time depends on the route, services and network.</p>
        <div role="group" aria-label="Choose an answer example" className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {EXAMPLES.map(item => (
            <button
              key={item.id}
              type="button"
              aria-pressed={item.id === exampleId}
              aria-controls={`worked-example-${item.id}`}
              onClick={() => setExampleId(item.id)}
              className={cn(
                'flex min-h-11 min-w-0 flex-col justify-between rounded-sm border p-4 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400',
                item.id === exampleId ? 'border-emerald-400/60 bg-emerald-400/10 text-emerald-300 ring-1 ring-emerald-400/30' : 'border-white/10 bg-obsidian-900/90 text-zinc-400 hover:border-white/20 hover:bg-obsidian-900'
              )}
            >
              <span className="text-sm font-semibold leading-snug">{item.question}</span>
              <span className="mt-3 border-t border-white/5 pt-2 text-xs text-zinc-400">Example: {item.target}</span>
            </button>
          ))}
        </div>
        {EXAMPLES.map(item => (
          <div key={item.id} id={`worked-example-${item.id}`} hidden={item.id !== exampleId} aria-labelledby={`worked-example-title-${item.id}`} className="min-w-0 rounded-md border border-white/10 bg-obsidian-900">
            <div className="min-w-0 border-b border-white/10 bg-obsidian-950/60 p-4 sm:p-5">
              <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">Illustrative target: {item.target}</p>
              <h3 id={`worked-example-title-${item.id}`} className="mt-2 font-serif text-xl text-sand-100">{item.question}</h3>
            </div>
            <div className="min-w-0 p-4 sm:p-5">
              <dl className="grid min-w-0 grid-cols-1 gap-4 text-sm leading-relaxed sm:grid-cols-2">
                <div className="min-w-0"><dt className="text-xs text-zinc-400">Example target</dt><dd className="mt-1">{item.target}</dd></div>
                <div className="min-w-0"><dt className="text-xs text-zinc-400">Route</dt><dd className="mt-1">{item.route}</dd></div>
                <div className="min-w-0"><dt className="text-xs text-zinc-400">Operation</dt><dd className="mt-1 font-mono text-xs text-emerald-300 [overflow-wrap:anywhere]">{item.operation}</dd></div>
                <div className="min-w-0"><dt className="text-xs text-zinc-400">Illustrative result</dt><dd className="mt-1">{item.result}</dd></div>
              </dl>
              <p className="mt-4 border-t border-white/10 pt-4 text-sm leading-relaxed">{item.lesson}</p>
            </div>
          </div>
        ))}
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
