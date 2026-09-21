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
import { blogService } from '../services/api';

export default function BlogListPage() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

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

  const featuredPost = posts.length > 0 && !search ? posts[0] : null;
  const regularPosts = featuredPost ? posts.slice(1) : posts;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-16">
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
                {t('blog.subtitle', 'Explore yesterday\'s mystery country, fascinating Wikipedia curiosities, and optimal deduction breakdowns.')}
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
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t('blog.searchPlaceholder', 'Search countries, facts, or keywords...')}
                  className="w-full rounded-md border border-white/15 bg-obsidian-900 py-3.5 pl-11 pr-4 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                />
              </div>
            </div>
          </div>
        </header>

        {loading ? (
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
                      {t('blog.latestBadge', "Yesterday's Solution")}
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
                  <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-zinc-500">
                    <span className="inline-flex items-center gap-1.5"><Calendar size={13} />{featuredPost.date}</span>
                    <span className="inline-flex items-center gap-1.5"><Clock size={13} />{featuredPost.reading_time_minutes} {t('blog.minRead', 'min read')}</span>
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
                        <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.16em] text-emerald-400">{post.country_name}</p>
                        <h3 className="font-serif text-2xl leading-snug text-sand-100">
                          <Link to={`/blog/${post.slug}`} className="transition-colors hover:text-emerald-300">{post.title}</Link>
                        </h3>
                        <p className="mt-3 line-clamp-3 text-sm leading-6 text-zinc-400">{post.summary}</p>
                        <div className="mb-5 mt-5 flex flex-wrap gap-x-4 gap-y-2 text-xs text-zinc-500">
                          <span>{post.date}</span>
                          <span>{post.reading_time_minutes} {t('blog.minRead', 'min read')}</span>
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
          </>
        )}
      </div>
    </div>
  );
}
