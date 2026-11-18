import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  BookOpen, 
  Search, 
  Calendar, 
  Clock, 
  ArrowRight, 
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
        <header className="grid min-w-0 gap-4 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:gap-12">
          <div className="min-w-0">
            <h1 className="flex items-center gap-2 font-serif text-3xl leading-tight tracking-tight text-app-text md:text-5xl">
              <BookOpen size={24} className="shrink-0 text-app-accent" />
              {'Country journal'}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-app-text-secondary md:text-base">
              {'Explore past-day solutions, country-specific reasoning, community questions and sources recorded in the articles.'}
            </p>
          </div>
          <div className="min-w-0">
            <label htmlFor="journal-search" className="mb-2 block text-sm font-medium text-app-text-secondary">
              {'Search articles'}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-app-text-muted" size={18} />
              <input id="journal-search" type="search" value={search} onChange={(e) => setView({ search: e.target.value, page: 1 })}
                placeholder={'Country, fact or keyword…'}
                className="min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface py-3 pl-11 pr-4 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-1 focus:ring-app-focus" />
            </div>
          </div>
        </header>

        <div className="min-w-0 border-b border-app-border pb-4">
          <details className="rounded-sm border border-app-border bg-app-surface">
            <summary className="min-h-11 cursor-pointer px-4 py-3 text-sm font-medium text-app-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">
              {'Filters and sorting'}
            </summary>
            <div className="grid gap-4 border-t border-app-border p-4 sm:grid-cols-3">
              <label className="min-w-0 space-y-2 text-sm text-app-text-secondary">
                <span className="block">{'Continent'}</span>
                <select value={selectedContinent} onChange={(e) => setView({ continent: e.target.value, page: 1 })} className="min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-2 text-app-text focus:outline focus:outline-app-focus">
                  {continents.map((cont) => <option key={cont} value={cont}>{filterLabel(cont)}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-2 text-sm text-app-text-secondary">
                <span className="block">{'Difficulty'}</span>
                <select value={selectedDifficulty} onChange={(e) => setView({ difficulty: e.target.value, page: 1 })} className="min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-2 text-app-text focus:outline focus:outline-app-focus">
                  {difficulties.map((diff) => <option key={diff} value={diff}>{filterLabel(diff)}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-2 text-sm text-app-text-secondary">
                <span className="block">{'Sort by'}</span>
                <select value={sortBy} onChange={(e) => setView({ sort: e.target.value as typeof sortBy })} className="min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-2 text-app-text focus:outline focus:outline-app-focus">
                  {(['newest', 'solvers', 'fastest'] as const).map((sort) => <option key={sort} value={sort}>{filterLabel(sort)}</option>)}
                </select>
              </label>
            </div>
          </details>
          {hasActiveFilters && (
            <div className="mt-2 flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-app-text-secondary">
              <p role="status" className="min-w-0 flex-1 break-words">
                {'Active settings: '}
                {[search && `“${search}”`, selectedContinent !== 'all' && filterLabel(selectedContinent), selectedDifficulty !== 'all' && filterLabel(selectedDifficulty), sortBy !== 'newest' && filterLabel(sortBy)].filter(Boolean).join(' · ')}
              </p>
              <button type="button" onClick={resetFilters} className="min-h-11 rounded-sm px-3 text-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus">
                {'Reset'}
              </button>
            </div>
          )}
        </div>

        {error ? (
          <div role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-8 text-center text-amber-900">
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
              <article className="grid min-w-0 rounded-md border border-app-border bg-app-surface md:grid-cols-2">
                <Link
                  to={`/blog/${featuredPost.slug}`}
                  aria-label={featuredPost.title}
                  className="flex min-h-24 items-center justify-center rounded-t-md border-b border-app-border bg-app-surface-muted p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus md:min-h-80 md:rounded-t-none md:rounded-l-md md:border-b-0 md:border-r md:p-12"
                >
                  {featuredPost.country_code ? (
                    <img
                      src={`https://flagcdn.com/w640/${featuredPost.country_code.toLowerCase()}.png`}
                      alt={featuredPost.country_name}
                      className="max-h-16 w-full max-w-28 object-contain md:max-h-64 md:max-w-sm"
                    />
                  ) : (
                    <Globe size={80} strokeWidth={1} className="text-app-text-muted" />
                  )}
                </Link>
                <div className="flex min-w-0 flex-col justify-center p-4 sm:p-8 md:p-10">
                  <div className="mb-3 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 text-xs">
                    <span className="font-medium text-app-accent">
                      {'Most recent past-day recap'}
                    </span>
                    <span className="text-app-text-muted">/</span>
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
                      <span className="rounded-sm border border-app-border bg-app-surface-muted px-2 py-0.5 font-mono text-xs text-app-accent">
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
                    className="mt-4 inline-flex min-h-11 w-fit max-w-full items-center gap-3 text-sm font-medium text-app-accent transition-colors hover:text-app-accent-hover md:mt-7"
                  >
                    {'Read article'}
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </article>
            )}

            {regularPosts.length > 0 ? (
              <section>
                <div className="mb-6 flex items-center gap-4">
                  <h2 className="min-w-0 text-sm font-medium text-app-text-secondary">
                    {search ? ('Search results') : ('Earlier entries')}
                  </h2>
                  <div className="h-px flex-1 bg-app-border" />
                </div>
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {regularPosts.map((post) => (
                    <article key={post.id} className="group flex min-w-0 flex-col rounded-md border border-app-border bg-app-surface transition-colors hover:border-app-accent-hover">
                      <Link to={`/blog/${post.slug}`} aria-label={post.title} className="flex h-24 items-center justify-center rounded-t-md border-b border-app-border bg-app-surface-muted p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus sm:h-48 sm:p-7">
                        {post.country_code ? (
                          <img
                            src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                            alt={post.country_name}
                            loading="lazy"
                            className="max-h-full w-full max-w-28 object-contain sm:max-w-56"
                          />
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
                              post.difficulty === 'Easy' ? 'bg-emerald-50 text-emerald-800' :
                              post.difficulty === 'Challenging' ? 'bg-rose-50 text-rose-800' :
                              'bg-amber-50 text-amber-800'
                            }`}>
                              {filterLabel(post.difficulty)}
                            </span>
                          )}
                        </div>
                        <Link to={`/blog/${post.slug}`} className="mt-auto flex min-h-11 items-center justify-between gap-3 border-t border-app-border pt-4 text-sm font-medium text-app-accent transition-colors hover:text-app-accent-hover">
                          {'Read article'}
                          <ArrowRight size={15} />
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ) : (
              !featuredPost && (
                <div className="rounded-md border border-app-border bg-app-surface px-6 py-20 text-center">
                  <Globe size={36} strokeWidth={1} className="mx-auto mb-4 text-app-text-muted" />
                  <p className="text-base text-app-text-secondary">{'No articles match your search.'}</p>
                </div>
              )
            )}
            {total > limit && <nav aria-label="Journal pagination" className="flex items-center justify-center gap-5 text-sm text-app-text-secondary">
              <button type="button" disabled={page <= 1} onClick={() => setView({ page: page - 1 })} className="min-h-11 rounded-sm border border-app-border px-4 py-2 disabled:opacity-40">Previous</button>
              <span>Page {page} of {Math.max(1, Math.ceil(total / limit))}</span>
              <button type="button" disabled={page * limit >= total} onClick={() => setView({ page: page + 1 })} className="min-h-11 rounded-sm border border-app-border px-4 py-2 disabled:opacity-40">Next</button>
            </nav>}
          </>
        )}

        {eligible && <AdSenseUnit slot="blog-list-footer" className="max-w-xl mx-auto pt-6" />}
      </div>
    </div>
  );
}
