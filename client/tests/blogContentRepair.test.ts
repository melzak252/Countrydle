import { expect, test } from 'bun:test';
import { blogDeductionSchema, blogListSchema, blogPostSchema, cleanDisplayText } from '../src/blogContent';

function storedArticle(quiz: unknown) {
  return {
    id: 42, date: '2026-09-19', slug: '2026-09-19-poland', title: 'Poland recap',
    subtitle: 'A past-day geography recap.', summary: 'Poland is in Europe.',
    country_name: 'Poland', country_code: 'pl', reading_time_minutes: 2,
    created_at: null, updated_at: '2026-09-20T12:34:56.123456Z', editorial_status: 'unreviewed',
    fast_facts: { capital: 'Warsaw', population: null },
    fun_facts: [{ title: 'Border', description: 'Poland borders Germany.' }],
    deduction_masterclass: {
      steps: [{ question: 'Is it in Europe?', answer: 'YES', explanation: 'The stored answer is YES.' }],
      pro_tip: 'Check shared borders.', quiz,
    },
    content_markdown: '## Historical claim\nAn unresolved claim remains [citation needed].\n\n## Additional article detail\nA substantive paragraph not repeated in the structured recap.',
    source_links: [{ label: 'Stored question evidence', url: 'https://en.wikipedia.org/wiki/Poland' }],
    editorial_note: 'Source excerpts retain unresolved [citation needed] warnings.',
    reviewed_at: null, reviewer_name: null, ai_assisted: false,
    game_debrief: {
      has_telemetry: true, total_challengers: 20, total_solvers: 15, win_rate_pct: 75,
      avg_questions_to_win: 4, top_questions: [{ question: 'Is it in Europe?', answer: 'YES', count: 8, pct: 40, explanation: 'The stored answer is YES.' }],
      top_winner_questions: [{ question: 'Is it in Europe?', answer: 'YES', count: 6 }],
      common_pitfalls: [{ guess: 'Germany', count: 2 }],
    },
  };
}

const completeQuiz = {
  question: 'What is the capital of Poland?', correct_answer: 'Warsaw',
  incorrect_distractor: 'Berlin', explanation: 'Warsaw is the capital of Poland.',
};

test('question-only historical quiz keeps useful article content and unchanged repair data', () => {
  const originalQuiz = { question: 'A historical claim [citation needed]?', legacy_note: 'Original warning [citation needed]' };
  const stored = storedArticle(originalQuiz);
  const before = JSON.stringify(stored);
  const post = blogPostSchema.parse(stored);
  const quiz = post.deduction_masterclass?.quiz;

  expect(quiz?.status).toBe('needs-editorial-repair');
  if (quiz?.status !== 'needs-editorial-repair') throw new Error('Historical quiz must be explicitly unavailable.');
  expect(quiz.stored).toEqual(originalQuiz);
  expect(quiz).not.toHaveProperty('content');
  expect(JSON.stringify(stored)).toBe(before);
  expect(post.summary).toBe('Poland is in Europe.');
  expect(post.fast_facts?.capital).toBe('Warsaw');
  expect(post.fun_facts[0].description).toBe('Poland borders Germany.');
  expect(post.source_links).toEqual(stored.source_links);
  expect(post.editorial_note).toContain('[citation needed]');
  expect(post.game_debrief?.top_questions[0]).toEqual(stored.game_debrief.top_questions[0]);
  // Admin/editor validation remains strict rather than saving the public repair view.
  expect(blogDeductionSchema.safeParse(stored.deduction_masterclass).success).toBe(false);
});

test('complete meaningful quiz remains interactive instead of being silently discarded', () => {
  const post = blogPostSchema.parse(storedArticle(completeQuiz));
  const quiz = post.deduction_masterclass?.quiz;
  expect(quiz?.status).toBe('available');
  if (quiz?.status !== 'available') throw new Error('Complete quiz must be available.');
  expect(quiz.content).toEqual(completeQuiz);
  expect(blogDeductionSchema.safeParse({ quiz: completeQuiz }).success).toBe(true);
});

for (const invalidQuiz of [
  { ...completeQuiz, question: ' ' },
  { ...completeQuiz, explanation: '' },
  { ...completeQuiz, incorrect_distractor: ' warsaw ' },
  null,
]) {
  test(`invalid quiz ${JSON.stringify(invalidQuiz)} is explicitly unavailable and cannot be saved`, () => {
    const post = blogPostSchema.parse(storedArticle(invalidQuiz));
    const quiz = post.deduction_masterclass?.quiz;
    expect(quiz?.status).toBe('needs-editorial-repair');
    if (quiz?.status !== 'needs-editorial-repair') throw new Error('Invalid quiz must need repair.');
    expect(quiz.stored).toEqual(invalidQuiz);
    expect(blogDeductionSchema.safeParse({ quiz: invalidQuiz }).success).toBe(false);
  });
}

