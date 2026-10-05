import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import AnswerReportsPanel from '../components/AnswerReportsPanel';
import TemplateDivergencesPanel from '../components/admin/TemplateDivergencesPanel';
import FriendAnswerReviewsPanel from '../components/FriendAnswerReviewsPanel';
import QuestionTestsPanel from '../components/QuestionTestsPanel';
import CacheStatsPanel from '../components/CacheStatsPanel';
import AdminOverviewTab from '../components/admin/AdminOverviewTab';
import AdminLiveFeedTab from '../components/admin/AdminLiveFeedTab';
import AdminCountrydleCostsTab from '../components/admin/AdminCountrydleCostsTab';
import AdminUsersTab from '../components/admin/AdminUsersTab';
import AdminQuestionsTab, { type AdminGameType } from '../components/admin/AdminQuestionsTab';
import AdminFactsTab from '../components/admin/AdminFactsTab';
import AdminSuggestionsTab from '../components/admin/AdminSuggestionsTab';
import type { AnswerReport } from '../types';
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
  RefreshCw, 
  Database, 
  Activity, 
  ShieldCheck, 
  FileText, 
  Sparkles,
  Gamepad2,
  Cpu,
  MessageSquare,
  DollarSign
} from 'lucide-react';

type AdminSection = 'gameplay' | 'qa' | 'system';
type AdminTab = 'overview' | 'liveFeed' | 'users' | 'suggestions' | 'questions' | 'facts' | 'reports' | 'templateDivergences' | 'friendAnswers' | 'questionTests' | 'cache' | 'aiCosts';

interface TabDefinition {
  id: AdminTab;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  section: AdminSection;
}

const TABS: TabDefinition[] = [
  // Gameplay Section
  { id: 'overview', label: 'Overview & Solve Rates', icon: Activity, section: 'gameplay' },
  { id: 'liveFeed', label: 'Live Player Feed', icon: Calendar, section: 'gameplay' },
  { id: 'users', label: 'User Directory', icon: Users, section: 'gameplay' },
  { id: 'suggestions', label: 'adminSuggestions.tab', icon: MessageSquare, section: 'gameplay' },
  { id: 'friendAnswers', label: 'Friend Duels', icon: HelpCircle, section: 'gameplay' },

  // QA & Knowledge Section
  { id: 'questions', label: 'Questions Log', icon: HelpCircle, section: 'qa' },
  { id: 'reports', label: 'Player Reports', icon: FileText, section: 'qa' },
  { id: 'templateDivergences', label: 'Template Shadow Audit', icon: ShieldCheck, section: 'qa' },
  { id: 'questionTests', label: 'QA Playground', icon: Sparkles, section: 'qa' },
  { id: 'facts', label: 'Facts Editor (SQLite)', icon: Database, section: 'qa' },

  // System Section
  { id: 'cache', label: 'Cache & Performance', icon: Cpu, section: 'system' },
  { id: 'aiCosts', label: 'adminCosts.tab', icon: DollarSign, section: 'system' },
];

