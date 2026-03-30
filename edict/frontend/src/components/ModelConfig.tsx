import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api } from '../api';
import { formatBeijingDateTime } from '../time';
import { selectVisibleAgentsByMode } from '../workbenchSelectors';
import { displayAgentLabel } from '../agentRegistry';
import PageHero from './PageHero';

function dedupeChiefOfStaffAliases<T extends { id: string }>(agents: T[]): T[] {
  const hasChiefAlias = agents.some((agent) => agent.id === 'chief_of_staff');
  if (!hasChiefAlias) return agents;
  return agents.filter((agent) => agent.id !== 'main');
}

const FALLBACK_MODELS = [
  { id: 'anthropic/claude-sonnet-4-6', l: 'Claude Sonnet 4.6', p: 'Anthropic' },
  { id: 'anthropic/claude-opus-4-5', l: 'Claude Opus 4.5', p: 'Anthropic' },
  { id: 'anthropic/claude-haiku-3-5', l: 'Claude Haiku 3.5', p: 'Anthropic' },
  { id: 'openai/gpt-4o', l: 'GPT-4o', p: 'OpenAI' },
  { id: 'openai/gpt-4o-mini', l: 'GPT-4o Mini', p: 'OpenAI' },
  { id: 'google/gemini-2.5-pro', l: 'Gemini 2.5 Pro', p: 'Google' },
  { id: 'copilot/claude-sonnet-4', l: 'Claude Sonnet 4', p: 'Copilot' },
  { id: 'copilot/claude-opus-4.5', l: 'Claude Opus 4.5', p: 'Copilot' },
  { id: 'copilot/gpt-4o', l: 'GPT-4o', p: 'Copilot' },
  { id: 'copilot/gemini-2.5-pro', l: 'Gemini 2.5 Pro', p: 'Copilot' },
];

const SERVICE_VENDORS = [
  { key: 'deepseek', label: 'DeepSeek' },
  { key: 'zhipu', label: '智谱' },
  { key: 'kimi', label: 'Kimi' },
  { key: 'minimax', label: 'MiniMax' },
  { key: 'qwen', label: '千问' },
  { key: 'openai', label: 'OpenAI' },
  { key: 'anthropic', label: 'Anthropic' },
  { key: 'gemini', label: 'Gemini' },
  { key: 'custom', label: '自定义' },
];

