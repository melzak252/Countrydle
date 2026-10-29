import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  Sparkles, 
  Globe, 
  Play, 
  Share2, 
  Check, 
  Loader2,
  Award
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { blogService } from '../services/api';
import AdSenseUnit from '../components/AdSenseUnit';
import { isAxiosError } from 'axios';
import { setPageEditorialEligibility } from '../advertising';
import { usePageMetadata } from '../lib/pageMetadata';
import { blogPostSchema, cleanDisplayText, safeSourceUrl, type BlogPost } from '../blogContent';


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

function cleanBorderList(bordersStr?: string | number): string {
  if (!bordersStr) return '';
  const parts = String(bordersStr).split(',').map((b) => b.trim()).filter(Boolean);
  const aliasMap: Record<string, string> = {
    'dr congo': 'Democratic Republic of the Congo',
    'democratic republic of the congo': 'Democratic Republic of the Congo',
    'czech republic': 'Czechia',
    'czechia': 'Czechia',
    'usa': 'United States',
    'united states': 'United States',
    'uk': 'United Kingdom',
    'united kingdom': 'United Kingdom',
  };
  const seen = new Set<string>();
  const result: string[] = [];
  for (const p of parts) {
    const canonical = aliasMap[p.toLowerCase()] || p;
    if (!seen.has(canonical.toLowerCase())) {
      seen.add(canonical.toLowerCase());
      result.push(canonical);
    }
  }
  return result.join(', ');
}


