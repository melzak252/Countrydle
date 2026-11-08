import { expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import { blogPostSchema } from '../src/blogContent';

function renderArticle(postData: unknown): string {
  const dom = new TestWindow({ url: 'https://countrydle.test/blog/test' });
  const globals: Record<string, unknown> = {
    window: dom,
    document: dom.document,
    navigator: dom.navigator,
    HTMLElement: dom.HTMLElement,
    Element: dom.Element,
    Node: dom.Node,
  };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  try {
    const { BlogArticle } = require('../src/pages/BlogPostPage');
    const parsed = blogPostSchema.parse(postData);
    return renderToStaticMarkup(
      <MemoryRouter>
        <BlogArticle post={parsed} preview />
      </MemoryRouter>
    );
  } finally {
    try {
      dom.happyDOM.close();
    } finally {
      for (const [name, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else Reflect.deleteProperty(globalThis, name);
      }
    }
  }
}

test('hero uses markdown body as canonical narrative without duplicating summary', () => {
  const introProse = 'Namibia is situated in southwestern Africa, featuring the arid Namib Desert along the Atlantic coast.';
  const htmlWithBody = renderArticle({
    id: 101,
    date: '2026-10-01',
    slug: '2026-10-01-namibia',
    title: 'Countrydle Solution: Namibia',
    subtitle: 'A vast desert coastline in southern Africa.',
    summary: introProse,
    country_name: 'Namibia',
    reading_time_minutes: 2,
    created_at: null,
    updated_at: '2026-10-02',
    editorial_status: 'reviewed',
    reviewed_at: '2026-10-02T10:00:00Z',
    reviewer_name: 'Lead Editor',
    ai_assisted: false,
    content_markdown: introProse,
    fast_facts: { capital: 'Windhoek' },
    fun_facts: [{ title: 'Fact', description: 'Description.' }],
    deduction_masterclass: null,
    source_links: [{ label: 'Source', url: 'https://example.com' }],
    editorial_note: null,
  });

  // When markdown body is present, body is canonical: no separate hero lead, intro appears exactly ONCE
  expect(htmlWithBody).not.toContain('A vast desert coastline in southern Africa.');
  const occurrences = htmlWithBody.split(introProse).length - 1;
  expect(occurrences).toBe(1);

  // When body is empty, summary serves as fallback hero lead
  const htmlNoBody = renderArticle({
    id: 102,
    date: '2026-10-01',
    slug: '2026-10-01-namibia',
    title: 'Countrydle Solution: Namibia',
    subtitle: '',
    summary: introProse,
    country_name: 'Namibia',
    reading_time_minutes: 2,
    created_at: null,
    updated_at: '2026-10-02',
    editorial_status: 'reviewed',
    reviewed_at: '2026-10-02T10:00:00Z',
    reviewer_name: 'Lead Editor',
    ai_assisted: false,
    content_markdown: '',
    fast_facts: { capital: 'Windhoek' },
    fun_facts: [],
    deduction_masterclass: null,
    source_links: [{ label: 'Source', url: 'https://example.com' }],
    editorial_note: null,
  });
  expect(htmlNoBody).toContain(introProse);
});

test('deduction analysis renders candidate funnel and comparison table when analysis is present', () => {
  const htmlWithAnalysis = renderArticle({
    id: 104,
    date: '2026-10-01',
    slug: '2026-10-01-zambia',
    title: 'Countrydle Solution: Zambia',
    subtitle: '',
    summary: 'Summary.',
    country_name: 'Zambia',
    reading_time_minutes: 2,
    created_at: null,
    updated_at: '2026-10-02',
    editorial_status: 'reviewed',
    reviewed_at: '2026-10-02T10:00:00Z',
    reviewer_name: 'Lead Editor',
    ai_assisted: false,
    content_markdown: 'Content.',
    fast_facts: { capital: 'Lusaka' },
    fun_facts: [],
    deduction_masterclass: null,
    source_links: [{ label: 'Source', url: 'https://example.com' }],
    editorial_note: null,
    deduction_analysis: {
      has_analysis: true,
      catalog_provenance: 'Current stored Countrydle country catalog facts (country_facts.sqlite)',
      disclaimer: 'Illustrative deduction model based on present catalog facts; this is not a recorded single-player walkthrough.',
      candidate_funnel: [
        { criterion: 'Continent: Africa', explanation: 'Nations situated in Africa.', remaining_count: 54, sample_candidates: ['Angola'] },
      ],
      wrong_guess_comparisons: [
        {
          guess: 'Zimbabwe',
          count: 15,
          shared_traits: ['Both situated in Africa'],
          differences: [],
          guess_facts: { capital: 'Harare', coastline: 'Landlocked' },
          target_facts: { capital: 'Lusaka', coastline: 'Landlocked' },
        },
      ],
    },
  });

  expect(htmlWithAnalysis).toContain('<table');
  expect(htmlWithAnalysis).toContain('Zimbabwe');

  const htmlWithoutAnalysis = renderArticle({
    id: 105,
    date: '2026-10-01',
    slug: '2026-10-01-zambia',
    title: 'Countrydle Solution: Zambia',
    subtitle: '',
    summary: 'Summary.',
    country_name: 'Zambia',
    reading_time_minutes: 2,
    created_at: null,
    updated_at: '2026-10-02',
    editorial_status: 'reviewed',
    reviewed_at: '2026-10-02T10:00:00Z',
    reviewer_name: 'Lead Editor',
    ai_assisted: false,
    content_markdown: 'Content.',
    fast_facts: { capital: 'Lusaka' },
    fun_facts: [],
    deduction_masterclass: null,
    source_links: [{ label: 'Source', url: 'https://example.com' }],
    editorial_note: null,
    deduction_analysis: {
      has_analysis: false,
      catalog_provenance: '',
      disclaimer: '',
      candidate_funnel: [],
      wrong_guess_comparisons: [],
    },
  });

  expect(htmlWithoutAnalysis).not.toContain('<table');
});