export default function ModelConfig() {
  const agentConfig = useStore((s) => s.agentConfig);
  const agentConfigLoading = useStore((s) => s.agentConfigLoading);
  const agentConfigError = useStore((s) => s.agentConfigError);
  const workbenchMode = useStore((s) => s.workbenchMode);
  const changeLog = useStore((s) => s.changeLog);
  const loadAgentConfig = useStore((s) => s.loadAgentConfig);
  const modelConfigFocusAgentId = useStore((s) => s.modelConfigFocusAgentId);
  const setModelConfigFocusAgentId = useStore((s) => s.setModelConfigFocusAgentId);
  const toast = useStore((s) => s.toast);

  const [selMap, setSelMap] = useState<Record<string, string>>({});
  const [statusMap, setStatusMap] = useState<Record<string, { cls: string; text: string }>>({});
  const [query, setQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [addStatus, setAddStatus] = useState<{ cls: string; text: string } | null>(null);
  const [testStatus, setTestStatus] = useState<{ cls: string; text: string } | null>(null);
  const [addForm, setAddForm] = useState({
    vendorKey: 'deepseek',
    vendorLabel: '',
    baseUrl: '',
    apiProtocol: 'openai',
    apiKey: '',
    authHeader: true,
    modelId: '',
    modelName: '',
    reasoning: false,
    contextWindow: '',
    maxTokens: '',
  });

  useEffect(() => {
    loadAgentConfig();
  }, [loadAgentConfig]);

  useEffect(() => {
    if (agentConfig?.agents) {
      const m: Record<string, string> = {};
      agentConfig.agents.forEach((ag) => {
        m[ag.id] = ag.model;
      });
      setSelMap(m);
    }
  }, [agentConfig]);

  const models = agentConfig?.knownModels?.length
    ? agentConfig.knownModels.map((m) => ({ id: m.id, l: m.label, p: m.provider }))
    : FALLBACK_MODELS;

  const handleSelect = (agentId: string, val: string) => {
    setSelMap((p) => ({ ...p, [agentId]: val }));
  };

  const updateAddForm = (patch: Partial<typeof addForm>) => {
    setAddForm((prev) => ({ ...prev, ...patch }));
  };

  const resetMC = (agentId: string) => {
    const ag = agentConfig?.agents?.find((a) => a.id === agentId);
    if (ag) setSelMap((p) => ({ ...p, [agentId]: ag.model }));
  };

  const applyModel = async (agentId: string) => {
    const model = selMap[agentId];
    if (!model) return;
    setStatusMap((p) => ({ ...p, [agentId]: { cls: 'pending', text: '⟳ 提交中…' } }));
    try {
      const r = await api.setModel(agentId, model);
      if (r.ok) {
        setStatusMap((p) => ({ ...p, [agentId]: { cls: 'ok', text: '✅ 已提交，Gateway 重启中（约5秒）' } }));
        toast(displayAgentLabel(agentId) + ' 模型已更改', 'ok');
        setTimeout(() => loadAgentConfig(), 5500);
      } else {
        setStatusMap((p) => ({ ...p, [agentId]: { cls: 'err', text: '❌ ' + (r.error || '错误') } }));
      }
    } catch {
      setStatusMap((p) => ({ ...p, [agentId]: { cls: 'err', text: '❌ 无法连接服务器' } }));
    }
  };

  const submitAddModel = async () => {
    const vendorKey = addForm.vendorKey.trim();
    const vendorLabel =
      addForm.vendorKey === 'custom'
        ? addForm.vendorLabel.trim()
        : SERVICE_VENDORS.find((item) => item.key === addForm.vendorKey)?.label || addForm.vendorKey;
    if (!vendorKey) {
      setAddStatus({ cls: 'err', text: '❌ 请选择服务商' });
      return;
    }
    if (addForm.vendorKey === 'custom' && !vendorLabel) {
      setAddStatus({ cls: 'err', text: '❌ 自定义服务商需要填写名称' });
      return;
    }
    if (!addForm.modelId.trim() || !addForm.modelName.trim()) {
      setAddStatus({ cls: 'err', text: '❌ 请填写模型 ID 和模型名称' });
      return;
    }
    if (!addForm.baseUrl.trim()) {
      setAddStatus({ cls: 'err', text: '❌ 请填写 Base URL' });
      return;
    }
    setAddStatus({ cls: 'pending', text: '⟳ 正在写入 OpenClaw 配置…' });
    try {
      const result = await api.addModel({
        vendorKey,
        modelId: addForm.modelId.trim(),
        modelName: addForm.modelName.trim(),
        vendorLabel,
        baseUrl: addForm.baseUrl.trim(),
        apiProtocol: addForm.apiProtocol,
        apiKey: addForm.apiKey.trim(),
        authHeader: addForm.authHeader,
        reasoning: addForm.reasoning,
        contextWindow: addForm.contextWindow.trim() ? Number(addForm.contextWindow) : null,
        maxTokens: addForm.maxTokens.trim() ? Number(addForm.maxTokens) : null,
      });
      if (!result.ok) {
        setAddStatus({ cls: 'err', text: '❌ ' + (result.error || '新增失败') });
        return;
      }
      setAddStatus({ cls: 'ok', text: `✅ 已添加 ${result.modelId || addForm.modelId.trim()}` });
      toast(`已添加模型 ${addForm.modelName.trim()}`, 'ok');
      setAddForm({
        vendorKey,
        vendorLabel: addForm.vendorKey === 'custom' ? vendorLabel : '',
        baseUrl: '',
        apiProtocol: 'openai',
        apiKey: '',
        authHeader: true,
        modelId: '',
        modelName: '',
        reasoning: false,
        contextWindow: '',
        maxTokens: '',
      });
      window.setTimeout(() => loadAgentConfig(), 1200);
    } catch {
      setAddStatus({ cls: 'err', text: '❌ 无法连接服务器' });
    }
  };

  const runTest = async () => {
    if (!addForm.baseUrl.trim() || !addForm.modelId.trim()) {
      setTestStatus({ cls: 'err', text: '❌ 请先填写 Base URL 和模型 ID' });
      return;
    }
    setTestStatus({ cls: 'pending', text: '⟳ 正在测试连通性…' });
    try {
      const result = await api.testModel({
        baseUrl: addForm.baseUrl.trim(),
        apiProtocol: addForm.apiProtocol,
        modelId: addForm.modelId.trim(),
        apiKey: addForm.apiKey.trim(),
      });
      if (!result.ok) {
        setTestStatus({ cls: 'err', text: '❌ ' + (result.error || '连通测试失败') });
        return;
      }
      setTestStatus({
        cls: 'ok',
        text: `✅ 连通测试通过${result.durationMs ? `，耗时 ${result.durationMs}ms` : ''}`,
      });
    } catch {
      setTestStatus({ cls: 'err', text: '❌ 连通测试失败' });
    }
  };

  const visibleAgents = dedupeChiefOfStaffAliases(
    selectVisibleAgentsByMode(agentConfig?.agents || [], workbenchMode)
  );
  const filteredAgents = visibleAgents.filter((ag) => {
    const haystack = [ag.id, ag.label, ag.role, ag.model].join(' ').toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  useEffect(() => {
    if (!modelConfigFocusAgentId) return;
    setQuery('');
    window.setTimeout(() => {
      const node = document.getElementById(`model-card-${modelConfigFocusAgentId}`);
      setModelConfigFocusAgentId(null);
      if (!node) return;
      node.classList.remove('model-card-focus');
      void node.clientHeight;
      node.classList.add('model-card-focus');
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      window.setTimeout(() => node.classList.remove('model-card-focus'), 1800);
    }, 80);
  }, [modelConfigFocusAgentId, setModelConfigFocusAgentId]);

  return (
    <div>
      <PageHero
        kicker="模型配置"
        title="统一管理各部门 Agent 的模型选择和外部模型接入。"
        desc=""
      />

      <div className="model-entry-card">
        <div className="model-entry-copy">
          <div className="model-entry-kicker">模型接入</div>
          <div className="model-entry-title">添加模型</div>
          <div className="model-entry-desc">把外部模型服务接入 OpenClaw，再同步到整个工作台。</div>
        </div>
        <button type="button" className="btn btn-p" onClick={() => setShowAddForm(true)}>
          添加模型
        </button>
      </div>

      {showAddForm && (
        <div className="modal-bg open model-add-modal-bg" onClick={() => setShowAddForm(false)}>
          <div className="modal model-add-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close model-add-modal-close" onClick={() => setShowAddForm(false)}>✕</button>
            <div className="model-add-modal-title">添加模型</div>
            <div className="model-add-warning">
              <span className="model-add-warning-icon">!</span>
              <span>添加外部模型即表示你理解并同意自行承担使用风险。</span>
            </div>

            <div className="model-add-form-grid">
              <label className="model-search model-add-field">
                <span>服务商</span>
                <select value={addForm.vendorKey} onChange={(e) => updateAddForm({ vendorKey: e.target.value })}>
                  {SERVICE_VENDORS.map((vendor) => (
                    <option key={vendor.key} value={vendor.key}>
                      {vendor.label}
                    </option>
                  ))}
                </select>
              </label>

              {addForm.vendorKey === 'custom' && (
                <label className="model-search model-add-field">
                  <span>自定义名称</span>
                  <input
                    value={addForm.vendorLabel}
                    onChange={(e) => updateAddForm({ vendorLabel: e.target.value })}
                    placeholder="请输入服务商名称"
                  />
                </label>
              )}

              <label className="model-search model-add-field">
                <span>模型 ID</span>
                <input
                  value={addForm.modelId}
                  onChange={(e) => updateAddForm({ modelId: e.target.value })}
                  placeholder="请输入模型 ID"
                />
              </label>

              <label className="model-search model-add-field">
                <span>显示名称</span>
                <input
                  value={addForm.modelName}
                  onChange={(e) => updateAddForm({ modelName: e.target.value })}
                  placeholder="请输入显示名称"
                />
              </label>

              <label className="model-search model-add-field">
                <span>{addForm.vendorKey === 'custom' ? 'API Key' : `${SERVICE_VENDORS.find((item) => item.key === addForm.vendorKey)?.label || '服务商'} API Key`}</span>
                <input
                  value={addForm.apiKey}
                  onChange={(e) => updateAddForm({ apiKey: e.target.value })}
                  placeholder="请输入 API Key（可选）"
                />
              </label>

              <label className="model-search model-add-field">
                <span>API 协议</span>
                <select
                  value={addForm.apiProtocol}
                  onChange={(e) => updateAddForm({ apiProtocol: e.target.value })}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </label>

              <label className="model-search model-add-field model-add-field--wide">
                <span>Base URL</span>
                <input
                  value={addForm.baseUrl}
                  onChange={(e) => updateAddForm({ baseUrl: e.target.value })}
                  placeholder="https://..."
                />
              </label>

              <label className="model-search model-add-field">
                <span>上下文窗口</span>
                <input
                  value={addForm.contextWindow}
                  onChange={(e) => updateAddForm({ contextWindow: e.target.value })}
                  placeholder="可选"
                />
              </label>

              <label className="model-search model-add-field">
                <span>最大输出 Token</span>
                <input
                  value={addForm.maxTokens}
                  onChange={(e) => updateAddForm({ maxTokens: e.target.value })}
                  placeholder="可选"
                />
              </label>
            </div>

            <div className="model-add-checks">
              <label className="model-add-check">
                <input
                  type="checkbox"
                  checked={addForm.authHeader}
                  onChange={(e) => updateAddForm({ authHeader: e.target.checked })}
                />
                <span>使用 Authorization Header</span>
              </label>
              <label className="model-add-check">
                <input
                  type="checkbox"
                  checked={addForm.reasoning}
                  onChange={(e) => updateAddForm({ reasoning: e.target.checked })}
                />
                <span>推理模型</span>
              </label>
            </div>

            <div className="model-add-test-row">
              <div className="model-add-test-box">
                {testStatus ? (
                  <div className={`mc-st ${testStatus.cls}`}>{testStatus.text}</div>
                ) : (
                  <div className="model-add-test-placeholder">
                    <span className="signal" />
                    <div>
                      <div className="model-add-test-title">尚未测试</div>
                      <div className="model-add-test-sub">会按当前配置真实发起一次请求，用于验证接口是否可用。</div>
                    </div>
                  </div>
                )}
              </div>
              <button type="button" className="btn btn-g model-add-test-btn" onClick={runTest}>
                连通测试
              </button>
            </div>

            {addStatus && <div className={`mc-st ${addStatus.cls}`} style={{ marginTop: 12 }}>{addStatus.text}</div>}

            <div className="model-add-actions">
              <button type="button" className="btn btn-g" onClick={() => setShowAddForm(false)}>
                取消
              </button>
              <button type="button" className="btn btn-p model-add-submit-btn" onClick={submitAddModel}>
                添加
              </button>
            </div>
          </div>
        </div>
      )}

      {agentConfigError && (
        <div className={`model-state-card ${agentConfig?.agents?.length ? 'warn' : 'danger'}`}>
          <div className="model-state-title">
            {agentConfig?.agents?.length ? '模型配置部分刷新失败' : '模型配置暂时不可用'}
          </div>
          <div className="model-state-copy">
            {agentConfigError}
            {agentConfigError === 'Failed to fetch' ? '。本地服务在线但模型配置接口没有成功返回，请稍后重试。' : ''}
          </div>
        </div>
      )}

      {!agentConfig?.agents?.length ? (
        <div className="model-state-card">
          <div className="model-state-title">
            {agentConfigLoading ? '正在加载模型配置…' : '还没有拿到 Agent 模型配置'}
          </div>
          <div className="model-state-copy">
            {agentConfigLoading
              ? '正在向本地服务请求 Agent 配置，请稍等几秒。'
              : '你可以点击上面的“重新加载”再试一次。若仍失败，说明模型配置接口当前没有正确返回。'}
          </div>
        </div>
      ) : (
        <>
          <div className="model-grid">
            {filteredAgents.map((ag) => {
              const sel = selMap[ag.id] || ag.model;
              const changed = sel !== ag.model;
              const st = statusMap[ag.id];
              return (
                <div className="mc-card" id={`model-card-${ag.id}`} key={ag.id}>
                  <div className="mc-top">
                    <span className="mc-emoji">{ag.emoji || '🏛️'}</span>
                    <div>
                      <div className="mc-name">
                        {ag.label}
                      </div>
                      <div className="mc-role">{ag.role}</div>
                    </div>
                  </div>
                  <div className="mc-cur">
                    当前: <b>{ag.model}</b>
                  </div>
                  <select className="msel" value={sel} onChange={(e) => handleSelect(ag.id, e.target.value)}>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.l} ({m.p})
                      </option>
                    ))}
                  </select>
                  <div className="mc-btns">
                    <button className="btn btn-p" disabled={!changed} onClick={() => applyModel(ag.id)}>
                      应用
                    </button>
                    <button className="btn btn-g" onClick={() => resetMC(ag.id)}>
                      重置
                    </button>
                  </div>
                  {st && <div className={`mc-st ${st.cls}`}>{st.text}</div>}
                </div>
              );
            })}
          </div>
          {!filteredAgents.length && (
            <div className="empty board-empty">当前筛选下没有可配置的 Agent</div>
          )}
        </>
      )}

      {/* Change Log */}
      <div style={{ marginTop: 24 }}>
        <div className="sec-title">变更日志</div>
        <div className="cl-list">
          {!changeLog?.length ? (
            <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>暂无变更</div>
          ) : (
            [...changeLog]
              .reverse()
              .slice(0, 15)
              .filter((e) => visibleAgents.some((agent) => agent.id === e.agentId))
              .map((e, i) => (
                <div className="cl-row" key={i}>
                  <span className="cl-t">{formatBeijingDateTime(e.at, { includeSeconds: false })}</span>
                  <span className="cl-a">{displayAgentLabel(e.agentId)}</span>
                  <span className="cl-c">
                    <b>{e.oldModel}</b> → <b>{e.newModel}</b>
                    {e.rolledBack && (
                      <span
                        style={{
                          color: 'var(--danger)',
                          fontSize: 10,
                          border: '1px solid #ff527044',
                          padding: '1px 5px',
                          borderRadius: 3,
                          marginLeft: 4,
                        }}
                      >
                        ⚠ 已回滚
                      </span>
                    )}
                  </span>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
