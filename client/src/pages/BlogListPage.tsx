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
import type { BlogPostSummary } from '../types/blog';
export default function BlogListPage() {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const [posts, setPosts] = useState<BlogPostSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedContinent, setSelectedContinent] = useState<string>('all');
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'newest' | 'solvers' | 'fastest'>('newest');
  useEffect(() => {
    let isMounted = true;
    const fetchPosts = async () => {
      setLoading(true);
      try {
        const data = await blogService.getPosts(1, 24, search);
        if (isMounted) {
          setPosts(data.posts || []);
        }
      } catch (err) {
        console.error('Failed to fetch blog posts', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    const timeoutId = setTimeout(fetchPosts, search ? 300 : 0);
    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
    };
  }, [search]);

  const continents = ['all', 'Africa', 'Americas', 'Asia', 'Europe', 'Oceania'];
  const difficulties = ['all', 'Easy', 'Medium', 'Challenging'];

  const filterLabel = (value: string): string => {
    const labels: Record<string, string> = {
      all: 'Wszystkie', Africa: 'Afryka', Americas: 'Ameryki', Asia: 'Azja',
      'North America': 'Ameryka Północna', 'South America': 'Ameryka Południowa',
      Europe: 'Europa', Oceania: 'Oceania', Easy: 'Łatwy', Medium: 'Średni',
      Challenging: 'Trudny', newest: 'Najnowsze', solvers: 'Najwięcej rozwiązań', fastest: 'Najszybsze',
    };
    return isPl ? labels[value] || value : value === 'all' ? 'All' : value === 'newest' ? 'Newest' : value === 'solvers' ? 'Most solved' : value === 'fastest' ? 'Fastest' : value;
  };
  const hasActiveFilters = Boolean(search || selectedContinent !== 'all' || selectedDifficulty !== 'all' || sortBy !== 'newest');
  const resetFilters = () => {
    setSearch('');
    setSelectedContinent('all');
    setSelectedDifficulty('all');
    setSortBy('newest');
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

  const featuredPost = filteredPosts.length > 0 && !search && selectedContinent === 'all' && selectedDifficulty === 'all'
    ? filteredPosts[0]
    : null;
  const regularPosts = featuredPost ? filteredPosts.slice(1) : filteredPosts;
  return (
    <div className="mx-auto min-w-0 max-w-6xl py-4 [overflow-wrap:anywhere] md:py-10">
      <div className="space-y-6 md:space-y-10">
        <header className="grid min-w-0 gap-4 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:gap-12">
          <div className="min-w-0">
            <h1 className="flex items-center gap-2 font-serif text-3xl leading-tight tracking-tight text-sand-100 md:text-5xl">
              <BookOpen size={24} className="shrink-0 text-emerald-400" />
              {isPl ? 'Dziennik krajów' : 'Country journal'}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400 md:text-base">
              {isPl ? 'Poznaj ostatnie rozwiązania, ciekawostki i wskazówki.' : 'Discover recent solutions, country stories and deduction tips.'}
            </p>
          </div>
          <div className="min-w-0">
            <label htmlFor="journal-search" className="mb-2 block text-sm font-medium text-zinc-300">
              {isPl ? 'Szukaj artykułów' : 'Search articles'}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
              <input id="journal-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder={isPl ? 'Kraj, fakt lub słowo kluczowe…' : 'Country, fact or keyword…'}
                className="min-h-11 w-full min-w-0 rounded-md border border-white/15 bg-obsidian-900 py-3 pl-11 pr-4 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400" />
            </div>
          </div>
        </header>

        <div className="min-w-0 border-b border-white/10 pb-4">
          <details className="rounded-md border border-white/10 bg-obsidian-900/60">
            <summary className="min-h-11 cursor-pointer px-4 py-3 text-sm font-medium text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
              {isPl ? 'Filtry i sortowanie' : 'Filters and sorting'}
            </summary>
            <div className="grid gap-4 border-t border-white/10 p-4 sm:grid-cols-3">
              <label className="min-w-0 space-y-2 text-sm text-zinc-400">
                <span className="block">{isPl ? 'Kontynent' : 'Continent'}</span>
                <select value={selectedContinent} onChange={(e) => setSelectedContinent(e.target.value)} className="min-h-11 w-full min-w-0 rounded border border-white/15 bg-obsidian-950 px-2 text-sand-100 focus:outline-emerald-400">
                  {continents.map((cont) => <option key={cont} value={cont}>{filterLabel(cont)}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-2 text-sm text-zinc-400">
                <span className="block">{isPl ? 'Trudność' : 'Difficulty'}</span>
                <select value={selectedDifficulty} onChange={(e) => setSelectedDifficulty(e.target.value)} className="min-h-11 w-full min-w-0 rounded border border-white/15 bg-obsidian-950 px-2 text-sand-100 focus:outline-emerald-400">
                  {difficulties.map((diff) => <option key={diff} value={diff}>{filterLabel(diff)}</option>)}
                </select>
              </label>
              <label className="min-w-0 space-y-2 text-sm text-zinc-400">
                <span className="block">{isPl ? 'Sortowanie' : 'Sort by'}</span>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="min-h-11 w-full min-w-0 rounded border border-white/15 bg-obsidian-950 px-2 text-sand-100 focus:outline-emerald-400">
                  {(['newest', 'solvers', 'fastest'] as const).map((sort) => <option key={sort} value={sort}>{filterLabel(sort)}</option>)}
                </select>
              </label>
            </div>
          </details>
          {hasActiveFilters && (
            <div className="mt-2 flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-zinc-400">
              <p role="status" className="min-w-0 flex-1 break-words">
                {isPl ? 'Aktywne ustawienia: ' : 'Active settings: '}
                {[search && `“${search}”`, selectedContinent !== 'all' && filterLabel(selectedContinent), selectedDifficulty !== 'all' && filterLabel(selectedDifficulty), sortBy !== 'newest' && filterLabel(sortBy)].filter(Boolean).join(' · ')}
              </p>
              <button type="button" onClick={resetFilters} className="min-h-11 rounded px-3 text-emerald-300 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">
                {isPl ? 'Wyczyść' : 'Reset'}
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div role="status" aria-label={isPl ? 'Ładowanie artykułów' : 'Loading articles'} className="flex justify-center py-24">
            <Loader2 className="animate-spin text-emerald-400" size={32} />
          </div>
        ) : (
          <>
            {featuredPost && (
              <article className="grid min-w-0 rounded-lg border border-white/10 bg-obsidian-900 md:grid-cols-2">
                <Link
                  to={`/blog/${featuredPost.slug}`}
                  aria-label={featuredPost.title}
                  className="flex min-h-24 items-center justify-center rounded-t-lg border-b border-white/10 bg-obsidian-950 p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 md:min-h-80 md:rounded-t-none md:rounded-l-lg md:border-b-0 md:border-r md:p-12"
                >
                  {featuredPost.country_code ? (
                    <img
                      src={`https://flagcdn.com/w640/${featuredPost.country_code.toLowerCase()}.png`}
                      alt={featuredPost.country_name}
                      className="max-h-16 w-full max-w-28 object-contain md:max-h-64 md:max-w-sm"
                    />
                  ) : (
                    <Globe size={80} strokeWidth={1} className="text-zinc-600" />
                  )}
                </Link>
                <div className="flex min-w-0 flex-col justify-center p-4 sm:p-8 md:p-10">
                  <div className="mb-3 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 text-xs">
                    <span className="font-medium text-emerald-400">
                      {isPl ? 'Wczorajsze rozwiązanie' : "Yesterday's solution"}
                    </span>
                    <span className="text-zinc-500">/</span>
                    <span className="text-zinc-400">{featuredPost.country_name}</span>
                  </div>
                  <h2 className="min-w-0 break-words font-serif text-2xl leading-tight tracking-tight text-sand-100 md:text-3xl lg:text-4xl">
                    <Link to={`/blog/${featuredPost.slug}`} className="transition-colors hover:text-emerald-300">
                      {featuredPost.title}
                    </Link>
                  </h2>
                  <p className="mt-4 text-sm leading-7 text-zinc-400">{featuredPost.summary}</p>
                  <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-400">
                    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5"><Calendar size={13} className="shrink-0" /><span className="min-w-0 break-words">{featuredPost.date}</span></span>
                    <span className="inline-flex min-w-0 max-w-full items-center gap-1.5"><Clock size={13} className="shrink-0" /><span className="min-w-0 break-words">{featuredPost.reading_time_minutes} {isPl ? 'min czytania' : 'min read'}</span></span>
                    {featuredPost.continent && (
                      <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-400 border border-emerald-500/20">
                        {filterLabel(featuredPost.continent)}
                      </span>
                    )}
                    {featuredPost.difficulty && (
                      <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                        {filterLabel(featuredPost.difficulty)}
                      </span>
                    )}
                  </div>
                  <Link
                    to={`/blog/${featuredPost.slug}`}
                    className="mt-4 inline-flex min-h-11 w-fit max-w-full items-center gap-3 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300 md:mt-7"
                  >
                    {isPl ? 'Czytaj artykuł' : 'Read article'}
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </article>
            )}

            {regularPosts.length > 0 ? (
              <section>
                <div className="mb-6 flex items-center gap-4">
                  <h2 className="min-w-0 text-sm font-medium text-zinc-400">
                    {search ? (isPl ? 'Wyniki wyszukiwania' : 'Search results') : (isPl ? 'Poprzednie artykuły' : 'Earlier entries')}
                  </h2>
                  <div className="h-px flex-1 bg-white/10" />
                </div>
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {regularPosts.map((post) => (
                    <article key={post.id} className="group flex min-w-0 flex-col rounded-lg border border-white/10 bg-obsidian-900 transition-colors hover:border-white/25">
                      <Link to={`/blog/${post.slug}`} aria-label={post.title} className="flex h-24 items-center justify-center rounded-t-lg border-b border-white/10 bg-obsidian-950 p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 sm:h-48 sm:p-7">
                        {post.country_code ? (
                          <img
                            src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                            alt={post.country_name}
                            loading="lazy"
                            className="max-h-full w-full max-w-28 object-contain sm:max-w-56"
                          />
                        ) : (
                          <Globe size={56} strokeWidth={1} className="text-zinc-600" />
                        )}
                      </Link>
                      <div className="flex min-w-0 flex-1 flex-col p-4 sm:p-6">
                        <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <p className="min-w-0 break-words text-xs font-medium text-emerald-400">{post.country_name}</p>
                          {post.continent && (
                            <span className="text-xs text-zinc-500">{filterLabel(post.continent)}</span>
                          )}
                        </div>
                        <h3 className="min-w-0 break-words font-serif text-2xl leading-snug text-sand-100">
                          <Link to={`/blog/${post.slug}`} className="transition-colors hover:text-emerald-300">{post.title}</Link>
                        </h3>
                        <p className="mt-3 text-sm leading-relaxed text-zinc-400">{post.summary}</p>
                        <div className="mb-5 mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-500">
                          <span>{post.date}</span>
                          <span>{post.reading_time_minutes} min</span>
                          {post.difficulty && (
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              post.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400' :
                              post.difficulty === 'Challenging' ? 'bg-rose-500/10 text-rose-400' :
                              'bg-amber-500/10 text-amber-400'
                            }`}>
                              {filterLabel(post.difficulty)}
                            </span>
                          )}
                        </div>
                        <Link to={`/blog/${post.slug}`} className="mt-auto flex min-h-11 items-center justify-between gap-3 border-t border-white/10 pt-4 text-sm font-medium text-emerald-400 transition-colors hover:text-emerald-300">
                          {isPl ? 'Czytaj artykuł' : 'Read article'}
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
                  <p className="text-base text-zinc-400">{isPl ? 'Brak artykułów pasujących do wyszukiwania.' : 'No articles match your search.'}</p>
                </div>
              )
            )}
          </>
        )}

        <AdSenseUnit slot="blog-list-footer" className="max-w-xl mx-auto pt-6" />
      </div>
    </div>
  );
}
