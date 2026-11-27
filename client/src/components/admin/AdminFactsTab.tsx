import React, { useMemo, useState } from 'react';
import { Check, Database, List, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
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

const FACT_MODES: { id: AnswerReportMode; label: string }[] = [
  { id: 'countrydle', label: 'World Countries' },
  { id: 'powiatdle', label: 'Polish Counties' },
  { id: 'wojewodztwodle', label: 'Voivodeships' },
  { id: 'us_statedle', label: 'US States' },
];

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
  const { t } = useTranslation();
  const [pendingWrites, setPendingWrites] = useState(0);
  const [entitySearch, setEntitySearch] = useState('');
  const [factFilter, setFactFilter] = useState('');
  const [savedRelation, setSavedRelation] = useState<string | null>(null);

  const busy = isEntitiesLoading || isFactsLoading || pendingWrites > 0;
  const writesDisabled = busy || !entityFacts || Boolean(factError);

  const filteredEntities = useMemo(() => {
    const q = entitySearch.trim().toLowerCase();
    if (!q) return factEntities;
    return factEntities.filter((e) => e.name.toLowerCase().includes(q));
  }, [entitySearch, factEntities]);

  const filteredScalars = useMemo(() => {
    const list = entityFacts?.scalar_facts ?? [];
    const q = factFilter.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (f) =>
        f.relation.replace(/_/g, ' ').toLowerCase().includes(q) ||
        String(f.value ?? '').toLowerCase().includes(q),
    );
  }, [entityFacts?.scalar_facts, factFilter]);

  const filteredLists = useMemo(() => {
    const list = entityFacts?.list_facts ?? [];
    const q = factFilter.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (f) =>
        f.relation.replace(/_/g, ' ').toLowerCase().includes(q) ||
        f.values.some((v) => v.value.toLowerCase().includes(q)),
    );
  }, [entityFacts?.list_facts, factFilter]);

  const runWrite = async (operation: () => Promise<void>, markSaved?: string) => {
    setPendingWrites((count) => count + 1);
    try {
      await operation();
      if (markSaved) {
        setSavedRelation(markSaved);
        window.setTimeout(() => setSavedRelation((prev) => (prev === markSaved ? null : prev)), 1500);
      }
    } finally {
      setPendingWrites((count) => Math.max(0, count - 1));
    }
  };

  return (
    <section className="min-w-0 space-y-5" aria-labelledby="admin-page-title">
      {/* Mode + Entity Selector Bar */}
      <div className="rounded-md border border-app-border bg-app-surface p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Fact database mode">
            {FACT_MODES.map((mode) => {
              const active = factMode === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setEntitySearch('');
                    setFactFilter('');
                    onFactModeChange(mode.id);
                  }}
                  disabled={busy}
                  className={`rounded-sm border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 ${
                    active
                      ? 'border-app-accent bg-app-accent text-app-canvas'
                      : 'border-app-border bg-app-surface-muted text-app-text-secondary hover:text-app-text'
                  }`}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-sm border border-app-border bg-app-surface px-3 py-1.5 text-xs font-medium text-app-text hover:bg-app-surface-muted cursor-pointer disabled:opacity-50"
          >
            <RefreshCw size={13} className={busy ? 'animate-spin' : ''} aria-hidden="true" />
            {busy ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {/* Searchable Entity Picker + Fact Filter */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" aria-hidden="true" />
            <input
              type="search"
              value={entitySearch}
              onChange={(e) => setEntitySearch(e.target.value)}
              placeholder={`Filter ${factEntities.length} entities...`}
              aria-label="Filter entities"
              className="w-full rounded-sm border border-app-border bg-app-canvas py-2 pl-9 pr-3 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none"
            />
          </div>

          <select
            id="admin-facts-entity"
            aria-label="Select entity"
            value={selectedEntityId ?? ''}
            onChange={(event) => {
              const entityId = Number(event.target.value);
              const entity = factEntities.find((item) => item.id === entityId);
              if (entity) onEntitySelect(entity.id, entity.name);
            }}
            disabled={busy || filteredEntities.length === 0}
            className="w-full rounded-sm border border-app-border bg-app-canvas px-3 py-2 text-sm text-app-text focus:border-app-accent focus:outline-none disabled:opacity-50"
          >
            <option value="">
              {filteredEntities.length === 0 ? 'No matching entities' : `Choose entity (${filteredEntities.length})...`}
            </option>
            {filteredEntities.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.name}
              </option>
            ))}
          </select>

          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" aria-hidden="true" />
            <input
              type="search"
              value={factFilter}
              onChange={(e) => setFactFilter(e.target.value)}
              placeholder="Filter facts or values..."
              aria-label="Filter facts or values"
              disabled={!entityFacts}
              className="w-full rounded-sm border border-app-border bg-app-canvas py-2 pl-9 pr-3 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>
      </div>

      {factError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <span>{t(factError)}</span>
          <button
            type="button"
            onClick={() => void onRefresh()}
            disabled={busy}
            className="rounded-sm border border-rose-300 bg-white px-3 py-1 text-xs font-medium text-rose-900 hover:bg-rose-100 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {(isEntitiesLoading || isFactsLoading) && (
        <p role="status" className="rounded-md border border-app-border bg-app-surface px-4 py-6 text-center text-sm text-app-text-muted">
          Loading facts...
        </p>
      )}

      {!isEntitiesLoading && !isFactsLoading && !factError && selectedEntityId === null && (
        <div className="rounded-md border border-dashed border-app-border bg-app-surface px-6 py-10 text-center text-sm text-app-text-muted">
          Select an entity above to inspect and edit its local knowledge base facts.
        </div>
      )}

      {entityFacts && !isFactsLoading && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <div>
              <h2 className="font-serif text-xl font-semibold text-app-text">{entityFacts.country.name}</h2>
              <p className="text-xs text-app-text-muted">
                Changes write directly to the local SQLite fact database.
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs font-mono text-app-text-muted">
              <span>{filteredScalars.length} scalar</span>
              <span>·</span>
              <span>{filteredLists.length} list relations</span>
            </div>
          </div>

          <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-2">
            {/* Scalar Facts */}
            <section className="rounded-md border border-app-border bg-app-surface p-4 space-y-3" aria-labelledby="admin-facts-scalars">
              <div className="flex items-center gap-2 border-b border-app-border pb-2.5">
                <Database size={16} className="text-app-accent" aria-hidden="true" />
                <h3 id="admin-facts-scalars" className="text-sm font-semibold text-app-text">
                  Single-Value Facts ({filteredScalars.length})
                </h3>
              </div>

              {filteredScalars.length === 0 ? (
                <p className="py-4 text-center text-xs text-app-text-muted">No matching scalar facts.</p>
              ) : (
                <div className="space-y-3 max-h-[620px] overflow-y-auto pr-1">
                  {filteredScalars.map((fact) => {
                    const relationLabel = fact.relation.replace(/_/g, ' ');
                    const currentVal = factInputs[fact.relation] ?? '';
                    const originalVal = fact.value == null ? '' : String(fact.value);
                    const isDirty = currentVal !== originalVal;
                    const justSaved = savedRelation === fact.relation;

                    return (
                      <div key={fact.relation} className="rounded-sm border border-app-border/70 bg-app-canvas/40 p-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <label htmlFor={`fact-value-${fact.relation}`} className="text-xs font-semibold capitalize text-app-text">
                            {relationLabel}
                          </label>
                          <span className="rounded-sm bg-app-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-app-text-muted">
                            {fact.value_type}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            id={`fact-value-${fact.relation}`}
                            type="text"
                            value={currentVal}
                            onChange={(e) => onFactInputChange(fact.relation, e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !writesDisabled && isDirty) {
                                void runWrite(() => onSaveScalarFact(fact.relation, currentVal), fact.relation);
                              }
                            }}
                            disabled={writesDisabled}
                            className={`min-w-0 flex-1 rounded-sm border bg-app-surface px-2.5 py-1.5 text-sm text-app-text focus:border-app-accent focus:outline-none disabled:opacity-50 ${
                              isDirty ? 'border-amber-500/80' : 'border-app-border'
                            }`}
                          />
                          <button
                            type="button"
                            onClick={() => void runWrite(() => onSaveScalarFact(fact.relation, currentVal), fact.relation)}
                            disabled={writesDisabled}
                            className={`inline-flex items-center gap-1 rounded-sm border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 ${
                              justSaved
                                ? 'border-emerald-400 bg-emerald-50 text-emerald-800'
                                : isDirty
                                  ? 'border-app-accent bg-app-accent text-app-canvas hover:opacity-90'
                                  : 'border-app-border bg-app-surface text-app-text-secondary hover:text-app-text'
                            }`}
                          >
                            {justSaved ? <><Check size={13} /> Saved</> : 'Save'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* List / Multi-Value Facts */}
            <section className="rounded-md border border-app-border bg-app-surface p-4 space-y-3" aria-labelledby="admin-facts-lists">
              <div className="flex items-center gap-2 border-b border-app-border pb-2.5">
                <List size={16} className="text-app-accent" aria-hidden="true" />
                <h3 id="admin-facts-lists" className="text-sm font-semibold text-app-text">
                  List &amp; Multi-Value Facts ({filteredLists.length})
                </h3>
              </div>

              {filteredLists.length === 0 ? (
                <p className="py-4 text-center text-xs text-app-text-muted">No matching list facts.</p>
              ) : (
                <div className="space-y-4 max-h-[620px] overflow-y-auto pr-1">
                  {filteredLists.map((listFact) => {
                    const relationLabel = listFact.relation.replace(/_/g, ' ');
                    const draft = newListValues[listFact.relation] ?? '';

                    return (
                      <div key={listFact.relation} className="rounded-sm border border-app-border/70 bg-app-canvas/40 p-3 space-y-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-xs font-semibold capitalize text-app-text">
                            {relationLabel}
                          </h4>
                          <span className="rounded-sm bg-app-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-app-text-muted">
                            {listFact.values.length} {listFact.values.length === 1 ? 'value' : 'values'}
                          </span>
                        </div>

                        {listFact.values.length === 0 ? (
                          <p className="text-xs italic text-app-text-muted">No values recorded.</p>
                        ) : (
                          <ul className="flex flex-wrap gap-1.5">
                            {listFact.values.map((item) => (
                              <li
                                key={item.value}
                                className="inline-flex max-w-full items-center gap-1.5 rounded-sm border border-app-border bg-app-surface px-2.5 py-1 text-xs text-app-text"
                              >
                                <span className="break-all font-medium">{item.value}</span>
                                <button
                                  type="button"
                                  aria-label={`Delete ${item.value} from ${relationLabel}`}
                                  title={`Delete "${item.value}"`}
                                  onClick={() => void runWrite(() => onDeleteListFact(listFact.relation, item.value))}
                                  disabled={writesDisabled}
                                  className="ml-0.5 rounded-sm p-0.5 text-app-text-muted hover:bg-rose-50 hover:text-rose-700 cursor-pointer disabled:opacity-40"
                                >
                                  <Trash2 size={12} aria-hidden="true" />
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}

                        <div className="flex items-center gap-2 pt-1">
                          <input
                            id={`fact-add-${listFact.relation}`}
                            type="text"
                            value={draft}
                            onChange={(e) => onNewListValueChange(listFact.relation, e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && draft.trim() && !writesDisabled) {
                                void runWrite(() => onAddListFact(listFact.relation, draft));
                              }
                            }}
                            placeholder={`Add ${relationLabel}...`}
                            aria-label={`New value for ${relationLabel}`}
                            disabled={writesDisabled}
                            className="min-w-0 flex-1 rounded-sm border border-app-border bg-app-surface px-2.5 py-1.5 text-xs text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none disabled:opacity-50"
                          />
                          <button
                            type="button"
                            onClick={() => void runWrite(() => onAddListFact(listFact.relation, draft))}
                            disabled={writesDisabled || !draft.trim()}
                            className="inline-flex items-center gap-1 rounded-sm border border-app-accent bg-app-accent px-2.5 py-1.5 text-xs font-medium text-app-canvas hover:opacity-90 cursor-pointer disabled:opacity-40"
                          >
                            <Plus size={13} aria-hidden="true" />
                            Add
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </section>
  );
};

export default AdminFactsTab;
