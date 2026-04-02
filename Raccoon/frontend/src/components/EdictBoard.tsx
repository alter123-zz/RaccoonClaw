import { useEffect, useState } from 'react';
import {
  useStore,
  isArchived,
  isAutomationTask,
  isSession,
  isScheduledTask,
  getPipeStatus,
  stateLabel,
  deptColor,
  PIPE,
  BOARD_STATE_ORDER,
  canResumeTask,
  canStopTask,
  isTerminalState,
  DEPTS,
  timeAgo,
  normalizeWorkflowState,
} from '../store';
import { api, type Task } from '../api';
import { deptVisibleInMode, getDefaultTargetDept, getVisibleDeptLabels } from '../workbenchModes';
import { selectWorkbenchTasks } from '../workbenchSelectors';
import PageHero from './PageHero';
import { formatBeijingDateTime } from '../time';

const FOCUS_FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'attention', label: '需关注' },
  { key: 'planning', label: '规划中' },
  { key: 'review', label: '待评审' },
  { key: 'execution', label: '执行中' },
  { key: 'scheduled', label: '定时任务' },
  { key: 'delivery', label: '已结束' },
] as const;

const SORT_OPTIONS = [
  { key: 'risk', label: '风险优先' },
  { key: 'recent', label: '最近更新' },
  { key: 'workflow', label: '流程顺序' },
  { key: 'title', label: '标题 A-Z' },
] as const;

const PRIORITY_OPTIONS = [
  { key: 'low', label: '低' },
  { key: 'normal', label: '标准' },
  { key: 'high', label: '高' },
  { key: 'urgent', label: '紧急' },
] as const;

const TASK_KIND_OPTIONS = [
  { key: 'normal', label: '立即执行' },
  { key: 'recurring', label: '定时任务' },
] as const;

const RECURRING_OPTIONS = [
  { key: 'daily', label: '每日' },
  { key: 'weekly', label: '每周' },
  { key: 'monthly', label: '每月' },
] as const;

const FLOW_MODE_LABELS = {
  direct: '总裁办直办',
  light: '轻流程直派',
  full: '完整协作',
} as const;

const WEEKDAY_OPTIONS = [
  { key: '1', label: '周一' },
  { key: '2', label: '周二' },
  { key: '3', label: '周三' },
  { key: '4', label: '周四' },
  { key: '5', label: '周五' },
  { key: '6', label: '周六' },
  { key: '0', label: '周日' },
] as const;

function parseTaskTime(task: Task): number {
  const raw = task.updatedAt || '';
  const ts = raw ? new Date(raw).getTime() : 0;
  return Number.isFinite(ts) ? ts : 0;
}

function taskRiskScore(task: Task): number {
  const state = normalizeWorkflowState(task.state);
  let score = 0;
  const sessionTask = isSession(task);
  if (state === 'Blocked') score += 120;
  if (task.block && task.block !== '无' && task.block !== '-') score += 80;
  if (task.heartbeat?.status === 'stalled') score += 70;
  if (task.heartbeat?.status === 'warn') score += 35;
  if (state === 'ReviewControl' || state === 'Review') score += 24;
  if (sessionTask && (state === 'Doing' || state === 'Review')) score += 28;
  if (state === 'ChiefOfStaff') score += 10;
  if (task.priority === 'urgent') score += 18;
  if (task.priority === 'high') score += 10;
  return score;
}

function riskLabel(task: Task): string {
  const state = normalizeWorkflowState(task.state);
  if (state === 'Blocked' || (task.block && task.block !== '无' && task.block !== '-')) return '阻塞';
  if (task.heartbeat?.status === 'stalled') return '停滞';
  if (task.heartbeat?.status === 'warn') return '预警';
  if (state === 'ReviewControl' || state === 'Review') return '待审';
  return '正常';
}

function priorityLabel(priority?: string): string {
  const found = PRIORITY_OPTIONS.find((item) => item.key === priority);
  return found?.label || '标准';
}

function scheduledSourceMeta(task: Task): Record<string, unknown> {
  const sourceMeta = task.sourceMeta;
  return sourceMeta && typeof sourceMeta === 'object' ? sourceMeta : {};
}

function scheduledActionTaskId(task: Task): string {
  const sourceMeta = scheduledSourceMeta(task);
  const directTarget = String(sourceMeta.target || sourceMeta.taskId || '').trim();
  if (directTarget) return directTarget;
  const jobId = String(sourceMeta.automationJobId || '').trim();
  if (jobId.startsWith('task-')) return jobId.slice(5);
  return task.id;
}

