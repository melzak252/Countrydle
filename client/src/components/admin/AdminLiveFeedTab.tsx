import React, { useState } from 'react';
import { HelpCircle, Target, Sparkles, RefreshCw, Filter } from 'lucide-react';

export interface LiveQuestionItem {
  id: number;
  mode: string;
  username: string;
  question: string;
  improved_question?: string | null;
  valid: boolean;
  answer?: boolean | null;
  explanation?: string | null;
  asked_at?: string | null;
}

export interface LiveGuessItem {
  id: number;
  mode: string;
  username: string;
  guess: string;
  answer: boolean;
  guessed_at?: string | null;
}

export interface LiveFeedData {
  recent_questions: LiveQuestionItem[];
  recent_guesses: LiveGuessItem[];
}

interface AdminLiveFeedTabProps {
  data: LiveFeedData;
  isLoading: boolean;
  onRefresh: (mode?: string) => Promise<void>;
}

const MODES = [
  { id: 'all', label: 'All Modes' },
  { id: 'countrydle', label: 'Countrydle' },
  { id: 'powiatdle', label: 'Powiatdle' },
  { id: 'wojewodztwodle', label: 'Województwa' },
  { id: 'us_statedle', label: 'US States' },
];

export const AdminLiveFeedTab: React.FC<AdminLiveFeedTabProps> = ({ data, isLoading, onRefresh }) => {
  const [selectedMode, setSelectedMode] = useState<string>('all');

  const handleModeChange = async (mode: string) => {
    setSelectedMode(mode);
    await onRefresh(mode === 'all' ? undefined : mode);
  };

  const getModeBadgeColor = (mode: string) => {
    switch (mode) {
      case 'countrydle':
        return 'text-sky-300 bg-sky-400/10 border-sky-400/20';
      case 'powiatdle':
        return 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20';
      case 'wojewodztwodle':
        return 'text-purple-300 bg-purple-400/10 border-purple-400/20';
      case 'us_statedle':
        return 'text-amber-300 bg-amber-400/10 border-amber-400/20';
      default:
        return 'text-zinc-300 bg-white/5 border-white/10';
    }
  };

  return (
    <div className="space-y-6 animate-message">
      {/* Mode Filters & Quick Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-sand-100/65" />
          <span className="text-xs uppercase font-mono tracking-wider text-sand-100/65 mr-2">Filter mode:</span>
          <div className="flex flex-wrap gap-1.5">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => handleModeChange(m.id)}
                className={`px-3 py-1 text-xs font-medium rounded-sm border transition-colors ${
                  selectedMode === m.id
                    ? 'bg-emerald-400/15 border-emerald-400/40 text-emerald-300'
                    : 'bg-obsidian-900 border-white/10 text-sand-100/70 hover:text-sand-100 hover:border-white/20'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onRefresh(selectedMode === 'all' ? undefined : selectedMode)}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 text-xs bg-obsidian-900 hover:bg-white/5 text-sand-100 rounded-sm border border-white/10 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          <span>Update Feed</span>
        </button>
      </div>

      {/* Side-by-side feeds */}
      <div className="min-w-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Questions Feed */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-lg font-semibold text-sand-100 flex items-center gap-2">
              <HelpCircle size={18} className="text-sand-100/80" />
              <span>Real-Time Questions</span>
            </h2>
            <span className="text-xs text-sand-100/55 font-mono">
              {data.recent_questions.length} items
            </span>
          </div>

          <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
            {data.recent_questions.length === 0 ? (
              <p className="text-center py-10 text-xs text-zinc-500 font-mono">No recent questions logged.</p>
            ) : (
              data.recent_questions.map((q) => (
                <div
                  key={q.id}
                  className="border-b border-white/10 pb-4 space-y-2 text-sm break-words"
                >
                  <div className="flex justify-between items-center text-sand-100/65 font-mono text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-emerald-300">{q.username}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-mono border ${getModeBadgeColor(q.mode)}`}>
                        {q.mode}
                      </span>
                    </div>
                    <span>{q.asked_at ? new Date(q.asked_at).toLocaleTimeString() : ''}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="font-medium text-sand-100 text-sm">
                      "{q.question}"
                    </div>
                    {q.improved_question && q.question && q.improved_question !== q.question && (
                      <div className="text-[11px] text-emerald-300 font-mono bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-sm flex items-center gap-1.5">
                        <Sparkles size={11} className="text-emerald-400 shrink-0" />
                        <span>AI plan: "{q.improved_question}"</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pt-1 text-xs">
                    {q.valid ? (
                      <span className={`px-2 py-0.5 rounded font-semibold border ${
                        q.answer ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-300 bg-rose-500/10 border-rose-500/30'
                      }`}>
                        {q.answer ? 'TAK / YES' : 'NIE / NO'}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-amber-300 bg-amber-500/10 border border-amber-500/30 font-semibold">
                        INVALID
                      </span>
                    )}
                    {q.explanation && (
                      <span className="text-sand-100/55 truncate" title={q.explanation}>{q.explanation}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Guesses Feed */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-lg font-semibold text-sand-100 flex items-center gap-2">
              <Target size={18} className="text-sand-100/80" />
              <span>Real-Time Guesses</span>
            </h2>
            <span className="text-xs text-sand-100/55 font-mono">
              {data.recent_guesses.length} items
            </span>
          </div>

          <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
            {data.recent_guesses.length === 0 ? (
              <p className="text-center py-10 text-xs text-zinc-500 font-mono">No recent guesses logged.</p>
            ) : (
              data.recent_guesses.map((g) => (
                <div
                  key={g.id}
                  className="border-b border-white/10 pb-4 space-y-2 text-sm flex flex-wrap justify-between items-center gap-3 break-words"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sand-100/65 font-mono text-xs">
                      <span className="font-semibold text-emerald-300">{g.username}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-mono border ${getModeBadgeColor(g.mode)}`}>
                        {g.mode}
                      </span>
                      <span>•</span>
                      <span>{g.guessed_at ? new Date(g.guessed_at).toLocaleTimeString() : ''}</span>
                    </div>
                    <div className="text-sm font-semibold text-sand-100">
                      {g.guess}
                    </div>
                  </div>

                  <div>
                    <span className={`px-2.5 py-1 rounded text-xs font-semibold border ${
                      g.answer
                        ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                        : 'border-white/10 bg-white/5 text-zinc-400'
                    }`}>
                      {g.answer ? '🎯 Solved / Hit' : '❌ Miss'}
                    </span>
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
