import type { ReactNode } from 'react';

interface LegalDocumentProps {
  title: string;
  lastUpdated: string;
  children: ReactNode;
}

export default function LegalDocument({ title, lastUpdated, children }: LegalDocumentProps) {
  return (
    <article className="mx-auto min-w-0 max-w-4xl bg-app-canvas pb-8 text-app-text-secondary">
      <header className="border-b border-app-border pb-8 md:pb-10">
        <p className="mb-4 font-mono text-xs text-app-accent">
          Countrydle / Legal
        </p>
        <h1 className="font-serif text-4xl leading-tight tracking-tight text-app-text sm:text-5xl">
          {title}
        </h1>
        <p className="mt-4 text-sm text-app-text-muted">Last updated: {lastUpdated}</p>
      </header>
      <div className="divide-y divide-app-border break-words text-base leading-7 [&>section]:py-8 md:[&>section]:py-10 [&_h2]:mb-4 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:leading-snug [&_h2]:text-app-text [&_h3]:mb-2 [&_h3]:font-medium [&_h3]:text-app-text [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5 [&_li]:pl-1 [&_a]:text-app-accent [&_a]:underline [&_a]:underline-offset-4 [&_a:hover]:text-app-accent-hover">
        {children}
      </div>
    </article>
  );
}
