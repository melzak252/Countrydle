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
import { isAxiosError } from 'axios';
import { setPageEditorialEligibility } from '../advertising';
import { usePageMetadata } from '../lib/pageMetadata';
import { blogPostSchema, cleanDisplayText, safeSourceUrl, additionalArticleSections, type BlogPost } from '../blogContent';


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
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
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
        if (data.date >= new Date().toISOString().slice(0, 10)) throw new Error('This solution is not public yet.');
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
  const reviewed = loadedPost?.editorial_status === 'reviewed' && !!loadedPost?.reviewed_at && !!loadedPost?.reviewer_name;
  useEffect(() => {
    setPageEditorialEligibility(reviewed);
    return () => setPageEditorialEligibility(false);
  }, [reviewed, slug]);
  usePageMetadata(loadedPost ? {
    title: `${loadedPost.title} — ${loadedPost.country_name}, ${loadedPost.date} | Countrydle`,
    description: loadedPost.summary || loadedPost.subtitle || `Past-day geography recap for ${loadedPost.country_name}.`,
    canonicalPath: `/blog/${encodeURIComponent(loadedPost.slug || loadedPost.date)}`,
    article: {
      countryName: loadedPost.country_name,
      puzzleDate: loadedPost.date,
      publishedAt: loadedPost.created_at || `${loadedPost.date}T00:00:00Z`,
      updatedAt: loadedPost.updated_at || loadedPost.created_at,
      reviewedBy: reviewed ? loadedPost.reviewer_name || undefined : undefined,
    },
  } : null);

  const handleShare = async () => {
    const url = window.location.href;
    const title = loadedPost?.title || 'Countrydle Solution';
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
      <div data-publisher-ready="false" role="status" aria-label="Loading debrief" className="flex justify-center py-32">
        <Loader2 className="animate-spin text-emerald-400" size={36} />
      </div>
    );
  }

  if (error || !loadedPost) {
    return (
      <div data-publisher-ready="false" data-publisher-error="true" className="mx-auto max-w-3xl py-20 text-center">
        <Globe size={40} className="mx-auto mb-4 text-zinc-600" />
        <h1 className="font-serif text-2xl text-sand-100">Recap unavailable</h1>
        <p role="alert" className="mt-2 text-sm text-zinc-400">{error || 'The recap could not be loaded.'}</p>
        <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 rounded border border-white/20 px-4 py-2 text-sand-100">Try again</button>
        <Link to="/blog" className="mt-6 inline-flex items-center gap-2 rounded bg-emerald-400 px-4 py-2 text-xs font-bold text-obsidian-950">
          <ArrowLeft size={14} /> Back to Daily Journal
        </Link>
      </div>
    );
  }

  const post = loadedPost;
  const stepsByQuestion = new Map<string, { question: string; answer?: string; explanation?: string }>();
  for (const step of post.deduction_masterclass?.steps || []) {
    const key = step.question.trim().toLowerCase();
    if (!key) continue;
    const existing = stepsByQuestion.get(key);
    if (!existing) stepsByQuestion.set(key, { question: step.question, answer: step.answer, explanation: step.explanation });
    else {
      if (step.explanation && !existing.explanation?.includes(step.explanation)) existing.explanation = [existing.explanation, step.explanation].filter(Boolean).join('\n');
      if (step.answer && !existing.answer?.split(' / ').includes(step.answer)) existing.answer = [existing.answer, step.answer].filter(Boolean).join(' / ');
    }
  }
  const steps = [...stepsByQuestion.values()];
  const proTip = post.deduction_masterclass?.pro_tip || '';
  const curiosities = post.fun_facts || [];
  const extraSections = additionalArticleSections(post);
  const sourceLinks = post.source_links.map((source) => ({ ...source, safeUrl: safeSourceUrl(source.url) }));
  const facts = post.fast_facts || {};
  const otherCommunityQuestions = post.game_debrief?.has_telemetry
    ? post.game_debrief.top_questions.filter((question) => !steps.some((step) => step.question.trim().toLowerCase() === question.question.trim().toLowerCase()))
    : [];

  return (
    <article data-publisher-ready="true" className="mx-auto max-w-4xl space-y-10 px-4 py-8 sm:px-6 md:py-12">
      {/* Navigation & Header */}
      <nav aria-label="Debrief navigation" className="flex flex-col items-start gap-3 border-b border-white/10 pb-4 text-xs font-mono sm:flex-row sm:items-center sm:justify-between">
        <Link to="/blog" className="inline-flex min-h-11 max-w-full items-center gap-1.5 text-zinc-400 hover:text-sand-100 transition-colors">
          <ArrowLeft size={14} />
          <span>{isPl ? 'Wszystkie podsumowania' : 'All Solutions'}</span>
        </Link>
        <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:gap-3">
          <span className="min-w-0 break-words text-zinc-500 font-mono">
            {post.date}
          </span>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded border border-white/15 px-3 py-1 text-zinc-300 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
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
                Past-day Solution · {post.date}
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
              {post.title}
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
      <section aria-label="Editorial provenance" className="rounded-lg border border-white/10 bg-obsidian-900/60 p-5 space-y-3 text-sm text-zinc-300">
        <p className="font-semibold text-sand-100">{post.ai_assisted ? 'AI-assisted recap' : 'Countrydle recap'} · {reviewed ? 'Editorially reviewed' : 'Not yet editorially reviewed'}</p>
        {reviewed ? <p>Reviewed by {post.reviewer_name} on <time dateTime={post.reviewed_at || undefined}>{post.reviewed_at}</time>.</p> : <p>Geographical claims and deduction advice may need verification. This page does not carry advertising until an editor reviews it.</p>}
        <p>Published <time dateTime={post.created_at}>{post.created_at}</time> · Updated <time dateTime={post.updated_at || post.created_at}>{post.updated_at || post.created_at}</time></p>
        {post.editorial_note && <p className="whitespace-pre-wrap">{post.editorial_note}</p>}
        {sourceLinks.length ? (
          <div><h2 className="font-semibold text-sand-100">Sources</h2><ul className="mt-2 space-y-1">
            {sourceLinks.map((source, index) => <li key={index}>{source.safeUrl ? <a href={source.safeUrl} target="_blank" rel="noopener noreferrer" className="break-words text-emerald-300 underline">{source.label}</a> : <span>{source.label} — source URL unavailable</span>}</li>)}
          </ul></div>
        ) : <p className="text-amber-300">No source links have been recorded for this recap. Treat factual claims as unverified.</p>}
      </section>
      {post.summary && <p className="text-base leading-7 text-zinc-300">{post.summary}</p>}

      {/* Analysis is not replaced by aggregate question telemetry. */}
      {steps.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-obsidian-900/60 p-6 sm:p-8 space-y-6">
          <h2 className="font-serif text-xl text-sand-100">Deduction path for {post.country_name}</h2>
          <p className="text-xs text-zinc-400">A suggested reasoning sequence, not a measured optimal strategy.</p>
          <ol className="space-y-3">
            {steps.map((step, index) => {
              const evidence = post.game_debrief?.has_telemetry ? post.game_debrief.top_questions?.find((question) => question.question.trim().toLowerCase() === step.question.trim().toLowerCase()) : undefined;
              return <li key={index} className="rounded-md border border-white/10 p-4 space-y-2">
                <h3 className="text-sm font-semibold text-sand-100">{index + 1}. {step.question} <span className="text-emerald-300">— {step.answer || 'Answer not recorded'}</span></h3>
                {step.explanation && <p className="text-sm leading-relaxed text-zinc-300">{cleanDisplayText(step.explanation)}</p>}
                {evidence && <p className="text-xs text-zinc-400">Community evidence: asked {evidence.count} times{evidence.pct != null ? ` (${evidence.pct}%)` : ''}.</p>}
              </li>;
            })}
          </ol>
        </section>
      )}
      {otherCommunityQuestions.length > 0 && (
        <section className="space-y-4">
          <h2 className="font-serif text-xl text-sand-100">Community question evidence</h2>
          <p className="text-xs text-zinc-400">Recorded questions for the {post.date} puzzle. Frequency is not proof of an optimal strategy.</p>
          <ul className="space-y-2 text-sm text-zinc-300">
            {otherCommunityQuestions.map((question, index) => (
              <li key={index}>{question.question} — {question.answer || 'Answer not recorded'}; asked {question.count} times{question.pct != null ? ` (${question.pct}%)` : ''}
                {question.explanation && <p className="mt-1 text-xs">{cleanDisplayText(question.explanation)}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Common Traps & Wrong Guesses */}
      {post.game_debrief?.has_telemetry && post.game_debrief.common_pitfalls && post.game_debrief.common_pitfalls.length > 0 && (
        <section className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-5 space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-rose-400 font-bold">
            <span>⚠️ Common Traps & Wrong Guesses</span>
          </div>
          <p className="text-xs text-zinc-300">
            Recorded incorrect guesses for the {post.date} puzzle before players found {post.country_name}:
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {post.game_debrief.common_pitfalls.map((pf, idx) => (
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
            {Object.entries(facts).filter(([key]) => !['capital', 'population', 'area', 'coastline', 'borders'].includes(key)).map(([key, value]) => (
              <div key={key} className="rounded border border-white/10 bg-obsidian-900/60 p-3">
                <span className="block text-[10px] uppercase text-zinc-500">{key.replaceAll('_', ' ')}</span>
                <span className="mt-0.5 block break-words text-sm font-bold text-sand-100">{value}</span>
              </div>
            ))}
          </div>

          {facts.borders && (
            <div className="rounded border border-white/10 bg-obsidian-900/40 p-4 text-xs font-mono">
              <span className="text-zinc-500 block text-[10px] uppercase mb-1.5">Bordering Neighbors:</span>
              <span className="text-zinc-300 leading-relaxed">{cleanBorderList(facts.borders)}</span>
            </div>
          )}
        </section>
      )}

      {/* Two Things Worth Knowing (Curiosities) */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-amber-400 font-bold flex items-center gap-1.5">
            <Sparkles size={14} />
            <span>Country Curiosities</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {curiosities.map((c, i) => (
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
            <span>Deduction Tip</span>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed text-zinc-200">
            {cleanDisplayText(proTip)}
          </p>
        </section>
      )}

      {/* Interactive Trivia Knowledge Check */}
      {post.deduction_masterclass?.quiz && (() => {
        const quiz = post.deduction_masterclass.quiz;
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
          <section className="rounded-lg border border-white/10 bg-obsidian-900 p-6 space-y-4">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-emerald-400 font-bold">
              <Award size={14} />
              <span>{isPl ? 'Szybki test wiedzy' : 'Quick Memory Check'}</span>
            </div>
            <h3 className="font-serif text-lg font-semibold text-sand-100">
              {questionText}
            </h3>

            <div className="space-y-2 text-xs sm:text-sm">
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
                    className={`w-full text-left p-3 rounded border transition-all ${btnClass}`}
                  >
                    {idx === 0 ? 'A) ' : 'B) '}{optText}
                  </button>
                );
              })}
            </div>

            {triviaRevealed && (
              <div className="rounded bg-emerald-500/10 border border-emerald-500/30 p-3 text-xs text-emerald-300">
                <span className="font-bold block mb-1">
                  {selectedTriviaOption === correctOptionIndex
                    ? (isPl ? '✓ Prawidłowo!' : '✓ Correct!')
                    : (isPl ? 'Niestety nie!' : 'Not quite!')}
                </span>
                <span>{explanationText}</span>
              </div>
            )}
          </section>
        );
      })()}

      {extraSections.length > 0 && <section aria-label="Additional article content" className="space-y-5 text-sm leading-7 text-zinc-300">
        {extraSections.map((section, index) => {
          const lines = section.split('\n');
          const heading = /^#{1,6}\s/.test(lines[0] || '') ? lines.shift()?.replace(/^#{1,6}\s+/, '') : undefined;
          return <div key={index} className="space-y-3 break-words">
            {heading && <h2 className="font-serif text-xl text-sand-100">{cleanDisplayText(heading)}</h2>}
            <p className="whitespace-pre-wrap">{cleanDisplayText(lines.join('\n'))}</p>
          </div>;
        })}
      </section>}
      {/* Compliant Ad Placement */}
      {reviewed && <AdSenseUnit slot="countrydle-blog-post-footer" className="max-w-xl mx-auto" />}

      {/* Related Country Recaps Carousel */}
      {post.related_posts && post.related_posts.length > 0 && (
        <section className="border-t border-white/10 pt-8 space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-zinc-400 font-bold flex items-center gap-1.5">
            <Globe size={14} />
            <span>More Recent Country Solutions</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {post.related_posts.map((rp) => (
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
    </article>
  );
}
