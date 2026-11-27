import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import AnswerReportsPanel from '../components/AnswerReportsPanel';
import TemplateDivergencesPanel from '../components/admin/TemplateDivergencesPanel';
import FriendAnswerReviewsPanel from '../components/FriendAnswerReviewsPanel';
import QuestionTestsPanel from '../components/QuestionTestsPanel';
import CacheStatsPanel from '../components/CacheStatsPanel';
import AdminOverviewTab, { type AdminOverviewData } from '../components/admin/AdminOverviewTab';
import AdminSessionsTab from '../components/admin/AdminSessionsTab';
import AdminLiveFeedTab from '../components/admin/AdminLiveFeedTab';
import AdminCountrydleCostsTab from '../components/admin/AdminCountrydleCostsTab';
import AdminUsersTab, { type AdminUserRecord } from '../components/admin/AdminUsersTab';
import AdminQuestionsTab from '../components/admin/AdminQuestionsTab';
import AdminFactsTab, { type EntityOption } from '../components/admin/AdminFactsTab';
import AdminSuggestionsTab from '../components/admin/AdminSuggestionsTab';
import AdminBlogTab from '../components/admin/AdminBlogTab';
import type { QuestionTestBridgeTarget } from '../components/QuestionTestsPanel';
import type { AnswerReport, AnswerReportMode, LiveFeedData } from '../types';
import {
  adminService,
  gameService,
  powiatService,
  usStateService,
  wojewodztwoService,
  type CountryFactsResponse,
} from '../services/api';
import {
  Activity,
  Database,
  Play,
  ShieldCheck,
  Sliders,
} from 'lucide-react';

type AdminTab =
  | 'overview'
  | 'sessions'
  | 'liveFeed'
  | 'questions'
  | 'facts'
  | 'reports'
  | 'questionTests'
  | 'blogs'
  | 'templateDivergences'
  | 'friendAnswers'
  | 'suggestions'
  | 'users'
  | 'aiCosts'
  | 'cache';

type AdminGroupId = 'overview' | 'games' | 'facts' | 'quality' | 'system';

interface SubTab {
  id: AdminTab;
  label: string;
  description: string;
}

interface AdminGroup {
  id: AdminGroupId;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  tabs: SubTab[];
}

const GROUPS: AdminGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: Activity,
    tabs: [
      {
        id: 'overview',
        label: 'Overview',
        description: 'Completed games, finishers, win rates, and daily targets across all modes.',
      },
    ],
  },
  {
    id: 'games',
    label: 'Games & Activity',
    icon: Play,
    tabs: [
      { id: 'sessions', label: 'Sessions', description: 'Completed player sessions and full Q&A timelines.' },
      { id: 'liveFeed', label: 'Live Feed', description: 'Most recent questions and guesses across modes.' },
      { id: 'questions', label: 'Questions Log', description: 'Searchable archive of player questions and answers.' },
    ],
  },
  {
    id: 'facts',
    label: 'Facts Editor',
    icon: Database,
    tabs: [
      { id: 'facts', label: 'Facts Editor', description: 'Inspect and edit local SQLite facts for countries, counties, voivodeships, and US states.' },
    ],
  },
  {
    id: 'quality',
    label: 'Quality & Content',
    icon: ShieldCheck,
    tabs: [
      { id: 'reports', label: 'Answer Reports', description: 'Review player-flagged answers and test them in QA.' },
      { id: 'questionTests', label: 'QA Tester', description: 'Run live question plans against any target entity.' },
      { id: 'blogs', label: 'Daily Blogs', description: 'Edit daily recaps and manage publication review.' },
      { id: 'templateDivergences', label: 'Divergences', description: 'Compare fast template answers against planner outputs.' },
      { id: 'friendAnswers', label: 'Friend Answers', description: 'Review disputed answers in friend duels.' },
      { id: 'suggestions', label: 'Suggestions', description: 'Player feedback and feature requests.' },
    ],
  },
  {
    id: 'system',
    label: 'Users & System',
    icon: Sliders,
    tabs: [
      { id: 'users', label: 'Users', description: 'Search registered accounts and inspect activity.' },
      { id: 'aiCosts', label: 'AI Costs', description: 'Measured daily Gemini and fallback spend for Countrydle.' },
      { id: 'cache', label: 'Cache', description: 'Inspect and manage planner and answer caches.' },
    ],
  },
];

