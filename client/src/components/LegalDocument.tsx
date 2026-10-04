import type { ReactNode } from 'react';

interface LegalDocumentProps {
  title: string;
  lastUpdated: string;
  children: ReactNode;
}

export default function LegalDocument({ title, lastUpdated, children }: LegalDocumentProps) {
  return (
    <article className="mx-auto min-w-0 max-w-4xl pb-8 text-zinc-300">
      <header className="border-b border-white/10 pb-8 md:pb-10">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">
          Countrydle / Legal
        </p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-sand-100 sm:text-5xl">
          {title}
        </h1>
        <p className="mt-4 text-sm text-zinc-400">Last updated: {lastUpdated}</p>
      </header>
      <div className="divide-y divide-white/10 break-words text-base leading-7 [&>section]:py-8 md:[&>section]:py-10 [&_h2]:mb-4 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:leading-snug [&_h2]:text-sand-100 [&_h3]:mb-2 [&_h3]:font-medium [&_h3]:text-sand-100 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5 [&_li]:pl-1 [&_a]:text-emerald-300 [&_a]:underline [&_a]:decoration-emerald-400/30 [&_a]:underline-offset-4 [&_a:hover]:text-emerald-200">
        {children}
      </div>
    </article>
  );
}
