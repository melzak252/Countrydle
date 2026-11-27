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
    title: `${loadedPost.title} (${loadedPost.country_name}, ${loadedPost.date}) | Countrydle`,
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
        <Loader2 className="animate-spin text-app-accent" size={36} />
      </div>
    );
  }

  if (error || !loadedPost) {
    return (
      <div data-publisher-ready="false" data-publisher-error="true" className="mx-auto max-w-3xl py-20 text-center text-app-text">
        <Globe size={40} className="mx-auto mb-4 text-app-text-muted" />
        <h1 className="font-serif text-2xl text-app-text">{'Recap unavailable'}</h1>
        <p role="alert" className="mx-auto mt-2 w-fit rounded-sm border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error || 'The recap could not be loaded.'}</p>
        <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 min-h-11 rounded-sm border border-app-border/20 px-4 py-2 text-app-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{'Try again'}</button>
        <Link to="/blog" className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-sm bg-app-accent px-4 py-2 text-sm font-bold text-white hover:bg-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
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
    <article data-publisher-ready={preview ? undefined : 'true'} className="mx-auto min-w-0 max-w-4xl space-y-6 py-4 text-app-text [overflow-wrap:anywhere] md:space-y-10 md:py-10">
      {/* Navigation & Header */}
      <nav aria-label={'Recap navigation'} className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-app-border/15 pb-3 text-sm sm:gap-3">
        <Link to="/blog" className="inline-flex min-h-11 max-w-full items-center gap-1.5 text-app-text-secondary hover:text-app-text transition-colors">
          <ArrowLeft size={14} />
          <span>{'All Solutions'}</span>
        </Link>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <time dateTime={post.date} className="min-w-0 break-words text-app-text-muted font-mono">
            {formatBlogDate(post.date)}
          </time>
          {!preview && (
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-sm border border-app-border/20 px-3 py-1 text-app-text-secondary hover:border-app-accent/40 hover:text-app-accent transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
          >
            {copied ? <Check size={12} className="text-emerald-700" /> : <Share2 size={12} />}
            <span>{copied ? ('Copied') : ('Share')}</span>
          </button>
          )}
        </div>
      </nav>

      {/* Hero Solution Card */}
      <header className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface">
        <div className="grid min-w-0 grid-cols-[56px_minmax(0,1fr)] items-start gap-3 p-4 sm:grid-cols-[100px_minmax(0,1fr)] sm:p-6 md:grid-cols-[180px_minmax(0,1fr)] md:items-center md:gap-8 md:p-8">
          {post.country_code ? (
            <div className="flex min-w-0 items-center justify-center rounded-sm border border-app-border/15 bg-app-canvas p-1.5 md:p-4">
              <img
                src={`https://flagcdn.com/w320/${post.country_code.toLowerCase()}.png`}
                alt={post.country_name}
                className="max-h-10 w-full object-contain drop-shadow-md sm:max-h-16 md:max-h-28"
              />
            </div>
          ) : (
            <div className="flex h-12 min-w-0 items-center justify-center rounded-sm border border-app-border/15 bg-app-canvas text-app-text-muted md:h-28">
              <Globe size={32} />
            </div>
          )}

          <div className="min-w-0 space-y-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-app-accent">
                {'Past-day solution'} · <time dateTime={post.date}>{formatBlogDate(post.date)}</time>
              </span>
              <span className="text-app-text-muted">&bull;</span>
              {post.continent && (
                <span className="rounded-sm bg-app-accent/10 px-2 py-0.5 font-mono text-[10px] text-app-accent border border-app-accent/20">
                  {post.continent}
                </span>
              )}
              {post.difficulty && (
                <span className={`px-2 py-0.5 rounded-sm font-mono text-[10px] ${
                  post.difficulty === 'Easy' ? 'bg-emerald-100 text-emerald-800' :
                  post.difficulty === 'Challenging' ? 'bg-rose-100 text-rose-800' :
                  'bg-amber-100 text-amber-900'
                }`}>
                  {post.difficulty}
                </span>
              )}
            </div>

            <h1 className="min-w-0 break-words font-serif text-2xl font-bold leading-tight tracking-tight text-app-text sm:text-4xl md:text-5xl">
              {post.title}
            </h1>

            {heroLead && (
              <p className="max-w-2xl break-words text-sm leading-relaxed text-app-text-secondary md:text-base">
                {heroLead}
              </p>
            )}

          </div>
        </div>
      </header>
      {sourceLinks.length > 0 && (
        <section aria-label="Sources" className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-4 text-sm text-app-text-secondary sm:p-5">
          <h2 className="font-semibold text-app-text">Sources</h2>
          <ul className="mt-2 space-y-1">
            {sourceLinks.map((source, index) => <li key={index}>{source.safeUrl ? <a href={source.safeUrl} target="_blank" rel="noopener noreferrer" className="break-words text-app-accent underline">{source.label}</a> : <span>{source.label} (source URL unavailable)</span>}</li>)}
          </ul>
        </section>
      )}


      {/* Quick Facts Grid */}
      {facts && Object.keys(facts).length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-app-text">
            {'Country at a glance'}
          </h2>
          <div className="grid min-w-0 grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
            {(facts.region || post.continent) && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Region'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.region || post.continent}</span>
              </div>
            )}
            {facts.capital && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Capital'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.capital}</span>
              </div>
            )}
            {facts.population && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Population'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.population}</span>
              </div>
            )}
            {facts.area && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Land area'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.area}</span>
              </div>
            )}
            {facts.coastline && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Maritime access'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.coastline}</span>
              </div>
            )}
            {facts.languages && (
              <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-3 flex flex-col justify-center">
                <span className="text-app-text-muted block text-xs">{'Languages in the dataset'}</span>
                <span className="text-app-text font-bold text-sm block mt-0.5 break-words">{facts.languages}</span>
              </div>
            )}
          </div>

          {facts.borders && facts.borders !== 'None' && (
            <div className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface-muted p-4 text-sm">
              <span className="text-app-text-muted block text-xs mb-1.5">{'Bordering neighbors'}</span>
              <span className="break-words text-app-text-secondary leading-6">{cleanBorderList(facts.borders)}</span>
            </div>
          )}
        </section>
      )}

      {/* Geographic & Deductive Analysis */}
      <section className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-4 sm:p-6 space-y-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-app-accent">
          <Globe size={18} className="shrink-0" />
          <span>{'Geographic & Deductive Analysis'}</span>
        </h2>

        {post.content_markdown && post.content_markdown.trim() && (
          <MarkdownRenderer content={post.content_markdown} />
        )}

        {post.deduction_masterclass?.steps && post.deduction_masterclass.steps.length > 0 && (
          <div className="space-y-3 pt-2">
            <h3 className="text-base font-semibold text-app-text">
              {'Questions recorded across games'}
            </h3>
            <p className="text-sm text-app-text-secondary">These questions may come from different players; they are not a single player&apos;s path.</p>
            <ol className="space-y-3">
              {post.deduction_masterclass.steps.map((step, idx) => {
                const answer = step.answer ? step.answer.trim().toUpperCase() : '';
                const isYes = answer === 'YES' || answer === 'TAK';
                const isNo = answer === 'NO' || answer === 'NIE';
                const explanation = cleanDisplayText(step.explanation);
                return (
                  <li
                    key={idx}
                    className="flex min-w-0 items-start gap-3 rounded-sm border border-app-border/15 bg-app-surface-muted p-3 sm:gap-4 sm:p-4"
                  >
                    <span
                      aria-hidden="true"
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-app-accent/30 bg-app-accent/10 font-mono text-xs font-bold text-app-accent"
                    >
                      {idx + 1}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                        <span className="min-w-0 break-words text-sm font-semibold leading-6 text-app-text">
                          {step.question}
                        </span>
                        {step.answer && (
                          <span
                            className={`rounded-sm border px-2 py-0.5 font-mono text-[10px] font-bold ${
                              isYes
                                ? 'border-emerald-300 bg-emerald-100 text-emerald-800'
                                : isNo
                                ? 'border-rose-300 bg-rose-100 text-rose-800'
                                : 'border-app-border/20 bg-app-surface text-app-text-secondary'
                            }`}
                          >
                            {step.answer}
                          </span>
                        )}
                      </div>
                      {explanation && (
                        <p className="min-w-0 break-words text-xs leading-5 text-app-text-secondary sm:text-sm">
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
          <div className="rounded-sm border border-emerald-200 bg-emerald-50 p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
              <Sparkles size={16} className="shrink-0" />
              <span>{'Strategy Pro-Tip'}</span>
            </div>
            <p className="min-w-0 break-words text-sm sm:text-base leading-relaxed text-app-text-secondary">
              {cleanDisplayText(post.deduction_masterclass.pro_tip)}
            </p>
          </div>
        )}

        {post.deduction_analysis?.has_analysis && (
          <div className="space-y-6 pt-4 border-t border-app-border/15">
            {/* Catalog Provenance & Non-Single-Player Walkthrough Disclaimer */}
            <div className="rounded-sm border border-app-border/15 bg-app-surface-muted p-3 sm:p-4 text-xs space-y-1.5">
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-app-accent flex items-center gap-1.5">
                  <Globe size={14} className="shrink-0 text-app-accent" />
                  {'Deterministic Catalog Deduction Analysis'}
                </span>
                <span className="font-mono text-[11px] text-app-text-muted break-words">
                  {post.deduction_analysis.catalog_provenance}
                </span>
              </div>
              <p className="leading-5 text-app-text-secondary">
                {post.deduction_analysis.disclaimer}
              </p>
            </div>

            {/* Candidate Funnel */}
            {post.deduction_analysis.candidate_funnel.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-base font-semibold text-app-text">
                  {'Illustrative Candidate Funnel'}
                </h3>
                <p className="text-xs text-app-text-secondary">
                  {'How candidate country pools narrow using verifiable geographic attributes in our present catalog:'}
                </p>
                <ol className="space-y-2">
                  {post.deduction_analysis.candidate_funnel.map((step, idx) => (
                    <li
                      key={idx}
                      className="flex min-w-0 items-start gap-3 rounded-sm border border-app-border/15 bg-app-surface-muted p-3"
                    >
                      <span
                        aria-hidden="true"
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-app-accent/30 bg-app-accent/10 font-mono text-xs font-bold text-app-accent"
                      >
                        {idx + 1}
                      </span>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-app-text break-words">
                            {step.criterion}
                          </span>
                          <span className="rounded-sm border border-app-accent/30 bg-app-accent/10 px-2 py-0.5 font-mono text-xs font-bold text-app-accent">
                            {step.remaining_count} {step.remaining_count === 1 ? 'candidate' : 'candidates'}
                          </span>
                        </div>
                        <p className="text-xs text-app-text-secondary break-words">{step.explanation}</p>
                        {step.sample_candidates.length > 0 && step.remaining_count > 1 && (
                          <p className="text-[11px] text-app-text-muted font-mono break-words">
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
                      className="rounded-sm border border-app-border/15 bg-app-surface-muted p-4 space-y-3"
                    >
                      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-app-border/15 pb-2">
                        <span className="text-sm font-semibold text-rose-800 break-words">
                          ❌ {cmp.guess}
                        </span>
                        <span className="text-xs text-app-text-muted">
                          {cmp.count} {cmp.count === 1 ? 'recorded guess' : 'recorded guesses'}
                        </span>
                      </div>

                      {cmp.shared_traits.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider block">
                            {'Shared traits'}
                          </span>
                          <ul className="text-xs text-app-text-secondary space-y-0.5 list-disc list-inside">
                            {cmp.shared_traits.map((t, tIdx) => (
                              <li key={tIdx} className="break-words">{t}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {cmp.differences.length > 0 && cmp.differences.some((d) => d.includes('unknown') || d.includes('not found')) && (
                        <div className="space-y-1">
                          <span className="text-xs font-semibold text-amber-900 uppercase tracking-wider block">
                            {'Catalog notes'}
                          </span>
                          <ul className="text-xs text-app-text-secondary space-y-0.5 list-disc list-inside">
                            {cmp.differences.map((d, dIdx) => (
                              <li key={dIdx} className="break-words">{d}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {cmp.target_facts && cmp.guess_facts && (
                        <div className="overflow-x-auto pt-1">
                          <table className="w-full text-left text-xs border border-app-border/15">
                            <thead>
                              <tr className="border-b border-app-border/15 bg-app-surface-muted">
                                <th className="p-2 text-app-text-muted font-normal">{'Catalog Attribute'}</th>
                                <th className="p-2 text-app-accent font-semibold">{post.country_name}</th>
                                <th className="p-2 text-rose-800 font-semibold">{cmp.guess}</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-app-border/10 text-app-text-secondary">
                              {['Capital', 'Continent', 'Region', 'Coastline', 'Borders'].map((attr) => {
                                const key = attr.toLowerCase();
                                const tVal = cmp.target_facts[key] || 'N/A';
                                const gVal = cmp.guess_facts[key] || 'N/A';
                                return (
                                  <tr key={attr}>
                                    <td className="p-2 text-app-text-muted font-mono text-[11px]">{attr}</td>
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

      {/* Country Curiosities — Pinned Sticky Notes */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="flex items-center gap-2 font-serif text-xl font-semibold text-amber-900">
            <Sparkles size={18} className="shrink-0" />
            <span>{'Field notes & curiosities'}</span>
          </h2>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            {curiosities.map((c, i) => (
              <div
                key={i}
                className={`relative min-w-0 rounded-sm border p-5 pt-6 space-y-2 shadow-[2px_5px_14px_rgba(85,75,57,0.10)] transition-transform duration-200 hover:rotate-0 hover:-translate-y-0.5 ${
                  i % 2 === 0
                    ? 'border-[#d8c08a] bg-[#fdf5dc] -rotate-[0.6deg]'
                    : 'border-[#c4cfb9] bg-[#f4f7ed] rotate-[0.6deg]'
                }`}
              >
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -top-2 left-1/2 h-4 w-14 -translate-x-1/2 rotate-1 rounded-[1px] border border-[#b9a578]/50 bg-[#e6d7b5]/85 shadow-xs"
                />
                <span className="block break-words font-serif text-lg font-semibold leading-6 text-app-text">
                  <span className="mr-1.5 font-mono text-xs text-app-accent">#{i + 1}</span>
                  {c.title}
                </span>
                <p className="break-words text-sm leading-7 text-app-text-secondary">
                  {cleanDisplayText(c.description)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
      {/* Recorded daily question rankings */}
      <details open className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface">
        <summary className="min-h-11 cursor-pointer px-4 py-4 text-base font-semibold text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus sm:px-6">
          {'How did others play? Stats and questions'}
        </summary>
        <div className="min-w-0 space-y-5 border-t border-app-border/15 p-4 sm:p-6">
          <div className="flex min-w-0 flex-wrap gap-x-5 gap-y-3 rounded-sm border border-app-border/15 bg-app-surface-muted p-4 text-sm leading-6 text-app-text-secondary">
            {post.game_debrief?.has_telemetry ? (
              <>
                <span className="min-w-0 break-words text-app-text">
                  <strong>{post.game_debrief.win_rate_pct}%</strong> {'solved'} ({post.game_debrief.total_solvers} {'of'} {post.game_debrief.total_challengers})
                </span>
                <span className="min-w-0 break-words">
                  {'Average questions to win: '}
                  <strong className="text-app-text">{post.game_debrief.avg_questions_to_win}</strong>
                </span>
                {post.game_debrief.high_score && (
                  <span className="min-w-0 break-words">
                    {'High score: '}
                    <strong className="text-app-accent">{post.game_debrief.high_score} {'pts'}</strong>
                  </span>
                )}
              </>
            ) : post.player_stats && post.player_stats.total_players > 0 ? (
              <>
                <span className="min-w-0 break-words text-app-text">
                  <strong>{post.player_stats.win_rate_pct}%</strong> {'solved'}
                </span>
                <span className="min-w-0 break-words">
                  {'Average questions: '}
                  <strong className="text-app-text">{post.player_stats.avg_questions_won}</strong>
                </span>
                <span className="min-w-0 break-words">
                  <strong className="text-app-text">{post.player_stats.total_players}</strong> {'challengers'}
                </span>
              </>
            ) : (
              <span className="min-w-0 break-words">{'Daily puzzle recap'} #{post.id}</span>
            )}
          </div>
          {questionLists.map((list) => (
            <section key={list.title} className="min-w-0 space-y-2">
              <h2 className="text-lg font-semibold leading-snug text-app-text">{list.title}</h2>
              {list.description && (
                <p className="text-xs text-app-text-secondary">{list.description}</p>
              )}
              {list.questions.length > 0 ? (
                <ol className="space-y-3 pt-1">
                  {list.questions.map((record, index) => {
                    const answer = record.answer.trim().toUpperCase();
                    const isYes = answer === 'YES';
                    const isNo = answer === 'NO';
                    return (
                      <li key={`${record.question}-${record.answer}-${index}`} className="flex min-w-0 items-start gap-2 rounded-sm border border-app-border/15 bg-app-surface p-3 sm:gap-4 sm:p-4">
                        <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-app-border/15 bg-app-surface-muted font-mono text-xs font-bold text-app-text">{index + 1}</span>
                        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 break-words text-sm font-semibold leading-6 text-app-text">{record.question}</span>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs text-app-text-muted">{'Asked'} {record.count}×</span>
                            <span
                              className={`rounded-sm border px-2 py-0.5 font-mono text-[10px] font-bold ${
                                isYes ? 'border-emerald-300 bg-emerald-100 text-emerald-800' :
                                isNo ? 'border-rose-300 bg-rose-100 text-rose-800' :
                                'border-app-border/20 bg-app-surface-muted text-app-text-secondary'
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
                <p className="rounded-sm border border-app-border/15 bg-app-surface-muted p-3 text-sm leading-6 text-app-text-secondary">{list.empty}</p>
              )}
            </section>
          ))}

      {/* Common Traps & Wrong Guesses */}
      {post.game_debrief?.has_telemetry && post.game_debrief.common_pitfalls.length > 0 && (
        <section className="min-w-0 rounded-sm border border-rose-200 bg-rose-50 p-4 space-y-3">
          <h2 className="text-base font-semibold text-rose-800">
            {'Common traps and wrong guesses'}
          </h2>
          <p className="text-sm leading-6 text-app-text-secondary">
            {`Recorded incorrect guesses for the ${post.date} puzzle before players found ${post.country_name}:`}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {post.game_debrief.common_pitfalls.map((pf, idx) => (
              <span key={idx} className="min-w-0 max-w-full break-words rounded-sm border border-rose-200 bg-rose-100 px-3 py-2 text-sm text-rose-800">
                ❌ {pf.guess} <span className="text-rose-800/80 text-xs">({pf.count} {'guesses'})</span>
              </span>
            ))}
          </div>
        </section>
      )}
        </div>
      </details>



      {post.deduction_masterclass?.quiz?.status === 'needs-editorial-repair' && (
        <section aria-label={'Quiz needs editorial repair'} className="min-w-0 space-y-3 rounded-sm border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <h2 className="font-semibold">{'Quiz unavailable (needs editorial repair)'}</h2>
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
          <section className="relative min-w-0 rounded-sm border border-[#d3c39f] bg-[#fbf6e8] p-5 pt-7 space-y-4 shadow-[2px_5px_16px_rgba(85,75,57,0.10)] sm:p-6 sm:pt-8">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -top-2 left-1/2 h-4 w-16 -translate-x-1/2 -rotate-1 rounded-[1px] border border-[#b9a578]/50 bg-[#e6d7b5]/85 shadow-xs"
            />
            <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-app-accent">
              <Award size={16} className="shrink-0" />
              <span>{'Quick memory check'}</span>
            </div>
            <h3 className="min-w-0 break-words font-serif text-xl font-semibold leading-7 text-app-text">
              {questionText}
            </h3>

            <div className="space-y-2 text-sm leading-6">
              {triviaOptions.map((optText, idx) => {
                const isSelected = selectedTriviaOption === idx;
                const isCorrect = idx === correctOptionIndex;
                let btnClass = 'border-app-border/20 bg-app-surface-muted text-app-text-secondary hover:border-app-border/30';
                if (triviaRevealed) {
                  if (isCorrect) {
                    btnClass = 'border-emerald-300 bg-emerald-100 text-emerald-800 font-semibold';
                  } else if (isSelected) {
                    btnClass = 'border-rose-300 bg-rose-100 text-rose-800 line-through';
                  }
                }
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => { setSelectedTriviaOption(idx); setTriviaRevealed(true); }}
                    className={`min-h-11 w-full min-w-0 break-words text-left p-3 rounded-sm border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus ${btnClass}`}
                  >
                    {idx === 0 ? 'A) ' : 'B) '}{optText}
                  </button>
                );
              })}
            </div>

            {triviaRevealed && (
              <div role="status" className={`break-words rounded-sm border p-3 text-sm leading-6 ${selectedTriviaOption === correctOptionIndex ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
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
        <section className="border-t border-app-border/15 pt-8 space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-app-text">
            <Globe size={18} className="shrink-0" />
            <span>{'More recent country solutions'}</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {post.related_posts.map((rp) => (
              <Link
                key={rp.id}
                to={`/blog/${rp.slug}`}
                className="group min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-4 transition-colors hover:border-app-accent/40 hover:bg-app-surface-muted flex flex-col justify-between focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
              >
                <div className="min-w-0">
                  <span className="block min-w-0 break-words text-xs text-app-accent mb-2">
                    {rp.country_name}
                  </span>
                  <h4 className="min-w-0 break-words font-serif text-base font-semibold leading-6 text-app-text group-hover:text-app-accent transition-colors">
                    {rp.title}
                  </h4>
                </div>
                <div className="mt-3 pt-2 border-t border-app-border/10 flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-app-text-muted">
                  <time dateTime={rp.date}>{formatBlogDate(rp.date)}</time>
                  <span className="text-app-accent group-hover:translate-x-1 transition-transform">&rarr;</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
      {/* Editorial Attribution & Author Byline */}
      <footer className="min-w-0 rounded-sm border border-app-border/15 bg-app-surface p-4 sm:p-6 text-sm text-app-text-secondary">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="font-semibold text-app-text">
              {post.ai_assisted ? 'AI-assisted recap' : 'Countrydle recap'}
            </p>
            <p className="text-xs leading-5 text-app-text-muted">
              {reviewed ? `Publication approved by ${post.reviewer_name} on ${post.reviewed_at}.` : 'No publication approval recorded.'}
            </p>
            {post.editorial_note && <p className="text-xs leading-5 text-app-text-muted">{post.editorial_note}</p>}
          </div>
          <Link
            to="/about"
            className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-sm border border-app-border/20 px-3 py-1.5 text-xs text-app-text-secondary hover:border-app-accent/40 hover:text-app-accent transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
          >
            {'About & Sources'}
          </Link>
        </div>
      </footer>


      {/* Play Today's Game CTA */}
      <div className="rounded-sm border border-app-accent/20 bg-app-accent/5 p-6 text-center space-y-3">
        <h3 className="font-serif text-xl font-bold text-app-text">
          {"Ready for today's daily challenge?"}
        </h3>
        <p className="text-sm leading-6 text-app-text-secondary max-w-md mx-auto">
          {'A new mystery country is ready. Test your deduction skills before midnight UTC!'}
        </p>
        <div className="pt-2">
          <Link
            to="/game"
            className="inline-flex min-h-11 max-w-full items-center gap-2 rounded-sm bg-app-accent px-4 py-3 text-sm font-bold text-white hover:bg-app-accent-hover transition-colors shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
          >
            <Play size={14} />
            <span>{"Play today's Countrydle"}</span>
          </Link>
        </div>
      </div>
    </article>
  );
}
