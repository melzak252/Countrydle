import { useState, useMemo } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
export interface FAQItem {
  id: string;
  category: 'gameplay' | 'modes' | 'data' | 'account';
  question: string;
  answer: string;
}

// Used by the visible FAQ and its page-specific structured data.
export const faqItems: FAQItem[] = [
  {
    id: 'how-it-works',
    category: 'gameplay',
    question: 'How does Countrydle work?',
    answer: 'Daily puzzles change at midnight UTC. Ask factual yes/no questions to narrow down the target, then submit a guess. Countrydle allows 10 questions and 3 guesses; each continental mode and US Statedle allow 8 and 3; Województwodle allows 5 and 2; Powiatdle allows 15 and 3. Flagdle is a flag-reveal challenge with 12 guesses and optional unlimited helper questions. Friend duels are live matches rather than daily puzzles.',
  },
  {
    id: 'valid-questions',
    category: 'gameplay',
    question: 'What kind of questions can I ask?',
    answer: 'Ask precise factual yes/no questions about geography, borders, physical features, demographics, or names. In Countrydle, direct identity questions and questions naming several candidate countries are allowed while the game is active and you have questions left. An accepted yes or no answer uses one question, not a guess. A yes answer does not win the game: submit the location in the guess field. Avoid vague criteria such as famous, nearby, or large without specifying what you mean.',
  },
  {
    id: 'typos-and-invalid',
    category: 'gameplay',
    question: 'Do typos or open-ended questions consume my question limit?',
    answer: 'Only a valid question with a resolved yes or no answer consumes a question. Invalid, undetermined, and failed requests do not use one. Open-ended requests such as "What is the capital?" are intended to be rejected, but question interpretation is not infallible. A typo may still be understood and accepted, in which case it counts normally. Read the feedback and rephrase when needed; a spelling mistake does not guarantee a free question.',
  },
  {
    id: 'scoring-and-limits',
    category: 'gameplay',
    question: 'How does scoring work and what happens when I run out of guesses?',
    answer: 'In the question-based daily modes, a win earns +500 base points, up to +1,500 for question efficiency, up to +500 for guess efficiency, up to +300 for speed over a 5-minute window, and +50 per consecutive day solved in that mode, capped at +500. Powiatdle adds +500 and US Statedle adds +200. Guest scores are previews; account streak bonuses use saved results. Flagdle has a separate formula. Running out of questions does not end a daily game while guesses remain: a correct guess or exhausting the guesses ends it.',
  },
  {
    id: 'game-modes',
    category: 'modes',
    question: 'Which game modes are available?',
    answer: 'There are nine daily modes: Countrydle (195 playable countries), Flagdle, Europedle, Asiadle, Africadle, Americadle, US Statedle (50 states), Województwodle (16 Polish voivodeships), and Powiatdle (380 Polish counties). The four continental modes focus on Europe, Asia, Africa, and the Americas. Play with a Friend offers separate live two-player duels.',
  },
  {
    id: 'flagdle',
    category: 'modes',
    question: 'How is Flagdle different?',
    answer: 'Flagdle asks you to identify a country from a partially revealed flag, with 12 guesses and more of the flag revealed after each guess. Optional yes/no helper questions have no total question budget and do not spend guesses; request-rate limits still apply. Its score uses +500 for a win, a guess bonus from +1,500 on the first guess to +50 on the twelfth, a speed bonus of up to +300 that decays over 3 minutes, and a streak bonus of up to +500. There is no question-efficiency scoring component.',
  },
  {
    id: 'friend-duels',
    category: 'modes',
    question: 'How do friend duels work? Are questions and guesses unlimited?',
    answer: 'Create an invite from Play with a Friend and share it with your opponent. Each player chooses a secret location. Take turns asking a question or making a guess; players answer each other’s questions. There is no total question or guess limit, but each action spends one turn and turn timers still apply. If the starting player solves first, the other player gets a final guess to draw or can pass. That final reply does not allow another question.',
  },
  {
    id: 'play-past-games',
    category: 'modes',
    question: 'Can I play previous daily puzzles?',
    answer: 'You can browse past answers, but the Archive does not replay past puzzles. It currently covers Countrydle, US Statedle, Województwodle, and Powiatdle, not all nine daily modes. Countrydle entries link to daily blog recaps. Open Archive from the navigation menu to see the available dates and solutions.',
  },
  {
    id: 'included-countries',
    category: 'data',
    question: 'What counts as a playable country or a continent in this game?',
    answer: 'The 195-country pool is a game catalog, not a list of only UN members or a statement about diplomatic recognition. Kosovo is included; Israel is currently excluded from playable targets and guesses without deleting its geography facts. Continental pools use stored physical-continent associations and eligibility rules: Europedle also excludes Azerbaijan, Kazakhstan, and Georgia; Asiadle also excludes Egypt. Americadle combines North and South America. A country can have more than one continent association. Choose from the current game suggestions rather than assuming every place shown on a map is playable.',
  },
  {
    id: 'data-sources',
    category: 'data',
    question: 'Where does Countrydle get its geography facts and maps?',
    answer: 'Sources vary by mode and field. Country facts combine REST Countries, CIA World Factbook profiles distributed through factbook.json, and curated additions. Regional facts use local article text and infoboxes, classification tables, static lists, and manual corrections. Some facts are extracted from Wikipedia text using AI. Maps use bundled boundary assets and Natural Earth-derived globe data, separately from the answer tables. These sources can contain errors or outdated information; they are not all direct official-statistics feeds.',
  },
  {
    id: 'hallucination-prevention',
    category: 'data',
    question: 'How are answers generated, and can they be wrong?',
    answer: 'Yes, answers can be wrong. Supported question templates can produce a local evaluation plan without an AI planner; other wording uses cached interpretations or AI planning. Local plans are evaluated against stored facts. Questions outside that coverage may use generative AI with retrieved article text or general knowledge. Incorrect interpretation, incomplete or outdated data, and AI fallback can all produce mistakes. Deterministic evaluation reduces some risks but does not guarantee factual truth. These answer services are distinct from friend duels, where players answer each other.',
  },
  {
    id: 'water-access',
    category: 'data',
    question: 'Does water access mean the same thing as being landlocked?',
    answer: 'Not always. Country water-access tables can include inland seas, while landlocked questions use marine access and exclude the Caspian, Aral, and Dead Seas. A river draining into a sea is not coastline access. Direct ocean coastline is different from a coast on a connected sea. In US Statedle, broad Atlantic access includes the Gulf of Mexico, but direct Atlantic coastline and East Coast are distinct. The mode guides explain these wording differences with examples.',
  },
  {
    id: 'historical-unions',
    category: 'data',
    question: 'Can I ask about historical blocs or former unions?',
    answer: 'Countrydle includes historical membership associations such as the USSR, Warsaw Pact, Yugoslavia, Gran Colombia, and the British and Spanish Empires. These are simplified associations, not a complete historical atlas. Ask about past membership separately from current membership, and specify a period when it matters. Coverage and interpretation can be incomplete, especially when borders or membership changed over time.',
  },
  {
    id: 'corrections',
    category: 'data',
    question: 'How can I report an incorrect answer or source?',
    answer: 'Use the Contact page or the question-report control where available. Include the mode, puzzle date, exact question, answer and explanation, and a source link supporting the correction. Avoid posting today’s hidden target publicly; past-day examples are easier to discuss without spoilers. A report is a request for review, not proof that the answer has already been corrected.',
  },
  {
    id: 'need-account',
    category: 'account',
    question: 'Do I need to create an account to play?',
    answer: 'No account is required for daily games or friend duels. Guest daily progress uses browser storage and server-side guest state; changing devices, clearing site data, or using private browsing can make it unavailable. Accepted guest gameplay activity is recorded using a short-lived pseudonymous browser identifier. Guest play is not a promise that all activity stays only on your device.',
  },
  {
    id: 'guest-sync',
    category: 'account',
    question: 'What happens to my guest progress if I sign up or log in later?',
    answer: 'After you sign in, the game tries to sync this browser’s current daily-puzzle progress. Password registration first asks you to log in; Google registration signs you in directly. If your account already has progress for that puzzle, the account state takes precedence instead of merging both attempts. Sync needs browser storage and a successful request; a failed request retains the local snapshot for retry. Do not rely on login to combine different attempts or transfer progress from another device.',
  },
  {
    id: 'streaks-and-profile',
    category: 'account',
    question: 'How do streaks, profiles and leaderboards work?',
    answer: 'Profiles and daily-game leaderboards cover all nine daily modes separately. Monthly rankings use points earned in the current UTC calendar month; all-time average rankings require at least 5 completed games in the original modes and Flagdle, or 3 in a continental mode. Streak bonuses reward consecutive days solved in the same mode. Rankings sort by points or average score, then wins; elapsed time affects the score rather than acting as a separate tie-break. Finished friend matches have their own profile section, without daily points or leaderboard ranking.',
  },
  {
    id: 'remember-me',
    category: 'account',
    question: 'How does Remember me keep me signed in?',
    answer: 'Select Remember me before signing in with a password or Google. By default, the remembered session lasts for 90 days of inactivity, while ordinary login lasts 60 minutes. Authenticated requests renew the selected window; these durations can be changed by server configuration. Logout clears the login cookie on this device. Clearing cookies or using private browsing can require another login. Use Remember me only on a private device.',
  },
  {
    id: 'privacy-and-cookies',
    category: 'account',
    question: 'What data and cookies does guest play use?',
    answer: 'Guest progress uses browser storage and server-side guest state. Account login uses an HttpOnly cookie. Advertising is limited to eligible publisher pages when enabled and when the configured consent service permits it; gameplay, results, account and contact screens are excluded. Analytics such as Rybbit may be enabled by deployment settings. See the Privacy Policy and Cookie Policy for details and privacy controls.',
  },
];


