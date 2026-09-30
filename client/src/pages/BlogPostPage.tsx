import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  Calendar, 
  Clock, 
  Sparkles, 
  Compass, 
  Globe, 
  Play, 
  Share2, 
  Check, 
  Loader2,
  Users,
} from 'lucide-react';
import MarkdownRenderer from '../components/MarkdownRenderer';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-hot-toast';
import { blogService } from '../services/api';
import AdSenseUnit from '../components/AdSenseUnit';

export default function BlogPostPage() {
  const { slug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const [post, setPost] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    blogService.getPostBySlug(slug)
      .then((data) => {
        setPost(data);
        if (data.title) {
          document.title = `${data.title} | Countrydle Blog`;
        }
      })
      .catch((err) => {
        console.error('Failed to load blog post', err);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    toast.success('Link copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };

  if (loading) {
    return (
      <div role="status" aria-label={'Loading article'} className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-emerald-400" size={32} />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-4 text-center space-y-4">
        <h2 className="font-serif text-3xl text-sand-100">{'Post not found'}</h2>
        <p className="text-zinc-400">{'The requested article could not be loaded.'}</p>
        <Link to="/blog" className="inline-flex items-center gap-2 text-emerald-400 hover:text-emerald-300">
          <ArrowLeft size={16} />
          {t('blog.backToBlog', 'Back to All Posts')}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 md:py-12">
      <div className="space-y-10 md:space-y-12">
        <nav aria-label={'Article navigation'} className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5 text-sm">
          <Link to="/blog" className="inline-flex items-center gap-2 text-zinc-400 transition-colors hover:text-sand-100">
            <span>{t('blog.backToBlog', '← Back to All Posts')}</span>
          </Link>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center gap-2 rounded-md border border-white/15 px-3 py-2 text-xs font-medium text-zinc-300 transition-colors hover:border-emerald-400/40 hover:text-emerald-300"
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Share2 size={14} />}
            <span>{copied ? ('Copied') : ('Share')}</span>
          </button>
        </nav>

        <header className="grid gap-8 md:grid-cols-[1fr_240px] md:items-center md:gap-12">
          <div>
            <p className="mb-4 text-xs font-medium uppercase tracking-[0.18em] text-emerald-400">{post.country_name}</p>
            <h1 className="font-serif text-4xl leading-[1.12] tracking-tight text-sand-100 sm:text-5xl md:text-[3.25rem]">{post.title}</h1>
            {post.subtitle && <p className="mt-5 text-base leading-7 text-zinc-400 md:text-lg md:leading-8">{post.subtitle}</p>}
            <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-400">
              <span className="inline-flex items-center gap-1.5"><Calendar size={13} />{post.date}</span>
              <span className="inline-flex items-center gap-1.5"><Clock size={13} />{post.reading_time_minutes} {t('blog.minRead', 'min read')}</span>
              {post.continent && (
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-400 border border-emerald-500/20">
                  {post.continent}
                </span>
              )}
              {post.difficulty && (
                <span className={`px-2 py-0.5 rounded font-mono text-[10px] ${
                  post.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400' :
                  post.difficulty === 'Challenging' ? 'bg-rose-500/10 text-rose-400' :
                  'bg-amber-500/10 text-amber-400'
                }`}>
                  {post.difficulty}
                </span>
              )}
            </div>
          </div>
          {post.country_code && (
            <figure className="flex flex-col items-center justify-center rounded-md border border-white/10 bg-obsidian-900 px-6 py-8">
              <img
                src={`https://flagcdn.com/w640/${post.country_code.toLowerCase()}.png`}
                className="max-h-44 w-full max-w-xs object-contain"
                alt={post.country_name}
              />
              <figcaption className="mt-5 text-xs tracking-wide text-zinc-400">{post.country_name}</figcaption>
            </figure>
          )}
        </header>

        {/* Community Performance Scoreboard */}
        {post.player_stats && post.player_stats.total_players > 0 && (
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-white/10 bg-obsidian-900/60 px-6 py-4 text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-400">
              <Users size={14} className="text-emerald-400" />
              <span>Community Solvers: <strong className="text-sand-100">{post.player_stats.winners_count}</strong> of {post.player_stats.total_players} ({post.player_stats.win_rate_pct}%)</span>
            </div>
            {post.player_stats.avg_questions_won > 0 && (
              <div className="flex items-center gap-2 text-zinc-400">
                <Compass size={14} className="text-amber-400" />
                <span>Average Solved in: <strong className="text-sand-100">{post.player_stats.avg_questions_won} questions</strong></span>
              </div>
            )}
          </section>
        )}

        {/* Article Body */}
        <article className="mx-auto max-w-[72ch] border-y border-white/10 py-8 text-zinc-300 md:py-12">
          <MarkdownRenderer content={post.content_markdown} />
        </article>
        {post.fun_facts && post.fun_facts.length > 0 && (
          <section className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400">
              <Sparkles size={14} />
              <span>Interactive Knowledge Check</span>
            </div>
            <h3 className="font-serif text-xl font-semibold text-sand-100">
              Test your geography memory: {post.country_name}
            </h3>
            <p className="text-sm text-zinc-300">
              Which of the following is true regarding <strong>{post.country_name}</strong>'s geography and culture?
            </p>
            <div className="space-y-2.5 pt-2">
              <details className="group rounded-sm border border-white/10 bg-obsidian-900 p-4 cursor-pointer hover:border-emerald-500/30">
                <summary className="list-none text-xs sm:text-sm font-medium text-sand-100 flex items-center justify-between">
                  <span>Question: What distinguishes {post.country_name}'s heritage and geography?</span>
                  <span className="text-xs font-mono text-emerald-400 group-open:hidden">Reveal Clue &rarr;</span>
                </summary>
                <div className="mt-3 pt-3 border-t border-white/10 text-xs sm:text-sm text-zinc-300 space-y-2">
                  <p className="font-bold text-emerald-400">Key Fact:</p>
                  <p>{post.fun_facts[0].description}</p>
                </div>
              </details>
            </div>
          </section>
        )}

        {post.deduction_masterclass && (
          <section className="rounded-lg border border-white/10 bg-obsidian-900 p-6 sm:p-8">
            <h2 className="mb-6 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-emerald-400">
              <Compass size={15} />
              {t('blog.deductionStrategy', 'Optimal Deduction Masterclass')}
            </h2>
            <div className="grid grid-cols-1 gap-7 md:grid-cols-3">
              <div>
                <h3 className="mb-3 text-sm font-medium text-sand-100">{'01 / Quadrant elimination'}</h3>
                <p className="text-sm leading-7 text-zinc-400">{post.deduction_masterclass.step_1}</p>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-medium text-sand-100">{'02 / Boundary isolation'}</h3>
                <p className="text-sm leading-7 text-zinc-400">{post.deduction_masterclass.step_2}</p>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-medium text-emerald-400">{'03 / Winning clue'}</h3>
                <p className="text-sm leading-7 text-zinc-400">{post.deduction_masterclass.winning_clue}</p>
              </div>
            </div>
          </section>
        )}

        <AdSenseUnit slot="countrydle-blog-post-footer" className="max-w-2xl mx-auto" />


        {/* Related Recaps Carousel */}
        {post.related_posts && post.related_posts.length > 0 && (
          <section className="border-t border-white/10 pt-8 space-y-4">
            <h2 className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400">
              <Globe size={14} />
              <span>Explore More Geography Recaps</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {post.related_posts.map((rp: any) => (
                <Link
                  key={rp.id}
                  to={`/blog/${rp.slug}`}
                  className="group rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between"
                >
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 block mb-1">
                      {rp.country_name}
                    </span>
                    <h4 className="font-serif text-sm font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors line-clamp-2">
                      {rp.title}
                    </h4>
                  </div>
                  <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                    <span>{rp.date}</span>
                    <span className="text-emerald-400 group-hover:translate-x-1 transition-transform">&rarr;</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
        <section className="flex flex-col items-start justify-between gap-6 border-t border-white/10 pt-8 sm:flex-row sm:items-center">
          <div className="max-w-lg">
            <h2 className="font-serif text-2xl text-sand-100 md:text-3xl">{'Today’s challenge'}</h2>
            <p className="mt-3 text-sm leading-6 text-zinc-400">{'Return to the map and solve today’s country challenge.'}</p>
          </div>
          <Link to="/game" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-emerald-400 px-5 py-3.5 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 sm:max-w-xs">
            <Play size={16} className="shrink-0" />
            <span>{t('blog.playToday', "Play Today's Countrydle Challenge")}</span>
          </Link>
        </section>
      </div>
    </div>
  );
}
