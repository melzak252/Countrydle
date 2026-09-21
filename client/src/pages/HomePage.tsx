import { Link } from 'react-router-dom';
import { ArrowDown, ArrowRight, BookOpen, Flag, Globe, Map, MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function HomePage() {
  const { t } = useTranslation();
  const copy = {
    eyebrow: 'The daily geography puzzle',
    title: 'A whole world.',
    titleEnd: 'One hidden place.',
    intro: 'Ask yes-or-no questions. Connect the clues and find the place on the map before your guesses run out.',
    choose: 'Choose your map',
    atlas: 'An atlas of deduction',
    diagram: 'Latitude and longitude',
    modes: 'Four maps. Four challenges.',
    modeNote: 'Each mode has its own question and guess limits.',
    questions: 'Questions',
    guesses: 'Guesses',
    play: 'Play',
    how: 'From question to location.',
    howLabel: 'How to play',
    steps: [
      { title: 'Ask a question', text: 'Start broad: is the place in the north? Does it have a coastline?' },
      { title: 'Narrow the map', text: 'Use the answers to rule out possibilities. Each new question can bring you closer.' },
      { title: 'Name the place', text: 'When you have a candidate, submit your guess. Choose carefully: your attempts are limited.' },
    ],
    journalLabel: 'Field notes',
    journalTitle: 'The puzzle ends. The discovery doesn’t.',
    journalText: 'Revisit past puzzles and get to know the places behind the answers.',
    journalLink: 'Explore the blog',
  };

  const games = [
    { id: 'world', title: t('home.games.worldTitle'), region: 'The world',
      description: 'From islands to landlocked nations. Find the mystery country.',
      path: '/game', icon: Globe, questions: 10, guesses: 3 },
    { id: 'us-states', title: t('home.games.usStatesTitle'), region: 'United States',
      description: 'Coastlines, borders and regions. Which state fits the clues?',
      path: '/us-states', icon: Map, questions: 8, guesses: 3 },
    { id: 'powiaty', title: t('home.games.powiatyTitle'), region: 'Poland / Counties',
      description: 'Take a closer look at Poland. Track down the hidden county.',
      path: '/powiaty', icon: MapPin, questions: 15, guesses: 3 },
    { id: 'wojewodztwa', title: t('home.games.wojewodztwaTitle'), region: 'Poland / Voivodeships',
      description: 'Think regionally. Identify the voivodeship with just a few questions.',
      path: '/wojewodztwa', icon: Flag, questions: 5, guesses: 2 },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 md:pb-24 md:pt-16">
      <section aria-labelledby="home-heading" className="grid items-center gap-10 border-b border-white/10 pb-12 md:grid-cols-[1.4fr_1fr] md:pb-16">
        <div>
          <p className="mb-6 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">
            <span aria-hidden="true" className="h-px w-7 bg-emerald-400" />
            {copy.eyebrow}
          </p>
          <h1 id="home-heading" className="text-4xl font-semibold leading-[1.08] tracking-tight text-sand-100 sm:text-5xl lg:text-6xl">
            {copy.title}
            <span className="mt-2 block font-serif font-normal italic text-sand-200">{copy.titleEnd}</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-slate-400 md:text-lg">{copy.intro}</p>
          <a href="#maps" className="mt-8 inline-flex min-h-12 items-center gap-5 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400">
            {copy.choose}<ArrowDown size={16} aria-hidden="true" />
          </a>
        </div>

        <figure className="mx-auto hidden w-full max-w-sm md:block">
          <svg viewBox="0 0 360 310" fill="none" className="w-full text-emerald-400" aria-hidden="true">
            <path d="M26 155h308M180 16v278" stroke="currentColor" strokeOpacity="0.18" strokeDasharray="3 6" />
            <circle cx="180" cy="155" r="124" stroke="currentColor" strokeOpacity="0.5" />
            <ellipse cx="180" cy="155" rx="83" ry="124" stroke="currentColor" strokeOpacity="0.22" />
            <ellipse cx="180" cy="155" rx="34" ry="124" stroke="currentColor" strokeOpacity="0.22" />
            <path d="M73 93h214M56 155h248M73 217h214" stroke="currentColor" strokeOpacity="0.22" />
            <circle cx="180" cy="155" r="5" fill="currentColor" />
            <path d="M170 155h-13m46 0h-13m-10-10v-13m0 46v-13" stroke="currentColor" />
            <text x="313" y="159" fill="currentColor" fillOpacity="0.7" fontSize="10" fontFamily="monospace">0°</text>
          </svg>
          <figcaption className="flex justify-between border-t border-white/10 pt-3 font-mono text-[10px] uppercase tracking-wider text-slate-500">
            <span>{copy.atlas}</span><span>{copy.diagram}</span>
          </figcaption>
        </figure>
      </section>

      <section id="maps" aria-labelledby="maps-heading" className="scroll-mt-24 py-10 md:py-14">
        <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <h2 id="maps-heading" className="text-2xl font-semibold tracking-tight text-sand-100">{copy.modes}</h2>
          <p className="text-sm text-slate-400">{copy.modeNote}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {games.map((game, index) => (
            <Link key={game.id} to={game.path} className="group flex flex-col rounded-sm border border-white/10 bg-obsidian-900 p-6 transition-colors hover:border-emerald-400/50 hover:bg-obsidian-850 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 md:p-7">
              <div className="mb-5 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">0{index + 1} / {game.region}</span>
                <game.icon size={22} strokeWidth={1.5} className="shrink-0 text-emerald-400" aria-hidden="true" />
              </div>
              <h3 className="break-words text-2xl font-semibold tracking-tight text-sand-100">{game.title}</h3>
              <p className="mb-7 mt-3 max-w-md flex-1 text-sm leading-relaxed text-slate-400">{game.description}</p>
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-4">
                <dl className="flex gap-5 text-xs">
                  <div className="flex items-baseline gap-2"><dt className="text-slate-400">{copy.questions}</dt><dd className="font-mono text-sand-100">{game.questions}</dd></div>
                  <div className="flex items-baseline gap-2"><dt className="text-slate-400">{copy.guesses}</dt><dd className="font-mono text-sand-100">{game.guesses}</dd></div>
                </dl>
                <span className="inline-flex items-center gap-3 text-sm font-medium text-emerald-400">{copy.play}<ArrowRight size={17} aria-hidden="true" /></span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="how-heading" className="border-y border-white/10 py-9 md:py-12">
        <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">{copy.howLabel}</p>
        <h2 id="how-heading" className="text-2xl font-semibold tracking-tight text-sand-100">{copy.how}</h2>
        <ol className="mt-7 grid gap-7 md:grid-cols-3 md:gap-10">
          {copy.steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span aria-hidden="true" className="mt-1 font-mono text-xs text-emerald-400">0{index + 1}</span>
              <div><h3 className="font-medium text-sand-100">{step.title}</h3><p className="mt-2 text-sm leading-relaxed text-slate-400">{step.text}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="journal-heading" className="flex flex-col justify-between gap-6 pt-10 sm:flex-row sm:items-center md:pt-12">
        <div className="max-w-xl">
          <p className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-400"><BookOpen size={14} aria-hidden="true" />{copy.journalLabel}</p>
          <h2 id="journal-heading" className="font-serif text-2xl text-sand-100">{copy.journalTitle}</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">{copy.journalText}</p>
        </div>
        <Link to="/blog" className="inline-flex min-h-12 shrink-0 items-center justify-center gap-4 self-start rounded-sm border border-white/20 px-5 py-3 text-sm font-medium text-sand-100 transition-colors hover:border-emerald-400/50 hover:text-emerald-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 sm:self-auto">
          {copy.journalLink}<ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}
