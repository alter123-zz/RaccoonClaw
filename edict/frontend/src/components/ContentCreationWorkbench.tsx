import type { Task } from '../api';
import { TEMPLATES, deptColor, normalizeWorkflowState, stateLabel, timeAgo } from '../store';

type StageKey = 'planning' | 'review' | 'production' | 'analysis';

function taskTouchesDept(task: Task, dept: string): boolean {
  if (task.org === dept || task.targetDept === dept) return true;
  return (task.flow_log || []).some((entry) => entry.from === dept || entry.to === dept);
}

function contentStage(task: Task): StageKey {
  const state = normalizeWorkflowState(task.state);
  if (taskTouchesDept(task, '经营分析部')) return 'analysis';
  if (state === 'ReviewControl' || state === 'Review' || task.org === '评审质控部') return 'review';
  if (taskTouchesDept(task, '品牌内容部') || task.org === '交付运营部') return 'production';
  return 'planning';
}

function extractChannels(tasks: Task[]) {
  const counts = new Map<string, number>();
  tasks.forEach((task) => {
    const raw = String(task.templateParams?.channels || task.sourceMeta?.channels || '').trim();
    if (!raw) return;
    raw
      .split(/[，,、/]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((channel) => counts.set(channel, (counts.get(channel) || 0) + 1));
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
}

export default function ContentCreationWorkbench({
  activeTasks,
  deliveredTasks,
  focusTasks,
  onOpenTask,
  onOpenTemplate,
  onOpenTemplates,
  onQuickCreate,
}: {
  activeTasks: Task[];
  deliveredTasks: Task[];
  focusTasks: Task[];
  onOpenTask: (taskId: string) => void;
  onOpenTemplate: (templateId: string) => void;
  onOpenTemplates: () => void;
  onQuickCreate: () => void;
}) {
  const buckets: Record<StageKey, Task[]> = {
    planning: [],
    review: [],
    production: [],
    analysis: [],
  };
  activeTasks.forEach((task) => {
    buckets[contentStage(task)].push(task);
  });

  const last7DaysDelivered = deliveredTasks.filter((task) => {
    const ts = new Date(task.updatedAt || '').getTime();
    return Number.isFinite(ts) && ts >= Date.now() - 7 * 24 * 3600 * 1000;
  }).length;
  const topChannels = extractChannels(activeTasks);
  const featuredTemplates = TEMPLATES.filter((template) => (template.modeIds || []).includes('content_creation')).slice(0, 4);
  const stageCards: { key: StageKey; label: string; desc: string; accent: string }[] = [
    { key: 'planning', label: '选题规划', desc: '需求拆解、栏目设计、排期确认', accent: '#1677ff' },
    { key: 'review', label: '审校质控', desc: '审稿、合规检查、结构修订', accent: '#d78b18' },
    { key: 'production', label: '制作发布', desc: '写作、润色、排版、发布动作', accent: '#23a36c' },
    { key: 'analysis', label: '数据复盘', desc: '数据回收、复盘总结、策略调整', accent: '#ff8a45' },
  ];

  return (
    <section className="content-workbench">
      <div className="content-overview-grid">
        <div className="content-overview-card">
          <span>活跃内容事项</span>
          <strong>{activeTasks.length}</strong>
          <small>当前还在推进中的选题、写作和复盘任务</small>
        </div>
        <div className="content-overview-card accent">
          <span>近 7 天交付</span>
          <strong>{last7DaysDelivered}</strong>
          <small>过去一周真正完成并交付的内容任务</small>
        </div>
        <div className="content-overview-card warm">
          <span>制作中</span>
          <strong>{buckets.production.length}</strong>
          <small>正在品牌内容部或交付运营部执行的任务</small>
        </div>
        <div className="content-overview-card highlight">
          <span>复盘中</span>
          <strong>{buckets.analysis.length}</strong>
          <small>经营分析部正在处理的数据复盘与效果分析</small>
        </div>
      </div>

      <div className="content-layout">
        <div className="content-panel">
          <div className="content-panel-head">
            <div>
              <div className="content-panel-kicker">内容流水线</div>
              <div className="content-panel-title">从选题到复盘，直接按内容业务节奏看当前工作面。</div>
            </div>
          </div>
          <div className="content-stage-grid">
            {stageCards.map((stage) => (
              <div key={stage.key} className="content-stage-card" style={{ ['--stage-accent' as string]: stage.accent }}>
                <div className="content-stage-top">
                  <div>
                    <div className="content-stage-name">{stage.label}</div>
                    <div className="content-stage-desc">{stage.desc}</div>
                  </div>
                  <div className="content-stage-count">{buckets[stage.key].length}</div>
                </div>
                <div className="content-stage-list">
                  {buckets[stage.key].length === 0 ? (
                    <div className="content-stage-empty">当前没有任务堆积</div>
                  ) : (
                    buckets[stage.key].slice(0, 3).map((task) => (
                      <button type="button" key={task.id} className="content-task-pill" onClick={() => onOpenTask(task.id)}>
                        <span>{task.title}</span>
                        <small>{stateLabel(task)}</small>
                      </button>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="content-side-stack">
          <div className="content-panel">
            <div className="content-panel-kicker">渠道焦点</div>
            <div className="content-panel-title">当前内容任务最常涉及的发布渠道</div>
            <div className="content-channel-list">
              {topChannels.length === 0 ? (
                <div className="content-stage-empty">还没有渠道参数，建议从内容创作增长包发起。</div>
              ) : (
                topChannels.map(([channel, count]) => (
                  <div key={channel} className="content-channel-item">
                    <span>{channel}</span>
                    <b>{count} 项</b>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="content-panel">
            <div className="content-panel-kicker">快速开工</div>
            <div className="content-panel-title">直接进入内容创作模式下最常用的工作包</div>
            <div className="content-template-list">
              {featuredTemplates.map((template) => (
                <button type="button" key={template.id} className="content-template-item" onClick={() => onOpenTemplate(template.id)}>
                  <div>
                    <span>{template.icon} {template.name}</span>
                    <small>{template.outcome || template.desc}</small>
                  </div>
                  <i>›</i>
                </button>
              ))}
            </div>
            <div className="content-panel-actions">
              <button type="button" className="mission-btn primary" onClick={onQuickCreate}>发起内容需求</button>
              <button type="button" className="mission-btn" onClick={onOpenTemplates}>打开模板中心</button>
            </div>
          </div>
        </div>
      </div>

      <div className="content-panel">
        <div className="content-panel-head">
          <div>
            <div className="content-panel-kicker">重点跟进</div>
            <div className="content-panel-title">优先处理这些内容事项，能最快改善当前创作节奏。</div>
          </div>
        </div>
        <div className="content-focus-list">
          {focusTasks.length === 0 ? (
            <div className="content-stage-empty">当前没有高风险内容任务，可以继续补充选题或安排新发布计划。</div>
          ) : (
            focusTasks.map((task) => (
              <button type="button" key={task.id} className="content-focus-item" onClick={() => onOpenTask(task.id)}>
                <div className="content-focus-head">
                  <span>{task.id}</span>
                  <span>{stateLabel(task)}</span>
                </div>
                <div className="content-focus-title">{task.title}</div>
                <div className="content-focus-meta">
                  <span style={{ color: deptColor(task.org || '品牌内容部') }}>{task.org || '未分配'}</span>
                  <span>{timeAgo(task.updatedAt) || '刚刚更新'}</span>
                  {task.targetDept && <span>目标 {task.targetDept}</span>}
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
