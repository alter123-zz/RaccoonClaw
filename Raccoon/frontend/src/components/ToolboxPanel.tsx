import { useEffect, useMemo, useState } from 'react';
import {
  api,
  type BootstrapProvisionResult,
  type BootstrapStatusResult,
  type DesktopStartupStatusResult,
  type ToolboxActionResult,
  type ToolboxStatusResult,
} from '../api';
import PageHero from './PageHero';
import { useStore } from '../store';
import { formatBeijingDateTime } from '../time';

type ToolboxActionKey =
  | 'gateway_status'
  | 'gateway_restart'
  | 'doctor'
  | 'doctor_fix'
  | 'runtime_sync'
  | 'refresh_live_status'
  | 'sync_agent_config';

type ToolboxActionDef = {
  key: ToolboxActionKey;
  label: string;
  desc: string;
};

type ToolboxCapabilityDef = {
  kicker: string;
  title: string;
  desc: string;
  primary: ToolboxActionDef;
  secondary?: ToolboxActionDef[];
};

const GATEWAY_ACTIONS: ToolboxActionDef[] = [
  { key: 'gateway_status', label: '检查网关', desc: '读取当前 Gateway 状态' },
  { key: 'gateway_restart', label: '重启网关', desc: '执行 openclaw gateway restart' },
];

const RUNTIME_ACTIONS: ToolboxActionDef[] = [
  { key: 'doctor', label: '环境诊断', desc: '执行 openclaw doctor' },
  { key: 'doctor_fix', label: 'Doctor 修复', desc: '执行 openclaw doctor --fix' },
  { key: 'runtime_sync', label: '同步 Runtime', desc: '同步 OpenClaw 会话到工作台' },
  { key: 'refresh_live_status', label: '刷新状态', desc: '重建 live_status.json' },
  { key: 'sync_agent_config', label: '同步配置', desc: '同步 Agent 配置与模型状态' },
];

const TOOLBOX_CAPABILITIES: ToolboxCapabilityDef[] = [
  {
    kicker: 'Gateway',
    title: '网关恢复',
    desc: '只保留真正会影响派发链路的网关操作。先看状态，再在必要时执行重启恢复。',
    primary: GATEWAY_ACTIONS[1],
    secondary: [GATEWAY_ACTIONS[0]],
  },
  {
    kicker: 'Runtime',
    title: '运行同步',
    desc: '同步 Runtime、Agent 配置和 live 状态，让看板、归档和真实执行保持一致。',
    primary: RUNTIME_ACTIONS[2],
    secondary: [RUNTIME_ACTIONS[4], RUNTIME_ACTIONS[3]],
  },
  {
    kicker: 'Doctor',
    title: '环境诊断',
    desc: '先做诊断，再在明确需要时执行自动修复。避免把高风险按钮长期摆在主页面中心。',
    primary: RUNTIME_ACTIONS[0],
    secondary: [RUNTIME_ACTIONS[1]],
  },
];

function ResultBlock({
  result,
}: {
  result: ToolboxActionResult | null;
}) {
  if (!result) return <div className="toolbox-empty">执行结果会显示在这里</div>;
  const body = [result.stdout, result.stderr].filter(Boolean).join('\n\n');
  return (
    <div className={`toolbox-result ${result.ok ? 'ok' : 'err'}`}>
      <div className="toolbox-result-hdr">
        <span>{result.ok ? '执行成功' : '执行失败'}</span>
        {result.executedAt && <span>{formatBeijingDateTime(result.executedAt)}</span>}
      </div>
      <div className="toolbox-result-meta">
        <span>{result.requestedAction || result.action || 'toolbox_action'}</span>
        {typeof result.code !== 'undefined' && <span>退出码 {String(result.code)}</span>}
      </div>
      {result.message && <div className="toolbox-result-msg">{result.message}</div>}
      {body ? <pre className="toolbox-pre">{body}</pre> : <div className="toolbox-empty">命令没有输出</div>}
    </div>
  );
}

