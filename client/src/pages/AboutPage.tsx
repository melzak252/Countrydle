import { motion } from 'framer-motion';
import { Globe, Database, Compass, Award, ShieldCheck, Heart } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-5xl mx-auto px-4 py-12 md:py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-12"
      >
        {/* Hero Header */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs md:text-sm font-semibold uppercase tracking-wider">
            <Compass size={16} />
            {t('about.badge', 'Educational Geography Platform')}
          </div>
          <h1 className="text-4xl md:text-6xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-teal-300 to-green-400 text-transparent bg-clip-text">
            {t('about.title', 'About Countrydle')}
          </h1>
          <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            {t('about.subtitle', 'Making geographical discovery engaging, educational, and accessible through daily deductive puzzles.')}
          </p>
        </div>

        {/* Origin & Mission */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="w-12 h-12 rounded-2xl bg-blue-500/10 flex items-center justify-center text-blue-400">
              <Globe size={24} />
            </div>
            <h2 className="text-2xl font-bold text-white">{t('about.missionTitle', 'Our Mission')}</h2>
            <p className="text-zinc-300 leading-relaxed">
              Countrydle was created by developer and geography enthusiast <strong>Jakub Melzacki</strong> to transform geographic learning from static memorization into dynamic, hypothesis-driven deduction. 
            </p>
            <p className="text-zinc-400 leading-relaxed text-sm">
              Inspired by the simplicity of <em>Wordle</em> and the strategic depth of <em>20 Questions</em>, Countrydle challenges players to ask smart yes/no questions about hemispheres, borders, coastlines, and demographics to deduce mystery locations across the globe.
            </p>
          </div>

          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="w-12 h-12 rounded-2xl bg-teal-500/10 flex items-center justify-center text-teal-400">
              <Award size={24} />
            </div>
            <h2 className="text-2xl font-bold text-white">{t('about.pedagogyTitle', 'Educational & Deductive Play')}</h2>
            <p className="text-zinc-300 leading-relaxed">
              Every daily challenge exercises spatial reasoning, deductive logic, and global awareness. Rather than relying on simple multiple-choice quizzes, players build their own elimination strategies.
            </p>
            <p className="text-zinc-400 leading-relaxed text-sm">
              Whether played by classrooms learning world geography or puzzle fans testing their knowledge over morning coffee, our goal is to foster genuine curiosity about world cultures, borders, and administrative structures.
            </p>
          </div>
        </div>

        {/* The Four Modes In-Depth */}
        <section className="space-y-6">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-bold text-white">{t('about.modesTitle', 'Four Unique Geographic Challenges')}</h2>
            <p className="text-zinc-400 text-sm max-w-xl mx-auto">
              From global sovereign nations to deep regional administrative units.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl space-y-3">
              <h3 className="text-xl font-bold text-blue-400">1. World Countries (Countrydle)</h3>
              <p className="text-zinc-300 text-sm leading-relaxed">
                Spans all 195 sovereign nations across 7 continents. Players can test hypotheses regarding continental placement, oceanic coastlines, neighboring sovereign nations, capital cities, driving orientation, and national flag designs within a strict 10-question budget.
              </p>
            </div>

            <div className="p-6 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl space-y-3">
              <h3 className="text-xl font-bold text-indigo-400">2. United States (US Statedle)</h3>
              <p className="text-zinc-300 text-sm leading-relaxed">
                Covers all 50 American states. Deduction features include US Census geographic regions and divisions (e.g., New England, Mountain, South Atlantic), border states, oceanic and Great Lakes coastlines, major rivers like the Mississippi, and statehood admission order.
              </p>
            </div>

            <div className="p-6 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl space-y-3">
              <h3 className="text-xl font-bold text-green-400">3. Polish Voivodeships (Województwodle)</h3>
              <p className="text-zinc-300 text-sm leading-relaxed">
                Explores Poland's 16 first-level administrative voivodeships (województwa). Players investigate macroregions, internal borders, foreign borders with neighboring countries, Baltic coastline access, and historical regions such as Silesia (Śląsk) and Greater Poland (Wielkopolska).
              </p>
            </div>

            <div className="p-6 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl space-y-3">
              <h3 className="text-xl font-bold text-red-400">4. Polish Counties (Powiatdle)</h3>
              <p className="text-zinc-300 text-sm leading-relaxed">
                A hyper-local challenge across 380 Polish counties (powiaty). Features include vehicle registration plate codes (e.g. KR for Kraków, WZ for Warsaw West), city-county status, arterial highways (A1, A4, S7), and river systems.
              </p>
            </div>
          </div>
        </section>

        {/* Data Provenance & Authority (E-E-A-T) */}
        <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-6 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400">
              <Database size={24} />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">{t('about.dataTitle', 'Data Sources & Verification')}</h2>
              <p className="text-zinc-400 text-xs">{t('about.dataSubtitle', 'Curated, factual, and strictly grounded datasets')}</p>
            </div>
          </div>

          <p className="text-zinc-300 leading-relaxed text-sm">
            To guarantee factual truth without AI hallucination, Countrydle evaluates questions against verified local databases rather than open-ended text generation. Our geospatial and demographic data are compiled from authoritative public bodies:
          </p>

          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-zinc-300">
            <li className="flex items-start gap-2">
              <span className="text-teal-400 font-bold">•</span>
              <span><strong>Natural Earth &amp; OpenStreetMap</strong>: Global boundary vectors, island classifications, and coordinate centroids.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-teal-400 font-bold">•</span>
              <span><strong>Główny Urząd Statystyczny (GUS)</strong>: Official Polish county demographics, TERYT territorial codes, and registration plate designations.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-teal-400 font-bold">•</span>
              <span><strong>United States Census Bureau</strong>: State population estimates, census divisions, and official land areas.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-teal-400 font-bold">•</span>
              <span><strong>CIA World Factbook &amp; REST Countries</strong>: International maritime coastlines, currencies, languages, and driving orientations.</span>
            </li>
          </ul>
        </div>

        {/* Privacy & Player Respect */}
        <div className="p-8 bg-zinc-900/40 border border-zinc-800/80 rounded-3xl flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-white font-bold text-lg">
              <ShieldCheck className="text-green-400" size={20} />
              <span>{t('about.privacyTitle', 'Player Privacy & Open Access')}</span>
            </div>
            <p className="text-zinc-400 text-sm max-w-2xl">
              Countrydle does not require registration. Guest play is 100% free with progress saved locally on your device. We do not sell player data or track personal browsing.
            </p>
          </div>
          <div className="flex items-center gap-2 text-zinc-500 text-xs shrink-0">
            <Heart size={14} className="text-red-500" />
            <span>Built for the global geography community</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
