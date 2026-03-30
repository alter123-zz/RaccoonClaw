import { useEffect } from 'react';
import { useStore, TAB_DEFS, type TabKey, startPolling, stopPolling, isTerminalState } from './store';
import EdictBoard from './components/EdictBoard';
import OfficialPanel from './components/OfficialPanel';
import ModelConfig from './components/ModelConfig';
import SkillsConfig from './components/SkillsConfig';
import ImChannelsPanel from './components/ImChannelsPanel';
import SessionsPanel from './components/SessionsPanel';
import MemorialPanel from './components/MemorialPanel';
import TemplatePanel from './components/TemplatePanel';
import ToolboxPanel from './components/ToolboxPanel';
import ChatPanel from './components/ChatPanel';
import TaskModal from './components/TaskModal';
import Toaster from './components/Toaster';
import GodViewPanel from './components/GodViewPanel';
import { selectWorkbenchTasks } from './workbenchSelectors';
import raccoonclawLogo from './assets/raccoonclaw-logo.png';

const TAB_MAP = TAB_DEFS.reduce<Partial<Record<TabKey, { key: TabKey; label: string; icon: string }>>>((acc, tab) => {
  acc[tab.key] = tab;
  return acc;
}, {});

const SIDEBAR_GROUPS: { key: string; label: string; items: TabKey[] }[] = [
  { key: 'workspace', label: '工作台', items: ['chat', 'godview', 'edicts', 'templates'] },
  { key: 'config', label: '配置中心', items: ['officials', 'models', 'skills', 'imchannels', 'toolbox'] },
  { key: 'insight', label: '资料中心', items: ['memorials'] },
];

function isTabEnabled(tabKey: TabKey, featureFlags: { imChannels: boolean; toolbox: boolean }) {
  if (tabKey === 'imchannels') return featureFlags.imChannels;
  if (tabKey === 'toolbox') return featureFlags.toolbox;
  return true;
}

function WorkspaceBrandHero() {
  return (
    <div className="workspace-brand-mark" aria-hidden="true">
        <img
          className="workspace-brand-logo"
          src={raccoonclawLogo}
          alt=""
          loading="eager"
          decoding="async"
      />
    </div>
  );
}

