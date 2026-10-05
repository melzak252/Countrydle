import React, { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  FileText,
  Filter,
  HelpCircle,
  Info,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
  User as UserIcon,
  UserX,
  X,
  XCircle,
} from 'lucide-react';
import { adminService } from '../../services/api';
import type { AdminQuestionItem, AdminQuestionSource } from '../../types';

export interface AdminQuestionsTabProps {
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
  initialMode?: string;
  initialSearch?: string;
}

const MODES = [
  { key: 'all', label: 'All Modes' },
  { key: 'countrydle', label: 'Countries' },
  { key: 'powiatdle', label: 'Powiaty' },
  { key: 'us_statedle', label: 'US States' },
  { key: 'wojewodztwodle', label: 'Voivodeships' },
  { key: 'continental', label: 'Continental' },
];

const SOURCES: { key: string; label: string; color: string }[] = [
  { key: 'all', label: 'All Sources', color: 'text-sand-300' },
  { key: 'fallback', label: 'AI Fallback (LLM)', color: 'text-indigo-400' },
  { key: 'local_kb', label: 'Local KB (Deterministic)', color: 'text-emerald-400' },
  { key: 'invalid', label: 'Invalid / Rejected', color: 'text-amber-400' },
];

const ANSWERS = [
  { key: 'all', label: 'All Answers' },
  { key: 'yes', label: 'YES' },
  { key: 'no', label: 'NO' },
  { key: 'invalid', label: 'INVALID' },
];

