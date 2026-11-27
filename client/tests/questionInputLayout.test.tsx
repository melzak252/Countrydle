import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import QuestionInput from '../src/components/QuestionInput';

const i18n = createInstance();
await i18n.init({ lng: 'en', resources: { en: { translation: {} } } });

test('ask button sits flush against the right edge of the question input', () => {
  const markup = renderToStaticMarkup(createElement(
    I18nextProvider,
    { i18n },
    createElement(QuestionInput, { onAsk: async () => {}, isLoading: false }),
  ));
  const askButton = markup.match(/<button\b(?=[^>]*aria-label="Ask question")[^>]*>/)?.[0];

  expect(askButton).toBeDefined();
  expect(askButton).toMatch(/(?:^|\s)right-0(?:\s|")/);
});
