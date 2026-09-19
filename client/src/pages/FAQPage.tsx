import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HelpCircle, ChevronDown, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface FAQItem {
  id: string;
  category: 'gameplay' | 'modes' | 'data' | 'account';
  question: string;
  answer: string;
}

const FAQ_DATA: FAQItem[] = [
  // Category 1: Gameplay & Mechanics
  {
    id: 'how-it-works',
    category: 'gameplay',
    question: 'How does Countrydle work?',
    answer: 'Countrydle is a daily geography deduction game. Every day at midnight UTC, a secret target location is chosen. You have a budget of questions (e.g. 10 for countries, 5 for voivodeships) and guesses (usually 2 to 3) to deduce the mystery location. You ask natural-language yes/no questions to eliminate regions, borders, and characteristics before submitting your final guess.'
  },
  {
    id: 'valid-questions',
    category: 'gameplay',
    question: 'What kind of questions can I ask?',
    answer: 'You can ask any factual yes/no question regarding geography, borders, physical features, or demographics! Great examples include: "Is it in the Northern Hemisphere?", "Does it have access to the sea?", "Does it border Germany?", "Is the population greater than 20 million?", "Does the flag contain red?", and "Is the capital city Paris?".'
  },
  {
    id: 'typos-and-invalid',
    category: 'gameplay',
    question: 'Do typos or open-ended questions consume my question limit?',
    answer: 'No! If you ask an open-ended question (e.g., "What is the capital?"), make a typo, or enter an unparseable sentence, the system flags it as invalid and provides an explanatory warning. Your question count is NOT deducted, allowing you to rephrase your thought without penalty.'
  },
  {
    id: 'scoring-and-limits',
    category: 'gameplay',
    question: 'How does scoring work and what happens when I run out of guesses?',
    answer: 'Points are awarded dynamically across five performance factors: 1) Base win bonus (+500 pts), 2) Question efficiency (up to +1,500 pts rewarding bold deductions with fewer questions asked), 3) Guess efficiency (up to +500 pts for 1st-try accuracy), 4) Speed bonus (up to +300 pts for fast solves under 5 minutes), and 5) Daily streak bonus (+50 pts/day up to +500 pts). Total scores range up to ~3,300+ points. If you exhaust your guesses or questions, the game ends and reveals the secret entity.'
  },

  // Category 2: Modes & Archive
  {
    id: 'game-modes',
    category: 'modes',
    question: 'What are the four different game modes?',
    answer: 'Countrydle offers four distinct geographic scopes: 1) World Countries (195 sovereign nations across all continents), 2) US Statedle (all 50 American states), 3) Województwodle (Poland\'s 16 administrative voivodeships), and 4) Powiatdle (380 Polish counties tested via registration plates, rivers, and roads).'
  },
  {
    id: 'play-past-games',
    category: 'modes',
    question: 'Can I play previous daily puzzles?',
    answer: 'You can view the full history and solutions of past daily puzzles by visiting the Archive page in the header menu. It lists previous dates and answers across all four game modes so you can check what you missed.'
  },

  // Category 3: Knowledge Base & Truth
  {
    id: 'data-sources',
    category: 'data',
    question: 'Where does Countrydle get its geography facts and maps?',
    answer: 'Our knowledge base is strictly verified from authoritative public sources: Natural Earth and OpenStreetMap for boundary geometries and coastlines; Główny Urząd Statystyczny (GUS) for official Polish county demographics and registration codes; and the US Census Bureau for American state statistics.'
  },
  {
    id: 'hallucination-prevention',
    category: 'data',
    question: 'How do you guarantee answers are factually accurate without AI hallucinations?',
    answer: 'Countrydle does not let generative AI invent answers. Instead, AI is used strictly as a semantic compiler that translates your natural language question into a structured query plan. That plan executes directly against curated, local SQLite relational tables, delivering 100% verified factual truth.'
  },
  {
    id: 'historical-unions',
    category: 'data',
    question: 'Can I ask about historical blocs or former unions?',
    answer: 'Yes! Our database includes major historical unions and former alliances such as the USSR, Warsaw Pact, Yugoslavia, Gran Colombia, and former colonial spheres (e.g., British Empire, Spanish Empire).'
  },

  // Category 4: Accounts & Privacy
  {
    id: 'need-account',
    category: 'account',
    question: 'Do I need to create an account to play?',
    answer: 'Not at all! Countrydle is 100% free and open for guest play. Your daily progress, guesses, and question history are saved automatically in your browser\'s local storage.'
  },
  {
    id: 'guest-sync',
    category: 'account',
    question: 'What happens to my guest progress if I sign up or log in later?',
    answer: 'Our platform features seamless guest synchronization. When you register or log in, your ongoing daily game state, questions, and guesses are automatically synced to your new profile without losing your current game.'
  },
  {
    id: 'streaks-and-profile',
    category: 'account',
    question: 'How do daily streaks and leaderboards work?',
    answer: 'Registered players earn points and daily streaks for every solved puzzle. Your profile tracks your total points, total wins, games played, and active win streak, ranking you on monthly and average-performance global leaderboards.'
  }
];

