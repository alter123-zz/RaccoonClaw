import { useEffect, useMemo, useState } from 'react';
import { api, type ImChannelCheck, type ImChannelKey, type ImChannelStatus } from '../api';
import { useStore } from '../store';
import { formatBeijingDateTime } from '../time';
import PageHero from './PageHero';
import weixinIcon from '../assets/imchannels/weixin.png';
import feishuIcon from '../assets/imchannels/feishu.png';
import wecomIcon from '../assets/imchannels/wecom.png';
import dingtalkIcon from '../assets/imchannels/dingtalk.webp';
import qqIcon from '../assets/imchannels/qq.png';

type ChannelFormState = Record<string, string | boolean>;

const CHANNEL_ORDER: ImChannelKey[] = ['weixin', 'feishu', 'wecom', 'dingtalk', 'qqbot'];

const QUICK_CHANNELS: { key: ImChannelKey; label: string }[] = [
  { key: 'feishu', label: '飞书' },
  { key: 'wecom', label: '企业微信' },
  { key: 'dingtalk', label: '钉钉' },
  { key: 'qqbot', label: 'QQ Bot' },
  { key: 'weixin', label: '微信' },
];

const DEFAULT_FORMS: Record<ImChannelKey, ChannelFormState> = {
  feishu: { appId: '', appSecret: '', domain: 'feishu', botName: '' },
  wecom: { botId: '', botSecret: '', botName: '', wsUrl: '' },
  dingtalk: { clientId: '', clientSecret: '', pluginInstalled: false },
  qqbot: { appId: '', appSecret: '', privateChatPolicy: 'open' },
  weixin: { pluginInstalled: false, environmentStatus: '' },
};

function statusTone(status: ImChannelStatus['status']) {
  if (status === 'configured') return 'ok';
  if (status === 'disabled') return 'muted';
  if (status === 'error') return 'err';
  return 'warn';
}

function buildFormState(channel: ImChannelStatus | null): ChannelFormState {
  if (!channel) return {};
  const summary = channel.configSummary || {};
  switch (channel.key) {
    case 'feishu':
      return {
        appId: String(summary['App ID'] || ''),
        appSecret: '',
        domain: String(summary['域名'] || 'feishu'),
        botName: String(summary['Bot 名称'] || ''),
      };
    case 'wecom':
      return {
        botId: String(summary['Bot ID'] || ''),
        botSecret: '',
        botName: '',
        wsUrl: '',
      };
    case 'dingtalk':
      return {
        clientId: String(summary['Client ID'] || ''),
        clientSecret: '',
        pluginInstalled: String(summary['插件状态'] || '') === '已安装',
      };
    case 'qqbot':
      return {
        appId: String(summary['App ID'] || ''),
        appSecret: '',
        privateChatPolicy: String(summary['私聊策略'] || 'open'),
      };
    case 'weixin':
      return {
        pluginInstalled: String(summary['插件状态'] || '') === '已安装',
        environmentStatus: String(summary['环境状态'] || ''),
      };
    default:
      return {};
  }
}

function ChecksBlock({ checks }: { checks: ImChannelCheck[] }) {
  if (!checks.length) return null;
  return (
    <div className="imch-checks">
      {checks.map((check) => (
        <div key={check.key} className={`imch-check ${check.ok ? 'ok' : 'warn'}`}>
          <span>{check.label}</span>
          <b>{check.detail || (check.ok ? '通过' : '未完成')}</b>
        </div>
      ))}
    </div>
  );
}

function ChannelBrandIcon({
  channelKey,
  className = '',
}: {
  channelKey: ImChannelKey;
  className?: string;
}) {
  const srcMap: Record<ImChannelKey, string> = {
    weixin: weixinIcon,
    feishu: feishuIcon,
    wecom: wecomIcon,
    dingtalk: dingtalkIcon,
    qqbot: qqIcon,
  };
  const altMap: Record<ImChannelKey, string> = {
    weixin: '微信',
    feishu: '飞书',
    wecom: '企业微信',
    dingtalk: '钉钉',
    qqbot: 'QQ',
  };
  return (
    <span className={`imch-brand-icon imch-brand-${channelKey} ${className}`.trim()} aria-hidden="true">
      <img src={srcMap[channelKey]} alt={altMap[channelKey]} />
    </span>
  );
}

