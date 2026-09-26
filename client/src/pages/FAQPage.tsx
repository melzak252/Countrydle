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
    answer: 'Daily puzzles change at midnight UTC. In the question-based modes, ask natural-language yes/no questions to narrow down the target, then submit a guess. Countrydle allows 10 questions and 3 guesses; each continental mode and US Statedle allow 8 and 3; Województwodle allows 5 and 2; Powiatdle allows 15 and 3. Flagdle is a separate flag-reveal challenge with 12 guesses. Friend duels are live matches rather than daily puzzles.'
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
    answer: 'Questions classified as invalid do not use a question. Open-ended requests such as "What is the capital?" are intended to be rejected, but AI classification is not infallible. A typo may still be understood and accepted, in which case the question counts normally. Read the feedback and rephrase when needed; a spelling mistake does not guarantee a free question.'
  },
  {
    id: 'scoring-and-limits',
    category: 'gameplay',
    question: 'How does scoring work and what happens when I run out of guesses?',
    answer: 'In the question-based daily modes, a win earns +500 base points, up to +1,500 for question efficiency, up to +500 for guess efficiency, up to +300 for speed over a 5-minute window, and +50 per consecutive day solved in that mode, capped at +500. Powiatdle adds +500 and US Statedle adds +200. Guest scores are previews; account streak bonuses use saved results. Flagdle has a separate formula. Running out of questions does not end a daily game while guesses remain: a correct guess or exhausting the guesses ends it.'
  },

  // Category 2: Modes & Archive
  {
    id: 'game-modes',
    category: 'modes',
    question: 'Which game modes are available?',
    answer: 'There are nine daily modes: Countrydle (195 countries worldwide), Flagdle, Europedle, Asiadle, Africadle, Americadle, US Statedle (50 states), Województwodle (16 Polish voivodeships), and Powiatdle (380 Polish counties). The four continental modes focus on Europe, Asia, Africa, and the Americas. Play with a Friend offers separate live two-player duels.'
  },
  {
    id: 'flagdle',
    category: 'modes',
    question: 'How is Flagdle different?',
    answer: 'Flagdle asks you to identify a country from a partially revealed flag, with 12 guesses and more of the flag revealed as you play. Its score uses +500 for a win, a guess bonus from +1,500 on the first guess to +50 on the twelfth, a speed bonus of up to +300 that decays over 3 minutes, and a streak bonus of up to +500. There is no question-efficiency scoring component.'
  },
  {
    id: 'friend-duels',
    category: 'modes',
    question: 'How do friend duels work? Are questions and guesses unlimited?',
    answer: 'Create an invite from Play with a Friend and share it with your opponent. Each player chooses a secret location. Take turns asking a question or making a guess; players answer each other’s questions. There is no total question or guess limit, but each action spends one turn and turn timers still apply. If the starting player solves first, the other player gets a final guess to draw or can pass. That final reply does not allow another question.'
  },
  {
    id: 'play-past-games',
    category: 'modes',
    question: 'Can I play previous daily puzzles?',
    answer: 'You can browse past answers, but the Archive does not replay past puzzles. It currently covers Countrydle, US Statedle, Województwodle, and Powiatdle, not all nine daily modes. Countrydle entries link to daily blog recaps. Open Archive from the navigation menu to see the available dates and solutions.'
  },

  // Category 3: Knowledge Base & Truth
  {
    id: 'data-sources',
    category: 'data',
    question: 'Where does Countrydle get its geography facts and maps?',
    answer: 'Sources vary by mode and field. Country facts combine REST Countries, Factbook-derived profiles, and curated additions. Regional facts use local article text and infoboxes, classification tables, and manual lists or corrections. Some geography facts are extracted from Wikipedia text using AI. Maps use bundled boundary assets and Natural Earth-derived globe data, separately from the answer tables. These sources can contain errors or outdated information; they are not all direct official-statistics feeds.'
  },
  {
    id: 'hallucination-prevention',
    category: 'data',
    question: 'How are answers generated, and can they be wrong?',
    answer: 'Yes, answers can be wrong. AI first interprets your question and, where supported, turns it into a plan evaluated against local fact tables. Questions outside that coverage may use generative AI with retrieved article text or general knowledge. Incorrect interpretation, incomplete data, and AI fallback can all produce mistakes. Database-backed answers reduce some risks, but do not guarantee factual truth.'
  },
  {
    id: 'historical-unions',
    category: 'data',
    question: 'Can I ask about historical blocs or former unions?',
    answer: 'Countrydle includes historical membership associations such as the USSR, Warsaw Pact, Yugoslavia, Gran Colombia, and the British and Spanish Empires. These are simplified associations, not a complete historical atlas. Coverage and interpretation can be incomplete, especially when borders or membership changed over time.'
  },

  // Category 4: Accounts & Privacy
  {
    id: 'need-account',
    category: 'account',
    question: 'Do I need to create an account to play?',
    answer: 'No account is required for daily games or friend duels. Guest daily progress is stored in this browser, so changing devices, clearing site data, or using private browsing can make it unavailable. History retention varies by mode; Flagdle question history is not reliably retained after a reload. Accepted guest gameplay activity is also recorded server-side using a short-lived pseudonymous browser identifier.'
  },
  {
    id: 'guest-sync',
    category: 'account',
    question: 'What happens to my guest progress if I sign up or log in later?',
    answer: 'After you sign in, the game tries to sync this browser’s current daily-puzzle progress. Password registration first asks you to log in; Google registration signs you in directly. If your account already has progress for that puzzle, the account state takes precedence instead of merging both versions. Sync depends on browser storage and a successful request, and a failed sync can lose local progress. Flagdle syncs guesses, not question text. Do not rely on login to combine different attempts or guarantee a lossless transfer.'
  },
  {
    id: 'streaks-and-profile',
    category: 'account',
    question: 'How do daily streaks and leaderboards work?',
    answer: 'Daily-game leaderboards are separate by mode. Monthly rankings use points earned in the current UTC calendar month; all-time average rankings require at least 5 completed games in the original modes and Flagdle, or 3 in a continental mode. Streak bonuses reward consecutive days solved in the same mode. Rankings sort by points or average score, then wins; elapsed time affects the score rather than acting as a separate tie-break.'
  },
  {
    id: 'profile-coverage',
    category: 'account',
    question: 'Which games appear in my profile?',
    answer: 'Profiles cover all nine daily modes: Countrydle, Flagdle, the four continental modes, US Statedle, Województwodle, and Powiatdle. Choose a game to view its own points, wins, activity, win rate, streaks, averages, and completed-game history. Friend matches have a separate section with finished-match outcomes and no points or leaderboard ranking. Unreleased daily answers stay hidden.'
  },
  {
    id: 'remember-me',
    category: 'account',
    question: 'How does Remember me keep me signed in?',
    answer: 'Select Remember me before signing in with a password or Google. By default, the remembered session lasts for 90 days of inactivity, while ordinary login lasts 60 minutes. Authenticated requests renew the selected window; these durations can be changed by the server configuration. Logout clears the login cookie on this device. Clearing cookies or using private browsing can require another login. Use Remember me only on a private device.'
  },
  {
    id: 'privacy-and-cookies',
    category: 'account',
    question: 'What data and cookies does guest play use?',
    answer: 'Guest daily progress is stored in your browser, and accepted gameplay activity is also recorded on the server under a short-lived pseudonymous browser identifier. Account login uses an HttpOnly cookie. The site loads Google AdSense, and analytics such as Rybbit may be enabled by deployment settings. See the Privacy Policy and Cookie Policy for more information; guest play does not mean that all activity stays only on your device.'
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
          {t('faq.subtitle', 'Rules, modes, scoring, answer limitations, and account help.')}
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
