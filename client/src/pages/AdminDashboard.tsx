import { useState, useEffect, useMemo } from 'react';
import { 
  adminService, 
  gameService, 
  powiatService, 
  usStateService, 
  wojewodztwoService,
  type CountryFactsResponse 
} from '../services/api';
import { 
  Users, 
  HelpCircle, 
  Target, 
  Trophy, 
  Calendar, 
  Search, 
  RefreshCw, 
  Globe, 
  Database, 
  Activity, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  ShieldCheck, 
  Flame, 
  FileText, 
  Plus, 
  Trash2, 
  Sparkles
} from 'lucide-react';

type AdminTab = 'overview' | 'liveFeed' | 'users' | 'questions' | 'facts';
type GameType = 'countrydle' | 'us_statedle' | 'powiatdle' | 'wojewodztwodle';

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [overview, setOverview] = useState<any | null>(null);
  const [isOverviewLoading, setIsOverviewLoading] = useState(true);

  // Users State
  const [usersData, setUsersData] = useState<{ total: number; users: any[] }>({ total: 0, users: [] });
  const [userSearch, setUserSearch] = useState('');
  const [userPage, setUserPage] = useState(1);
  const [isUsersLoading, setIsUsersLoading] = useState(false);

  // Live Feed State
  const [liveFeed, setLiveFeed] = useState<{ recent_questions: any[]; recent_guesses: any[] }>({ recent_questions: [], recent_guesses: [] });
  const [isFeedLoading, setIsFeedLoading] = useState(false);

  // Questions Log State
  const [questionsMode, setQuestionsMode] = useState<GameType>('countrydle');
  const [questions, setQuestions] = useState<any[]>([]);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [questionPage, setQuestionPage] = useState(1);
  const [questionSearch, setQuestionSearch] = useState('');

  // Facts Editor State
  // Facts Editor State
  const [factMode, setFactMode] = useState<GameType>('countrydle');
  const [factEntities, setFactEntities] = useState<any[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
  const [entityFacts, setEntityFacts] = useState<CountryFactsResponse | null>(null);
  const [factInputs, setFactInputs] = useState<Record<string, any>>({});
  const [newListValues, setNewListValues] = useState<Record<string, string>>({});
  const [factError, setFactError] = useState<string | null>(null);
  // Fetch Overview Data
  const fetchOverview = async () => {
    setIsOverviewLoading(true);
    try {
      const data = await adminService.getOverview();
      setOverview(data);
    } catch (err) {
      console.error('Failed to load admin overview:', err);
    } finally {
      setIsOverviewLoading(false);
    }
  };

  // Fetch Users
  const fetchUsers = async () => {
    setIsUsersLoading(true);
    try {
      const data = await adminService.getUsers(userPage, 25, userSearch);
      setUsersData(data);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setIsUsersLoading(false);
    }
  };

  // Fetch Live Feed
  const fetchLiveFeed = async () => {
    setIsFeedLoading(true);
    try {
      const data = await adminService.getLiveFeed();
      setLiveFeed(data);
    } catch (err) {
      console.error('Failed to load live feed:', err);
    } finally {
      setIsFeedLoading(false);
    }
  };

  // Fetch Questions
  const fetchQuestions = async () => {
    try {
      const limit = 30;
      const offset = (questionPage - 1) * limit;
      let data = { items: [] as any[], total: 0 };
      if (questionsMode === 'countrydle') data = await adminService.getCountrydleQuestions(limit, offset);
      else if (questionsMode === 'us_statedle') data = await adminService.getUSStatedleQuestions(limit, offset);
      else if (questionsMode === 'powiatdle') data = await adminService.getPowiatdleQuestions(limit, offset);
      else if (questionsMode === 'wojewodztwodle') data = await adminService.getWojewodztwodleQuestions(limit, offset);

      setQuestions(data.items || []);
      setTotalQuestions(data.total || 0);
    } catch (err) {
      console.error('Failed to load questions log:', err);
    }
  };

  // Facts Editor helpers
  const fetchFactEntities = async () => {
    try {
      setFactError(null);
      let list: any[] = [];
      if (factMode === 'countrydle') list = await gameService.getCountries();
      else if (factMode === 'us_statedle') list = await usStateService.getStates();
      else if (factMode === 'powiatdle') list = (await powiatService.getPowiaty()).map((p: any) => ({ id: p.id, name: p.nazwa || p.name }));
      else if (factMode === 'wojewodztwodle') list = (await wojewodztwoService.getWojewodztwa()).map((w: any) => ({ id: w.id, name: w.nazwa || w.name }));

      setFactEntities(list);
      if (list.length > 0) {
        setSelectedEntityId(list[0].id);
        fetchEntityFacts(list[0].name || list[0].id);
      }
    } catch (err: any) {
      setFactError(err.message || 'Failed to load entities');
    }
  };

  const fetchEntityFacts = async (idOrName: number | string) => {
    try {
      const facts = await adminService.getCountryFacts(idOrName, factMode);
      setEntityFacts(facts);
      setFactInputs(Object.fromEntries((facts.scalar_facts || []).map((f) => [f.relation, f.value ?? ''])));
    } catch (err: any) {
      setFactError(err.message || 'Failed to load facts');
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  useEffect(() => {
    if (activeTab === 'users') fetchUsers();
  }, [activeTab, userPage, userSearch]);

  useEffect(() => {
    if (activeTab === 'liveFeed') fetchLiveFeed();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'questions') fetchQuestions();
  }, [activeTab, questionsMode, questionPage]);

  useEffect(() => {
    if (activeTab === 'facts') fetchFactEntities();
  }, [activeTab, factMode]);

  const filteredQuestions = useMemo(() => {
    if (!questionSearch.trim()) return questions;
    const q = questionSearch.toLowerCase();
    return questions.filter((item) => 
      (item.original_question || item.question || '').toLowerCase().includes(q) ||
      (item.explanation || '').toLowerCase().includes(q) ||
      (item.user?.username || '').toLowerCase().includes(q)
    );
  }, [questions, questionSearch]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 md:py-12 space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-zinc-900 border border-zinc-800 rounded-3xl p-6 md:p-8 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-red-400 font-bold text-xs uppercase tracking-wider">
            <ShieldCheck size={16} />
            <span>Mission Control • Administrator</span>
          </div>
          <h1 className="text-2xl md:text-4xl font-black text-white tracking-tight">
            Countrydle Admin Dashboard
          </h1>
          <p className="text-zinc-400 text-xs md:text-sm">
            Live gameplay monitoring, community solve metrics, user directory, and factual knowledge base.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (activeTab === 'overview') fetchOverview();
              else if (activeTab === 'users') fetchUsers();
              else if (activeTab === 'liveFeed') fetchLiveFeed();
              else if (activeTab === 'questions') fetchQuestions();
            }}
            className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white rounded-xl text-xs md:text-sm font-semibold transition-all border border-zinc-700/60 shadow-sm"
          >
            <RefreshCw size={14} className={isOverviewLoading || isUsersLoading || isFeedLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex overflow-x-auto gap-2 pb-2 border-b border-zinc-800">
        {[
          { id: 'overview', label: 'Today & Analytics', icon: Activity },
          { id: 'liveFeed', label: 'Live Player Feed', icon: Clock },
          { id: 'users', label: 'User Directory', icon: Users },
          { id: 'questions', label: 'Questions Log', icon: HelpCircle },
          { id: 'facts', label: 'Knowledge Base Editor', icon: Database },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as AdminTab)}
              className={`flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs md:text-sm transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                  : 'bg-zinc-900 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
              }`}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW & TODAY'S STATS */}
      {activeTab === 'overview' && (
        <div className="space-y-8 animate-in fade-in duration-300">
          {/* Key Metric Hero Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <span>Challengers Today</span>
                <Users size={18} className="text-blue-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-white">
                {overview?.today?.total_players ?? 0}
              </div>
              <p className="text-xs text-zinc-500">Across all 4 game challenges</p>
            </div>

            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <span>Questions Today</span>
                <HelpCircle size={18} className="text-yellow-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-yellow-400">
                {overview?.today?.total_questions ?? 0}
              </div>
              <p className="text-xs text-zinc-500">Deduction queries evaluated</p>
            </div>

            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <span>Guesses Submitted</span>
                <Target size={18} className="text-teal-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-teal-400">
                {overview?.today?.total_guesses ?? 0}
              </div>
              <p className="text-xs text-zinc-500">Target attempts made</p>
            </div>

            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                <span>Today's Solve Rate</span>
                <Trophy size={18} className="text-green-400" />
              </div>
              <div className="text-3xl md:text-4xl font-black text-green-400">
                {overview?.today?.win_rate_pct ?? 0}%
              </div>
              <p className="text-xs text-zinc-500">
                {overview?.today?.total_winners ?? 0} successful solvers
              </p>
            </div>
          </div>

          {/* Today's Mode-by-Mode Breakdown */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Globe size={18} className="text-blue-400" />
              <span>Today's Mode Breakdown &amp; Scheduled Targets</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {(overview?.modes_today || []).map((m: any) => (
                <div
                  key={m.mode_key}
                  className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-lg space-y-4 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                      {m.mode_label}
                    </div>
                    <div className="text-xl font-black text-white">
                      {m.target_name}
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-zinc-800 text-xs">
                    <div className="flex justify-between text-zinc-400">
                      <span>Players:</span>
                      <span className="font-bold text-white">{m.players}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Winners:</span>
                      <span className="font-bold text-green-400">{m.winners} ({m.win_rate_pct}%)</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Questions:</span>
                      <span className="font-bold text-yellow-400">{m.questions}</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Guesses:</span>
                      <span className="font-bold text-teal-400">{m.guesses}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 14-Day Historical Performance Table */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Calendar size={18} className="text-teal-400" />
              <span>Past 14 Days Community Activity</span>
            </h2>

            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
              <table className="w-full text-left text-xs md:text-sm">
                <thead className="bg-zinc-800/60 text-zinc-400 border-b border-zinc-800">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Date</th>
                    <th className="px-5 py-3 font-semibold text-right">Challengers</th>
                    <th className="px-5 py-3 font-semibold text-right">Solvers</th>
                    <th className="px-5 py-3 font-semibold">Win Rate</th>
                    <th className="px-5 py-3 font-semibold text-right">Questions</th>
                    <th className="px-5 py-3 font-semibold text-right">Guesses</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/80">
                  {(overview?.history_14d || []).map((h: any) => (
                    <tr key={h.date} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="px-5 py-3.5 font-mono text-zinc-300 font-bold">{h.date}</td>
                      <td className="px-5 py-3.5 text-right font-mono font-bold text-white">{h.total_players}</td>
                      <td className="px-5 py-3.5 text-right font-mono font-bold text-green-400">{h.total_winners}</td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-zinc-800 rounded-full h-2 overflow-hidden">
                            <div
                              className="bg-green-500 h-2 rounded-full"
                              style={{ width: `${Math.min(100, h.win_rate_pct)}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-zinc-400">{h.win_rate_pct}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right font-mono text-yellow-400">{h.total_questions}</td>
                      <td className="px-5 py-3.5 text-right font-mono text-teal-400">{h.total_guesses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Platform All-Time Totals */}
          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-3xl space-y-4">
            <h3 className="text-lg font-bold text-white">Platform Overall Telemetry</h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-xs md:text-sm">
              <div className="space-y-1">
                <div className="text-zinc-500">Registered Users</div>
                <div className="text-2xl font-black text-white">{overview?.totals?.total_users ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-zinc-500">Games Played</div>
                <div className="text-2xl font-black text-white">{overview?.totals?.total_games ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-zinc-500">Questions Asked</div>
                <div className="text-2xl font-black text-yellow-400">{overview?.totals?.total_questions ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-zinc-500">Guesses Submitted</div>
                <div className="text-2xl font-black text-teal-400">{overview?.totals?.total_guesses ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-zinc-500">Daily Blog Recaps</div>
                <div className="text-2xl font-black text-blue-400">{overview?.totals?.total_blog_posts ?? 0}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LIVE PLAYER FEED */}
      {activeTab === 'liveFeed' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-300">
          {/* Questions Feed */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <HelpCircle size={18} className="text-yellow-400" />
                <span>Real-Time Questions (Latest 35)</span>
              </h2>
              <span className="text-xs text-zinc-500 font-mono">
                {liveFeed.recent_questions.length} items
              </span>
            </div>

            <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
              {liveFeed.recent_questions.map((q) => (
                <div
                  key={q.id}
                  className="p-3.5 bg-zinc-800/40 border border-zinc-800 rounded-xl space-y-1.5 text-xs"
                >
                  <div className="flex justify-between items-center text-zinc-400 font-mono">
                    <span className="font-bold text-blue-400">{q.username}</span>
                    <span>{q.asked_at ? new Date(q.asked_at).toLocaleTimeString() : ''}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="font-medium text-white text-sm">
                      "{q.original_question || q.question}"
                    </div>
                    {q.improved_question && q.original_question && q.improved_question !== q.original_question && (
                      <div className="text-[11px] text-teal-300 font-mono bg-teal-500/10 border border-teal-500/20 px-2 py-0.5 rounded-md flex items-center gap-1.5">
                        <Sparkles size={11} className="text-teal-400 shrink-0" />
                        <span>AI: "{q.improved_question}"</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    {q.valid ? (
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        q.answer ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        Answer: {q.answer ? 'YES' : 'NO'}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] font-bold">
                        INVALID / TYPO
                      </span>
                    )}
                    {q.explanation && (
                      <span className="text-zinc-500 truncate">{q.explanation}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Guesses Feed */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Target size={18} className="text-teal-400" />
                <span>Real-Time Guesses (Latest 35)</span>
              </h2>
              <span className="text-xs text-zinc-500 font-mono">
                {liveFeed.recent_guesses.length} items
              </span>
            </div>

            <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
              {liveFeed.recent_guesses.map((g) => (
                <div
                  key={g.id}
                  className="p-3.5 bg-zinc-800/40 border border-zinc-800 rounded-xl space-y-1.5 text-xs flex justify-between items-center"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-zinc-400 font-mono">
                      <span className="font-bold text-blue-400">{g.username}</span>
                      <span>•</span>
                      <span>{g.guessed_at ? new Date(g.guessed_at).toLocaleTimeString() : ''}</span>
                    </div>
                    <div className="text-sm font-bold text-white">
                      {g.guess}
                    </div>
                  </div>

                  <div>
                    {g.answer ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-500/20 text-green-400 font-bold rounded-lg text-xs">
                        <CheckCircle2 size={14} />
                        <span>CORRECT</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-500/20 text-red-400 font-bold rounded-lg text-xs">
                        <XCircle size={14} />
                        <span>WRONG</span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: USER DIRECTORY */}
      {activeTab === 'users' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
              <input
                type="text"
                value={userSearch}
                onChange={(e) => {
                  setUserSearch(e.target.value);
                  setUserPage(1);
                }}
                placeholder="Search username or email..."
                className="w-full pl-10 pr-4 py-2.5 bg-zinc-900 border border-zinc-800 rounded-xl text-white text-xs md:text-sm focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="text-xs text-zinc-400 font-mono">
              Total registered: {usersData.total} users
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
            <table className="w-full text-left text-xs md:text-sm">
              <thead className="bg-zinc-800/60 text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="px-5 py-3 font-semibold">User</th>
                  <th className="px-5 py-3 font-semibold">Email</th>
                  <th className="px-5 py-3 font-semibold">Registered</th>
                  <th className="px-5 py-3 font-semibold text-right">Points</th>
                  <th className="px-5 py-3 font-semibold text-right">Wins</th>
                  <th className="px-5 py-3 font-semibold text-right">Games</th>
                  <th className="px-5 py-3 font-semibold text-right">Streak</th>
                  <th className="px-5 py-3 font-semibold text-center">Role</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/80">
                {usersData.users.map((u) => (
                  <tr key={u.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-5 py-3.5 font-bold text-white">{u.username}</td>
                    <td className="px-5 py-3.5 text-zinc-400 font-mono text-xs">{u.email}</td>
                    <td className="px-5 py-3.5 text-zinc-500 font-mono text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-yellow-500">{u.total_points}</td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-green-400">{u.total_wins}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-zinc-300">{u.games_played}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-amber-400 flex items-center justify-end gap-1">
                      <span>{u.current_streak}</span>
                      <Flame size={12} className="text-amber-500" />
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      {u.is_admin ? (
                        <span className="px-2 py-0.5 rounded bg-red-900/30 text-red-400 border border-red-800/50 text-[10px] font-bold">
                          ADMIN
                        </span>
                      ) : (
                        <span className="text-zinc-600 text-[10px]">Player</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex justify-between items-center text-xs text-zinc-400">
            <span>Page {userPage}</span>
            <div className="flex gap-2">
              <button
                disabled={userPage <= 1}
                onClick={() => setUserPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded-lg text-white font-medium"
              >
                Previous
              </button>
              <button
                disabled={usersData.users.length < 25}
                onClick={() => setUserPage((p) => p + 1)}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded-lg text-white font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: QUESTIONS LOG */}
      {activeTab === 'questions' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Mode Switcher */}
            <div className="flex gap-2">
              {[
                { id: 'countrydle', label: 'Countries' },
                { id: 'us_statedle', label: 'US States' },
                { id: 'powiatdle', label: 'Powiaty' },
                { id: 'wojewodztwodle', label: 'Voivodeships' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => {
                    setQuestionsMode(m.id as GameType);
                    setQuestionPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    questionsMode === m.id
                      ? 'bg-zinc-200 text-zinc-900'
                      : 'bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={15} />
              <input
                type="text"
                value={questionSearch}
                onChange={(e) => setQuestionSearch(e.target.value)}
                placeholder="Filter questions or explanations..."
                className="w-full pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
            <table className="w-full text-left text-xs md:text-sm">
              <thead className="bg-zinc-800/60 text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="px-5 py-3 font-semibold">User</th>
                  <th className="px-5 py-3 font-semibold">Question Asked</th>
                  <th className="px-5 py-3 font-semibold">Status / Answer</th>
                  <th className="px-5 py-3 font-semibold">Explanation</th>
                  <th className="px-5 py-3 font-semibold text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/80">
                {filteredQuestions.map((q) => (
                  <tr key={q.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-5 py-3.5 font-bold text-blue-400">{q.user?.username || 'Guest'}</td>
                    <td className="px-5 py-3.5 space-y-1.5 max-w-sm">
                      <div className="font-medium text-white text-sm">
                        "{q.original_question || q.question}"
                      </div>
                      {q.question && q.original_question && q.question !== q.original_question && (
                        <div className="text-[11px] text-teal-300 font-mono bg-teal-500/10 border border-teal-500/20 px-2 py-0.5 rounded-md flex items-center gap-1.5">
                          <Sparkles size={11} className="text-teal-400 shrink-0" />
                          <span>AI: "{q.question}"</span>
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {q.valid ? (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          q.answer ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {q.answer ? 'YES' : 'NO'}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] font-bold">
                          INVALID
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-zinc-400 text-xs max-w-sm">{q.explanation || '-'}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-zinc-500 text-xs">
                      {q.asked_at ? new Date(q.asked_at).toLocaleTimeString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between items-center text-xs text-zinc-400">
            <span>Page {questionPage} (Total: {totalQuestions})</span>
            <div className="flex gap-2">
              <button
                disabled={questionPage <= 1}
                onClick={() => setQuestionPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded-lg text-white font-medium"
              >
                Previous
              </button>
              <button
                disabled={questions.length < 30}
                onClick={() => setQuestionPage((p) => p + 1)}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 rounded-lg text-white font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: KNOWLEDGE BASE FACT EDITOR */}
      {activeTab === 'facts' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex gap-2">
              {[
                { id: 'countrydle', label: 'Countries (SQLite)' },
                { id: 'us_statedle', label: 'US States (SQLite)' },
                { id: 'powiatdle', label: 'Powiaty (SQLite)' },
                { id: 'wojewodztwodle', label: 'Voivodeships (SQLite)' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setFactMode(m.id as GameType)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    factMode === m.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {/* Select Destination Entity */}
            <div className="w-full sm:w-72">
              <select
                value={selectedEntityId || ''}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  setSelectedEntityId(id);
                  const selected = factEntities.find((item) => item.id === id);
                  fetchEntityFacts(selected?.name || id);
                }}
                className="w-full bg-zinc-900 border border-zinc-800 text-white rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-blue-500"
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
            <div className="p-4 bg-red-900/20 border border-red-500/40 rounded-xl text-red-400 text-xs">
              {factError}
            </div>
          )}

          {entityFacts && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Scalar Facts Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Database size={16} className="text-blue-400" />
                  <span>Scalar Facts: {entityFacts.country.name}</span>
                </h3>

                <div className="space-y-3 max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
                  {(entityFacts.scalar_facts || []).map((fact) => (
                    <div key={fact.relation} className="p-3 bg-zinc-800/40 rounded-xl space-y-1.5 text-xs">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-zinc-300 capitalize">{fact.relation.replace(/_/g, ' ')}</span>
                        <span className="text-[10px] text-zinc-500 font-mono">{fact.value_type}</span>
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={factInputs[fact.relation] ?? ''}
                          onChange={(e) => setFactInputs({ ...factInputs, [fact.relation]: e.target.value })}
                          className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1 text-white text-xs"
                        />
                        <button
                          onClick={async () => {
                            try {
                              await adminService.updateCountryScalarFact(
                                entityFacts.country.id,
                                fact.relation,
                                factInputs[fact.relation],
                                undefined,
                                factMode
                              );
                              fetchEntityFacts(entityFacts.country.id);
                            } catch (e: any) {
                              setFactError(e.message || 'Failed to update fact');
                            }
                          }}
                          className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg text-xs"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* List Facts Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <FileText size={16} className="text-teal-400" />
                  <span>List / Multi-Value Facts</span>
                </h3>

                <div className="space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar pr-1">
                  {(entityFacts.list_facts || []).map((listFact) => (
                    <div key={listFact.relation} className="p-4 bg-zinc-800/40 rounded-xl space-y-3 text-xs">
                      <div className="font-bold text-zinc-200 capitalize">
                        {listFact.relation.replace(/_/g, ' ')} ({listFact.values.length})
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {listFact.values.map((v) => (
                          <span
                            key={v.value}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs"
                          >
                            <span>{v.value}</span>
                            <button
                              onClick={async () => {
                                try {
                                  await adminService.deleteCountryListFact(
                                    entityFacts.country.id,
                                    listFact.relation,
                                    v.value,
                                    undefined,
                                    factMode
                                  );
                                  fetchEntityFacts(entityFacts.country.id);
                                } catch (e: any) {
                                  setFactError(e.message || 'Failed to delete');
                                }
                              }}
                              className="text-zinc-500 hover:text-red-400 transition-colors"
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
                          onChange={(e) => setNewListValues({ ...newListValues, [listFact.relation]: e.target.value })}
                          placeholder={`Add new ${listFact.relation.replace(/_/g, ' ')}...`}
                          className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1 text-white text-xs"
                        />
                        <button
                          onClick={async () => {
                            const val = newListValues[listFact.relation]?.trim();
                            if (!val) return;
                            try {
                              await adminService.addCountryListFact(
                                entityFacts.country.id,
                                listFact.relation,
                                val,
                                {},
                                undefined,
                                factMode
                              );
                              setNewListValues({ ...newListValues, [listFact.relation]: '' });
                              fetchEntityFacts(entityFacts.country.id);
                            } catch (e: any) {
                              setFactError(e.message || 'Failed to add');
                            }
                          }}
                          className="px-3 py-1 bg-green-600 hover:bg-green-500 text-white font-bold rounded-lg text-xs flex items-center gap-1"
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
      )}
    </div>
  );
}
