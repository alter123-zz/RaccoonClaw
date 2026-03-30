import { useEffect, useState, useRef, useCallback } from 'react';
import { useStore, getPipeStatus, deptColor, stateLabel, STATE_LABEL, canAdvanceTask, canResumeTask, canStopTask, isAutomationTask, isTerminalState, normalizeWorkflowState } from '../store';
import { api } from '../api';
import { AGENT_LABELS, displayAgentLabel, sanitizeAgentText } from '../agentRegistry';
import { getTaskReviewProfile } from '../reviewRubric';
import { formatBeijingDateTime, formatBeijingTime, parseTimeValue } from '../time';
import type {
  Task,
  TaskActivityData,
  SchedulerStateData,
  ActivityEntry,
  TodoItem,
  PhaseDuration,
} from '../api';

const NEXT_LABELS: Record<string, string> = {
  ChiefOfStaff: '产品规划部规划',
  Planning: '评审质控部评审',
  ReviewControl: '交付运营部派发',
  Assigned: '开始执行',
  Doing: '进入复核',
  Review: '完成',
};

function fmtStalled(sec: number): string {
  const v = Math.max(0, sec);
  if (v < 60) return `${v}秒`;
  if (v < 3600) return `${Math.floor(v / 60)}分${v % 60}秒`;
  const h = Math.floor(v / 3600);
  const m = Math.floor((v % 3600) / 60);
  return `${h}小时${m}分`;
}

function fmtActivityTime(ts: number | string | undefined): string {
  if (!ts) return '';
  return formatBeijingTime(ts) || String(ts).substring(0, 8);
}

