import type { RegionalSymbolComponentCredit } from '../types';

export default function SymbolComponentCredits({ credits }: { credits?: RegionalSymbolComponentCredit[] }) {
  if (!credits?.length) return null;
  return (
    <details className="basis-full select-text text-xs text-zinc-300">
      <summary className="cursor-pointer text-emerald-300 underline">Component credits ({credits.length})</summary>
      <ul className="mt-2 max-h-40 space-y-2 overflow-y-auto pl-4 list-disc sm:max-h-60">
        {credits.map((credit, index) => (
          <li key={`${credit.url}-${index}`}>
            <a href={credit.url} target="_blank" rel="noopener noreferrer" className="text-emerald-300 underline">{credit.title}</a>
            {' — '}{credit.author}{' — '}
            <a href={credit.license_url} target="_blank" rel="noopener noreferrer" className="text-emerald-300 underline">{credit.license}</a>
          </li>
        ))}
      </ul>
    </details>
  );
}
