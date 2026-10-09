import { z } from 'zod';

export function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export const blogSourceSchema = z.object({
  label: z.string().trim().min(1).max(200),
  url: z.string().trim().max(2048).refine((value) => safeSourceUrl(value) !== null, 'Use an HTTP(S) URL without credentials.'),
});
export const blogFactsSchema = z.record(z.string(), z.union([z.string(), z.number().finite(), z.boolean(), z.null()])).nullable();
export const blogFunFactsSchema = z.array(z.object({ title: z.string(), description: z.string() }).passthrough()).max(50);
const blogQuizSchema = z.object({
  question: z.string().trim().min(1),
  correct_answer: z.string().trim().min(1),
  incorrect_distractor: z.string().trim().min(1),
  explanation: z.string().trim().min(1),
}).passthrough().refine(
  (quiz) => cleanDisplayText(quiz.correct_answer).toLowerCase() !== cleanDisplayText(quiz.incorrect_distractor).toLowerCase(),
  'The correct answer and distractor must display different choices.',
);
export const blogDeductionSchema = z.object({
  steps: z.array(z.object({
    question: z.string(), answer: z.string().optional(), explanation: z.string().optional(),
  }).passthrough()).optional(),
  pro_tip: z.string().optional(),
  quiz: blogQuizSchema.optional(),
}).passthrough().nullable();
// The public reader keeps a historical broken quiz honest and repairable without
// rejecting the rest of the article. Editors still validate the strict schema.
const publicQuizSchema = z.unknown().transform((stored) => {
  const parsed = blogQuizSchema.safeParse(stored);
  return parsed.success
    ? { status: 'available' as const, content: parsed.data }
    : { status: 'needs-editorial-repair' as const, stored };
});
const publicDeductionSchema = blogDeductionSchema.unwrap().extend({
  quiz: publicQuizSchema.optional(),
}).nullable();
export const blogSummarySchema = z.object({
  id: z.number().int().positive(), date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  slug: z.string().min(1), title: z.string().min(1), subtitle: z.string(), summary: z.string(),
  country_name: z.string().min(1), country_code: z.string().nullable().optional(),
  continent: z.string().nullable().optional(), difficulty: z.string().nullable().optional(),
  reading_time_minutes: z.number().int().nonnegative(), total_players: z.number().nullable().optional(),
  created_at: z.string().min(1).nullable(), updated_at: z.string().min(1),
  editorial_status: z.enum(['unreviewed', 'reviewed']),
});
export const blogListSchema = z.object({ total: z.number().int().nonnegative(), posts: z.array(blogSummarySchema) });
export const blogPostSchema = blogSummarySchema.extend({
  fast_facts: blogFactsSchema.transform((facts) => facts === null ? null : Object.fromEntries(
    Object.entries(facts).flatMap(([key, value]) => value === null ? [] : [[key, typeof value === 'boolean' ? String(value) : value]]),
  ) as Record<string, string | number>), fun_facts: blogFunFactsSchema,
  deduction_masterclass: publicDeductionSchema, content_markdown: z.string(),
  source_links: z.array(blogSourceSchema).max(20), editorial_note: z.string().nullable(),
  reviewed_at: z.string().nullable(), reviewer_name: z.string().nullable(), ai_assisted: z.boolean(),
  related_posts: z.array(blogSummarySchema).nullable().optional(),
  player_stats: z.object({ total_players: z.number(), win_rate_pct: z.number(), avg_questions_won: z.number() }).nullable().optional(),
  game_debrief: z.object({
    has_telemetry: z.boolean(), total_challengers: z.number(), total_solvers: z.number(),
    win_rate_pct: z.number(), avg_questions_to_win: z.number(), high_score: z.number().nullable().optional(),
    top_questions: z.array(z.object({ question: z.string(), answer: z.string(), count: z.number(), pct: z.number().nullable().optional(), explanation: z.string().nullable().optional() })),
    common_pitfalls: z.array(z.object({ guess: z.string(), count: z.number() })),
  }).nullable().optional(),
});
export type BlogSummary = z.infer<typeof blogSummarySchema>;
export type BlogPost = z.infer<typeof blogPostSchema>;

export function cleanDisplayText(text?: string): string {
  if (!text) return '';
  // Never remove citation-needed markers or unresolved reference numbers.
  return text.replace(/\\([_()[\]*])/g, '$1').trim();
}

export function additionalArticleSections(post: BlogPost): string[] {
  // Compare whole claims, never remove a section just because its heading overlaps.
  // Citation markers participate in comparison, so a warning cannot disappear.
  const comparableClaim = (value: string) => cleanDisplayText(value).replace(/^\s*(?:\d+[.)]|[-*>])\s*/, '').replace(/[*_"“”]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  const displayed = new Set<string>([
    comparableClaim(post.summary),
    comparableClaim(post.deduction_masterclass?.pro_tip || ''),
    ...post.fun_facts.map((fact) => comparableClaim(`${fact.title}: ${fact.description}`)),
    ...(post.deduction_masterclass?.steps || []).map((step) => comparableClaim(`[${step.answer || ''}] "${step.question}" — ${step.explanation || ''}`)),
  ]);
  const factLabels: Record<string, string> = {
    capital: 'Capital', population: 'Population', area: 'Land Area', coastline: 'Maritime Access',
    borders: 'Bordering Neighbors', languages: 'Official Languages', region: 'Region', continent: 'Continent',
  };
  for (const [key, value] of Object.entries(post.fast_facts || {})) {
    displayed.add(comparableClaim(`${factLabels[key] || key}: ${value}`));
  }
  const facts = post.fast_facts || {};
  if (facts.continent && facts.region) displayed.add(comparableClaim(`Region: ${facts.continent} (${facts.region})`));
  if (facts.area && facts.coastline) displayed.add(comparableClaim(`Land Area: ${facts.area} (${facts.coastline})`));
  return post.content_markdown.split(/(?=^#{1,6}\s)/m).flatMap((section) => {
    const lines = section.trim().split('\n');
    const heading = /^#{1,6}\s/.test(lines[0] || '') ? lines.shift() : undefined;
    const remaining = lines.filter((line) => line.trim() && !displayed.has(comparableClaim(line)));
    if (!remaining.length) return [];
    return [[heading, ...remaining].filter(Boolean).join('\n')];
  });
}
