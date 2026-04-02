/**
 * API 层 — 对接 dashboard/server.py
 * 生产环境从同源 (port 7891) 请求，开发环境可通过 VITE_API_URL 指定
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

// ── 通用请求 ──

async function fetchJ<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

async function postJ<T>(url: string, data: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

// ── API 接口 ──

export const api = {
  // 核心数据
  liveStatus: () => fetchJ<LiveStatus>(`${API_BASE}/api/live-status`),
  agentConfig: () => fetchJ<AgentConfig>(`${API_BASE}/api/agent-config`),
  modelChangeLog: () => fetchJ<ChangeLogEntry[]>(`${API_BASE}/api/model-change-log`).catch(() => []),
  officialsStats: () => fetchJ<OfficialsData>(`${API_BASE}/api/officials-stats`),
  agentsStatus: () => fetchJ<AgentsStatusData>(`${API_BASE}/api/agents-status`),

  // 任务实时动态
  taskActivity: (id: string) =>
    fetchJ<TaskActivityData>(`${API_BASE}/api/task-activity/${encodeURIComponent(id)}`),
  schedulerState: (id: string) =>
    fetchJ<SchedulerStateData>(`${API_BASE}/api/scheduler-state/${encodeURIComponent(id)}`),

  // 技能内容
  skillContent: (agentId: string, skillName: string) =>
    fetchJ<SkillContentResult>(
      `${API_BASE}/api/skill-content/${encodeURIComponent(agentId)}/${encodeURIComponent(skillName)}`
    ),

  // 操作类
  setModel: (agentId: string, model: string) =>
    postJ<ActionResult>(`${API_BASE}/api/set-model`, { agentId, model }),
  addModel: (data: AddModelPayload) =>
    postJ<ActionResult & { modelId?: string; providerId?: string; backup?: string }>(`${API_BASE}/api/add-model`, data),
  testModel: (data: TestModelPayload) =>
    postJ<ActionResult & { status?: number; durationMs?: number; preview?: string }>(`${API_BASE}/api/test-model`, data),
  agentWake: (agentId: string) =>
    postJ<ActionResult>(`${API_BASE}/api/agent-wake`, { agentId }),
  taskAction: (taskId: string, action: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/task-action`, { taskId, action, reason }),
  reviewAction: (taskId: string, action: string, comment: string) =>
    postJ<ActionResult>(`${API_BASE}/api/review-action`, { taskId, action, comment }),
  advanceState: (taskId: string, comment: string) =>
    postJ<ActionResult>(`${API_BASE}/api/advance-state`, { taskId, comment }),
  archiveTask: (taskId: string, archived: boolean) =>
    postJ<ActionResult>(`${API_BASE}/api/archive-task`, { taskId, archived }),
  archiveAllDone: () =>
    postJ<ActionResult & { count?: number }>(`${API_BASE}/api/archive-task`, { archiveAllDone: true }),
  schedulerScan: (thresholdSec = 180) =>
    postJ<ActionResult & { count?: number; actions?: ScanAction[]; checkedAt?: string }>(
      `${API_BASE}/api/scheduler-scan`,
      { thresholdSec }
    ),
  schedulerRetry: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-retry`, { taskId, reason }),
  schedulerEscalate: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-escalate`, { taskId, reason }),
  schedulerRollback: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-rollback`, { taskId, reason }),
  addSkill: (agentId: string, skillName: string, description: string, trigger: string) =>
    postJ<ActionResult>(`${API_BASE}/api/add-skill`, { agentId, skillName, description, trigger }),

  // 远程 Skills 管理
  addRemoteSkill: (agentId: string, skillName: string, sourceUrl: string, description?: string) =>
    postJ<ActionResult & { skillName?: string; agentId?: string; source?: string; localPath?: string; size?: number; addedAt?: string }>(
      `${API_BASE}/api/add-remote-skill`, { agentId, skillName, sourceUrl, description: description || '' }
    ),
  remoteSkillsList: () =>
    fetchJ<RemoteSkillsListResult>(`${API_BASE}/api/remote-skills-list`),
  availableSkills: () =>
    fetchJ<AvailableSkillsResult>(`${API_BASE}/api/available-skills`),
  chatSessions: () =>
    fetchJ<ChatSessionsResult>(`${API_BASE}/api/chat/sessions`),
  chatSession: (sessionId: string) =>
    fetchJ<ChatSessionResult>(`${API_BASE}/api/chat/sessions/${encodeURIComponent(sessionId)}`),
  chatNewSession: (title = '') =>
    postJ<ChatSessionResult>(`${API_BASE}/api/chat/sessions`, { title }),
  chatUploadAttachments: (sessionId: string, files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return postForm<ChatSessionResult>(`${API_BASE}/api/chat/sessions/${encodeURIComponent(sessionId)}/attachments`, formData);
  },
  chatRemoveAttachment: (sessionId: string, attachmentId: string) =>
    postJ<ChatSessionResult>(`${API_BASE}/api/chat/sessions/${encodeURIComponent(sessionId)}/attachments/remove`, { attachmentId }),
  chatSend: (sessionId: string, content: string) =>
    postJ<ChatSessionResult>(`${API_BASE}/api/chat/sessions/${encodeURIComponent(sessionId)}/send`, { content }),
  toolboxStatus: () =>
    fetchJ<ToolboxStatusResult>(`${API_BASE}/api/toolbox/status`),
  bootstrapStatus: () =>
    fetchJ<BootstrapStatusResult>(`${API_BASE}/api/bootstrap-status`),
  desktopStartupStatus: () =>
    fetchJ<DesktopStartupStatusResult>(`${API_BASE}/api/desktop/startup-status`),
  provisionOpenClawRuntime: () =>
    postJ<BootstrapProvisionResult>(`${API_BASE}/api/bootstrap/provision`, {}),
  imChannelsStatus: () =>
    fetchJ<ImChannelsStatusResult>(`${API_BASE}/api/im-channels/status`),
  imChannelsUpsert: (payload: ImChannelUpsertPayload) =>
    postJ<ActionResult & { channel?: ImChannelStatus; backupPath?: string }>(`${API_BASE}/api/im-channels/upsert`, payload),
  imChannelsToggle: (channelKey: string, enabled: boolean) =>
    postJ<ActionResult & { channel?: ImChannelStatus; backupPath?: string }>(`${API_BASE}/api/im-channels/toggle`, { channelKey, enabled }),
  imChannelsDelete: (channelKey: string) =>
    postJ<ActionResult & { deleted?: string; backupPath?: string }>(`${API_BASE}/api/im-channels/delete`, { channelKey }),
  imChannelsTest: (payload: ImChannelTestPayload) =>
    postJ<ActionResult & { checks?: ImChannelCheck[] }>(`${API_BASE}/api/im-channels/test`, payload),
  openPath: (path: string) =>
    postJ<ActionResult>(`${API_BASE}/api/open-path`, { path }),
  toolboxAction: (action: string) =>
    postJ<ToolboxActionResult>(`${API_BASE}/api/toolbox/action`, { action }),
  toolboxConnectFeishu: (payload: FeishuConnectPayload) =>
    postJ<ToolboxActionResult>(`${API_BASE}/api/toolbox/feishu/connect`, payload),
  updateRemoteSkill: (agentId: string, skillName: string) =>
    postJ<ActionResult>(`${API_BASE}/api/update-remote-skill`, { agentId, skillName }),
  removeRemoteSkill: (agentId: string, skillName: string) =>
    postJ<ActionResult>(`${API_BASE}/api/remove-remote-skill`, { agentId, skillName }),

  createTask: (data: CreateTaskPayload) =>
    postJ<ActionResult & { taskId?: string }>(`${API_BASE}/api/create-task`, data),
};

// ── Types ──

export interface ActionResult {
  ok: boolean;
  message?: string;
  error?: string;
}

export interface FlowEntry {
  at: string;
  from: string;
  to: string;
  remark: string;
}

export interface TodoItem {
  id: string | number;
  title: string;
  status: 'not-started' | 'in-progress' | 'completed';
  detail?: string;
}

export interface Heartbeat {
  status: 'active' | 'warn' | 'stalled' | 'unknown' | 'idle';
  label: string;
}

export interface Task {
  id: string;
  title: string;
  official?: string;
  state: string;
  modeId?: string;
  org: string;
  now: string;
  eta: string;
  block: string;
  ac: string;
  output: string;
  resolvedOutput?: string;
  heartbeat: Heartbeat;
  flow_log: FlowEntry[];
  todos: TodoItem[];
  review_round: number;
  archived: boolean;
  archivedAt?: string;
  updatedAt?: string;
  sourceMeta?: Record<string, unknown>;
  outputMeta?: {
    exists?: boolean;
    lastModified?: string | null;
  };
  outputArtifacts?: OutputArtifact[];
  blockerFeedback?: BlockerFeedback;
  activity?: ActivityEntry[];
  _prev_state?: string;
  priority?: string;
  targetDept?: string;
  templateId?: string;
  templateParams?: Record<string, string>;
}

export interface SyncStatus {
  ok?: boolean | null;
  error?: string | null;
  [key: string]: unknown;
}

export interface LiveStatus {
  generatedAt?: string;
  tasks: Task[];
  history?: {
    at?: string;
    official?: string;
    task?: string;
    out?: string;
    qa?: string;
  }[];
  automation?: AutomationSnapshot;
  syncStatus: SyncStatus;
  metrics?: {
    officialCount?: number;
    todayDone?: number;
    totalDone?: number;
    inProgress?: number;
    blocked?: number;
  };
  health?: {
    syncOk?: boolean | null;
    syncLatencyMs?: number | null;
    missingFieldCount?: number;
    [key: string]: unknown;
  };
}

export interface AgentInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  model: string;
  skills: SkillInfo[];
}

export interface SkillInfo {
  name: string;
  description: string;
  path: string;
}

export interface AvailableSkillInfo {
  name: string;
  description: string;
  path: string;
  sources: string[];
  agents: string[];
}

export interface AvailableSkillsResult extends ActionResult {
  skills: AvailableSkillInfo[];
  count?: number;
  listedAt?: string;
}

export interface ToolboxCommandResult extends ActionResult {
  action?: string;
  message?: string;
  stdout?: string;
  stderr?: string;
  code?: number | null;
  executedAt?: string;
  requestedAction?: string;
}

export interface ToolboxStatusResult extends ActionResult {
  checkedAt?: string;
  gateway?: ToolboxCommandResult;
  doctor?: ToolboxCommandResult;
  runtimeSync?: ToolboxCommandResult;
  refreshLiveStatus?: ToolboxCommandResult;
  syncAgentConfig?: ToolboxCommandResult;
  entrySessionsReset?: ToolboxCommandResult;
  agentSessionsReset?: ToolboxCommandResult;
  feishu?: {
    mode?: string;
    configured?: boolean;
    defaultAccount?: string;
    appId?: string;
    domain?: string;
    botName?: string;
    dmPolicy?: string;
    groupPolicy?: string;
    connectionMode?: string;
  };
  wechat?: {
    supported?: boolean;
    message?: string;
    requiredVersion?: string;
    installCommand?: string;
    appInstalled?: boolean;
    appPath?: string;
    version?: string;
    versionOk?: boolean;
    nodeAvailable?: boolean;
    npxAvailable?: boolean;
  };
}

export interface ToolboxActionResult extends ToolboxCommandResult {}

export interface BootstrapStatusResult extends ActionResult {
  ready?: boolean;
  recommendedAction?: string;
  summary?: string;
  detail?: string;
  cliInstalled?: boolean;
  cliPath?: string;
  configExists?: boolean;
  openclawHome?: string;
  runtimeAgentIds?: string[];
  chiefOfStaffRuntimeReady?: boolean;
  chiefOfStaffAuthReady?: boolean;
  gatewayTokenSynced?: boolean;
  missingAgents?: string[];
  missingWorkspaces?: string[];
  missingSoul?: string[];
  missingScripts?: string[];
  missingSkills?: string[];
  missingDataFiles?: string[];
}

export interface DesktopStartupStatusResult extends ActionResult {
  ready?: boolean;
  summary?: string;
  detail?: string;
  recommendedAction?: string;
  cliInstalled?: boolean;
  gatewayStatusOk?: boolean;
  gatewayReachable?: boolean;
  gatewayDashboardUrl?: string;
  statusOutput?: string;
  bootstrapReady?: boolean;
  bootstrapSummary?: string;
  bootstrapDetail?: string;
  bootstrapRecommendedAction?: string;
  runtimeAgentIds?: string[];
  missingAgents?: string[];
  missingWorkspaces?: string[];
  missingSoul?: string[];
  missingScripts?: string[];
  missingSkills?: string[];
  missingDataFiles?: string[];
}

export interface BootstrapProvisionResult extends ActionResult {
  summary?: string;
  detail?: string;
  output?: string;
  backupDir?: string;
  gatewayRestarted?: boolean;
  status?: BootstrapStatusResult;
}

export type ImChannelKey = 'feishu' | 'wecom' | 'dingtalk' | 'qqbot' | 'weixin';

export interface ImChannelCheck {
  key: string;
  label: string;
  ok: boolean;
  detail?: string;
}

export interface ImChannelStatus {
  key: ImChannelKey;
  label: string;
  description: string;
  icon: string;
  configured: boolean;
  enabled: boolean;
  status: 'configured' | 'draft' | 'disabled' | 'error';
  statusLabel: string;
  setupMode: string;
  summary: string;
  lastUpdated?: string;
  configSummary?: Record<string, string | boolean | number | null>;
  checks?: ImChannelCheck[];
  capabilities?: string[];
}

export interface ImChannelsStatusResult extends ActionResult {
  checkedAt?: string;
  channels: ImChannelStatus[];
  configuredCount?: number;
}

export interface ImChannelUpsertPayload {
  channelKey: ImChannelKey;
  enabled?: boolean;
  setupMode?: string;
  config: Record<string, string | boolean | number | null>;
}

export interface ImChannelTestPayload {
  channelKey: ImChannelKey;
  config: Record<string, string | boolean | number | null>;
}

export interface FeishuConnectPayload {
  appId: string;
  appSecret: string;
  domain: string;
  botName: string;
}

export interface KnownModel {
  id: string;
  label: string;
  provider: string;
}

export interface AddModelPayload {
  vendorKey: string;
  modelId: string;
  modelName: string;
  vendorLabel?: string;
  baseUrl?: string;
  apiProtocol?: string;
  apiKey?: string;
  authHeader?: boolean;
  reasoning?: boolean;
  contextWindow?: number | null;
  maxTokens?: number | null;
}

export interface TestModelPayload {
  baseUrl: string;
  apiProtocol?: string;
  modelId: string;
  apiKey?: string;
}

export interface AgentConfig {
  agents: AgentInfo[];
  knownModels?: KnownModel[];
}

export interface ChangeLogEntry {
  at: string;
  agentId: string;
  oldModel: string;
  newModel: string;
  rolledBack?: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  error?: boolean;
  meta?: Record<string, unknown>;
  attachments?: ChatAttachment[];
}

export interface ChatAttachment {
  id: string;
  name: string;
  path: string;
  size: number;
  contentType: string;
  kind: 'image' | 'document';
  uploadedAt: string;
  textExcerpt?: string;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  lastMessage: string;
  messageCount: number;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessage[];
  pendingAttachments?: ChatAttachment[];
}

export interface ChatSessionsResult extends ActionResult {
  sessions: ChatSessionSummary[];
  count?: number;
}

export interface ChatSessionResult extends ActionResult {
  session?: ChatSessionDetail;
  stdout?: string;
  stderr?: string;
  code?: number | null;
}

export interface OfficialInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  rank: string;
  model: string;
  model_short: string;
  tokens_in: number;
  tokens_out: number;
  cache_read: number;
  cache_write: number;
  cost_cny: number;
  cost_usd: number;
  sessions: number;
  messages: number;
  tasks_done: number;
  tasks_active: number;
  flow_participations: number;
  merit_score: number;
  merit_rank: number;
  last_active: string;
  heartbeat: Heartbeat;
  participated_edicts: { id: string; title: string; state: string }[];
}

export interface OfficialsData {
  officials: OfficialInfo[];
  totals: { tasks_done: number; cost_cny: number };
  top_official: string;
}

export interface AgentStatusInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  status: 'running' | 'queued' | 'idle' | 'offline' | 'unconfigured';
  statusLabel: string;
  lastActive?: string;
  queuedTasks?: number;
}

export interface GatewayStatus {
  alive: boolean;
  probe: boolean;
  status: string;
}

export interface AgentsStatusData {
  ok: boolean;
  gateway: GatewayStatus;
  agents: AgentStatusInfo[];
  checkedAt: string;
}

export interface MorningNewsItem {
  title: string;
  summary?: string;
  desc?: string;
  link: string;
  source: string;
  image?: string;
  pub_date?: string;
}

export interface MorningBrief {
  date?: string;
  generated_at?: string;
  items?: MorningNewsItem[];
  categories?: Record<string, MorningNewsItem[]>;
}

export interface CustomFeed {
  name: string;
  url: string;
  category?: string;
}

export interface SubConfig {
  keywords: string[];
  custom_feeds: CustomFeed[];
  feishu_webhook: string;
}

export interface MorningAutomationStatus {
  ok: boolean;
  status: 'disabled' | 'running' | 'installed' | 'missing' | string;
  enabled: boolean;
  feedCount: number;
  launchAgentLabel?: string;
  launchAgentInstalled?: boolean;
  launchAgentLoaded?: boolean;
  lastRunAt?: string;
  nextRunAt?: string;
  summary?: string;
  stdoutLog?: string;
  stderrLog?: string;
  dataFile?: string;
}

export interface ActivityEntry {
  kind: string;
  at?: number | string;
  text?: string;
  thinking?: string;
  agent?: string;
  from?: string;
  to?: string;
  remark?: string;
  tools?: { name: string; input_preview?: string }[];
  tool?: string;
  output?: string;
  exitCode?: number | null;
  items?: TodoItem[];
  diff?: {
    changed?: { id: string; from: string; to: string }[];
    added?: { id: string; title: string }[];
    removed?: { id: string; title: string }[];
  };
}

export interface PhaseDuration {
  phase: string;
  durationSec: number;
  durationText: string;
  ongoing?: boolean;
}

export interface TodosSummary {
  total: number;
  completed: number;
  inProgress: number;
  notStarted: number;
  percent: number;
}

export interface ResourceSummary {
  totalTokens?: number;
  totalCost?: number;
  totalElapsedSec?: number;
}

export interface TaskActivityData {
  ok: boolean;
  message?: string;
  error?: string;
  activity?: ActivityEntry[];
  relatedAgents?: string[];
  agentLabel?: string;
  lastActive?: string;
  phaseDurations?: PhaseDuration[];
  totalDuration?: string;
  todosSummary?: TodosSummary;
  resourceSummary?: ResourceSummary;
}

export interface SchedulerInfo {
  retryCount?: number;
  escalationLevel?: number;
  lastDispatchStatus?: string;
  stallThresholdSec?: number;
  enabled?: boolean;
  lastProgressAt?: string;
  lastDispatchAt?: string;
  lastDispatchAgent?: string;
  autoRollback?: boolean;
}

export interface AutomationJob {
  id: string;
  name: string;
  agentId: string;
  enabled: boolean;
  status: 'healthy' | 'warning' | 'critical' | 'pending' | 'paused' | string;
  tone: 'ok' | 'warn' | 'err' | 'muted' | string;
  message: string;
  scheduleExpr: string;
  scheduleLabel?: string;
  timezone: string;
  routeMode?: string;
  routeLabel?: string;
  routeReason?: string;
  directAgentHint?: string;
  channel: string;
  target: string;
  lastRunAtMs?: number | null;
  lastRunAt?: string | null;
  nextRunAtMs?: number | null;
  nextRunAt?: string | null;
  lastRunStatus?: string;
  lastDeliveryStatus?: string;
  lastDurationMs?: number;
  consecutiveErrors?: number;
  overdueMs?: number;
  graceMs?: number;
  intervalMs?: number | null;
  lastError?: string;
  incident?: {
    kind: string;
    label: string;
    severity: string;
    severityLabel: string;
    tone: string;
    summary: string;
    ownerDept: string;
    steps: string[];
    nextUpdateBy?: string | null;
    updateWithinMin?: number;
  } | null;
}

export interface AutomationSnapshot {
  checkedAt?: string;
  jobs: AutomationJob[];
  alerts: AutomationJob[];
  incident?: {
    severity: string;
    severityLabel: string;
    tone: string;
    title: string;
    summary: string;
    ownerDept: string;
    steps: string[];
    nextUpdateBy?: string | null;
    affectedJobs: { jobId: string; jobName: string; severity: string; severityLabel: string }[];
    count: number;
  } | null;
  summary?: {
    jobCount?: number;
    enabledCount?: number;
    healthyCount?: number;
    pendingCount?: number;
    pausedCount?: number;
    warningCount?: number;
    criticalCount?: number;
    alertCount?: number;
    incidentCount?: number;
  };
}

export interface SchedulerStateData {
  ok: boolean;
  error?: string;
  scheduler?: SchedulerInfo;
  stalledSec?: number;
}

export interface SkillContentResult {
  ok: boolean;
  name?: string;
  agent?: string;
  content?: string;
  path?: string;
  error?: string;
}

export interface ScanAction {
  taskId: string;
  action: string;
  to?: string;
  toState?: string;
  stalledSec?: number;
}

export interface CreateTaskPayload {
  title: string;
  org: string;
  targetDept?: string;
  priority?: string;
  templateId?: string;
  modeId?: string;
  flowMode?: 'direct' | 'light' | 'full';
  params?: Record<string, string>;
}

export interface RemoteSkillItem {
  skillName: string;
  agentId: string;
  sourceUrl: string;
  description: string;
  localPath: string;
  addedAt: string;
  lastUpdated: string;
  status: 'valid' | 'not-found' | string;
}

export interface RemoteSkillsListResult {
  ok: boolean;
  remoteSkills?: RemoteSkillItem[];
  count?: number;
  listedAt?: string;
  error?: string;
}

export interface OutputArtifact {
  path: string;
  name: string;
  agentId?: string;
  folder?: string;
  lastModified?: string;
  preview?: string;
}

export interface BlockerFeedback {
  taskId?: string;
  state?: string;
  org?: string;
  kind: string;
  summary: string;
  missingItems: string[];
  actions: string[];
  evidence: string[];
  awaitingUserAction?: boolean;
}
