import { useState } from 'react';
import { useStore, isEdict, STATE_LABEL, isTerminalState } from '../store';
import { api } from '../api';
import type { Task, FlowEntry } from '../api';
import { formatBeijingDateTime } from '../time';
import PageHero from './PageHero';

export default function MemorialPanel() {
  const liveStatus = useStore((s) => s.liveStatus);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [detailTask, setDetailTask] = useState<Task | null>(null);
  const toast = useStore((s) => s.toast);

  const tasks = liveStatus?.tasks || [];
  let mems = tasks.filter((t) => isEdict(t) && isTerminalState(t.state));
  if (filter !== 'all') mems = mems.filter((t) => t.state === filter);
  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery) {
    mems = mems.filter((t) => {
      const flowLogText = (t.flow_log || [])
        .map((entry) => [entry.from, entry.to, entry.remark].filter(Boolean).join(' '))
        .join(' ');
      const haystack = [
        t.id,
        t.title,
        t.org,
        t.now,
        t.output,
        t.resolvedOutput,
        flowLogText,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }
  mems = [...mems].sort((a, b) => {
    const aTs = Date.parse(String(a.updatedAt || '')) || 0;
    const bTs = Date.parse(String(b.updatedAt || '')) || 0;
    return bTs - aTs;
  });

  const exportMemorial = (t: Task) => {
    const fl = t.flow_log || [];
    let md = `# 📦 交付报告 · ${t.title}\n\n`;
    md += `- **任务编号**: ${t.id}\n`;
    md += `- **状态**: ${t.state}\n`;
    md += `- **负责部门**: ${t.org}\n`;
    if (fl.length) {
      const startAt = fl[0].at ? formatBeijingDateTime(fl[0].at) : '未知';
      const endAt = fl[fl.length - 1].at ? formatBeijingDateTime(fl[fl.length - 1].at) : '未知';
      md += `- **开始时间**: ${startAt}\n`;
      md += `- **完成时间**: ${endAt}\n`;
    }
    md += `\n## 流转记录\n\n`;
    for (const f of fl) {
      md += `- **${f.from}** → **${f.to}**  \n  ${f.remark}  \n  _${formatBeijingDateTime(f.at)}_\n\n`;
    }
    if (t.output && t.output !== '-') md += `## 产出物\n\n\`${t.output}\`\n`;
    navigator.clipboard.writeText(md).then(
      () => toast('✅ 交付报告已复制为 Markdown', 'ok'),
      () => toast('复制失败', 'err')
    );
  };

  return (
    <div>
      <PageHero
        kicker="交付归档"
        title="集中查看已经完成或取消的任务沉淀。"
        desc=""
      />

      {/* Filter */}
      <div className="tpl-cats mem-filters">
        {[
          { key: 'all', label: '全部' },
          { key: 'Done', label: '✅ 已完成' },
          { key: 'Cancelled', label: '🚫 已取消' },
        ].map((f) => (
          <button
            type="button"
            key={f.key}
            className={`mem-filter${filter === f.key ? ' active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
        <label className="mem-search">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索任务标题、编号、部门或产出物"
          />
        </label>
      </div>

      {/* List */}
      <div className="mem-list">
        {!mems.length ? (
          <div className="mem-empty">暂无交付归档 — 任务完成后自动生成</div>
        ) : (
          mems.map((t) => {
            const fl = t.flow_log || [];
            const depts = [...new Set(fl.map((f) => f.from).concat(fl.map((f) => f.to)).filter((x) => x && x !== '需求方'))];
            const firstAt = fl.length ? formatBeijingDateTime(fl[0].at, { includeSeconds: false }) : '';
            const lastAt = fl.length ? formatBeijingDateTime(fl[fl.length - 1].at, { includeSeconds: false }) : '';
            const stIcon = t.state === 'Done' ? '✅' : '🚫';
            const stateLabel = t.state === 'Done' ? '已完成' : '已取消';
            const headline = t.title || t.id;
            const metaLine = [t.id, t.org || '', `流转 ${fl.length} 步`].filter(Boolean).join(' · ');
            return (
              <div className="mem-card" key={t.id} onClick={() => setDetailTask(t)}>
                <div className="mem-card-head">
                  <span className={`tpl-mini-badge mem-state-badge ${t.state === 'Done' ? 'is-done' : 'is-cancelled'}`}>
                    {stIcon} {stateLabel}
                  </span>
                  <span className="mem-card-meta">{metaLine}</span>
                </div>
                <div className="mem-top">
                  <div className="mem-icon">🧾</div>
                  <div className="mem-name">{headline}</div>
                </div>
                <div className="mem-desc">
                  {t.now && t.now !== '-' ? t.now : '任务已沉淀到交付归档，可点开查看完整流转和产出物。'}
                </div>
                {(t.resolvedOutput || t.output) && (t.resolvedOutput || t.output) !== '-' ? (
                  <div className="mem-outcome">
                    产出物：{t.resolvedOutput || t.output}
                  </div>
                ) : null}
                <div className="mem-footer">
                  <div className="mem-tags">
                    {depts.slice(0, 5).map((d) => (
                      <span className="mem-tag" key={d}>{d}</span>
                    ))}
                  </div>
                  <div className="mem-right">
                    <span className="mem-date">{firstAt}</span>
                    {lastAt !== firstAt && <span className="mem-date">{lastAt}</span>}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Detail Modal */}
      {detailTask && (
        <MemorialDetailModal task={detailTask} onClose={() => setDetailTask(null)} onExport={exportMemorial} />
      )}
    </div>
  );
}

function MemorialDetailModal({
  task: t,
  onClose,
  onExport,
}: {
  task: Task;
  onClose: () => void;
  onExport: (t: Task) => void;
}) {
  const fl = t.flow_log || [];
  const st = t.state || 'Unknown';
  const stIcon = st === 'Done' ? '✅' : st === 'Cancelled' ? '🚫' : '🔄';
  const depts = [...new Set(fl.map((f) => f.from).concat(fl.map((f) => f.to)).filter((x) => x && x !== '需求方'))];
  const toast = useStore((s) => s.toast);
  const [openingPath, setOpeningPath] = useState(false);

  // Reconstruct phases
  const originLog: FlowEntry[] = [];
  const planLog: FlowEntry[] = [];
  const reviewLog: FlowEntry[] = [];
  const execLog: FlowEntry[] = [];
  const resultLog: FlowEntry[] = [];
  const legacyResultMarkers = ['完成', '\u56de\u594f'];
  for (const f of fl) {
    if (f.from === '需求方') originLog.push(f);
    else if (f.to === '产品规划部' || f.from === '产品规划部') planLog.push(f);
    else if (f.to === '评审质控部' || f.from === '评审质控部') reviewLog.push(f);
    else if (f.remark && legacyResultMarkers.some((marker) => f.remark.includes(marker))) resultLog.push(f);
    else execLog.push(f);
  }

  const renderPhase = (title: string, icon: string, items: FlowEntry[]) => {
    if (!items.length) return null;
    return (
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
          {icon} {title}
        </div>
        <div className="md-timeline">
          {items.map((f, i) => {
            const dotCls = f.remark?.includes('✅') ? 'green' : f.remark?.includes('驳') ? 'red' : '';
            return (
              <div className="md-tl-item" key={i}>
                <div className={`md-tl-dot ${dotCls}`} />
                <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                  <span className="md-tl-from">{f.from}</span>
                  <span className="md-tl-to">→ {f.to}</span>
                </div>
                <div className="md-tl-remark">{f.remark}</div>
                <div className="md-tl-time">{formatBeijingDateTime(f.at)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const openOutputPath = async () => {
    const path = t.resolvedOutput || t.output;
    if (!path || path === '-') {
      toast('没有可打开的产出物路径', 'err');
      return;
    }
    setOpeningPath(true);
    try {
      const result = await api.openPath(path);
      if (!result.ok) {
        toast(result.error || result.message || '打开失败', 'err');
      }
    } catch {
      toast('打开失败', 'err');
    } finally {
      setOpeningPath(false);
    }
  };

  return (
    <div className="modal-bg open" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <div className="modal-body">
          <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>{t.id}</div>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>{stIcon} {t.title || t.id}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
            <span className={`tag st-${st}`}>{STATE_LABEL[st] || st}</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{t.org}</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>流转 {fl.length} 步</span>
            {depts.map((d) => (
              <span className="mem-tag" key={d}>{d}</span>
            ))}
          </div>

          {t.now && (
            <div style={{ background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: 'var(--muted)' }}>
              {t.now}
            </div>
          )}

          {renderPhase('原始需求', '👤', originLog)}
          {renderPhase('产品规划', '📋', planLog)}
          {renderPhase('评审质控', '🔍', reviewLog)}
          {renderPhase('专项团队执行', '⚙️', execLog)}
          {renderPhase('交付回传', '📨', resultLog)}

          {t.output && t.output !== '-' && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 4 }}>📦 产出物</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <code style={{ fontSize: 11, wordBreak: 'break-all', flex: 1 }}>{t.resolvedOutput || t.output}</code>
                <button
                  type="button"
                  className="btn btn-g"
                  onClick={openOutputPath}
                  disabled={openingPath}
                  style={{ fontSize: 12, padding: '6px 12px', flexShrink: 0 }}
                >
                  {openingPath ? '打开中…' : '📂 直接打开'}
                </button>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
            <button className="btn btn-g" onClick={() => onExport(t)} style={{ fontSize: 12, padding: '6px 16px' }}>
              📋 复制交付报告
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
