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
import MarkdownRenderer from '../components/MarkdownRenderer';
import { isAxiosError } from 'axios';
import { setPageEditorialEligibility } from '../advertising';
import { usePageMetadata } from '../lib/pageMetadata';
import { blogPostSchema, cleanDisplayText, safeSourceUrl, type BlogPost } from '../blogContent';
import RecapComparisonMap from '../components/RecapComparisonMap';


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
  const [error, setError] = useState<string | null>(null);
  const [loadedSlug, setLoadedSlug] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let isMounted = true;
    const fetchPost = async () => {
      setLoading(true);
      setPost(null);
      setError(null);
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
    },
  } : null);


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

  return <BlogArticle key={loadedPost.id} post={loadedPost} eligibleForAds={eligibleForAds} />;
}

export function BlogArticle({ post, eligibleForAds = false, preview = false }: { post: BlogPost; eligibleForAds?: boolean; preview?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [selectedTriviaOption, setSelectedTriviaOption] = useState<number | null>(null);
  const [triviaRevealed, setTriviaRevealed] = useState(false);
  const reviewed = post.editorial_status === 'reviewed' && !!post.reviewed_at && !!post.reviewer_name;
  const handleShare = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: post.title, url });
        return;
      } catch {
        // Fallback to clipboard
      }
    }
    await navigator.clipboard.writeText(url);
    setCopied(true);
    toast.success('Link copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };
  const curiosities = post.fun_facts || [];
  const sourceLinks = post.source_links.map((source) => ({ ...source, safeUrl: safeSourceUrl(source.url) }));
  const facts = post.fast_facts || {};
  const hasMarkdownBody = Boolean(post.content_markdown && post.content_markdown.trim());
  const heroLead = hasMarkdownBody
    ? ''
    : (cleanDisplayText(post.summary) || cleanDisplayText(post.subtitle));
  const questionLists = [
    {
      title: 'Recorded in-game questions (all players)',
      description: `Player questions and automated feedback logged during active matches on ${formatBlogDate(post.date)}. In-game responses reflect match logs, not verified catalog facts.`,
      questions: post.game_debrief?.top_questions ?? [],
      empty: 'No recorded questions in gameplay logs for this daily puzzle.',
    },
    {
      title: 'Recorded in-game questions (winning runs)',
      description: `Player questions asked by solvers who completed the puzzle on ${formatBlogDate(post.date)}.`,
      questions: post.game_debrief?.top_winner_questions ?? [],
      empty: 'No recorded questions linked to winners in gameplay logs for this daily puzzle.',
    },
  ];
  return (
    <article data-publisher-ready={preview ? undefined : 'true'} className="mx-auto min-w-0 max-w-4xl space-y-6 py-4 [overflow-wrap:anywhere] md:space-y-10 md:py-10">
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
          {!preview && (
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded border border-white/15 px-3 py-1 text-zinc-300 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Share2 size={12} />}
            <span>{copied ? ('Copied') : ('Share')}</span>
          </button>
          )}
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

            {heroLead && (
              <p className="max-w-2xl break-words text-sm leading-relaxed text-zinc-300 md:text-base">
                {heroLead}
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
                <span className="text-zinc-400 block text-xs">{'Languages in the dataset'}</span>
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

        {post.content_markdown && post.content_markdown.trim() && (
          <MarkdownRenderer content={post.content_markdown} />
        )}

        {post.deduction_masterclass?.steps && post.deduction_masterclass.steps.length > 0 && (
          <div className="space-y-3 pt-2">
            <h3 className="text-base font-semibold text-sand-100">
              {'Questions recorded across games'}
            </h3>
            <p className="text-sm text-zinc-400">These questions may come from different players; they are not a single player&apos;s path.</p>
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

        {post.deduction_analysis?.has_analysis && (
          <div className="space-y-6 pt-4 border-t border-white/10">
            {/* Catalog Provenance & Non-Single-Player Walkthrough Disclaimer */}
            <div className="rounded-md border border-white/10 bg-obsidian-950 p-3 sm:p-4 text-xs space-y-1.5">
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-emerald-300 flex items-center gap-1.5">
                  <Globe size={14} className="shrink-0 text-emerald-400" />
                  {'Deterministic Catalog Deduction Analysis'}
                </span>
                <span className="font-mono text-[11px] text-zinc-500 break-words">
                  {post.deduction_analysis.catalog_provenance}
                </span>
              </div>
              <p className="leading-5 text-zinc-400">
                {post.deduction_analysis.disclaimer}
              </p>
            </div>

            {/* Candidate Funnel */}
            {post.deduction_analysis.candidate_funnel.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-base font-semibold text-sand-100">
                  {'Illustrative Candidate Funnel'}
                </h3>
                <p className="text-xs text-zinc-400">
                  {'How candidate country pools narrow using verifiable geographic attributes in our present catalog:'}
                </p>
                <ol className="space-y-2">
                  {post.deduction_analysis.candidate_funnel.map((step, idx) => (
                    <li
                      key={idx}
                      className="flex min-w-0 items-start gap-3 rounded-md border border-white/10 bg-obsidian-950 p-3"
                    >
                      <span
                        aria-hidden="true"
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/10 font-mono text-xs font-bold text-emerald-300"
                      >
                        {idx + 1}
                      </span>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-sand-100 break-words">
                            {step.criterion}
                          </span>
                          <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-xs font-bold text-emerald-300">
                            {step.remaining_count} {step.remaining_count === 1 ? 'candidate' : 'candidates'}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-400 break-words">{step.explanation}</p>
                        {step.sample_candidates.length > 0 && step.remaining_count > 1 && (
                          <p className="text-[11px] text-zinc-500 font-mono break-words">
                            {'Sample pool: '}
                            {step.sample_candidates.join(', ')}
                            {step.remaining_count > step.sample_candidates.length ? '…' : ''}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Catalog Comparison: Target vs Common Misguesses */}
            {post.deduction_analysis.wrong_guess_comparisons.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3 className="text-base font-semibold text-sand-100">
                  {'Catalog Comparison: Target vs. Common Misguesses'}
                </h3>
                <p className="text-xs text-zinc-400">
                  {`Comparing catalog facts between ${post.country_name} and recorded common incorrect guesses:`}
                </p>
                {!preview && (
                  <RecapComparisonMap
                    key={`recap-map-${post.slug || post.date}`}
                    targetName={post.country_name}
                    wrongGuesses={post.deduction_analysis.wrong_guess_comparisons}
                  />
                )}
                <div className="space-y-3">
                  {post.deduction_analysis.wrong_guess_comparisons.map((cmp, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-white/10 bg-obsidian-950 p-4 space-y-3"
                    >
                      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2">
                        <span className="text-sm font-semibold text-rose-300 break-words">
                          ❌ {cmp.guess}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {cmp.count} {cmp.count === 1 ? 'recorded guess' : 'recorded guesses'}
                        </span>
                      </div>

                      {cmp.shared_traits.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider block">
                            {'Shared traits'}
                          </span>
                          <ul className="text-xs text-zinc-300 space-y-0.5 list-disc list-inside">
                            {cmp.shared_traits.map((t, tIdx) => (
                              <li key={tIdx} className="break-words">{t}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {cmp.differences.length > 0 && cmp.differences.some((d) => d.includes('unknown') || d.includes('not found')) && (
                        <div className="space-y-1">
                          <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider block">
                            {'Catalog notes'}
                          </span>
                          <ul className="text-xs text-zinc-300 space-y-0.5 list-disc list-inside">
                            {cmp.differences.map((d, dIdx) => (
                              <li key={dIdx} className="break-words">{d}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {cmp.target_facts && cmp.guess_facts && (
                        <div className="overflow-x-auto pt-1">
                          <table className="w-full text-left text-xs border border-white/10">
                            <thead>
                              <tr className="border-b border-white/10 bg-white/[0.03]">
                                <th className="p-2 text-zinc-400 font-normal">{'Catalog Attribute'}</th>
                                <th className="p-2 text-emerald-300 font-semibold">{post.country_name}</th>
                                <th className="p-2 text-rose-300 font-semibold">{cmp.guess}</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5 text-zinc-300">
                              {['Capital', 'Continent', 'Region', 'Coastline', 'Borders'].map((attr) => {
                                const key = attr.toLowerCase();
                                const tVal = cmp.target_facts[key] || 'N/A';
                                const gVal = cmp.guess_facts[key] || 'N/A';
                                return (
                                  <tr key={attr}>
                                    <td className="p-2 text-zinc-500 font-mono text-[11px]">{attr}</td>
                                    <td className="p-2 break-words">{tVal}</td>
                                    <td className="p-2 break-words">{gVal}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Country Curiosities */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-amber-300">
            <Sparkles size={18} className="shrink-0" />
            <span>{'Country context'}</span>
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
            <section key={list.title} className="min-w-0 space-y-2">
              <h2 className="text-lg font-semibold leading-snug text-sand-100">{list.title}</h2>
              {list.description && (
                <p className="text-xs text-zinc-400">{list.description}</p>
              )}
              {list.questions.length > 0 ? (
                <ol className="space-y-3 pt-1">
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
                            <span
                              className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${
                                isYes ? 'border-emerald-500/30 bg-emerald-500/20 text-emerald-300' :
                                isNo ? 'border-rose-500/30 bg-rose-500/20 text-rose-300' :
                                'border-white/15 bg-white/5 text-zinc-400'
                              }`}
                              title="In-game match response from gameplay logs, not verified catalog facts"
                            >
                              <span className="text-[9px] font-normal opacity-75 mr-1">Game log:</span>
                              {record.answer || 'Not recorded'}
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
                    className={`min-h-11 w-full min-w-0 break-words text-left p-3 rounded border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 ${btnClass}`}
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
      {!preview && eligibleForAds && <AdSenseUnit slot="countrydle-blog-post-footer" className="max-w-xl mx-auto" />}

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
                className="group min-w-0 rounded-md border border-white/10 bg-obsidian-900/60 p-4 transition-colors hover:border-emerald-500/40 hover:bg-obsidian-900 flex flex-col justify-between focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
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
              {post.ai_assisted ? 'AI-assisted recap' : 'Countrydle recap'}
            </p>
            <p className="text-xs leading-5 text-zinc-400">
              {reviewed ? `Publication approved by ${post.reviewer_name} on ${post.reviewed_at}.` : 'No publication approval recorded.'}
            </p>
            {post.editorial_note && <p className="text-xs leading-5 text-zinc-400">{post.editorial_note}</p>}
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
