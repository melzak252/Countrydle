import type { RegionalSymbolScope } from '../types';

export default function RegionalGeographyCredit({ scope }: { scope: RegionalSymbolScope }) {
  return (
    <p aria-label="Geography data credit" className="text-xs leading-relaxed text-zinc-400">
      {scope === 'voivodeships' ? (
        <>Source: GUGiK Geoportal, August 2025; simplified GeoJSON by JW (waszkiewiczja), centroid calculations by Countrydle. <a className="text-emerald-300 underline" href="https://github.com/waszkiewiczja/GeoJSON-Polska-Wojewodztwa-Powiaty-Gminy" target="_blank" rel="noopener noreferrer">GeoJSON source</a>.</>
      ) : (
        <>{scope === 'london_boroughs'
          ? 'Contains National Statistics data © Crown copyright and database right 2026; contains OS data © Crown copyright and database right 2026.'
          : 'Contains OS data © Crown copyright and database right 2026. OS Boundary-Line, October 2026.'} <a className="text-emerald-300 underline" href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/" target="_blank" rel="noopener noreferrer">Open Government Licence v3.0</a>.</>
      )}
    </p>
  );
}
