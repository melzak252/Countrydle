import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
  type CountryFactsResponse 
} from '../services/api';
import { 
  Users, 
  HelpCircle, 
  Calendar, 
  Database, 
  Activity, 
  ShieldCheck, 
  FileText, 
  Sparkles,
  Cpu,
  MessageSquare,
  Play,
  DollarSign
} from 'lucide-react';

type AdminSection = 'gameplay' | 'qa' | 'system';
type AdminTab = 'overview' | 'sessions' | 'liveFeed' | 'users' | 'suggestions' | 'blogs' | 'questions' | 'facts' | 'reports' | 'templateDivergences' | 'friendAnswers' | 'questionTests' | 'cache' | 'aiCosts';

interface TabDefinition {
  id: AdminTab;
  labelKey: string;
  descriptionKey: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  section: AdminSection;
}

const TABS: TabDefinition[] = [
  { id: 'overview', labelKey: 'adminNavigation.pages.overview.label', descriptionKey: 'adminNavigation.pages.overview.description', icon: Activity, section: 'gameplay' },
  { id: 'sessions', labelKey: 'adminNavigation.pages.sessions.label', descriptionKey: 'adminNavigation.pages.sessions.description', icon: Play, section: 'gameplay' },
  { id: 'liveFeed', labelKey: 'adminNavigation.pages.liveFeed.label', descriptionKey: 'adminNavigation.pages.liveFeed.description', icon: Calendar, section: 'gameplay' },
  { id: 'users', labelKey: 'adminNavigation.pages.users.label', descriptionKey: 'adminNavigation.pages.users.description', icon: Users, section: 'gameplay' },
  { id: 'suggestions', labelKey: 'adminNavigation.pages.suggestions.label', descriptionKey: 'adminNavigation.pages.suggestions.description', icon: MessageSquare, section: 'gameplay' },
  { id: 'friendAnswers', labelKey: 'adminNavigation.pages.friendAnswers.label', descriptionKey: 'adminNavigation.pages.friendAnswers.description', icon: HelpCircle, section: 'gameplay' },
  { id: 'blogs', labelKey: 'Blogs', descriptionKey: 'Edit daily recaps, record source evidence, and explicitly review or revoke publication review.', icon: FileText, section: 'qa' },
  { id: 'questions', labelKey: 'adminNavigation.pages.questions.label', descriptionKey: 'adminNavigation.pages.questions.description', icon: HelpCircle, section: 'qa' },
  { id: 'reports', labelKey: 'adminNavigation.pages.reports.label', descriptionKey: 'adminNavigation.pages.reports.description', icon: FileText, section: 'qa' },
  { id: 'questionTests', labelKey: 'adminNavigation.pages.questionTests.label', descriptionKey: 'adminNavigation.pages.questionTests.description', icon: Sparkles, section: 'qa' },
  { id: 'templateDivergences', labelKey: 'adminNavigation.pages.templateDivergences.label', descriptionKey: 'adminNavigation.pages.templateDivergences.description', icon: ShieldCheck, section: 'qa' },
  { id: 'facts', labelKey: 'adminNavigation.pages.facts.label', descriptionKey: 'adminNavigation.pages.facts.description', icon: Database, section: 'qa' },
  { id: 'cache', labelKey: 'adminNavigation.pages.cache.label', descriptionKey: 'adminNavigation.pages.cache.description', icon: Cpu, section: 'system' },
  { id: 'aiCosts', labelKey: 'adminCosts.tab', descriptionKey: 'adminNavigation.pages.aiCosts.description', icon: DollarSign, section: 'system' },
];
const SECTIONS: AdminSection[] = ['gameplay', 'qa', 'system'];

function requestError(error: unknown): string {
  if (isAxiosError(error)) {
    return typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'adminCommon.error';
  }
  return error instanceof Error ? error.message : 'adminCommon.error';
}

