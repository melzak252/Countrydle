import React, { useState } from 'react';
import { Database, FileText, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService, type CountryFactsResponse } from '../../services/api';
import type { AnswerReportMode, FactProvenance as FactProvenanceData, FactProvenanceRecord } from '../../types';
import FactProvenance from '../FactProvenance';
import { factProvenanceLabels, PROVENANCE_TEXT_FIELDS, safeFactSourceUrl, UNKNOWN_FACT_PROVENANCE } from '../../lib/factProvenance';

export interface EntityOption {
  id: number;
  name: string;
}

interface AdminFactsTabProps {
  factMode: AnswerReportMode;
  factEntities: EntityOption[];
  selectedEntityId: number | null;
  entityFacts: CountryFactsResponse | null;
  factInputs: Record<string, string>;
  newListValues: Record<string, string>;
  factError: string | null;
  isEntitiesLoading: boolean;
  isFactsLoading: boolean;
  onRefresh: () => Promise<void>;
  onFactModeChange: (mode: AnswerReportMode) => void;
  onEntitySelect: (id: number, name: string) => void;
  onFactInputChange: (relation: string, value: string) => void;
  onSaveScalarFact: (relation: string, value: string) => Promise<void>;
  onNewListValueChange: (relation: string, value: string) => void;
  onAddListFact: (relation: string, value: string) => Promise<void>;
  onDeleteListFact: (relation: string, value: string) => Promise<void>;
}

const FACT_MODES: AnswerReportMode[] = ['countrydle', 'powiatdle', 'wojewodztwodle', 'us_statedle'];
function ProvenanceEditor({ record, disabled, onSave }: {
  record: FactProvenanceRecord;
  disabled: boolean;
  onSave: (record: FactProvenanceRecord) => Promise<void>;
}) {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const labels = factProvenanceLabels(isPl);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<FactProvenanceData>({ ...record.provenance });
  const [error, setError] = useState<string | null>(null);

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (disabled) return;
    setError(null);
    if (draft.source_url && !safeFactSourceUrl(draft.source_url)) {
      setError(isPl ? 'Źródło musi być bezwzględnym adresem HTTP(S) bez danych logowania.' : 'Source must be an absolute HTTP(S) URL without credentials.');
      return;
    }
    if (draft.status === 'cited' && (!draft.citation || !draft.source_url)) {
      setError(isPl ? 'Status ze źródłem wymaga cytatu i adresu źródła.' : 'Cited evidence requires a citation and source URL.');
      return;
    }
    if (draft.effective_from && draft.effective_to && draft.effective_to < draft.effective_from) {
      setError(isPl ? 'Data końcowa nie może poprzedzać daty początkowej.' : 'Effective to must not precede effective from.');
      return;
    }
    try {
      await onSave({ relation: record.relation, value: record.value, provenance: { ...draft } });
      setEditing(false);
    } catch {
      setError(isPl ? 'Nie udało się zapisać pochodzenia. Sprawdź format dat (ISO 8601) i spróbuj ponownie.' : 'Could not save provenance. Check date formats (ISO 8601) and retry.');
    }
  };

  return (
    <div className="min-w-0 space-y-2">
      <FactProvenance records={[record]} />
      {!editing ? (
        <button type="button" className="admin-button" disabled={disabled} onClick={() => {
          setDraft({ ...record.provenance });
          setError(null);
          setEditing(true);
        }}>{labels.edit}: {record.value ?? labels.aggregate}</button>
      ) : (
        <form onSubmit={(event) => void save(event)} className="min-w-0 space-y-3 rounded-sm border border-emerald-400/30 p-3">
          <p className="text-sm text-slate-300">{isPl ? 'Edytujesz wyłącznie dowody, nie wartość faktu. Puste pola oznaczają „Nieznane”.' : 'Editing evidence only, not the fact value. Empty fields mean “Unknown”.'}</p>
          <label className="block space-y-1 text-sm text-slate-300">
            <span>{labels.status}</span>
            <select className="admin-control" value={draft.status} disabled={disabled} onChange={(event) => setDraft({ ...draft, status: event.target.value as FactProvenanceData['status'] })}>
              <option value="unknown">{labels.unknown}</option>
              <option value="cited">{labels.cited}</option>
            </select>
          </label>
          {PROVENANCE_TEXT_FIELDS.map(field => (
            <label key={field} className="block space-y-1 text-sm text-slate-300">
              <span>{labels[field]}{(field === 'retrieved_at' || field === 'updated_at') && ' (ISO 8601)'}</span>
              {field === 'citation' || field === 'convention' ? (
                <textarea className="admin-control" rows={3} value={draft[field] ?? ''} placeholder={labels.unknown} disabled={disabled} required={field === 'citation' && draft.status === 'cited'} onChange={(event) => setDraft({ ...draft, [field]: event.target.value.trim() ? event.target.value : null })} />
              ) : (
                <input className="admin-control" type={field === 'source_url' ? 'url' : field === 'effective_from' || field === 'effective_to' ? 'date' : 'text'} value={draft[field] ?? ''} placeholder={labels.unknown} disabled={disabled} required={field === 'source_url' && draft.status === 'cited'} onChange={(event) => setDraft({ ...draft, [field]: event.target.value.trim() || null })} />
              )}
            </label>
          ))}
          {error && <p role="alert" className="text-sm text-rose-200">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className="admin-button admin-button-primary" disabled={disabled}>{isPl ? 'Zapisz pochodzenie' : 'Save provenance'}</button>
            <button type="button" className="admin-button" disabled={disabled} onClick={() => setEditing(false)}>{isPl ? 'Anuluj' : 'Cancel'}</button>
          </div>
        </form>
      )}
    </div>
  );
}


