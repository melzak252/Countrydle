import { useNavigate, Link } from 'react-router-dom';
import { 
  Globe, 
  Trophy, 
  MessageSquare, 
  Search, 
  MapPin, 
  Map as MapIcon,
  Flag,
  BookOpen,
  ArrowRight
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';

export default function HomePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const games = [
    {
      id: 'world',
      title: t('home.games.worldTitle'),
      description: t('home.games.worldDescription'),
      path: '/game',
      icon: <Globe size={32} className="text-blue-500" />,
      color: 'from-blue-600 to-teal-600',
      hoverColor: 'group-hover:text-blue-400'
    },
    {
      id: 'us-states',
      title: t('home.games.usStatesTitle'),
      description: t('home.games.usStatesDescription'),
      path: '/us-states',
      icon: <MapIcon size={32} className="text-indigo-500" />,
      color: 'from-indigo-600 to-purple-600',
      hoverColor: 'group-hover:text-indigo-400'
    },
    {
      id: 'powiaty',
      title: t('home.games.powiatyTitle'),
      description: t('home.games.powiatyDescription'),
      path: '/powiaty',
      icon: <MapPin size={32} className="text-red-500" />,
      color: 'from-red-600 to-orange-600',
      hoverColor: 'group-hover:text-red-400'
    },
    {
      id: 'wojewodztwa',
      title: t('home.games.wojewodztwaTitle'),
      description: t('home.games.wojewodztwaDescription'),
      path: '/wojewodztwa',
      icon: <Flag size={32} className="text-green-500" />,
      color: 'from-green-600 to-emerald-600',
      hoverColor: 'group-hover:text-green-400'
    }
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12 md:py-20">
      {/* Hero Section */}
      <section className="text-center mb-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-5xl md:text-7xl font-black mb-6 bg-gradient-to-r from-blue-500 via-teal-400 to-green-500 text-transparent bg-clip-text">
            {t('home.heroTitle')}
          </h1>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto mb-10">
            {t('home.heroSubtitle')}
          </p>
        </motion.div>
      </section>

      {/* How It Works Section */}
      <section className="mb-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">{t('home.howToPlayTitle')}</h2>
          <div className="w-20 h-1.5 bg-blue-500 mx-auto rounded-full"></div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-blue-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <MessageSquare className="text-blue-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">{t('home.step1Title')}</h3>
            <p className="text-zinc-400">{t('home.step1Text')}</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-teal-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Search className="text-teal-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">{t('home.step2Title')}</h3>
            <p className="text-zinc-400">{t('home.step2Text')}</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-yellow-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Trophy className="text-yellow-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">{t('home.step3Title')}</h3>
            <p className="text-zinc-400">{t('home.step3Text')}</p>
          </div>
        </div>
      </section>

      {/* Game Tiles Section */}
      <section>
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">{t('home.chooseMapTitle')}</h2>
          <p className="text-zinc-500">{t('home.chooseMapText')}</p>
        </div>

        <motion.div 
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          {games.map((game) => (
            <motion.div
              key={game.id}
              variants={itemVariants}
              whileHover={{ y: -10 }}
              onClick={() => navigate(game.path)}
              className="group cursor-pointer bg-zinc-900 border border-zinc-800 p-8 rounded-3xl hover:border-zinc-600 transition-all shadow-xl flex flex-col h-full"
            >
              <div className="mb-6 p-4 bg-zinc-800/50 rounded-2xl w-fit group-hover:scale-110 transition-transform">
                {game.icon}
              </div>
              <h3 className={`text-2xl font-bold mb-3 transition-colors ${game.hoverColor}`}>
                {game.title}
              </h3>
              <p className="text-zinc-400 mb-8 flex-grow">
                {game.description}
              </p>
              <div className={`mt-auto w-full py-3 rounded-xl bg-gradient-to-r ${game.color} text-center font-bold shadow-lg opacity-90 group-hover:opacity-100 transition-opacity`}>
                {t('home.playNow')}
              </div>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Editorial Guide: The Art of Geographic Deduction */}
      <section className="mt-28 space-y-12">
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <h2 className="text-3xl md:text-5xl font-black text-white">
            The Art of Geographic Deduction
          </h2>
          <p className="text-zinc-400 text-base md:text-lg leading-relaxed">
            Countrydle combines the daily anticipation of Wordle with the analytical rigor of 20 Questions. Instead of guessing blindly, use systematic spatial triangulation to isolate any secret territory.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="text-blue-400 font-bold text-sm uppercase tracking-wider">Step 1 • Macro Triangulation</div>
            <h3 className="text-2xl font-bold text-white">Eliminate Hemispheres &amp; Continents</h3>
            <p className="text-zinc-300 leading-relaxed text-sm">
              Begin by cutting the search space in half. Asking whether the mystery country lies in the <em>Northern Hemisphere</em> immediately eliminates 32 sovereign nations in the south. Follow up with broad continental and regional checks like <em>"Is it in Europe?"</em> or <em>"Is it in Asia?"</em> to lock in your global quadrant.
            </p>
          </div>

          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="text-teal-400 font-bold text-sm uppercase tracking-wider">Step 2 • Physical Boundaries</div>
            <h3 className="text-2xl font-bold text-white">Coastline &amp; Island Classification</h3>
            <p className="text-zinc-300 leading-relaxed text-sm">
              Maritime geography provides decisive clues. Inquire whether the target <em>has access to the sea</em> or is an <em>island nation</em>. There are 44 landlocked countries in the world; identifying a landlocked nation immediately rules out thousands of kilometers of global coastline.
            </p>
          </div>

          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="text-indigo-400 font-bold text-sm uppercase tracking-wider">Step 3 • Border Topology</div>
            <h3 className="text-2xl font-bold text-white">Neighbor &amp; Frontier Mapping</h3>
            <p className="text-zinc-300 leading-relaxed text-sm">
              Once you have narrowed down a geographic cluster, test direct shared borders with pivotal hub countries (e.g., <em>"Does it border Germany?"</em> in Europe, <em>"Does it border Brazil?"</em> in South America, or <em>"Does it border DRC?"</em> in Central Africa). Each border confirmation pins the target to a small cluster of adjacent states.
            </p>
          </div>

          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="text-yellow-400 font-bold text-sm uppercase tracking-wider">Step 4 • Demographics &amp; Flags</div>
            <h3 className="text-2xl font-bold text-white">Cultural &amp; Visual Signatures</h3>
            <p className="text-zinc-300 leading-relaxed text-sm">
              When choosing between 2–3 final candidates, leverage demographic and visual attributes: driving side (left vs right), population thresholds (e.g. <em>"Is population over 20M?"</em>), official language families, or national flag colors (e.g., <em>"Does the flag contain green?"</em>).
            </p>
          </div>
        </div>

        {/* Deep Dive on Modes */}
        <div className="p-10 bg-zinc-900/60 border border-zinc-800 rounded-3xl space-y-8">
          <div className="space-y-2">
            <h3 className="text-2xl md:text-3xl font-bold text-white">Deep Regional Mastery Across 4 Modes</h3>
            <p className="text-zinc-400 text-sm">
              Countrydle is not limited to world maps. Explore our specialized regional challenges:
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
            <div className="space-y-2">
              <h4 className="font-bold text-white text-base">Poland: Voivodeships &amp; Counties</h4>
              <p className="text-zinc-400 leading-relaxed">
                Discover Poland through 16 administrative voivodeships and 380 local powiaty. Deduce locations using territorial registration plate codes (e.g. KR, WZ), major river basins like the Vistula and Oder, and historical regions such as Silesia, Mazovia, and Pomerania.
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="font-bold text-white text-base">United States: 50 States</h4>
              <p className="text-zinc-400 leading-relaxed">
                Test your American geography across all 50 US states. Use US Census regional boundaries (New England, Mountain, Pacific), Great Lakes coastlines, major highway corridors, and admission order to pinpoint the secret state.
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="font-bold text-white text-base">Global Sovereign Nations</h4>
              <p className="text-zinc-400 leading-relaxed">
                Challenge yourself daily with 195 sovereign nations across all seven continents. With verified SQLite fact tables, questions are answered with zero AI hallucinations and high factual fidelity.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Scoring Engine Breakdown: Maximize Your Rank */}
      <section className="mt-28 space-y-8">
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-semibold uppercase tracking-wider">
            <Trophy size={14} />
            Competitive Scoring System
          </div>
          <h2 className="text-3xl md:text-5xl font-black text-white">
            How Points &amp; Rankings Work
          </h2>
          <p className="text-zinc-400 text-base md:text-lg leading-relaxed">
            Every daily puzzle scores your performance dynamically across five distinct factors. Deduce boldly, solve quickly, and maintain daily streaks to top the global leaderboards.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl space-y-3">
            <div className="text-blue-400 font-bold text-xs uppercase tracking-wider">Floor</div>
            <div className="text-2xl font-black text-white">+500 pts</div>
            <h4 className="font-bold text-white text-sm">Base Win</h4>
            <p className="text-zinc-400 text-xs leading-relaxed">
              Guaranteed baseline reward for correctly solving today's mystery location.
            </p>
          </div>

          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl space-y-3">
            <div className="text-purple-400 font-bold text-xs uppercase tracking-wider">Skill Multiplier</div>
            <div className="text-2xl font-black text-purple-400">Up to +1,500 pts</div>
            <h4 className="font-bold text-white text-sm">Question Efficiency</h4>
            <p className="text-zinc-400 text-xs leading-relaxed">
              Exponential curve heavily rewarding bold deductions with minimal questions used.
            </p>
          </div>

          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl space-y-3">
            <div className="text-green-400 font-bold text-xs uppercase tracking-wider">Accuracy</div>
            <div className="text-2xl font-black text-green-400">Up to +500 pts</div>
            <h4 className="font-bold text-white text-sm">Guess Precision</h4>
            <p className="text-zinc-400 text-xs leading-relaxed">
              500 pts for 1st-try guess wins, scaling down on 2nd (+333) and 3rd (+167) attempts.
            </p>
          </div>

          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl space-y-3">
            <div className="text-amber-400 font-bold text-xs uppercase tracking-wider">Speed Decays</div>
            <div className="text-2xl font-black text-amber-400">Up to +300 pts</div>
            <h4 className="font-bold text-white text-sm">Speed Bonus</h4>
            <p className="text-zinc-400 text-xs leading-relaxed">
              Decays by 1 pt/sec over 5 minutes. Breaks leaderboard ties down to the exact second.
            </p>
          </div>

          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl space-y-3">
            <div className="text-red-400 font-bold text-xs uppercase tracking-wider">Habit Loop</div>
            <div className="text-2xl font-black text-red-400">Up to +500 pts</div>
            <h4 className="font-bold text-white text-sm">Daily Streak</h4>
            <p className="text-zinc-400 text-xs leading-relaxed">
              +50 pts per consecutive day played, scaling up to a 500 pt bonus for a 10-day streak.
            </p>
          </div>
        </div>
      </section>

      {/* Daily Blog Featurette */}
      <section className="mt-28">
        <div className="relative overflow-hidden bg-gradient-to-r from-blue-950/40 via-zinc-900 to-teal-950/30 border border-blue-500/30 rounded-3xl p-8 md:p-12 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="space-y-4 max-w-2xl text-center md:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs font-bold uppercase tracking-wider">
              <BookOpen size={14} />
              Educational Recaps
            </div>
            <h3 className="text-2xl md:text-4xl font-black text-white leading-tight">
              Missed yesterday's mystery country? Read the daily recap!
            </h3>
            <p className="text-zinc-300 text-sm md:text-base leading-relaxed">
              Every day at midnight UTC, we reveal yesterday's solution with 3 fascinating Wikipedia curiosities, optimal deduction walkthroughs, and community solve statistics.
            </p>
          </div>

          <div className="shrink-0">
            <Link
              to="/blog"
              className="inline-flex items-center gap-2 px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-black rounded-2xl shadow-xl shadow-blue-500/25 transition-all text-sm md:text-base hover:scale-105"
            >
              <span>Explore Daily Blog</span>
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer-like Stats section */}
      <motion.div 
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-32 p-12 bg-zinc-900 border border-zinc-800 rounded-[3rem] text-center"
      >
        <div className="flex justify-center">
          <div>
            <div className="text-4xl font-black mb-2">{t('home.statsDaily')}</div>
            <div className="text-zinc-500 uppercase tracking-widest text-xs font-bold">{t('home.statsChallenges')}</div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
