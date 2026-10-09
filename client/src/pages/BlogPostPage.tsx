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
  const reviewed = loadedPost?.editorial_status === 'reviewed' && !!loadedPost?.reviewed_at && !!loadedPost?.reviewer_name;
  useEffect(() => {
    setPageEditorialEligibility(reviewed);
    return () => setPageEditorialEligibility(false);
  }, [reviewed, slug]);
  usePageMetadata(loadedPost ? {
    title: `${loadedPost.title} — ${loadedPost.country_name}, ${loadedPost.date} | Countrydle`,
    description: `Past-day recap for ${loadedPost.country_name} (${loadedPost.date}). ${loadedPost.summary || loadedPost.subtitle || 'Country-specific geography and deduction analysis.'}`,
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
    const title = loadedPost?.title || (isPl ? 'Rozwiązanie Countrydle' : 'Countrydle solution');
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
    toast.success(isPl ? 'Link skopiowany do schowka!' : 'Link copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading || (!error && loadedSlug !== slug)) {
    return (
      <div data-publisher-ready="false" role="status" aria-label={isPl ? 'Ładowanie podsumowania' : 'Loading recap'} className="flex justify-center py-32">
        <Loader2 className="animate-spin text-emerald-400" size={36} />
      </div>
    );
  }

  if (error || !loadedPost) {
    return (
      <div data-publisher-ready="false" data-publisher-error="true" className="mx-auto max-w-3xl py-20 text-center">
        <Globe size={40} className="mx-auto mb-4 text-zinc-600" />
        <h1 className="font-serif text-2xl text-sand-100">{isPl ? 'Podsumowanie niedostępne' : 'Recap unavailable'}</h1>
        <p role="alert" className="mt-2 text-sm text-zinc-400">{error || 'The recap could not be loaded.'}</p>
        <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-4 min-h-11 rounded border border-white/20 px-4 py-2 text-sand-100">{isPl ? 'Spróbuj ponownie' : 'Try again'}</button>
        <Link to="/blog" className="mt-6 inline-flex min-h-11 items-center gap-2 rounded bg-emerald-400 px-4 py-2 text-sm font-bold text-obsidian-950">
          <ArrowLeft size={14} /> {isPl ? 'Wróć do dziennika' : 'Back to journal'}
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

  const localizedMeta = (value: string): string => {
    if (!isPl) return value;
    const labels: Record<string, string> = {
      Africa: 'Afryka', Americas: 'Ameryki', 'North America': 'Ameryka Północna',
      'South America': 'Ameryka Południowa', Asia: 'Azja', Europe: 'Europa',
      Oceania: 'Oceania', Easy: 'Łatwy', Medium: 'Średni', Challenging: 'Trudny',
    };
    return labels[value] || value;
  };

  return (
    <article data-publisher-ready="true" className="mx-auto min-w-0 max-w-4xl space-y-6 py-4 [overflow-wrap:anywhere] md:space-y-10 md:py-10">
      {/* Navigation & Header */}
      <nav aria-label={isPl ? 'Nawigacja podsumowania' : 'Recap navigation'} className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-white/10 pb-3 text-sm sm:gap-3">
        <Link to="/blog" className="inline-flex min-h-11 max-w-full items-center gap-1.5 text-zinc-400 hover:text-sand-100 transition-colors">
          <ArrowLeft size={14} />
          <span>{isPl ? 'Wszystkie podsumowania' : 'All Solutions'}</span>
        </Link>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <span className="min-w-0 break-words text-zinc-500 font-mono">
            {post.date}
          </span>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded border border-white/15 px-3 py-1 text-zinc-300 hover:border-emerald-400/40 hover:text-emerald-300 transition-colors"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Share2 size={12} />}
            <span>{copied ? (isPl ? 'Skopiowano' : 'Copied') : (isPl ? 'Udostępnij' : 'Share')}</span>
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
                {isPl ? 'Rozwiązanie z poprzedniego dnia' : 'Past-day solution'} · {post.date}
              </span>
              <span className="text-zinc-600">&bull;</span>
              {post.continent && (
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300 border border-emerald-500/20">
                  {localizedMeta(post.continent)}
                </span>
              )}
              {post.difficulty && (
                <span className={`px-2 py-0.5 rounded font-mono text-[10px] ${
                  post.difficulty === 'Easy' ? 'bg-emerald-500/10 text-emerald-400' :
                  post.difficulty === 'Challenging' ? 'bg-rose-500/10 text-rose-400' :
                  'bg-amber-500/10 text-amber-400'
                }`}>
                  {localizedMeta(post.difficulty)}
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

          </div>
        </div>
      </header>
      <section aria-label="Editorial provenance" className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60 p-4 space-y-3 text-sm text-zinc-300 sm:p-5">
        <p className="font-semibold text-sand-100">{post.ai_assisted ? 'AI-assisted recap' : 'Countrydle recap'} · {reviewed ? 'Editorially reviewed' : 'Not yet editorially reviewed'}</p>
        {reviewed ? <p>Reviewed by {post.reviewer_name} on <time dateTime={post.reviewed_at || undefined}>{post.reviewed_at}</time>.</p> : <p>Geographical claims and deduction advice may need verification. This page does not carry advertising until an editor reviews it.</p>}
        <p>Published <time dateTime={post.created_at}>{post.created_at}</time> · Updated <time dateTime={post.updated_at || post.created_at}>{post.updated_at || post.created_at}</time></p>
        <p>These timestamps record article changes, not the measurement year of population or other changing statistics. Check the cited source for its reference date; a figure without one is undated.</p>
        {post.editorial_note && <p className="whitespace-pre-wrap">{post.editorial_note}</p>}
        {sourceLinks.length ? (
          <div><h2 className="font-semibold text-sand-100">Sources</h2><ul className="mt-2 space-y-1">
            {sourceLinks.map((source, index) => <li key={index}>{source.safeUrl ? <a href={source.safeUrl} target="_blank" rel="noopener noreferrer" className="break-words text-emerald-300 underline">{source.label}</a> : <span>{source.label} — source URL unavailable</span>}</li>)}
          </ul></div>
        ) : <p className="text-amber-300">No source links have been recorded for this recap. Treat factual claims as unverified.</p>}
      </section>
      {post.summary && <p className="text-base leading-7 text-zinc-300">{post.summary}</p>}


      {/* Quick Facts Grid */}
      {facts && Object.keys(facts).length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-sand-100">
            {isPl ? 'Kraj w skrócie' : 'Country at a glance'}
          </h2>
          <div className="grid min-w-0 grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {facts.capital && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{isPl ? 'Stolica' : 'Capital'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.capital}</span>
              </div>
            )}
            {facts.population && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{isPl ? 'Ludność' : 'Population'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.population}</span>
              </div>
            )}
            {facts.area && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{isPl ? 'Powierzchnia' : 'Land area'}</span>
                <span className="text-sand-100 font-bold text-sm block mt-0.5 break-words">{facts.area}</span>
              </div>
            )}
            {facts.coastline && (
              <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/60 p-3 flex flex-col justify-center">
                <span className="text-zinc-400 block text-xs">{isPl ? 'Dostęp do morza' : 'Maritime access'}</span>
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
            <div className="min-w-0 rounded border border-white/10 bg-obsidian-900/40 p-4 text-sm">
              <span className="text-zinc-400 block text-xs mb-1.5">{isPl ? 'Sąsiednie kraje' : 'Bordering neighbors'}</span>
              <span className="break-words text-zinc-300 leading-6">{cleanBorderList(facts.borders)}</span>
            </div>
          )}
        </section>
      )}

      {/* Country Curiosities */}
      {curiosities && curiosities.length > 0 && (
        <section className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-amber-300">
            <Sparkles size={18} className="shrink-0" />
            <span>{isPl ? 'Ciekawostki o kraju' : 'Country curiosities'}</span>
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
      {/* Community Question Telemetry / Deduction Ladder */}
      <details className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900/60">
        <summary className="min-h-11 cursor-pointer px-4 py-4 text-base font-semibold text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 sm:px-6">
          {isPl ? 'Jak grali inni? Statystyki i dedukcja' : 'How did others play? Stats and deduction'}
        </summary>
        <div className="min-w-0 space-y-5 border-t border-white/10 p-4 sm:p-6">
          <div className="flex min-w-0 flex-wrap gap-x-5 gap-y-3 rounded-md border border-white/10 bg-obsidian-950 p-4 text-sm leading-6 text-zinc-400">
            {post.game_debrief?.has_telemetry ? (
              <>
                <span className="min-w-0 break-words text-sand-100">
                  <strong>{post.game_debrief.win_rate_pct}%</strong> {isPl ? 'rozwiązało' : 'solved'} ({post.game_debrief.total_solvers} {isPl ? 'z' : 'of'} {post.game_debrief.total_challengers})
                </span>
                <span className="min-w-0 break-words">
                  {isPl ? 'Średnia liczba pytań do wygranej: ' : 'Average questions to win: '}
                  <strong className="text-sand-100">{post.game_debrief.avg_questions_to_win}</strong>
                </span>
                {post.game_debrief.high_score && (
                  <span className="min-w-0 break-words">
                    {isPl ? 'Najlepszy wynik: ' : 'High score: '}
                    <strong className="text-emerald-300">{post.game_debrief.high_score} {isPl ? 'pkt' : 'pts'}</strong>
                  </span>
                )}
              </>
            ) : post.player_stats && post.player_stats.total_players > 0 ? (
              <>
                <span className="min-w-0 break-words text-sand-100">
                  <strong>{post.player_stats.win_rate_pct}%</strong> {isPl ? 'rozwiązało' : 'solved'}
                </span>
                <span className="min-w-0 break-words">
                  {isPl ? 'Średnia liczba pytań: ' : 'Average questions: '}
                  <strong className="text-sand-100">{post.player_stats.avg_questions_won}</strong>
                </span>
                <span className="min-w-0 break-words">
                  <strong className="text-sand-100">{post.player_stats.total_players}</strong> {isPl ? 'graczy' : 'challengers'}
                </span>
              </>
            ) : (
              <span className="min-w-0 break-words">{isPl ? 'Podsumowanie dziennej zagadki' : 'Daily puzzle recap'} #{post.id}</span>
            )}
          </div>
          {/* Analysis is not replaced by aggregate question telemetry. */}
          {steps.length > 0 && (
            <section className="min-w-0 space-y-4">
              <h2 className="text-lg font-semibold leading-snug text-sand-100">
                {isPl ? `Ścieżka dedukcji: ${post.country_name}` : `Deduction path for ${post.country_name}`}
              </h2>
              <p className="text-sm text-zinc-400">
                {isPl ? 'Proponowana sekwencja rozumowania, nie zmierzona strategia optymalna.' : 'A suggested reasoning sequence, not a measured optimal strategy.'}
              </p>
              <ol className="space-y-3">
                {steps.map((step, index) => {
                  const evidence = post.game_debrief?.has_telemetry ? post.game_debrief.top_questions.filter((question) => question.question.trim().toLowerCase() === step.question.trim().toLowerCase()) : [];
                  return (
                    <li key={index} className="flex min-w-0 items-start gap-2 rounded-md border border-white/5 bg-white/[0.02] p-3 sm:gap-4 sm:p-4">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 font-mono text-xs font-bold text-sand-100">{index + 1}</span>
                      <div className="min-w-0 flex-1 space-y-2">
                        <h3 className="break-words text-sm font-semibold leading-6 text-sand-100">
                          {step.question} <span className="text-emerald-300">— {step.answer || (isPl ? 'Brak zapisanej odpowiedzi' : 'Answer not recorded')}</span>
                        </h3>
                        {step.explanation && <p className="break-words text-sm leading-6 text-zinc-400">{cleanDisplayText(step.explanation)}</p>}
                        {evidence.map((record, evidenceIndex) => (
                          <div key={evidenceIndex} className="space-y-1 text-xs text-zinc-400">
                            <p>{isPl ? 'Dane społeczności' : 'Community evidence'}: {record.answer || (isPl ? 'Brak zapisanej odpowiedzi' : 'Answer not recorded')} — {isPl ? 'zadano' : 'asked'} {record.count}×{record.pct != null ? ` (${record.pct}%)` : ''}.</p>
                            {record.explanation && record.explanation !== step.explanation && <p className="whitespace-pre-wrap leading-6">{cleanDisplayText(record.explanation)}</p>}
                          </div>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          )}
          {otherCommunityQuestions.length > 0 && (
            <section className="min-w-0 space-y-4">
              <h2 className="text-lg font-semibold text-sand-100">{isPl ? 'Pytania społeczności' : 'Community question evidence'}</h2>
              <p className="text-sm text-zinc-400">
                {isPl ? `Zapisane pytania dla zagadki z ${post.date}. Częstotliwość nie dowodzi optymalności strategii.` : `Recorded questions for the ${post.date} puzzle. Frequency is not proof of an optimal strategy.`}
              </p>
              <ul className="space-y-3 text-sm text-zinc-300">
                {otherCommunityQuestions.map((question, index) => (
                  <li key={index} className="min-w-0 rounded-md border border-white/5 bg-white/[0.02] p-3 space-y-2 sm:p-4">
                    <p className="break-words font-semibold leading-6 text-sand-100">{question.question} — <span className="text-emerald-300">{question.answer || (isPl ? 'Brak zapisanej odpowiedzi' : 'Answer not recorded')}</span></p>
                    <p className="text-xs text-zinc-400">{isPl ? 'Zadano' : 'Asked'} {question.count}×{question.pct != null ? ` (${question.pct}%)` : ''}.</p>
                    {question.explanation && <p className="break-words leading-6 text-zinc-400">{cleanDisplayText(question.explanation)}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}

      {/* Common Traps & Wrong Guesses */}
      {post.game_debrief?.has_telemetry && post.game_debrief.common_pitfalls.length > 0 && (
        <section className="min-w-0 rounded-lg border border-rose-500/20 bg-rose-500/5 p-4 space-y-3">
          <h2 className="text-base font-semibold text-rose-400">
            {isPl ? 'Pułapki i błędne odpowiedzi' : 'Common traps and wrong guesses'}
          </h2>
          <p className="text-sm leading-6 text-zinc-300">
            {isPl ? `Zapisane błędne odpowiedzi dla zagadki z ${post.date}, zanim gracze znaleźli kraj ${post.country_name}:` : `Recorded incorrect guesses for the ${post.date} puzzle before players found ${post.country_name}:`}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {post.game_debrief.common_pitfalls.map((pf, idx) => (
              <span key={idx} className="min-w-0 max-w-full break-words rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
                ❌ {pf.guess} <span className="text-rose-400/70 text-xs">({pf.count} {isPl ? 'odpowiedzi' : 'guesses'})</span>
              </span>
            ))}
          </div>
        </section>
      )}
        </div>
      </details>


      {/* Curator Pro Tip */}
      {proTip && (
        <section className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-5 space-y-2">
          <div className="flex items-center gap-2 text-base font-semibold text-emerald-300">
            <Compass size={18} className="shrink-0" />
            <span>{isPl ? 'Wskazówka do dedukcji' : 'Deduction pro tip'}</span>
          </div>
          <p className="break-words text-sm leading-7 text-zinc-200">
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
        if (!questionText || !correctAnswer || !incorrectDistractor || !explanationText || correctAnswer.toLowerCase() === incorrectDistractor.toLowerCase()) return null;

        const triviaSeed = (post?.id || 0) + (post?.country_name ? post.country_name.length : 0);
        const correctOptionIndex = triviaSeed % 2;
        const triviaOptions = correctOptionIndex === 0
          ? [correctAnswer, incorrectDistractor]
          : [incorrectDistractor, correctAnswer];

        return (
          <section className="min-w-0 rounded-lg border border-white/10 bg-obsidian-900 p-4 space-y-4 sm:p-6">
            <div className="flex items-center gap-2 text-base font-semibold text-emerald-300">
              <Award size={18} className="shrink-0" />
              <span>{isPl ? 'Szybki test wiedzy' : 'Quick memory check'}</span>
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
          <h2 className="flex items-center gap-2 text-lg font-semibold text-sand-100">
            <Globe size={18} className="shrink-0" />
            <span>{isPl ? 'Inne ostatnie rozwiązania' : 'More recent country solutions'}</span>
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
          {isPl ? 'Gotowi na dzisiejsze wyzwanie?' : "Ready for today's daily challenge?"}
        </h3>
        <p className="text-sm leading-6 text-zinc-400 max-w-md mx-auto">
          {isPl ? 'Nowy tajemniczy kraj już czeka. Sprawdź swoją dedukcję przed północą UTC!' : 'A new mystery country is ready. Test your deduction skills before midnight UTC!'}
        </p>
        <div className="pt-2">
          <Link
            to="/game"
            className="inline-flex min-h-11 max-w-full items-center gap-2 rounded bg-emerald-400 px-4 py-3 text-sm font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors shadow"
          >
            <Play size={14} />
            <span>{isPl ? 'Zagraj w dzisiejsze Countrydle' : "Play today's Countrydle"}</span>
          </Link>
        </div>
      </div>
    </article>
  );
}