export const AdminFactsTab: React.FC<AdminFactsTabProps> = ({
  factMode,
  factEntities,
  selectedEntityId,
  entityFacts,
  factInputs,
  newListValues,
  factError,
  isEntitiesLoading,
  isFactsLoading,
  onRefresh,
  onFactModeChange,
  onEntitySelect,
  onFactInputChange,
  onSaveScalarFact,
  onNewListValueChange,
  onAddListFact,
  onDeleteListFact,
}) => {
  const { t, i18n } = useTranslation();
  const numberFormat = new Intl.NumberFormat(i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US');
  const [pendingWrites, setPendingWrites] = useState(0);
  const busy = isEntitiesLoading || isFactsLoading || pendingWrites > 0;
  const writesDisabled = busy || !entityFacts || Boolean(factError);

  const runWrite = async (operation: () => Promise<void>) => {
    setPendingWrites((count) => count + 1);
    try {
      await operation();
    } finally {
      setPendingWrites((count) => Math.max(0, count - 1));
    }
  };

  return (
    <section className="min-w-0 space-y-5" aria-labelledby="admin-page-title">
      <div className="admin-toolbar flex flex-wrap items-end gap-4">
        <fieldset className="min-w-0 flex-1">
          <legend className="mb-2 text-sm font-medium text-slate-300">{t('adminFacts.modeLabel')}</legend>
          <div className="flex flex-wrap gap-2">
            {FACT_MODES.map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={factMode === mode}
                className={factMode === mode ? 'admin-button admin-button-primary' : 'admin-button'}
                onClick={() => onFactModeChange(mode)}
                disabled={busy}
              >
                {t(`adminFacts.modes.${mode}`)}
              </button>
            ))}
          </div>
        </fieldset>
        <div className="w-full sm:w-80">
          <label htmlFor="admin-facts-entity" className="mb-2 block text-sm font-medium text-slate-300">{t('adminFacts.entityLabel')}</label>
          <select
            id="admin-facts-entity"
            className="admin-control"
            value={selectedEntityId ?? ''}
            onChange={(event) => {
              const entityId = Number(event.target.value);
              const entity = factEntities.find((item) => item.id === entityId);
              if (entity) onEntitySelect(entity.id, entity.name);
            }}
            disabled={busy || factEntities.length === 0}
          >
            <option value="">{t('adminFacts.chooseEntity')}</option>
            {factEntities.map((entity) => <option key={entity.id} value={entity.id}>{entity.name}</option>)}
          </select>
        </div>
        <button type="button" className="admin-button" onClick={() => void onRefresh()} disabled={busy}>
          <RefreshCw aria-hidden="true" size={15} />
          {busy ? t('adminCommon.updating') : t('adminCommon.refresh')}
        </button>
      </div>

      {selectedEntityId !== null && entityFacts && (
        <h2 className="text-lg font-semibold text-sand-100">{entityFacts.country.name}</h2>
      )}
      <p className="admin-panel text-sm leading-6 text-slate-300">
        {t('adminFacts.immediateWarning')} <span className="font-medium text-rose-300">{t('adminFacts.deleteWarning')}</span>
      </p>
      {factError && <div role="alert" className="admin-panel border-rose-400/40 text-rose-200">{t(factError)}</div>}
      {(isEntitiesLoading || isFactsLoading) && <p role="status" className="admin-panel">{t('adminCommon.loading')}</p>}
      {factError && !isEntitiesLoading && !isFactsLoading && (
        <button type="button" className="admin-button" onClick={() => void onRefresh()} disabled={busy}>{t('adminCommon.retry')}</button>
      )}
      {!isEntitiesLoading && !isFactsLoading && !factError && factEntities.length === 0 && (
        <p className="admin-panel admin-muted">{t('adminFacts.noEntities')}</p>
      )}
      {!isEntitiesLoading && !isFactsLoading && !factError && factEntities.length > 0 && selectedEntityId === null && (
        <p className="admin-panel admin-muted">{t('adminFacts.selectEntity')}</p>
      )}
      {!isEntitiesLoading && !isFactsLoading && !factError && selectedEntityId !== null && !entityFacts && (
        <p className="admin-panel admin-muted">{t('adminFacts.noFacts')}</p>
      )}

      {entityFacts && !isFactsLoading && (
        <div className="grid min-w-0 grid-cols-1 gap-4 min-[1280px]:grid-cols-2">
          <section className="admin-panel min-w-0 space-y-4" aria-labelledby="admin-facts-scalars">
            <h3 id="admin-facts-scalars" className="flex items-center gap-2 text-base font-semibold text-sand-100">
              <Database aria-hidden="true" size={17} className="text-emerald-300" />
              {t('adminFacts.scalarHeading')}
            </h3>
            {entityFacts.scalar_facts.length === 0 ? <p className="admin-muted">{t('adminFacts.noScalarFacts')}</p> : (
              <div className="space-y-4 min-[1280px]:max-h-[500px] min-[1280px]:overflow-y-auto">
                {entityFacts.scalar_facts.map((fact) => {
                  const relation = fact.relation.replace(/_/g, ' ');
                  return (
                    <div key={fact.relation} className="space-y-2 border-b border-white/10 pb-4">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <label htmlFor={`fact-value-${fact.relation}`} className="font-medium capitalize text-sand-100">{relation}</label>
                        <span className="admin-meta">{fact.value_type}</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <input id={`fact-value-${fact.relation}`} type="text" value={factInputs[fact.relation] ?? ''} onChange={(event) => onFactInputChange(fact.relation, event.target.value)} className="admin-control min-w-0 flex-1" disabled={writesDisabled} />
                        <button type="button" className="admin-button admin-button-primary" onClick={() => void runWrite(() => onSaveScalarFact(fact.relation, factInputs[fact.relation] ?? ''))} disabled={writesDisabled}>{t('adminCommon.save')}</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="admin-panel min-w-0 space-y-4" aria-labelledby="admin-facts-lists">
            <h3 id="admin-facts-lists" className="flex items-center gap-2 text-base font-semibold text-sand-100">
              <FileText aria-hidden="true" size={17} className="text-slate-300" />
              {t('adminFacts.listHeading')}
            </h3>
            {entityFacts.list_facts.length === 0 ? <p className="admin-muted">{t('adminFacts.noListFacts')}</p> : (
              <div className="space-y-4 min-[1280px]:max-h-[500px] min-[1280px]:overflow-y-auto">
                {entityFacts.list_facts.map((listFact) => {
                  const relation = listFact.relation.replace(/_/g, ' ');
                  const evidenceRelation = listFact.relation === 'membership' || listFact.relation === 'hemisphere' ? listFact.relation : null;
                  const evidenceRecords: FactProvenanceRecord[] = factMode === 'countrydle' && evidenceRelation
                    ? [null, ...listFact.values.map(value => value.value)].map(value => ({
                      relation: evidenceRelation,
                      value,
                      provenance: entityFacts.fact_provenance?.find(record => record.relation === evidenceRelation && record.value === value)?.provenance ?? UNKNOWN_FACT_PROVENANCE,
                    }))
                    : [];
                  return (
                    <div key={listFact.relation} className="space-y-3 border-b border-white/10 pb-4">
                      <h4 className="font-medium capitalize text-sand-100">{relation} <span className="admin-meta">({numberFormat.format(listFact.values.length)})</span></h4>
                      <ul className="space-y-2">
                        {listFact.values.map((value) => (
                          <li key={value.value} className="flex min-w-0 items-start justify-between gap-3 rounded-sm border border-white/10 bg-obsidian-950 px-3 py-2">
                            <span className="min-w-0 break-words text-sm text-slate-300">{value.value}</span>
                            <button type="button" className="admin-button admin-button-danger shrink-0" aria-label={t('adminFacts.deleteValue', { value: value.value, relation })} onClick={() => void runWrite(() => onDeleteListFact(listFact.relation, value.value))} disabled={writesDisabled}>
                              <Trash2 aria-hidden="true" size={15} />{t('adminCommon.delete')}
                            </button>
                          </li>
                        ))}
                      </ul>
                      {evidenceRecords.map(record => (
                        <ProvenanceEditor
                          key={`${entityFacts.country.id}:${record.relation}:${JSON.stringify(record.value)}`}
                          record={record}
                          disabled={writesDisabled}
                          onSave={(updated) => runWrite(async () => {
                            await adminService.updateCountryFactProvenance(entityFacts.country.id, updated);
                            await onRefresh();
                          })}
                        />
                      ))}
                      <div className="flex flex-wrap gap-2">
                        <label className="w-full text-sm font-medium text-slate-300" htmlFor={`fact-add-${listFact.relation}`}>{t('adminFacts.newValue', { relation })}</label>
                        <input id={`fact-add-${listFact.relation}`} type="text" value={newListValues[listFact.relation] ?? ''} onChange={(event) => onNewListValueChange(listFact.relation, event.target.value)} placeholder={t('adminFacts.newValue', { relation })} className="admin-control min-w-0 flex-1" disabled={writesDisabled} />
                        <button type="button" className="admin-button admin-button-primary" onClick={() => void runWrite(() => onAddListFact(listFact.relation, newListValues[listFact.relation] ?? ''))} disabled={writesDisabled}>
                          <Plus aria-hidden="true" size={15} />{t('adminCommon.add')}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
};

export default AdminFactsTab;
