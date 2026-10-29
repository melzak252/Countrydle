export const gameCatalog = [
  { title: 'Flags and coats', games: [
    { path: '/flagdle', name: 'Flagdle' },
    { path: '/flag-shades', name: 'Flag Shades' },
    { path: '/herby-powiatow', name: 'County Coats of Arms' },
    { path: '/quiz-herbow', name: 'Coats of Arms Quiz' },
  ] },
  { title: 'Continents', games: [
    { path: '/europe', name: 'Europedle' },
    { path: '/asia', name: 'Asiadle' },
    { path: '/africa', name: 'Africadle' },
    { path: '/americas', name: 'Americadle' },
  ] },
  { title: 'States and regions', games: [
    { path: '/us-states', name: 'US Statedle' },
    { path: '/wojewodztwa', name: 'Województwodle' },
    { path: '/powiaty', name: 'Powiatdle' },
  ] },
  { title: 'More ways to play', games: [
    { path: '/border-hop', name: 'Border Hop' },
    { path: '/friends', name: 'Friend duels' },
  ] },
] as const;
