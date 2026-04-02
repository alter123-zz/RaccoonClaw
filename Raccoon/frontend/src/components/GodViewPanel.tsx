import { useMemo } from 'react';
import { getPipeStatus, isScheduledTask, isTerminalState, normalizeWorkflowState, useStore } from '../store';
import { selectWorkbenchTasks } from '../workbenchSelectors';
import type { Task } from '../api';
import { TaskMonitorPanel } from './EdictBoard';
import PageHero from './PageHero';

type RoomKey = 'command' | 'planning' | 'review' | 'dispatch' | 'execution' | 'blocked';

type RoomDef = {
  key: RoomKey;
  label: string;
  subtitle: string;
};

type Occupant = {
  id: string;
  name: string;
  emoji: string;
  detail: string;
  status: string;
  tone: 'active' | 'queued' | 'warn';
  room: RoomKey;
  taskId: string;
};

type FlowCard = {
  taskId: string;
  title: string;
  status: string;
  tone: 'active' | 'queued' | 'warn';
  route: string[];
  flowMode: string;
};

const ROOM_DEFS: RoomDef[] = [
  { key: 'command', label: '总裁办', subtitle: '统一接单与分诊' },
  { key: 'planning', label: '产品规划部', subtitle: '仅完整流程进入规划' },
  { key: 'review', label: '评审质控部', subtitle: '仅完整流程进入评审' },
  { key: 'dispatch', label: '交付运营部', subtitle: '复核、归档、结构化回传' },
  { key: 'execution', label: '执行部门', subtitle: '工程研发 / 品牌内容 / 经营分析 等' },
  { key: 'blocked', label: '阻塞事项', subtitle: '缺信息、派发失败、等待确认' },
];

function isBlockedTask(task: Task): boolean {
  return normalizeWorkflowState(task.state) === 'Blocked' || Boolean(task.block && task.block !== '无' && task.block !== '-');
}

function stageRoom(dept: string): RoomKey | null {
  if (dept === '需求方' || dept === '结果回传') return null;
  if (dept === '总裁办') return 'command';
  if (dept === '产品规划部') return 'planning';
  if (dept === '评审质控部') return 'review';
  if (dept === '交付运营部') return 'dispatch';
  if (dept === '阻塞事项') return 'blocked';
  return 'execution';
}

function activeStage(task: Task) {
  return getPipeStatus(task).find((stage) => stage.status === 'active') || getPipeStatus(task)[getPipeStatus(task).length - 1];
}

function routeForTask(task: Task): string[] {
  const route = getPipeStatus(task).map((stage) => stage.dept);
  if (isBlockedTask(task) && route[route.length - 1] !== '阻塞事项') {
    route.push('阻塞事项');
  }
  return route;
}

function roomForTask(task: Task): RoomKey {
  if (isBlockedTask(task)) return 'blocked';
  return stageRoom(activeStage(task)?.dept || task.org || '执行部门') || 'execution';
}

function statusForTask(task: Task): string {
  const state = normalizeWorkflowState(task.state);
  if (isBlockedTask(task)) return task.block && task.block !== '无' ? task.block : '阻塞';
  if (state === 'ChiefOfStaff') return '总裁办分诊中';
  if (state === 'Planning') return '产品规划中';
  if (state === 'ReviewControl') return '评审质控中';
  if (state === 'Assigned') return '等待执行';
  if (state === 'Review') return '交付复核中';
  return task.now || '执行中';
}

function toneForTask(task: Task): FlowCard['tone'] {
  const state = normalizeWorkflowState(task.state);
  if (isBlockedTask(task)) return 'warn';
  if (state === 'ChiefOfStaff' || state === 'Planning' || state === 'ReviewControl' || state === 'Assigned' || state === 'Review') {
    return 'queued';
  }
  return 'active';
}

function lastTouched(task: Task): number {
  return Date.parse(String(task.updatedAt || task.sourceMeta?.updatedAt || '')) || 0;
}

