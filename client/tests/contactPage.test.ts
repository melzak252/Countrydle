import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import ContactPage from '../src/pages/ContactPage';

const i18n = createInstance();
await i18n.init({ lng: 'en', resources: { en: { translation: {} } } });

test('Contact & Feedback shows the canonical contact email and mailto link', () => {
  const markup = renderToStaticMarkup(createElement(
    I18nextProvider,
    { i18n },
    createElement(ContactPage),
  ));

  expect(markup).toContain('href="mailto:melzacki.jakub@gmail.com"');
  expect(markup).toContain('>melzacki.jakub@gmail.com</a>');
  expect(markup).not.toContain('@jmelzacki.com');
});
