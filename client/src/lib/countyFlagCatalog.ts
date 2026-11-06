import type { PowiatHeraldrySourceAttribution } from '../types';

export interface CountyFlagCatalogEntry {
  id: number;
  name: string;
  voivodeship: string;
  is_city_county: boolean;
  flag_asset_url: string;
  thumbnail_asset_url?: string;
  source_attribution?: PowiatHeraldrySourceAttribution | null;
}

/** The server catalog is the sole authority on flag eligibility. */
export function countyFlagQuizCatalog<T extends { id: number }>(flags: CountyFlagCatalogEntry[], counties: T[]): Array<T & CountyFlagCatalogEntry> {
  const byId = new Map(counties.map((county) => [county.id, county]));
  return flags.flatMap((flag) => {
    const county = byId.get(flag.id);
    return county ? [{ ...county, ...flag }] : [];
  });
}
