import { useTranslation } from 'react-i18next';
import type { FactProvenanceRecord } from '../types';
import { factProvenanceLabels, PROVENANCE_TEXT_FIELDS, safeFactSourceUrl } from '../lib/factProvenance';

export default function FactProvenance({ records }: { records?: FactProvenanceRecord[] }) {
  const { i18n } = useTranslation();
  const labels = factProvenanceLabels(i18n.language.startsWith('pl'));
  if (!records?.length) return null;

  return (
    <section aria-label={labels.title} className="min-w-0 space-y-3 text-sm [overflow-wrap:anywhere]">
      <h4 className="font-medium text-sand-100">{labels.title}</h4>
      <ul className="space-y-3">
        {records.map(record => {
          const sourceUrl = safeFactSourceUrl(record.provenance.source_url);
          return (
            <li key={`${record.relation}:${JSON.stringify(record.value)}`} className="min-w-0 space-y-2 rounded-sm border border-white/10 p-3">
              <p className="font-medium text-sand-100">{record.relation} · {record.value === null ? labels.aggregate : record.value}</p>
              <dl className="space-y-2 text-xs">
                <div><dt className="text-slate-400">{labels.status}</dt><dd className="text-slate-300">{record.provenance.status === 'cited' ? labels.cited : labels.unknown}</dd></div>
                {PROVENANCE_TEXT_FIELDS.map(field => (
                  <div key={field}>
                    <dt className="text-slate-400">{labels[field]}</dt>
                    <dd className="whitespace-pre-wrap text-slate-300">
                      {field === 'source_url'
                        ? sourceUrl
                          ? <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-emerald-300 underline">{sourceUrl}</a>
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