function scheduledRunStatusLabel(task: Task): string {
  const sourceMeta = scheduledSourceMeta(task);
  const lastError = String(sourceMeta.lastError || '').trim();
  const lastRunStatus = String(sourceMeta.lastRunStatus || '').trim();
  const enabled = sourceMeta.enabled;
  const jobEnabled = sourceMeta.jobEnabled;
  if (lastRunStatus === 'cancelled' || enabled === false || jobEnabled === false) {
    return '已取消，不再调度';
  }
  if (lastError) return '上次执行异常';
  if (String(task.org || '').trim() === '调度器') return '等待下一次执行';
  if (normalizeWorkflowState(task.state) === 'Doing') return '本轮执行中';
  if (lastRunStatus === 'queued') return '已入队，待执行';
  if (lastRunStatus === 'ok') return '上次执行成功';
  if (lastRunStatus === 'error') return '上次执行失败';
  return task.now || '等待调度执行';
}

function scheduledDeliveryLabel(task: Task): string {
  const sourceMeta = scheduledSourceMeta(task);
  const status = String(sourceMeta.lastDeliveryStatus || '').trim();
  if (!status) return '尚无投递记录';
  if (status === 'queued') return '已派发到执行链';
  if (status === 'delivered') return '已完成投递';
  if (status === 'error') return '投递失败';
  return status;
}

function scheduledLastRunLabel(task: Task): string {
  const sourceMeta = scheduledSourceMeta(task);
  const raw = String(sourceMeta.lastRunAt || '').trim();
  return raw ? formatBeijingDateTime(raw, { includeSeconds: false }) : '尚未执行';
}

function scheduledNextRunLabel(task: Task): string {
  const sourceMeta = scheduledSourceMeta(task);
  const raw = String(sourceMeta.nextRunAt || '').trim();
  if (raw) return formatBeijingDateTime(raw, { includeSeconds: false });
  return task.eta && task.eta !== '-' ? task.eta : '待确定';
}

function focusMatches(task: Task, focus: string): boolean {
  const state = normalizeWorkflowState(task.state);
  const sessionTask = isSession(task);
  if (focus === 'all') return true;
  if (focus === 'attention') return taskRiskScore(task) >= 35;
  if (focus === 'planning') return state === 'ChiefOfStaff' || state === 'Planning';
  if (focus === 'review') return state === 'ReviewControl' || state === 'Review';
  if (focus === 'execution') return state === 'Assigned' || state === 'Doing' || (sessionTask && state === 'Review');
  if (focus === 'scheduled') return isScheduledTask(task);
  if (focus === 'delivery') return isTerminalState(state);
  return true;
}

function MiniPipe({ task }: { task: Task }) {
  const stages = getPipeStatus(task);
  return (
    <div className="ec-pipe">
      {stages.map((s, i) => (
        <span key={s.key} style={{ display: 'contents' }}>
          <div className={`ep-node ${s.status}`}>
            <div className="ep-icon">{s.icon}</div>
            <div className="ep-name">{s.dept}</div>
          </div>
          {i < stages.length - 1 && <div className="ep-arrow">›</div>}
        </span>
      ))}
    </div>
  );
}

