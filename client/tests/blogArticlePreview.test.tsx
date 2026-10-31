import { expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import { blogPostSchema } from '../src/blogContent';

const post = blogPostSchema.parse({
  id: 7, date: '2020-01-01', slug: 'test', title: 'Saved title', subtitle: 'Subtitle', summary: 'Summary',
  country_name: 'Example', reading_time_minutes: 1, created_at: null, updated_at: '2020-01-02',
  editorial_status: 'unreviewed', reviewed_at: null, reviewer_name: null, ai_assisted: true,
  content_markdown: 'A saved **markdown** fact. [Unsafe](javascript:alert) [Source](https://example.com/)', fast_facts: { capital: 'Saved capital' },
  fun_facts: [{ title: 'Curiosity', description: 'Saved curiosity' }],
  deduction_masterclass: { quiz: { question: 'Saved question?', correct_answer: 'Correct', incorrect_distractor: 'Wrong', explanation: 'Saved explanation' } },
  source_links: [{ label: 'Recorded source', url: 'https://example.com/' }], editorial_note: null,
});

test('private preview uses the public article presentation without ads or invented review attribution', async () => {
  const dom = new TestWindow({ url: 'https://countrydle.test/blog/test' });
  const globals: Record<string, unknown> = {
    window: dom, document: dom.document, navigator: dom.navigator,
    HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node,
  };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  try {
    // The article's advertising dependency reads document during module initialization.
    const { BlogArticle } = await import('../src/pages/BlogPostPage');
    const html = renderToStaticMarkup(<MemoryRouter><BlogArticle post={post} eligibleForAds preview /></MemoryRouter>);
    for (const text of ['Saved title', 'Saved capital', 'markdown', 'Curiosity', 'Saved question?', 'Correct', 'Wrong', 'Recorded source']) expect(html).toContain(text);
    expect(html).not.toContain('countrydle-blog-post-footer');
    expect(html).not.toContain('href="javascript:');
    expect(html).toContain('href="https://example.com/"');
  } finally {
    try {
      await dom.happyDOM.close();
    } finally {
      for (const [name, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else Reflect.deleteProperty(globalThis, name);
      }
    }
  }
});