const ALL_TABS: SubTab[] = GROUPS.flatMap((g) => g.tabs);

function groupForTab(tabId: AdminTab): AdminGroup {
  return GROUPS.find((g) => g.tabs.some((t) => t.id === tabId)) ?? GROUPS[0];
}

function requestError(error: unknown): string {
  if (isAxiosError(error)) {
    return typeof error.response?.data?.detail === 'string'
      ? error.response.data.detail
      : 'Request failed. Please retry.';
  }
  return error instanceof Error ? error.message : 'Request failed. Please retry.';
}

export default function AdminDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const activeTab: AdminTab = ALL_TABS.find((t) => t.id === requestedTab)?.id ?? 'overview';
  const activeGroup = groupForTab(activeTab);
  const activeSubTab = ALL_TABS.find((t) => t.id === activeTab) ?? ALL_TABS[0];

  const setActiveTab = (tab: AdminTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', tab);
    setSearchParams(next);
  };

  const setSessionFilters = (mode: string, date: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', 'sessions');
    next.set('mode', mode);
    next.set('date', date);
    setSearchParams(next);
  };

  const [questionTestReport, setQuestionTestReport] = useState<AnswerReport | null>(null);
  const [qaBridgeTarget, setQaBridgeTarget] = useState<QuestionTestBridgeTarget | null>(null);
  const focusQA = useRef(false);

  const handleTestInQA = (target: QuestionTestBridgeTarget) => {
    setQuestionTestReport(null);
    setQaBridgeTarget(target);
    focusQA.current = true;
    setActiveTab('questionTests');
  };

  const mounted = useRef(true);
  const currentTab = useRef(activeTab);
  currentTab.current = activeTab;
  const overviewRequest = useRef(0);
  const usersRequest = useRef(0);
  const feedRequest = useRef(0);
  const entitiesRequest = useRef(0);
  const factsRequest = useRef(0);

  const [overview, setOverview] = useState<AdminOverviewData | null>(null);
  const [isOverviewLoading, setIsOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [usersData, setUsersData] = useState<{ total: number; users: AdminUserRecord[] }>({ total: 0, users: [] });
  const [userSearch, setUserSearch] = useState('');
  const [userPage, setUserPage] = useState(1);
  const [isUsersLoading, setIsUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);
  const usersQuery = `${userPage}:${userSearch}`;
  const currentUsersQuery = useRef(usersQuery);
  currentUsersQuery.current = usersQuery;
  const [loadedUsersQuery, setLoadedUsersQuery] = useState<string | null>(null);

  const [liveFeed, setLiveFeed] = useState<LiveFeedData>({ recent_questions: [], recent_guesses: [] });
  const [isFeedLoading, setIsFeedLoading] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [feedHasLoaded, setFeedHasLoaded] = useState(false);
  const [feedUpdatedAt, setFeedUpdatedAt] = useState<string | null>(null);
  const feedMode = useRef<string | undefined>(undefined);
  const pendingFeed = useRef<{ mode: string | undefined; promise: Promise<void> } | null>(null);

  const [factMode, setFactMode] = useState<AnswerReportMode>('countrydle');
  const currentFactMode = useRef(factMode);
  currentFactMode.current = factMode;
  const [factEntities, setFactEntities] = useState<EntityOption[]>([]);
  const currentFactEntities = useRef<EntityOption[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
  const currentEntity = useRef(selectedEntityId);
  currentEntity.current = selectedEntityId;
  const [entityFacts, setEntityFacts] = useState<CountryFactsResponse | null>(null);
  const [factInputs, setFactInputs] = useState<Record<string, string>>({});
  const [newListValues, setNewListValues] = useState<Record<string, string>>({});
  const [factError, setFactError] = useState<string | null>(null);
  const [isEntitiesLoading, setIsEntitiesLoading] = useState(false);
  const [isFactsLoading, setIsFactsLoading] = useState(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      overviewRequest.current++;
      usersRequest.current++;
      feedRequest.current++;
      entitiesRequest.current++;
      factsRequest.current++;
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'questionTests' && focusQA.current) {
      document.getElementById('admin-page-title')?.focus();
      focusQA.current = false;
    }
  }, [activeTab, qaBridgeTarget, questionTestReport]);

  const fetchOverview = useCallback(async () => {
    const request = ++overviewRequest.current;
    setIsOverviewLoading(true);
    setOverviewError(null);
    try {
      const data: AdminOverviewData = await adminService.getOverview();
      if (mounted.current && request === overviewRequest.current && currentTab.current === 'overview') {
        setOverview(data);
      }
    } catch (error) {
      if (mounted.current && request === overviewRequest.current && currentTab.current === 'overview') {
        setOverviewError(requestError(error));
      }
    } finally {
      if (mounted.current && request === overviewRequest.current) setIsOverviewLoading(false);
    }
  }, []);

  const fetchUsers = useCallback(async () => {
    const request = ++usersRequest.current;
    const query = `${userPage}:${userSearch}`;
    const applies = () =>
      mounted.current &&
      request === usersRequest.current &&
      currentUsersQuery.current === query &&
      currentTab.current === 'users';
    setIsUsersLoading(true);
    setUsersError(null);
    try {
      const data: { total: number; users: AdminUserRecord[] } = await adminService.getUsers(userPage, 25, userSearch);
      if (applies()) {
        setUsersData(data);
        setLoadedUsersQuery(query);
      }
    } catch (error) {
      if (applies()) {
        setUsersData({ total: 0, users: [] });
        setLoadedUsersQuery(query);
        setUsersError(requestError(error));
      }
    } finally {
      if (applies()) setIsUsersLoading(false);
    }
  }, [userPage, userSearch]);

  const fetchLiveFeed = useCallback((mode?: string): Promise<void> => {
    if (pendingFeed.current && pendingFeed.current.mode === mode) return pendingFeed.current.promise;
    const request = ++feedRequest.current;
    if (feedMode.current !== mode) {
      setLiveFeed({ recent_questions: [], recent_guesses: [] });
      setFeedHasLoaded(false);
      setFeedUpdatedAt(null);
    }
    feedMode.current = mode;
    setIsFeedLoading(true);
    setFeedError(null);
    const applies = () =>
      mounted.current && request === feedRequest.current && currentTab.current === 'liveFeed';
    const promise = (async () => {
      try {
        const data = await adminService.getLiveFeed(mode);
        if (applies()) {
          setLiveFeed(data);
          setFeedHasLoaded(true);
          setFeedUpdatedAt(new Date().toISOString());
        }
      } catch (error) {
        if (applies()) setFeedError(requestError(error));
      } finally {
        if (applies()) setIsFeedLoading(false);
        if (request === feedRequest.current) pendingFeed.current = null;
      }
    })();
    pendingFeed.current = { mode, promise };
    return promise;
  }, []);

  const fetchEntityFacts = useCallback(
    async (entityId: number): Promise<void> => {
      const request = ++factsRequest.current;
      const mode = factMode;
      const applies = () =>
        mounted.current &&
        request === factsRequest.current &&
        currentFactMode.current === mode &&
        currentEntity.current === entityId &&
        currentTab.current === 'facts';
      setEntityFacts(null);
      setFactInputs({});
      setNewListValues({});
      setIsFactsLoading(true);
      setFactError(null);
      try {
        const entityName = currentFactEntities.current.find((entity) => entity.id === entityId)?.name;
        if (!entityName) return;
        const data = await adminService.getCountryFacts(entityName, mode);
        if (applies()) {
          setEntityFacts(data);
          setFactInputs(
            Object.fromEntries(data.scalar_facts.map((fact) => [fact.relation, fact.value == null ? '' : String(fact.value)])),
          );
        }
      } catch (error) {
        if (applies()) setFactError(requestError(error));
      } finally {
        if (applies()) setIsFactsLoading(false);
      }
    },
    [factMode],
  );

  const fetchFactEntities = useCallback(async (): Promise<void> => {
    const request = ++entitiesRequest.current;
    const mode = factMode;
    const applies = () =>
      mounted.current &&
      request === entitiesRequest.current &&
      currentFactMode.current === mode &&
      currentTab.current === 'facts';
    factsRequest.current++;
    setIsEntitiesLoading(true);
    setIsFactsLoading(false);
    setFactError(null);
    setFactEntities([]);
    currentFactEntities.current = [];
    setSelectedEntityId(null);
    currentEntity.current = null;
    setEntityFacts(null);
    setFactInputs({});
    setNewListValues({});
    try {
      let data: EntityOption[] = [];
      if (mode === 'countrydle') {
        const countries = await gameService.getCountries();
        data = countries.map(({ id, name }) => ({ id, name }));
      } else if (mode === 'us_statedle') {
        const states: Array<{ id: number; name: string }> = await usStateService.getStates();
        data = states.map(({ id, name }) => ({ id, name }));
      } else if (mode === 'powiatdle') {
        const counties: Array<{ id: number; nazwa: string }> = await powiatService.getPowiaty();
        data = counties.map(({ id, nazwa }) => ({ id, name: nazwa }));
      } else if (mode === 'wojewodztwodle') {
        const voivodeships: Array<{ id: number; nazwa: string }> = await wojewodztwoService.getWojewodztwa();
        data = voivodeships.map(({ id, nazwa }) => ({ id, name: nazwa }));
      }
      data.sort((a, b) => a.name.localeCompare(b.name));
      if (applies()) {
        setFactEntities(data);
        currentFactEntities.current = data;
        if (data.length) {
          currentEntity.current = data[0].id;
          setSelectedEntityId(data[0].id);
          await fetchEntityFacts(data[0].id);
        }
      }
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    } finally {
      if (applies()) setIsEntitiesLoading(false);
    }
  }, [factMode, fetchEntityFacts]);

  const handleRefreshFacts = async (): Promise<void> => {
    if (selectedEntityId !== null) await fetchEntityFacts(selectedEntityId);
    else await fetchFactEntities();
  };

  const handleSaveScalarFact = async (relation: string, value: string) => {
    if (!entityFacts || selectedEntityId === null || isFactsLoading || isEntitiesLoading) return;
    const applies = () =>
      mounted.current &&
      currentTab.current === 'facts' &&
      currentFactMode.current === factMode &&
      currentEntity.current === selectedEntityId;
    try {
      await adminService.updateCountryScalarFact(entityFacts.country.id, relation, value, undefined, factMode);
      if (applies()) await fetchEntityFacts(selectedEntityId);
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    }
  };

  const handleAddListFact = async (relation: string, value: string) => {
    if (!entityFacts || selectedEntityId === null || isFactsLoading || isEntitiesLoading || !value.trim()) return;
    const applies = () =>
      mounted.current &&
      currentTab.current === 'facts' &&
      currentFactMode.current === factMode &&
      currentEntity.current === selectedEntityId;
    try {
      await adminService.addCountryListFact(entityFacts.country.id, relation, value.trim(), {}, undefined, factMode);
      if (applies()) {
        setNewListValues((prev) => ({ ...prev, [relation]: '' }));
        await fetchEntityFacts(selectedEntityId);
      }
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    }
  };

  const handleDeleteListFact = async (relation: string, value: string) => {
    if (!entityFacts || selectedEntityId === null || isFactsLoading || isEntitiesLoading) return;
    const applies = () =>
      mounted.current &&
      currentTab.current === 'facts' &&
      currentFactMode.current === factMode &&
      currentEntity.current === selectedEntityId;
    try {
      await adminService.deleteCountryListFact(entityFacts.country.id, relation, value, undefined, factMode);
      if (applies()) await fetchEntityFacts(selectedEntityId);
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    }
  };

  useEffect(() => {
    if (activeTab === 'overview') void fetchOverview();
    return () => {
      overviewRequest.current++;
    };
  }, [activeTab, fetchOverview]);

  useEffect(() => {
    if (activeTab === 'users') void fetchUsers();
    return () => {
      usersRequest.current++;
    };
  }, [activeTab, fetchUsers]);

  useEffect(() => {
    return () => {
      feedRequest.current++;
      pendingFeed.current = null;
    };
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'facts') void fetchFactEntities();
    return () => {
      entitiesRequest.current++;
      factsRequest.current++;
    };
  }, [activeTab, fetchFactEntities]);

  return (
    <div className="min-h-screen bg-app-canvas text-app-text">
      <div className="mx-auto flex max-w-[1440px] flex-col lg:flex-row">
        {/* Desktop Sidebar: 5 clean top-level sections */}
        <aside className="hidden lg:block lg:w-60 lg:shrink-0 border-r border-app-border bg-app-surface/70 p-4">
          <div className="mb-5 px-2">
            <p className="font-mono text-[10px] uppercase tracking-widest text-app-text-muted">Countrydle</p>
            <p className="font-serif text-lg font-bold text-app-text">Admin Console</p>
          </div>
          <nav className="space-y-1" aria-label="Admin sections">
            {GROUPS.map((group) => {
              const Icon = group.icon;
              const isCurrentGroup = group.id === activeGroup.id;
              return (
                <div key={group.id} className="space-y-0.5">
                  <button
                    type="button"
                    onClick={() => setActiveTab(group.tabs[0].id)}
                    aria-current={isCurrentGroup && group.tabs.length === 1 ? 'page' : undefined}
                    className={`flex w-full items-center gap-2.5 rounded-sm px-3 py-2 text-left text-sm font-medium transition-colors cursor-pointer ${
                      isCurrentGroup
                        ? 'bg-app-accent/10 text-app-accent font-semibold'
                        : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                    }`}
                  >
                    <Icon size={16} aria-hidden="true" />
                    <span>{group.label}</span>
                  </button>
                  {isCurrentGroup && group.tabs.length > 1 && (
                    <div className="ml-6 border-l border-app-border pl-2.5 py-0.5 space-y-0.5">
                      {group.tabs.map((sub) => (
                        <button
                          key={sub.id}
                          type="button"
                          onClick={() => setActiveTab(sub.id)}
                          aria-current={activeTab === sub.id ? 'page' : undefined}
                          className={`block w-full rounded-sm px-2.5 py-1.5 text-left text-xs transition-colors cursor-pointer ${
                            activeTab === sub.id
                              ? 'bg-app-accent text-app-canvas font-medium'
                              : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                          }`}
                        >
                          {sub.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8 space-y-5">
          {/* Mobile Navigation Bar */}
          <div className="lg:hidden space-y-2">
            <div className="flex gap-1.5 overflow-x-auto pb-1" role="tablist" aria-label="Admin sections">
              {GROUPS.map((group) => {
                const Icon = group.icon;
                const active = group.id === activeGroup.id;
                return (
                  <button
                    key={group.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setActiveTab(group.tabs[0].id)}
                    className={`inline-flex shrink-0 items-center gap-1.5 rounded-sm border px-3 py-1.5 text-xs font-medium cursor-pointer ${
                      active
                        ? 'border-app-accent bg-app-accent text-app-canvas'
                        : 'border-app-border bg-app-surface text-app-text-secondary'
                    }`}
                  >
                    <Icon size={14} aria-hidden="true" />
                    <span>{group.label}</span>
                  </button>
                );
              })}
            </div>
            {activeGroup.tabs.length > 1 && (
              <div className="flex gap-1.5 overflow-x-auto pb-1">
                {activeGroup.tabs.map((sub) => (
                  <button
                    key={sub.id}
                    type="button"
                    onClick={() => setActiveTab(sub.id)}
                    className={`shrink-0 rounded-sm border px-2.5 py-1 text-xs cursor-pointer ${
                      activeTab === sub.id
                        ? 'border-app-accent bg-app-accent/10 text-app-accent font-semibold'
                        : 'border-app-border bg-app-surface text-app-text-secondary'
                    }`}
                  >
                    {sub.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Page Header */}
          <header className="border-b border-app-border pb-4">
            <p className="font-mono text-[11px] uppercase tracking-wider text-app-text-muted">
              Admin / {activeGroup.label}
            </p>
            <h1 id="admin-page-title" tabIndex={-1} className="mt-0.5 font-serif text-2xl font-bold text-app-text">
              {activeSubTab.label}
            </h1>
            <p className="mt-1 text-sm text-app-text-secondary">{activeSubTab.description}</p>
          </header>

          {/* Active Panel */}
          {activeTab === 'overview' && (
            <AdminOverviewTab
              overview={overview}
              isLoading={isOverviewLoading}
              error={overviewError}
              onRefresh={fetchOverview}
              onOpenCosts={() => setActiveTab('aiCosts')}
              onOpenSessions={(mode) => {
                if (overview) setSessionFilters(mode, overview.date);
              }}
            />
          )}

          {activeTab === 'sessions' && (
            <AdminSessionsTab
              key={`${searchParams.get('mode') || 'countrydle'}:${searchParams.get('date') || ''}`}
              onTestInQA={handleTestInQA}
              selectedMode={searchParams.get('mode') || 'countrydle'}
              selectedDate={searchParams.get('date') || new Date().toISOString().slice(0, 10)}
              onFiltersChange={setSessionFilters}
            />
          )}

          {activeTab === 'liveFeed' && (
            <AdminLiveFeedTab
              data={liveFeed}
              isLoading={isFeedLoading}
              error={feedError}
              hasLoaded={feedHasLoaded}
              lastUpdatedAt={feedUpdatedAt}
              onRefresh={fetchLiveFeed}
              onTestInQA={handleTestInQA}
            />
          )}

          {activeTab === 'questions' && <AdminQuestionsTab onTestInQA={handleTestInQA} />}

          {activeTab === 'facts' && (
            <AdminFactsTab
              factMode={factMode}
              factEntities={factEntities}
              selectedEntityId={selectedEntityId}
              entityFacts={entityFacts}
              factInputs={factInputs}
              newListValues={newListValues}
              factError={factError}
              isEntitiesLoading={isEntitiesLoading}
              isFactsLoading={isFactsLoading}
              onRefresh={handleRefreshFacts}
              onFactModeChange={(mode) => {
                if (mode === factMode) return;
                currentFactMode.current = mode;
                entitiesRequest.current++;
                factsRequest.current++;
                setFactEntities([]);
                currentFactEntities.current = [];
                setEntityFacts(null);
                setSelectedEntityId(null);
                currentEntity.current = null;
                setFactError(null);
                setIsEntitiesLoading(true);
                setFactMode(mode);
              }}
              onEntitySelect={(id) => {
                currentEntity.current = id;
                setSelectedEntityId(id);
                void fetchEntityFacts(id);
              }}
              onFactInputChange={(rel, val) => setFactInputs((prev) => ({ ...prev, [rel]: val }))}
              onSaveScalarFact={handleSaveScalarFact}
              onNewListValueChange={(rel, val) => setNewListValues((prev) => ({ ...prev, [rel]: val }))}
              onAddListFact={handleAddListFact}
              onDeleteListFact={handleDeleteListFact}
            />
          )}

          {activeTab === 'reports' && (
            <AnswerReportsPanel
              onTestQuestion={(report) => {
                setQaBridgeTarget(null);
                setQuestionTestReport(report);
                focusQA.current = true;
                setActiveTab('questionTests');
              }}
            />
          )}

          {activeTab === 'questionTests' && (
            <QuestionTestsPanel
              report={questionTestReport}
              onClearReport={() => setQuestionTestReport(null)}
              initialTarget={qaBridgeTarget}
              onClearInitialTarget={() => setQaBridgeTarget(null)}
            />
          )}

          {activeTab === 'blogs' && <AdminBlogTab />}

          {activeTab === 'templateDivergences' && (
            <TemplateDivergencesPanel onTestQuestion={(questionText, mode) => handleTestInQA({ mode, questionText })} />
          )}

          {activeTab === 'friendAnswers' && <FriendAnswerReviewsPanel />}

          {activeTab === 'suggestions' && <AdminSuggestionsTab />}

          {activeTab === 'users' && (
            <AdminUsersTab
              users={loadedUsersQuery === usersQuery ? usersData.users : []}
              totalUsers={loadedUsersQuery === usersQuery ? usersData.total : 0}
              search={userSearch}
              page={userPage}
              isLoading={isUsersLoading || loadedUsersQuery !== usersQuery}
              error={loadedUsersQuery === usersQuery ? usersError : null}
              onRefresh={fetchUsers}
              onSearchChange={(s) => {
                setUserSearch(s);
                setUserPage(1);
              }}
              onPageChange={setUserPage}
            />
          )}

          {activeTab === 'aiCosts' && <AdminCountrydleCostsTab />}

          {activeTab === 'cache' && <CacheStatsPanel />}
        </main>
      </div>
    </div>
  );
}
