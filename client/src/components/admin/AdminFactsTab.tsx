import React, { useState } from 'react';
import { Database, FileText, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { CountryFactsResponse } from '../../services/api';
import type { AnswerReportMode } from '../../types';

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
