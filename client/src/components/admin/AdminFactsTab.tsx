import React from 'react';
import { Database, FileText, Trash2, Plus } from 'lucide-react';
import type { CountryFactsResponse } from '../../services/api';
import type { AdminGameType } from './AdminQuestionsTab';

export interface EntityOption {
  id: number;
  name: string;
}

interface AdminFactsTabProps {
  factMode: AdminGameType;
  factEntities: EntityOption[];
  selectedEntityId: number | null;
  entityFacts: CountryFactsResponse | null;
  factInputs: Record<string, string>;
  newListValues: Record<string, string>;
  factError: string | null;
  onFactModeChange: (mode: AdminGameType) => void;
  onEntitySelect: (id: number, name: string) => void;
  onFactInputChange: (relation: string, value: string) => void;
  onSaveScalarFact: (relation: string, value: string) => Promise<void>;
  onNewListValueChange: (relation: string, value: string) => void;
  onAddListFact: (relation: string, value: string) => Promise<void>;
  onDeleteListFact: (relation: string, value: string) => Promise<void>;
}

const FACT_MODES: { id: AdminGameType; label: string }[] = [
  { id: 'countrydle', label: 'Countries (SQLite)' },
  { id: 'powiatdle', label: 'Counties (SQLite)' },
  { id: 'wojewodztwodle', label: 'Voivodeships (SQLite)' },
  { id: 'us_statedle', label: 'US States (SQLite)' },
];

export const AdminFactsTab: React.FC<AdminFactsTabProps> = ({
  factMode,
  factEntities,
  selectedEntityId,
  entityFacts,
  factInputs,
  newListValues,
  factError,
  onFactModeChange,
  onEntitySelect,
  onFactInputChange,
  onSaveScalarFact,
  onNewListValueChange,
  onAddListFact,
  onDeleteListFact,
}) => {
  return (
    <div className="space-y-6 animate-message">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          {FACT_MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onFactModeChange(m.id)}
              className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors border ${
                factMode === m.id
                  ? 'bg-emerald-400/15 text-emerald-300 border-emerald-400/40'
                  : 'bg-obsidian-900 text-sand-100/65 hover:text-sand-100 border-white/10 hover:border-white/20'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Select Destination Entity */}
        <div className="w-full sm:w-72">
          <select
            aria-label="Select knowledge base entity"
            value={selectedEntityId || ''}
            onChange={(e) => {
              const id = Number(e.target.value);
              const selected = factEntities.find((item) => item.id === id);
              if (selected) {
                onEntitySelect(id, selected.name);
              }
            }}
            className="w-full bg-obsidian-900 border border-white/10 text-sand-100 rounded-sm px-3 py-2 text-xs focus:outline-none focus:border-emerald-400"
          >
            {factEntities.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {factError && (
        <div className="p-4 bg-red-900/20 border border-red-500/40 rounded-sm text-red-400 text-xs">
          {factError}
        </div>
      )}

      {entityFacts && (
        <div className="min-w-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Scalar Facts Card */}
          <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
            <h3 className="text-base font-semibold text-sand-100 flex items-center gap-2">
              <Database size={16} className="text-emerald-300" />
              <span>Scalar Facts: {entityFacts.country.name}</span>
            </h3>

            <div className="space-y-3 max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
              {(entityFacts.scalar_facts || []).map((fact) => (
                <div key={fact.relation} className="border-b border-white/10 pb-4 space-y-2 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-sand-100/80 capitalize">{fact.relation.replace(/_/g, ' ')}</span>
                    <span className="text-xs text-sand-100/55 font-mono">{fact.value_type}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={factInputs[fact.relation] ?? ''}
                      aria-label={`${fact.relation.replace(/_/g, ' ')} value`}
                      onChange={(e) => onFactInputChange(fact.relation, e.target.value)}
                      className="min-w-0 flex-1 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs"
                    />
                    <button
                      type="button"
                      aria-label={`Save ${fact.relation.replace(/_/g, ' ')}`}
                      onClick={() => onSaveScalarFact(fact.relation, factInputs[fact.relation] ?? '')}
                      className="px-2.5 py-1 bg-emerald-400/10 hover:bg-emerald-400/20 text-sand-100 font-semibold rounded-sm text-xs border border-emerald-400/20"
                    >
                      Save
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* List Facts Card */}
          <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
            <h3 className="text-base font-semibold text-sand-100 flex items-center gap-2">
              <FileText size={16} className="text-sand-100/80" />
              <span>List / Multi-Value Facts</span>
            </h3>

            <p className="text-xs leading-relaxed text-sand-100/65">
              Changes are saved immediately. <span className="text-rose-300 font-medium">Deleting a value removes it from the facts catalog.</span>
            </p>
            <div className="space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
              {(entityFacts.list_facts || []).map((listFact) => (
                <div key={listFact.relation} className="border-b border-white/10 pb-4 space-y-3 text-sm">
                  <div className="font-semibold text-sand-100 capitalize">
                    {listFact.relation.replace(/_/g, ' ')} ({listFact.values.length})
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {listFact.values.map((v) => (
                      <span
                        key={v.value}
                        className="inline-flex max-w-full items-center gap-1.5 px-2.5 py-1 rounded-sm bg-obsidian-950 border border-white/10 text-sand-100/80 text-xs"
                      >
                        <span className="min-w-0 break-all">{v.value}</span>
                        <button
                          type="button"
                          aria-label={`Delete ${v.value} from ${listFact.relation.replace(/_/g, ' ')}`}
                          onClick={() => onDeleteListFact(listFact.relation, v.value)}
                          className="p-1 text-rose-400 hover:text-rose-300 transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </span>
                    ))}
                  </div>

                  {/* Add new value input */}
                  <div className="flex gap-2 pt-1">
                    <input
                      type="text"
                      value={newListValues[listFact.relation] || ''}
                      aria-label={`New ${listFact.relation.replace(/_/g, ' ')} value`}
                      onChange={(e) => onNewListValueChange(listFact.relation, e.target.value)}
                      placeholder={`Add new ${listFact.relation.replace(/_/g, ' ')}...`}
                      className="min-w-0 flex-1 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs"
                    />
                    <button
                      type="button"
                      aria-label={`Add ${listFact.relation.replace(/_/g, ' ')} value`}
                      onClick={() => onAddListFact(listFact.relation, newListValues[listFact.relation] || '')}
                      className="px-3 py-1 bg-emerald-400/10 hover:bg-emerald-400/20 text-sand-100 font-semibold rounded-sm text-xs flex items-center gap-1 border border-emerald-400/20"
                    >
                      <Plus size={12} />
                      <span>Add</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminFactsTab;
