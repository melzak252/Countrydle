import { expect, test } from 'bun:test';
import { gameCatalog } from '../src/lib/gameCatalog';

test('map quiz catalog lists powiat and US state quizzes as separate routes', () => {
  const mapQuizGames = gameCatalog.flatMap(({ games }) => games)
    .filter(({ name }) => name === 'Powiat Map Quiz' || name === 'US State Map Quiz');

  expect(mapQuizGames).toEqual([
    { path: '/powiat-map-quiz', name: 'Powiat Map Quiz', geography: 'poland' },
    { path: '/us-state-map-quiz', name: 'US State Map Quiz', geography: 'united-states' },
  ]);
});