export default function TaskModal() {
  const modalTaskId = useStore((s) => s.modalTaskId);
  const setModalTaskId = useStore((s) => s.setModalTaskId);
  const liveStatus = useStore((s) => s.liveStatus);
  const loadAll = useStore((s) => s.loadAll);
  const toast = useStore((s) => s.toast);

  const [activityData, setActivityData] = useState<TaskActivityData | null>(null);
  const [schedData, setSchedData] = useState<SchedulerStateData | null>(null);
  const laTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const task = liveStatus?.tasks?.find((t) => t.id === modalTaskId) || null;
  const automationTask = task ? isAutomationTask(task) : false;
  const edictTask = task ? /^(?:JJC-|D-|L-|F-)/i.test(task.id || '') : false;

  const fetchActivity = useCallback(async () => {
    if (!modalTaskId) return;
    try {
      const d = await api.taskActivity(modalTaskId);
      setActivityData(d);
    } catch {
      setActivityData(null);
    }
  }, [modalTaskId]);

  const fetchSched = useCallback(async () => {
    if (!modalTaskId) return;
    try {
      const d = await api.schedulerState(modalTaskId);
      setSchedData(d);
    } catch {
      setSchedData(null);
    }
  }, [modalTaskId]);

  useEffect(() => {
    if (!modalTaskId || !task || automationTask) return;
    fetchActivity();
    fetchSched();

    const isDone = isTerminalState(task.state);
    if (!isDone) {
      laTimerRef.current = setInterval(() => {
        fetchActivity();
        fetchSched();
      }, 4000);
    }

    return () => {
      if (laTimerRef.current) {
        clearInterval(laTimerRef.current);
        laTimerRef.current = null;
      }
    };
  }, [modalTaskId, task?.state, fetchActivity, fetchSched, automationTask]);

  // scroll log on new entries
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [activityData?.activity?.length]);

  if (!modalTaskId || !task) return null;

  const close = () => setModalTaskId(null);

  const normalizedState = normalizeWorkflowState(task.state);
  const stages = getPipeStatus(task);
  const activeStage = stages.find((s) => s.status === 'active');
  const hb = task.heartbeat || { status: 'unknown' as const, label: '⚪ 无数据' };
  const flowLog = task.flow_log || [];
  const todos = task.todos || [];
  const todoDone = todos.filter((x) => x.status === 'completed').length;
  const todoTotal = todos.length;
  const canStop = canStopTask(normalizedState);
  const canResume = canResumeTask(normalizedState);
  const reviewProfile = getTaskReviewProfile(task);
  const outputArtifacts = task.outputArtifacts || [];
  const outputDisplayPath = task.resolvedOutput || task.output;
  const blockerFeedback = task.blockerFeedback;
  const automationMeta = (task.sourceMeta as Record<string, unknown> | undefined) || undefined;

  const doTaskAction = async (action: string, reason: string) => {
    try {
      const r = await api.taskAction(task.id, action, reason);
      if (r.ok) {
        toast(r.message || '操作成功', 'ok');
        loadAll();
        close();
      } else {
        toast(r.error || '操作失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const doArchive = async (archived: boolean) => {
    try {
      const r = await api.archiveTask(task.id, archived);
      if (r.ok) {
        toast(r.message || (archived ? '已归档' : '已取消归档'), 'ok');
        loadAll();
        close();
      } else {
        toast(r.error || '归档操作失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const doReview = async (action: string) => {
    const labels: Record<string, string> = { approve: '通过', reject: '打回' };
    const comment = prompt(`${labels[action]} ${task.id}\n\n请输入批注（可留空）：`);
    if (comment === null) return;
    try {
      const r = await api.reviewAction(task.id, action, comment || '');
      if (r.ok) {
        toast(`✅ ${task.id} 已${labels[action]}`, 'ok');
        loadAll();
        close();
      } else {
        toast(r.error || '操作失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const doAdvance = async () => {
    const next = NEXT_LABELS[normalizedState] || '下一步';
    const current = STATE_LABEL[normalizedState] || stateLabel(task);
    const comment = prompt(`⏩ 手动推进 ${task.id}\n当前: ${current} → 下一步: ${next}\n\n请输入说明（可留空）：`);
    if (comment === null) return;
    try {
      const r = await api.advanceState(task.id, comment || '');
      if (r.ok) {
        toast(`⏩ ${r.message}`, 'ok');
        loadAll();
        close();
      } else {
        toast(r.error || '推进失败', 'err');
      }
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const doSchedAction = async (action: string) => {
    if (action === 'scan') {
      try {
        const r = await api.schedulerScan(180);
        if (r.ok) toast(`🔍 扫描完成：${r.count || 0} 个动作`, 'ok');
        else toast(r.error || '扫描失败', 'err');
        fetchSched();
      } catch {
        toast('服务器连接失败', 'err');
      }
      return;
    }
    const labels: Record<string, string> = { retry: '重试', escalate: '升级', rollback: '回滚' };
    const reason = prompt(`请输入${labels[action]}原因（可留空）：`);
    if (reason === null) return;
    const handlers: Record<string, (id: string, r: string) => Promise<{ ok: boolean; message?: string; error?: string }>> = {
      retry: api.schedulerRetry,
      escalate: api.schedulerEscalate,
      rollback: api.schedulerRollback,
    };
    try {
      const r = await handlers[action](task.id, reason);
      if (r.ok) toast(r.message || '操作成功', 'ok');
      else toast(r.error || '操作失败', 'err');
      fetchSched();
      loadAll();
    } catch {
      toast('服务器连接失败', 'err');
    }
  };

  const handleStop = () => {
    const reason = prompt('请输入叫停原因（可留空）：');
    if (reason === null) return;
    doTaskAction('stop', reason);
  };

  const handleCancel = () => {
    if (!confirm(`确定要取消 ${task.id} 吗？`)) return;
    const reason = prompt('请输入取消原因（可留空）：');
    if (reason === null) return;
    doTaskAction('cancel', reason);
  };

  // Scheduler state
  const sched = schedData?.scheduler;
  const stalledSec = schedData?.stalledSec || 0;

  return (
    <div className="modal-bg open" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={close}>✕</button>
        <div className="modal-body">
          <div className="modal-id">{task.id}</div>
          <div className="modal-title">{task.title || '(无标题)'}</div>

          {/* Current Stage Banner */}
          {edictTask && !automationTask && activeStage && (
            <div className="cur-stage">
              <div className="cs-icon">{activeStage.icon}</div>
              <div className="cs-info">
                <div className="cs-dept" style={{ color: deptColor(activeStage.dept) }}>{activeStage.dept}</div>
                <div className="cs-action">当前阶段：{activeStage.action}</div>
              </div>
              <span className={`hb ${hb.status} cs-hb`}>{hb.label}</span>
            </div>
          )}

          {/* Pipeline */}
          {edictTask && !automationTask && (
            <div className="m-pipe">
              {stages.map((s, i) => (
                <div className="mp-stage" key={s.key}>
                  <div className={`mp-node ${s.status}`}>
                    {s.status === 'done' && <div className="mp-done-tick">✓</div>}
                    <div className="mp-icon">{s.icon}</div>
                    <div className="mp-dept" style={s.status === 'active' ? { color: 'var(--acc)' } : s.status === 'done' ? { color: 'var(--ok)' } : {}}>
                      {s.dept}
                    </div>
                    <div className="mp-action">{s.action}</div>
                  </div>
                  {i < stages.length - 1 && (
                    <div className="mp-arrow" style={s.status === 'done' ? { color: 'var(--ok)', opacity: 0.6 } : {}}>→</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {edictTask && !automationTask && (
            <>
              <div className="task-actions">
                {canStop && (
                  <>
                    <button className="btn-action btn-stop" onClick={handleStop}>⏸ 叫停任务</button>
                    <button className="btn-action btn-cancel" onClick={handleCancel}>🚫 取消任务</button>
                  </>
                )}
                {canResume && (
                  <button className="btn-action btn-resume" onClick={() => doTaskAction('resume', '恢复执行')}>▶️ 恢复执行</button>
                )}
                {!task.archived && (task.state === 'Blocked' || (task.block && task.block !== '无' && task.block !== '-')) && (
                  <button
                    className="btn-action"
                    style={{ background: '#fff6eb', color: '#ad6800', border: '1px solid rgba(215, 139, 24, 0.26)' }}
                    onClick={() => doArchive(true)}
                  >
                    📦 归档阻塞任务
                  </button>
                )}
                {task.archived && (
                  <button
                    className="btn-action"
                    style={{ background: '#eef4ff', color: 'var(--acc)', border: '1px solid rgba(22, 119, 255, 0.2)' }}
                    onClick={() => doArchive(false)}
                  >
                    📤 取消归档
                  </button>
                )}
                {['ReviewControl', 'Review'].includes(normalizedState) && (
                  <>
                    <button className="btn-action" style={{ background: '#2ecc8a22', color: '#2ecc8a', border: '1px solid #2ecc8a44' }} onClick={() => doReview('approve')}>✅ 通过</button>
                    <button className="btn-action" style={{ background: '#ff527022', color: '#ff5270', border: '1px solid #ff527044' }} onClick={() => doReview('reject')}>🚫 打回</button>
                  </>
                )}
                {canAdvanceTask(normalizedState) && (
                  <button className="btn-action" style={{ background: '#7c5cfc18', color: '#7c5cfc', border: '1px solid #7c5cfc44' }} onClick={doAdvance}>⏩ 推进到下一步</button>
                )}
              </div>

              <div className="sched-section">
                <div className="sched-head">
                  <span className="sched-title">🧭 总裁办调度</span>
                  <span className="sched-status">
                    {sched ? `${sched.enabled === false ? '已禁用' : '运行中'} · 阈值 ${sched.stallThresholdSec || 180}s` : '加载中...'}
                  </span>
                </div>
                <div className="sched-grid">
                  <div className="sched-kpi"><div className="k">停滞时长</div><div className="v">{fmtStalled(stalledSec)}</div></div>
                  <div className="sched-kpi"><div className="k">重试次数</div><div className="v">{sched?.retryCount || 0}</div></div>
                  <div className="sched-kpi"><div className="k">升级级别</div><div className="v">{!sched?.escalationLevel ? '无' : sched.escalationLevel === 1 ? '评审质控部' : '交付运营部'}</div></div>
                  <div className="sched-kpi"><div className="k">派发状态</div><div className="v">{sched?.lastDispatchStatus || 'idle'}</div></div>
                </div>
                {sched && (
                  <div className="sched-line">
                    {sched.lastProgressAt && <span>最近进展 {formatBeijingDateTime(sched.lastProgressAt)}</span>}
                    {sched.lastDispatchAt && <span>最近派发 {formatBeijingDateTime(sched.lastDispatchAt)}</span>}
                    <span>自动回滚 {sched.autoRollback === false ? '关闭' : '开启'}</span>
                    {sched.lastDispatchAgent && <span>目标 {sched.lastDispatchAgent}</span>}
                  </div>
                )}
                <div className="sched-actions">
                  <button className="sched-btn" onClick={() => doSchedAction('retry')}>🔁 重试派发</button>
                  <button className="sched-btn warn" onClick={() => doSchedAction('escalate')}>📣 升级协调</button>
                  <button className="sched-btn danger" onClick={() => doSchedAction('rollback')}>↩️ 回滚稳定点</button>
                  <button className="sched-btn" onClick={() => doSchedAction('scan')}>🔍 立即扫描</button>
                </div>
              </div>
            </>
          )}

          {automationTask && (
            <div className="m-section">
              <div className="m-sec-label">自动化配置</div>
              <div className="m-rows">
                <div className="m-row">
                  <div className="mr-label">计划</div>
                  <div className="mr-val">{String(automationMeta?.scheduleLabel || task.output || '定时任务')}</div>
                </div>
                <div className="m-row">
                  <div className="mr-label">路由</div>
                  <div className="mr-val">{String(automationMeta?.routeLabel || task.org || '自动化')}</div>
                </div>
                <div className="m-row">
                  <div className="mr-label">通道</div>
                  <div className="mr-val">{String(automationMeta?.channel || '—')} → {String(automationMeta?.target || '—')}</div>
                </div>
                {Boolean(automationMeta?.lastRunAt) && (
                  <div className="m-row">
                    <div className="mr-label">最近执行</div>
                    <div className="mr-val">{formatBeijingDateTime(String(automationMeta?.lastRunAt || ''))}</div>
                  </div>
                )}
                {Boolean(automationMeta?.nextRunAt) && (
                  <div className="m-row">
                    <div className="mr-label">下一次执行</div>
                    <div className="mr-val">{formatBeijingDateTime(String(automationMeta?.nextRunAt || ''))}</div>
                  </div>
                )}
                {Boolean(automationMeta?.lastDeliveryStatus) && (
                  <div className="m-row">
                    <div className="mr-label">最近投递</div>
                    <div className="mr-val">{String(automationMeta?.lastDeliveryStatus || '')}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Todo List */}
          {todoTotal > 0 && (
            <TodoSection todos={todos} todoDone={todoDone} todoTotal={todoTotal} />
          )}

          {edictTask && !automationTask && (
            <div className="m-section review-rubric-section">
              <div className="m-sec-label">评审标准</div>
              <div className="review-rubric-head">
                <span className="review-rubric-title">{reviewProfile.label}</span>
                <span className="review-rubric-note">评审质控部统一按 Blocker / Suggestion / Nit 输出结论</span>
              </div>
              <div className="review-rubric-pills">
                {reviewProfile.requiredChecks.map((item) => (
                  <span key={item.key} className="review-check-pill" title={item.prompt}>
                    {item.label}
                  </span>
                ))}
              </div>
              {reviewProfile.focus.length > 0 && (
                <div className="review-rubric-focus">
                  {reviewProfile.focus.map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
              )}
              <div className="review-level-list">
                {reviewProfile.findingLevels.map((item) => (
                  <div key={item.key} className={`review-level-item ${item.key}`}>
                    <strong>{item.label}</strong>
                    <span>{item.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {blockerFeedback && (
            <div className="m-section blocker-feedback-section">
              <div className="m-sec-label">OpenClaw 阻塞反馈</div>
              <div className="blocker-feedback-summary">
                <strong>{blockerFeedback.summary}</strong>
                <span>{blockerFeedback.awaitingUserAction ? '需要补充配置或授权后才能继续执行。' : '当前已识别到明确阻塞，请先处理后再继续。'}</span>
              </div>
              {blockerFeedback.missingItems.length > 0 && (
                <div className="blocker-feedback-list">
                  <div className="blocker-feedback-title">缺失项</div>
                  {blockerFeedback.missingItems.map((item) => (
                    <div key={item} className="blocker-feedback-item">
                      <span>缺少</span>
                      <strong>{item}</strong>
                    </div>
                  ))}
                </div>
              )}
              {blockerFeedback.actions.length > 0 && (
                <div className="blocker-feedback-list">
                  <div className="blocker-feedback-title">建议下一步</div>
                  {blockerFeedback.actions.map((item) => (
                    <div key={item} className="blocker-feedback-item action">
                      <span>处理</span>
                      <strong>{item}</strong>
                    </div>
                  ))}
                </div>
              )}
              {blockerFeedback.evidence.length > 0 && (
                <div className="blocker-feedback-evidence">
                  {blockerFeedback.evidence.slice(0, 3).map((item) => (
                    <div key={item}>{item}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Basic Info */}
          <div className="m-section">
            <div className="m-rows">
              <div className="m-row">
                <div className="mr-label">状态</div>
                <div className="mr-val">
                  <span className={`tag st-${normalizedState}`}>{stateLabel(task)}</span>
                  {(task.review_round || 0) > 0 && <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 8 }}>共磋商 {task.review_round} 轮</span>}
                </div>
              </div>
              <div className="m-row">
                <div className="mr-label">执行部门</div>
                <div className="mr-val"><span className={`tag dt-${(task.org || '').replace(/\s/g, '')}`}>{task.org || '—'}</span></div>
              </div>
              {task.eta && task.eta !== '-' && (
                <div className="m-row"><div className="mr-label">预计完成</div><div className="mr-val">{task.eta}</div></div>
              )}
              {task.block && task.block !== '无' && task.block !== '-' && (
                <div className="m-row"><div className="mr-label" style={{ color: 'var(--danger)' }}>阻塞项</div><div className="mr-val" style={{ color: 'var(--danger)' }}>{task.block}</div></div>
              )}
              {task.now && task.now !== '-' && (
                <div className="m-row" style={{ gridColumn: '1/-1' }}>
                  <div className="mr-label">当前进展</div>
                  <div className="mr-val" style={{ fontWeight: 400, fontSize: 12 }}>{task.now}</div>
                </div>
              )}
              {task.ac && (
                <div className="m-row" style={{ gridColumn: '1/-1' }}>
                  <div className="mr-label">验收标准</div>
                  <div className="mr-val" style={{ fontWeight: 400, fontSize: 12 }}>{task.ac}</div>
                </div>
              )}
            </div>
          </div>

          {/* Flow Log */}
          {flowLog.length > 0 && (
            <div className="m-section">
              <div className="m-sec-label">流转日志（{flowLog.length} 条）</div>
              <div className="fl-timeline">
                {flowLog.map((fl, i) => {
                  const col = deptColor(fl.from || '');
                  return (
                    <div className="fl-item" key={i}>
                      <div className="fl-time">{formatBeijingTime(fl.at, { includeSeconds: false })}</div>
                      <div className="fl-dot" style={{ background: col }} />
                      <div className="fl-content">
                        <div className="fl-who">
                          <span className="from" style={{ color: col }}>{fl.from}</span>
                          <span style={{ color: 'var(--muted)' }}> → </span>
                          <span className="to" style={{ color: deptColor(fl.to || '') }}>{fl.to}</span>
                        </div>
                        <div className="fl-rem">{sanitizeAgentText(fl.remark || '')}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Output */}
          {(outputArtifacts.length > 0 || (outputDisplayPath && outputDisplayPath !== '-' && outputDisplayPath !== '')) && (
            <div className="m-section">
              <div className="m-sec-label">产出物</div>
              {outputArtifacts.length > 0 ? (
                <div className="output-artifact-list">
                  {outputArtifacts.map((artifact) => (
                    <div key={artifact.path} className="output-artifact-item">
                      <div className="output-artifact-head">
                        <strong>{artifact.name}</strong>
                        <span>{artifact.lastModified || '未知时间'}</span>
                      </div>
                      <div className="output-artifact-meta">
                        <span>{displayAgentLabel(artifact.agentId || '') || AGENT_LABELS[artifact.agentId || ''] || artifact.agentId || artifact.folder || '交付文件'}</span>
                        <code>{artifact.path}</code>
                      </div>
                      {artifact.preview && <div className="output-artifact-preview">{artifact.preview}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <code>{outputDisplayPath}</code>
              )}
            </div>
          )}

          {/* Live Activity */}
          {!automationTask && <LiveActivitySection data={activityData} isDone={isTerminalState(normalizedState)} logRef={logRef} />}
        </div>
      </div>
    </div>
  );
}

function TodoSection({ todos, todoDone, todoTotal }: { todos: TodoItem[]; todoDone: number; todoTotal: number }) {
  return (
    <div className="todo-section">
      <div className="todo-header">
        <div className="m-sec-label" style={{ marginBottom: 0, border: 'none', padding: 0 }}>
          子任务清单（{todoDone}/{todoTotal}）
        </div>
        <div className="todo-progress">
          <div className="todo-bar">
            <div className="todo-bar-fill" style={{ width: `${Math.round((todoDone / todoTotal) * 100)}%` }} />
          </div>
          <span>{Math.round((todoDone / todoTotal) * 100)}%</span>
        </div>
      </div>
      <div className="todo-list">
        {todos.map((td) => {
          const ico = td.status === 'completed' ? '✅' : td.status === 'in-progress' ? '🔄' : '⬜';
          const stLabel = td.status === 'completed' ? '已完成' : td.status === 'in-progress' ? '进行中' : '待开始';
          const stCls = td.status === 'completed' ? 's-done' : td.status === 'in-progress' ? 's-progress' : 's-notstarted';
          const itemCls = td.status === 'completed' ? 'done' : '';
          return (
            <div className={`todo-item ${itemCls}`} key={td.id}>
              <div className="t-row">
                <span className="t-icon">{ico}</span>
                <span className="t-id">#{td.id}</span>
                <span className="t-title">{td.title}</span>
                <span className={`t-status ${stCls}`}>{stLabel}</span>
              </div>
              {td.detail && <div className="todo-detail">{td.detail}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LiveActivitySection({
  data,
  isDone,
  logRef,
}: {
  data: TaskActivityData | null;
  isDone: boolean;
  logRef: React.RefObject<HTMLDivElement | null>;
}) {
  if (!data) return null;

  const activity = data.activity || [];
  const isActive = (() => {
    if (!activity.length) return false;
    const last = activity[activity.length - 1];
    if (!last.at) return false;
    const ts = parseTimeValue(last.at)?.getTime() || 0;
    return Date.now() - ts < 300000;
  })();

  const agentParts: string[] = [];
  if (data.agentLabel) {
    agentParts.push(
      displayAgentLabel(String(data.agentLabel).toLowerCase()) || sanitizeAgentText(data.agentLabel)
    );
  }
  if (data.relatedAgents && data.relatedAgents.length > 1) agentParts.push(`${data.relatedAgents.length}个 Agent`);
  if (data.lastActive) agentParts.push(`最后活跃: ${data.lastActive}`);

  // Phase durations
  const phaseDurations = data.phaseDurations || [];
  const maxDur = Math.max(...phaseDurations.map((p) => p.durationSec || 1), 1);
  const phaseColors: Record<string, string> = {
    '需求方': '#eab308', '总裁办': '#f97316', '产品规划部': '#3b82f6', '评审质控部': '#8b5cf6',
    '交付运营部': '#10b981', '专项团队': '#06b6d4', '品牌内容部': '#ec4899', '经营分析部': '#f59e0b',
    '安全运维部': '#ef4444', '合规测试部': '#6366f1', '工程研发部': '#14b8a6', '人力组织部': '#d946ef',
  };

  // Todos summary
  const ts = data.todosSummary;

  // Resource summary
  const rs = data.resourceSummary;

  // Group non-flow activity by agent
  const flowItems = activity.filter((a) => a.kind === 'flow');
  const nonFlow = activity.filter((a) => a.kind !== 'flow');
  const grouped = new Map<string, ActivityEntry[]>();
  nonFlow.forEach((a) => {
    const key = a.agent || 'unknown';
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(a);
  });

  return (
    <div className="la-section">
      <div className="la-header">
        <span className="la-title">
          <span className={`la-dot${isActive ? '' : ' idle'}`} />
          {isDone ? '执行回顾' : '实时动态'}
        </span>
        <span className="la-agent">{agentParts.join(' · ') || '加载中...'}</span>
      </div>

      {/* Phase Bars */}
      {phaseDurations.length > 0 && (
        <div style={{ padding: '4px 0 8px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600 }}>⏱ 阶段耗时</span>
            {data.totalDuration && <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted)' }}>总耗时 {data.totalDuration}</span>}
          </div>
          {phaseDurations.map((p, i) => {
            const pct = Math.max(5, Math.round(((p.durationSec || 1) / maxDur) * 100));
            const color = phaseColors[p.phase] || '#6b7280';
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '2px 0', fontSize: 11 }}>
                <span style={{ minWidth: 48, color: 'var(--muted)', textAlign: 'right' }}>{p.phase}</span>
                <div style={{ flex: 1, height: 14, background: 'var(--panel)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, opacity: p.ongoing ? 0.6 : 0.85 }} />
                </div>
                <span style={{ minWidth: 60, fontSize: 10, color: 'var(--muted)' }}>
                  {p.durationText}
                  {p.ongoing && <span style={{ fontSize: 9, color: '#60a5fa' }}> ●进行中</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Todos Progress */}
      {ts && (
        <div style={{ padding: '4px 0 8px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600 }}>📊 执行进度</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: ts.percent >= 100 ? '#22c55e' : ts.percent >= 50 ? '#60a5fa' : 'var(--text)' }}>{ts.percent}%</span>
            <span style={{ fontSize: 10, color: 'var(--muted)' }}>✅{ts.completed} 🔄{ts.inProgress} ⬜{ts.notStarted} / 共{ts.total}项</span>
          </div>
          <div style={{ height: 8, background: 'var(--panel)', borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${ts.total ? (ts.completed / ts.total) * 100 : 0}%`, background: '#22c55e', transition: 'width .3s' }} />
            <div style={{ width: `${ts.total ? (ts.inProgress / ts.total) * 100 : 0}%`, background: '#3b82f6', transition: 'width .3s' }} />
          </div>
        </div>
      )}

      {/* Resource Summary */}
      {rs && (rs.totalTokens || rs.totalCost) && (
        <div style={{ padding: '4px 0 8px', borderBottom: '1px solid var(--line)', display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 11, fontWeight: 600 }}>📈 资源消耗</span>
          {rs.totalTokens != null && <span style={{ fontSize: 11, color: 'var(--muted)' }}>🔢 {rs.totalTokens.toLocaleString()} tokens</span>}
          {rs.totalCost != null && <span style={{ fontSize: 11, color: 'var(--muted)' }}>💰 ${rs.totalCost.toFixed(4)}</span>}
          {rs.totalElapsedSec != null && (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
              ⏳ {rs.totalElapsedSec >= 60 ? `${Math.floor(rs.totalElapsedSec / 60)}分` : ''}{rs.totalElapsedSec % 60}秒
            </span>
          )}
        </div>
      )}

      {/* Activity Log */}
      <div className="la-log" ref={logRef as React.RefObject<HTMLDivElement>}>
        {/* Flow entries */}
        {flowItems.length > 0 && (
          <div className="la-flow-wrap">
            {flowItems.map((a, i) => (
              <div className="la-entry la-tool" key={`flow-${i}`}>
                <span className="la-icon">📋</span>
                <span className="la-body"><b>{sanitizeAgentText(a.from || '')}</b> → <b>{sanitizeAgentText(a.to || '')}</b>　{sanitizeAgentText(a.remark || '')}</span>
                <span className="la-time">{fmtActivityTime(a.at)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Grouped entries */}
        {grouped.size > 0 ? (
          <div className="la-groups">
            {Array.from(grouped.entries()).map(([agent, items]) => {
              const label = displayAgentLabel(agent || '') || AGENT_LABELS[agent] || agent || '未标识';
              const last = items[items.length - 1];
              const lastTime = last?.at ? fmtActivityTime(last.at) : '--:--:--';
              return (
                <div className="la-group" key={agent}>
                  <div className="la-group-hd">
                    <span className="name">{label}</span>
                    <span>最近更新 {lastTime}</span>
                  </div>
                  <div className="la-group-bd">
                    {items.map((a, i) => (
                      <ActivityEntryView key={i} entry={a} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          !flowItems.length && (
            <div className="la-empty">
              {data.message || data.error || 'Agent 尚未上报进展（等待 Agent 调用 progress 命令）'}
            </div>
          )
        )}
      </div>
    </div>
  );
}

function ActivityEntryView({ entry: a }: { entry: ActivityEntry }) {
  const time = fmtActivityTime(a.at);
  const agBadge = a.agent ? (
    <span style={{ fontSize: 9, color: 'var(--muted)', background: 'var(--panel)', padding: '1px 4px', borderRadius: 3, marginRight: 4 }}>
      {displayAgentLabel(a.agent || '') || AGENT_LABELS[a.agent] || sanitizeAgentText(a.agent || '')}
    </span>
  ) : null;

  if (a.kind === 'progress') {
    return (
      <div className="la-entry la-assistant">
        <span className="la-icon">🔄</span>
        <span className="la-body">{agBadge}<b>当前进展：</b>{sanitizeAgentText(a.text || '')}</span>
        <span className="la-time">{time}</span>
      </div>
    );
  }

  if (a.kind === 'todos') {
    const items = a.items || [];
    const diffMap = new Map<string, { type: string; from?: string; to?: string }>();
    if (a.diff) {
      (a.diff.changed || []).forEach((c) => diffMap.set(c.id, { type: 'changed', from: c.from, to: c.to }));
      (a.diff.added || []).forEach((c) => diffMap.set(c.id, { type: 'added' }));
    }
    return (
      <div className="la-entry" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>{agBadge}📝 执行计划</div>
        {items.map((td) => {
          const icon = td.status === 'completed' ? '✅' : td.status === 'in-progress' ? '🔄' : '⬜';
          const d = diffMap.get(String(td.id));
          const style: React.CSSProperties = td.status === 'completed'
            ? { opacity: 0.5, textDecoration: 'line-through' }
            : td.status === 'in-progress'
              ? { color: '#60a5fa', fontWeight: 'bold' }
              : {};
          return (
            <div key={td.id} style={style}>
              {icon} {sanitizeAgentText(td.title)}
              {d && d.type === 'changed' && d.to === 'completed' && <span style={{ color: '#22c55e', fontSize: 9, marginLeft: 4 }}>✨刚完成</span>}
              {d && d.type === 'changed' && d.to !== 'completed' && <span style={{ color: '#f59e0b', fontSize: 9, marginLeft: 4 }}>↻{d.from}→{d.to}</span>}
              {d && d.type === 'added' && <span style={{ color: '#3b82f6', fontSize: 9, marginLeft: 4 }}>🆕新增</span>}
            </div>
          );
        })}
        {a.diff?.removed?.map((r) => (
          <div key={r.id} style={{ opacity: 0.4, textDecoration: 'line-through' }}>🗑 {sanitizeAgentText(r.title)}</div>
        ))}
      </div>
    );
  }

  if (a.kind === 'assistant') {
    return (
      <>
        {a.thinking && (
          <div className="la-entry la-thinking">
            <span className="la-icon">💭</span>
            <span className="la-body">{agBadge}{sanitizeAgentText(a.thinking)}</span>
            <span className="la-time">{time}</span>
          </div>
        )}
        {a.tools?.map((tc, i) => (
          <div className="la-entry la-tool" key={i}>
            <span className="la-icon">🔧</span>
            <span className="la-body">{agBadge}<span className="la-tool-name">{tc.name}</span><span className="la-trunc">{tc.input_preview || ''}</span></span>
            <span className="la-time">{time}</span>
          </div>
        ))}
        {a.text && (
          <div className="la-entry la-assistant">
            <span className="la-icon">🤖</span>
            <span className="la-body">{agBadge}{sanitizeAgentText(a.text)}</span>
            <span className="la-time">{time}</span>
          </div>
        )}
      </>
    );
  }

  if (a.kind === 'tool_result') {
    const ok = a.exitCode === 0 || a.exitCode === null || a.exitCode === undefined;
    return (
      <div className={`la-entry la-tool-result ${ok ? 'ok' : 'err'}`}>
        <span className="la-icon">{ok ? '✅' : '❌'}</span>
        <span className="la-body">{agBadge}<span className="la-tool-name">{sanitizeAgentText(a.tool || '')}</span>{a.output ? sanitizeAgentText(a.output).substring(0, 150) : ''}</span>
        <span className="la-time">{time}</span>
      </div>
    );
  }

  if (a.kind === 'user') {
    return (
      <div className="la-entry la-user">
        <span className="la-icon">📥</span>
        <span className="la-body">{agBadge}{sanitizeAgentText(a.text || '')}</span>
        <span className="la-time">{time}</span>
      </div>
    );
  }

  return null;
}
