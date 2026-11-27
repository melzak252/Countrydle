import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router-dom';
import BorderHopPage from '../src/pages/BorderHopPage';

const i18n = createInstance();
await i18n.init({
  lng: 'en',
  resources: {
    en: {
      translation: {
        borderHop: {
          title: 'Border Hop',
        },
      },
    },
  },
});

test('BorderHopPage renders title, mode selector, and navigation elements', () => {
  const markup = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: ['/border-hop?mode=countries'] },
      createElement(
        I18nextProvider,
        { i18n },
        createElement(BorderHopPage)
      )
    )
  );

  expect(markup).toContain('Border Hop');
  expect(markup).toContain('World Countries');
  expect(markup).toContain('US States');
});
test('BorderHopPage exposes the Polish powiat mode and selects it from the URL', () => {
  const markup = renderToStaticMarkup(
    createElement(
      MemoryRouter,
      { initialEntries: ['/border-hop?mode=powiaty'] },
      createElement(
        I18nextProvider,
        { i18n },
        createElement(BorderHopPage)
      )
    )
  );

  expect(markup).toContain('Powiaty');
  expect(markup).toContain('aria-label="Powiaty (Polish counties)"');
  expect(markup).toContain('aria-pressed="true"');
});