export default function FAQPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<'all' | 'gameplay' | 'modes' | 'data' | 'account'>('all');
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set(
    window.__COUNTRYDLE_PRERENDER__ ? faqItems.map(item => item.id) : ['how-it-works', 'valid-questions']
  ));

  const toggleItem = (id: string) => {
    setOpenIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredFAQs = useMemo(() => {
    return faqItems.filter(item => {
      const matchesCategory = activeCategory === 'all' || item.category === activeCategory;
      const matchesSearch = !search.trim() || 
        item.question.toLowerCase().includes(search.toLowerCase()) || 
        item.answer.toLowerCase().includes(search.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [search, activeCategory]);

  return (
    <div className="mx-auto max-w-4xl bg-obsidian-950 pb-8">
      <script
        id="countrydle-faq-schema"
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: filteredFAQs.map(item => ({
              '@type': 'Question',
              name: item.question,
              acceptedAnswer: { '@type': 'Answer', text: item.answer },
            })),
          }).replace(/</g, '\\u003c'),
        }}
      />
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
      <p className="mt-6 text-base leading-7 text-zinc-400">
        Read the <Link to="/explore/modes/countrydle" className="text-emerald-300 underline underline-offset-4">game conventions and worked examples</Link>,
        {' '}see <Link to="/about" className="text-emerald-300 underline underline-offset-4">our source inventory</Link>,
        {' '}or <Link to="/contact" className="text-emerald-300 underline underline-offset-4">send a question or correction</Link>.
        {' '}Privacy details are in the <Link to="/privacy-policy" className="text-emerald-300 underline underline-offset-4">Privacy Policy</Link>
        {' '}and <Link to="/cookie-policy" className="text-emerald-300 underline underline-offset-4">Cookie Policy</Link>.
      </p>
    </div>
  );
}
