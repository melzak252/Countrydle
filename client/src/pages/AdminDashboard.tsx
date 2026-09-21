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
    <div className="min-w-0 space-y-8 bg-obsidian-950 text-sand-100 [&_button]:focus-visible:outline [&_button]:focus-visible:outline-2 [&_button]:focus-visible:outline-offset-2 [&_button]:focus-visible:outline-emerald-300 [&_input]:focus-visible:outline-emerald-300 [&_select]:focus-visible:outline-emerald-300">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5 border-b border-white/10 pb-6">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-emerald-300 font-medium text-xs uppercase tracking-[0.18em]">
            <ShieldCheck size={16} />
            <span>Administrator</span>
          </div>
          <h1 className="font-serif text-3xl md:text-5xl text-sand-100 tracking-tight">
            Countrydle Admin Dashboard
          </h1>
          <p className="max-w-2xl text-sand-100/65 text-sm leading-relaxed">
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
            className="flex items-center gap-2 px-4 py-2.5 bg-obsidian-950 hover:bg-white/5 text-sand-100 hover:text-sand-100 rounded-sm text-xs md:text-sm font-semibold transition-colors border border-white/10"
          >
            <RefreshCw size={14} className={isOverviewLoading || isUsersLoading || isFeedLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-white/10 pb-4" aria-label="Admin sections">
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
              aria-pressed={isActive}
              className={`flex items-center gap-2 px-3 py-2 rounded-sm border font-medium text-sm transition-colors ${
                isActive
                  ? 'bg-emerald-400/10 border-emerald-400/30 text-emerald-300'
                  : 'bg-transparent border-transparent text-sand-100/65 hover:text-sand-100 hover:border-white/10'
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
        <div className="space-y-8">
          {/* Key Metric Hero Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
              <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
                <span>Challengers Today</span>
                <Users size={18} className="text-emerald-300" />
              </div>
              <div className="text-3xl md:text-4xl font-semibold text-sand-100">
                {overview?.today?.total_players ?? 0}
              </div>
              <p className="text-xs text-sand-100/55">Across all 4 game challenges</p>
            </div>

            <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
              <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
                <span>Questions Today</span>
                <HelpCircle size={18} className="text-sand-100/80" />
              </div>
              <div className="text-3xl md:text-4xl font-semibold text-sand-100/80">
                {overview?.today?.total_questions ?? 0}
              </div>
              <p className="text-xs text-sand-100/55">Deduction queries evaluated</p>
            </div>

            <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
              <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
                <span>Guesses Submitted</span>
                <Target size={18} className="text-sand-100/80" />
              </div>
              <div className="text-3xl md:text-4xl font-semibold text-sand-100/80">
                {overview?.today?.total_guesses ?? 0}
              </div>
              <p className="text-xs text-sand-100/55">Target attempts made</p>
            </div>

            <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
              <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
                <span>Today's Solve Rate</span>
                <Trophy size={18} className="text-emerald-300" />
              </div>
              <div className="text-3xl md:text-4xl font-semibold text-emerald-300">
                {overview?.today?.win_rate_pct ?? 0}%
              </div>
              <p className="text-xs text-sand-100/55">
                {overview?.today?.total_winners ?? 0} successful solvers
              </p>
            </div>
          </div>

          {/* Today's Mode-by-Mode Breakdown */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-sand-100 flex items-center gap-2">
              <Globe size={18} className="text-emerald-300" />
              <span>Today's Mode Breakdown &amp; Scheduled Targets</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {(overview?.modes_today || []).map((m: any) => (
                <div
                  key={m.mode_key}
                  className="bg-obsidian-900 border border-white/10 rounded-sm p-5 space-y-4 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-sand-100/65 uppercase tracking-wider">
                      {m.mode_label}
                    </div>
                    <div className="text-xl font-semibold text-sand-100">
                      {m.target_name}
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-white/10 text-xs">
                    <div className="flex justify-between text-sand-100/65">
                      <span>Players:</span>
                      <span className="font-semibold text-sand-100">{m.players}</span>
                    </div>
                    <div className="flex justify-between text-sand-100/65">
                      <span>Winners:</span>
                      <span className="font-semibold text-emerald-300">{m.winners} ({m.win_rate_pct}%)</span>
                    </div>
                    <div className="flex justify-between text-sand-100/65">
                      <span>Questions:</span>
                      <span className="font-semibold text-sand-100/80">{m.questions}</span>
                    </div>
                    <div className="flex justify-between text-sand-100/65">
                      <span>Guesses:</span>
                      <span className="font-semibold text-sand-100/80">{m.guesses}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 14-Day Historical Performance Table */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-sand-100 flex items-center gap-2">
              <Calendar size={18} className="text-sand-100/80" />
              <span>Past 14 Days Community Activity</span>
            </h2>

            <div className="bg-obsidian-900 border border-white/10 rounded-sm overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-xs md:text-sm">
                <thead className="bg-white/[0.03] text-sand-100/65 border-b border-white/10">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Date</th>
                    <th className="px-5 py-3 font-semibold text-right">Challengers</th>
                    <th className="px-5 py-3 font-semibold text-right">Solvers</th>
                    <th className="px-5 py-3 font-semibold">Win Rate</th>
                    <th className="px-5 py-3 font-semibold text-right">Questions</th>
                    <th className="px-5 py-3 font-semibold text-right">Guesses</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {(overview?.history_14d || []).map((h: any) => (
                    <tr key={h.date} className="hover:bg-white/[0.03] transition-colors">
                      <td className="px-5 py-3.5 font-mono text-sand-100/80 font-semibold">{h.date}</td>
                      <td className="px-5 py-3.5 text-right font-mono font-semibold text-sand-100">{h.total_players}</td>
                      <td className="px-5 py-3.5 text-right font-mono font-semibold text-emerald-300">{h.total_winners}</td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-obsidian-950 rounded-sm h-2 overflow-hidden">
                            <div
                              className="bg-emerald-400 h-2 rounded-sm"
                              style={{ width: `${Math.min(100, h.win_rate_pct)}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-sand-100/65">{h.win_rate_pct}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right font-mono text-sand-100/80">{h.total_questions}</td>
                      <td className="px-5 py-3.5 text-right font-mono text-sand-100/80">{h.total_guesses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Platform All-Time Totals */}
          <div className="p-5 md:p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-4">
            <h3 className="text-lg font-semibold text-sand-100">Platform Overall Telemetry</h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-xs md:text-sm">
              <div className="space-y-1">
                <div className="text-sand-100/55">Registered Users</div>
                <div className="text-2xl font-semibold text-sand-100">{overview?.totals?.total_users ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sand-100/55">Games Played</div>
                <div className="text-2xl font-semibold text-sand-100">{overview?.totals?.total_games ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sand-100/55">Questions Asked</div>
                <div className="text-2xl font-semibold text-sand-100/80">{overview?.totals?.total_questions ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sand-100/55">Guesses Submitted</div>
                <div className="text-2xl font-semibold text-sand-100/80">{overview?.totals?.total_guesses ?? 0}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sand-100/55">Daily Blog Recaps</div>
                <div className="text-2xl font-semibold text-emerald-300">{overview?.totals?.total_blog_posts ?? 0}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LIVE PLAYER FEED */}
      {activeTab === 'liveFeed' && (
        <div className="min-w-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Questions Feed */}
          <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h2 className="text-lg font-semibold text-sand-100 flex items-center gap-2">
                <HelpCircle size={18} className="text-sand-100/80" />
                <span>Real-Time Questions (Latest 35)</span>
              </h2>
              <span className="text-xs text-sand-100/55 font-mono">
                {liveFeed.recent_questions.length} items
              </span>
            </div>

            <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
              {liveFeed.recent_questions.map((q) => (
                <div
                  key={q.id}
                  className="border-b border-white/10 pb-4 space-y-2 text-sm break-words"
                >
                  <div className="flex justify-between items-center text-sand-100/65 font-mono">
                    <span className="font-semibold text-emerald-300">{q.username}</span>
                    <span>{q.asked_at ? new Date(q.asked_at).toLocaleTimeString('en-US') : ''}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="font-medium text-sand-100 text-sm">
                      "{q.original_question || q.question}"
                    </div>
                    {q.improved_question && q.original_question && q.improved_question !== q.original_question && (
                      <div className="text-[11px] text-emerald-300 font-mono bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-sm flex items-center gap-1.5">
                        <Sparkles size={11} className="text-emerald-400 shrink-0" />
                        <span>AI: "{q.improved_question}"</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    {q.valid ? (
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        q.answer ? 'text-emerald-300' : 'text-red-400'
                      }`}>
                        Answer: {q.answer ? 'YES' : 'NO'}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-sand-100/80 text-xs font-semibold">
                        INVALID / TYPO
                      </span>
                    )}
                    {q.explanation && (
                      <span className="text-sand-100/55 truncate">{q.explanation}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Guesses Feed */}
          <div className="bg-obsidian-900 border border-white/10 rounded-sm min-w-0 p-4 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h2 className="text-lg font-semibold text-sand-100 flex items-center gap-2">
                <Target size={18} className="text-sand-100/80" />
                <span>Real-Time Guesses (Latest 35)</span>
              </h2>
              <span className="text-xs text-sand-100/55 font-mono">
                {liveFeed.recent_guesses.length} items
              </span>
            </div>

            <div className="space-y-3 max-h-[650px] overflow-y-auto custom-scrollbar pr-1">
              {liveFeed.recent_guesses.map((g) => (
                <div
                  key={g.id}
                  className="border-b border-white/10 pb-4 space-y-2 text-sm flex flex-wrap justify-between items-center gap-3 break-words"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sand-100/65 font-mono">
                      <span className="font-semibold text-emerald-300">{g.username}</span>
                      <span>•</span>
                      <span>{g.guessed_at ? new Date(g.guessed_at).toLocaleTimeString('en-US') : ''}</span>
                    </div>
                    <div className="text-sm font-semibold text-sand-100">
                      {g.guess}
                    </div>
                  </div>

                  <div>
                    {g.answer ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1 text-emerald-300 font-semibold rounded-sm text-xs">
                        <CheckCircle2 size={14} />
                        <span>CORRECT</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-3 py-1 text-red-400 font-semibold rounded-sm text-xs">
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
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sand-100/55" size={16} />
              <input
                type="text"
                aria-label="Search users by username or email"
                value={userSearch}
                onChange={(e) => {
                  setUserSearch(e.target.value);
                  setUserPage(1);
                }}
                placeholder="Search username or email..."
                className="w-full pl-10 pr-4 py-2.5 bg-obsidian-900 border border-white/10 rounded-sm text-sand-100 text-xs md:text-sm focus:outline-none focus:border-emerald-400 transition-colors"
              />
            </div>
            <div className="text-xs text-sand-100/65 font-mono">
              Total registered: {usersData.total} users
            </div>
          </div>

          <div className="bg-obsidian-900 border border-white/10 rounded-sm overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-xs md:text-sm">
              <thead className="bg-white/[0.03] text-sand-100/65 border-b border-white/10">
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
              <tbody className="divide-y divide-white/10">
                {usersData.users.map((u) => (
                  <tr key={u.id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="px-5 py-3.5 font-semibold text-sand-100">{u.username}</td>
                    <td className="px-5 py-3.5 text-sand-100/65 font-mono text-xs">{u.email}</td>
                    <td className="px-5 py-3.5 text-sand-100/55 font-mono text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('en-US') : '-'}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-semibold text-sand-100/80">{u.total_points}</td>
                    <td className="px-5 py-3.5 text-right font-mono font-semibold text-emerald-300">{u.total_wins}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-sand-100/80">{u.games_played}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-sand-100/80 flex items-center justify-end gap-1">
                      <span>{u.current_streak}</span>
                      <Flame size={12} className="text-emerald-300" />
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      {u.is_admin ? (
                        <span className="text-emerald-300 text-xs font-medium">
                          ADMIN
                        </span>
                      ) : (
                        <span className="text-sand-100/55 text-xs">Player</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex flex-wrap gap-3 justify-between items-center text-xs text-sand-100/65">
            <span>Page {userPage}</span>
            <div className="flex gap-2">
              <button
                disabled={userPage <= 1}
                onClick={() => setUserPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium"
              >
                Previous
              </button>
              <button
                disabled={usersData.users.length < 25}
                onClick={() => setUserPage((p) => p + 1)}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: QUESTIONS LOG */}
      {activeTab === 'questions' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Mode Switcher */}
            <div className="flex flex-wrap gap-2">
              {[
                { id: 'countrydle', label: 'Countries' },
                { id: 'us_statedle', label: 'US States' },
                { id: 'powiatdle', label: 'Counties' },
                { id: 'wojewodztwodle', label: 'Voivodeships' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => {
                    setQuestionsMode(m.id as GameType);
                    setQuestionPage(1);
                  }}
                  aria-pressed={questionsMode === m.id}
                  className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors ${
                    questionsMode === m.id
                      ? 'bg-emerald-400/10 text-emerald-300 border border-emerald-400/30'
                      : 'bg-obsidian-900 text-sand-100/65 hover:text-sand-100 border border-white/10'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sand-100/55" size={15} />
              <input
                type="text"
                aria-label="Filter questions or explanations"
                value={questionSearch}
                onChange={(e) => setQuestionSearch(e.target.value)}
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
                {filteredQuestions.map((q) => (
                  <tr key={q.id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="px-5 py-3.5 font-semibold text-emerald-300">{q.user?.username || 'Guest'}</td>
                    <td className="px-5 py-3.5 space-y-1.5 max-w-sm">
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
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          q.answer ? 'text-emerald-300' : 'text-red-400'
                        }`}>
                          {q.answer ? 'YES' : 'NO'}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-sand-100/80 text-xs font-semibold">
                          INVALID
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-sand-100/65 text-xs max-w-sm">{q.explanation || '-'}</td>
                    <td className="px-5 py-3.5 text-right font-mono text-sand-100/55 text-xs">
                      {q.asked_at ? new Date(q.asked_at).toLocaleTimeString('en-US') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap gap-3 justify-between items-center text-xs text-sand-100/65">
            <span>Page {questionPage} (Total: {totalQuestions})</span>
            <div className="flex gap-2">
              <button
                disabled={questionPage <= 1}
                onClick={() => setQuestionPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium"
              >
                Previous
              </button>
              <button
                disabled={questions.length < 30}
                onClick={() => setQuestionPage((p) => p + 1)}
                className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: KNOWLEDGE BASE FACT EDITOR */}
      {activeTab === 'facts' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-2">
              {[
                { id: 'countrydle', label: 'Countries (SQLite)' },
                { id: 'us_statedle', label: 'US States (SQLite)' },
                { id: 'powiatdle', label: 'Counties (SQLite)' },
                { id: 'wojewodztwodle', label: 'Voivodeships (SQLite)' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setFactMode(m.id as GameType)}
                  aria-pressed={factMode === m.id}
                  className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors ${
                    factMode === m.id
                      ? 'bg-emerald-400/10 text-emerald-300 border border-emerald-400/30'
                      : 'bg-obsidian-900 text-sand-100/65 hover:text-sand-100 border border-white/10'
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
                  setSelectedEntityId(id);
                  const selected = factEntities.find((item) => item.id === id);
                  fetchEntityFacts(selected?.name || id);
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
                          onChange={(e) => setFactInputs({ ...factInputs, [fact.relation]: e.target.value })}
                          className="min-w-0 flex-1 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs"
                        />
                        <button
                          aria-label={`Save ${fact.relation.replace(/_/g, ' ')}`}
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
                          className="px-2.5 py-1 bg-emerald-400/10 hover:bg-emerald-400/20 text-sand-100 font-semibold rounded-sm text-xs"
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

                <p className="text-xs leading-relaxed text-sand-100/65">Changes are saved immediately. <span className="text-red-300">Deleting a value removes it from the knowledge base.</span></p>
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
                              aria-label={`Delete ${v.value} from ${listFact.relation.replace(/_/g, ' ')}`}
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
                              className="p-1 text-red-400 hover:text-red-300 transition-colors"
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
                          onChange={(e) => setNewListValues({ ...newListValues, [listFact.relation]: e.target.value })}
                          placeholder={`Add new ${listFact.relation.replace(/_/g, ' ')}...`}
                          className="min-w-0 flex-1 bg-obsidian-950 border border-white/10 rounded-sm px-2.5 py-1 text-sand-100 text-xs"
                        />
                        <button
                          aria-label={`Add ${listFact.relation.replace(/_/g, ' ')} value`}
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
                          className="px-3 py-1 bg-emerald-400/10 hover:bg-emerald-400/20 text-sand-100 font-semibold rounded-sm text-xs flex items-center gap-1"
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