export default function GodViewPanel() {
  const liveStatus = useStore((s) => s.liveStatus);
  const setModalTaskId = useStore((s) => s.setModalTaskId);
  const setBoardPreset = useStore((s) => s.setBoardPreset);
  const workbenchMode = useStore((s) => s.workbenchMode);

  const tasks = liveStatus?.tasks || [];
  const { activeEdicts } = selectWorkbenchTasks(tasks, workbenchMode);
  const activeTasks = activeEdicts
    .filter((task) => !task.archived && !isScheduledTask(task))
    .sort((a, b) => lastTouched(b) - lastTouched(a));

  const flowCards = useMemo<FlowCard[]>(
    () =>
      activeTasks.slice(0, 6).map((task) => ({
        taskId: task.id,
        title: task.title || task.id,
        status: statusForTask(task),
        tone: toneForTask(task),
        route: routeForTask(task),
        flowMode: String(task.sourceMeta?.flowMode || 'full'),
      })),
    [activeTasks],
  );

  const roomMap = useMemo(() => {
    const map = new Map<RoomKey, Occupant[]>();
    ROOM_DEFS.forEach((room) => map.set(room.key, []));
    activeTasks.forEach((task) => {
      const stage = activeStage(task);
      const room = roomForTask(task);
      map.get(room)?.push({
        id: task.id,
        name: task.id,
        emoji: stage?.icon || '📋',
        detail: task.title || task.id,
        status: statusForTask(task),
        tone: toneForTask(task),
        room,
        taskId: task.id,
      });
    });
    return map;
  }, [activeTasks]);

  const jumpToTasks = (preset: {
    edictFilter?: 'active' | 'archived' | 'all';
    focusFilter?: string;
    flowModeFilter?: string;
  }) => {
    setBoardPreset({
      edictFilter: 'active',
      focusFilter: 'all',
      flowModeFilter: 'all',
      ...preset,
    });
    const board = document.getElementById('board-filters');
    board?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <section className="godview-shell">
      <PageHero
        kicker="Task Status"
        title="集中查看任务推进、真实流转和部门运行态。"
        desc=""
      />

      <section className="godview-task-zone">
        {flowCards.length > 0 ? (
          <>
            <TaskMonitorPanel singleRow />
          <div className="godview-flow-list">
            {flowCards.map((card) => (
              <button
                key={card.taskId}
                type="button"
                className={`godview-flow-card ${card.tone}`}
                onClick={() => setModalTaskId(card.taskId)}
              >
                <div className="godview-flow-card-top">
                  <strong>{card.taskId}</strong>
                  <span>{card.flowMode}</span>
                </div>
                <div className="godview-flow-card-title">{card.title}</div>
                <div className="godview-flow-route">
                  {card.route.map((stop, index) => (
                    <span key={`${card.taskId}-${stop}-${index}`} className="godview-flow-stop">
                      <span>{stop}</span>
                      {index < card.route.length - 1 && <i />}
                    </span>
                  ))}
                </div>
                <div className="godview-flow-status">{card.status}</div>
              </button>
            ))}
          </div>
          </>
        ) : (
          <>
            <TaskMonitorPanel singleRow />
            <div className="godview-flow-empty">当前没有活跃协同任务。</div>
          </>
        )}
      </section>

      <section className="godview-map">
        <div className="godview-map-head">
          <div>
            <div className="godview-map-kicker">Team Runtime</div>
            <h2>部门运行态</h2>
          </div>
          <p>每个房间显示当前处于该阶段的任务，不再以 gateway 在线/离线作为主指标。</p>
        </div>

        <div className="godview-map-board">
          <div className="godview-map-grid is-lean">
            {ROOM_DEFS.map((room) => {
              const occupants = roomMap.get(room.key) || [];
              const hot = occupants.some((item) => item.tone === 'active' || item.tone === 'warn');
              return (
                <article key={room.key} className={`godview-map-room room-${room.key} ${hot ? 'is-hot' : ''}`}>
                  <div className="godview-map-room-halo" />
                  <div className="godview-map-room-head">
                    <div>
                      <div className="godview-map-room-title">{room.label}</div>
                      <div className="godview-map-room-subtitle">{room.subtitle}</div>
                    </div>
                    <div className="godview-map-room-count">{occupants.length}</div>
                  </div>

                  <div className="godview-map-room-metrics">
                    <span className="active">{occupants.filter((item) => item.tone === 'active').length} 执行</span>
                    <span className="queued">{occupants.filter((item) => item.tone === 'queued').length} 排队</span>
                    <span className="warn">{occupants.filter((item) => item.tone === 'warn').length} 阻塞</span>
                  </div>

                  <div className="godview-map-room-peek">
                    <div className="godview-map-room-scene">
                      <div className="godview-map-room-floor" />
                      <div className="godview-map-room-desk">
                        <div className="godview-map-room-screen" />
                      </div>
                      <div className="godview-map-room-deskline" />
                      <div className="godview-map-room-workers">
                        {occupants.slice(0, room.key === 'command' ? 5 : 4).map((occupant, index) => (
                          <button
                            key={occupant.id}
                            type="button"
                            className={`godview-worker ${occupant.tone}`}
                            style={{ ['--worker-delay' as string]: `${index * 0.18}s` }}
                            onClick={() => setModalTaskId(occupant.taskId)}
                          >
                            <span className="godview-worker-avatar">{occupant.emoji}</span>
                            <span className="godview-worker-dot" />
                            <span className="godview-worker-name">{occupant.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </section>
  );
}
