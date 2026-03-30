import { useStore, getAutomationIndicator, getSyncIndicator, normalizeWorkflowState } from '../store';
import type { AutomationJob, Task } from '../api';
import { formatBeijingDateTime, formatBeijingTime } from '../time';
import { selectWorkbenchTasks } from '../workbenchSelectors';

function taskRiskScore(task: Task): number {
  const state = normalizeWorkflowState(task.state);
  let score = 0;
  if (state === 'Blocked') score += 120;
  if (task.block && task.block !== '无' && task.block !== '-') score += 80;
  if (task.heartbeat?.status === 'stalled') score += 70;
  if (task.heartbeat?.status === 'warn') score += 35;
  if (state === 'ReviewControl' || state === 'Review') score += 28;
  if (state === 'ChiefOfStaff') score += 12;
  return score;
}

function isBlockedTask(task: Task): boolean {
  return normalizeWorkflowState(task.state) === 'Blocked' || Boolean(task.block && task.block !== '无' && task.block !== '-');
}

function isReviewQueueTask(task: Task): boolean {
  const state = normalizeWorkflowState(task.state);
  return state === 'ReviewControl' || state === 'Review';
}

function nextAutomationJob(jobs: AutomationJob[] | undefined) {
  return [...(jobs || [])]
    .filter((job) => job.enabled !== false && typeof job.nextRunAtMs === 'number' && job.status !== 'paused')
    .sort((a, b) => (a.nextRunAtMs || 0) - (b.nextRunAtMs || 0))[0];
}