export default function AdminDashboard() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [activeSection, setActiveSection] = useState<AdminSection>('gameplay');
  const [questionTestReport, setQuestionTestReport] = useState<AnswerReport | null>(null);

  // Overview State
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
  const [questionsMode, setQuestionsMode] = useState<AdminGameType>('countrydle');
  const [questions, setQuestions] = useState<any[]>([]);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [questionPage, setQuestionPage] = useState(1);
  const [questionSearch, setQuestionSearch] = useState('');
  const [continentalFilter, setContinentalFilter] = useState('all');

  // Facts Editor State
  const [factMode, setFactMode] = useState<AdminGameType>('countrydle');
  const [factEntities, setFactEntities] = useState<any[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
  const [entityFacts, setEntityFacts] = useState<CountryFactsResponse | null>(null);
  const [factInputs, setFactInputs] = useState<Record<string, string>>({});
  const [newListValues, setNewListValues] = useState<Record<string, string>>({});
  const [factError, setFactError] = useState<string | null>(null);

  // Sync section with active tab
  useEffect(() => {
    const tabDef = TABS.find((t) => t.id === activeTab);
    if (tabDef && tabDef.section !== activeSection) {
      setActiveSection(tabDef.section);
    }
  }, [activeTab]);

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
  const fetchLiveFeed = async (mode?: string) => {
    setIsFeedLoading(true);
    try {
      const data = await adminService.getLiveFeed(mode);
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
      let data: { items: unknown[]; total: number } = { items: [], total: 0 };
      if (questionsMode === 'countrydle') data = await adminService.getCountrydleQuestions(limit, offset);
      else if (questionsMode === 'continental') data = await adminService.getContinentalQuestions(limit, offset, continentalFilter);
      else if (questionsMode === 'us_statedle') data = await adminService.getUSStatedleQuestions(limit, offset);
      else if (questionsMode === 'powiatdle') data = await adminService.getPowiatdleQuestions(limit, offset);
      else if (questionsMode === 'wojewodztwodle') data = await adminService.getWojewodztwodleQuestions(limit, offset);
      setQuestions(data.items || []);
      setTotalQuestions(data.total || 0);
    } catch (err) {
      console.error('Failed to load questions:', err);
    }
  };

  // Fetch Fact Entities
  const fetchFactEntities = async () => {
    try {
      let data: any[] = [];
      if (factMode === 'countrydle') data = await gameService.getCountries();
      else if (factMode === 'us_statedle') data = await usStateService.getStates();
      else if (factMode === 'powiatdle') data = await powiatService.getPowiaty();
      else if (factMode === 'wojewodztwodle') data = await wojewodztwoService.getWojewodztwa();

      setFactEntities(data || []);
      if (data && data.length > 0) {
        setSelectedEntityId(data[0].id);
        fetchEntityFacts(data[0].name || data[0].nazwa || data[0].id);
      }
    } catch (err) {
      console.error('Failed to load fact entities:', err);
    }
  };

  // Fetch Facts for Entity
  const fetchEntityFacts = async (entityIdOrName: number | string) => {
    try {
      const data = await adminService.getCountryFacts(entityIdOrName, factMode);
      setEntityFacts(data);
      const inputs: Record<string, string> = {};
      (data.scalar_facts || []).forEach((f: any) => {
        inputs[f.relation] = f.value ?? '';
      });
      setFactInputs(inputs);
      setFactError(null);
    } catch (err) {
      console.error('Failed to load entity facts:', err);
      setFactError('Failed to load entity facts');
    }
  };

  const handleSaveScalarFact = async (relation: string, value: string) => {
    if (!entityFacts) return;
    try {
      await adminService.updateCountryScalarFact(
        entityFacts.country.id,
        relation,
        value,
        undefined,
        factMode
      );
      fetchEntityFacts(entityFacts.country.id);
    } catch (e: any) {
      setFactError(e.message || 'Failed to update fact');
    }
  };

  const handleAddListFact = async (relation: string, value: string) => {
    if (!entityFacts || !value.trim()) return;
    try {
      await adminService.addCountryListFact(
        entityFacts.country.id,
        relation,
        value.trim(),
        {},
        undefined,
        factMode
      );
      setNewListValues((prev) => ({ ...prev, [relation]: '' }));
      fetchEntityFacts(entityFacts.country.id);
    } catch (e: any) {
      setFactError(e.message || 'Failed to add fact');
    }
  };

  const handleDeleteListFact = async (relation: string, value: string) => {
    if (!entityFacts) return;
    try {
      await adminService.deleteCountryListFact(
        entityFacts.country.id,
        relation,
        value,
        undefined,
        factMode
      );
      fetchEntityFacts(entityFacts.country.id);
    } catch (e: any) {
      setFactError(e.message || 'Failed to delete fact');
    }
  };

  // Initial load
  useEffect(() => {
    fetchOverview();
  }, []);

  useEffect(() => {
    if (activeTab === 'overview') fetchOverview();
    else if (activeTab === 'users') fetchUsers();
    else if (activeTab === 'liveFeed') fetchLiveFeed();
  }, [activeTab, userPage]);

  useEffect(() => {
    if (activeTab === 'questions') fetchQuestions();
  }, [activeTab, questionsMode, questionPage, continentalFilter]);

  useEffect(() => {
    if (activeTab === 'facts') fetchFactEntities();
  }, [activeTab, factMode]);

  const activeSectionTabs = TABS.filter((t) => t.section === activeSection);

  return (
    <div className="min-w-0 space-y-6 bg-obsidian-950 text-sand-100 [&_button]:focus-visible:outline [&_button]:focus-visible:outline-2 [&_button]:focus-visible:outline-offset-2 [&_button]:focus-visible:outline-emerald-300 [&_input]:focus-visible:outline-emerald-300 [&_select]:focus-visible:outline-emerald-300">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-emerald-300 font-medium text-xs uppercase tracking-[0.18em]">
            <ShieldCheck size={16} />
            <span>Administrator Control Center</span>
          </div>
          <h1 className="font-serif text-2xl md:text-4xl text-sand-100 tracking-tight">
            Countrydle Admin Dashboard
          </h1>
          <p className="max-w-2xl text-sand-100/65 text-xs md:text-sm leading-relaxed">
            Real-time player monitoring, community solve progression, knowledge base management, and QA verification.
          </p>
        </div>

        {activeTab !== 'reports' && activeTab !== 'friendAnswers' && activeTab !== 'questionTests' && activeTab !== 'cache' && activeTab !== 'aiCosts' && activeTab !== 'suggestions' && (
          <div>
            <button
              type="button"
              onClick={() => {
                if (activeTab === 'overview') fetchOverview();
                else if (activeTab === 'users') fetchUsers();
                else if (activeTab === 'liveFeed') fetchLiveFeed();
                else if (activeTab === 'questions') fetchQuestions();
              }}
              className="flex items-center gap-2 px-4 py-2 bg-obsidian-900 hover:bg-white/5 text-sand-100 rounded-sm text-xs font-semibold transition-colors border border-white/10"
            >
              <RefreshCw size={13} className={isOverviewLoading || isUsersLoading || isFeedLoading ? 'animate-spin' : ''} />
              <span>Refresh View</span>
            </button>
          </div>
        )}
      </div>

      {/* Primary Section Selector (3 Main Pillars) */}
      <div className="flex flex-wrap gap-2 border-b border-white/10 pb-3" role="tablist">
        {[
          { id: 'gameplay', label: 'Gameplay & Players', icon: Gamepad2 },
          { id: 'qa', label: 'Knowledge Base & QA Engine', icon: Sparkles },
          { id: 'system', label: 'System & Cache', icon: Cpu },
        ].map((sec) => {
          const Icon = sec.icon;
          const isSelected = activeSection === sec.id;
          return (
            <button
              key={sec.id}
              type="button"
              onClick={() => {
                setActiveSection(sec.id as AdminSection);
                // Switch to first tab in that section
                const firstTab = TABS.find((t) => t.section === sec.id);
                if (firstTab) setActiveTab(firstTab.id);
              }}
              role="tab"
              aria-selected={isSelected}
              className={`flex items-center gap-2 px-4 py-2 rounded-sm font-semibold text-xs md:text-sm transition-colors border ${
                isSelected
                  ? 'bg-emerald-400/15 border-emerald-400/40 text-emerald-300 shadow-sm'
                  : 'bg-obsidian-900/60 border-white/10 text-sand-100/65 hover:text-sand-100 hover:border-white/20'
              }`}
            >
              <Icon size={16} />
              <span>{sec.label}</span>
            </button>
          );
        })}
      </div>

      {/* Secondary Sub-Tabs Navigation */}
      <div className="flex flex-wrap gap-1.5 pb-2" role="tablist">
        {activeSectionTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              aria-selected={isActive}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm font-medium text-xs transition-colors border ${
                isActive
                  ? 'bg-white/10 border-white/25 text-sand-100 font-semibold shadow-inner'
                  : 'bg-transparent border-transparent text-sand-100/55 hover:text-sand-100 hover:bg-white/5'
              }`}
            >
              <Icon size={14} className={isActive ? 'text-emerald-300' : 'text-sand-100/55'} />
              <span>{tab.id === 'suggestions' || tab.id === 'aiCosts' ? t(tab.label) : tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT PANELS */}
      {activeTab === 'overview' && (
        <AdminOverviewTab overview={overview} isLoading={isOverviewLoading} />
      )}

      {activeTab === 'liveFeed' && (
        <AdminLiveFeedTab data={liveFeed} isLoading={isFeedLoading} onRefresh={fetchLiveFeed} />
      )}

      {activeTab === 'users' && (
        <AdminUsersTab
          users={usersData.users}
          totalUsers={usersData.total}
          search={userSearch}
          page={userPage}
          isLoading={isUsersLoading}
          onSearchChange={(s) => {
            setUserSearch(s);
            setUserPage(1);
          }}
          onPageChange={setUserPage}
        />
      )}

      {activeTab === 'suggestions' && <AdminSuggestionsTab />}
      {activeTab === 'questions' && (
        <AdminQuestionsTab
          mode={questionsMode}
          selectedContinent={continentalFilter}
          onContinentChange={(c) => {
            setContinentalFilter(c);
            setQuestionPage(1);
          }}
          questions={questions}
          totalQuestions={totalQuestions}
          page={questionPage}
          search={questionSearch}
          onModeChange={(m) => {
            setQuestionsMode(m);
            setContinentalFilter('all');
            setQuestionPage(1);
          }}
          onSearchChange={setQuestionSearch}
          onPageChange={setQuestionPage}
        />
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
          onFactModeChange={setFactMode}
          onEntitySelect={(id, name) => {
            setSelectedEntityId(id);
            fetchEntityFacts(name);
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
            setQuestionTestReport(report);
            setActiveTab('questionTests');
          }}
        />
      )}
      {activeTab === 'templateDivergences' && (
        <TemplateDivergencesPanel />
      )}


      {activeTab === 'questionTests' && (
        <QuestionTestsPanel
          report={questionTestReport}
          onClearReport={() => setQuestionTestReport(null)}
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
  );
}
