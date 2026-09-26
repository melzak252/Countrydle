import { expect, test } from 'bun:test';
import { getQuickQuestions } from '../src/components/QuestionInput';

// Mock translation function returning the key
const mockT = (key: string) => key;

test('country mode returns global country starter chips', () => {
  const chips = getQuickQuestions('country', mockT);
  expect(chips.length).toBe(6);
  expect(chips.map(c => c.icon)).toEqual(['🌍', '🌊', '👑', '🚗', '🇪🇺', '🏝️']);
  expect(chips[0].question).toBe('inputs.questionEurope');
});

test('wojewodztwa mode returns Polish voivodeship-specific chips', () => {
  const chips = getQuickQuestions('wojewodztwa', mockT);
  expect(chips.length).toBe(6);
  expect(chips.map(c => c.icon)).toEqual(['🌊', '⛰️', '🌐', '🧭', '🧭', '🏙️']);
  expect(chips[0].question).toBe('inputs.questionWojCoastline');
  expect(chips[1].question).toBe('inputs.questionWojMountains');
  expect(chips[2].question).toBe('inputs.questionWojBorderCountry');
});

test('powiaty mode returns Polish county-specific chips', () => {
  const chips = getQuickQuestions('powiaty', mockT);
  expect(chips.length).toBe(6);
  expect(chips.map(c => c.icon)).toEqual(['🏙️', '🌳', '🌊', '⛰️', '🧭', '🌐']);
  expect(chips[0].question).toBe('inputs.questionPowCityCounty');
  expect(chips[1].question).toBe('inputs.questionPowLandCounty');
  expect(chips[2].question).toBe('inputs.questionPowCoastline');
});

test('us_states mode returns US State-specific chips', () => {
  const chips = getQuickQuestions('us_states', mockT);
  expect(chips.length).toBe(6);
  expect(chips.map(c => c.icon)).toEqual(['🌊', '🌽', '🦞', '🌵', '🏔️', '⚔️']);
  expect(chips[0].question).toBe('inputs.questionUsCoastal');
  expect(chips[1].question).toBe('inputs.questionUsMidwest');
  expect(chips[2].question).toBe('inputs.questionUsNewEngland');
  expect(chips[5].question).toBe('inputs.questionUsConfederacy');
});

test('continental modes return continent-tailored chips', () => {
  const europeChips = getQuickQuestions('europe', mockT);
  expect(europeChips[0].question).toBe('inputs.questionEu');
  expect(europeChips[3].question).toBe('inputs.questionContEuro');

  const asiaChips = getQuickQuestions('asia', mockT);
  expect(asiaChips[4].question).toBe('inputs.questionAsiaIslam');
  expect(asiaChips[5].question).toBe('inputs.questionAsiaSoutheast');

  const africaChips = getQuickQuestions('africa', mockT);
  expect(africaChips[1].question).toBe('inputs.questionAfricaNorth');
  expect(africaChips[3].question).toBe('inputs.questionAfricaSouthEquator');

  const americasChips = getQuickQuestions('americas', mockT);
  expect(americasChips[0].question).toBe('inputs.questionAmericasSouth');
  expect(americasChips[1].question).toBe('inputs.questionAmericasCaribbean');
  expect(americasChips[2].question).toBe('inputs.questionAmericasPacific');
});