export default function AdminDashboard() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
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
      if (mounted.current && request === overviewRequest.current && currentTab.current === 'overview') setOverview(data);
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
    const applies = () => mounted.current && request === usersRequest.current && currentUsersQuery.current === query && currentTab.current === 'users';
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
    const applies = () => mounted.current && request === feedRequest.current && currentTab.current === 'liveFeed';
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

  const fetchEntityFacts = useCallback(async (entityId: number): Promise<void> => {
    const request = ++factsRequest.current;
    const mode = factMode;
    const applies = () => mounted.current && request === factsRequest.current && currentFactMode.current === mode && currentEntity.current === entityId && currentTab.current === 'facts';
    setEntityFacts(null);
    setFactInputs({});
    setNewListValues({});
    setIsFactsLoading(true);
    setFactError(null);
    try {
      // Selector IDs belong to PostgreSQL; fact IDs belong to the local SQLite catalog.
      const entityName = currentFactEntities.current.find((entity) => entity.id === entityId)?.name;
      if (!entityName) return;
      const data = await adminService.getCountryFacts(entityName, mode);
      if (applies()) {
        setEntityFacts(data);
        setFactInputs(Object.fromEntries(data.scalar_facts.map((fact) => [fact.relation, fact.value == null ? '' : String(fact.value)])));
      }
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    } finally {
      if (applies()) setIsFactsLoading(false);
    }
  }, [factMode]);

  const fetchFactEntities = useCallback(async (): Promise<void> => {
    const request = ++entitiesRequest.current;
    const mode = factMode;
    const applies = () => mounted.current && request === entitiesRequest.current && currentFactMode.current === mode && currentTab.current === 'facts';
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
    const applies = () => mounted.current && currentTab.current === 'facts' && currentFactMode.current === factMode && currentEntity.current === selectedEntityId;
    try {
      await adminService.updateCountryScalarFact(
        entityFacts.country.id,
        relation,
        value,
        undefined,
        factMode
      );
      if (applies()) await fetchEntityFacts(selectedEntityId);
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    }
  };

  const handleAddListFact = async (relation: string, value: string) => {
    if (!entityFacts || selectedEntityId === null || isFactsLoading || isEntitiesLoading || !value.trim()) return;
    const applies = () => mounted.current && currentTab.current === 'facts' && currentFactMode.current === factMode && currentEntity.current === selectedEntityId;
    try {
      await adminService.addCountryListFact(
        entityFacts.country.id,
        relation,
        value.trim(),
        {},
        undefined,
        factMode
      );
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
    const applies = () => mounted.current && currentTab.current === 'facts' && currentFactMode.current === factMode && currentEntity.current === selectedEntityId;
    try {
      await adminService.deleteCountryListFact(
        entityFacts.country.id,
        relation,
        value,
        undefined,
        factMode
      );
      if (applies()) await fetchEntityFacts(selectedEntityId);
    } catch (error) {
      if (applies()) setFactError(requestError(error));
    }
  };

  useEffect(() => {
    if (activeTab === 'overview') void fetchOverview();
    return () => { overviewRequest.current++; };
  }, [activeTab, fetchOverview]);
  useEffect(() => {
    if (activeTab === 'users') void fetchUsers();
    return () => { usersRequest.current++; };
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

  const activeDefinition = TABS.find((tab) => tab.id === activeTab)!;

  return (
    <div className="admin-workspace">
      <nav className="admin-sidebar" aria-label={t('adminNavigation.pageSelector')}>
        {SECTIONS.map((section) => (
          <div key={section} className="mb-6">
            <p className="admin-meta mb-2 px-3">{t(`adminNavigation.sections.${section}`)}</p>
            {TABS.filter((tab) => tab.section === section).map((tab) => {
              const Icon = tab.icon;
              return <button key={tab.id} type="button" className="admin-button" aria-current={activeTab === tab.id ? 'page' : undefined} onClick={() => setActiveTab(tab.id)}>
                <Icon size={18} aria-hidden="true" /><span>{t(tab.labelKey)}</span>
              </button>;
            })}
          </div>
        ))}
      </nav>
      <div className="admin-content">
        <label className="admin-field admin-mobile-navigation">
          <span>{t('adminNavigation.pageSelector')}</span>
          <select className="admin-control" value={activeTab} onChange={(event) => {
            const destination = TABS.find((tab) => tab.id === event.target.value);
            if (destination) setActiveTab(destination.id);
          }}>
            {SECTIONS.map((section) => <optgroup key={section} label={t(`adminNavigation.sections.${section}`)}>
              {TABS.filter((tab) => tab.section === section).map((tab) => <option key={tab.id} value={tab.id}>{t(tab.labelKey)}</option>)}
            </optgroup>)}
          </select>
        </label>
        <header className="admin-page-header">
          <p className="admin-meta">Countrydle / Admin</p>
          <h1 id="admin-page-title" tabIndex={-1}>{t(activeDefinition.labelKey)}</h1>
          <p className="admin-muted">{t(activeDefinition.descriptionKey)}</p>
        </header>
      {/* TAB CONTENT PANELS */}
      {activeTab === 'overview' && (
        <AdminOverviewTab overview={overview} isLoading={isOverviewLoading} error={overviewError} onRefresh={fetchOverview} />
      )}

      {activeTab === 'sessions' && (
        <AdminSessionsTab onTestInQA={handleTestInQA} />
      )}

      {activeTab === 'liveFeed' && (
        <AdminLiveFeedTab data={liveFeed} isLoading={isFeedLoading} error={feedError} hasLoaded={feedHasLoaded} lastUpdatedAt={feedUpdatedAt} onRefresh={fetchLiveFeed} onTestInQA={handleTestInQA} />
      )}
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

      {activeTab === 'suggestions' && <AdminSuggestionsTab />}
      {activeTab === 'blogs' && <AdminBlogTab />}
      {activeTab === 'questions' && (
        <AdminQuestionsTab onTestInQA={handleTestInQA} />
      )}
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
      {activeTab === 'templateDivergences' && (
        <TemplateDivergencesPanel onTestQuestion={(questionText, mode) => handleTestInQA({ mode, questionText })} />
      )}


      {activeTab === 'questionTests' && (
        <QuestionTestsPanel
          report={questionTestReport}
          onClearReport={() => setQuestionTestReport(null)}
          initialTarget={qaBridgeTarget}
          onClearInitialTarget={() => setQaBridgeTarget(null)}
        />
      )}

      {activeTab === 'friendAnswers' && (
        <FriendAnswerReviewsPanel />
      )}

      {activeTab === 'cache' && (
        <CacheStatsPanel />
      )}
      {activeTab === 'aiCosts' && <AdminCountrydleCostsTab />}
      </div>
    </div>
  );
}