export default function FAQPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<'all' | 'gameplay' | 'modes' | 'data' | 'account'>('all');
  const [openIds, setOpenIds] = useState<Set<string>>(new Set(['how-it-works', 'valid-questions']));

  const toggleItem = (id: string) => {
    setOpenIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredFAQs = useMemo(() => {
    return FAQ_DATA.filter(item => {
      const matchesCategory = activeCategory === 'all' || item.category === activeCategory;
      const matchesSearch = !search.trim() || 
        item.question.toLowerCase().includes(search.toLowerCase()) || 
        item.answer.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [search, activeCategory]);

  return (
    <div className="max-w-4xl mx-auto px-4 py-12 md:py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-10"
      >
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold uppercase tracking-wider">
            <HelpCircle size={15} />
            <span>{t('faq.badge', 'Knowledge Base & Help')}</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-teal-300 to-green-400 text-transparent bg-clip-text">
            {t('faq.title', 'Frequently Asked Questions')}
          </h1>
          <p className="text-zinc-400 max-w-xl mx-auto text-sm md:text-base">
            {t('faq.subtitle', 'Everything you need to know about deduction rules, scoring, geography datasets, and game mechanics.')}
          </p>
        </div>

        {/* Search Bar & Category Filters */}
        <div className="space-y-4">
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions (e.g. streaks, borders, invalid questions, data)..."
              className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 pl-11 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors shadow-lg"
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 w-4 h-4" />
          </div>

          <div className="flex flex-wrap gap-2">
            {(
              [
                { id: 'all', label: 'All Topics' },
                { id: 'gameplay', label: 'Gameplay & Rules' },
                { id: 'modes', label: 'Game Modes' },
                { id: 'data', label: 'Data & Facts' },
                { id: 'account', label: 'Accounts & Streaks' },
              ] as const
            ).map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setActiveCategory(cat.id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeCategory === cat.id
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Accordion List */}
        <div className="space-y-3">
          {filteredFAQs.length === 0 ? (
            <div className="p-12 text-center text-zinc-500 bg-zinc-900/50 border border-zinc-800 rounded-3xl">
              No questions found matching "{search}". Try searching for another topic.
            </div>
          ) : (
            filteredFAQs.map((faq) => {
              const isOpen = openIds.has(faq.id);
              return (
                <div
                  key={faq.id}
                  className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden transition-colors hover:border-zinc-700"
                >
                  <button
                    type="button"
                    onClick={() => toggleItem(faq.id)}
                    className="w-full text-left px-6 py-4 flex items-center justify-between gap-4 cursor-pointer"
                  >
                    <span className="font-bold text-white text-base md:text-lg">{faq.question}</span>
                    <ChevronDown
                      size={20}
                      className={`text-zinc-400 shrink-0 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-blue-400' : ''
                      }`}
                    />
                  </button>

                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <div className="px-6 pb-5 pt-1 text-zinc-300 text-sm leading-relaxed border-t border-zinc-800/60 mt-1">
                          {faq.answer}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })
          )}
        </div>
      </motion.div>
    </div>
  );
}
