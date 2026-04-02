import { useEffect, useState } from 'react';
import { useStore, TEMPLATES, TPL_CATS } from '../store';
import type { Template } from '../store';
import { api } from '../api';
import { selectTemplatesByMode } from '../workbenchSelectors';

export default function TemplatePanel() {
  const tplCatFilter = useStore((s) => s.tplCatFilter);
  const setTplCatFilter = useStore((s) => s.setTplCatFilter);
  const pendingTemplateId = useStore((s) => s.pendingTemplateId);
  const setPendingTemplateId = useStore((s) => s.setPendingTemplateId);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const toast = useStore((s) => s.toast);
  const loadAll = useStore((s) => s.loadAll);

  const [formTpl, setFormTpl] = useState<Template | null>(null);
  const [formVals, setFormVals] = useState<Record<string, string>>({});
  const [previewCmd, setPreviewCmd] = useState('');

  let tpls = selectTemplatesByMode(TEMPLATES, workbenchMode, tplCatFilter);
  if (tplCatFilter === '全部') {
    tpls = tpls.filter((t) => t.cat !== '懒人包');
  }

  const openForm = (tpl: Template) => {
    const vals: Record<string, string> = {};
    tpl.params.forEach((p) => {
      vals[p.key] = p.default || '';
    });
    setFormVals(vals);
    setFormTpl(tpl);
    setPreviewCmd('');
  };

  useEffect(() => {
    if (!pendingTemplateId) return;
    const tpl = TEMPLATES.find((item) => item.id === pendingTemplateId);
    if (tpl) {
      setTplCatFilter(tpl.cat);
      openForm(tpl);
    }
    setPendingTemplateId(null);
  }, [pendingTemplateId, setPendingTemplateId, setTplCatFilter]);

  const buildCmd = (tpl: Template) => {
    let cmd = tpl.command;
    for (const p of tpl.params) {
      cmd = cmd.replace(new RegExp('\\{' + p.key + '\\}', 'g'), formVals[p.key] || p.default || '');
    }
    return cmd;
  };

  const preview = () => {
    if (!formTpl) return;
    setPreviewCmd(buildCmd(formTpl));
  };

  const execute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTpl) return;
    const cmd = buildCmd(formTpl);
    if (!cmd.trim()) {
      toast('请填写必填参数', 'err');
      return;
    }

    // Pre-check gateway
    try {
      const st = await api.agentsStatus();
      if (st.ok && st.gateway && !st.gateway.alive) {
        toast('⚠️ Gateway 未启动，任务将无法派发！', 'err');
        if (!confirm('Gateway 未启动，继续？')) return;
      }
    } catch {
      /* ignore */
    }

    if (!confirm(`确认创建任务？\n\n${cmd.substring(0, 200)}${cmd.length > 200 ? '…' : ''}`)) return;

    try {
      const params: Record<string, string> = {};
      for (const p of formTpl.params) {
        params[p.key] = formVals[p.key] || p.default || '';
      }
      const r = await api.createTask({
        title: cmd.substring(0, 120),
        org: '产品规划部',
        targetDept: formTpl.depts[0] || '',
        priority: 'normal',
        templateId: formTpl.id,
        params,
      });
      if (r.ok) {
        toast(`📋 ${r.taskId} 任务已创建`, 'ok');
        setFormTpl(null);
        loadAll();
      } else {
        toast(r.error || '创建任务失败', 'err');
      }
    } catch {
      toast('⚠️ 服务器连接失败', 'err');
    }
  };

  return (
    <div className="tpl-shell">
      <div className="tpl-hero">
        <div className="tpl-hero-main">
          <div className="tpl-hero-kicker">任务模板</div>
          <div className="tpl-hero-title">按模板分类挑选可直接开工的任务。</div>
        </div>
      </div>

      <div className="tpl-cats">
        {TPL_CATS.map((c) => (
          <span
            key={c.name}
            className={`tpl-cat${tplCatFilter === c.name ? ' active' : ''}`}
            onClick={() => setTplCatFilter(c.name)}
          >
            {c.icon} {c.name}
          </span>
        ))}
      </div>

      <div className="tpl-grid">
        {tpls.map((t) => (
          <div className="tpl-card" key={t.id}>
            <div className="tpl-card-head">
              <span className="tpl-mini-badge">{t.badge || t.cat}</span>
              <span className="tpl-est">{t.est} · {t.cost}</span>
            </div>
            <div className="tpl-top">
              <span className="tpl-icon">{t.icon}</span>
              <span className="tpl-name">{t.name}</span>
            </div>
            <div className="tpl-desc">{t.desc}</div>
            {t.outcome && <div className="tpl-outcome">交付结果：{t.outcome}</div>}
            {t.starter && t.starter.length > 0 && (
              <div className="tpl-starter-list">
                {t.starter.map((item) => (
                  <div key={item} className="tpl-starter-item">{item}</div>
                ))}
              </div>
            )}
            <div className="tpl-footer">
              {t.depts.map((d) => (
                <span className="tpl-dept" key={d}>{d}</span>
              ))}
              <button className="tpl-go" onClick={() => openForm(t)}>
                创建任务
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Template Form Modal */}
      {formTpl && (
        <div className="modal-bg open" onClick={() => setFormTpl(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setFormTpl(null)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                任务模板
              </div>
              <div className="tpl-modal-headline">
                {formTpl.icon} {formTpl.name}
              </div>
              <div className="tpl-modal-sub">{formTpl.desc}</div>
              {formTpl.outcome && <div className="tpl-modal-outcome">交付结果：{formTpl.outcome}</div>}
              <div style={{ display: 'flex', gap: 6, marginBottom: 18, flexWrap: 'wrap' }}>
                {formTpl.depts.map((d) => (
                  <span className="tpl-dept" key={d}>{d}</span>
                ))}
                <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>
                  {formTpl.est} · {formTpl.cost}
                </span>
              </div>

              <form className="tpl-form" onSubmit={execute}>
                {formTpl.params.map((p) => (
                  <div className="tpl-field" key={p.key}>
                    <label className="tpl-label">
                      {p.label}
                      {p.required && <span style={{ color: '#ff5270' }}> *</span>}
                    </label>
                    {p.type === 'textarea' ? (
                      <textarea
                        className="tpl-input"
                        style={{ minHeight: 80, resize: 'vertical' }}
                        required={p.required}
                        value={formVals[p.key] || ''}
                        onChange={(e) => setFormVals((v) => ({ ...v, [p.key]: e.target.value }))}
                      />
                    ) : p.type === 'select' ? (
                      <select
                        className="tpl-input"
                        value={formVals[p.key] || p.default || ''}
                        onChange={(e) => setFormVals((v) => ({ ...v, [p.key]: e.target.value }))}
                      >
                        {(p.options || []).map((o) => (
                          <option key={o}>{o}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="tpl-input"
                        type="text"
                        required={p.required}
                        value={formVals[p.key] || ''}
                        onChange={(e) => setFormVals((v) => ({ ...v, [p.key]: e.target.value }))}
                      />
                    )}
                  </div>
                ))}

                {previewCmd && (
                  <div className="tpl-preview">
                    <div className="tpl-preview-title">将发送给产品规划部的任务</div>
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{previewCmd}</div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-g" onClick={preview} style={{ padding: '8px 16px', fontSize: 12 }}>
                    👁 预览任务
                  </button>
                  <button type="submit" className="tpl-go" style={{ padding: '8px 20px', fontSize: 13 }}>
                    📋 创建任务
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
