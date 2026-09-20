import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
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
  Loader2
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-hot-toast';
import { blogService } from '../services/api';

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
      <div className="flex justify-center items-center min-h-[60vh]">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-4 text-center space-y-4">
        <h2 className="text-2xl font-bold text-white">Post Not Found</h2>
        <p className="text-zinc-400">The requested article could not be loaded.</p>
        <Link to="/blog" className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300">
          <ArrowLeft size={16} />
          {t('blog.backToBlog', 'Back to All Posts')}
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-12 md:py-16">
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="space-y-10"
      >
        {/* Navigation Back & Share */}
        <div className="flex justify-between items-center text-sm">
          <Link
            to="/blog"
            className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors"
          >
            <ArrowLeft size={16} />
            <span>{t('blog.backToBlog', 'Back to All Posts')}</span>
          </Link>

          <button
            onClick={handleShare}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors text-xs font-medium"
          >
            {copied ? <Check size={14} className="text-green-400" /> : <Share2 size={14} />}
            <span>{copied ? 'Copied' : 'Share'}</span>
          </button>
        </div>

        {/* Article Header */}
        <header className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-zinc-400">
            <span className="px-2.5 py-1 rounded-md bg-blue-500/20 text-blue-300 font-bold uppercase tracking-wider">
              {post.country_name}
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar size={13} />
              {post.date}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <Clock size={13} />
              {post.reading_time_minutes} {t('blog.minRead', 'min read')}
            </span>
          </div>

          <h1 className="text-3xl md:text-5xl font-black text-white leading-tight tracking-tight">
            {post.title}
          </h1>

          <p className="text-zinc-300 text-base md:text-lg leading-relaxed">
            {post.subtitle}
          </p>
        </header>

        {/* Fast Facts Card */}
        {post.fast_facts && (
          <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl space-y-4">
            <div className="flex items-center gap-2 text-teal-400 font-bold text-xs uppercase tracking-wider">
              <Globe size={16} />
              {t('blog.fastFacts', 'Fast Facts')}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs md:text-sm">
              {Object.entries(post.fast_facts).map(([key, val]) => (
                <div key={key} className="space-y-1">
                  <div className="text-zinc-500 capitalize">{key.replace(/_/g, ' ')}</div>
                  <div className="text-white font-semibold">{String(val)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Curated Wikipedia Fun Facts */}
        {post.fun_facts && post.fun_facts.length > 0 && (
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-yellow-400 font-bold text-xs uppercase tracking-wider">
              <Sparkles size={16} />
              {t('blog.funFacts', 'Wikipedia Curiosities & Fun Facts')}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {post.fun_facts.map((fact: any, idx: number) => (
                <div
                  key={idx}
                  className="p-5 bg-gradient-to-b from-zinc-900 to-zinc-900/80 border border-zinc-800 rounded-2xl space-y-2"
                >
                  <div className="text-yellow-400 font-bold text-sm">
                    {fact.title}
                  </div>
                  <p className="text-zinc-300 text-xs leading-relaxed">
                    {fact.description}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Main Article Content (Markdown) */}
        <article className="prose prose-invert prose-zinc max-w-none text-zinc-300 leading-relaxed space-y-6 text-sm md:text-base border-y border-zinc-800/80 py-8">
          <div className="whitespace-pre-line leading-relaxed">
            {post.content_markdown}
          </div>
        </article>

        {/* Deduction Masterclass Callout */}
        {post.deduction_masterclass && (
          <section className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4 shadow-xl">
            <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase tracking-wider">
              <Compass size={16} />
              {t('blog.deductionStrategy', 'Optimal Deduction Masterclass')}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
              <div className="space-y-1">
                <div className="text-zinc-400 font-bold text-xs uppercase">Step 1 • Quadrant Elimination</div>
                <p className="text-zinc-300 text-xs leading-relaxed">{post.deduction_masterclass.step_1}</p>
              </div>
              <div className="space-y-1">
                <div className="text-zinc-400 font-bold text-xs uppercase">Step 2 • Boundary Isolation</div>
                <p className="text-zinc-300 text-xs leading-relaxed">{post.deduction_masterclass.step_2}</p>
              </div>
              <div className="space-y-1">
                <div className="text-purple-400 font-bold text-xs uppercase">Winning Clue</div>
                <p className="text-zinc-300 text-xs leading-relaxed">{post.deduction_masterclass.winning_clue}</p>
              </div>
            </div>
          </section>
        )}

        {/* Call to Action: Play Today */}
        <div className="p-8 md:p-12 bg-gradient-to-r from-blue-900/40 via-teal-900/30 to-zinc-900 border border-blue-500/30 rounded-3xl text-center space-y-6 shadow-2xl">
          <div className="space-y-2 max-w-xl mx-auto">
            <h3 className="text-2xl md:text-3xl font-black text-white">
              Ready to test your geography skills?
            </h3>
            <p className="text-zinc-300 text-sm">
              Today's mystery country is live now. Can you deduce it in fewer than 4 questions and claim the top of the leaderboard?
            </p>
          </div>
          <div>
            <Link
              to="/game"
              className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-600 to-teal-500 hover:from-blue-500 hover:to-teal-400 text-white font-black rounded-2xl shadow-xl shadow-blue-500/25 transition-all text-base hover:scale-105"
            >
              <Play size={18} />
              <span>{t('blog.playToday', "Play Today's Countrydle Challenge")}</span>
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
