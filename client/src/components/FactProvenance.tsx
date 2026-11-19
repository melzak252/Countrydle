import type { FactProvenanceRecord } from '../types';
import { factProvenanceLabels, PROVENANCE_TEXT_FIELDS, safeFactSourceUrl } from '../lib/factProvenance';

export default function FactProvenance({ records }: { records?: FactProvenanceRecord[] }) {
  const labels = factProvenanceLabels;
  if (!records?.length) return null;

  return (
    <section aria-label={labels.title} className="min-w-0 space-y-3 text-sm [overflow-wrap:anywhere]">
      <h4 className="font-medium text-app-text">{labels.title}</h4>
      <ul className="space-y-3">
        {records.map(record => {
          const sourceUrl = safeFactSourceUrl(record.provenance.source_url);
          return (
            <li key={`${record.relation}:${JSON.stringify(record.value)}`} className="min-w-0 space-y-2 rounded-sm border border-app-border/15 p-3">
              <p className="font-medium text-app-text">{record.relation} · {record.value === null ? labels.aggregate : record.value}</p>
              <dl className="space-y-2 text-xs">
                <div><dt className="text-app-text-muted">{labels.status}</dt><dd className="text-app-text-secondary">{record.provenance.status === 'cited' ? labels.cited : labels.unknown}</dd></div>
                {PROVENANCE_TEXT_FIELDS.map(field => (
                  <div key={field}>
                    <dt className="text-app-text-muted">{labels[field]}</dt>
                    <dd className="whitespace-pre-wrap text-app-text-secondary">
                      {field === 'source_url'
                        ? sourceUrl
                          ? <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-app-accent underline">{sourceUrl}</a>
                          : labels.unknown
                        : record.provenance[field] || labels.unknown}
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
