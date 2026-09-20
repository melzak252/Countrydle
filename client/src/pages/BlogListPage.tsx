import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  BookOpen, 
  Search, 
  Calendar, 
  Clock, 
  ArrowRight, 
  Globe, 
  Loader2, 
  Sparkles
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
    <div className="max-w-6xl mx-auto px-4 py-12 md:py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-12"
      >
        {/* Hero Header */}
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs md:text-sm font-semibold uppercase tracking-wider">
            <BookOpen size={16} />
            {t('blog.badge', 'Daily Country Recaps & Trivia')}
          </div>
          <h1 className="text-4xl md:text-6xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-teal-300 to-green-400 text-transparent bg-clip-text">
            {t('blog.title', 'Countrydle Daily Blog')}
          </h1>
          <p className="text-zinc-400 text-base md:text-lg leading-relaxed">
            {t('blog.subtitle', 'Explore yesterday\'s mystery country, fascinating Wikipedia curiosities, and optimal deduction breakdowns.')}
          </p>

          {/* Search bar */}
          <div className="pt-4 max-w-lg mx-auto relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('blog.searchPlaceholder', 'Search countries, facts, or keywords...')}
              className="w-full pl-11 pr-4 py-3 bg-zinc-900 border border-zinc-800 rounded-2xl text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
            />
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="flex justify-center p-20">
            <Loader2 className="animate-spin text-blue-500" size={48} />
          </div>
        ) : (
          <>
            {/* Featured Post (Yesterday's Country) */}
            {featuredPost && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="relative overflow-hidden bg-zinc-900 border border-blue-500/30 rounded-3xl p-8 md:p-12 shadow-2xl group"
              >
                {/* Ambient Flag Background with Vignette Gradient */}
                {featuredPost.country_code && (
                  <div
                    className="absolute inset-0 bg-cover bg-center opacity-20 pointer-events-none scale-105 filter saturate-150 transition-all duration-700 group-hover:scale-110 group-hover:opacity-25"
                    style={{ backgroundImage: `url(https://flagcdn.com/w1280/${featuredPost.country_code.toLowerCase()}.png)` }}
                  />
                )}
                <div className="absolute inset-0 bg-gradient-to-r from-zinc-950 via-zinc-950/85 to-blue-950/40 pointer-events-none" />

                <div className="relative z-10">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs font-bold uppercase tracking-wider">
                      <Sparkles size={14} />
                      {t('blog.latestBadge', "Yesterday's Solution")}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-zinc-400 font-mono">
                      <span className="flex items-center gap-1.5">
                        <Calendar size={14} />
                        {featuredPost.date}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Clock size={14} />
                        {featuredPost.reading_time_minutes} {t('blog.minRead', 'min read')}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-4 max-w-3xl">
                    <div className="flex items-center gap-2 text-teal-400 font-bold tracking-wider text-sm uppercase">
                      {featuredPost.country_code && (
                        <img
                          src={`https://flagcdn.com/w80/${featuredPost.country_code.toLowerCase()}.png`}
                          className="w-7 h-4.5 object-cover rounded shadow border border-white/20"
                          alt={featuredPost.country_name}
                        />
                      )}
                      <span>Featured Destination: {featuredPost.country_name}</span>
                    </div>
                    <h2 className="text-2xl md:text-4xl font-black text-white hover:text-blue-300 transition-colors">
                      <Link to={`/blog/${featuredPost.slug}`}>
                        {featuredPost.title}
                      </Link>
                    </h2>
                    <p className="text-zinc-300 text-sm md:text-base leading-relaxed">
                      {featuredPost.summary}
                    </p>
                    <div className="pt-2">
                      <Link
                        to={`/blog/${featuredPost.slug}`}
                        className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 text-sm"
                      >
                        <span>{t('blog.readArticle', 'Read Full Post')}</span>
                        <ArrowRight size={16} />
                      </Link>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Posts Grid */}
            {regularPosts.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {regularPosts.map((post) => (
                  <motion.div
                    key={post.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="relative overflow-hidden bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-6 flex flex-col justify-between transition-all hover:-translate-y-1.5 shadow-xl group"
                  >
                    {/* Flag Ambient Background with Smooth Zoom on Hover */}
                    {post.country_code && (
                      <div
                        className="absolute inset-0 bg-cover bg-center opacity-15 group-hover:opacity-30 transition-all duration-500 scale-100 group-hover:scale-110 pointer-events-none filter saturate-150"
                        style={{ backgroundImage: `url(https://flagcdn.com/w640/${post.country_code.toLowerCase()}.png)` }}
                      />
                    )}
                    {/* Vignette Gradient Overlay */}
                    <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-900/90 to-zinc-900/75 pointer-events-none" />

                    {/* Card Content */}
                    <div className="relative z-10 space-y-3">
                      <div className="flex justify-between items-center text-xs text-zinc-400">
                        <span className="flex items-center gap-1 font-mono">
                          <Calendar size={12} />
                          {post.date}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          {post.reading_time_minutes} {t('blog.minRead', 'min')}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {post.country_code && (
                          <img
                            src={`https://flagcdn.com/w40/${post.country_code.toLowerCase()}.png`}
                            className="w-5 h-3.5 object-cover rounded-sm shadow-sm border border-white/20"
                            alt={post.country_name}
                          />
                        )}
                        <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                          {post.country_name}
                        </span>
                      </div>

                      <h3 className="text-lg font-bold text-white leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                        <Link to={`/blog/${post.slug}`}>
                          {post.title}
                        </Link>
                      </h3>

                      <p className="text-zinc-400 text-xs line-clamp-3 leading-relaxed">
                        {post.summary}
                      </p>
                    </div>

                    <div className="relative z-10 pt-6 border-t border-zinc-800/80 mt-6 flex justify-between items-center">
                      <Link
                        to={`/blog/${post.slug}`}
                        className="text-xs font-bold text-blue-400 group-hover:text-blue-300 flex items-center gap-1.5 transition-colors"
                      >
                        <span>{t('blog.readArticle', 'Read Post')}</span>
                        <ArrowRight size={12} className="group-hover:translate-x-1 transition-transform" />
                      </Link>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              !featuredPost && (
                <div className="text-center py-16 bg-zinc-900/40 border border-zinc-800 rounded-3xl p-8">
                  <Globe size={48} className="mx-auto text-zinc-600 mb-4" />
                  <p className="text-zinc-400 text-base">
                    {t('blog.noPosts', 'No daily blog posts found matching your search.')}
                  </p>
                </div>
              )
            )}
          </>
        )}
      </motion.div>
    </div>
  );
}