export default function App() {
  const activeTab = useStore((s) => s.activeTab);
  const publicConfig = useStore((s) => s.publicConfig);
  const setActiveTab = useStore((s) => s.setActiveTab);
  const setWorkbenchMode = useStore((s) => s.setWorkbenchMode);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const liveStatus = useStore((s) => s.liveStatus);
  const loadAgentConfig = useStore((s) => s.loadAgentConfig);
  const loadPublicConfig = useStore((s) => s.loadPublicConfig);
  const unseenCompletedTaskIds = useStore((s) => s.unseenCompletedTaskIds);
  const unseenChatTaskNoticeIds = useStore((s) => s.unseenChatTaskNoticeIds);
  const markCompletedTasksSeen = useStore((s) => s.markCompletedTasksSeen);
  const markChatTaskNoticesSeen = useStore((s) => s.markChatTaskNoticesSeen);

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, []);

  useEffect(() => {
    loadPublicConfig();
  }, [loadPublicConfig]);

  useEffect(() => {
    setWorkbenchMode('all');
  }, [setWorkbenchMode]);

  useEffect(() => {
    if (activeTab === 'overview') {
      setActiveTab('godview');
    }
  }, [activeTab, setActiveTab]);

  const visibleTabDefs = TAB_DEFS.filter((tab) => isTabEnabled(tab.key, publicConfig.features));
  const visibleTabKeys = new Set(visibleTabDefs.map((tab) => tab.key));
  const visibleSidebarGroups = SIDEBAR_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => visibleTabKeys.has(item)),
    }))
    .filter((group) => group.items.length > 0);

  useEffect(() => {
    if (!visibleTabKeys.has(activeTab)) {
      setActiveTab('chat');
    }
  }, [activeTab, setActiveTab, visibleTabDefs]);

  useEffect(() => {
    if (activeTab === 'models') {
      loadAgentConfig();
    }
  }, [activeTab, loadAgentConfig]);

  useEffect(() => {
    if (activeTab === 'chat') {
      markChatTaskNoticesSeen();
    }
  }, [activeTab, markChatTaskNoticesSeen]);

  useEffect(() => {
    if (activeTab === 'memorials') {
      markCompletedTasksSeen();
    }
  }, [activeTab, markCompletedTasksSeen]);

  const tasks = liveStatus?.tasks || [];
  const { edicts, activeEdicts, sessions: visibleSessions } = selectWorkbenchTasks(tasks, workbenchMode);
  const activeTaskCount = activeEdicts.length;
  const tabBadge = (key: TabKey): string => {
    if (key === 'overview') return '';
    if (key === 'chat') return unseenChatTaskNoticeIds.length ? String(unseenChatTaskNoticeIds.length) : '';
    if (key === 'godview') return String(activeTaskCount);
    if (key === 'edicts') return '';
    if (key === 'templates') return '';
    if (key === 'sessions') return String(visibleSessions.length);
    if (key === 'memorials') return String(unseenCompletedTaskIds.length || edicts.filter((t) => isTerminalState(t.state)).length);
    return '';
  };

  const renderActivePanel = () => {
    if (activeTab === 'chat') return <div id="workspace-panel-chat"><ChatPanel /></div>;
    if (activeTab === 'godview') return <div id="workspace-panel-godview"><GodViewPanel /></div>;
    if (activeTab === 'edicts') return <div id="workspace-panel-edicts"><EdictBoard /></div>;
    if (activeTab === 'officials') return <div id="workspace-panel-officials"><OfficialPanel /></div>;
    if (activeTab === 'models') return <div id="workspace-panel-models"><ModelConfig /></div>;
    if (activeTab === 'skills') return <div id="workspace-panel-skills"><SkillsConfig /></div>;
    if (activeTab === 'imchannels' && publicConfig.features.imChannels) return <div id="workspace-panel-imchannels"><ImChannelsPanel /></div>;
    if (activeTab === 'toolbox' && publicConfig.features.toolbox) return <div id="workspace-panel-toolbox"><ToolboxPanel /></div>;
    if (activeTab === 'sessions') return <div id="workspace-panel-sessions"><SessionsPanel /></div>;
    if (activeTab === 'memorials') return <div id="workspace-panel-memorials"><MemorialPanel /></div>;
    if (activeTab === 'templates') return <div id="workspace-panel-templates"><TemplatePanel /></div>;
    return <div className="empty">该模块已从当前 OSS 版本移除。</div>;
  };

  return (
    <div className="wrap enterprise-wrap enterprise-shell">
      <aside className="workspace-sidebar">
        <div className="workspace-sidebar-brand">
          <div className="workspace-brand-lockup">
            <WorkspaceBrandHero />
            <div className="workspace-sidebar-brand-copy">
              <div className="workspace-sidebar-title" aria-label="RaccoonClaw">
                <span className="workspace-sidebar-title-badge">RaccoonClaw</span>
              </div>
              <div className="workspace-sidebar-copy">协同、调度与交付统一在一个工作台里</div>
            </div>
          </div>
        </div>

        <nav className="workspace-sidebar-nav" aria-label="工作台导航">
          {visibleSidebarGroups.map((group) => (
            <details key={group.key} className="workspace-sidebar-group" open>
              <summary>{group.label}</summary>
              <div className="workspace-sidebar-links">
                {group.items.map((tabKey) => {
                  const tab = TAB_MAP[tabKey];
                  if (!tab) return null;
                  const badge = tabBadge(tabKey);
                  return (
                    <button
                      key={tab.key}
                      type="button"
                      className={`workspace-sidebar-link ${activeTab === tab.key ? 'active' : ''}`}
                      onClick={() => setActiveTab(tab.key)}
                    >
                      <span className="workspace-sidebar-link-copy">
                        <i>{tab.icon}</i>
                        <span>{tab.label}</span>
                      </span>
                      {badge && (
                        <span
                          className={`workspace-sidebar-badge ${
                            tab.key === 'chat' ? 'workspace-sidebar-badge-chat' : ''
                          }`.trim()}
                        >
                          {badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </details>
          ))}
        </nav>

      </aside>

      <main className="workspace-main">
        <section className="workspace-content">
          {renderActivePanel()}
        </section>
      </main>

      <TaskModal />
      <Toaster />
    </div>
  );
}