export default function MissionControl() {
  const liveStatus = useStore((s) => s.liveStatus);
  const activeTab = useStore((s) => s.activeTab);
  const setActiveTab = useStore((s) => s.setActiveTab);
  const setPendingTemplateId = useStore((s) => s.setPendingTemplateId);
  const setBoardPreset = useStore((s) => s.setBoardPreset);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const toast = useStore((s) => s.toast);

  const tasks = liveStatus?.tasks || [];
  const { activeEdicts, terminalEdicts, scheduledEdicts } = selectWorkbenchTasks(tasks, workbenchMode);
  const blockedTasks = activeEdicts.filter((task) => isBlockedTask(task));
  const reviewQueue = activeEdicts.filter((task) => isReviewQueueTask(task));
  const attentionTasks = activeEdicts.filter((task) => taskRiskScore(task) >= 35);
  const deliveredTasks = terminalEdicts;
  const syncIndicator = getSyncIndicator(liveStatus);
  const automationIndicator = getAutomationIndicator(liveStatus);
  const automation = liveStatus?.automation;
  const automationJobs = automation?.jobs || [];
  const automationIncident = automation?.incident;
  const nextJob = nextAutomationJob(automationJobs);
  const directTasks = activeEdicts.filter((task) => String(task.sourceMeta?.flowMode || '') === 'direct').length;
  const lightTasks = activeEdicts.filter((task) => String(task.sourceMeta?.flowMode || '') === 'light').length;
  const fullTasks = activeEdicts.filter((task) => !String(task.sourceMeta?.flowMode || '').trim() || String(task.sourceMeta?.flowMode || '') === 'full').length;

  const deptBuckets: Record<string, number> = {};
  activeEdicts.forEach((task) => {
    const dept = task.org || task.targetDept || '未分配';
    deptBuckets[dept] = (deptBuckets[dept] || 0) + 1;
  });
  const bottleneck = Object.entries(deptBuckets).sort((a, b) => b[1] - a[1])[0];

  const scrollToTarget = (targetId: string, delay = 0) => {
    const attempt = (triesLeft = 8) => {
      const node = document.getElementById(targetId);
      if (node) {
        node.classList.remove('workspace-panel-focus');
        void node.clientHeight;
        node.classList.add('workspace-panel-focus');
        window.setTimeout(() => node.classList.remove('workspace-panel-focus'), 1500);
        node.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      if (triesLeft > 0) {
        window.setTimeout(() => attempt(triesLeft - 1), 120);
      }
    };
    window.setTimeout(() => attempt(), delay);
  };

  const openTabAndScroll = (tab: 'edicts' | 'godview' | 'templates', targetId: string, templateId?: string) => {
    const tabLabel = tab === 'templates' ? '模板中心' : tab === 'godview' ? '状态监控' : '任务中心';
    if (templateId) setPendingTemplateId(templateId);
    if (activeTab !== tab) setActiveTab(tab);
    toast(templateId ? `已打开 ${tabLabel}，并定位到对应模板` : `已打开 ${tabLabel}`, 'ok');
    scrollToTarget(targetId, activeTab === tab ? 0 : 200);
  };

  const openBoardView = (
    preset: {
      edictFilter?: 'active' | 'archived' | 'all';
      focusFilter?: string;
      deptFilter?: string;
      query?: string;
    },
    label: string,
  ) => {
    setBoardPreset({ deptFilter: '全部部门', query: '', ...preset });
    if (activeTab !== 'edicts') setActiveTab('edicts');
    toast(`已切换到任务中心 · ${label}`, 'ok');
    scrollToTarget('workspace-panel-edicts', activeTab === 'edicts' ? 0 : 200);
  };

  const heroSummary = blockedTasks.length > 0
    ? `当前有 ${blockedTasks.length} 个阻塞任务，建议优先清风险链路。`
    : reviewQueue.length > 0
      ? `当前有 ${reviewQueue.length} 个任务等待评审或复核，适合优先清队列。`
      : scheduledEdicts.length > 0
        ? `当前有 ${scheduledEdicts.length} 个定时任务常驻运行，首页会持续显示自动化状态。`
        : activeEdicts.length > 0
          ? `当前共有 ${activeEdicts.length} 个活跃任务在推进，可直接点数字进入对应视图。`
          : '当前没有活跃任务，可以从模板或新建任务开始。';

  const rhythmItems = [
    {
      label: '部门负载',
      value: bottleneck ? bottleneck[0] : '均衡',
      detail: bottleneck ? `${bottleneck[1]} 个活跃任务集中在该部门` : '当前没有明显瓶颈部门',
    },
    {
      label: '下一关键节拍',
      value: nextJob?.nextRunAt ? formatBeijingTime(nextJob.nextRunAt, { includeSeconds: false }) : '待安排',
      detail: nextJob ? `${nextJob.name} · ${nextJob.scheduleLabel || '自动巡检'}` : '当前没有已配置的自动化节点',
    },
    {
      label: '自动化状态',
      value: automationIndicator.label,
      detail: automationIndicator.detail,
    },
    {
      label: '流程裁剪',
      value: `${directTasks}/${lightTasks}/${fullTasks}`,
      detail: 'direct / light / full 当前活跃任务数',
    },
  ];

  return (
    <section className="mission-shell mission-overview">
      <div className="mission-overview-hero">
        <div className="mission-copy">
          <div className="mission-kicker">今日概览</div>
          <h1>企业协同总览</h1>
          <div className="mission-overview-copy">{heroSummary}</div>
          <div className="mission-actions">
            <button type="button" className="mission-btn primary" onClick={() => openTabAndScroll('edicts', 'quick-create')}>
              新建任务
            </button>
            <button type="button" className="mission-btn" onClick={() => openTabAndScroll('templates', 'workspace-panel-templates')}>
              模板中心
            </button>
          </div>
          <div className="mission-note">
            <span className={`signal ${syncIndicator.tone}`} />
            <span>
              {syncIndicator.detail}
              {liveStatus?.generatedAt ? ` · 数据更新时间 ${formatBeijingDateTime(liveStatus.generatedAt)}` : ''}
            </span>
          </div>
        </div>
      </div>

      <div className="mission-metrics mission-metrics-main">
        <button
          type="button"
          className="mission-stat mission-stat-btn"
          onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'all' }, '查看全部活跃任务')}
        >
          <div className="ms-label">活跃任务</div>
          <div className="ms-value">{activeEdicts.length}</div>
          <div className="ms-sub">{scheduledEdicts.length > 0 ? `含 ${scheduledEdicts.length} 个定时自动化` : '正在推进中的协作事项'}</div>
        </button>
        <button
          type="button"
          className="mission-stat mission-stat-btn warning"
          onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'attention' }, '查看需关注任务')}
        >
          <div className="ms-label">需关注</div>
          <div className="ms-value">{attentionTasks.length}</div>
          <div className="ms-sub">阻塞、停滞或等待评审</div>
        </button>
        <button
          type="button"
          className="mission-stat mission-stat-btn accent"
          onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'review' }, '查看评审队列')}
        >
          <div className="ms-label">评审队列</div>
          <div className="ms-value">{reviewQueue.length}</div>
          <div className="ms-sub">等待评审质控或复核</div>
        </button>
        <button
          type="button"
          className="mission-stat mission-stat-btn success"
          onClick={() => openBoardView({ edictFilter: 'all', focusFilter: 'delivery' }, '查看已交付任务')}
        >
          <div className="ms-label">已交付</div>
          <div className="ms-value">{deliveredTasks.length}</div>
          <div className="ms-sub">已进入完成或归档阶段</div>
        </button>
      </div>

      {automationIncident && (
        <div className={`incident-panel ${automationIncident.tone}`}>
          <div className="incident-head">
            <div>
              <div className="mission-panel-title">自动化告警</div>
              <div className="incident-sub">已自动归并成统一事故视图，可按责任部门处理。</div>
            </div>
            <div className={`incident-badge ${automationIncident.tone}`}>{automationIncident.severityLabel}</div>
          </div>
          <div className="incident-title">{automationIncident.title}</div>
          <div className="incident-summary">{automationIncident.summary}</div>
        </div>
      )}

      <div className="mission-main-grid mission-overview-grid">
        <div className="mission-rhythm">
          <div className="mission-panel-title">运行节奏</div>
          <div className="rhythm-list">
            {rhythmItems.map((item) => (
              <div key={item.label} className="rhythm-item">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.detail}</small>
              </div>
            ))}
          </div>
        </div>

        <div className="mission-overview-side">
          <div className="mission-side-card">
            <div className="mission-panel-title">快速提醒</div>
            <div className="mission-reminder-list">
              <button type="button" className="mission-reminder-item" onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'attention' }, '查看阻塞和高风险任务')}>
                <span>阻塞任务</span>
                <strong>{blockedTasks.length}</strong>
              </button>
              <button type="button" className="mission-reminder-item" onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'review' }, '查看评审队列')}>
                <span>待评审</span>
                <strong>{reviewQueue.length}</strong>
              </button>
              <button type="button" className="mission-reminder-item" onClick={() => openTabAndScroll('godview', 'workspace-panel-godview')}>
                <span>团队活跃</span>
                <strong>{activeEdicts.filter((task) => normalizeWorkflowState(task.state) === 'Doing').length}</strong>
              </button>
            </div>
          </div>

          {scheduledEdicts.length > 0 && (
            <div className="mission-side-card">
              <div className="mission-panel-title">自动化常驻任务</div>
              <div className="mission-side-card-copy">
                {scheduledEdicts[0].title}
                {scheduledEdicts.length > 1 ? ` 等 ${scheduledEdicts.length} 个任务持续运行中。` : ' 当前保持常驻。'}
              </div>
              <button
                type="button"
                className="mission-btn"
                onClick={() => openBoardView({ edictFilter: 'active', focusFilter: 'scheduled' }, '查看定时任务')}
              >
                查看任务
              </button>
            </div>
          )}

          <div className="mission-side-card">
            <div className="mission-panel-title">流程裁剪</div>
            <div className="mission-side-card-value">{directTasks} / {lightTasks} / {fullTasks}</div>
            <div className="mission-side-card-copy">
              当前活跃任务按 direct、light、full 三条路径分流。总裁办统一接单，交付结果统一归档。
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