function EdictCard({ task }: { task: Task }) {
  const setModalTaskId = useStore((s) => s.setModalTaskId);
  const toast = useStore((s) => s.toast);
  const loadAll = useStore((s) => s.loadAll);

  const hb = task.heartbeat || { status: 'unknown', label: '⚪' };
  const normalizedState = normalizeWorkflowState(task.state);
  const stCls = 'st-' + (normalizedState || '');
  const deptCls = 'dt-' + (task.org || '').replace(/\s/g, '');
  const curStage = PIPE.find((_, i) => getPipeStatus(task)[i].status === 'active');
  const todos = task.todos || [];
  const todoDone = todos.filter((x) => x.status === 'completed').length;
  const todoTotal = todos.length;
  const canStop = canStopTask(normalizedState);
  const canResume = canResumeTask(normalizedState);
  const archived = isArchived(task);
  const isBlocked = task.block && task.block !== '无' && task.block !== '-';
  const isAwaitingApproval = normalizedState === 'ReviewControl' || normalizedState === 'Review';
  const scheduled = isScheduledTask(task);
  const sessionTask = isSession(task);
  const automationTask = isAutomationTask(task);

  // 判断是否“刚刚更新”（5分钟内）
  const lastUpdateTs = parseTaskTime(task);
  const isJustUpdated = lastUpdateTs > 0 && (Date.now() - lastUpdateTs < 300000);

  const handleAction = async (action: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (action === 'stop' || action === 'cancel') {
      const reason = prompt(action === 'stop' ? '请输入叫停原因：' : '请输入取消原因：');
      if (reason === null) return;
      try {
        const r = await api.taskAction(task.id, action, reason);
        if (r.ok) {
          toast(r.message || '操作成功');
          loadAll();
        } else {
          toast(r.error || '操作失败', 'err');
        }
      } catch {
        toast('服务器连接失败', 'err');
      }
    } else if (action === 'resume') {
      try {
        const r = await api.taskAction(task.id, 'resume', '恢复执行');
        if (r.ok) {
          toast(r.message || '已恢复');
          loadAll();
        } else {
          toast(r.error || '操作失败', 'err');
        }
      } catch {
        toast('服务器连接失败', 'err');
      }
    }
  };

  const handleArchive = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const r = await api.archiveTask(task.id, !task.archived);
      if (r.ok) {
        toast(r.message || '操作成功');
        loadAll();
      } else {
        toast(r.error || '操作失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  return (
    <div
      className={`edict-card${archived ? ' archived' : ''}${isAwaitingApproval ? ' pulse-review' : ''}`}
      onClick={() => setModalTaskId(task.id)}
    >
      {isJustUpdated && <div className="active-dot-ping" title="刚刚有新进展" />}
      {!automationTask && !sessionTask && <MiniPipe task={task} />}
      <div className="ec-headline">
        <div>
          <div className="ec-id">{task.id}</div>
          <div className="ec-title">{task.title || '(无标题)'}</div>
        </div>
        <div className={`risk-pill ${riskLabel(task) === '正常' ? 'normal' : ''}`}>
          {isAwaitingApproval ? '👉 待您审批' : riskLabel(task)}
        </div>
      </div>
      <div className="ec-meta">
        <span className={`tag ${stCls}`}>{stateLabel(task)}</span>
        {task.org && <span className={`tag ${deptCls}`}>{task.org}</span>}
        {scheduled && <span className="tag schedule-tag">⏰ 定时任务</span>}
        {automationTask && <span className="tag target-tag">自动化</span>}
        {sessionTask && <span className="tag target-tag">运行会话</span>}
        {task.targetDept && <span className="tag target-tag">目标 {task.targetDept}</span>}
        <span className={`tag priority-tag pr-${task.priority || 'normal'}`}>优先级 {priorityLabel(task.priority)}</span>
      </div>
      {automationTask && (
        <div className="ec-stage-line">
          自动化计划
          <b>
            {String((task.sourceMeta as Record<string, unknown> | undefined)?.scheduleLabel || task.output || '定时任务')}
          </b>
        </div>
      )}
      {!automationTask && !sessionTask && curStage && (
        <div className="ec-stage-line">
          当前阶段
          <b style={{ color: deptColor(curStage.dept) }}>
            {curStage.dept} · {curStage.action}
          </b>
        </div>
      )}
      {sessionTask && (
        <div className="ec-stage-line">
          当前类型
          <b>OpenClaw 运行会话</b>
        </div>
      )}
      {task.now && task.now !== '-' && <div className="ec-now">{task.now.substring(0, 96)}</div>}
      {(task.review_round || 0) > 0 && (
        <div className="ec-review-round">
          {Array.from({ length: task.review_round || 0 }, (_, i) => (
            <span key={i} className="round-dot">{i + 1}</span>
          ))}
          <span>第 {task.review_round} 轮磋商</span>
        </div>
      )}
      {todoTotal > 0 && (
        <div className="ec-todo-bar">
          <span>📋 {todoDone}/{todoTotal}</span>
          <div className="ec-todo-track">
            <div 
              className={`ec-todo-fill ${todoDone === todoTotal ? 'done' : isBlocked ? 'blocked' : ''}`} 
              style={{ width: `${Math.round((todoDone / todoTotal) * 100)}%` }} 
            />
          </div>
          <span>{todoDone === todoTotal ? '✅ 全部完成' : '🔄 推进中'}</span>
        </div>
      )}
      <div className="ec-footer">
        <span className={`hb ${hb.status}`}>{hb.label}</span>
        {isBlocked && (
          <span className="tag block-tag">🚫 {task.block}</span>
        )}
        <span className="ec-time">{timeAgo(task.updatedAt) || '刚刚更新'}</span>
      </div>
      <div className="ec-actions" onClick={(e) => e.stopPropagation()}>
        {!automationTask && !sessionTask && canStop && (
          <>
            <button className="mini-act" onClick={(e) => handleAction('stop', e)}>⏸ 叫停</button>
            <button className="mini-act danger" onClick={(e) => handleAction('cancel', e)}>🚫 取消</button>
          </>
        )}
        {!automationTask && !sessionTask && canResume && (
          <button className="mini-act" onClick={(e) => handleAction('resume', e)}>▶ 恢复</button>
        )}
        {!automationTask && !sessionTask && archived && !task.archived && (
          <button className="mini-act" onClick={handleArchive}>📦 归档</button>
        )}
        {!automationTask && !sessionTask && !task.archived && isBlocked && (
          <button className="mini-act archive" onClick={handleArchive}>📦 归档阻塞</button>
        )}
        {!automationTask && !sessionTask && task.archived && (
          <button className="mini-act" onClick={handleArchive}>📤 取消归档</button>
        )}
      </div>
    </div>
  );
}

export function TaskMonitorPanel({ singleRow = false }: { singleRow?: boolean }) {
  const liveStatus = useStore((s) => s.liveStatus);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const edictFilter = useStore((s) => s.edictFilter);
  const setEdictFilter = useStore((s) => s.setEdictFilter);
  const boardPreset = useStore((s) => s.boardPreset);
  const consumeBoardPreset = useStore((s) => s.consumeBoardPreset);
  const toast = useStore((s) => s.toast);
  const loadAll = useStore((s) => s.loadAll);
  const setActiveTab = useStore((s) => s.setActiveTab);

  const [query, setQuery] = useState('');
  const [focusFilter, setFocusFilter] = useState<(typeof FOCUS_FILTERS)[number]['key']>('all');
  const [deptFilter, setDeptFilter] = useState('全部部门');
  const [sortBy, setSortBy] = useState<(typeof SORT_OPTIONS)[number]['key']>('risk');
  const [flowModeFilter, setFlowModeFilter] = useState<'all' | 'direct' | 'light' | 'full'>('all');
  const tasks = liveStatus?.tasks || [];
  const { edicts: allEdicts, activeEdicts, archivedEdicts, scheduledEdicts, sessions } = selectWorkbenchTasks(tasks, workbenchMode);
  const boardActiveItems = activeEdicts;
  const boardAllItems = allEdicts;
  const attentionCount = boardActiveItems.filter((task) => taskRiskScore(task) >= 35).length;
  const reviewCount = boardActiveItems.filter((task) => {
    const state = normalizeWorkflowState(task.state);
    return state === 'ReviewControl' || state === 'Review';
  }).length;
  const executionCount = boardActiveItems.filter(
    (task) => {
      const state = normalizeWorkflowState(task.state);
      return state === 'Assigned' || state === 'Doing' || (isSession(task) && state === 'Review');
    }
  ).length;
  useEffect(() => {
    if (!boardPreset) return;
    if (boardPreset.edictFilter) setEdictFilter(boardPreset.edictFilter);
    if (boardPreset.focusFilter) {
      setFocusFilter(boardPreset.focusFilter as (typeof FOCUS_FILTERS)[number]['key']);
    }
    if (boardPreset.deptFilter) setDeptFilter(boardPreset.deptFilter);
    if (typeof boardPreset.query === 'string') setQuery(boardPreset.query);
    if (boardPreset.flowModeFilter) {
      setFlowModeFilter(boardPreset.flowModeFilter as 'all' | 'direct' | 'light' | 'full');
    }
    consumeBoardPreset();
  }, [boardPreset, consumeBoardPreset, setEdictFilter]);

  let edicts: Task[];
  if (edictFilter === 'active') edicts = boardActiveItems;
  else if (edictFilter === 'archived') edicts = archivedEdicts;
  else edicts = boardAllItems;

  edicts = edicts.filter((task) => focusMatches(task, focusFilter));

  if (flowModeFilter !== 'all') {
    edicts = edicts.filter((task) => {
      const flowMode = String(task.sourceMeta?.flowMode || '').trim() || 'full';
      return flowMode === flowModeFilter;
    });
  }

  if (deptFilter !== '全部部门') {
    edicts = edicts.filter((task) => task.org === deptFilter || task.targetDept === deptFilter);
  }

  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery) {
    edicts = edicts.filter((task) => {
      const haystack = [
        task.id,
        task.title,
        task.org,
        task.now,
        task.block,
        task.targetDept,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }

  edicts.sort((a, b) => {
    if (sortBy === 'workflow') {
      return (BOARD_STATE_ORDER[a.state] ?? 9) - (BOARD_STATE_ORDER[b.state] ?? 9);
    }
    if (sortBy === 'recent') {
      return parseTaskTime(b) - parseTaskTime(a);
    }
    if (sortBy === 'title') {
      return (a.title || '').localeCompare(b.title || '', 'zh-Hans-CN');
    }
    return taskRiskScore(b) - taskRiskScore(a) || parseTaskTime(b) - parseTaskTime(a);
  });

  const unArchivedDone = allEdicts.filter((t) => !t.archived && isTerminalState(t.state) && !isScheduledTask(t));

  const deptOptions = ['全部部门', ...DEPTS.filter((dept) => deptVisibleInMode(dept.label, workbenchMode)).map((dept) => dept.label)];

  const handleArchiveAll = async () => {
    if (!confirm('将所有已完成/已取消的任务移入归档？')) return;
    try {
      const r = await api.archiveAllDone();
      if (r.ok) {
        toast(`📦 ${r.count || 0} 个任务已归档`);
        loadAll();
      } else {
        toast(r.error || '批量归档失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const handleScan = async () => {
    try {
      const r = await api.schedulerScan();
      if (r.ok) toast(`🧭 总裁办巡检完成：${r.count || 0} 个动作`);
      else toast(r.error || '巡检失败', 'err');
      loadAll();
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const handleFocusFilter = (key: (typeof FOCUS_FILTERS)[number]['key']) => {
    setFocusFilter(key);
    if (key === 'delivery') {
      setEdictFilter('all');
      return;
    }
    setEdictFilter('active');
  };

  return (
    <div className={`board-monitor-shell ${singleRow ? 'single-row' : ''}`}>
      <div className="board-filter-panel" id="board-filters">
        <div className="board-filter-head">
          <div>
            <div className="mission-panel-title">任务视图</div>
            <div className="board-filter-sub">
              当前显示 {edicts.length} / {boardAllItems.length} 个事项
              ，支持按范围、部门和阶段筛选
              {scheduledEdicts.length > 0 ? ` · 常驻定时任务 ${scheduledEdicts.length}` : ''}
              {sessions.length > 0 ? ` · 运行会话 ${sessions.length}` : ''}
            </div>
          </div>
          <div className="board-filter-actions">
            <span className="board-inline-stat">活跃 {boardActiveItems.length}</span>
            <span className="board-inline-stat warn">需关注 {attentionCount}</span>
            <span className="board-inline-stat accent">待评审 {reviewCount}</span>
            <span className="board-inline-stat ok">执行中 {executionCount}</span>
            <button className="ab-scan" onClick={handleScan}>🧭 总裁办巡检</button>
            <button className="board-link-btn" onClick={() => setActiveTab('templates')}>
              🧩 用模板发起
            </button>
          </div>
        </div>

        <div className="archive-bar">
          <span className="ab-label">范围:</span>
          {(['active', 'archived', 'all'] as const).map((f) => (
            <button
              key={f}
              className={`ab-btn ${edictFilter === f ? 'active' : ''}`}
              onClick={() => setEdictFilter(f)}
            >
              {f === 'active' ? '活跃' : f === 'archived' ? '归档' : '全部'}
            </button>
          ))}
          {unArchivedDone.length > 0 && (
            <button className="ab-btn" onClick={handleArchiveAll}>📦 一键归档</button>
          )}
          <span className="ab-count">
            活跃 {boardActiveItems.length} · 定时 {scheduledEdicts.length} · 运行会话 {sessions.length} · 归档 {archivedEdicts.length} · 共 {boardAllItems.length}
          </span>
        </div>

        <div className="board-filter-row">
          <label className="board-search">
            <span>搜索</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="按任务标题、ID、部门或当前进展搜索"
            />
          </label>

          <label className="board-select">
            <span>部门</span>
            <select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
              {deptOptions.map((dept) => (
                <option key={dept} value={dept}>{dept}</option>
              ))}
            </select>
          </label>

          <label className="board-select">
            <span>排序</span>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as (typeof SORT_OPTIONS)[number]['key'])}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="focus-filters">
          {FOCUS_FILTERS.map((item) => (
            <button
              key={item.key}
              className={`focus-chip ${focusFilter === item.key ? 'active' : ''}`}
              onClick={() => handleFocusFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div
        className={`edict-grid ${singleRow ? 'edict-grid--single-row edict-grid--hidden' : ''}`}
        hidden={singleRow}
        aria-hidden={singleRow}
      >
        {edicts.length === 0 ? (
          <div className="empty board-empty" style={{ gridColumn: '1/-1' }}>
            没有匹配当前筛选条件的任务
            <small>
              试着清空搜索、切换阶段筛选，或者直接在上方快速发起一条新任务。
            </small>
          </div>
        ) : (
          edicts.map((task) => <EdictCard key={task.id} task={task} />)
        )}
      </div>
    </div>
  );
}

export function TaskLaunchPanel() {
  const toast = useStore((s) => s.toast);
  const loadAll = useStore((s) => s.loadAll);
  const setActiveTab = useStore((s) => s.setActiveTab);
  const setEdictFilter = useStore((s) => s.setEdictFilter);
  const setModalTaskId = useStore((s) => s.setModalTaskId);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const liveStatus = useStore((s) => s.liveStatus);
  const visibleDeptLabels = getVisibleDeptLabels(workbenchMode);
  const tasks = liveStatus?.tasks || [];
  const { scheduledEdicts } = selectWorkbenchTasks(tasks, workbenchMode);
  const isRealAutomationTask = (t: Task) => /^JJC-AUTO-/i.test(t.id || '');
  const runningScheduledEdicts = [...scheduledEdicts]
    .filter((task) => {
      const state = normalizeWorkflowState(task.state);
      return !isRealAutomationTask(task) && state !== 'Cancelled' && !isTerminalState(task.state);
    })
    .sort((a, b) => {
      const aEta = Date.parse(String(a.eta || '')) || Number.MAX_SAFE_INTEGER;
      const bEta = Date.parse(String(b.eta || '')) || Number.MAX_SAFE_INTEGER;
      if (aEta !== bEta) return aEta - bEta;
      return parseTaskTime(b) - parseTaskTime(a);
    });

  const [quickTitle, setQuickTitle] = useState('');
  const [quickBrief, setQuickBrief] = useState('');
  const [quickTargetDept, setQuickTargetDept] = useState(getDefaultTargetDept(workbenchMode));
  const [quickPriority, setQuickPriority] = useState('normal');
  const [quickFlowMode, setQuickFlowMode] = useState<'direct' | 'light' | 'full'>('light');
  const [quickTaskKind, setQuickTaskKind] = useState<(typeof TASK_KIND_OPTIONS)[number]['key']>('normal');
  const [quickScheduleMode, setQuickScheduleMode] = useState<(typeof RECURRING_OPTIONS)[number]['key']>('daily');
  const [quickScheduleTime, setQuickScheduleTime] = useState('09:00');
  const [quickWeekday, setQuickWeekday] = useState('1');
  const [quickMonthday, setQuickMonthday] = useState('1');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!visibleDeptLabels.includes(quickTargetDept)) {
      setQuickTargetDept(getDefaultTargetDept(workbenchMode));
    }
  }, [quickTargetDept, visibleDeptLabels, workbenchMode]);

  const scheduleLabel = (() => {
    if (quickTaskKind === 'normal') {
      return '';
    }
    if (quickTaskKind === 'recurring') {
      if (quickScheduleMode === 'daily') return `定时任务 · 每日 ${quickScheduleTime}`;
      if (quickScheduleMode === 'weekly') {
        const weekday = WEEKDAY_OPTIONS.find((item) => item.key === quickWeekday)?.label || '每周';
        return `定时任务 · ${weekday} ${quickScheduleTime}`;
      }
      return `定时任务 · 每月 ${quickMonthday} 日 ${quickScheduleTime}`;
    }
    return '';
  })();

  const handleQuickCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = quickTitle.trim();
    const brief = quickBrief.trim();
    if (title.length < 6) {
      toast('任务标题至少 6 个字，避免被当成闲聊', 'err');
      return;
    }
    setCreating(true);
    try {
      const scheduleLines = [];
      if (quickTaskKind === 'recurring') {
        if (scheduleLabel) scheduleLines.push(`执行频率：${scheduleLabel}`);
      }
      const rawParts = [title, brief, ...scheduleLines].filter(Boolean);
      const r = await api.createTask({
        title,
        org: '总裁办',
        targetDept: quickTargetDept,
        priority: quickPriority,
        flowMode: quickFlowMode,
        params: {
          ...(brief ? { userBrief: brief } : {}),
          rawRequest: rawParts.join('\n\n'),
          taskKind: quickTaskKind,
          scheduleMode: quickTaskKind === 'recurring' ? quickScheduleMode : '',
          scheduleLabel,
          scheduleTime: quickTaskKind === 'recurring' ? quickScheduleTime : '',
          scheduleWeekday: quickTaskKind === 'recurring' && quickScheduleMode === 'weekly' ? quickWeekday : '',
          scheduleMonthday: quickTaskKind === 'recurring' && quickScheduleMode === 'monthly' ? quickMonthday : '',
        },
      });
      if (r.ok) {
        toast(`📋 ${r.taskId} 已创建`, 'ok');
        setQuickTitle('');
        setQuickBrief('');
        setQuickTaskKind('normal');
        setQuickScheduleMode('daily');
        setQuickScheduleTime('09:00');
        setQuickWeekday('1');
        setQuickMonthday('1');
        setEdictFilter('all');
        loadAll();
      } else {
        toast(r.error || '创建任务失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    } finally {
      setCreating(false);
    }
  };

  const handleCancelScheduled = async (task: Task, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    const actionTaskId = scheduledActionTaskId(task);
    if (!confirm(`确定要取消 ${actionTaskId} 吗？`)) return;
    const reason = prompt('请输入取消原因（可留空）：');
    if (reason === null) return;
    try {
      const r = await api.taskAction(actionTaskId, 'cancel', reason);
      if (r.ok) {
        toast(r.message || `${actionTaskId} 已取消`, 'ok');
        loadAll();
      } else {
        toast(r.error || '取消失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  return (
    <div className="board-shell">
      <PageHero
        kicker="发起任务"
        title="统一发起新任务，再由总裁办决定如何分诊和派发。"
        desc=""
      />

      <div className="board-command-grid">
        <form className="quick-create-card" id="quick-create" onSubmit={handleQuickCreate}>
          <div className="qc-kicker">任务表单</div>
          <div className="qc-title">填写任务信息与执行方式</div>
          <div className="qc-sub">
            可立即发起任务或设置定时任务。执行结果统一回收到交付归档。
          </div>

          <div className="qc-fields">
            <label className="qc-field wide">
              <span>任务标题</span>
              <input
                value={quickTitle}
                onChange={(e) => setQuickTitle(e.target.value)}
                placeholder="例如：整理本周产品会议纪要，输出执行清单"
              />
            </label>
            <label className="qc-field">
              <span>任务类型</span>
              <select value={quickTaskKind} onChange={(e) => setQuickTaskKind(e.target.value as (typeof TASK_KIND_OPTIONS)[number]['key'])}>
                {TASK_KIND_OPTIONS.map((option) => (
                  <option key={option.key} value={option.key}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="qc-field">
              <span>建议派发部门</span>
              <select value={quickTargetDept} onChange={(e) => setQuickTargetDept(e.target.value)}>
                {DEPTS.filter((dept) => !['总裁办', '产品规划部', '评审质控部', '交付运营部'].includes(dept.label) && deptVisibleInMode(dept.label, workbenchMode)).map((dept) => (
                  <option key={dept.id} value={dept.label}>{dept.label}</option>
                ))}
              </select>
            </label>
            <label className="qc-field">
              <span>优先级</span>
              <select value={quickPriority} onChange={(e) => setQuickPriority(e.target.value)}>
                {PRIORITY_OPTIONS.map((option) => (
                  <option key={option.key} value={option.key}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="qc-field">
              <span>流转方式</span>
              <select value={quickFlowMode} onChange={(e) => setQuickFlowMode(e.target.value as 'direct' | 'light' | 'full')}>
                <option value="direct">direct · 总裁办直办</option>
                <option value="light">light · 轻流程直派</option>
                <option value="full">full · 完整协作</option>
              </select>
            </label>

            {quickTaskKind === 'recurring' && (
              <>
                <label className="qc-field">
                  <span>执行频率</span>
                  <select value={quickScheduleMode} onChange={(e) => setQuickScheduleMode(e.target.value as (typeof RECURRING_OPTIONS)[number]['key'])}>
                    {RECURRING_OPTIONS.map((option) => (
                      <option key={option.key} value={option.key}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="qc-field">
                  <span>执行时间</span>
                  <input type="time" value={quickScheduleTime} onChange={(e) => setQuickScheduleTime(e.target.value)} />
                </label>
                {quickScheduleMode === 'weekly' && (
                  <label className="qc-field">
                    <span>每周</span>
                    <select value={quickWeekday} onChange={(e) => setQuickWeekday(e.target.value)}>
                      {WEEKDAY_OPTIONS.map((option) => (
                        <option key={option.key} value={option.key}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                )}
                {quickScheduleMode === 'monthly' && (
                  <label className="qc-field">
                    <span>每月日期</span>
                    <select value={quickMonthday} onChange={(e) => setQuickMonthday(e.target.value)}>
                      {Array.from({ length: 28 }, (_, index) => String(index + 1)).map((day) => (
                        <option key={day} value={day}>{day} 日</option>
                      ))}
                    </select>
                  </label>
                )}
              </>
            )}

            <label className="qc-field wide">
              <span>上下文补充（可选）</span>
              <textarea
                value={quickBrief}
                onChange={(e) => setQuickBrief(e.target.value)}
                placeholder="补充目标、约束或期望产出，便于总裁办分诊和下游执行。"
              />
            </label>
          </div>

          <div className="qc-actions">
            <div className="qc-hint">
              {quickTaskKind === 'normal'
                ? '提交后立即由总裁办分诊并派发执行，结果进入交付归档。'
                : `${scheduleLabel || '定时规则待补充'}，后续由调度器按计划反复执行。`}
            </div>
            <div className="qc-action-row">
              <button className="board-link-btn" type="button" onClick={() => setActiveTab('templates')}>
                🧩 用模板发起
              </button>
              <button className="mission-btn primary" type="submit" disabled={creating}>
                {creating ? '创建中...' : '创建任务'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {scheduledEdicts.length > 0 && (
        <div className="scheduled-strip">
          <div className="scheduled-strip-copy">
            <strong>⏰ 定时任务已常驻显示</strong>
            <span>这类自动化任务即使执行完成，也会继续保留在活跃视图里，方便你随时查看配置和最近结果。</span>
          </div>
          <button
            className="board-link-btn"
            type="button"
            onClick={() => {
              setActiveTab('godview');
              setEdictFilter('all');
            }}
          >
            去任务状态查看
          </button>
        </div>
      )}

      <section className="launch-scheduled-panel">
        {runningScheduledEdicts.length ? (
        <div className="launch-scheduled-grid">
            {runningScheduledEdicts.map((task) => {
              const sourceMeta = scheduledSourceMeta(task);
              const schedule = String(sourceMeta.scheduleLabel || task.output || '定时任务');
              const flowMode = String(sourceMeta.flowMode || '').trim();
              const nextRunLabel = scheduledNextRunLabel(task);
              const lastRunLabel = scheduledLastRunLabel(task);
              const deliveryLabel = scheduledDeliveryLabel(task);
              const runStatusLabel = scheduledRunStatusLabel(task);
              const lastError = String(sourceMeta.lastError || '').trim();
              return (
                <button
                  key={task.id}
                  type="button"
                  className="launch-scheduled-card"
                  onClick={() => setModalTaskId(task.id)}
                >
                  <div className="launch-scheduled-card-head">
                    <span className="launch-scheduled-mini-badge">⏰ 定时任务</span>
                    <span className="launch-scheduled-card-est">下次执行 {nextRunLabel}</span>
                  </div>
                  <div className="launch-scheduled-card-top">
                    <span className="launch-scheduled-card-icon">⏰</span>
                    <span className="launch-scheduled-card-title">{task.title || task.id}</span>
                  </div>
                  <div className="launch-scheduled-card-desc">
                    {runStatusLabel}
                  </div>
                  <div className="launch-scheduled-card-outcome">
                    计划：{schedule}
                  </div>
                  <div className="launch-scheduled-card-stats">
                    <div className="launch-scheduled-stat">
                      <span>最近执行</span>
                      <strong>{lastRunLabel}</strong>
                    </div>
                    <div className="launch-scheduled-stat">
                      <span>下一次</span>
                      <strong>{nextRunLabel}</strong>
                    </div>
                    <div className="launch-scheduled-stat">
                      <span>最近投递</span>
                      <strong>{deliveryLabel}</strong>
                    </div>
                  </div>
                  {lastError && (
                    <div className="launch-scheduled-card-error">
                      最近错误：{lastError}
                    </div>
                  )}
                  <div className="launch-scheduled-card-meta">
                    <span className={`tag st-${normalizeWorkflowState(task.state)}`}>{stateLabel(task)}</span>
                    {task.org && <span className="tag target-tag">{task.org}</span>}
                    {flowMode && <span className="tag priority-tag">流程 {FLOW_MODE_LABELS[flowMode as keyof typeof FLOW_MODE_LABELS] || flowMode}</span>}
                  </div>
                  <div className="launch-scheduled-card-foot">
                    <div className="launch-scheduled-card-tags">
                      <span className="tpl-dept">{task.id}</span>
                      <span className="tpl-dept">{timeAgo(task.updatedAt) || '刚刚更新'}</span>
                    </div>
                    <div className="launch-scheduled-card-actions">
                      <button
                        type="button"
                        className="launch-scheduled-card-cancel"
                        onClick={(e) => handleCancelScheduled(task, e)}
                      >
                        取消任务
                      </button>
                      <span className="launch-scheduled-card-go">查看详情</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="launch-scheduled-empty">
            当前没有运行中的定时任务。创建定时任务后，会在这里持续显示运行卡片。
          </div>
        )}
      </section>
    </div>
  );
}

export default function EdictBoard() {
  return <TaskLaunchPanel />;
}
