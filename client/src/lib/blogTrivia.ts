export function getFalseDistractor(
  _countryName?: string,
  continent?: string | null,
  facts?: { continent?: string | null } | null,
  isPl: boolean = false,
): string {
  const normCont = (continent || facts?.continent || '').toLowerCase();

  if (normCont.includes('africa')) {
    return isPl
      ? 'Jest państwem śródlądowym położonym całkowicie w Ameryce Południowej.'
      : 'It is a landlocked country located entirely within South America.';
  }
  if (normCont.includes('europe')) {
    return isPl
      ? 'Jest państwem wyspiarskim położonym całkowicie na półkuli południowej.'
      : 'It is an island nation situated entirely in the Southern Hemisphere.';
  }
  if (normCont.includes('asia')) {
    return isPl
      ? 'Jest suwerennym państwem położonym w Ameryce Środkowej.'
      : 'It is a sovereign country located entirely within Central America.';
  }
  if (normCont.includes('south america')) {
    return isPl
      ? 'Jest państwem członkowskim Unii Europejskiej w Europie.'
      : 'It is a member state of the European Union situated in Europe.';
  }
  if (normCont.includes('north america') || normCont.includes('americas')) {
    return isPl
      ? 'Leży na kontynencie afrykańskim i graniczy z Jeziorem Wiktorii.'
      : 'It is located on the African continent and borders Lake Victoria.';
  }
  if (normCont.includes('oceania')) {
    return isPl
      ? 'Jest alpejskim państwem śródlądowym w Europie Środkowej.'
      : 'It is a landlocked alpine country located in Central Europe.';
  }
  return isPl
    ? 'Posiada bezpośrednią granicę lądową z Antarktydą.'
    : 'It shares an extensive direct land border with Antarctica.';
}