for (const [answer, distractor] of [
  ['Warsaw\\(Poland\\)', 'Warsaw(Poland)'],
  ['\uFEFFWarsaw\\(Poland\\)\uFEFF', 'Warsaw(Poland)'],
  ['Warsaw\\_capital\\_', 'WARSAW_capital_'],
  ['Warsaw\\[1\\]', 'Warsaw[1]'],
  ['Warsaw\\*', 'Warsaw*'],
]) {
  test(`equal displayed choices ${JSON.stringify([answer, distractor])} require repair without changing raw JSON`, () => {
    const originalQuiz = {
      ...completeQuiz, correct_answer: answer, incorrect_distractor: distractor,
      explanation: 'A stored warning \\[citation needed\\] and reference \\[1\\].',
    };
    const stored = storedArticle(originalQuiz);
    const before = JSON.stringify(stored);
    expect(cleanDisplayText(answer).toLowerCase()).toBe(cleanDisplayText(distractor).toLowerCase());
    expect(blogDeductionSchema.safeParse({ quiz: originalQuiz }).success).toBe(false);
    const quiz = blogPostSchema.parse(stored).deduction_masterclass?.quiz;
    expect(quiz?.status).toBe('needs-editorial-repair');
    if (quiz?.status !== 'needs-editorial-repair') throw new Error('Ambiguous displayed quiz must need repair.');
    expect(quiz.stored).toEqual(originalQuiz);
    expect(quiz).not.toHaveProperty('content');
    expect(JSON.stringify(stored)).toBe(before);
  });
}

for (const [answer, distractor] of [
  ['Warsaw\\(Poland\\)', 'Berlin(Germany)'],
  ['Warsaw\\[citation needed\\]', 'Warsaw'],
  ['Warsaw\\[1\\]', 'Warsaw[2]'],
  ['Warsaw\\!', 'Warsaw!'],
]) {
  test(`distinct displayed choices ${JSON.stringify([answer, distractor])} remain usable and retain citation markers`, () => {
    const originalQuiz = {
      ...completeQuiz, correct_answer: answer, incorrect_distractor: distractor,
      explanation: 'Check \\[citation needed\\] and \\[1\\] before editorial review.',
    };
    expect(cleanDisplayText(answer)).not.toBe(cleanDisplayText(distractor));
    expect(blogDeductionSchema.safeParse({ quiz: originalQuiz }).success).toBe(true);
    const quiz = blogPostSchema.parse(storedArticle(originalQuiz)).deduction_masterclass?.quiz;
    expect(quiz?.status).toBe('available');
    if (quiz?.status !== 'available') throw new Error('Distinct displayed quiz must remain available.');
    expect(quiz.content).toEqual(originalQuiz);
    expect(cleanDisplayText(quiz.content.explanation)).toBe('Check [citation needed] and [1] before editorial review.');
  });
}

test('unknown historical publication time stays null for article, list and related metadata', () => {
  const stored = storedArticle(completeQuiz);
  const post = blogPostSchema.parse({ ...stored, related_posts: [stored] });
  const list = blogListSchema.parse({ total: 1, posts: [stored] });
  expect(post.created_at).toBeNull();
  expect(post.related_posts?.[0].created_at).toBeNull();
  expect(list.posts[0].created_at).toBeNull();
  expect(post.updated_at).toBe('2026-09-20T12:34:56.123456Z');
  expect(blogPostSchema.safeParse({ ...stored, updated_at: undefined }).success).toBe(false);
});


test('an omitted quiz is legitimate and does not claim editorial repair is needed', () => {
  const stored = storedArticle(completeQuiz);
  const deduction = { steps: stored.deduction_masterclass.steps, pro_tip: stored.deduction_masterclass.pro_tip };
  const post = blogPostSchema.parse({ ...stored, deduction_masterclass: deduction });
  expect(post.deduction_masterclass?.quiz).toBeUndefined();
  expect(blogDeductionSchema.safeParse(deduction).success).toBe(true);
});



for (const field of ['question', 'correct_answer', 'incorrect_distractor', 'explanation'] as const) {
  test(`display-blank ${field} cannot be saved and historical raw content remains repairable`, () => {
    const quiz = { ...completeQuiz, [field]: '\uFEFF' };
    expect(blogDeductionSchema.safeParse({ quiz }).success).toBe(false);
    const historical = blogPostSchema.parse(storedArticle(quiz)).deduction_masterclass?.quiz;
    expect(historical?.status).toBe('needs-editorial-repair');
    if (historical?.status !== 'needs-editorial-repair') throw new Error('Blank display text requires repair.');
    expect(historical.stored).toEqual(quiz);
  });
}
