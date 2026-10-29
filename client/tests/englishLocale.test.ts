import assert from 'node:assert/strict';
import { test } from 'node:test';
import i18n from '../src/i18n.ts';

test('a Polish language request resolves application translations in English', async () => {
  await i18n.changeLanguage('pl');
  assert.equal(i18n.resolvedLanguage, 'en');
  assert.equal(i18n.t('header.archive'), 'Archive');
  await i18n.changeLanguage('en');
});
