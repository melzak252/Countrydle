import React, { useEffect, useState } from 'react';
import {
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  HelpCircle,
  Loader2,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  User as UserIcon,
  UserX,
  XCircle,
} from 'lucide-react';
import { adminService } from '../../services/api';
import type {
  AdminGameSessionItem,
  AdminTargetStrategyStats,
} from '../../types';

interface AdminSessionsTabProps {
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
}

const MODES = [
  { key: 'countrydle', label: 'World Countries' },
  { key: 'powiatdle', label: 'Polish Counties' },
  { key: 'us_statedle', label: 'US States' },
  { key: 'wojewodztwodle', label: 'Voivodeships' },
  { key: 'continental', label: 'Continental' },
];

function formatDuration(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function formatTime(isoString?: string | null): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoString;
  }
}

export const AdminSessionsTab: React.FC<AdminSessionsTabProps> = ({ onTestInQA }) => {
  const [selectedMode, setSelectedMode] = useState<string>('countrydle');
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [playerTypeFilter, setPlayerTypeFilter] = useState<string>('all');
  const [page, setPage] = useState<number>(1);
  const limit = 20;

  // Data states
  const [sessions, setSessions] = useState<AdminGameSessionItem[]>([]);
  const [totalSessions, setTotalSessions] = useState<number>(0);
  const [stats, setStats] = useState<AdminTargetStrategyStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [sessionsRes, statsRes] = await Promise.all([
        adminService.getGameSessions({
          mode: selectedMode,
          date: selectedDate,
          status: statusFilter,
          player_type: playerTypeFilter,
          page,
          limit,
        }),
        adminService.getTargetStrategyStats({
          mode: selectedMode,
          date: selectedDate,
        }),
      ]);

      setSessions(sessionsRes.items);
      setTotalSessions(sessionsRes.total);
      setStats(statsRes);
    } catch (err) {
      console.error('Failed to fetch admin game sessions data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setPage(1);
  }, [selectedMode, selectedDate, statusFilter, playerTypeFilter]);

  useEffect(() => {
    fetchData();
  }, [selectedMode, selectedDate, statusFilter, playerTypeFilter, page]);

  const handleDatePreset = (offsetDays: number) => {
    const d = new Date();
    d.setDate(d.getDate() - offsetDays);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const toggleSession = (sessionId: string) => {
    setExpandedSessions((prev) => ({
      ...prev,
      [sessionId]: !prev[sessionId],
    }));
  };

  const totalPages = Math.ceil(totalSessions / limit) || 1;

  return (
    <div className="space-y-6">
      {/* 1. Header: Mode & Date Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-obsidian-900 p-4 rounded-sm border border-white/10">
        {/* Mode selector */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => setSelectedMode(m.key)}
              className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-all ${
                selectedMode === m.key
                  ? 'bg-amber-400 text-obsidian-950 shadow-sm'
                  : 'bg-obsidian-950 text-sand-300 hover:bg-white/5 border border-white/5'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Date presets & picker */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleDatePreset(0)}
            className="px-2.5 py-1.5 text-xs bg-obsidian-950 hover:bg-white/5 text-sand-300 border border-white/10 rounded-sm font-medium"
          >
            Today
          </button>
          <button
            onClick={() => handleDatePreset(1)}
            className="px-2.5 py-1.5 text-xs bg-obsidian-950 hover:bg-white/5 text-sand-300 border border-white/10 rounded-sm font-medium"
          >
            Yesterday
          </button>
          <div className="flex items-center gap-1.5 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs">
            <Calendar className="w-3.5 h-3.5 text-sand-400" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-transparent text-sand-100 text-xs focus:outline-none"
            />
          </div>
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="p-1.5 bg-obsidian-950 hover:bg-white/5 text-sand-300 border border-white/10 rounded-sm transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 2. Target Banner */}
      <div className="bg-obsidian-900 border border-white/10 rounded-sm p-5 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-full bg-gradient-to-l from-amber-400/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-sand-400 bg-obsidian-950 px-2 py-0.5 rounded-sm border border-white/10">
                Secret Target Entity
              </span>
              {stats?.target_subtitle && (
                <span className="text-[10px] font-semibold text-amber-400/80 bg-amber-400/10 px-2 py-0.5 rounded-sm border border-amber-400/20">
                  {stats.target_subtitle}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold text-sand-100 flex items-center gap-2">
              <Target className="w-6 h-6 text-amber-400" />
              {stats?.target_name || 'Loading...'}
            </h2>
            <p className="text-xs text-sand-400 mt-0.5">
              Challenge puzzle for date <span className="text-sand-200 font-medium">{stats?.game_date || selectedDate}</span>
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-obsidian-950 border border-white/5 rounded-sm p-3 min-w-[110px]">
              <div className="text-[11px] text-sand-400 font-medium">Total Players</div>
              <div className="text-lg font-bold text-sand-100 mt-0.5">{stats?.total_players ?? 0}</div>
            </div>
            <div className="bg-obsidian-950 border border-white/5 rounded-sm p-3 min-w-[110px]">
              <div className="text-[11px] text-sand-400 font-medium">Solve Rate</div>
              <div className="text-lg font-bold text-emerald-400 mt-0.5">{stats?.win_rate_pct ?? 0}%</div>
            </div>
            <div className="bg-obsidian-950 border border-white/5 rounded-sm p-3 min-w-[110px]">
              <div className="text-[11px] text-sand-400 font-medium">Avg Qs (Win)</div>
              <div className="text-lg font-bold text-sand-200 mt-0.5">{stats?.avg_questions_winners ?? 0}</div>
            </div>
            <div className="bg-obsidian-950 border border-white/5 rounded-sm p-3 min-w-[110px]">
              <div className="text-[11px] text-sand-400 font-medium">Avg Qs (Loss)</div>
              <div className="text-lg font-bold text-sand-400 mt-0.5">{stats?.avg_questions_losers ?? 0}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Deductive Strategy & Insights Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Top Questions Card */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-sand-100 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-amber-400" />
                Top Deductive Questions
              </h3>
              <span className="text-[11px] text-sand-400">Asked frequency & win correlation</span>
            </div>

            {stats && stats.top_questions.length > 0 ? (
              <div className="space-y-2">
                {stats.top_questions.slice(0, 6).map((q, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-obsidian-950 border border-white/5 rounded-sm flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-sand-100 font-medium truncate" title={q.text}>
                        "{q.text}"
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[11px] text-sand-400">
                        <span>Asked: <b className="text-sand-200">{q.count}x</b></span>
                        <span>•</span>
                        <span className="text-emerald-400 font-medium">YES: {q.yes_pct}%</span>
                        <span>•</span>
                        <span className="text-amber-400 font-medium">Win Rate: {q.win_correlation}%</span>
                      </div>
                    </div>
                    {onTestInQA && (
                      <button
                        onClick={() =>
                          onTestInQA({
                            mode: selectedMode,
                            targetName: stats.target_name,
                            questionText: q.text,
                          })
                        }
                        className="p-1.5 text-sand-400 hover:text-amber-400 hover:bg-white/5 rounded-sm transition-colors border border-transparent hover:border-white/10"
                        title="Test in QA Playground"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-sand-400">
                No question deduction data recorded for this target yet.
              </div>
            )}
          </div>
        </div>

        {/* Top Guesses Card */}
        <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-sand-100 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Player Guess Patterns
              </h3>
              <span className="text-[11px] text-sand-400">Target matches vs mistaken entities</span>
            </div>

            {stats && stats.top_guesses.length > 0 ? (
              <div className="space-y-2">
                {stats.top_guesses.slice(0, 6).map((g, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-obsidian-950 border border-white/5 rounded-sm flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {g.correct_pct > 0 ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-4 h-4 text-sand-500 flex-shrink-0" />
                      )}
                      <span className="text-sand-100 font-medium truncate">{g.guess}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-sand-400">{g.count} guesses</span>
                      {g.correct_pct > 0 ? (
                        <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-sm font-semibold border border-emerald-500/20">
                          TARGET
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 bg-white/5 text-sand-400 rounded-sm font-medium">
                          Mistake
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-sand-400">
                No player guesses recorded for this target yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Player Sessions Explorer */}
      <div className="bg-obsidian-900 border border-white/10 rounded-sm p-4 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-sand-100">Player Sessions & Chronological Replay</h3>
            <span className="px-2 py-0.5 bg-obsidian-950 text-sand-400 text-xs rounded-sm border border-white/10 font-mono">
              {totalSessions} {totalSessions === 1 ? 'session' : 'sessions'}
            </span>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap text-xs">
            {/* Status Filter */}
            <div className="flex items-center bg-obsidian-950 border border-white/10 rounded-sm p-0.5">
              {['all', 'won', 'lost', 'in_progress'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-sm text-[11px] font-medium capitalize transition-colors ${
                    statusFilter === st ? 'bg-white/15 text-sand-100' : 'text-sand-400 hover:text-sand-200'
                  }`}
                >
                  {st.replace('_', ' ')}
                </button>
              ))}
            </div>

            {/* Player Type */}
            <div className="flex items-center bg-obsidian-950 border border-white/10 rounded-sm p-0.5">
              {[
                { key: 'all', label: 'All Players' },
                { key: 'registered', label: 'Users' },
                { key: 'guest', label: 'Guests' },
              ].map((pt) => (
                <button
                  key={pt.key}
                  onClick={() => setPlayerTypeFilter(pt.key)}
                  className={`px-2.5 py-1 rounded-sm text-[11px] font-medium transition-colors ${
                    playerTypeFilter === pt.key ? 'bg-white/15 text-sand-100' : 'text-sand-400 hover:text-sand-200'
                  }`}
                >
                  {pt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sessions List */}
        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center gap-2 text-sand-400">
            <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
            <span className="text-xs">Loading player session logs...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="py-12 text-center text-xs text-sand-400 bg-obsidian-950/50 rounded-sm border border-dashed border-white/10">
            No player sessions found matching the selected filters.
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((sess) => {
              const isExpanded = !!expandedSessions[sess.session_id];

              return (
                <div
                  key={sess.session_id}
                  className="bg-obsidian-950 border border-white/10 rounded-sm overflow-hidden transition-all"
                >
                  {/* Session Card Header */}
                  <div
                    onClick={() => toggleSession(sess.session_id)}
                    className="p-3.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded-sm bg-obsidian-900 border border-white/10 text-sand-300">
                        {sess.is_guest ? <UserX className="w-4 h-4 text-sand-400" /> : <UserIcon className="w-4 h-4 text-amber-400" />}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-sand-100 truncate">{sess.username}</span>
                          {sess.is_guest && (
                            <span className="text-[10px] px-1.5 py-0.2 bg-white/5 text-sand-400 rounded-sm border border-white/10 font-mono">
                              Guest
                            </span>
                          )}
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-sm uppercase tracking-wide border ${
                              sess.status === 'won'
                                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                : sess.status === 'lost'
                                ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                                : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                            }`}
                          >
                            {sess.status.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-sand-400 mt-0.5">
                          <span>{sess.questions_asked} Qs</span>
                          <span>•</span>
                          <span>{sess.guesses_made} Guesses</span>
                          {sess.duration_seconds != null && (
                            <>
                              <span>•</span>
                              <span className="flex items-center gap-1 text-sand-300">
                                <Clock className="w-3 h-3 text-sand-400" />
                                {formatDuration(sess.duration_seconds)}
                              </span>
                            </>
                          )}
                          {sess.started_at && (
                            <>
                              <span>•</span>
                              <span>Started {formatTime(sess.started_at)}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-sand-400">
                      <span className="text-xs hidden sm:inline text-sand-400">
                        {isExpanded ? 'Hide replay' : 'Replay session'}
                      </span>
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                  </div>

                  {/* Expanded Chronological Timeline Replay */}
                  {isExpanded && (
                    <div className="p-4 border-t border-white/10 bg-obsidian-900/60 space-y-3">
                      <div className="text-xs font-bold text-sand-300 flex items-center justify-between pb-2 border-b border-white/5">
                        <span>Chronological Deduction Timeline ({sess.timeline.length} events)</span>
                        <span className="text-[11px] text-sand-500 font-normal">Ordered by execution time</span>
                      </div>

                      {sess.timeline.length === 0 ? (
                        <div className="py-4 text-center text-xs text-sand-400 italic">
                          No logged questions or guesses in this session timeline.
                        </div>
                      ) : (
                        <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-white/10">
                          {sess.timeline.map((ev, evIdx) => (
                            <div key={ev.id + '-' + evIdx} className="relative group">
                              {/* Step indicator node */}
                              <div
                                className={`absolute -left-6 top-1 w-4 h-4 rounded-full border-2 flex items-center justify-center text-[9px] font-bold ${
                                  ev.event_type === 'guess'
                                    ? ev.correct
                                      ? 'bg-emerald-500 border-emerald-300 text-obsidian-950'
                                      : 'bg-rose-500 border-rose-300 text-obsidian-950'
                                    : 'bg-obsidian-950 border-amber-400 text-amber-400'
                                }`}
                              >
                                {evIdx + 1}
                              </div>

                              {/* Question Event Card */}
                              {ev.event_type === 'question' ? (
                                <div className="bg-obsidian-950 p-3 rounded-sm border border-white/10 space-y-2">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                                      <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-sm bg-obsidian-900 text-sand-400 border border-white/10">
                                        Question
                                      </span>
                                      {/* Answer Badge */}
                                      {ev.valid ? (
                                        <span
                                          className={`text-[10px] font-bold px-2 py-0.5 rounded-sm ${
                                            ev.answer === true
                                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                              : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                          }`}
                                        >
                                          {ev.answer === true ? 'YES' : 'NO'}
                                        </span>
                                      ) : (
                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-sm bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                          INVALID
                                        </span>
                                      )}

                                      {/* Engine Source Badge */}
                                      {ev.source === 'local_kb' ? (
                                        <span className="text-[10px] px-2 py-0.5 rounded-sm bg-emerald-950 text-emerald-400 border border-emerald-800 font-medium">
                                          Local KB {ev.relation ? `(${ev.relation})` : ''}
                                        </span>
                                      ) : ev.source === 'fallback' ? (
                                        <span className="text-[10px] px-2 py-0.5 rounded-sm bg-indigo-950 text-indigo-400 border border-indigo-800 font-medium">
                                          AI Fallback (LLM)
                                        </span>
                                      ) : (
                                        <span className="text-[10px] px-2 py-0.5 rounded-sm bg-amber-950 text-amber-400 border border-amber-800 font-medium">
                                          Invalid Question
                                        </span>
                                      )}
                                    </div>

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                      {ev.timestamp && (
                                        <span className="text-[10px] text-sand-500">{formatTime(ev.timestamp)}</span>
                                      )}
                                      {onTestInQA && (
                                        <button
                                          onClick={() =>
                                            onTestInQA({
                                              mode: sess.mode,
                                              targetName: sess.target_name,
                                              questionText: ev.original_question || ev.question || '',
                                            })
                                          }
                                          className="text-[11px] text-sand-400 hover:text-amber-400 flex items-center gap-1 transition-colors"
                                          title="Test in QA Playground"
                                        >
                                          <Sparkles className="w-3 h-3" />
                                          <span className="hidden sm:inline">QA Test</span>
                                        </button>
                                      )}
                                    </div>
                                  </div>

                                  <div className="text-xs font-semibold text-sand-100">
                                    "{ev.original_question || ev.question}"
                                  </div>

                                  {ev.explanation && (
                                    <div className="text-xs text-sand-300 bg-obsidian-900/60 p-2 rounded-sm border border-white/5 leading-relaxed">
                                      <span className="text-sand-400 font-medium">AI explanation: </span>
                                      {ev.explanation}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                /* Guess Event Card */
                                <div
                                  className={`p-3 rounded-sm border flex items-center justify-between gap-3 text-xs ${
                                    ev.correct
                                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-100'
                                      : 'bg-obsidian-950 border-white/10 text-sand-300'
                                  }`}
                                >
                                  <div className="flex items-center gap-2.5 min-w-0">
                                    <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-sm bg-obsidian-900 text-sand-400 border border-white/10">
                                      Guess
                                    </span>
                                    <span className="font-bold text-sm text-sand-100 truncate">
                                      "{ev.guess}"
                                    </span>
                                    {ev.correct ? (
                                      <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded-sm border border-emerald-500/30">
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                        VICTORY (Target Entity Found)
                                      </span>
                                    ) : (
                                      <span className="flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-sm border border-rose-500/20">
                                        <XCircle className="w-3.5 h-3.5" />
                                        Incorrect
                                      </span>
                                    )}
                                  </div>
                                  {ev.timestamp && (
                                    <span className="text-[10px] text-sand-500 flex-shrink-0">
                                      {formatTime(ev.timestamp)}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-3 border-t border-white/10 text-xs">
            <span className="text-sand-400">
              Page <b className="text-sand-200">{page}</b> of <b className="text-sand-200">{totalPages}</b>
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 text-sand-200 rounded-sm border border-white/10 transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 text-sand-200 rounded-sm border border-white/10 transition-colors"
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

export default AdminSessionsTab;