export default function ToolboxPanel() {
  const toast = useStore((s) => s.toast);
  const [status, setStatus] = useState<ToolboxStatusResult | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapStatusResult | null>(null);
  const [startup, setStartup] = useState<DesktopStartupStatusResult | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [result, setResult] = useState<ToolboxActionResult | null>(null);

  const refreshStatus = async () => {
    setStatusLoading(true);
    try {
      const [toolboxResult, bootstrapResult, startupResult] = await Promise.allSettled([
        api.toolboxStatus(),
        api.bootstrapStatus(),
        api.desktopStartupStatus(),
      ]);

      if (toolboxResult.status === 'fulfilled') {
        setStatus(toolboxResult.value);
      } else {
        throw toolboxResult.reason;
      }
      if (bootstrapResult.status === 'fulfilled') {
        setBootstrap(bootstrapResult.value);
      }
      if (startupResult.status === 'fulfilled') {
        setStartup(startupResult.value);
      }
    } catch {
      toast('网关设置状态加载失败', 'err');
    } finally {
      setStatusLoading(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  const statusSummary = useMemo(() => {
    const gatewayOk = !!status?.gateway?.ok;
    const doctorOk = !!status?.doctor?.ok;
    const runtimeOk = !!status?.runtimeSync?.ok;
    const syncConfigOk = !!status?.syncAgentConfig?.ok;
    const liveStatusOk = !!status?.refreshLiveStatus?.ok;
    return {
      gateway: gatewayOk ? '已连通' : '待修复',
      dispatch: gatewayOk && doctorOk && runtimeOk && syncConfigOk && liveStatusOk ? '可派发' : '待修复',
      runtime: runtimeOk ? '已同步' : '待同步',
      doctor: doctorOk ? '通过' : '待修复',
      syncConfig: syncConfigOk ? '已同步' : '待同步',
      liveStatus: liveStatusOk ? '已刷新' : '待刷新',
    };
  }, [status]);

  const statusStrip = useMemo(
    () => [
      { label: 'OpenClaw', value: startup?.ready ? '已就绪' : startup?.summary || '待初始化', tone: startup?.ready ? 'ok' : 'warn' },
      { label: '网关', value: statusSummary.gateway, tone: status?.gateway?.ok ? 'ok' : 'warn' },
      { label: '派发链路', value: statusSummary.dispatch, tone: statusSummary.dispatch === '可派发' ? 'ok' : 'warn' },
      { label: 'Runtime', value: statusSummary.runtime, tone: status?.runtimeSync?.ok ? 'ok' : 'warn' },
      { label: '配置', value: statusSummary.syncConfig, tone: status?.syncAgentConfig?.ok ? 'ok' : 'warn' },
      { label: '状态', value: statusSummary.liveStatus, tone: status?.refreshLiveStatus?.ok ? 'ok' : 'warn' },
      { label: 'Doctor', value: statusSummary.doctor, tone: status?.doctor?.ok ? 'ok' : 'warn' },
    ],
    [startup, statusSummary, status]
  );

  const startupIssues = useMemo(() => {
    const issues: string[] = [];
    for (const item of bootstrap?.missingAgents || []) issues.push(`缺少 Agent: ${item}`);
    for (const item of bootstrap?.missingWorkspaces || []) issues.push(`缺少 Workspace: ${item}`);
    for (const item of bootstrap?.missingSoul || []) issues.push(`缺少 SOUL: ${item}`);
    for (const item of bootstrap?.missingScripts || []) issues.push(`缺少脚本: ${item}`);
    for (const item of bootstrap?.missingSkills || []) issues.push(`缺少技能: ${item}`);
    for (const item of bootstrap?.missingDataFiles || []) issues.push(`缺少数据: ${item}`);
    return issues.slice(0, 8);
  }, [bootstrap]);

  const startupMeta = useMemo(
    () =>
      [
        `CLI：${startup?.cliInstalled ? '已安装' : '未安装'}`,
        `Bootstrap：${bootstrap?.ready ? '已完成' : bootstrap?.recommendedAction || '待处理'}`,
        `Gateway：${startup?.gatewayStatusOk ? '已就绪' : '未就绪'}`,
        `总裁办：${bootstrap?.chiefOfStaffRuntimeReady ? '已注册' : '未注册'}`,
        `认证：${bootstrap?.chiefOfStaffAuthReady ? '已同步' : '待同步'}`,
        status?.checkedAt ? `最近检查：${formatBeijingDateTime(status.checkedAt)}` : null,
      ].filter(Boolean) as string[],
    [bootstrap, startup, status]
  );

  const runAction = async (action: ToolboxActionDef) => {
    setRunningAction(action.key);
    try {
      const data = await api.toolboxAction(action.key);
      setResult(data);
      if (data.ok) {
        toast(`${action.label} 已执行`, 'ok');
      } else {
        toast(data.message || data.error || `${action.label} 失败`, 'err');
      }
      await refreshStatus();
    } catch {
      toast(`${action.label} 请求失败`, 'err');
    } finally {
      setRunningAction(null);
    }
  };

  const runProvision = async () => {
    if (!startup?.cliInstalled) {
      toast('当前机器尚未安装 OpenClaw CLI', 'err');
      return;
    }
    setRunningAction('bootstrap_runtime');
    try {
      const data: BootstrapProvisionResult = await api.provisionOpenClawRuntime();
      setResult({
        ok: data.ok,
        action: 'bootstrap_runtime',
        requestedAction: 'bootstrap_runtime',
        message: data.summary || data.detail || '',
        stdout: data.output || '',
        stderr: data.ok ? '' : data.detail || '',
        code: data.ok ? 0 : 1,
        executedAt: new Date().toISOString(),
      });
      if (data.ok) {
        toast(data.summary || 'OpenClaw 工作台初始化完成', 'ok');
      } else {
        toast(data.summary || data.detail || 'OpenClaw 初始化失败', 'err');
      }
      await refreshStatus();
    } catch {
      toast('OpenClaw 初始化请求失败', 'err');
    } finally {
      setRunningAction(null);
    }
  };

  const renderCapabilityCard = (card: ToolboxCapabilityDef) => (
    <div className="toolbox-card toolbox-capability-card">
      <div className="toolbox-group-head">
        <div className="toolbox-group-kicker">{card.kicker}</div>
        <div className="toolbox-card-title">{card.title}</div>
        <div className="toolbox-group-desc">{card.desc}</div>
      </div>
      <div className="toolbox-capability-actions">
        <button
          type="button"
          className="toolbox-primary-btn"
          onClick={() => runAction(card.primary)}
          disabled={runningAction !== null}
        >
          {runningAction === card.primary.key ? '执行中…' : card.primary.label}
        </button>
        {card.secondary?.length ? (
          <div className="toolbox-secondary-actions">
            {card.secondary.map((action) => (
              <button
                key={action.key}
                type="button"
                className="toolbox-secondary-btn"
                onClick={() => runAction(action)}
                disabled={runningAction !== null}
                title={action.desc}
              >
                {runningAction === action.key ? '执行中…' : action.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="toolbox-inline-meta">
        <span>{card.primary.desc}</span>
        {card.secondary?.map((action) => (
          <span key={action.key}>{action.desc}</span>
        ))}
      </div>
    </div>
  );

  return (
    <div className="toolbox-wrap">
      <PageHero
        kicker="Gateway Settings"
        title="统一处理项目与 OpenClaw 的网关、同步和会话治理。"
        desc=""
      />

      <div className="tpl-cats toolbox-status-strip">
        {statusStrip.map((item) => (
          <span key={`${item.label}-${item.value}`} className={`toolbox-status-pill ${item.tone}`}>
            <b>{item.label}</b>
            <span>{item.value}</span>
          </span>
        ))}
      </div>

      <div className="toolbox-card toolbox-startup-card">
        <div className="toolbox-group-head">
          <div className="toolbox-group-kicker">OpenClaw Startup</div>
          <div className="toolbox-card-title">先确认 OpenClaw 本体、组织配置和 Gateway 是否都已接通。</div>
          <div className="toolbox-group-desc">
            这是工作台真正能派发任务的前置条件。这里集中展示 OpenClaw CLI、bootstrap 导入和 Gateway 就绪状态。
          </div>
        </div>
        <div className={`toolbox-result ${startup?.ready ? 'ok' : 'err'}`}>
          <div className="toolbox-result-hdr">
            <span>{startup?.summary || '正在读取 OpenClaw 启动状态'}</span>
            {startup?.ready ? <span>工作台可进入</span> : <span>需要处理</span>}
          </div>
          {startup?.detail ? <div className="toolbox-result-msg">{startup.detail}</div> : null}
          <div className="toolbox-inline-meta">
            {startupMeta.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
          {!startup?.ready && startupIssues.length ? (
            <div className="toolbox-inline-meta">
              {startupIssues.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          ) : null}
          {startup?.statusOutput ? <pre className="toolbox-pre">{startup.statusOutput}</pre> : null}
        </div>
        <div className="toolbox-capability-actions">
          <button
            type="button"
            className="toolbox-primary-btn"
            onClick={runProvision}
            disabled={runningAction !== null || !startup?.cliInstalled}
          >
            {runningAction === 'bootstrap_runtime' ? '初始化中…' : '初始化 / 修复 OpenClaw 工作台'}
          </button>
          <div className="toolbox-secondary-actions">
            <button
              type="button"
              className="toolbox-secondary-btn"
              onClick={refreshStatus}
              disabled={runningAction !== null}
            >
              重新检查启动状态
            </button>
          </div>
        </div>
      </div>

      <div className="toolbox-capability-grid toolbox-capability-grid--trimmed">
        {TOOLBOX_CAPABILITIES.map((card) => (
          <div key={card.title}>{renderCapabilityCard(card)}</div>
        ))}
      </div>

      <div className="toolbox-card toolbox-result-card">
        <div className="toolbox-group-head">
          <div className="toolbox-group-kicker">Recent Action</div>
          <div className="toolbox-card-title">最近一次执行</div>
          <div className="toolbox-group-desc">
            这里保留最后一次网关、同步或诊断动作的结果，方便判断链路有没有真正修好。
          </div>
        </div>
        <ResultBlock result={result} />
      </div>
    </div>
  );
}
