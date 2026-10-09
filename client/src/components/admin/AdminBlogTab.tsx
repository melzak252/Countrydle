import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import { z } from 'zod';
import { blogService } from '../../services/api';
import { blogListSchema, blogPostSchema, blogFactsSchema, blogFunFactsSchema, blogDeductionSchema, blogSourceSchema, safeSourceUrl, type BlogSummary } from '../../blogContent';

const editableSchema = z.object({
  title: z.string().trim().min(1).max(240), subtitle: z.string().trim().min(1).max(500),
  summary: z.string().trim().min(1).max(10000), content_markdown: z.string().trim().min(1).max(100000),
  fast_facts: blogFactsSchema, fun_facts: blogFunFactsSchema, deduction_masterclass: blogDeductionSchema,
  source_links: z.array(blogSourceSchema).max(20), editorial_note: z.string().max(10000).nullable(),
});
// Load stored JSON without hiding an article that needs repair. Saving/reviewing
// still requires the strict reader-compatible editable schema above.
const adminPostSchema = blogPostSchema.extend({
  fast_facts: z.record(z.string(), z.unknown()).nullable(),
  fun_facts: z.array(z.record(z.string(), z.unknown())),
  deduction_masterclass: z.record(z.string(), z.unknown()).nullable(),
});
type EditablePost = z.infer<typeof adminPostSchema>;
type Draft = { title: string; subtitle: string; summary: string; content_markdown: string; fast_facts: string; fun_facts: string; deduction_masterclass: string; source_links: { label: string; url: string }[]; editorial_note: string };
function postDraft(post: EditablePost): Draft {
  return {
    title: post.title, subtitle: post.subtitle, summary: post.summary, content_markdown: post.content_markdown,
    fast_facts: JSON.stringify(post.fast_facts, null, 2), fun_facts: JSON.stringify(post.fun_facts, null, 2),
    deduction_masterclass: JSON.stringify(post.deduction_masterclass, null, 2),
    source_links: post.source_links.map((source) => ({ ...source })), editorial_note: post.editorial_note || '',
  };
}
function editorialError(error: unknown): string {
  if (error instanceof z.ZodError) return error.issues.map((issue) => `${issue.path.join('.') || 'Post'}: ${issue.message}`).join('; ');
  if (error instanceof SyntaxError) return 'One of the JSON fields is invalid. Correct its syntax before saving.';
  if (isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return 'The server rejected these edits. Check required text, source URLs and field lengths.';
    return 'The request failed. Your unsaved edits have been kept; please try again.';
  }
  return error instanceof Error ? error.message : 'The editorial request failed.';
}

