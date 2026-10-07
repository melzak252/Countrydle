import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement, type ReactElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import QuestionChat from '../src/components/QuestionChat';
import ResultsQuestionHistory from '../src/components/ResultsQuestionHistory';
import AdminFactsTab from '../src/components/admin/AdminFactsTab';

const unknown = {
  status: 'unknown' as const, citation: null, source_url: null,
  effective_from: null, effective_to: null, retrieved_at: null, updated_at: null, convention: null,
};
const source = 'https://www.nato.int/en/about-us/nato-history/poland-and-nato';
const question = {
  id: 1, original_question: 'Is it a NATO member?', valid: true, answer: true,
  user_id: 1, day_id: 1, asked_at: '2026-09-26T10:00:00Z',
  fact_provenance: [{ relation: 'membership', value: 'NATO', provenance: {
    ...unknown, status: 'cited' as const, citation: 'Primary accession citation', source_url: source,
    effective_from: '1999-03-12', convention: 'Accession inclusive; no recorded end.',
  } }],
};
async function render(element: ReactElement, language = 'en') {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: { [language]: { translation: {} } } });
  return renderToStaticMarkup(createElement(I18nextProvider, { i18n }, element));
}

test('terminal chat renders the answer-used citation, interval, convention and safe source link', async () => {
  for (const [language, label] of [['en', 'Unknown'], ['pl', 'Nieznane']]) {
    const markup = await render(createElement(QuestionChat, { questions: [question], mode: 'countrydle', isGameOver: true }), language);
    expect(markup).toContain('Primary accession citation');
    expect(markup).toContain('1999-03-12');
    expect(markup).toContain('Accession inclusive; no recorded end.');
    expect(markup).toContain(`href="${source}"`);
    expect(markup).toContain('rel="noopener noreferrer"');
    expect(markup).toContain(label);
  }
});

test('a citation with an unknown source stays plain text instead of a fabricated hyperlink', async () => {
  const cited = { ...question, fact_provenance: [{ relation: 'hemisphere', value: null, provenance: {
    ...unknown, citation: 'Unverified hemisphere audit record 14477',
    convention: 'Any-territory versus representative-point remains disputed.',
  } }] };
  const markup = await render(createElement(QuestionChat, { questions: [cited], mode: 'continental', isGameOver: true }));
  expect(markup).toContain('Unverified hemisphere audit record 14477');
  expect(markup).toContain('Any-territory versus representative-point remains disputed.');
  expect(markup).toContain('Unknown');
  expect(markup).not.toContain('href=');
});

test('active chat never mounts stale detailed provenance including invalid-question evidence', async () => {
  for (const valid of [true, false]) {
    const markup = await render(createElement(QuestionChat, { questions: [{ ...question, valid }], mode: 'countrydle', isGameOver: false }));
    expect(markup).not.toContain('Primary accession citation');
    expect(markup).not.toContain(source);
    expect(markup).not.toContain('1999-03-12');
    expect(markup).not.toContain('Accession inclusive');
  }
});

test('terminal history never turns an unsafe or credential-bearing source into a link', async () => {
  for (const source_url of ['javascript:alert(1)', 'https://user:secret@example.com/source', 'https://@example.com/source', null]) {
    const unsafe = { ...question, fact_provenance: [{ ...question.fact_provenance[0], provenance: { ...unknown, source_url } }] };
    const markup = await render(createElement(ResultsQuestionHistory, { questions: [unsafe], mode: 'countrydle', isGameOver: true }));
    expect(markup).toContain('Unknown');
    expect(markup).not.toContain('javascript:');
    expect(markup).not.toContain('user:secret');
    expect(markup).not.toContain('href="https://user');
    expect(markup).not.toContain('href="https://@example.com');
  }
});

test('history requires an explicit terminal owner before mounting stale sources', async () => {
  const markup = await render(createElement(ResultsQuestionHistory, { questions: [question], mode: 'countrydle', isGameOver: false }));
  expect(markup).not.toContain('Primary accession citation');
  expect(markup).not.toContain(source);
});

test('terminal history rejects provenance from an unrelated mode even when stale storage contains it', async () => {
  const markup = await render(createElement(ResultsQuestionHistory, { questions: [question], mode: 'powiatdle', isGameOver: true }));
  expect(markup).not.toContain('Primary accession citation');
  expect(markup).not.toContain(source);
});

test('admin exposes aggregate evidence for an empty family and localizes every unknown without inventing dates', async () => {
  for (const [language, label] of [['en', 'Unknown'], ['pl', 'Nieznane']]) {
    const markup = await render(createElement(AdminFactsTab, {
      factMode: 'countrydle', factEntities: [{ id: 2, name: 'Japan' }], selectedEntityId: 2,
      entityFacts: { country: { id: 2, name: 'Japan' }, scalar_facts: [], list_facts: [
        { relation: 'membership', table: 'country_memberships', value_column: 'organization', metadata_columns: [], values: [] },
      ], fact_provenance: [{ relation: 'membership', value: null, provenance: unknown }] },
      factInputs: {}, newListValues: {}, factError: null, isEntitiesLoading: false, isFactsLoading: false,
      onRefresh: async () => {}, onFactModeChange: () => {}, onEntitySelect: () => {},
      onFactInputChange: () => {}, onSaveScalarFact: async () => {}, onNewListValueChange: () => {},
      onAddListFact: async () => {}, onDeleteListFact: async () => {},
    }), language);
    expect(markup.match(new RegExp(`>${label}<`, 'g'))?.length ?? 0).toBeGreaterThanOrEqual(8);
    expect(markup).toContain(language === 'pl' ? 'Cała relacja / brak wartości' : 'Whole relation / absence');
    expect(markup).toContain(language === 'pl' ? 'Edytuj pochodzenie' : 'Edit provenance');
    expect(markup).not.toContain('2026-');
  }
});

test('admin binds citation to the existing member and separately shows disputed aggregate convention', async () => {
  const markup = await render(createElement(AdminFactsTab, {
    factMode: 'countrydle', factEntities: [{ id: 1, name: 'Poland' }], selectedEntityId: 1,
    entityFacts: { country: { id: 1, name: 'Poland' }, scalar_facts: [], list_facts: [
      { relation: 'membership', table: 'country_memberships', value_column: 'organization', metadata_columns: [], values: [{ value: 'NATO', metadata: {} }, { value: 'UN', metadata: {} }] },
      { relation: 'hemisphere', table: 'country_hemispheres', value_column: 'hemisphere', metadata_columns: [], values: [] },
    ], fact_provenance: [
      question.fact_provenance[0],
      { relation: 'membership', value: null, provenance: unknown },
      { relation: 'membership', value: 'UN', provenance: unknown },
      { relation: 'hemisphere', value: null, provenance: { ...unknown, convention: 'Disputed any-territory convention.' } },
    ] },
    factInputs: {}, newListValues: {}, factError: null, isEntitiesLoading: false, isFactsLoading: false,
    onRefresh: async () => {}, onFactModeChange: () => {}, onEntitySelect: () => {},
    onFactInputChange: () => {}, onSaveScalarFact: async () => {}, onNewListValueChange: () => {},
    onAddListFact: async () => {}, onDeleteListFact: async () => {},
  }));
  expect(markup.match(/Primary accession citation/g)).toHaveLength(1);
  expect(markup).toContain('Disputed any-territory convention.');
  expect(markup).toContain('1999-03-12');
  expect(markup).toContain(`href="${source}"`);
});
