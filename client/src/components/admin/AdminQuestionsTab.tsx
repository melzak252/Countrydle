import React, { useMemo } from 'react';
import { Search, Sparkles } from 'lucide-react';

export interface AdminQuestionRecord {
  id: number;
  original_question?: string | null;
  question?: string | null;
  valid: boolean;
  answer?: boolean | null;
  explanation?: string | null;
  asked_at?: string | null;
  user?: {
    username?: string | null;
  } | null;
  day?: {
    continent?: string | null;
    country?: {
      name?: string | null;
    } | null;
  } | null;
}

export type AdminGameType = 'countrydle' | 'continental' | 'us_statedle' | 'powiatdle' | 'wojewodztwodle';
interface AdminQuestionsTabProps {
  mode: AdminGameType;
  questions: AdminQuestionRecord[];
  totalQuestions: number;
  page: number;
  search: string;
  selectedContinent?: string;
  onContinentChange?: (continent: string) => void;
  onModeChange: (mode: AdminGameType) => void;
  onSearchChange: (search: string) => void;
  onPageChange: (page: number) => void;
}

const MODES: { id: AdminGameType; label: string }[] = [
  { id: 'countrydle', label: 'Countries' },
  { id: 'continental', label: 'Continental' },
  { id: 'powiatdle', label: 'Counties (Powiaty)' },
  { id: 'wojewodztwodle', label: 'Voivodeships' },
  { id: 'us_statedle', label: 'US States' },
];

const CONTINENT_FILTERS = [
  { id: 'all', label: 'All Continents' },
  { id: 'europe', label: 'Europe' },
  { id: 'asia', label: 'Asia' },
  { id: 'africa', label: 'Africa' },
  { id: 'americas', label: 'Americas' },
];

export const AdminQuestionsTab: React.FC<AdminQuestionsTabProps> = ({
  mode,
  questions,
  totalQuestions,
  page,
  search,
  selectedContinent = 'all',
  onContinentChange,
  onModeChange,
  onSearchChange,
  onPageChange,
}) => {
  const filtered = useMemo(() => {
    if (!search.trim()) return questions;
    const q = search.toLowerCase();
    return questions.filter(
      (item) =>
        (item.original_question || item.question || '').toLowerCase().includes(q) ||
        (item.explanation || '').toLowerCase().includes(q) ||
        (item.user?.username || '').toLowerCase().includes(q) ||
        (item.day?.continent || '').toLowerCase().includes(q) ||
        (item.day?.country?.name || '').toLowerCase().includes(q)
    );
  }, [questions, search]);

  return (
    <div className="space-y-6 animate-message">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Mode Switcher */}
        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onModeChange(m.id as AdminGameType)}
              className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors border ${
                mode === m.id
                  ? 'bg-emerald-400/15 text-emerald-300 border-emerald-400/40'
                  : 'bg-obsidian-900 text-sand-100/65 hover:text-sand-100 border-white/10 hover:border-white/20'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Continent Sub-Filter when in Continental mode */}
        {mode === 'continental' && onContinentChange && (
          <div className="flex flex-wrap items-center gap-1.5 w-full pt-1 border-t border-white/5">
            <span className="text-[11px] uppercase font-mono tracking-wider text-sand-100/50 mr-1">Continent:</span>
            {CONTINENT_FILTERS.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onContinentChange(c.id)}
                className={`px-2.5 py-1 rounded-sm text-[11px] font-semibold transition-colors border ${
                  selectedContinent === c.id
                    ? 'bg-sky-400/20 text-sky-200 border-sky-400/40'
                    : 'bg-obsidian-950 text-sand-100/60 hover:text-sand-100 border-white/10'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sand-100/55" size={15} />
          <input
            type="text"
            aria-label="Filter questions or explanations"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter questions or explanations..."
            className="w-full pl-9 pr-4 py-2 bg-obsidian-900 border border-white/10 rounded-sm text-sand-100 text-xs focus:outline-none focus:border-emerald-400"
          />
        </div>
      </div>

      <div className="bg-obsidian-900 border border-white/10 rounded-sm overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs md:text-sm">
          <thead className="bg-white/[0.03] text-sand-100/65 border-b border-white/10">
            <tr>
              <th className="px-5 py-3 font-semibold">User</th>
              <th className="px-5 py-3 font-semibold">Question Asked</th>
              <th className="px-5 py-3 font-semibold">Status / Answer</th>
              <th className="px-5 py-3 font-semibold">Explanation</th>
              <th className="px-5 py-3 font-semibold text-right">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-xs font-mono text-zinc-500">
                  No questions match your filter.
                </td>
              </tr>
            ) : (
              filtered.map((q) => (
                <tr key={q.id} className="hover:bg-white/[0.03] transition-colors">
                  <td className="px-5 py-3.5 font-semibold text-emerald-300 font-mono text-xs">
                    {q.user?.username || 'Guest'}
                  </td>
                  <td className="px-5 py-3.5 space-y-1.5 max-w-sm">
                    {q.day?.continent && (
                      <div className="flex items-center gap-1.5">
                        <span className="inline-block text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-sky-400/10 text-sky-300 border border-sky-400/20">
                          {q.day.continent}{q.day.country?.name ? ` · ${q.day.country.name}` : ''}
                        </span>
                      </div>
                    )}
                    <div className="font-medium text-sand-100 text-sm">
                      "{q.original_question || q.question}"
                    </div>
                    {q.question && q.original_question && q.question !== q.original_question && (
                      <div className="text-[11px] text-emerald-300 font-mono bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-sm flex items-center gap-1.5">
                        <Sparkles size={11} className="text-emerald-400 shrink-0" />
                        <span>AI: "{q.question}"</span>
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {q.valid ? (
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${
                        q.answer ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-300 bg-rose-500/10 border-rose-500/30'
                      }`}>
                        {q.answer ? 'YES' : 'NO'}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-amber-300 bg-amber-500/10 border border-amber-500/30 text-xs font-semibold">
                        INVALID
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-sand-100/65 text-xs max-w-sm">{q.explanation || '-'}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-sand-100/55 text-xs">
                    {q.asked_at ? new Date(q.asked_at).toLocaleTimeString() : '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-3 justify-between items-center text-xs text-sand-100/65 font-mono">
        <span>Page {page} (Total: {totalQuestions})</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
            className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium border border-white/10"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={questions.length < 30}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium border border-white/10"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminQuestionsTab;