export default function BlogPostPage() {
  const { slug } = useParams<{ slug: string }>();
  const [fetchedPost, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [selectedTriviaOption, setSelectedTriviaOption] = useState<number | null>(null);
  const [triviaRevealed, setTriviaRevealed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let isMounted = true;
    const fetchPost = async () => {
      setLoading(true);
      setPost(null);
      setError(null);
      setSelectedTriviaOption(null);
      setTriviaRevealed(false);
      setPageEditorialEligibility(false);
      try {
        if (!slug) throw new Error('Missing recap address.');
        const data = blogPostSchema.parse(await blogService.getPostBySlug(slug));
        const today = new Date().toISOString().slice(0, 10);
        if (data.date >= today || data.related_posts?.some((related) => related.date >= today)) throw new Error('This solution is not public yet.');
        if (isMounted) {
          setPost(data);
          setLoadedSlug(slug);
        }
      } catch (err) {
        if (isMounted) setError(isAxiosError(err) && err.response?.status === 404
          ? 'This past-day recap was not found. Today’s solution is not published here.'
          : 'The recap could not be loaded. Please try again.');
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchPost();
    return () => {
      isMounted = false;
      setPageEditorialEligibility(false);
    };
  }, [slug, retry]);

  const loadedPost = !loading && !error && loadedSlug === slug ? fetchedPost : null;
  const quizNeedsRepair = loadedPost?.deduction_masterclass?.quiz?.status === 'needs-editorial-repair';
  const reviewed = loadedPost?.editorial_status === 'reviewed' && !!loadedPost?.reviewed_at && !!loadedPost?.reviewer_name;
  const eligibleForAds = reviewed && !quizNeedsRepair;
  useEffect(() => {
    setPageEditorialEligibility(eligibleForAds);
    return () => setPageEditorialEligibility(false);
  }, [eligibleForAds, slug]);
  usePageMetadata(loadedPost ? {
    title: `${loadedPost.title} — ${loadedPost.country_name}, ${loadedPost.date} | Countrydle`,
    description: `Past-day recap for ${loadedPost.country_name} (${loadedPost.date}). ${loadedPost.summary || loadedPost.subtitle || 'Country-specific geography and deduction analysis.'}`,
    canonicalPath: `/blog/${encodeURIComponent(loadedPost.slug || loadedPost.date)}`,
    article: {
      countryName: loadedPost.country_name,
      puzzleDate: loadedPost.date,
      publishedAt: loadedPost.created_at || undefined,
      updatedAt: loadedPost.updated_at,
      authorName: loadedPost.reviewer_name || 'Jakub Melzacki',
      reviewedBy: reviewed ? loadedPost.reviewer_name || undefined : undefined,
    },
  } : null);

  const handleShare = async () => {
    const url = window.location.href;
    const title = loadedPost?.title || ('Countrydle solution');
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

  if (loading || (!error && loadedSlug !== slug)) {
    return (
      <div data-publisher-ready="false" role="status" aria-label={'Loading recap'} className="flex justify-center py-32">
        <Loader2 className="animate-spin text-emerald-400" size={36} />
      </div>
    );
  }

  if (error || !loadedPost) {
    return (
      <div data-publisher-ready="false" data-publisher-error="true" className="mx-auto max-w-3xl py-20 text-center">
        <Globe size={40} className="mx-auto mb-4 text-zinc-600" />
        <h1 className="font-serif text-2xl text-sand-100">{'Recap unavailable'}</h1>
        <p role="alert" className="mt-2 text-sm text-zinc-400">{error || 'The recap could not be loaded.'}</p>
        <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 min-h-11 rounded border border-white/20 px-4 py-2 text-sand-100">{'Try again'}</button>
        <Link to="/blog" className="mt-6 inline-flex min-h-11 items-center gap-2 rounded bg-emerald-400 px-4 py-2 text-sm font-bold text-obsidian-950">
          <ArrowLeft size={14} /> {'Back to journal'}
        </Link>
      </div>
    );
  }

  const post = loadedPost;
  const curiosities = post.fun_facts || [];
  const sourceLinks = post.source_links.map((source) => ({ ...source, safeUrl: safeSourceUrl(source.url) }));
  const facts = post.fast_facts || {};
  const questionLists = [
    {
      title: 'Most common questions overall',
      questions: post.game_debrief?.top_questions ?? [],
      empty: 'No recorded questions are available for this daily puzzle.',
    },
    {
      title: 'Most common questions asked by winners',
      questions: post.game_debrief?.top_winner_questions ?? [],
      empty: 'No recorded questions linked to winners are available for this daily puzzle.',
    },
  ];

  return (
    <article data-publisher-ready="true" className="mx-auto min-w-0 max-w-4xl space-y-6 py-4 [overflow-wrap:anywhere] md:space-y-10 md:py-10">
      {/* Navigation & Header */}
      <nav aria-label={'Recap navigation'} className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-white/10 pb-3 text-sm sm:gap-3">
        <Link to="/blog" className="inline-flex min-h-11 max-w-full items-center gap-1.5 text-zinc-400 hover:text-sand-100 transition-colors">
          <ArrowLeft size={14} />
          <span>{'All Solutions'}</span>
        </Link>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <time dateTime={post.date} className="min-w-0 break-words text-zinc-500 font-mono">
            {formatBlogDate(post.date)}
          </time>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded border border-white/15 px-3 py-1 text-zinc-300 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Share2 size={12} />}
            <span>{copied ? ('Copied') : ('Share')}</span>
          </button>
        </div>
      </nav>

      {/* Hero Solution Card */}
      <header className="min-w-0 rounded-lg border border-white/15 bg-obsidian-900">
        <div className="grid min-w-0 grid-cols-[56px_minmax(0,1fr)] items-start gap-3 p-4 sm:grid-cols-[100px_minmax(0,1fr)] sm:p-6 md:grid-cols-[180px_minmax(0,1fr)] md:items-center md:gap-8 md:p-8">
          {post.country_code ? (
            <div className="flex min-w-0 items-center justify-center rounded-md border border-white/10 bg-obsidian-950 p-1.5 md:p-4">
              <img
                src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                alt={post.country_name}
                className="max-h-10 w-full object-contain drop-shadow-md sm:max-h-16 md:max-h-28"
              />
            </div>
          ) : (
            <div className="flex h-12 min-w-0 items-center justify-center rounded-md border border-white/10 bg-obsidian-950 text-zinc-600 md:h-28">
              <Globe size={32} />
            </div>
          )}

          <div className="min-w-0 space-y-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-emerald-400">
                {'Past-day solution'} · <time dateTime={post.date}>{formatBlogDate(post.date)}</time>
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

            <h1 className="min-w-0 break-words font-serif text-2xl font-bold leading-tight tracking-tight text-sand-100 sm:text-4xl md:text-5xl">
              {post.title}
            </h1>

            {post.subtitle && (
              <p className="max-w-xl break-words text-sm leading-6 text-zinc-400 md:text-base">
                {post.subtitle}
              </p>
            )}

            {cleanDisplayText(post.summary) && cleanDisplayText(post.summary) !== cleanDisplayText(post.subtitle) && (
              <p className="max-w-2xl break-words text-sm leading-relaxed text-zinc-300 md:text-base">
                {cleanDisplayText(post.summary)}
              </p>
            )}

          </div>
        </div>
      </header>
      {sourceLinks.length > 0 && (
        <section aria-label="Sources" className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60 p-4 text-sm text-zinc-300 sm:p-5">
          <h2 className="font-semibold text-sand-100">Sources</h2>
          <ul className="mt-2 space-y-1">
            {sourceLinks.map((source, index) => <li key={index}>{source.safeUrl ? <a href={source.safeUrl} target="_blank" rel="noopener noreferrer" className="break-words text-emerald-300 underline">{source.label}</a> : <span>{source.label} — source URL unavailable</span>}</li>)}
          </ul>
        </section>
      )}


      {/* Quick Facts Grid */}
      {facts && Object.keys(facts).length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-sand-100">
            {'Country at a glance'}
          </h2>
          <div className="grid min-w-0 grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
            {(facts.region || post.continent) && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Region'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.region || post.continent}</span>
              </div>
            )}
            {facts.capital && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Capital'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.capital}</span>
              </div>
            )}
            {facts.population && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Population'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.population}</span>
              </div>
            )}
            {facts.area && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Land area'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.area}</span>
              </div>
            )}
            {facts.coastline && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Maritime access'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.coastline}</span>
              </div>
            )}
            {facts.languages && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{'Official languages'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.languages}</span>
              </div>
            )}
          </div>

          {facts.borders && facts.borders !== 'None' && (
            <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/40 p-4 text-sm">
              <span className="text-zinc-400 block text-xs mb-1.5">{'Bordering neighbors'}</span>
              <span className="break-words text-zinc-300 leading-6">{cleanBorderList(facts.borders)}</span>
            </div>
          )}
        </section>
      )}

      {/* Geographic & Deductive Analysis */}
      <section className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60 p-4 sm:p-6 space-y-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-emerald-300">
          <Globe size={18} className="shrink-0" />
          <span>{'Geographic & Deductive Analysis'}</span>
        </h2>

        <div className="space-y-4 text-sm sm:text-base leading-relaxed text-zinc-300">
          <p>
            {(
              <>
                <strong className="text-sand-100">{post.country_name}</strong> occupies a distinctive position {facts.region || post.continent ? <>in <strong className="text-sand-100">{String(facts.region || post.continent)}</strong></> : 'in global geography'}{facts.capital ? <>, centered administratively around its capital, <strong className="text-sand-100">{String(facts.capital)}</strong></> : null}. {facts.languages ? <>The nation&apos;s linguistic landscape, featuring <strong className="text-sand-100">{String(facts.languages)}</strong>, serves as a defining cultural and regional identifier.</> : <>Its geopolitical profile anchors its identity within the broader continental framework.</>}
              </>
            )}
          </p>

          <p>
            {(
              <>
                From a geographic and demographic perspective, {post.country_name} spans {facts.area ? <>a land area of <strong className="text-sand-100">{String(facts.area)}</strong></> : 'its national territory'}{facts.population ? <> with a population of approximately <strong className="text-sand-100">{String(facts.population)}</strong></> : null}. In terms of maritime connectivity, the country {facts.coastline ? <>features a coastline status of <strong className="text-sand-100">{String(facts.coastline)}</strong></> : 'has unique maritime characteristics'}. Its terrestrial boundary configuration {cleanBorderList(facts.borders) ? <>— including direct borders with <strong className="text-sand-100">{cleanBorderList(facts.borders)}</strong> —</> : facts.borders === 'None' || !facts.borders ? '— with no shared land borders, giving it an insular or isolated territorial profile —' : null} forms a distinct physical signature on the world map.
              </>
            )}
          </p>

          <p>
            {(
              <>
                For players navigating Countrydle&apos;s deductive challenges, <strong className="text-sand-100">{post.country_name}</strong> can be systematically pinpointed using a structured elimination tree. Beginning with macro-geographic queries targeting continent and regional coordinates narrows down hundreds of possibilities to a tight geographic cluster. Next, probing coastline status—determining whether the country has open sea access or is landlocked—instantly bifurcates candidate nations. Finally, analyzing the number and identity of neighboring states alongside linguistic cues allows solvers to rule out adjacent territories and isolate <strong className="text-sand-100">{post.country_name}</strong> with analytical precision.
              </>
            )}
          </p>
        </div>

        {post.deduction_masterclass?.steps && post.deduction_masterclass.steps.length > 0 && (
          <div className="space-y-3 pt-2">
            <h3 className="text-base font-semibold text-sand-100">
              {'Step-by-Step Deduction Path'}
            </h3>
            <ol className="space-y-3">
              {post.deduction_masterclass.steps.map((step, idx) => {
                const answer = step.answer ? step.answer.trim().toUpperCase() : '';
                const isYes = answer === 'YES' || answer === 'TAK';
                const isNo = answer === 'NO' || answer === 'NIE';
                const explanation = cleanDisplayText(step.explanation);
                return (
                  <li
                    key={idx}
                    className="flex min-w-0 items-start gap-3 rounded-md border border-white/10 bg-obsidian-950 p-3 sm:gap-4 sm:p-4"
                  >
                    <span
                      aria-hidden="true"
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/10 font-mono text-xs font-bold text-emerald-300"
                    >
                      {idx + 1}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                        <span className="min-w-0 break-words text-sm font-semibold leading-6 text-sand-100">
                          {step.question}
                        </span>
                        {step.answer && (
                          <span
                            className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${
                              isYes
                                ? 'border-emerald-500/30 bg-emerald-500/20 text-emerald-300'
                                : isNo
                                ? 'border-rose-500/30 bg-rose-500/20 text-rose-300'
                                : 'border-white/15 bg-white/5 text-zinc-300'
                            }`}
                          >
                            {step.answer}
                          </span>
                        )}
                      </div>
                      {explanation && (
                        <p className="min-w-0 break-words text-xs leading-5 text-zinc-400 sm:text-sm">
                          {explanation}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        {post.deduction_masterclass?.pro_tip && cleanDisplayText(post.deduction_masterclass.pro_tip) && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
              <Sparkles size={16} className="shrink-0" />
              <span>{'Strategy Pro-Tip'}</span>
            </div>
            <p className="min-w-0 break-words text-sm sm:text-base leading-relaxed text-sand-100">
              {cleanDisplayText(post.deduction_masterclass.pro_tip)}
            </p>
          </div>
        )}
      </section>

      {/* Country Curiosities */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-amber-300">
            <Sparkles size={18} className="shrink-0" />
            <span>{'Two things worth knowing'}</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {curiosities.map((c, i) => (
              <div key={i} className="min-w-0 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 space-y-2 sm:p-5">
                <span className="block break-words text-base font-semibold leading-6 text-amber-300">
                  #{i + 1} &bull; {c.title}
                </span>
                <p className="break-words text-sm leading-7 text-zinc-300">
                  {cleanDisplayText(c.description)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
      {/* Recorded daily question rankings */}
      <details open className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60">
        <summary className="min-h-11 cursor-pointer px-4 py-4 text-base font-semibold text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 sm:px-6">
          {'How did others play? Stats and questions'}
        </summary>
        <div className="min-w-0 space-y-5 border-t border-white/10 p-4 sm:p-6">
          <div className="flex min-w-0 flex-wrap gap-x-5 gap-y-3 rounded-md border border-white/10 bg-obsidian-950 p-4 text-sm leading-6 text-zinc-400">
            {post.game_debrief?.has_telemetry ? (
              <>
                <span className="min-w-0 break-words text-sand-100">
                  <strong>{post.game_debrief.win_rate_pct}%</strong> {'solved'} ({post.game_debrief.total_solvers} {'of'} {post.game_debrief.total_challengers})
                </span>
                <span className="min-w-0 break-words">
                  {'Average questions to win: '}
                  <strong className="text-sand-100">{post.game_debrief.avg_questions_to_win}</strong>
                </span>
                {post.game_debrief.high_score && (
                  <span className="min-w-0 break-words">
                    {'High score: '}
                    <strong className="text-emerald-300">{post.game_debrief.high_score} {'pts'}</strong>
                  </span>
                )}
              </>
            ) : post.player_stats && post.player_stats.total_players > 0 ? (
              <>
                <span className="min-w-0 break-words text-sand-100">
                  <strong>{post.player_stats.win_rate_pct}%</strong> {'solved'}
                </span>
                <span className="min-w-0 break-words">
                  {'Average questions: '}
                  <strong className="text-sand-100">{post.player_stats.avg_questions_won}</strong>
                </span>
                <span className="min-w-0 break-words">
                  <strong className="text-sand-100">{post.player_stats.total_players}</strong> {'challengers'}
                </span>
              </>
            ) : (
              <span className="min-w-0 break-words">{'Daily puzzle recap'} #{post.id}</span>
            )}
          </div>
          {questionLists.map((list) => (
            <section key={list.title} className="min-w-0 space-y-3">
              <h2 className="text-lg font-semibold leading-snug text-sand-100">{list.title}</h2>
              {list.questions.length > 0 ? (
                <ol className="space-y-3">
                  {list.questions.map((record, index) => {
                    const answer = record.answer.trim().toUpperCase();
                    const isYes = answer === 'YES';
                    const isNo = answer === 'NO';
                    return (
                      <li key={`${record.question}-${record.answer}-${index}`} className="flex min-w-0 items-start gap-2 rounded-md border border-white/5 bg-white/[0.02] p-3 sm:gap-4 sm:p-4">
                        <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 font-mono text-xs font-bold text-sand-100">{index + 1}</span>
                        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 break-words text-sm font-semibold leading-6 text-sand-100">{record.question}</span>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs text-zinc-400">{'Asked'} {record.count}×</span>
                            <span className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${
                              isYes ? 'border-emerald-500/30 bg-emerald-500/20 text-emerald-300' :
                              isNo ? 'border-rose-500/30 bg-rose-500/20 text-rose-300' :
                              'border-white/15 bg-white/5 text-zinc-400'
                            }`}>
                              {isYes ? ('YES') : isNo ? ('NO') : ('Answer not recorded')}
                            </span>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="rounded-md border border-white/5 bg-white/[0.02] p-3 text-sm leading-6 text-zinc-400">{list.empty}</p>
              )}
            </section>
          ))}

      {/* Common Traps & Wrong Guesses */}
      {post.game_debrief?.has_telemetry && post.game_debrief.common_pitfalls.length > 0 && (
        <section className="min-w-0 rounded-lg border border-rose-500/20 bg-rose-500/5 p-4 space-y-3">
          <h2 className="text-base font-semibold text-rose-400">
            {'Common traps and wrong guesses'}
          </h2>
          <p className="text-sm leading-6 text-zinc-300">
            {`Recorded incorrect guesses for the ${post.date} puzzle before players found ${post.country_name}:`}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {post.game_debrief.common_pitfalls.map((pf, idx) => (
              <span key={idx} className="min-w-0 max-w-full break-words rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
                ❌ {pf.guess} <span className="text-rose-400/70 text-xs">({pf.count} {'guesses'})</span>
              </span>
            ))}
          </div>
        </section>
      )}
        </div>
      </details>



      {post.deduction_masterclass?.quiz?.status === 'needs-editorial-repair' && (
        <section aria-label={'Quiz needs editorial repair'} className="min-w-0 space-y-3 rounded-lg border border-amber-400/25 bg-amber-400/5 p-4 text-sm text-amber-100">
          <h2 className="font-semibold">{'Quiz unavailable — needs editorial repair'}</h2>
          <p>{'The stored quiz is incomplete or invalid. We have not invented missing answers. The rest of this article remains available.'}</p>
          <details>
            <summary className="cursor-pointer">{'Stored quiz content (unchanged)'}</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-xs leading-6">{JSON.stringify(post.deduction_masterclass.quiz.stored, null, 2)}</pre>
          </details>
        </section>
      )}

      {/* Interactive Trivia Knowledge Check */}
      {post.deduction_masterclass?.quiz?.status === 'available' && (() => {
        const quiz = post.deduction_masterclass.quiz.content;
        const questionText = cleanDisplayText(quiz.question);
        const correctAnswer = cleanDisplayText(quiz.correct_answer);
        const incorrectDistractor = cleanDisplayText(quiz.incorrect_distractor);
        const explanationText = cleanDisplayText(quiz.explanation);

        const triviaSeed = (post?.id || 0) + (post?.country_name ? post.country_name.length : 0);
        const correctOptionIndex = triviaSeed % 2;
        const triviaOptions = correctOptionIndex === 0
          ? [correctAnswer, incorrectDistractor]
          : [incorrectDistractor, correctAnswer];

        return (
          <section className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900 p-4 space-y-4 sm:p-6">
            <div className="flex items-center gap-2 text-base font-semibold text-emerald-300">
              <Award size={18} className="shrink-0" />
              <span>{'Quick memory check'}</span>
            </div>
            <h3 className="min-w-0 break-words font-serif text-xl font-semibold leading-7 text-sand-100">
              {questionText}
            </h3>

            <div className="space-y-2 text-sm leading-6">
              {triviaOptions.map((optText, idx) => {
                const isSelected = selectedTriviaOption === idx;
                const isCorrect = idx === correctOptionIndex;
                let btnClass = 'border-white/10 bg-white/[0.02] text-zinc-300 hover:border-white/20';
                if (triviaRevealed) {
                  if (isCorrect) {
                    btnClass = 'border-emerald-500 bg-emerald-500/10 text-emerald-300 font-semibold';
                  } else if (isSelected) {
                    btnClass = 'border-rose-500 bg-rose-500/10 text-rose-300 line-through';
                  }
                }
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => { setSelectedTriviaOption(idx); setTriviaRevealed(true); }}
                    className={`min-h-11 w-full min-w-0 break-words text-left p-3 rounded border transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 ${btnClass}`}
                  >
                    {idx === 0 ? 'A) ' : 'B) '}{optText}
                  </button>
                );
              })}
            </div>

            {triviaRevealed && (
              <div role="status" className="break-words rounded bg-emerald-500/10 border border-emerald-500/30 p-3 text-sm leading-6 text-emerald-300">
                <span className="font-bold block mb-1">
                  {selectedTriviaOption === correctOptionIndex
                    ? ('✓ Correct!')
                    : ('Not quite!')}
                </span>
                <span>{explanationText}</span>
              </div>
            )}
          </section>
        );
      })()}

      {/* Compliant Ad Placement */}
      {eligibleForAds && <AdSenseUnit slot="countrydle-blog-post-footer" className="max-w-xl mx-auto" />}

      {/* Related Country Recaps Carousel */}
      {post.related_posts && post.related_posts.length > 0 && (
        <section className="border-t border-white/10 pt-8 space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-sand-100">
            <Globe size={18} className="shrink-0" />
            <span>{'More recent country solutions'}</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {post.related_posts.map((rp) => (
              <Link
                key={rp.id}
                to={`/blog/${rp.slug}`}
                className="group min-w-0 rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-all hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
              >
                <div className="min-w-0">
                  <span className="block min-w-0 break-words text-xs text-emerald-400 mb-2">
                    {rp.country_name}
                  </span>
                  <h4 className="min-w-0 break-words font-serif text-base font-semibold leading-6 text-sand-100 group-hover:text-emerald-300 transition-colors">
                    {rp.title}
                  </h4>
                </div>
                <div className="mt-3 pt-2 border-t border-white/5 flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
                  <time dateTime={rp.date}>{formatBlogDate(rp.date)}</time>
                  <span className="text-emerald-400 group-hover:translate-x-1 transition-transform">&rarr;</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
      {/* Editorial Attribution & Author Byline */}
      <footer className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60 p-4 sm:p-6 text-sm text-zinc-300">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="font-semibold text-sand-100">
              {'Author & Editorial: Jakub Melzacki'}
            </p>
            <p className="text-xs leading-5 text-zinc-400">
              {'Countrydle creator and geography enthusiast. Geographic analysis compiled from verified CIA World Factbook, Natural Earth, and REST Countries data.'}
            </p>
          </div>
          <Link
            to="/about"
            className="inline-flex min-h-11 shrink-0 items-center justify-center rounded border border-white/15 px-3 py-1.5 text-xs text-sand-100 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
          >
            {'About & Sources'}
          </Link>
        </div>
      </footer>


      {/* Play Today's Game CTA */}
      <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6 text-center space-y-3">
        <h3 className="font-serif text-xl font-bold text-sand-100">
          {"Ready for today's daily challenge?"}
        </h3>
        <p className="text-sm leading-6 text-zinc-400 max-w-md mx-auto">
          {'A new mystery country is ready. Test your deduction skills before midnight UTC!'}
        </p>
        <div className="pt-2">
          <Link
            to="/game"
            className="inline-flex min-h-11 max-w-full items-center gap-2 rounded bg-emerald-400 px-4 py-3 text-sm font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors shadow"
          >
            <Play size={14} />
            <span>{"Play today's Countrydle"}</span>
          </Link>
        </div>
      </div>
    </article>
  );
}
