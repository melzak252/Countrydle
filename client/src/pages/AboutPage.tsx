import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="mx-auto max-w-5xl bg-obsidian-950 pb-8 text-zinc-300">
      <header className="border-b border-white/10 pb-8 md:pb-10">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
          {t('about.badge', 'Educational Geography Platform')}
        </p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {t('about.title', 'About Countrydle')}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          {t('about.subtitle', 'Making geographical discovery engaging, educational, and accessible through daily deductive puzzles.')}
        </p>
      </header>

      <section aria-labelledby="about-mission" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <h2 id="about-mission" className="text-xl font-semibold text-sand-100">{t('about.missionTitle', 'Our Mission')}</h2>
        <div className="space-y-4 text-base leading-7">
          <p>Countrydle was created by developer and geography enthusiast <strong className="font-semibold text-sand-100">Jakub Melzacki</strong> to transform geographic learning from static memorization into dynamic, hypothesis-driven deduction.</p>
          <p>Inspired by the simplicity of <em>Wordle</em> and the strategic depth of <em>20 Questions</em>, Countrydle challenges players to ask smart yes/no questions about hemispheres, borders, coastlines, and demographics to deduce mystery locations across the globe.</p>
        </div>
      </section>

      <section aria-labelledby="about-learning" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <h2 id="about-learning" className="text-xl font-semibold text-sand-100">{t('about.pedagogyTitle', 'Educational & Deductive Play')}</h2>
        <div className="space-y-4 text-base leading-7">
          <p>Every daily challenge exercises spatial reasoning, deductive logic, and global awareness. Rather than relying on simple multiple-choice quizzes, players build their own elimination strategies.</p>
          <p>Whether played by classrooms learning world geography or puzzle fans testing their knowledge over morning coffee, our goal is to foster genuine curiosity about world cultures, borders, and administrative structures.</p>
        </div>
      </section>

      <section aria-labelledby="about-modes" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <div>
          <h2 id="about-modes" className="text-xl font-semibold text-sand-100">{t('about.modesTitle', 'Nine Daily Modes & Friend Duels')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">Daily puzzles range from world countries and flags to continents and regional maps. Friend duels are a separate, live two-player game.</p>
        </div>
        <div className="divide-y divide-white/10">
          <div className="pb-5">
            <h3 className="mb-2 font-semibold text-sand-100">World Countries (Countrydle)</h3>
            <p className="text-base leading-7">Find the daily target among 195 playable countries worldwide. You have 10 questions and 3 guesses to narrow it down using facts such as borders, capitals, languages, coastlines, and flag designs.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">Four Continental Modes</h3>
            <p className="text-base leading-7">Europedle, Asiadle, Africadle, and Americadle focus on Europe, Asia, Africa, and the Americas respectively. Each has its own daily target, with 8 questions and 3 guesses.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">Flagdle</h3>
            <p className="text-base leading-7">Identify a country from its partially revealed flag. You have 12 guesses, with more of the flag revealed as you play and feedback to help narrow the candidates. Flagdle uses its own scoring formula.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">United States (US Statedle)</h3>
            <p className="text-base leading-7">Explore all 50 US states with 8 questions and 3 guesses. Clues can involve regions, neighboring states, water access, and statehood history.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">Polish Voivodeships (Województwodle)</h3>
            <p className="text-base leading-7">Find one of Poland&apos;s 16 voivodeships with 5 questions and 2 guesses. Investigate regional geography, internal and international borders, and Baltic coastline access.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">Polish Counties (Powiatdle)</h3>
            <p className="text-base leading-7">A local challenge covering 380 Polish counties, with 15 questions and 3 guesses. Clues include vehicle registration codes, city-county status, roads, and rivers.</p>
          </div>
          <div className="pt-5">
            <h3 className="mb-2 font-semibold text-sand-100">Play with a Friend</h3>
            <p className="text-base leading-7">Each player chooses a secret location, then takes turns asking questions or guessing. Players answer each other&apos;s questions. There is no total question or guess limit, but each action spends a turn; timers and the final-reply rule still apply.</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="about-scoring" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <div>
          <h2 id="about-scoring" className="text-xl font-semibold text-sand-100">{t('about.scoringTitle', 'Dynamic Competitive Scoring')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">{t('about.scoringSubtitle', 'Reward skill, speed, and daily consistency')}</p>
        </div>
        <div>
          <p className="mb-6 text-base leading-7">Account scores in Countrydle, the continental modes, US Statedle, Województwodle, and Powiatdle use five components for a successful solve. Guest scores are previews; streak bonuses are calculated from saved account results.</p>
          <dl className="divide-y divide-white/10 border-y border-white/10">
            <div className="py-4">
              <dt className="font-medium text-sand-100">1. Base Win Floor (+500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">The starting score for a successful daily solve. Unsolved puzzles earn no win points.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">2. Question Efficiency (Up to +1,500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">A nonlinear curve rewards solving with fewer questions.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">3. Guess Precision (Up to +500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+500 pts for a 1st-try guess win, scaled down on subsequent attempts.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">4. Speed Bonus (Up to +300 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">Decreases by one point per elapsed second, reaching zero after 5 minutes. Speed contributes to the score rather than acting as a separate leaderboard tie-break.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">5. Daily Streak Bonus (Up to +500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+50 pts per consecutive day solved in the same mode, capped at +500 pts.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">Category Bonuses</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+500 pts difficulty bonus for Powiaty (380 counties); +200 pts for US States.</dd>
            </div>
          </dl>
          <p className="mt-5 text-base leading-7">These components total up to 3,300 points before the category bonuses: up to 3,800 for Powiatdle and 3,500 for US Statedle.</p>
          <p className="mt-4 text-base leading-7"><strong className="font-semibold text-sand-100">Flagdle is scored separately:</strong> +500 for a win, a guess bonus ranging from +1,500 on the first guess to +50 on the twelfth, a speed bonus of up to +300 that decays over 3 minutes, and a streak bonus of up to +500. It has no question-efficiency component.</p>
          <p className="mt-4 text-base leading-7">Daily leaderboards are separate by mode, with monthly points and all-time average rankings. Rankings use points or average score, then wins; friend duels are separate from these daily-game scores.</p>
        </div>
      </section>

      <section aria-labelledby="about-data" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <div>
          <h2 id="about-data" className="text-xl font-semibold text-sand-100">{t('about.dataTitle', 'Data Sources & Answer Limitations')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">{t('about.dataSubtitle', 'Local facts, AI interpretation, and transparent limitations')}</p>
        </div>
        <div className="space-y-5 text-base leading-7">
          <p>AI interprets natural-language questions. When a question maps to supported facts, the game evaluates it against local fact tables. Other questions may use an AI fallback with retrieved article text or general knowledge. Interpretations and answers can be wrong, incomplete, or outdated; neither local data nor AI guarantees factual accuracy.</p>
          <ul className="list-disc space-y-3 pl-5 marker:text-emerald-400">
            <li><strong className="font-semibold text-sand-100">Country facts</strong>: REST Countries data, CIA World Factbook profiles distributed through the factbook.json project, and curated additions.</li>
            <li><strong className="font-semibold text-sand-100">US and Polish regional facts</strong>: Local article text and infoboxes, geographic classification tables, static lists, and manual corrections. These are not exclusively direct official-statistics feeds.</li>
            <li><strong className="font-semibold text-sand-100">AI-assisted extraction</strong>: Some facts, including selected rivers and water-access relationships, are extracted from Wikipedia article text using AI.</li>
            <li><strong className="font-semibold text-sand-100">Maps and globe</strong>: Bundled boundary files and Natural Earth-derived globe data are separate from the tables used to answer questions.</li>
          </ul>
        </div>
      </section>

      <section aria-labelledby="about-privacy" className="grid gap-5 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <h2 id="about-privacy" className="text-xl font-semibold text-sand-100">{t('about.privacyTitle', 'Player Privacy & Open Access')}</h2>
        <div>
          <p className="text-base leading-7">No account is required to play. For daily games, guest progress is stored in your browser; clearing site data or changing devices can make that progress unavailable. Accepted guest gameplay activity is also recorded server-side using a short-lived pseudonymous browser identifier.</p>
          <p className="mt-4 text-base leading-7">The site loads Google AdSense, and analytics such as Rybbit may be enabled by deployment settings. See the <Link to="/privacy-policy" className="whitespace-nowrap text-emerald-300 underline underline-offset-4 hover:text-emerald-200">Privacy Policy</Link> and <Link to="/cookie-policy" className="whitespace-nowrap text-emerald-300 underline underline-offset-4 hover:text-emerald-200">Cookie Policy</Link> for details about data and cookies.</p>
          <p className="mt-5 text-sm text-zinc-400">Built for the global geography community</p>
        </div>
      </section>
    </div>
  );
}