export default function ImChannelsPanel() {
  const toast = useStore((s) => s.toast);
  const [loading, setLoading] = useState(false);
  const [channels, setChannels] = useState<ImChannelStatus[]>([]);
  const [checkedAt, setCheckedAt] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<ImChannelKey | null>(null);
  const [forms, setForms] = useState<Record<ImChannelKey, ChannelFormState>>(DEFAULT_FORMS);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; checks: ImChannelCheck[] } | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.imChannelsStatus();
      setChannels((data.channels || []).slice().sort((a, b) => CHANNEL_ORDER.indexOf(a.key) - CHANNEL_ORDER.indexOf(b.key)));
      setCheckedAt(data.checkedAt || '');
    } catch {
      toast('IM 频道状态加载失败', 'err');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const configuredChannels = useMemo(
    () => channels.filter((item) => item.status !== 'draft' || item.configured || item.enabled),
    [channels],
  );
  const enabledCount = configuredChannels.filter((item) => item.enabled).length;
  const errorCount = channels.filter((item) => item.status === 'error').length;

  const openEditor = (channelKey: ImChannelKey) => {
    const channel = channels.find((item) => item.key === channelKey) || null;
    setForms((prev) => ({ ...prev, [channelKey]: { ...DEFAULT_FORMS[channelKey], ...buildFormState(channel) } }));
    setEditingKey(channelKey);
    setPickerOpen(false);
    setTestResult(null);
  };

  const closeEditor = () => {
    setEditingKey(null);
    setTestResult(null);
  };

  const updateField = (channelKey: ImChannelKey, patch: ChannelFormState) => {
    setForms((prev) => ({ ...prev, [channelKey]: { ...prev[channelKey], ...patch } }));
  };

  const runTest = async () => {
    if (!editingKey) return;
    setBusyAction(`test:${editingKey}`);
    try {
      const result = await api.imChannelsTest({ channelKey: editingKey, config: forms[editingKey] });
      setTestResult({
        ok: !!result.ok,
        message: result.message || result.error || (result.ok ? '检查通过' : '检查失败'),
        checks: result.checks || [],
      });
      if (result.ok) {
        toast('检查通过', 'ok');
      } else {
        toast(result.error || result.message || '仍有未完成项', 'err');
      }
    } catch {
      toast('检查失败', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const saveChannel = async () => {
    if (!editingKey) return;
    setBusyAction(`save:${editingKey}`);
    try {
      const result = await api.imChannelsUpsert({
        channelKey: editingKey,
        enabled: true,
        setupMode: channels.find((item) => item.key === editingKey)?.setupMode || '',
        config: forms[editingKey],
      });
      if (!result.ok) {
        toast(result.error || result.message || '保存失败', 'err');
        return;
      }
      toast(`${channels.find((item) => item.key === editingKey)?.label || '频道'} 已保存`, 'ok');
      await refresh();
      closeEditor();
    } catch {
      toast('保存失败', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const toggleChannel = async (channel: ImChannelStatus) => {
    setBusyAction(`toggle:${channel.key}`);
    try {
      const result = await api.imChannelsToggle(channel.key, !channel.enabled);
      if (!result.ok) {
        toast(result.error || result.message || '状态更新失败', 'err');
        return;
      }
      toast(`${channel.label} 已${channel.enabled ? '停用' : '启用'}`, 'ok');
      await refresh();
    } catch {
      toast('状态更新失败', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const removeChannel = async (channel: ImChannelStatus) => {
    const confirmed = window.confirm(`确认删除 ${channel.label} 的频道配置？`);
    if (!confirmed) return;
    setBusyAction(`delete:${channel.key}`);
    try {
      const result = await api.imChannelsDelete(channel.key);
      if (!result.ok) {
        toast(result.error || result.message || '删除失败', 'err');
        return;
      }
      toast(`${channel.label} 已删除`, 'ok');
      await refresh();
    } catch {
      toast('删除失败', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const copyWechatCommand = async () => {
    const command = 'npx -y @tencent-weixin/openclaw-weixin-cli@latest install';
    try {
      await navigator.clipboard.writeText(command);
      toast('微信安装命令已复制', 'ok');
    } catch {
      toast('复制失败', 'err');
    }
  };

  const editingChannel = editingKey ? channels.find((item) => item.key === editingKey) || null : null;

  return (
    <div className="imch-wrap">
      <PageHero
        kicker="IM 频道"
        title="把外部聊天渠道接到 Gateway，由工作台统一管理。"
        desc=""
      />

      <div className="page-inline-toolbar imch-inline-toolbar">
        <div className="page-inline-summary imch-inline-summary">
          <span className="imch-summary-pill">已接入 {configuredChannels.length}</span>
          <span className="imch-summary-pill">当前启用 {enabledCount}</span>
          <span className="imch-summary-pill">异常频道 {errorCount}</span>
        </div>
        <div className="page-inline-actions imch-inline-actions-bar">
          <button type="button" className="btn btn-g" onClick={refresh}>
            {loading ? '刷新中…' : '刷新'}
          </button>
          <button type="button" className="btn btn-p" onClick={() => setPickerOpen(true)}>
            添加频道
          </button>
        </div>
      </div>

      <div className="imch-list-card">
        {configuredChannels.length ? (
          configuredChannels.map((channel) => (
            <div key={channel.key} className="imch-row">
                <div className="imch-row-main">
                <ChannelBrandIcon channelKey={channel.key} className="imch-row-icon" />
                <div className="imch-row-copy">
                  <div className="imch-row-title">
                    <span>{channel.label}</span>
                    <span className={`imch-badge ${statusTone(channel.status)}`}>{channel.statusLabel}</span>
                  </div>
                  <div className="imch-row-desc">{channel.summary}</div>
                </div>
              </div>
              <div className="imch-row-actions">
                <button type="button" className="btn btn-g" onClick={() => toggleChannel(channel)} disabled={busyAction !== null}>
                  {busyAction === `toggle:${channel.key}` ? '处理中…' : channel.enabled ? '停用' : '启用'}
                </button>
                <button type="button" className="btn btn-g" onClick={() => openEditor(channel.key)} disabled={busyAction !== null}>
                  设置
                </button>
                <button type="button" className="btn btn-g" onClick={() => removeChannel(channel)} disabled={busyAction !== null}>
                  删除
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="imch-empty">当前还没有已接入的 IM 频道。可以先从下方快速添加开始。</div>
        )}
      </div>

      <div className="imch-quick-block">
        <div className="sub-sec-title">快速添加</div>
        <div className="imch-quick-grid">
          {QUICK_CHANNELS.map((item) => (
            <button key={item.key} type="button" className="imch-quick-btn" onClick={() => openEditor(item.key)}>
              <ChannelBrandIcon channelKey={item.key} className="imch-quick-icon" />
              <span>+ {item.label}</span>
            </button>
          ))}
        </div>
        {checkedAt ? <div className="imch-footnote">最近检查：{formatBeijingDateTime(checkedAt)}</div> : null}
      </div>

      {pickerOpen && (
        <div className="modal-bg open" onClick={() => setPickerOpen(false)}>
          <div className="modal imch-picker-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setPickerOpen(false)}>✕</button>
            <div className="imch-modal-title">添加 IM 频道</div>
            <div className="imch-picker-grid">
              {QUICK_CHANNELS.map((item) => (
                <button key={item.key} type="button" className="imch-picker-card" onClick={() => openEditor(item.key)}>
                  <ChannelBrandIcon channelKey={item.key} className="imch-picker-icon" />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {editingKey && editingChannel && (
        <div className="modal-bg open" onClick={closeEditor}>
          <div className="modal imch-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={closeEditor}>✕</button>
            <div className="imch-modal-title">连接 {editingChannel.label}</div>
            <div className="imch-modal-sub">{editingChannel.description}</div>

            {(editingKey === 'feishu' || editingKey === 'wecom') && (
              <div className="imch-scan-callout">
                <div className="imch-scan-title">{editingKey === 'feishu' ? '扫码连接预留' : '扫码创建机器人预留'}</div>
                <div className="imch-scan-copy">首版先支持手动配置与状态管理，后续再补官方扫码接入。</div>
              </div>
            )}

            {editingKey === 'dingtalk' && (
              <div className="imch-step-card">
                <div className="imch-step-title">第 1 步：安装钉钉插件</div>
                <div className="imch-step-copy">先完成插件安装，再填写应用凭据。当前首版只记录安装状态，不在页面里直接执行安装。</div>
                <label className="imch-toggle-check">
                  <input
                    type="checkbox"
                    checked={Boolean(forms.dingtalk.pluginInstalled)}
                    onChange={(e) => updateField('dingtalk', { pluginInstalled: e.target.checked })}
                  />
                  <span>我已完成插件安装</span>
                </label>
              </div>
            )}

            {editingKey === 'weixin' && (
              <div className="imch-step-card">
                <div className="imch-step-title">微信 ClawBot 接入</div>
                <div className="imch-step-copy">工作台只提供环境检查和命令引导，不在页面里直接执行安装命令。</div>
                <ol className="imch-steps">
                  <li>打开微信，确认版本为 8.0.70。</li>
                  <li>返回设置，进入“插件”。</li>
                  <li>找到“微信 ClawBot”并查看详情。</li>
                  <li>在终端执行安装命令并扫码完成绑定。</li>
                </ol>
                <div className="imch-inline-actions">
                  <button type="button" className="btn btn-g" onClick={copyWechatCommand}>复制安装命令</button>
                </div>
              </div>
            )}

            {editingKey === 'feishu' && (
              <div className="imch-form-grid">
                <label className="imch-field">
                  <span>App ID</span>
                  <input value={String(forms.feishu.appId || '')} onChange={(e) => updateField('feishu', { appId: e.target.value })} placeholder="cli_xxx" />
                </label>
                <label className="imch-field">
                  <span>App Secret</span>
                  <input type="password" value={String(forms.feishu.appSecret || '')} onChange={(e) => updateField('feishu', { appSecret: e.target.value })} placeholder="首次接入必填" />
                </label>
                <label className="imch-field">
                  <span>域名</span>
                  <select value={String(forms.feishu.domain || 'feishu')} onChange={(e) => updateField('feishu', { domain: e.target.value })}>
                    <option value="feishu">feishu</option>
                    <option value="lark">lark</option>
                  </select>
                </label>
                <label className="imch-field">
                  <span>Bot 名称</span>
                  <input value={String(forms.feishu.botName || '')} onChange={(e) => updateField('feishu', { botName: e.target.value })} placeholder="可选" />
                </label>
              </div>
            )}

            {editingKey === 'wecom' && (
              <div className="imch-form-grid">
                <label className="imch-field">
                  <span>Bot ID</span>
                  <input value={String(forms.wecom.botId || '')} onChange={(e) => updateField('wecom', { botId: e.target.value })} placeholder="请输入 Bot ID" />
                </label>
                <label className="imch-field">
                  <span>Bot Secret</span>
                  <input type="password" value={String(forms.wecom.botSecret || '')} onChange={(e) => updateField('wecom', { botSecret: e.target.value })} placeholder="请输入 Bot Secret" />
                </label>
                <label className="imch-field">
                  <span>Bot 名称</span>
                  <input value={String(forms.wecom.botName || '')} onChange={(e) => updateField('wecom', { botName: e.target.value })} placeholder="可选" />
                </label>
                <label className="imch-field">
                  <span>WS URL</span>
                  <input value={String(forms.wecom.wsUrl || '')} onChange={(e) => updateField('wecom', { wsUrl: e.target.value })} placeholder="可选" />
                </label>
              </div>
            )}

            {editingKey === 'dingtalk' && (
              <div className="imch-form-grid">
                <label className="imch-field">
                  <span>Client ID</span>
                  <input value={String(forms.dingtalk.clientId || '')} onChange={(e) => updateField('dingtalk', { clientId: e.target.value })} placeholder="dingxxxx" />
                </label>
                <label className="imch-field">
                  <span>Client Secret</span>
                  <input type="password" value={String(forms.dingtalk.clientSecret || '')} onChange={(e) => updateField('dingtalk', { clientSecret: e.target.value })} placeholder="请输入 Client Secret" />
                </label>
              </div>
            )}

            {editingKey === 'qqbot' && (
              <>
                <div className="imch-form-grid">
                  <label className="imch-field">
                    <span>App ID</span>
                    <input value={String(forms.qqbot.appId || '')} onChange={(e) => updateField('qqbot', { appId: e.target.value })} placeholder="QQ Bot App ID" />
                  </label>
                  <label className="imch-field">
                    <span>App Secret</span>
                    <input type="password" value={String(forms.qqbot.appSecret || '')} onChange={(e) => updateField('qqbot', { appSecret: e.target.value })} placeholder="QQ Bot App Secret" />
                  </label>
                  <label className="imch-field imch-field--wide">
                    <span>私聊策略</span>
                    <select value={String(forms.qqbot.privateChatPolicy || 'open')} onChange={(e) => updateField('qqbot', { privateChatPolicy: e.target.value })}>
                      <option value="open">开放（允许所有人）</option>
                      <option value="contacts_only">仅联系人</option>
                      <option value="closed">关闭</option>
                    </select>
                  </label>
                </div>
                <div className="imch-note-box">QQ Bot 首版只管理凭据和策略，不在工作台里代替你完成插件安装。</div>
              </>
            )}

            {editingKey === 'weixin' && (
              <div className="imch-note-box">微信渠道需要先完成本机环境和插件安装，再由 Gateway 接管消息通道。</div>
            )}

            <ChecksBlock checks={testResult?.checks || editingChannel.checks || []} />
            {testResult ? <div className={`imch-test-status ${testResult.ok ? 'ok' : 'warn'}`}>{testResult.message}</div> : null}

            <div className="imch-modal-actions">
              <button type="button" className="btn btn-g" onClick={runTest} disabled={busyAction !== null}>
                {busyAction === `test:${editingKey}` ? '检查中…' : '连通测试'}
              </button>
              <div className="imch-modal-actions-right">
                <button type="button" className="btn btn-g" onClick={closeEditor}>取消</button>
                <button type="button" className="btn btn-p" onClick={saveChannel} disabled={busyAction !== null}>
                  {busyAction === `save:${editingKey}` ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