export default function AdminBlogTab() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [posts, setPosts] = useState<BlogSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [post, setPost] = useState<EditablePost | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [detailRetry, setDetailRetry] = useState(0);
  const [staleReview, setStaleReview] = useState(false);
  const limit = 12;
  useEffect(() => {
    let active = true;
    setListLoading(true);
    setListError(null);
    const timer = setTimeout(async () => {
      try {
        const result = blogListSchema.parse(await blogService.listAdminPosts(page, limit, search));
        if (active) { setPosts(result.posts); setTotal(result.total); }
      } catch (failure) {
        if (active) { setPosts([]); setListError(editorialError(failure)); }
      } finally { if (active) setListLoading(false); }
    }, search ? 250 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [page, search, refresh]);
  useEffect(() => {
    let active = true;
    setPost(null); setDraft(null); setError(null); setMessage(null);
    setStaleReview(false);
    if (selectedId === null) return;
    setDetailLoading(true);
    void (async () => {
      try {
        const result = adminPostSchema.parse(await blogService.getAdminPost(selectedId));
        if (active) { setPost(result); setDraft(postDraft(result)); }
      } catch (failure) { if (active) setError(editorialError(failure)); }
      finally { if (active) setDetailLoading(false); }
    })();
    return () => { active = false; };
  }, [selectedId, detailRetry]);

  const dirty = !!post && !!draft && JSON.stringify(draft) !== JSON.stringify(postDraft(post));
  const privateDate = !!post && post.date >= new Date().toISOString().slice(0, 10);
  const reviewed = post?.editorial_status === 'reviewed';
  const mutate = async (action: 'save' | 'review' | 'unreview') => {
    if (!post || !draft || busy) return;
    if (action === 'review' && (staleReview || !post.updated_at)) {
      setError('Reload the latest saved post, inspect its content and sources, then deliberately record a new review.'); return;
    }
    if (action === 'review' && (dirty || privateDate || !post.source_links.length)) {
      setError('Save edits first, and review only a past-day post with actual source links.'); return;
    }
    if (action === 'review' && !window.confirm('Record your signed-in admin identity and the current time as the reviewer of this saved post? Only confirm after you have personally checked the content against its recorded sources.')) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      let response: unknown;
      if (action === 'save' || action === 'review') {
        const payload = editableSchema.parse({ ...draft,
          fast_facts: JSON.parse(draft.fast_facts), fun_facts: JSON.parse(draft.fun_facts),
          deduction_masterclass: JSON.parse(draft.deduction_masterclass), editorial_note: draft.editorial_note.trim() || null,
        });
        response = action === 'save'
          ? await blogService.updatePost(post.id, payload)
          : await blogService.reviewPost(post.id, post.updated_at!);
      } else response = await blogService.unreviewPost(post.id);
      const result = adminPostSchema.parse(response);
      setPost(result);
      if (action !== 'unreview' || !dirty) setDraft(postDraft(result));
      setRefresh((value) => value + 1);
      setMessage(action === 'save' ? 'Saved. Any prior editorial review has been invalidated.' : action === 'review' ? 'Review recorded by the server for your signed-in admin account.' : 'Editorial review revoked. This post is no longer advertising-eligible.');
    } catch (failure) {
      if (action === 'review' && isAxiosError(failure) && failure.response?.status === 409) {
        setStaleReview(true);
        setError('This post changed after you loaded it. No review was recorded. Reload the latest saved version and check its content and sources before reviewing again.');
      } else setError(editorialError(failure));
    }
    finally { setBusy(false); }
  };
  const reloadLatest = () => {
    if (busy || (dirty && !window.confirm('Discard unsaved edits and load the latest saved version?'))) return;
    setDetailRetry((value) => value + 1);
  };

  return <section className="space-y-6 text-zinc-300">
    <header><h2 className="font-serif text-2xl text-sand-100">Blog editorial management</h2><p className="mt-2 text-sm">Generated recaps are not automatically approved. Saving any edit clears review attribution. Review requires a sourced, substantive past-day post and a deliberate action by the signed-in administrator.</p></header>
    <label className="block text-sm">Search posts<input type="search" value={search} disabled={busy} onChange={(event) => { setSearch(event.target.value); setPage(1); }} className="mt-2 block w-full rounded border border-white/20 bg-obsidian-950 p-3" /></label>
    {listLoading ? <p role="status">Loading posts…</p> : listError ? <div role="alert"><p>{listError}</p><button type="button" onClick={() => setRefresh((value) => value + 1)} className="mt-2 underline">Retry list</button></div> : <>
      <ul className="grid gap-3 sm:grid-cols-2">{posts.map((item) => <li key={item.id}><button type="button" disabled={busy} onClick={() => {
        if (item.id !== selectedId && dirty && !window.confirm('Discard the unsaved edits before selecting another post?')) return;
        if (item.id !== selectedId) { setPost(null); setDraft(null); setSelectedId(item.id); }
      }} className={`w-full rounded border p-4 text-left ${selectedId === item.id ? 'border-emerald-400' : 'border-white/20'}`}><span className="block font-semibold text-sand-100">{item.title}</span><span className="block text-xs">{item.date} · {item.country_name} · {item.editorial_status === 'reviewed' ? 'Reviewed' : 'Unreviewed'}{item.date >= new Date().toISOString().slice(0, 10) ? ' · Private date' : ''}</span></button></li>)}</ul>
      {!posts.length && <p>No posts match this page and search.</p>}
      <nav aria-label="Admin blog pagination" className="flex items-center gap-4"><button type="button" disabled={page <= 1 || busy} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(total / limit))} · {total} posts</span><button type="button" disabled={page * limit >= total || busy} onClick={() => setPage((value) => value + 1)}>Next</button></nav>
    </>}
    {detailLoading && <p role="status">Loading editable post…</p>}
    {error && <div role="alert" className="rounded border border-rose-500/40 p-4"><p>{error}</p>{!post && selectedId !== null && <button type="button" onClick={() => setDetailRetry((value) => value + 1)} className="mt-2 underline">Retry selected post</button>}</div>}
    {post && staleReview && <p className="rounded border border-amber-500/40 p-4 text-amber-300">Review is blocked until you reload and inspect the latest saved version. <button type="button" disabled={busy} onClick={reloadLatest} className="underline">Reload latest saved post</button></p>}
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    {post && draft && <form onSubmit={(event) => { event.preventDefault(); void mutate('save'); }} className="space-y-5 rounded border border-white/20 p-5">
      <header><h3 className="font-serif text-xl text-sand-100">Editing {post.country_name} · {post.date}</h3><p className="text-sm">{post.ai_assisted ? 'AI-assisted' : 'Countrydle recap'} · {reviewed ? `Reviewed by ${post.reviewer_name} at ${post.reviewed_at}` : 'Unreviewed'} · Updated {post.updated_at || post.created_at}</p>{privateDate && <p className="mt-2 text-amber-300">Today/future post: private admin preview only. It cannot be reviewed for public publication.</p>}</header>
      <fieldset disabled={busy} className="space-y-5">
        {(['title', 'subtitle', 'summary', 'content_markdown', 'editorial_note', 'fast_facts', 'fun_facts', 'deduction_masterclass'] as const).map((field) => <label key={field} className="block text-sm"><span className="mb-2 block">{field.replaceAll('_', ' ')}{['fast_facts', 'fun_facts', 'deduction_masterclass'].includes(field) ? ' (JSON; use null for absent facts/deduction)' : ''}</span><textarea value={draft[field]} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })} rows={field === 'content_markdown' ? 12 : ['title', 'subtitle'].includes(field) ? 2 : 5} required={['title', 'subtitle', 'summary', 'content_markdown'].includes(field)} className="block w-full rounded border border-white/20 bg-obsidian-950 p-3 font-mono text-sm" /></label>)}
        <p className="text-xs text-zinc-400">Fast facts accept text, numbers, booleans and null for unknown values; unknown facts are omitted from the public display. Curiosities require title and description strings. Deduction steps require a question, with optional answer and explanation strings; a quiz requires question, correct_answer, incorrect_distractor and explanation strings. Stored JSON that needs repair remains editable, but must be corrected before saving or reviewing.</p>
        <section className="space-y-3"><h4 className="font-semibold text-sand-100">Source links actually consulted</h4><p className="text-xs">Add real sources you checked. A URL alone does not verify a claim. HTTP(S) URLs only; sources are not fetched by this form.</p>
          {draft.source_links.map((source, index) => <div key={index} className="space-y-2 rounded border border-white/10 p-3">
            <label className="block text-sm">Source label<input value={source.label} maxLength={200} required onChange={(event) => setDraft({ ...draft, source_links: draft.source_links.map((entry, position) => position === index ? { ...entry, label: event.target.value } : entry) })} className="mt-1 block w-full rounded bg-obsidian-950 p-2" /></label>
            <label className="block text-sm">Source URL<input type="url" value={source.url} maxLength={2048} required onChange={(event) => setDraft({ ...draft, source_links: draft.source_links.map((entry, position) => position === index ? { ...entry, url: event.target.value } : entry) })} className="mt-1 block w-full rounded bg-obsidian-950 p-2" /></label>
            {safeSourceUrl(source.url) && <a href={safeSourceUrl(source.url) || undefined} target="_blank" rel="noopener noreferrer" className="text-sm text-emerald-300 underline">Open recorded source</a>}
            <button type="button" onClick={() => setDraft({ ...draft, source_links: draft.source_links.filter((_, position) => position !== index) })} className="ml-4 text-sm text-rose-300">Remove source</button>
          </div>)}
          <button type="button" disabled={draft.source_links.length >= 20} onClick={() => setDraft({ ...draft, source_links: [...draft.source_links, { label: '', url: '' }] })} className="rounded border border-white/20 px-3 py-2">Add source</button>
        </section>
        <div className="flex flex-wrap gap-3"><button type="submit" disabled={!dirty} className="rounded bg-emerald-400 px-4 py-2 font-semibold text-obsidian-950">{busy ? 'Saving…' : 'Save edits and invalidate review'}</button><button type="button" disabled={dirty || reviewed || privateDate || !post.source_links.length || staleReview || !post.updated_at} onClick={() => { void mutate('review'); }} className="rounded border border-emerald-400 px-4 py-2">Record editorial review…</button><button type="button" disabled={!reviewed} onClick={() => { void mutate('unreview'); }} className="rounded border border-rose-400 px-4 py-2">Revoke review</button></div>
        {dirty && <p className="text-xs text-amber-300">Unsaved changes. Save before recording a review. Revoking review preserves these unsaved edits.</p>}
      </fieldset>
    </form>}
  </section>;
}
