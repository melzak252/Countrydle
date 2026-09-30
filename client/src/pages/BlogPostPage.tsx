import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  Sparkles, 
  Compass, 
  Globe, 
  Play, 
  Share2, 
  Check, 
  Loader2,
  Award
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-hot-toast';
import { blogService } from '../services/api';
import AdSenseUnit from '../components/AdSenseUnit';

function cleanDisplayText(text?: string): string {
  if (!text) return '';
  return text
    .replace(/\\?\[\*?\s*citation needed\s*\*?\\?\]/gi, '')
    .replace(/\[\d+\]/g, '')
    .replace(/\\([_()\[\]*])/g, '$1')
    .replace(/\\/g, '')
    .trim();
}
export default function BlogPostPage() {
  const { slug } = useParams<{ slug: string }>();
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const [post, setPost] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [selectedTriviaOption, setSelectedTriviaOption] = useState<number | null>(null);
  const [triviaRevealed, setTriviaRevealed] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const fetchPost = async () => {
      if (!slug) return;
      setLoading(true);
      try {
        const data = await blogService.getPostBySlug(slug);
        if (isMounted) {
          setPost(data);
        }
      } catch (err) {
        console.error('Failed to fetch blog post', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchPost();
    return () => {
      isMounted = false;
    };
  }, [slug]);

  const handleShare = async () => {
    const url = window.location.href;
    const title = post?.title || 'Countrydle Solution';
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        // Fallback to clipboard
      }
    }
    await navigator.clipboard.writeText(url);
    setCopied(true);
    toast.success('Link copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div role="status" aria-label="Loading debrief" className="flex justify-center py-32">
        <Loader2 className="animate-spin text-emerald-400" size={36} />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center">
        <Globe size={40} className="mx-auto mb-4 text-zinc-600" />
        <h1 className="font-serif text-2xl text-sand-100">Solution Not Found</h1>
        <p className="mt-2 text-sm text-zinc-400">The daily puzzle recap you are looking for does not exist.</p>
        <Link to="/blog" className="mt-6 inline-flex items-center gap-2 rounded bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950">
          <ArrowLeft size={14} /> Back to Daily Journal
        </Link>
      </div>
    );
  }

  const steps = post.deduction_masterclass?.steps || [];
  const proTip = post.deduction_masterclass?.pro_tip || '';
  const curiosities = post.fun_facts || [];
  const facts = post.fast_facts || {};

  return (
    <div className="mx-auto max-w-4xl space-y-10 px-4 py-8 sm:px-6 md:py-12">
      {/* Navigation & Header */}
      <nav aria-label="Debrief navigation" className="flex items-center justify-between border-b border-white/10 pb-4 text-xs font-mono">
        <Link to="/blog" className="inline-flex items-center gap-1.5 text-zinc-400 hover:text-sand-100 transition-colors">
          <ArrowLeft size={14} />
          <span>{isPl ? 'Wszystkie podsumowania' : 'All Solutions'}</span>
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-zinc-500 font-mono">
            {post.date}
          </span>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center gap-1.5 rounded border border-white/15 px-2.5 py-1 text-zinc-300 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Share2 size={12} />}
            <span>{copied ? 'Copied' : 'Share'}</span>
          </button>
        </div>
      </nav>

      {/* Hero Solution Card */}
      <header className="overflow-hidden rounded-lg border border-white/15 bg-obsidian-900 shadow-2xl">
        <div className="grid gap-6 p-6 sm:p-8 md:grid-cols-[180px_1fr] md:items-center md:gap-8">
          {post.country_code ? (
            <div className="flex items-center justify-center rounded-md border border-white/10 bg-obsidian-950 p-4">
              <img
                src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                alt={post.country_name}
                className="max-h-28 w-auto object-contain drop-shadow-md"
              />
            </div>
          ) : (
            <div className="flex h-28 items-center justify-center rounded-md border border-white/10 bg-obsidian-950 text-zinc-600">
              <Globe size={48} />
            </div>
          )}

          <div className="space-y-3 text-center md:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 md:justify-start">
              <span className="font-mono text-xs uppercase tracking-widest text-emerald-400 font-bold">
                Yesterday's Solution
              </span>
              <span className="text-zinc-600">&bull;</span>
              {post.continent && (
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300 border border-emerald-500/20">
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

            <h1 className="font-serif text-3xl font-bold tracking-tight text-sand-100 sm:text-4xl md:text-5xl uppercase">
              {post.country_name}
            </h1>

            {post.subtitle && (
              <p className="text-sm text-zinc-400 max-w-xl leading-relaxed">
                {post.subtitle}
              </p>
            )}

            {/* Community Performance Scoreboard */}
            <div className="mt-4 pt-3 border-t border-white/10 flex flex-wrap items-center justify-center md:justify-start gap-4 text-xs font-mono text-zinc-400">
              {post.game_debrief?.has_telemetry ? (
                <>
                  <span className="text-sand-100 font-bold">
                    {post.game_debrief.win_rate_pct}% Solved ({post.game_debrief.total_solvers} of {post.game_debrief.total_challengers})
                  </span>
                  <span>&bull;</span>
                  <span>
                    Avg: <strong className="text-sand-100">{post.game_debrief.avg_questions_to_win}</strong> Questions to Win
                  </span>
                  {post.game_debrief.high_score && (
                    <>
                      <span>&bull;</span>
                      <span>High Score: <strong className="text-emerald-400">{post.game_debrief.high_score} pts</strong></span>
                    </>
                  )}
                </>
              ) : post.player_stats && post.player_stats.total_players > 0 ? (
                <>
                  <span className="text-sand-100 font-bold">
                    {post.player_stats.win_rate_pct}% Solved
                  </span>
                  <span>&bull;</span>
                  <span>
                    Avg: <strong className="text-sand-100">{post.player_stats.avg_questions_won}</strong> Qs
                  </span>
                  <span>&bull;</span>
                  <span>
                    <strong className="text-sand-100">{post.player_stats.total_players}</strong> Challengers
                  </span>
                </>
              ) : (
                <span>Daily Puzzle #{post.id} Debrief</span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Community Question Telemetry / Deduction Ladder */}
      <section className="rounded-lg border border-white/10 bg-obsidian-900/60 p-6 sm:p-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between border-b border-white/10 pb-4 gap-2">
          <div className="flex items-center gap-2">
            <Compass size={18} className="text-emerald-400" />
            <h2 className="font-mono text-xs uppercase tracking-widest text-emerald-400 font-bold">
              {post.game_debrief?.top_questions?.length ? 'What Questions Players Asked Yesterday' : 'The Deduction Ladder'}
            </h2>
          </div>
          <span className="text-xs text-zinc-500 font-mono">
            {post.game_debrief?.top_questions?.length ? 'Real Community Question Telemetry' : 'Optimal Elimination Sequence'}
          </span>
        </div>

        <div className="space-y-3">
          {(post.game_debrief?.top_questions?.length ? post.game_debrief.top_questions : steps).map((st: any, idx: number) => {
            const isYes = String(st.answer).toUpperCase() === 'YES';
            return (
              <div key={idx} className="flex items-start gap-4 rounded-md border border-white/5 bg-white/[0.02] p-4 transition-colors hover:border-white/15">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/5 font-mono text-xs font-bold text-sand-100 border border-white/10">
                  {idx + 1}
                </div>
                <div className="flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-sand-100">
                      "{st.question}"
                    </span>
                    <div className="flex items-center gap-2">
                      {st.count !== undefined && (
                        <span className="text-[11px] font-mono text-zinc-400">
                          Asked {st.count}x {st.pct ? `(${st.pct}%)` : ''}
                        </span>
                      )}
                      <span className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold uppercase tracking-wider ${
                        isYes 
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      }`}>
                        {isYes ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs leading-relaxed text-zinc-400">
                    {cleanDisplayText(st.explanation)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Common Traps & Wrong Guesses */}
      {post.game_debrief?.common_pitfalls && post.game_debrief.common_pitfalls.length > 0 && (
        <section className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-5 space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-rose-400 font-bold">
            <span>⚠️ Common Traps & Wrong Guesses</span>
          </div>
          <p className="text-xs text-zinc-300">
            Solvers who stumbled yesterday frequently submitted these incorrect countries before zeroing in on {post.country_name}:
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {post.game_debrief.common_pitfalls.map((pf: any, idx: number) => (
              <span key={idx} className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-1 font-mono text-xs text-rose-300">
                ❌ {pf.guess} <span className="text-rose-400/70 text-[10px]">({pf.count} guesses)</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Quick Facts Grid */}
      {facts && Object.keys(facts).length > 0 && (
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-zinc-400 font-bold">
            Geographic Identity At a Glance
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            {facts.capital && (
              <div className="rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-500 block text-[10px] uppercase">Capital</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.capital}</span>
              </div>
            )}
            {facts.population && (
              <div className="rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-500 block text-[10px] uppercase">Population</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.population}</span>
              </div>
            )}
            {facts.area && (
              <div className="rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-500 block text-[10px] uppercase">Land Area</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.area}</span>
              </div>
            )}
            {facts.coastline && (
              <div className="rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-500 block text-[10px] uppercase">Maritime Access</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.coastline}</span>
              </div>
            )}
          </div>

          {facts.borders && facts.borders !== 'None' && (
            <div className="rounded border border-white/10 bg-obsidian-900/40 p-4 text-xs font-mono">
              <span className="text-zinc-500 block text-[10px] uppercase mb-1.5">Bordering Neighbors:</span>
              <span className="text-zinc-300 leading-relaxed">{facts.borders}</span>
            </div>
          )}
        </section>
      )}

      {/* Two Things Worth Knowing (Curiosities) */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-amber-400 font-bold flex items-center gap-1.5">
            <Sparkles size={14} />
            <span>Two Things Worth Knowing</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {curiosities.slice(0, 2).map((c: any, i: number) => (
              <div key={i} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-5 space-y-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-amber-400/80 font-bold block">
                  #{i + 1} &bull; {c.title}
                </span>
                <p className="text-xs leading-relaxed text-zinc-300">
                  {cleanDisplayText(c.description)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Curator Pro Tip */}
      {proTip && (
        <section className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-5 space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400 font-bold">
            <Compass size={14} />
            <span>Curator's Deduction Pro Tip</span>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed text-zinc-200">
            {cleanDisplayText(proTip)}
          </p>
        </section>
      )}

      {/* Interactive Trivia Knowledge Check */}
      {curiosities && curiosities.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-obsidian-900 p-6 space-y-4">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400 font-bold">
            <Award size={14} />
            <span>Quick Memory Check</span>
          </div>
          <h3 className="font-serif text-lg font-semibold text-sand-100">
            Which statement about {post.country_name} is true?
          </h3>

          <div className="space-y-2 text-xs sm:text-sm">
            <button
              type="button"
              onClick={() => { setSelectedTriviaOption(0); setTriviaRevealed(true); }}
              className={`w-full text-left p-3 rounded border transition-all ${
                triviaRevealed
                  ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300 font-semibold'
                  : 'border-white/10 bg-white/[0.02] text-zinc-300 hover:border-white/20'
              }`}
            >
              A) {cleanDisplayText(curiosities[0]?.description)}
            </button>
            <button
              type="button"
              onClick={() => { setSelectedTriviaOption(1); setTriviaRevealed(true); }}
              className={`w-full text-left p-3 rounded border transition-all ${
                triviaRevealed && selectedTriviaOption === 1
                  ? 'border-rose-500 bg-rose-500/10 text-rose-300 line-through'
                  : 'border-white/10 bg-white/[0.02] text-zinc-300 hover:border-white/20'
              }`}
            >
              B) It has a coastline on the Mediterranean Sea.
            </button>
          </div>

          {triviaRevealed && (
            <div className="rounded bg-emerald-500/10 border border-emerald-500/30 p-3 text-xs text-emerald-300">
              <span className="font-bold block mb-1">
                {selectedTriviaOption === 0 ? '✓ Correct!' : 'Not quite!'}
              </span>
              <span>{cleanDisplayText(curiosities[0]?.description)}</span>
            </div>
          )}
        </section>
      )}

      {/* Compliant Ad Placement */}
      <AdSenseUnit slot="countrydle-blog-post-footer" className="max-w-xl mx-auto" />

      {/* Related Country Recaps Carousel */}
      {post.related_posts && post.related_posts.length > 0 && (
        <section className="border-t border-white/10 pt-8 space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-zinc-400 font-bold flex items-center gap-1.5">
            <Globe size={14} />
            <span>More Recent Country Solutions</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
                  <h4 className="font-serif text-sm font-semibold text-sand-100 group-hover:text-emerald-300 transition-colors">
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

      {/* Play Today's Game CTA */}
      <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6 text-center space-y-3">
        <h3 className="font-serif text-xl font-bold text-sand-100">
          Ready for Today's Daily Challenge?
        </h3>
        <p className="text-xs text-zinc-400 max-w-md mx-auto">
          A new mystery country is active now. Test your deduction skills before midnight UTC!
        </p>
        <div className="pt-2">
          <Link
            to="/game"
            className="inline-flex items-center gap-2 rounded bg-emerald-400 px-6 py-2.5 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors shadow"
          >
            <Play size={14} />
            <span>Play Today's Countrydle</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
