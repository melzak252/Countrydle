import { useState, useMemo } from 'react';
import { ChevronDown, Search } from 'lucide-react';
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
    answer: 'You can ask factual yes/no questions about geography, borders, physical features, demographics, or the country name. In Countrydle, direct identity questions and questions naming several candidate countries are allowed while the game is active and you have questions left. Each valid question uses one question, not a guess. A yes answer does not win the game: submit the location in the guess field to finish.'
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
    answer: 'Points are awarded dynamically across five performance factors: 1) Base win bonus (+500 pts), 2) Question efficiency (up to +1,500 pts rewarding bold deductions with fewer questions asked), 3) Guess efficiency (up to +500 pts for 1st-try accuracy), 4) Speed bonus (up to +300 pts for fast solves under 5 minutes), and 5) Daily streak bonus (+50 pts/day up to +500 pts). Total scores range up to ~3,300+ points. Running out of questions does not end the game: you can still use any remaining guesses. The game ends when you guess correctly or exhaust your guesses.'
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
    <div className="mx-auto max-w-4xl bg-obsidian-950 pb-8">
      <header className="border-b border-white/10 pb-8 md:pb-10">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
          {t('faq.badge', 'Knowledge Base & Help')}
        </p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {t('faq.title', 'Frequently Asked Questions')}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400">
          {t('faq.subtitle', 'Everything you need to know about deduction rules, scoring, geography datasets, and game mechanics.')}
        </p>
      </header>

      <div className="space-y-5 py-7">
        <div>
          <label htmlFor="faq-search" className="mb-3 block text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
            Search questions
          </label>
          <div className="relative">
            <Search aria-hidden="true" size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              id="faq-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search rules, streaks, borders or data..."
              className="w-full rounded-sm border border-white/15 bg-obsidian-900 py-3 pl-11 pr-4 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
            />
          </div>
        </div>

        <div role="group" aria-label="Filter questions by topic" className="flex flex-wrap gap-2">
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
              aria-pressed={activeCategory === cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`min-h-11 rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 ${
                activeCategory === cat.id
                  ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                  : 'border-white/10 bg-obsidian-900 text-zinc-400 hover:border-white/25 hover:text-sand-100'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      <p role="status" className="mb-3 text-sm text-zinc-400">
        {filteredFAQs.length} {filteredFAQs.length === 1 ? 'question' : 'questions'}
      </p>
      <div className="divide-y divide-white/10 border-y border-white/10">
        {filteredFAQs.length === 0 ? (
          <div className="bg-obsidian-900 px-5 py-10 text-base leading-7 text-zinc-400">
            No questions found matching "{search}". Try searching for another topic.
          </div>
        ) : (
          filteredFAQs.map((faq) => {
            const isOpen = openIds.has(faq.id);
            return (
              <section key={faq.id} aria-labelledby={`question-${faq.id}`} className={isOpen ? 'bg-obsidian-900' : ''}>
                <h2>
                  <button
                    id={`question-${faq.id}`}
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={`answer-${faq.id}`}
                    onClick={() => toggleItem(faq.id)}
                    className="flex w-full items-center justify-between gap-5 px-4 py-5 text-left transition-colors hover:bg-white/[0.03] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400 sm:px-5"
                  >
                    <span className="text-base font-medium leading-7 text-sand-100 sm:text-lg">{faq.question}</span>
                    <ChevronDown
                      aria-hidden="true"
                      size={20}
                      className={`shrink-0 text-emerald-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                </h2>
                <div id={`answer-${faq.id}`} hidden={!isOpen} className="px-4 pb-6 sm:px-5">
                  <p className="max-w-3xl text-base leading-7 text-zinc-300">{faq.answer}</p>
                </div>
              </section>
            );
          })
        )}
      </div>
    </div>
  );
}
