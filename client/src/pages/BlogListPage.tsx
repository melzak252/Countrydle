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
import { useTranslation } from 'react-i18next';
import AdSenseUnit from '../components/AdSenseUnit';
import { blogService } from '../services/api';
import { setPageEditorialEligibility } from '../advertising';
import { usePageMetadata } from '../lib/pageMetadata'
import { blogListSchema, type BlogSummary } from '../blogContent';
const continents = ['all', 'Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];
const difficulties = ['all', 'Easy', 'Medium', 'Challenging'];
type JournalView = { page: number; search: string; continent: string; difficulty: string; sort: 'newest' | 'solvers' | 'fastest' };
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
  const { t } = useTranslation();
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

  const filteredPosts = posts.filter((post) => {
    const matchesSearch = !search ||
      post.title.toLowerCase().includes(search.toLowerCase()) ||
      post.country_name.toLowerCase().includes(search.toLowerCase()) ||
      post.summary.toLowerCase().includes(search.toLowerCase());
    const matchesContinent = selectedContinent === 'all' || post.continent === selectedContinent;
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
    <div data-publisher-ready={!pending && !error ? 'true' : 'false'} data-publisher-error={error ? 'true' : undefined} className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-16">
      <div className="space-y-10 md:space-y-14">
        <header className="border-b border-white/10 pb-8 md:pb-10">
          <div className="mb-5 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-400">
            <BookOpen size={15} />
            {t('blog.badge', 'Daily Country Recaps & Trivia')}
          </div>
          <div className="grid gap-7 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:gap-16">
            <div>
              <h1 className="max-w-2xl font-serif text-4xl leading-[1.1] tracking-tight text-sand-100 sm:text-5xl md:text-6xl">
                {t('blog.title', 'Countrydle Daily Blog')}
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-7 text-zinc-400">
                Explore past-day mystery countries, country-specific reasoning and recorded community questions. Each recap labels its editorial status and available sources.
              </p>
            </div>
            <div>
              <label htmlFor="journal-search" className="mb-3 block text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
                {'Search the journal'}
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
                <input
                  id="journal-search"
                  type="search"
                  value={search}
                  onChange={(e) => setView({ search: e.target.value, page: 1 })}
                  placeholder={t('blog.searchPlaceholder', 'Search countries, facts, or keywords...')}
                  className="w-full rounded-md border border-white/15 bg-obsidian-900 py-3.5 pl-11 pr-4 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                />
              </div>
            </div>
          </div>
        </header>

        {/* Dynamic Filters & Controls */}
        <div className="flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              Continent:
            </span>
            {continents.map((cont) => (
              <button
                key={cont}
                type="button"
                onClick={() => setView({ continent: cont, page: 1 })}
                className={`min-h-11 rounded-sm px-2.5 py-1 text-xs font-medium transition-colors md:min-h-0 ${
                  selectedContinent === cont
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
                }`}
              >
                {cont === 'all' ? 'All' : cont}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                Difficulty:
              </span>
              {difficulties.map((diff) => (
                <button
                  key={diff}
                  type="button"
                  onClick={() => setView({ difficulty: diff, page: 1 })}
                  className={`min-h-11 rounded-sm px-2 py-0.5 text-xs transition-colors md:min-h-0 ${
                    selectedDifficulty === diff
                      ? 'bg-sand-100 text-obsidian-950 font-semibold'
                      : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {diff === 'all' ? 'All' : diff}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-1.5 border-l border-white/10 pl-3">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                Sort:
              </span>
              {(['newest', 'solvers', 'fastest'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setView({ sort: s })}
                  className={`min-h-11 rounded-sm px-2 py-0.5 text-xs capitalize transition-colors md:min-h-0 ${
                    sortBy === s
                      ? 'bg-emerald-400 text-obsidian-950 font-semibold'
                      : 'bg-white/5 text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error ? (
          <div role="alert" className="rounded-lg border border-amber-500/30 bg-obsidian-900 p-8 text-center text-zinc-300">
            <p>{error}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 rounded border border-white/20 px-4 py-2">Try again</button>
          </div>
        ) : pending ? (
          <div role="status" aria-label={'Loading articles'} className="flex justify-center py-24">
            <Loader2 className="animate-spin text-emerald-400" size={32} />
          </div>
        ) : (
          <>
            {featuredPost && (
              <article className="grid overflow-hidden rounded-lg border border-white/10 bg-obsidian-900 md:grid-cols-2">
                <Link
                  to={`/blog/${featuredPost.slug}`}
                  aria-label={featuredPost.title}
                  className="flex min-h-56 items-center justify-center border-b border-white/10 bg-obsidian-950 p-8 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 md:min-h-80 md:border-b-0 md:border-r md:p-12"
                >
                  {featuredPost.country_code ? (
                    <img
                      src={`https://flagcdn.com/w640/${featuredPost.country_code.toLowerCase()}.png`}
                      alt={featuredPost.country_name}
                      className="max-h-64 w-full max-w-sm object-contain"
                    />
                  ) : (
                    <Globe size={80} strokeWidth={1} className="text-zinc-600" />
                  )}
                </Link>
                <div className="flex flex-col justify-center p-6 sm:p-8 md:p-10">
                  <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs">
                    <span className="font-medium uppercase tracking-[0.14em] text-emerald-400">
                      Most recent past-day recap
                    </span>
                    <span className="text-zinc-500">/</span>
                    <span className="text-zinc-400">{featuredPost.country_name}</span>
                  </div>
                  <h2 className="font-serif text-3xl leading-tight tracking-tight text-sand-100 lg:text-4xl">
                    <Link to={`/blog/${featuredPost.slug}`} className="transition-colors hover:text-emerald-300">
                      {featuredPost.title}
                    </Link>
                  </h2>
                  <p className="mt-4 text-sm leading-7 text-zinc-400">{featuredPost.summary}</p>
                  <p className="mt-3 text-xs text-zinc-400">{featuredPost.editorial_status === 'reviewed' ? 'Editorially reviewed' : 'Not yet editorially reviewed'} · Updated <time dateTime={featuredPost.updated_at || featuredPost.created_at}>{featuredPost.updated_at || featuredPost.created_at}</time></p>
                  <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-400">
                    <span className="inline-flex items-center gap-1.5"><Calendar size={13} />{featuredPost.date}</span>
                    <span className="inline-flex items-center gap-1.5"><Clock size={13} />{featuredPost.reading_time_minutes} {t('blog.minRead', 'min read')}</span>
                    {featuredPost.continent && (
                      <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-400 border border-emerald-500/20">
                        {featuredPost.continent}
                      </span>
                    )}
                    {featuredPost.difficulty && (
                      <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                        {featuredPost.difficulty}
                      </span>
                    )}
                  </div>
                  <Link
                    to={`/blog/${featuredPost.slug}`}
                    className="mt-7 inline-flex w-fit items-center gap-3 border-b border-emerald-400/40 pb-1 text-sm font-medium text-emerald-400 transition-colors hover:border-emerald-300 hover:text-emerald-300"
                  >
                    {t('blog.readArticle', 'Read Full Post')}
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </article>
            )}

            {regularPosts.length > 0 ? (
              <section>
                <div className="mb-6 flex items-center gap-4">
                  <h2 className="shrink-0 text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
                    {search ? ('Search results') : ('Earlier entries')}
                  </h2>
                  <div className="h-px flex-1 bg-white/10" />
                </div>
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {regularPosts.map((post) => (
                    <article key={post.id} className="group flex flex-col overflow-hidden rounded-lg border border-white/10 bg-obsidian-900 transition-colors hover:border-white/25">
                      <Link to={`/blog/${post.slug}`} aria-label={post.title} className="flex h-48 items-center justify-center border-b border-white/10 bg-obsidian-950 p-7 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
                        {post.country_code ? (
                          <img
                            src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                            alt={post.country_name}
                            loading="lazy"
                            className="max-h-full w-full max-w-56 object-contain"
                          />
                        ) : (
                          <Globe size={56} strokeWidth={1} className="text-zinc-600" />
                        )}
                      </Link>
                      <div className="flex flex-1 flex-col p-6">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-emerald-400">{post.country_name}</p>
                          {post.continent && (
                            <span className="font-mono text-[10px] text-zinc-500">{post.continent}</span>
                          )}
                        </div>
                        <h3 className="font-serif text-2xl leading-snug text-sand-100">
                          <Link to={`/blog/${post.slug}`} className="transition-colors hover:text-emerald-300">{post.title}</Link>
                        </h3>
                        <p className="mt-3 text-sm leading-relaxed text-zinc-400">{post.summary}</p>
                        <p className="mt-3 text-xs text-zinc-400">{post.editorial_status === 'reviewed' ? 'Editorially reviewed' : 'Not yet editorially reviewed'} · Updated <time dateTime={post.updated_at || post.created_at}>{post.updated_at || post.created_at}</time></p>
                        <div className="mb-5 mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-500">
                          <span>{post.date}</span>
                          <span>{post.reading_time_minutes} min</span>
                          {post.difficulty && (
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              post.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400' :
                              post.difficulty === 'Challenging' ? 'bg-rose-500/10 text-rose-400' :
                              'bg-amber-500/10 text-amber-400'
                            }`}>
                              {post.difficulty}
                            </span>
                          )}
                        </div>
                        <Link to={`/blog/${post.slug}`} className="mt-auto flex items-center justify-between gap-3 border-t border-white/10 pt-4 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300">
                          {t('blog.readArticle', 'Read Full Post')}
                          <ArrowRight size={15} />
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ) : (
              !featuredPost && (
                <div className="rounded-lg border border-white/10 bg-obsidian-900 px-6 py-20 text-center">
                  <Globe size={36} strokeWidth={1} className="mx-auto mb-4 text-zinc-600" />
                  <p className="text-base text-zinc-400">{t('blog.noPosts', 'No daily blog posts found matching your search.')}</p>
                </div>
              )
            )}
            {total > limit && <nav aria-label="Journal pagination" className="flex items-center justify-center gap-5 text-sm text-zinc-300">
              <button type="button" disabled={page <= 1} onClick={() => setView({ page: page - 1 })} className="rounded border border-white/20 px-4 py-2 disabled:opacity-40">Previous</button>
              <span>Page {page} of {Math.max(1, Math.ceil(total / limit))}</span>
              <button type="button" disabled={page * limit >= total} onClick={() => setView({ page: page + 1 })} className="rounded border border-white/20 px-4 py-2 disabled:opacity-40">Next</button>
            </nav>}
          </>
        )}

        {eligible && <AdSenseUnit slot="blog-list-footer" className="max-w-xl mx-auto pt-6" />}
      </div>
    </div>
  );
}
