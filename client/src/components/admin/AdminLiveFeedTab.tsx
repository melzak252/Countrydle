import React, { useEffect, useState } from 'react';
import {
  Clock,
  Filter,
  HelpCircle,
  Pause,
  Play,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-react';
import type { LiveFeedData } from '../../types';

interface AdminLiveFeedTabProps {
  data: LiveFeedData;
  isLoading: boolean;
  onRefresh: (mode?: string) => Promise<void>;
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
}

const MODES = [
  { id: 'all', label: 'All Modes' },
  { id: 'countrydle', label: 'Countries' },
  { id: 'powiatdle', label: 'Powiaty' },
  { id: 'us_statedle', label: 'US States' },
  { id: 'wojewodztwodle', label: 'Voivodeships' },
  { id: 'continental', label: 'Continental' },
];

const AUTO_REFRESH_INTERVALS = [
  { label: 'Off', seconds: 0 },
  { label: '10s', seconds: 10 },
  { label: '30s', seconds: 30 },
];

const MODE_COLORS: Record<string, string> = {
  countrydle: 'text-sky-300 bg-sky-400/10 border-sky-400/20',
  continental: 'text-teal-300 bg-teal-400/10 border-teal-400/20',
  powiatdle: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20',
  wojewodztwodle: 'text-purple-300 bg-purple-400/10 border-purple-400/20',
  us_statedle: 'text-amber-300 bg-amber-400/10 border-amber-400/20',
};

export const AdminLiveFeedTab: React.FC<AdminLiveFeedTabProps> = ({
  data,
  isLoading,
  onRefresh,
  onTestInQA,
}) => {
  const [selectedMode, setSelectedMode] = useState<string>('all');
  const [autoRefreshSecs, setAutoRefreshSecs] = useState<number>(10);

  // Polling effect
  useEffect(() => {
    if (autoRefreshSecs <= 0) return;
    const interval = setInterval(() => {
      onRefresh(selectedMode === 'all' ? undefined : selectedMode);
    }, autoRefreshSecs * 1000);
    return () => clearInterval(interval);
  }, [autoRefreshSecs, selectedMode, onRefresh]);

  const handleModeChange = async (mode: string) => {
    setSelectedMode(mode);
    await onRefresh(mode === 'all' ? undefined : mode);
  };

  return (
    <div className="space-y-6">
      {/* Mode Filters & Auto-Refresh Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-obsidian-900 border border-white/10 rounded-sm p-4">
        {/* Mode selector */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={15} className="text-sand-400" />
          <span className="text-xs uppercase font-mono tracking-wider text-sand-500 mr-1">Mode:</span>
          <div className="flex flex-wrap gap-1.5">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => handleModeChange(m.id)}
                className={`px-3 py-1 text-xs font-semibold rounded-sm border transition-all ${
                  selectedMode === m.id
                    ? 'bg-amber-400 text-obsidian-950 font-bold border-amber-400 shadow-sm'
                    : 'bg-obsidian-950 border-white/5 text-sand-300 hover:text-sand-100 hover:bg-white/5'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* Polling toggle & manual refresh */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Auto-refresh interval selector */}
          <div className="flex items-center bg-obsidian-950 border border-white/10 rounded-sm p-0.5 text-xs">
            <span className="text-[11px] text-sand-500 px-2 flex items-center gap-1 font-mono">
              <Clock className="w-3 h-3" />
              Auto:
            </span>
            {AUTO_REFRESH_INTERVALS.map((opt) => (
              <button
                key={opt.seconds}
                onClick={() => setAutoRefreshSecs(opt.seconds)}
                className={`px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
                  autoRefreshSecs === opt.seconds
                    ? 'bg-white/15 text-sand-100'
                    : 'text-sand-400 hover:text-sand-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => onRefresh(selectedMode === 'all' ? undefined : selectedMode)}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-obsidian-950 hover:bg-white/5 text-sand-200 rounded-sm border border-white/10 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
            <span>Update Now</span>
          </button>
        </div>
      </div>

      {/* Side-by-side feeds */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Real-Time Questions Feed */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 sm:p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-base font-bold text-sand-100 flex items-center gap-2">
              <HelpCircle size={18} className="text-amber-400" />
              <span>Real-Time Questions</span>
            </h2>
            <span className="text-xs text-sand-400 font-mono">
              {data.recent_questions.length} recent events
            </span>
          </div>

          <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
            {data.recent_questions.length === 0 ? (
              <p className="text-center py-12 text-xs text-sand-500 font-mono">
                No recent questions logged.
              </p>
            ) : (
              data.recent_questions.map((q) => (
                <div
                  key={q.id}
                  className="bg-obsidian-950 border border-white/5 hover:border-white/15 p-3 rounded-sm space-y-2 text-xs transition-colors"
                >
                  {/* Top Bar: Player, Mode, Target Entity, Timestamp */}
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-sand-200">{q.username}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded-sm text-[10px] font-mono border ${
                          MODE_COLORS[q.mode] || 'text-zinc-300 bg-white/5 border-white/10'
                        }`}
                      >
                        {q.mode}
                      </span>
                      {q.target_name && (
                        <span className="px-1.5 py-0.2 bg-amber-400/10 text-amber-300 border border-amber-400/25 rounded-sm text-[10px] font-semibold">
                          Target: {q.target_name}
                          {q.target_subtitle ? ` (${q.target_subtitle})` : ''}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-sand-500 font-mono flex-shrink-0">
                      {q.asked_at ? new Date(q.asked_at).toLocaleTimeString() : ''}
                    </span>
                  </div>

                  {/* Question Text */}
                  <div className="font-semibold text-sand-100 text-xs">
                    "{q.question}"
                  </div>

                  {/* Badges & Actions */}
                  <div className="flex items-center justify-between gap-2 flex-wrap pt-1 border-t border-white/5">
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Answer */}
                      {q.valid ? (
                        <span
                          className={`px-2 py-0.5 rounded-sm font-bold text-[10px] border ${
                            q.answer
                              ? 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30'
                              : 'text-rose-300 bg-rose-500/15 border-rose-500/30'
                          }`}
                        >
                          {q.answer ? 'YES' : 'NO'}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-sm text-amber-300 bg-amber-500/15 border border-amber-500/30 text-[10px] font-bold">
                          INVALID
                        </span>
                      )}

                      {/* Source Engine */}
                      {q.source === 'local_kb' ? (
                        <span className="px-2 py-0.5 rounded-sm text-[10px] font-medium bg-emerald-950 text-emerald-400 border border-emerald-800">
                          Local KB
                        </span>
                      ) : q.source === 'fallback' ? (
                        <span className="px-2 py-0.5 rounded-sm text-[10px] font-medium bg-indigo-950 text-indigo-400 border border-indigo-800">
                          AI Fallback
                        </span>
                      ) : null}
                    </div>

                    {/* QA Playground bridge button */}
                    {onTestInQA && (
                      <button
                        onClick={() =>
                          onTestInQA({
                            mode: q.mode,
                            targetName: q.target_name || undefined,
                            questionText: q.question,
                          })
                        }
                        className="text-[11px] text-sand-400 hover:text-amber-400 flex items-center gap-1 transition-colors"
                        title="Test in QA Playground"
                      >
                        <Sparkles className="w-3 h-3" />
                        <span>Test in QA</span>
                      </button>
                    )}
                  </div>

                  {/* Explanation */}
                  {q.explanation && (
                    <div className="text-[11px] text-sand-400 bg-obsidian-900/60 p-2 rounded-sm border border-white/5 leading-relaxed">
                      {q.explanation}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Real-Time Guesses Feed */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 sm:p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-base font-bold text-sand-100 flex items-center gap-2">
              <Target size={18} className="text-emerald-400" />
              <span>Real-Time Guesses</span>
            </h2>
            <span className="text-xs text-sand-400 font-mono">
              {data.recent_guesses.length} recent events
            </span>
          </div>

          <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
            {data.recent_guesses.length === 0 ? (
              <p className="text-center py-12 text-xs text-sand-500 font-mono">
                No recent guesses logged.
              </p>
            ) : (
              data.recent_guesses.map((g) => (
                <div
                  key={g.id}
                  className={`border p-3 rounded-sm space-y-2 text-xs transition-colors ${
                    g.answer
                      ? 'bg-emerald-950/30 border-emerald-500/30'
                      : 'bg-obsidian-950 border-white/5 hover:border-white/15'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-sand-200">{g.username}</span>
                      <span
                        className={`px-1.5 py-0.2 rounded-sm text-[10px] font-mono border ${
                          MODE_COLORS[g.mode] || 'text-zinc-300 bg-white/5 border-white/10'
                        }`}
                      >
                        {g.mode}
                      </span>
                      {g.target_name && (
                        <span className="px-1.5 py-0.2 bg-amber-400/10 text-amber-300 border border-amber-400/25 rounded-sm text-[10px] font-semibold">
                          Target: {g.target_name}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-sand-500 font-mono flex-shrink-0">
                      {g.guessed_at ? new Date(g.guessed_at).toLocaleTimeString() : ''}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-3 pt-1">
                    <div className="font-bold text-sand-100 text-sm">
                      "{g.guess}"
                    </div>

                    <div>
                      <span
                        className={`px-2.5 py-1 rounded-sm text-[11px] font-bold border ${
                          g.answer
                            ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                            : 'border-white/10 bg-white/5 text-sand-400'
                        }`}
                      >
                        {g.answer ? '🎯 Target Entity Solved' : '❌ Mistake / Miss'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminLiveFeedTab;
