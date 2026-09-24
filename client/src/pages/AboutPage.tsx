import { useTranslation } from 'react-i18next';

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
          <h2 id="about-modes" className="text-xl font-semibold text-sand-100">{t('about.modesTitle', 'Four Unique Geographic Challenges')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">From global sovereign nations to deep regional administrative units.</p>
        </div>
        <div className="divide-y divide-white/10">
          <div className="pb-5">
            <h3 className="mb-2 font-semibold text-sand-100">1. World Countries (Countrydle)</h3>
            <p className="text-base leading-7">Spans 195 playable countries across 7 continents. Players can test hypotheses regarding continental placement, oceanic coastlines, neighboring sovereign nations, capital cities, driving orientation, and national flag designs within a strict 10-question budget.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">2. United States (US Statedle)</h3>
            <p className="text-base leading-7">Covers all 50 American states. Deduction features include US Census geographic regions and divisions (e.g., New England, Mountain, South Atlantic), border states, oceanic and Great Lakes coastlines, major rivers like the Mississippi, and statehood admission order.</p>
          </div>
          <div className="py-5">
            <h3 className="mb-2 font-semibold text-sand-100">3. Polish Voivodeships (Województwodle)</h3>
            <p className="text-base leading-7">Explores Poland's 16 first-level administrative voivodeships (województwa). Players investigate macroregions, internal borders, foreign borders with neighboring countries, Baltic coastline access, and historical regions such as Silesia (Śląsk) and Greater Poland (Wielkopolska).</p>
          </div>
          <div className="pt-5">
            <h3 className="mb-2 font-semibold text-sand-100">4. Polish Counties (Powiatdle)</h3>
            <p className="text-base leading-7">A hyper-local challenge across 380 Polish counties (powiaty). Features include vehicle registration plate codes (e.g. KR for Kraków, WZ for Warsaw West), city-county status, arterial highways (A1, A4, S7), and river systems.</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="about-scoring" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <div>
          <h2 id="about-scoring" className="text-xl font-semibold text-sand-100">{t('about.scoringTitle', 'Dynamic Competitive Scoring')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">{t('about.scoringSubtitle', 'Reward skill, speed, and daily consistency')}</p>
        </div>
        <div>
          <p className="mb-6 text-base leading-7">Unlike static games where scores cluster identically, Countrydle features an exponential 5-factor scoring engine designed for true player differentiation:</p>
          <dl className="divide-y divide-white/10 border-y border-white/10">
            <div className="py-4">
              <dt className="font-medium text-sand-100">1. Base Win Floor (+500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">Guaranteed points for any successfully solved daily puzzle.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">2. Question Efficiency (Up to +1,500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">Exponential curve that rewards bold deduction with minimal questions used.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">3. Guess Precision (Up to +500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+500 pts for a 1st-try guess win, scaled down on subsequent attempts.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">4. Speed Bonus (Up to +300 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">Decays over 5 minutes, breaking leaderboard ties down to the exact second.</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">5. Daily Streak Bonus (Up to +500 pts)</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+50 pts per consecutive day solved, up to a 10-day cap (+500 pts).</dd>
            </div>
            <div className="py-4">
              <dt className="font-medium text-sand-100">Category Bonuses</dt>
              <dd className="mt-1 text-sm leading-6 text-zinc-400">+500 pts difficulty bonus for Powiaty (380 counties); +200 pts for US States.</dd>
            </div>
          </dl>
        </div>
      </section>

      <section aria-labelledby="about-data" className="grid gap-5 border-b border-white/10 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <div>
          <h2 id="about-data" className="text-xl font-semibold text-sand-100">{t('about.dataTitle', 'Data Sources & Verification')}</h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">{t('about.dataSubtitle', 'Curated, factual, and strictly grounded datasets')}</p>
        </div>
        <div className="space-y-5 text-base leading-7">
          <p>To guarantee factual truth without AI hallucination, Countrydle evaluates questions against verified local databases rather than open-ended text generation. Our geospatial and demographic data are compiled from authoritative public bodies:</p>
          <ul className="list-disc space-y-3 pl-5 marker:text-emerald-400">
            <li><strong className="font-semibold text-sand-100">Natural Earth &amp; OpenStreetMap</strong>: Global boundary vectors, island classifications, and coordinate centroids.</li>
            <li><strong className="font-semibold text-sand-100">Główny Urząd Statystyczny (GUS)</strong>: Official Polish county demographics, TERYT territorial codes, and registration plate designations.</li>
            <li><strong className="font-semibold text-sand-100">United States Census Bureau</strong>: State population estimates, census divisions, and official land areas.</li>
            <li><strong className="font-semibold text-sand-100">CIA World Factbook &amp; REST Countries</strong>: International maritime coastlines, currencies, languages, and driving orientations.</li>
          </ul>
        </div>
      </section>

      <section aria-labelledby="about-privacy" className="grid gap-5 py-8 md:grid-cols-[1fr_2fr] md:gap-12 md:py-10">
        <h2 id="about-privacy" className="text-xl font-semibold text-sand-100">{t('about.privacyTitle', 'Player Privacy & Open Access')}</h2>
        <div>
          <p className="text-base leading-7">Countrydle does not require registration. Guest play is 100% free with progress saved locally on your device. We do not sell player data or track personal browsing.</p>
          <p className="mt-5 text-sm text-zinc-400">Built for the global geography community</p>
        </div>
      </section>
    </div>
  );
}