export const AdminQuestionsTab: React.FC<AdminQuestionsTabProps> = ({
  onTestInQA,
  initialMode = 'all',
  initialSearch = '',
}) => {
  const [mode, setMode] = useState<string>(initialMode);
  const [search, setSearch] = useState<string>(initialSearch);
  const [debouncedSearch, setDebouncedSearch] = useState<string>(initialSearch);
  const [date, setDate] = useState<string>('');
  const [source, setSource] = useState<string>('all');
  const [answer, setAnswer] = useState<string>('all');
  const [hasReport, setHasReport] = useState<boolean | undefined>(undefined);
  const [page, setPage] = useState<number>(1);
  const limit = 30;

  // Data states
  const [items, setItems] = useState<AdminQuestionItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [expandedContexts, setExpandedContexts] = useState<Record<number, boolean>>({});

  // Remediation states
  const [invalidatingId, setInvalidatingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [mode, date, source, answer, hasReport]);

  const fetchQuestions = async () => {
    setIsLoading(true);
    try {
      const res = await adminService.getQuestions({
        mode: mode === 'all' ? undefined : mode,
        search: debouncedSearch.trim() || undefined,
        date: date || undefined,
        source: source === 'all' ? undefined : source,
        answer: answer === 'all' ? undefined : answer,
        has_report: hasReport,
        page,
        limit,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to fetch admin questions:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, [mode, debouncedSearch, date, source, answer, hasReport, page]);

  const handleInvalidate = async (item: AdminQuestionItem) => {
    if (!window.confirm(`Are you sure you want to invalidate and block the AI fallback answer for question #${item.id} on target '${item.target_name}'? This will remove the cached LLM answer.`)) {
      return;
    }
    setInvalidatingId(item.id);
    setActionMessage(null);
    try {
      const res = await adminService.invalidateQuestionFallback(item.mode, item.id);
      setActionMessage({ type: 'success', text: res.message || 'Cached answer invalidated successfully.' });
      await fetchQuestions();
    } catch (err: unknown) {
      let errMsg = 'Failed to invalidate fallback answer.';
      if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
        errMsg = err.response.data.detail;
      }
      setActionMessage({ type: 'error', text: errMsg });
    } finally {
      setInvalidatingId(null);
    }
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="space-y-6">
      {/* Action Notification Banner */}
      {actionMessage && (
        <div
          className={`p-3 rounded-sm text-xs flex items-center justify-between gap-3 border ${
            actionMessage.type === 'success'
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200'
              : 'bg-rose-950/60 border-rose-500/40 text-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-sand-400 hover:text-sand-200 text-xs p-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 1. Filter Controls & Search */}
      <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 space-y-4">
        {/* Search Bar + Date Presets */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-sand-400 w-4 h-4" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search question text, explanation, target entity, or username..."
              className="w-full bg-obsidian-950 border border-white/10 rounded-sm pl-9 pr-8 py-2 text-xs text-sand-100 placeholder:text-sand-500 focus:outline-none focus:border-amber-400"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-sand-500 hover:text-sand-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Date controls */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs">
              <Calendar className="w-3.5 h-3.5 text-sand-400" />
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="bg-transparent text-sand-100 text-xs focus:outline-none"
              />
            </div>
            {date && (
              <button
                onClick={() => setDate('')}
                className="text-[11px] text-amber-400 hover:underline px-1"
              >
                Clear Date
              </button>
            )}
            <button
              onClick={fetchQuestions}
              disabled={isLoading}
              className="p-2 bg-obsidian-950 hover:bg-white/5 text-sand-300 border border-white/10 rounded-sm transition-colors"
              title="Refresh questions"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Filter Pills: Mode, Source, Answer, Reported */}
        <div className="space-y-3 pt-2 border-t border-white/5 text-xs">
          {/* Modes */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] uppercase font-bold tracking-wider text-sand-500 mr-1">Mode:</span>
            {MODES.map((m) => (
              <button
                key={m.key}
                onClick={() => setMode(m.key)}
                className={`px-2.5 py-1 rounded-sm text-xs font-semibold transition-all ${
                  mode === m.key
                    ? 'bg-amber-400 text-obsidian-950 font-bold'
                    : 'bg-obsidian-950 text-sand-300 hover:bg-white/5 border border-white/5'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Source & Answer Filters */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 flex-wrap">
            {/* Source */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sand-500 mr-1">Source:</span>
              {SOURCES.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setSource(s.key)}
                  className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors border ${
                    source === s.key
                      ? 'bg-white/15 text-sand-100 border-white/20'
                      : `bg-obsidian-950 ${s.color} hover:bg-white/5 border-white/5`
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            {/* Answer & Anomaly */}
            <div className="flex items-center gap-3 flex-wrap">
              {/* Answer */}
              <div className="flex items-center bg-obsidian-950 border border-white/10 rounded-sm p-0.5">
                {ANSWERS.map((a) => (
                  <button
                    key={a.key}
                    onClick={() => setAnswer(a.key)}
                    className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
                      answer === a.key ? 'bg-white/15 text-sand-100' : 'text-sand-400 hover:text-sand-200'
                    }`}
                  >
                    {a.label}
                  </button>
                ))}
              </div>

              {/* High Risk / Reported Filter */}
              <button
                onClick={() => setHasReport(hasReport === true ? undefined : true)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-sm text-[11px] font-semibold border transition-all ${
                  hasReport === true
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-sm'
                    : 'bg-obsidian-950 text-sand-400 hover:text-rose-400 border-white/10'
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                <span>Reported Only</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Questions Audit Table */}
      <div className="bg-obsidian-900 border border-white/10 rounded-sm overflow-hidden">
        {/* Table summary bar */}
        <div className="px-4 py-3 bg-obsidian-950/60 border-b border-white/10 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sand-200">Questions Audit Log</span>
            <span className="text-sand-500">•</span>
            <span className="text-sand-400 font-mono">
              {total} {total === 1 ? 'record' : 'records'} matching criteria
            </span>
          </div>
          {isLoading && (
            <div className="flex items-center gap-1.5 text-amber-400 text-xs">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Querying...</span>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-obsidian-950 text-sand-400 border-b border-white/10 font-medium">
              <tr>
                <th className="px-4 py-2.5 min-w-[130px]">Target Entity</th>
                <th className="px-3 py-2.5 min-w-[100px]">Player</th>
                <th className="px-4 py-2.5 min-w-[280px]">Question Asked</th>
                <th className="px-3 py-2.5 min-w-[80px]">Answer</th>
                <th className="px-3 py-2.5 min-w-[140px]">Source Engine</th>
                <th className="px-4 py-2.5 min-w-[240px]">Explanation & Context</th>
                <th className="px-3 py-2.5 text-right min-w-[120px]">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading && items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-sand-400">
                    <Loader2 className="w-6 h-6 animate-spin text-amber-400 mx-auto mb-2" />
                    <span>Loading questions audit log...</span>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-sand-400 italic">
                    No questions match the selected filters.
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const isContextExpanded = !!expandedContexts[item.id];
                  const isInvalidating = invalidatingId === item.id;

                  return (
                    <tr key={item.id} className="hover:bg-white/[0.02] transition-colors group">
                      {/* Target Entity */}
                      <td className="px-4 py-3 align-top">
                        <div className="font-bold text-sand-100">{item.target_name}</div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[10px] text-amber-400/80 bg-amber-400/10 px-1.5 py-0.2 rounded-sm border border-amber-400/20 font-medium">
                            {item.target_subtitle || item.mode}
                          </span>
                        </div>
                        <div className="text-[10px] text-sand-500 font-mono mt-1">{item.game_date}</div>
                      </td>

                      {/* Player */}
                      <td className="px-3 py-3 align-top">
                        <div className="flex items-center gap-1 font-semibold text-sand-200">
                          {item.is_guest ? (
                            <UserX className="w-3.5 h-3.5 text-sand-400 flex-shrink-0" />
                          ) : (
                            <UserIcon className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                          )}
                          <span className="truncate max-w-[90px]" title={item.username}>
                            {item.username}
                          </span>
                        </div>
                        <div className="text-[10px] text-sand-500 mt-0.5">
                          {item.asked_at ? new Date(item.asked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                        </div>
                      </td>

                      {/* Question */}
                      <td className="px-4 py-3 align-top space-y-1">
                        <div className="font-semibold text-sand-100 text-xs leading-relaxed">
                          "{item.original_question}"
                        </div>
                        {item.question && item.question !== item.original_question && (
                          <div className="flex items-center gap-1 text-[11px] text-sand-400 font-mono bg-obsidian-950 p-1.5 rounded-sm border border-white/5">
                            <Sparkles className="w-3 h-3 text-amber-400 flex-shrink-0" />
                            <span>Rephrased: "{item.question}"</span>
                          </div>
                        )}
                      </td>

                      {/* Answer */}
                      <td className="px-3 py-3 align-top">
                        {item.valid ? (
                          <span
                            className={`px-2 py-0.5 rounded-sm text-[11px] font-bold border inline-block ${
                              item.answer === true
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            }`}
                          >
                            {item.answer === true ? 'YES' : 'NO'}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-sm text-[11px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 inline-block">
                            INVALID
                          </span>
                        )}
                      </td>

                      {/* Source Engine */}
                      <td className="px-3 py-3 align-top space-y-1">
                        <div>
                          {item.source === 'local_kb' ? (
                            <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                              Local KB {item.relation ? `· ${item.relation}` : ''}
                            </span>
                          ) : item.source === 'fallback' ? (
                            <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-semibold bg-indigo-950/80 text-indigo-300 border border-indigo-800">
                              AI Fallback (LLM)
                            </span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-800">
                              Invalid Question
                            </span>
                          )}
                        </div>

                        {item.has_report && (
                          <div>
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded-sm text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                              <ShieldAlert className="w-3 h-3" />
                              Reported #{item.report_id}
                            </span>
                          </div>
                        )}
                      </td>

                      {/* Explanation & Context */}
                      <td className="px-4 py-3 align-top space-y-2">
                        <div className="text-xs text-sand-300 leading-relaxed font-sans">
                          {item.explanation || <span className="text-sand-500 italic">No explanation recorded</span>}
                        </div>

                        {/* Raw Retrieved Context Drawer for Fallback */}
                        {item.context && (
                          <div>
                            <button
                              onClick={() =>
                                setExpandedContexts((prev) => ({
                                  ...prev,
                                  [item.id]: !prev[item.id],
                                }))
                              }
                              className="text-[11px] text-indigo-400 hover:text-indigo-300 font-mono flex items-center gap-1 transition-colors"
                            >
                              {isContextExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                              <span>{isContextExpanded ? 'Hide Raw Retrieved Context' : 'Inspect Retrieved Context'}</span>
                            </button>

                            {isContextExpanded && (
                              <div className="mt-1.5 p-2.5 bg-obsidian-950 rounded-sm border border-indigo-500/20 text-[11px] font-mono text-sand-300 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                                {item.context}
                              </div>
                            )}
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-3 py-3 align-top text-right space-y-1">
                        {/* Verify in QA */}
                        {onTestInQA && (
                          <button
                            onClick={() =>
                              onTestInQA({
                                mode: item.mode,
                                targetName: item.target_name,
                                questionText: item.original_question || item.question || '',
                              })
                            }
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-obsidian-950 hover:bg-amber-400/10 hover:text-amber-400 text-sand-300 rounded-sm border border-white/10 transition-colors text-[11px] font-medium"
                            title="Verify question in QA Playground"
                          >
                            <Sparkles className="w-3 h-3 text-amber-400" />
                            <span>Verify in QA</span>
                          </button>
                        )}

                        {/* Invalidate Fallback Cache */}
                        {item.source === 'fallback' && (
                          <div>
                            <button
                              disabled={isInvalidating}
                              onClick={() => handleInvalidate(item)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-obsidian-950 hover:bg-rose-500/10 hover:text-rose-400 text-sand-400 rounded-sm border border-white/10 transition-colors text-[11px] font-medium disabled:opacity-40"
                              title="Purge cached LLM answer and block false claim"
                            >
                              {isInvalidating ? (
                                <Loader2 className="w-3 h-3 animate-spin text-rose-400" />
                              ) : (
                                <Trash2 className="w-3 h-3 text-rose-400" />
                              )}
                              <span>Invalidate</span>
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 3. Server Pagination Controls */}
        {totalPages > 1 && (
          <div className="p-3 bg-obsidian-950 border-t border-white/10 flex items-center justify-between text-xs">
            <span className="text-sand-400">
              Page <b className="text-sand-200">{page}</b> of <b className="text-sand-200">{totalPages}</b>
            </span>

            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 bg-obsidian-900 hover:bg-white/5 disabled:opacity-40 text-sand-200 rounded-sm border border-white/10 transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1 bg-obsidian-900 hover:bg-white/5 disabled:opacity-40 text-sand-200 rounded-sm border border-white/10 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminQuestionsTab;
