import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  BookOpen, 
  Search, 
  Calendar, 
  Clock, 
  ArrowRight, 
  Compass,
  Globe, 
  Loader2
} from 'lucide-react';
import AdSenseUnit from '../components/AdSenseUnit';
import { blogService } from '../services/api';
import { setPageEditorialEligibility } from '../advertising';
import { usePageMetadata } from '../lib/pageMetadata'
import { blogListSchema, type BlogSummary } from '../blogContent';
const continents = ['all', 'Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];
const difficulties = ['all', 'Easy', 'Medium', 'Challenging'];
type JournalView = { page: number; search: string; continent: string; difficulty: string; sort: 'newest' | 'solvers' | 'fastest' };
function formatBlogDate(dateStr: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (!match) return dateStr;
  const utcDate = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (Number.isNaN(utcDate.getTime())) return dateStr;
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(utcDate);
}
function requestedView(): JournalView {
  const params = new URLSearchParams(window.__COUNTRYDLE_PRERENDER__ ? '' : window.location.hash.slice(1));
  const page = Number(params.get('page') || 1);
  const continent = params.get('continent') || 'all';
  const difficulty = params.get('difficulty') || 'all';
  const sort = params.get('sort');
  return {
    page: Number.isSafeInteger(page) && page > 0 ? page : 1, search: params.get('q') || '',
    continent: continents.includes(continent) ? continent : 'all',
    difficulty: difficulties.includes(difficulty) ? difficulty : 'all',
    sort: sort === 'solvers' || sort === 'fastest' ? sort : 'newest',
  };
}
function rememberView(view: JournalView) {
  const params = new URLSearchParams();
  if (view.page > 1) params.set('page', String(view.page));
  if (view.search) params.set('q', view.search);
  if (view.continent !== 'all') params.set('continent', view.continent);
  if (view.difficulty !== 'all') params.set('difficulty', view.difficulty);
  if (view.sort !== 'newest') params.set('sort', view.sort);
  const hash = params.toString();
  const url = window.location.pathname + window.location.search + (hash ? `#${hash}` : '');
  // Persist before any eligibility effect can unload the advertising document.
  if (url !== window.location.pathname + window.location.search + window.location.hash) window.history.pushState(window.history.state, '', url);
}
export default function BlogListPage() {
  const [posts, setPosts] = useState<BlogSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, updateView] = useState<JournalView>(requestedView);
  const { page, search, continent: selectedContinent, difficulty: selectedDifficulty, sort: sortBy } = view;
  const setView = (change: Partial<JournalView>) => {
    const next = { ...view, ...change };
    rememberView(next);
    updateView(next);
  };
  const [error, setError] = useState<string | null>(null);
  const [loadedRequest, setLoadedRequest] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const limit = 24;
  const requestKey = JSON.stringify([page, search]);
  useEffect(() => {
    const restoreView = () => updateView(requestedView());
    window.addEventListener('popstate', restoreView);
    window.addEventListener('hashchange', restoreView);
    return () => {
      window.removeEventListener('popstate', restoreView);
      window.removeEventListener('hashchange', restoreView);
    };
  }, []);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let isMounted = true;
    setPageEditorialEligibility(false);
    setLoading(true);
    setError(null);
    const fetchPosts = async () => {
      setLoading(true);
      try {
        const data = blogListSchema.parse(await blogService.getPosts(page, limit, search));
        if (data.posts.some((post) => post.date >= new Date().toISOString().slice(0, 10))) throw new Error('Invalid public recap dates.');
        if (isMounted) {
          setPosts(data.posts);
          setTotal(data.total);
          setLoadedRequest(requestKey);
        }
      } catch {
        if (isMounted) {
          setPosts([]);
          setError('The journal could not be loaded. Please try again.');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    const timeoutId = setTimeout(fetchPosts, search ? 300 : 0);
    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
      setPageEditorialEligibility(false);
    };
  }, [page, search, retry, requestKey]);

  const filterLabel = (value: string): string => {
    return value === 'all' ? 'All' : value === 'newest' ? 'Newest' : value === 'solvers' ? 'Most solved' : value === 'fastest' ? 'Fastest' : value;
  };
  const hasActiveFilters = Boolean(search || selectedContinent !== 'all' || selectedDifficulty !== 'all' || sortBy !== 'newest');
  const resetFilters = () => {
    setView({ search: '', continent: 'all', difficulty: 'all', sort: 'newest', page: 1 });
  };
  const filteredPosts = posts.filter((post) => {
    const matchesSearch = !search ||
      post.title.toLowerCase().includes(search.toLowerCase()) ||
      post.country_name.toLowerCase().includes(search.toLowerCase()) ||
      post.summary.toLowerCase().includes(search.toLowerCase());
    const matchesContinent = selectedContinent === 'all' || post.continent === selectedContinent ||
      (selectedContinent === 'Americas' && (post.continent === 'North America' || post.continent === 'South America'));
    const matchesDifficulty = selectedDifficulty === 'all' || post.difficulty === selectedDifficulty;
    return matchesSearch && matchesContinent && matchesDifficulty;
  }).sort((a, b) => {
    if (sortBy === 'solvers') return (b.total_players || 0) - (a.total_players || 0);
    if (sortBy === 'fastest') return (a.reading_time_minutes || 2) - (b.reading_time_minutes || 2);
    return new Date(b.date).getTime() - new Date(a.date).getTime();
  });

  const featuredPost = page === 1 && filteredPosts.length > 0 && !search && selectedContinent === 'all' && selectedDifficulty === 'all'
    ? filteredPosts[0]
    : null;
  const regularPosts = featuredPost ? filteredPosts.slice(1) : filteredPosts;
  const pending = loading || loadedRequest !== requestKey;
  const eligible = !pending && !error && filteredPosts.some((post) =>
    post.editorial_status === 'reviewed' && post.title.trim().length > 0 && post.summary.trim().length > 0);
  useEffect(() => {
    setPageEditorialEligibility(eligible);
    return () => setPageEditorialEligibility(false);
  }, [eligible, search]);
  usePageMetadata({
    title: error ? 'Journal unavailable | Countrydle' : 'Past-day country recaps and deduction journal | Countrydle',
    description: error ? 'The Countrydle journal is temporarily unavailable.' : 'Explore past Countrydle solutions, country-specific deduction paths, community question evidence and recorded sources.',
    canonicalPath: '/blog',
    noindex: !!error || pending || posts.length === 0,
  });
  return (
    <div data-publisher-ready={!pending && !error ? 'true' : 'false'} data-publisher-error={error ? 'true' : undefined} className="mx-auto min-w-0 max-w-6xl bg-app-canvas py-4 text-app-text [overflow-wrap:anywhere] md:py-10">
      <div className="space-y-6 md:space-y-10">
        <header className="grid min-w-0 gap-4 border-b border-app-border pb-6 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:gap-12">
          <div className="min-w-0">
            <div className="mb-3 inline-flex items-center gap-2 rounded-sm border border-app-border/70 bg-app-surface-muted/80 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-app-accent">
              <Compass size={13} aria-hidden="true" />
              <span>Field Notes · Country Journal</span>
            </div>
            <h1 className="flex items-center gap-2.5 font-serif text-3xl leading-tight tracking-tight text-app-text md:text-5xl">
              <BookOpen size={26} className="shrink-0 text-app-accent" aria-hidden="true" />
              <span>Country journal</span>
            </h1>
            <p className="mt-2.5 max-w-2xl text-sm leading-6 text-app-text-secondary md:text-base">
              {'Explore past-day solutions, country-specific reasoning, community questions and sources recorded in the articles.'}
            </p>
          </div>
          <div className="min-w-0">
            <label htmlFor="journal-search" className="mb-2 block font-mono text-[11px] uppercase tracking-wider text-app-text-muted">
              {'Search dispatches'}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-app-text-muted" size={17} />
              <input id="journal-search" type="search" value={search} onChange={(e) => setView({ search: e.target.value, page: 1 })}
                placeholder={'Country, fact or keyword…'}
                className="min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface py-2.5 pl-10 pr-4 text-sm text-app-text placeholder:text-app-text-muted shadow-[inset_0_1px_2px_rgba(85,75,57,0.06)] focus:border-app-accent focus:outline-none focus:ring-1 focus:ring-app-focus" />
            </div>
          </div>
        </header>

        <div className="min-w-0 space-y-3 border-b border-app-border pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by continent">
              {continents.map((cont) => (
                <button
                  key={cont}
                  type="button"
                  onClick={() => setView({ continent: cont, page: 1 })}
                  className={`rounded-sm border px-2.5 py-1.5 font-mono text-xs transition-colors cursor-pointer ${
                    selectedContinent === cont
                      ? 'border-app-accent bg-app-accent text-app-canvas font-semibold'
                      : 'border-app-border bg-app-surface text-app-text-secondary hover:border-app-accent hover:bg-app-surface-muted hover:text-app-text'
                  }`}
                >
                  {filterLabel(cont)}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <select
                aria-label="Difficulty"
                value={selectedDifficulty}
                onChange={(e) => setView({ difficulty: e.target.value, page: 1 })}
                className="min-h-9 rounded-sm border border-app-border bg-app-surface px-2.5 py-1.5 text-app-text focus:border-app-accent focus:outline-none"
              >
                {difficulties.map((diff) => <option key={diff} value={diff}>{diff === 'all' ? 'All difficulties' : filterLabel(diff)}</option>)}
              </select>
              <select
                aria-label="Sort by"
                value={sortBy}
                onChange={(e) => setView({ sort: e.target.value as typeof sortBy })}
                className="min-h-9 rounded-sm border border-app-border bg-app-surface px-2.5 py-1.5 text-app-text focus:border-app-accent focus:outline-none"
              >
                {(['newest', 'solvers', 'fastest'] as const).map((sort) => <option key={sort} value={sort}>{`Sort: ${filterLabel(sort)}`}</option>)}
              </select>
            </div>
          </div>
          {hasActiveFilters && (
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-app-text-secondary">
              <p role="status" className="min-w-0 flex-1 break-words font-mono">
                {'Active filters: '}
                {[search && `“${search}”`, selectedContinent !== 'all' && filterLabel(selectedContinent), selectedDifficulty !== 'all' && filterLabel(selectedDifficulty), sortBy !== 'newest' && filterLabel(sortBy)].filter(Boolean).join(' · ')}
              </p>
              <button type="button" onClick={resetFilters} className="rounded-sm px-2.5 py-1 font-semibold text-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">
                {'Reset'}
              </button>
            </div>
          )}
        </div>

        {error ? (
          <div role="alert" className="rounded-sm border border-amber-300 bg-amber-50 p-8 text-center text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/60 dark:text-amber-200">
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 min-h-11 rounded-sm border border-app-border px-4 py-2 text-app-text">Try again</button>
          </div>
        ) : pending ? (
          <div role="status" aria-label={'Loading articles'} className="flex justify-center py-24">
            <Loader2 className="animate-spin text-app-accent" size={32} />
          </div>
        ) : (
          <>
            {featuredPost && (
              <motion.article
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                className="relative grid min-w-0 rounded-sm border border-app-border bg-app-surface shadow-[0_3px_14px_rgba(85,75,57,0.06)] md:grid-cols-2"
              >
                <span aria-hidden="true" className="pointer-events-none absolute left-2 top-2 h-2.5 w-2.5 border-l border-t border-app-accent/60" />
                <span aria-hidden="true" className="pointer-events-none absolute right-2 top-2 h-2.5 w-2.5 border-r border-t border-app-accent/60" />
                <span aria-hidden="true" className="pointer-events-none absolute bottom-2 left-2 h-2.5 w-2.5 border-b border-l border-app-accent/60" />
                <span aria-hidden="true" className="pointer-events-none absolute bottom-2 right-2 h-2.5 w-2.5 border-b border-r border-app-accent/60" />

                <Link
                  to={`/blog/${featuredPost.slug}`}
                  aria-label={featuredPost.title}
                  className="flex min-h-28 items-center justify-center rounded-t-sm border-b border-app-border bg-app-surface-muted/80 p-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus md:min-h-80 md:rounded-t-none md:rounded-l-sm md:border-b-0 md:border-r md:p-10"
                >
                  {featuredPost.country_code ? (
                    <span className="inline-flex items-center justify-center rounded-sm border border-app-border bg-app-surface-raised p-3 shadow-sm">
                      <img
                        src={`https://flagcdn.com/w640/${featuredPost.country_code.toLowerCase()}.png`}
                        alt={featuredPost.country_name}
                        className="max-h-20 w-full max-w-32 object-contain md:max-h-56 md:max-w-xs"
                      />
                    </span>
                  ) : (
                    <Globe size={80} strokeWidth={1} className="text-app-text-muted" />
                  )}
                </Link>
                <div className="flex min-w-0 flex-col justify-center p-5 sm:p-8 md:p-10">
                  <div className="mb-3 flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-2 font-mono text-[11px] uppercase tracking-wider">
                    <span className="rounded-sm border border-app-accent/30 bg-app-accent/10 px-2 py-0.5 font-semibold text-app-accent">
                      {'Latest dispatch'}
                    </span>
                    <span className="text-app-text-muted">·</span>
                    <span className="text-app-text-secondary">{featuredPost.country_name}</span>
                  </div>
                  <h2 className="min-w-0 break-words font-serif text-2xl leading-tight tracking-tight text-app-text md:text-3xl lg:text-4xl">
                    <Link to={`/blog/${featuredPost.slug}`} className="transition-colors hover:text-app-accent">
                      {featuredPost.title}
                    </Link>
                  </h2>
                  <p className="mt-4 text-sm leading-7 text-app-text-secondary">{featuredPost.summary}</p>
                  <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-app-text-secondary">
                    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5"><Calendar size={13} className="shrink-0" /><time dateTime={featuredPost.date} className="min-w-0 break-words">{formatBlogDate(featuredPost.date)}</time></span>
                    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5"><Clock size={13} className="shrink-0" /><span className="min-w-0 break-words">{featuredPost.reading_time_minutes} {'min read'}</span></span>
                    {featuredPost.continent && (
                      <span className="rounded-sm border border-emerald-200 bg-emerald-50 px-2 py-0.5 font-mono text-xs text-emerald-800 dark:border-emerald-700/50 dark:bg-emerald-950/60 dark:text-emerald-200">
                        {filterLabel(featuredPost.continent)}
                      </span>
                    )}
                    {featuredPost.difficulty && (
                      <span className="rounded-sm bg-app-surface-muted px-2 py-0.5 font-mono text-xs text-app-text-secondary">
                        {filterLabel(featuredPost.difficulty)}
                      </span>
                    )}
                  </div>
                  <Link
                    to={`/blog/${featuredPost.slug}`}
                    className="mt-5 inline-flex min-h-11 w-fit max-w-full items-center gap-2.5 rounded-sm border border-app-accent bg-app-accent px-4 py-2 text-sm font-semibold text-app-canvas transition-colors hover:bg-app-accent-hover md:mt-7"
                  >
                    <span>{'Read dispatch'}</span>
                    <ArrowRight size={15} />
                  </Link>
                </div>
              </motion.article>
            )}

            {regularPosts.length > 0 ? (
              <section className="cartography-desk-mat rounded-sm border border-[#c7b896] p-4 shadow-[inset_0_2px_10px_rgba(85,75,57,0.08)] dark:border-app-border sm:p-6 md:p-8">
                <div className="mb-6 flex items-center gap-4">
                  <h2 className="min-w-0 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#554b39] dark:text-app-text-secondary">
                    {search ? ('Search results') : ('Pinned field dispatches')}
                  </h2>
                  <div className="h-px flex-1 bg-[#bfb08f] dark:bg-app-border" />
                </div>
                <div className="grid grid-cols-1 gap-7 sm:grid-cols-2 lg:grid-cols-3">
                  {regularPosts.map((post, idx) => {
                    const noteStyles = [
                      { card: 'bg-[#fdf7e4] border-[#d3c095] dark:bg-[#1c2329] dark:border-[#49555e] -rotate-[0.8deg]', pin: 'bg-[#a84436] ring-[#f7d8d2] dark:ring-[#3d2522]' },
                      { card: 'bg-[#f4f7ed] border-[#bcc9b0] dark:bg-[#192421] dark:border-[#3c5648] rotate-[0.7deg]', pin: 'bg-[#2a5942] ring-[#d4e7dc] dark:ring-[#1f362a]' },
                      { card: 'bg-[#faf1de] border-[#d4ba8c] dark:bg-[#1b222c] dark:border-[#415062] -rotate-[0.5deg]', pin: 'bg-[#355c7d] ring-[#d5e3ef] dark:ring-[#233242]' },
                      { card: 'bg-[#fcf5ea] border-[#ccb999] dark:bg-[#23201a] dark:border-[#584c38] rotate-[0.4deg]', pin: 'bg-[#9a6b2f] ring-[#efe2cc] dark:ring-[#3a3021]' },
                    ];
                    const style = noteStyles[idx % noteStyles.length];
                    return (
                    <motion.article
                      key={post.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      whileHover={{ y: -4, rotate: 0 }}
                      transition={{ type: 'spring', stiffness: 320, damping: 24, delay: idx * 0.04 }}
                      className={`group relative flex min-w-0 flex-col rounded-sm border ${style.card} shadow-[3px_6px_16px_rgba(68,56,36,0.14)] hover:border-app-accent hover:shadow-[5px_12px_26px_rgba(68,56,36,0.20)]`}
                    >
                      {/* Colored enamel pushpin */}
                      <span
                        aria-hidden="true"
                        className={`pointer-events-none absolute -top-2 left-1/2 z-10 h-3.5 w-3.5 -translate-x-1/2 rounded-full ${style.pin} ring-2 shadow-[0_2px_4px_rgba(0,0,0,0.28)]`}
                      />
                      <Link to={`/blog/${post.slug}`} aria-label={post.title} className="flex h-28 items-center justify-center rounded-t-sm border-b border-app-border/60 bg-app-surface-muted/60 p-4 pt-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus sm:h-48 sm:p-6">
                        {post.country_code ? (
                          <span className="inline-flex h-full max-h-36 items-center justify-center rounded-sm border border-app-border bg-app-surface-raised p-2 shadow-xs">
                            <img
                              src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                              alt={post.country_name}
                              loading="lazy"
                              className="max-h-full w-full max-w-28 object-contain sm:max-w-48"
                            />
                          </span>
                        ) : (
                          <Globe size={56} strokeWidth={1} className="text-app-text-muted" />
                        )}
                      </Link>
                      <div className="flex min-w-0 flex-1 flex-col p-4 sm:p-6">
                        <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
                        <p className="min-w-0 break-words text-xs font-medium text-app-accent">{post.country_name}</p>
                          {post.continent && (
                            <span className="text-xs text-app-text-muted">{filterLabel(post.continent)}</span>
                          )}
                        </div>
                        <h3 className="min-w-0 break-words font-serif text-2xl leading-snug text-app-text">
                          <Link to={`/blog/${post.slug}`} className="transition-colors hover:text-app-accent">{post.title}</Link>
                        </h3>
                        <p className="mt-3 text-sm leading-relaxed text-app-text-secondary">{post.summary}</p>
                        <div className="mb-5 mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-app-text-muted">
                          <time dateTime={post.date}>{formatBlogDate(post.date)}</time>
                          <span>{post.reading_time_minutes} min</span>
                          {post.difficulty && (
                            <span className={`rounded-sm px-1.5 py-0.5 text-xs font-mono ${
                              post.difficulty === 'Easy' ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200' :
                              post.difficulty === 'Challenging' ? 'bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-200' :
                              'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-200'
                            }`}>
                              {filterLabel(post.difficulty)}
                            </span>
                          )}
                        </div>
                        <Link to={`/blog/${post.slug}`} className="mt-auto flex min-h-11 items-center justify-between gap-3 border-t border-app-border pt-4 text-sm font-medium text-app-accent transition-colors hover:text-app-accent-hover">
                          {'Read dispatch'}
                          <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
                        </Link>
                      </div>
                    </motion.article>
                    );
                  })}
                </div>
              </section>
            ) : (
              !featuredPost && (
                <div className="rounded-sm border border-app-border bg-app-surface px-6 py-20 text-center">
                  <Globe size={36} strokeWidth={1} className="mx-auto mb-4 text-app-text-muted" />
                  <p className="text-base text-app-text">{'No articles match your search.'}</p>
                </div>
              )
            )}
            {total > limit && <nav aria-label="Journal pagination" className="flex items-center justify-center gap-5 text-sm text-app-text-secondary">
              <button type="button" disabled={page <= 1} onClick={() => setView({ page: page - 1 })} className="min-h-11 rounded-sm border border-app-border bg-app-surface px-4 py-2 text-app-text transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:opacity-40">Previous</button>
              <span>Page {page} of {Math.max(1, Math.ceil(total / limit))}</span>
              <button type="button" disabled={page * limit >= total} onClick={() => setView({ page: page + 1 })} className="min-h-11 rounded-sm border border-app-border bg-app-surface px-4 py-2 text-app-text transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:opacity-40">Next</button>
            </nav>}
          </>
        )}

        {eligible && <AdSenseUnit slot="blog-list-footer" className="max-w-xl mx-auto pt-6" />}
      </div>
    </div>
  );
}
