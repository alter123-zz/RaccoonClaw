import { useEffect } from 'react';
import { useStore, STATE_LABEL } from '../store';
import { formatBeijingDateTime } from '../time';
import { selectVisibleAgentsByMode } from '../workbenchSelectors';
import PageHero from './PageHero';

const MEDALS = ['🥇', '🥈', '🥉'];

export default function OfficialPanel() {
  const officialsData = useStore((s) => s.officialsData);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const selectedOfficial = useStore((s) => s.selectedOfficial);
  const setSelectedOfficial = useStore((s) => s.setSelectedOfficial);
  const loadOfficials = useStore((s) => s.loadOfficials);
  const setModalTaskId = useStore((s) => s.setModalTaskId);

  useEffect(() => {
    loadOfficials();
  }, [loadOfficials]);

  if (!officialsData?.officials) {
    return <div className="empty">⚠️ 请确保本地服务器已启动</div>;
  }

  const offs = selectVisibleAgentsByMode(officialsData.officials, workbenchMode);
  if (!offs.length) {
    return <div className="empty">暂无可展示的团队角色</div>;
  }
  const maxTk = Math.max(...offs.map((o) => o.tokens_in + o.tokens_out + o.cache_read + o.cache_write), 1);
  const alive = offs.filter((o) => o.heartbeat?.status === 'active');

  // Selected official detail
  const sel = offs.find((o) => o.id === (selectedOfficial || offs[0]?.id));
  const selId = sel?.id || offs[0]?.id;

  return (
    <div className="official-shell">
      <PageHero
        kicker="团队总览"
        title="查看团队角色的实时产能、成本和分工表现。"
        desc=""
      />

      {/* Activity banner */}
      {alive.length > 0 && (
        <div className="off-activity">
          <span className="off-activity-label">🟢 当前活跃</span>
          {alive.map((o) => (
            <span key={o.id} className="off-activity-chip">{o.emoji} {o.role}</span>
          ))}
          <span className="off-activity-trail">
            其余团队角色待命
          </span>
        </div>
      )}

      {/* Layout: Ranklist + Detail */}
      <div className="off-layout">
        {/* Left: Ranklist */}
        <div className="off-ranklist">
          <div className="orl-hdr">贡献排行</div>
          {offs.map((o) => {
            const hb = o.heartbeat || { status: 'idle' };
            return (
              <div
                key={o.id}
                className={`orl-item${selId === o.id ? ' selected' : ''}`}
                onClick={() => setSelectedOfficial(o.id)}
              >
                <span className="orl-medal">
                  {o.merit_rank <= 3 ? MEDALS[o.merit_rank - 1] : '#' + o.merit_rank}
                </span>
                <span className="orl-emoji">{o.emoji}</span>
                <span className="orl-name">
                  <div className="orl-role">{o.role}</div>
                  <div className="orl-org">{o.label}</div>
                </span>
                <span className="orl-score">{o.merit_score}分</span>
                <span className={`orl-hbdot ${hb.status}`} />
              </div>
            );
          })}
        </div>

        {/* Right: Detail */}
        <div className="off-detail">
          {sel ? (
            <OfficialDetail official={sel} maxTk={maxTk} onOpenTask={setModalTaskId} />
          ) : (
            <div className="empty">选择左侧角色查看详情</div>
          )}
        </div>
      </div>
    </div>
  );
}

function OfficialDetail({
  official: o,
  maxTk,
  onOpenTask,
}: {
  official: NonNullable<ReturnType<typeof useStore.getState>['officialsData']>['officials'][0];
  maxTk: number;
  onOpenTask: (id: string) => void;
}) {
  const hb = o.heartbeat || { status: 'idle', label: '⚪ 待命' };
  const totTk = o.tokens_in + o.tokens_out + o.cache_read + o.cache_write;
  const edicts = o.participated_edicts || [];

  const tkBars = [
    { l: '输入', v: o.tokens_in, color: '#6a9eff' },
    { l: '输出', v: o.tokens_out, color: '#a07aff' },
    { l: '缓存读', v: o.cache_read, color: '#2ecc8a' },
    { l: '缓存写', v: o.cache_write, color: '#f5c842' },
  ];

  return (
    <div className="od-shell">
      <div className="od-hero">
        <div className="od-emoji">{o.emoji}</div>
        <div className="od-head">
          <div className="od-name">{o.role}</div>
          <div className="od-role-line">
            {o.label} · <span className="od-model">{o.model_short || o.model}</span>
          </div>
          <div className="od-rank-line">🏅 {o.rank} · 功绩分 {o.merit_score}</div>
        </div>
        <div className="od-hb">
          <div className={`hb ${hb.status}`}>{hb.label}</div>
          {o.last_active && (
            <div className="od-meta-line">
              活跃 {formatBeijingDateTime(o.last_active, { includeYear: false, includeSeconds: false })}
            </div>
          )}
          <div className="od-meta-line">{o.sessions} 个会话 · {o.messages} 条消息</div>
        </div>
      </div>

      <div className="od-section">
        <div className="od-sec-title">功绩统计</div>
        <div className="od-stats">
          <div className="ods">
            <div className="ods-v ods-v-ok">{o.tasks_done}</div>
            <div className="ods-l">完成任务</div>
          </div>
          <div className="ods">
            <div className="ods-v ods-v-warn">{o.tasks_active}</div>
            <div className="ods-l">执行中</div>
          </div>
          <div className="ods">
            <div className="ods-v ods-v-acc">{o.flow_participations}</div>
            <div className="ods-l">流转参与</div>
          </div>
        </div>
      </div>

      <div className="od-section">
        <div className="od-sec-title">Token 消耗</div>
        {tkBars.map((b) => (
          <div key={b.l} className="tbar">
            <div className="tbar-top">
              <span className="tbar-label">{b.l}</span>
              <span className="tbar-value">{b.v.toLocaleString()}</span>
            </div>
            <div className="tbar-track">
              <div
                className="tbar-fill"
                style={{
                  width: `${maxTk > 0 ? Math.round((b.v / maxTk) * 100) : 0}%`,
                  background: b.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="od-section">
        <div className="od-sec-title">累计费用</div>
        <div className="od-cost">
          <span className={`od-cost-cny ${o.cost_cny > 10 ? 'danger' : o.cost_cny > 3 ? 'warn' : 'ok'}`}>
            <b>¥{o.cost_cny}</b> 人民币
          </span>
          <span className="od-cost-usd"><b>${o.cost_usd}</b> 美元</span>
          <span className="od-cost-total">总计 {totTk.toLocaleString()} tokens</span>
        </div>
      </div>

      <div className="od-section">
        <div className="od-sec-title">参与任务（{edicts.length} 个）</div>
        {edicts.length === 0 ? (
          <div className="od-empty-list">暂无任务记录</div>
        ) : (
          <div className="od-task-list">
            {edicts.map((e) => (
              <div
                key={e.id}
                className="od-task-row"
                onClick={() => onOpenTask(e.id)}
              >
                <span className="od-task-id">{e.id}</span>
                <span className="od-task-title">{e.title.substring(0, 35)}</span>
                <span className={`tag st-${e.state} od-task-state`}>{STATE_LABEL[e.state] || e.state}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
