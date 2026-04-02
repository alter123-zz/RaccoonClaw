/**
 * Zustand Store — 现代公司架构看板状态管理
 * HTTP 5s 轮询，无 WebSocket
 */

import { create } from 'zustand';
import {
  api,
  type Task,
  type LiveStatus,
  type AgentConfig,
  type OfficialsData,
  type AgentsStatusData,
  type ChangeLogEntry,
} from './api';
import { MONITOR_DEPTS } from './agentRegistry';
import { parseTimeValue } from './time';
import {
  WORKFLOW_BOARD_ORDER,
  WORKFLOW_MANUAL_ADVANCE_STATES,
  WORKFLOW_PIPE,
  WORKFLOW_RESUMABLE_STATES,
  WORKFLOW_STATE_INDEX,
  WORKFLOW_STATE_LABELS,
  WORKFLOW_STOP_DISABLED_STATES,
  WORKFLOW_TERMINAL_STATES,
} from './workflowRegistry';
import type { WorkbenchModeKey } from './workbenchModes';

// ── Pipeline Definition (PIPE) ──

export const PIPE = WORKFLOW_PIPE;
export const PIPE_STATE_IDX: Record<string, number> = WORKFLOW_STATE_INDEX;

export const DEPT_COLOR: Record<string, string> = {
  '总裁办': '#e8a040', '产品规划部': '#a07aff', '评审质控部': '#6a9eff', '交付运营部': '#6aef9a',
  '品牌内容部': '#f5c842', '经营分析部': '#ff9a6a', '安全运维部': '#ff5270', '合规测试部': '#cc4444',
  '工程研发部': '#44aaff', '人力组织部': '#9b59b6', '需求方': '#ffd700', '结果回传': '#2ecc8a',
  '专项团队': '#06b6d4',
};

export const STATE_LABEL: Record<string, string> = WORKFLOW_STATE_LABELS;
export const TERMINAL_STATES = WORKFLOW_TERMINAL_STATES;
export const TERMINAL_STATE_SET = new Set(TERMINAL_STATES);
export const STOP_DISABLED_STATES = WORKFLOW_STOP_DISABLED_STATES;
export const STOP_DISABLED_STATE_SET = new Set(STOP_DISABLED_STATES);
export const RESUMABLE_STATES = WORKFLOW_RESUMABLE_STATES;
export const RESUMABLE_STATE_SET = new Set(RESUMABLE_STATES);
export const MANUAL_ADVANCE_STATES = WORKFLOW_MANUAL_ADVANCE_STATES;
export const MANUAL_ADVANCE_STATE_SET = new Set(MANUAL_ADVANCE_STATES);
export const BOARD_STATE_ORDER: Record<string, number> = WORKFLOW_BOARD_ORDER;

export function deptColor(d: string): string {
  return DEPT_COLOR[d] || '#6a9eff';
}

export const LEGACY_WORKFLOW_STATE_MAP: Record<string, string> = {};

export function normalizeWorkflowState(state: string): string {
  return LEGACY_WORKFLOW_STATE_MAP[state] || state;
}

export function isTerminalState(state: string): boolean {
  return TERMINAL_STATE_SET.has(normalizeWorkflowState(state));
}

export function canStopTask(state: string): boolean {
  return !STOP_DISABLED_STATE_SET.has(normalizeWorkflowState(state));
}

export function canResumeTask(state: string): boolean {
  return RESUMABLE_STATE_SET.has(normalizeWorkflowState(state));
}

export function canAdvanceTask(state: string): boolean {
  return MANUAL_ADVANCE_STATE_SET.has(normalizeWorkflowState(state));
}

export function stateLabel(t: Task): string {
  const r = t.review_round || 0;
  const state = normalizeWorkflowState(t.state);
  if (state === 'ReviewControl' && r > 1) return `评审质控（第${r}轮）`;
  if (state === 'Planning' && r > 0) return `产品规划修订（第${r}轮）`;
  return STATE_LABEL[state] || state;
}

export function isEdict(t: Task): boolean {
  return /^(?:JJC-|D-|L-|F-)/i.test(t.id || '');
}

export function isSession(t: Task): boolean {
  return /^(OC-|MC-)/i.test(t.id || '');
}

export function isAutomationTask(t: Task): boolean {
  const sourceMeta = t.sourceMeta as Record<string, unknown> | undefined;
  return (
    /^JJC-AUTO-/i.test(t.id || '') ||
    String(sourceMeta?.kind || '') === 'automation_job' ||
    Boolean(sourceMeta?.automationJobId)
  );
}

const SCHEDULED_TASK_PATTERN = /(定时任务|(?:^|\W)cron(?:\W|$)|每小时执行|每天\d{0,2}|每周|周期任务|定时自动化)/i;
const RECENTLY_COMPLETED_WINDOW_MS = 15 * 60 * 1000;
const AUTO_SCHEDULER_SCAN_MS = 60 * 1000;
export function isScheduledTask(t: Task): boolean {
  const sourceMeta = t.sourceMeta as Record<string, unknown> | undefined;
  const templateParams = t.templateParams as Record<string, unknown> | undefined;
  const taskKind = String(sourceMeta?.taskKind || templateParams?.taskKind || '').trim().toLowerCase();
  if (taskKind === 'oneshot' || taskKind === 'recurring') return true;

  const scheduler = (t as Task & { scheduler?: { enabled?: boolean } }).scheduler;
  if (scheduler?.enabled) return true;

  const flowRemarks = (t.flow_log || []).map((entry) => entry.remark || '').join(' ');
  const text = [t.title, t.now, t.output, t.ac, flowRemarks]
    .filter(Boolean)
    .join(' ');

  return SCHEDULED_TASK_PATTERN.test(text);
}

function taskUpdatedAtMs(t: Task): number {
  const candidates = [
    t.updatedAt,
    t.sourceMeta?.updatedAt,
    t.outputMeta?.lastModified,
  ];
  for (const raw of candidates) {
    if (!raw) continue;
    const ts = Date.parse(String(raw));
    if (Number.isFinite(ts) && ts > 0) return ts;
  }
  return 0;
}

export function isRecentlyCompleted(t: Task): boolean {
  if (t.archived || isScheduledTask(t) || !isTerminalState(t.state)) return false;
  const updatedAtMs = taskUpdatedAtMs(t);
  if (!updatedAtMs) return false;
  return Date.now() - updatedAtMs <= RECENTLY_COMPLETED_WINDOW_MS;
}

export function isArchived(t: Task): boolean {
  if (t.archived) return true;
  if (isScheduledTask(t) || isRecentlyCompleted(t)) return false;
  return isTerminalState(t.state);
}

export type PipeStatus = { key: string; dept: string; icon: string; action: string; status: 'done' | 'active' | 'pending' };

function trimmedPipe(task: Task, mode: 'direct' | 'light'): PipeStatus[] {
  const targetDept = task.org && task.org !== '总裁办' ? task.org : task.targetDept || (mode === 'direct' ? '总裁办' : '专项团队');
  const pipe = [
    { key: 'Inbox', dept: '需求方', icon: '👤', action: '发起' },
    { key: 'ChiefOfStaff', dept: '总裁办', icon: '🧭', action: mode === 'direct' ? '直办' : '分诊' },
    { key: 'Doing', dept: targetDept, icon: '⚙️', action: '执行' },
    { key: 'Review', dept: '交付运营部', icon: '🔎', action: '归档' },
    { key: 'Done', dept: '结果回传', icon: '✅', action: '完成' },
  ];
  const state = normalizeWorkflowState(task.state);
  let stateIdx = 1;
  if (state === 'Doing') stateIdx = 2;
  if (state === 'Review') stateIdx = 3;
  if (state === 'Done') stateIdx = 4;
  return pipe.map((stage, i) => ({
    ...stage,
    status: (i < stateIdx ? 'done' : i === stateIdx ? 'active' : 'pending') as 'done' | 'active' | 'pending',
  }));
}

export function getPipeStatus(t: Task): PipeStatus[] {
  const flowMode = String((t.sourceMeta as Record<string, unknown> | undefined)?.flowMode || '').trim();
  if (flowMode === 'chief_direct' || flowMode === 'direct') {
    return trimmedPipe(t, 'direct');
  }
  if (flowMode === 'light') {
    return trimmedPipe(t, 'light');
  }
  const stateIdx = PIPE_STATE_IDX[normalizeWorkflowState(t.state)] ?? 1;
  return PIPE.map((stage, i) => ({
    ...stage,
    status: (i < stateIdx ? 'done' : i === stateIdx ? 'active' : 'pending') as 'done' | 'active' | 'pending',
  }));
}

// ── Tabs ──

export type TabKey =
  | 'chat' | 'overview' | 'godview' | 'edicts' | 'officials' | 'models'
  | 'skills' | 'toolbox' | 'sessions' | 'memorials' | 'templates';

export const TAB_DEFS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'chat',      label: '对话',     icon: '💬' },
  { key: 'godview',   label: '任务状态', icon: '📡' },
  { key: 'edicts',    label: '发起任务', icon: '📋' },
  { key: 'officials', label: '团队总览', icon: '👥' },
  { key: 'models',    label: '模型配置', icon: '🤖' },
  { key: 'skills',    label: '技能配置', icon: '🎯' },
  { key: 'toolbox',   label: '网关设置', icon: '🧰' },
  { key: 'sessions',  label: '会话监控', icon: '💬' },
  { key: 'memorials', label: '交付归档', icon: '📦' },
  { key: 'templates', label: '任务模板', icon: '🧩' },
];

// ── DEPTS for monitor ──

export const DEPTS = MONITOR_DEPTS;

// ── Templates ──

export interface TemplateParam {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'select';
  default?: string;
  required?: boolean;
  options?: string[];
}

export interface Template {
  id: string;
  cat: string;
  icon: string;
  name: string;
  desc: string;
  weight?: number;
  badge?: string;
  outcome?: string;
  starter?: string[];
  modeIds?: WorkbenchModeKey[];
  depts: string[];
  est: string;
  cost: string;
  params: TemplateParam[];
  command: string;
}

export const TEMPLATES: Template[] = [
  {
    id: 'opc-app-dev-launch', cat: '懒人包', icon: '🧩', name: '应用开发开工包',
    badge: '应用开发',
    desc: '适合 SaaS、工具型、AI 应用或独立产品型一人公司，直接生成从 MVP 到首版上线的执行方案。',
    outcome: '输出 MVP 范围、功能优先级、研发排期、测试上线清单和首月迭代节奏。',
    starter: ['明确产品定位与目标用户', '拆出 MVP 功能和开发顺序', '生成上线和首月迭代清单'],
    modeIds: ['app_dev'],
    depts: ['产品规划部', '工程研发部', '合规测试部'], est: '~35分钟', cost: '¥3',
    params: [
      { key: 'product_name', label: '产品名称', type: 'text', required: true },
      { key: 'target_user', label: '目标用户', type: 'text', required: true },
      { key: 'core_problem', label: '核心要解决的问题', type: 'textarea', required: true },
      { key: 'goal', label: '本期目标', type: 'select', options: ['MVP 验证', '首版上线', '功能重构'], default: 'MVP 验证' },
      { key: 'tech_stack', label: '技术偏好', type: 'text', default: 'Next.js + Supabase + OpenAI API' },
    ],
    command: '围绕「{product_name}」为一人公司设计一套应用开发开工方案。目标用户：{target_user}。核心问题：{core_problem}。本期目标：{goal}。技术偏好：{tech_stack}。请输出 MVP 范围、需求优先级、开发排期、测试与上线清单，以及首月迭代建议。',
  },
  {
    id: 'opc-content-studio', cat: '懒人包', icon: '✍️', name: '内容创作增长包',
    badge: '内容创作',
    desc: '适合做公众号、视频号、播客、博客或知识 IP 的一人内容公司，快速生成选题和产出节奏。',
    outcome: '输出内容定位、栏目结构、7 天选题、首批文案框架和分发节奏。',
    starter: ['梳理账号定位与人设', '生成 7 天内容排期', '给出首批可直接写作的选题和文案框架'],
    modeIds: ['content_creation'],
    depts: ['品牌内容部', '经营分析部'], est: '~25分钟', cost: '¥2',
    params: [
      { key: 'content_brand', label: '内容品牌/账号名称', type: 'text', required: true },
      { key: 'audience', label: '目标受众', type: 'text', required: true },
      { key: 'channels', label: '主要渠道', type: 'text', default: '公众号、小红书、视频号' },
      { key: 'topic_domain', label: '内容主题方向', type: 'text', required: true },
      { key: 'conversion_goal', label: '转化目标', type: 'select', options: ['涨粉', '获客', '卖课', '卖服务'], default: '获客' },
    ],
    command: '为内容品牌「{content_brand}」制定一套一人公司内容创作增长方案。目标受众：{audience}。主要渠道：{channels}。主题方向：{topic_domain}。转化目标：{conversion_goal}。请输出账号定位、栏目结构、7 天选题排期、首批内容框架和分发动作。',
  },
  {
    id: 'opc-marketing-consulting', cat: '懒人包', icon: '📣', name: '营销咨询成交包',
    badge: '营销咨询',
    desc: '适合做品牌顾问、增长顾问、投放咨询或商业顾问的一人服务公司，直接产出可售卖方案。',
    outcome: '输出咨询产品包装、客户分层、获客路径、成交话术和 30 天推进计划。',
    starter: ['定义服务卖点与报价结构', '梳理目标客户和获客渠道', '生成咨询提案和成交话术'],
    modeIds: ['marketing_consulting'],
    depts: ['经营分析部', '品牌内容部', '交付运营部'], est: '~30分钟', cost: '¥2.5',
    params: [
      { key: 'service_name', label: '咨询服务名称', type: 'text', required: true },
      { key: 'client_type', label: '目标客户类型', type: 'text', required: true },
      { key: 'problem_scope', label: '客户最常见问题', type: 'textarea', required: true },
      { key: 'offer_type', label: '服务形式', type: 'select', options: ['诊断咨询', '陪跑顾问', '项目代做', '培训 + 顾问'], default: '陪跑顾问' },
      { key: 'acquisition_channels', label: '现有获客渠道', type: 'text', default: '朋友圈、公众号、社群、转介绍' },
    ],
    command: '为一人公司咨询产品「{service_name}」设计成交方案。目标客户：{client_type}。客户常见问题：{problem_scope}。服务形式：{offer_type}。现有获客渠道：{acquisition_channels}。请输出产品包装、报价结构、获客路径、成交话术和 30 天咨询业务推进计划。',
  },
  {
    id: 'opc-tech-service-delivery', cat: '懒人包', icon: '🛠️', name: '技术服务交付包',
    badge: '技术服务',
    desc: '适合接网站开发、自动化、AI 集成、运维改造等项目的一人技术服务公司，直接落到交付。',
    outcome: '输出需求诊断、实施范围、交付排期、风险点、报价建议和售后边界。',
    starter: ['明确服务范围与验收边界', '拆出实施阶段和风险点', '生成报价与售后说明'],
    modeIds: ['tech_service'],
    depts: ['工程研发部', '安全运维部', '交付运营部'], est: '~40分钟', cost: '¥3.5',
    params: [
      { key: 'service_type', label: '服务类型', type: 'text', required: true },
      { key: 'client_background', label: '客户背景', type: 'text', required: true },
      { key: 'current_system', label: '现有系统/环境', type: 'textarea', required: true },
      { key: 'delivery_goal', label: '期望交付结果', type: 'textarea', required: true },
      { key: 'timeline', label: '预期交付周期', type: 'select', options: ['1 周内', '2 周内', '1 个月内', '按阶段推进'], default: '2 周内' },
    ],
    command: '为一人技术服务项目设计交付方案。服务类型：{service_type}。客户背景：{client_background}。现有系统/环境：{current_system}。期望交付结果：{delivery_goal}。预期周期：{timeline}。请输出需求诊断、实施步骤、风险点、报价建议、验收边界和售后支持说明。',
  },
  {
    id: 'opc-education-program', cat: '懒人包', icon: '🎓', name: '教育培训产品包',
    badge: '教育培训',
    desc: '适合知识付费、训练营、工作坊或企业内训型一人教育公司，快速拿到课程和成交方案。',
    outcome: '输出课程结构、教学大纲、招生文案、交付形式、课后转化与复购方案。',
    starter: ['搭建课程结构与学习路径', '生成招生与转化文案', '明确交付节奏与复购设计'],
    modeIds: ['education_training'],
    depts: ['产品规划部', '品牌内容部', '经营分析部'], est: '~35分钟', cost: '¥2.8',
    params: [
      { key: 'program_name', label: '课程/训练营名称', type: 'text', required: true },
      { key: 'learner_profile', label: '学员画像', type: 'text', required: true },
      { key: 'learning_result', label: '希望学员获得的结果', type: 'textarea', required: true },
      { key: 'delivery_format', label: '交付形式', type: 'select', options: ['录播课', '直播课', '训练营', '企业内训'], default: '训练营' },
      { key: 'price_band', label: '目标价格带', type: 'text', default: '1999-3999 元' },
    ],
    command: '围绕「{program_name}」设计一套一人公司教育培训产品方案。学员画像：{learner_profile}。学习结果：{learning_result}。交付形式：{delivery_format}。目标价格带：{price_band}。请输出课程结构、教学大纲、招生文案、交付节奏、课后转化与复购设计。',
  },
  {
    id: 'tpl-weekly-report', cat: '日常办公', icon: '📝', name: '周报生成',
    desc: '基于本周看板数据和各部产出，自动生成结构化周报',
    weight: 88,
    depts: ['经营分析部', '品牌内容部'], est: '~10分钟', cost: '¥0.5',
    params: [
      { key: 'date_range', label: '报告周期', type: 'text', default: '本周', required: true },
      { key: 'focus', label: '重点关注（逗号分隔）', type: 'text', default: '项目进展,下周计划' },
      { key: 'format', label: '输出格式', type: 'select', options: ['Markdown', '飞书文档'], default: 'Markdown' },
    ],
    command: '生成{date_range}的周报，重点覆盖{focus}，输出为{format}格式',
  },
  {
    id: 'tpl-meeting-minutes', cat: '日常办公', icon: '🗒️', name: '会议纪要整理',
    desc: '把会议录音、速记或散乱笔记整理成结构化纪要和待办清单',
    weight: 84,
    modeIds: ['app_dev', 'marketing_consulting', 'education_training'],
    depts: ['交付运营部', '品牌内容部'], est: '~8分钟', cost: '¥0.4',
    params: [
      { key: 'meeting_topic', label: '会议主题', type: 'text', required: true },
      { key: 'notes', label: '会议内容/笔记', type: 'textarea', required: true },
      { key: 'focus', label: '输出重点', type: 'select', options: ['决策 + 待办', '完整纪要', '仅待办清单'], default: '决策 + 待办' },
    ],
    command: '整理会议纪要。会议主题：{meeting_topic}。原始记录：{notes}。请输出{focus}，并明确责任人与时间节点。',
  },
  {
    id: 'tpl-action-breakdown', cat: '日常办公', icon: '✅', name: '任务拆解清单',
    desc: '把一个目标拆成可执行步骤、优先级和责任分工',
    weight: 80,
    modeIds: ['app_dev', 'marketing_consulting', 'tech_service', 'education_training'],
    depts: ['产品规划部', '交付运营部'], est: '~12分钟', cost: '¥0.8',
    params: [
      { key: 'goal', label: '目标/项目', type: 'text', required: true },
      { key: 'deadline', label: '截止时间', type: 'text', default: '本周内' },
      { key: 'constraints', label: '约束条件', type: 'textarea', default: '资源有限，优先完成关键路径' },
    ],
    command: '把目标「{goal}」拆解为执行清单。截止时间：{deadline}。约束：{constraints}。请输出按优先级排序的步骤、责任建议和检查点。',
  },
  {
    id: 'tpl-followup-summary', cat: '日常办公', icon: '📌', name: '客户/事项跟进摘要',
    desc: '汇总某个客户或事项的最新进展、风险点和下一步动作',
    weight: 78,
    modeIds: ['marketing_consulting', 'tech_service', 'education_training'],
    depts: ['交付运营部', '经营分析部'], est: '~6分钟', cost: '¥0.3',
    params: [
      { key: 'subject', label: '客户/事项名称', type: 'text', required: true },
      { key: 'context', label: '已有进展', type: 'textarea', required: true },
      { key: 'goal', label: '希望输出', type: 'select', options: ['跟进摘要', '风险提醒', '下一步建议'], default: '跟进摘要' },
    ],
    command: '针对「{subject}」整理跟进摘要。背景与进展：{context}。请输出{goal}，并明确当前风险和下一步动作。',
  },
  {
    id: 'tpl-boss-brief', cat: '日常办公', icon: '📣', name: '老板汇报摘要',
    desc: '把项目进展、风险和下一步动作压缩成老板可快速浏览的一页摘要',
    weight: 100,
    modeIds: ['app_dev', 'content_creation', 'marketing_consulting', 'tech_service', 'education_training'],
    depts: ['交付运营部', '品牌内容部'], est: '~8分钟', cost: '¥0.4',
    params: [
      { key: 'topic', label: '汇报主题', type: 'text', required: true },
      { key: 'context', label: '项目进展/背景', type: 'textarea', required: true },
      { key: 'focus', label: '汇报重点', type: 'select', options: ['进展 + 风险 + 下一步', '结论优先', '给老板决策用'], default: '进展 + 风险 + 下一步' },
    ],
    command: '整理一版老板汇报摘要。主题：{topic}。背景与进展：{context}。重点：{focus}。请输出能直接发给老板的简洁版本。',
  },
  {
    id: 'tpl-push-reminder', cat: '日常办公', icon: '⏰', name: '催办提醒',
    desc: '把待推进事项整理成明确、不冒犯但有推动力的催办话术',
    weight: 96,
    modeIds: ['app_dev', 'content_creation', 'marketing_consulting', 'tech_service', 'education_training'],
    depts: ['交付运营部', '品牌内容部'], est: '~5分钟', cost: '¥0.2',
    params: [
      { key: 'subject', label: '催办对象/事项', type: 'text', required: true },
      { key: 'context', label: '当前背景', type: 'textarea', required: true },
      { key: 'tone', label: '语气', type: 'select', options: ['克制提醒', '礼貌推进', '强执行导向'], default: '礼貌推进' },
    ],
    command: '为事项「{subject}」写一版催办提醒。背景：{context}。语气：{tone}。请直接给可发送版本。',
  },
  {
    id: 'tpl-project-retro', cat: '日常办公', icon: '🔁', name: '项目复盘',
    desc: '围绕结果、问题、经验和改进动作生成结构化复盘',
    weight: 92,
    modeIds: ['app_dev', 'content_creation', 'marketing_consulting', 'tech_service', 'education_training'],
    depts: ['交付运营部', '经营分析部'], est: '~14分钟', cost: '¥0.9',
    params: [
      { key: 'project_name', label: '项目/活动名称', type: 'text', required: true },
      { key: 'result', label: '结果与过程', type: 'textarea', required: true },
      { key: 'focus', label: '复盘重点', type: 'select', options: ['经验教训', '问题追因', '下次改进'], default: '经验教训' },
    ],
    command: '为项目「{project_name}」做复盘。结果与过程：{result}。重点：{focus}。请输出结构化复盘和可执行改进项。',
  },
  {
    id: 'tpl-external-reply', cat: '内容创作', icon: '📮', name: '对外回复',
    desc: '为客户、合作方、媒体或公众场景生成专业稳妥的对外回复',
    weight: 94,
    modeIds: ['content_creation', 'marketing_consulting', 'tech_service', 'education_training'],
    depts: ['品牌内容部', '合规测试部'], est: '~7分钟', cost: '¥0.4',
    params: [
      { key: 'audience', label: '回复对象', type: 'text', required: true },
      { key: 'issue', label: '背景/问题', type: 'textarea', required: true },
      { key: 'tone', label: '回复风格', type: 'select', options: ['专业克制', '坚定澄清', '友好解释'], default: '专业克制' },
    ],
    command: '生成一版对外回复。对象：{audience}。背景：{issue}。风格：{tone}。请直接输出可发送版本。',
  },
  {
    id: 'tpl-code-review', cat: '工程开发', icon: '🔍', name: '代码审查',
    desc: '对指定代码仓库/文件进行质量审查，输出问题清单和改进建议',
    weight: 74,
    modeIds: ['app_dev', 'tech_service'],
    depts: ['安全运维部', '合规测试部'], est: '~20分钟', cost: '¥2',
    params: [
      { key: 'repo', label: '仓库/文件路径', type: 'text', required: true },
      { key: 'scope', label: '审查范围', type: 'select', options: ['全量', '增量(最近commit)', '指定文件'], default: '增量(最近commit)' },
      { key: 'focus', label: '重点关注（可选）', type: 'text', default: '安全漏洞,错误处理,性能' },
    ],
    command: '对 {repo} 进行代码审查，范围：{scope}，重点关注：{focus}',
  },
  {
    id: 'tpl-api-design', cat: '工程开发', icon: '⚡', name: 'API 设计与实现',
    desc: '从需求描述到 RESTful API 设计、实现、测试一条龙',
    modeIds: ['app_dev', 'tech_service'],
    depts: ['产品规划部', '安全运维部'], est: '~45分钟', cost: '¥3',
    params: [
      { key: 'requirement', label: '需求描述', type: 'textarea', required: true },
      { key: 'tech', label: '技术栈', type: 'select', options: ['Python/FastAPI', 'Node/Express', 'Go/Gin'], default: 'Python/FastAPI' },
      { key: 'auth', label: '鉴权方式', type: 'select', options: ['JWT', 'API Key', '无'], default: 'JWT' },
    ],
    command: '设计并实现一个 {tech} 的 RESTful API：{requirement}。鉴权方式：{auth}',
  },
  {
    id: 'tpl-bugfix', cat: '工程开发', icon: '🩹', name: 'Bug 修复',
    desc: '定位问题根因，给出修复方案并验证回归风险',
    weight: 86,
    modeIds: ['app_dev', 'tech_service'],
    depts: ['工程研发部', '合规测试部'], est: '~18分钟', cost: '¥1.5',
    params: [
      { key: 'bug_desc', label: '问题描述', type: 'textarea', required: true },
      { key: 'scope', label: '影响范围', type: 'text', default: '当前页面/当前功能' },
      { key: 'expectation', label: '期望结果', type: 'text', default: '恢复正常可用' },
    ],
    command: '修复一个 Bug。问题描述：{bug_desc}。影响范围：{scope}。期望结果：{expectation}。请定位根因、修复并说明验证结果。',
  },
  {
    id: 'tpl-page-revamp', cat: '工程开发', icon: '🖼️', name: '页面改版',
    desc: '围绕指定页面做布局、文案和交互改版，并保持可用性',
    modeIds: ['app_dev', 'tech_service'],
    depts: ['工程研发部', '品牌内容部'], est: '~30分钟', cost: '¥2.2',
    params: [
      { key: 'page_name', label: '页面名称', type: 'text', required: true },
      { key: 'goal', label: '改版目标', type: 'textarea', required: true },
      { key: 'constraints', label: '限制条件', type: 'textarea', default: '保留现有主流程，不影响移动端' },
    ],
    command: '对页面「{page_name}」做改版。目标：{goal}。限制：{constraints}。请给出并落地视觉与交互调整，并说明验证结果。',
  },
  {
    id: 'tpl-automation-script', cat: '工程开发', icon: '🤖', name: '自动化脚本',
    desc: '为重复流程编写脚本或工具，减少手工操作',
    weight: 72,
    modeIds: ['app_dev', 'tech_service'],
    depts: ['工程研发部'], est: '~20分钟', cost: '¥1.6',
    params: [
      { key: 'workflow', label: '要自动化的流程', type: 'textarea', required: true },
      { key: 'input_output', label: '输入输出', type: 'text', default: '读取输入并生成结果文件' },
      { key: 'runtime', label: '脚本环境', type: 'select', options: ['Python', 'Node.js', 'Shell'], default: 'Python' },
    ],
    command: '为以下流程编写自动化脚本：{workflow}。输入输出：{input_output}。运行环境：{runtime}。请给出可执行脚本和使用说明。',
  },
  {
    id: 'tpl-competitor', cat: '数据分析', icon: '📊', name: '竞品分析',
    desc: '爬取竞品网站数据，分析对比，生成结构化报告',
    modeIds: ['marketing_consulting'],
    depts: ['安全运维部', '经营分析部', '品牌内容部'], est: '~60分钟', cost: '¥5',
    params: [
      { key: 'targets', label: '竞品名称/URL（每行一个）', type: 'textarea', required: true },
      { key: 'dimensions', label: '分析维度', type: 'text', default: '产品功能,定价策略,用户评价' },
      { key: 'format', label: '输出格式', type: 'select', options: ['Markdown报告', '表格对比'], default: 'Markdown报告' },
    ],
    command: '对以下竞品进行分析：\n{targets}\n\n分析维度：{dimensions}，输出格式：{format}',
  },
  {
    id: 'tpl-data-report', cat: '数据分析', icon: '📈', name: '数据报告',
    desc: '对给定数据集进行清洗、分析、可视化，输出分析报告',
    modeIds: ['content_creation', 'marketing_consulting'],
    depts: ['经营分析部', '品牌内容部'], est: '~30分钟', cost: '¥2',
    params: [
      { key: 'data_source', label: '数据源描述/路径', type: 'text', required: true },
      { key: 'questions', label: '分析问题（每行一个）', type: 'textarea' },
      { key: 'viz', label: '是否需要可视化图表', type: 'select', options: ['是', '否'], default: '是' },
    ],
    command: '对数据 {data_source} 进行分析。{questions}\n需要可视化：{viz}',
  },
  {
    id: 'tpl-feedback-analysis', cat: '数据分析', icon: '🧠', name: '用户反馈分析',
    desc: '汇总评论、客服记录或调研反馈，提炼共性问题和优先级',
    weight: 82,
    modeIds: ['app_dev', 'content_creation', 'marketing_consulting', 'education_training'],
    depts: ['经营分析部', '品牌内容部'], est: '~25分钟', cost: '¥1.8',
    params: [
      { key: 'feedback_source', label: '反馈来源', type: 'text', required: true },
      { key: 'feedback_text', label: '反馈内容', type: 'textarea', required: true },
      { key: 'goal', label: '输出重点', type: 'select', options: ['问题归类', '优先级建议', '产品改进建议'], default: '问题归类' },
    ],
    command: '分析用户反馈。来源：{feedback_source}。内容：{feedback_text}。请输出{goal}，并给出结构化结论。',
  },
  {
    id: 'tpl-sales-funnel', cat: '数据分析', icon: '💹', name: '销售漏斗复盘',
    desc: '分析线索到成交的转化链路，找出主要流失点和改进动作',
    modeIds: ['marketing_consulting', 'tech_service', 'education_training'],
    depts: ['经营分析部'], est: '~28分钟', cost: '¥2',
    params: [
      { key: 'funnel_data', label: '漏斗数据/描述', type: 'textarea', required: true },
      { key: 'period', label: '分析周期', type: 'text', default: '最近30天' },
      { key: 'focus', label: '重点关注', type: 'text', default: '流失环节,转化率,改进建议' },
    ],
    command: '复盘销售漏斗。周期：{period}。数据：{funnel_data}。重点关注：{focus}。请输出主要问题和改进建议。',
  },
  {
    id: 'tpl-industry-brief', cat: '数据分析', icon: '🌐', name: '行业快报',
    desc: '快速调研某个行业/赛道的最新动态并形成摘要',
    modeIds: ['marketing_consulting', 'education_training', 'content_creation'],
    depts: ['经营分析部'], est: '~35分钟', cost: '¥2.4',
    params: [
      { key: 'topic', label: '行业/主题', type: 'text', required: true },
      { key: 'angle', label: '关注角度', type: 'text', default: '市场规模,趋势,机会点' },
      { key: 'format', label: '输出形式', type: 'select', options: ['摘要简报', '结构化报告'], default: '摘要简报' },
    ],
    command: '围绕「{topic}」做一版行业快报。关注角度：{angle}。输出形式：{format}。请给出最新动态、关键信号和机会判断。',
  },
  {
    id: 'tpl-blog', cat: '内容创作', icon: '✍️', name: '博客文章',
    desc: '给定主题和要求，生成高质量博客文章',
    weight: 70,
    modeIds: ['content_creation', 'education_training'],
    depts: ['品牌内容部'], est: '~15分钟', cost: '¥1',
    params: [
      { key: 'topic', label: '文章主题', type: 'text', required: true },
      { key: 'audience', label: '目标读者', type: 'text', default: '技术人员' },
      { key: 'length', label: '期望字数', type: 'select', options: ['~1000字', '~2000字', '~3000字'], default: '~2000字' },
      { key: 'style', label: '风格', type: 'select', options: ['技术教程', '观点评论', '案例分析'], default: '技术教程' },
    ],
    command: '写一篇关于「{topic}」的博客文章，面向{audience}，{length}，风格：{style}',
  },
  {
    id: 'tpl-title-polish', cat: '内容创作', icon: '🏷️', name: '标题优化',
    desc: '围绕现有内容生成多版标题，兼顾点击率和专业感',
    weight: 90,
    modeIds: ['content_creation', 'marketing_consulting', 'education_training'],
    depts: ['品牌内容部'], est: '~5分钟', cost: '¥0.2',
    params: [
      { key: 'draft_title', label: '原始标题', type: 'text', required: true },
      { key: 'content_summary', label: '内容摘要', type: 'textarea', required: true },
      { key: 'style', label: '标题风格', type: 'select', options: ['行业观察', '案例拆解', '专业克制', '强信息量'], default: '行业观察' },
    ],
    command: '优化标题。原始标题：{draft_title}。内容摘要：{content_summary}。风格：{style}。请给出 5 个不过度标题党的版本。',
  },
  {
    id: 'tpl-social-post', cat: '内容创作', icon: '📣', name: '社媒短文案',
    desc: '根据主题和目标平台生成朋友圈、公众号预告或社媒短文案',
    weight: 87,
    modeIds: ['content_creation', 'marketing_consulting', 'education_training'],
    depts: ['品牌内容部'], est: '~6分钟', cost: '¥0.3',
    params: [
      { key: 'topic', label: '主题/产品', type: 'text', required: true },
      { key: 'platform', label: '平台', type: 'select', options: ['朋友圈', '公众号预告', '小红书', '视频号文案'], default: '朋友圈' },
      { key: 'tone', label: '语气', type: 'select', options: ['专业', '轻松', '克制', '转化导向'], default: '专业' },
    ],
    command: '为{platform}撰写短文案。主题：{topic}。语气：{tone}。请直接给出可发布版本。',
  },
  {
    id: 'tpl-poster-copy', cat: '内容创作', icon: '🎨', name: '海报/活动文案',
    desc: '为活动、课程、发布会等场景生成海报主标题和报名引导语',
    weight: 76,
    modeIds: ['content_creation', 'marketing_consulting', 'education_training'],
    depts: ['品牌内容部'], est: '~8分钟', cost: '¥0.5',
    params: [
      { key: 'event_name', label: '活动/项目名称', type: 'text', required: true },
      { key: 'selling_points', label: '核心卖点', type: 'textarea', required: true },
      { key: 'cta', label: '希望引导动作', type: 'text', default: '立即报名' },
    ],
    command: '为「{event_name}」生成海报文案。核心卖点：{selling_points}。引导动作：{cta}。请输出主标题、副标题和报名引导语。',
  },
  {
    id: 'tpl-deploy', cat: '工程开发', icon: '🚀', name: '部署方案',
    desc: '生成完整的部署检查单、Docker配置、CI/CD流程',
    modeIds: ['app_dev', 'tech_service'],
    depts: ['安全运维部', '工程研发部'], est: '~25分钟', cost: '¥2',
    params: [
      { key: 'project', label: '项目名称/描述', type: 'text', required: true },
      { key: 'env', label: '部署环境', type: 'select', options: ['Docker', 'K8s', 'VPS', 'Serverless'], default: 'Docker' },
      { key: 'ci', label: 'CI/CD 工具', type: 'select', options: ['GitHub Actions', 'GitLab CI', '无'], default: 'GitHub Actions' },
    ],
    command: '为项目「{project}」生成{env}部署方案，CI/CD使用{ci}',
  },
  {
    id: 'tpl-email', cat: '内容创作', icon: '📧', name: '邮件/通知文案',
    desc: '根据场景和目的，生成专业邮件或通知文案',
    modeIds: ['content_creation', 'marketing_consulting', 'education_training'],
    depts: ['品牌内容部'], est: '~5分钟', cost: '¥0.3',
    params: [
      { key: 'scenario', label: '使用场景', type: 'select', options: ['商务邮件', '产品发布', '客户通知', '内部公告'], default: '商务邮件' },
      { key: 'purpose', label: '目的/内容', type: 'textarea', required: true },
      { key: 'tone', label: '语调', type: 'select', options: ['正式', '友好', '简洁'], default: '正式' },
    ],
    command: '撰写一封{scenario}，{tone}语调。内容：{purpose}',
  },
  {
    id: 'tpl-standup', cat: '日常办公', icon: '🗓️', name: '每日站会摘要',
    desc: '汇总各部今日进展和明日计划，生成站会摘要',
    depts: ['交付运营部'], est: '~5分钟', cost: '¥0.3',
    params: [
      { key: 'range', label: '汇总范围', type: 'select', options: ['今天', '最近24小时', '昨天+今天'], default: '今天' },
    ],
    command: '汇总{range}各部工作进展和待办，生成站会摘要',
  },
];

export const TPL_CATS = [
  { name: '全部', icon: '📋' },
  { name: '懒人包', icon: '🧰' },
  { name: '日常办公', icon: '💼' },
  { name: '数据分析', icon: '📊' },
  { name: '工程开发', icon: '⚙️' },
  { name: '内容创作', icon: '✍️' },
];

// ── Main Store ──

interface AppStore {
  // Data
  liveStatus: LiveStatus | null;
  agentConfig: AgentConfig | null;
  agentConfigLoading: boolean;
  agentConfigError: string | null;
  changeLog: ChangeLogEntry[];
  officialsData: OfficialsData | null;
  agentsStatusData: AgentsStatusData | null;

  // UI State
  activeTab: TabKey;
  workbenchMode: WorkbenchModeKey;
  edictFilter: 'active' | 'archived' | 'all';
  sessFilter: string;
  tplCatFilter: string;
  pendingTemplateId: string | null;
  boardPreset: {
    edictFilter?: 'active' | 'archived' | 'all';
    focusFilter?: string;
    deptFilter?: string;
    query?: string;
    flowModeFilter?: string;
  } | null;
  modelConfigFocusAgentId: string | null;
  selectedOfficial: string | null;
  modalTaskId: string | null;
  countdown: number;
  unseenCompletedTaskIds: string[];
  unseenChatTaskNoticeIds: string[];

  // Toast
  toasts: { id: number; msg: string; type: 'ok' | 'err' }[];

  // Actions
  setActiveTab: (tab: TabKey) => void;
  setWorkbenchMode: (mode: WorkbenchModeKey) => void;
  setEdictFilter: (f: 'active' | 'archived' | 'all') => void;
  setSessFilter: (f: string) => void;
  setTplCatFilter: (f: string) => void;
  setPendingTemplateId: (id: string | null) => void;
  setBoardPreset: (preset: {
    edictFilter?: 'active' | 'archived' | 'all';
    focusFilter?: string;
    deptFilter?: string;
    query?: string;
    flowModeFilter?: string;
  } | null) => void;
  consumeBoardPreset: () => {
    edictFilter?: 'active' | 'archived' | 'all';
    focusFilter?: string;
    deptFilter?: string;
    query?: string;
    flowModeFilter?: string;
  } | null;
  setModelConfigFocusAgentId: (id: string | null) => void;
  setSelectedOfficial: (id: string | null) => void;
  setModalTaskId: (id: string | null) => void;
  setCountdown: (n: number) => void;
  markCompletedTasksSeen: () => void;
  markChatTaskNoticesSeen: () => void;
  toast: (msg: string, type?: 'ok' | 'err') => void;

  // Data fetching
  loadLive: () => Promise<void>;
  loadAgentConfig: () => Promise<void>;
  loadOfficials: () => Promise<void>;
  loadAgentsStatus: () => Promise<void>;
  loadAll: () => Promise<void>;
}

let _toastId = 0;
let _lastAutoSchedulerScanAt = 0;

export const useStore = create<AppStore>((set, get) => ({
  liveStatus: null,
  agentConfig: null,
  agentConfigLoading: false,
  agentConfigError: null,
  changeLog: [],
  officialsData: null,
  agentsStatusData: null,

  activeTab: 'chat',
  workbenchMode: 'all',
  edictFilter: 'active',
  sessFilter: 'all',
  tplCatFilter: '全部',
  pendingTemplateId: null,
  boardPreset: null,
  modelConfigFocusAgentId: null,
  selectedOfficial: null,
  modalTaskId: null,
  countdown: 5,
  unseenCompletedTaskIds: [],
  unseenChatTaskNoticeIds: [],

  toasts: [],

  setActiveTab: (tab) => {
    set({ activeTab: tab });
    const s = get();
    if (['models', 'skills', 'sessions'].includes(tab)) s.loadAgentConfig();
    if (tab === 'officials' && !s.officialsData) s.loadOfficials();
  },
  setWorkbenchMode: (_mode) => set({ workbenchMode: 'all', tplCatFilter: '全部', selectedOfficial: null }),
  setEdictFilter: (f) => set({ edictFilter: f }),
  setSessFilter: (f) => set({ sessFilter: f }),
  setTplCatFilter: (f) => set({ tplCatFilter: f }),
  setPendingTemplateId: (id) => set({ pendingTemplateId: id }),
  setBoardPreset: (preset) => set({ boardPreset: preset }),
  consumeBoardPreset: () => {
    const preset = get().boardPreset;
    if (preset) set({ boardPreset: null });
    return preset;
  },
  setModelConfigFocusAgentId: (id) => set({ modelConfigFocusAgentId: id }),
  setSelectedOfficial: (id) => set({ selectedOfficial: id }),
  setModalTaskId: (id) => set({ modalTaskId: id }),
  setCountdown: (n) => set({ countdown: n }),
  markCompletedTasksSeen: () => set({ unseenCompletedTaskIds: [] }),
  markChatTaskNoticesSeen: () => set({ unseenChatTaskNoticeIds: [] }),

  toast: (msg, type = 'ok') => {
    const id = ++_toastId;
    set((s) => ({ toasts: [...s.toasts, { id, msg, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 3000);
  },

  loadLive: async () => {
    try {
      const prevLive = get().liveStatus;
      const data = await api.liveStatus();
      const prevDoneIds = new Set(
        (prevLive?.tasks || [])
          .filter((task) => isTerminalState(task.state) && !task.archived && !isScheduledTask(task))
          .map((task) => String(task.id || ''))
      );
      const nextDone = (data.tasks || []).filter(
        (task) => isTerminalState(task.state) && !task.archived && !isScheduledTask(task)
      );
      const freshDoneIds = nextDone
        .map((task) => String(task.id || ''))
        .filter((taskId) => taskId && !prevDoneIds.has(taskId));
      const freshChatNoticeIds = nextDone
        .filter((task) => {
          const sourceMeta = task.sourceMeta as Record<string, unknown> | undefined;
          const templateParams = task.templateParams as Record<string, unknown> | undefined;
          const chatSessionId =
            String(sourceMeta?.chatSessionId || '').trim() || String(templateParams?.chatSessionId || '').trim();
          return Boolean(chatSessionId);
        })
        .map((task) => String(task.id || ''))
        .filter((taskId) => taskId && !prevDoneIds.has(taskId));

      set((state) => ({
        liveStatus: data,
        unseenCompletedTaskIds: Array.from(
          new Set(
            state.unseenCompletedTaskIds
              .filter((taskId) => nextDone.some((task) => String(task.id || '') === taskId))
              .concat(freshDoneIds)
          )
        ),
        unseenChatTaskNoticeIds: Array.from(
          new Set(
            state.unseenChatTaskNoticeIds
              .filter((taskId) => nextDone.some((task) => String(task.id || '') === taskId))
              .concat(freshChatNoticeIds)
          )
        ),
      }));

      if (freshDoneIds.length > 0) {
        get().toast(`📦 有 ${freshDoneIds.length} 个任务已完成，交付已进入归档。`, 'ok');
      }
      if (freshChatNoticeIds.length > 0) {
        get().toast(`💬 有 ${freshChatNoticeIds.length} 条任务完成提醒已回到对话。`, 'ok');
      }

      const prevAlertKey = automationAlertKey(prevLive);
      const nextAlertKey = automationAlertKey(data);
      if (!prevAlertKey && nextAlertKey) {
        const count = data.automation?.summary?.alertCount || 0;
        const lead = data.automation?.alerts?.[0]?.name || '自动化任务';
        get().toast(`⚠️ 检测到 ${count} 个自动化任务异常，优先检查：${lead}`, 'err');
      } else if (prevAlertKey && !nextAlertKey) {
        get().toast('✅ 自动化任务已恢复正常', 'ok');
      } else if (prevAlertKey && nextAlertKey && prevAlertKey !== nextAlertKey) {
        const critical = data.automation?.summary?.criticalCount || 0;
        const lead = data.automation?.alerts?.[0]?.name || '自动化任务';
        get().toast(
          critical > 0
            ? `⚠️ 自动化告警升级，优先处理：${lead}`
            : `⚠️ 自动化预警发生变化，优先检查：${lead}`,
          'err'
        );
      }

      // Also preload officials for monitor tab
      const s = get();
      if (!s.officialsData) {
        api.officialsStats().then((d) => set({ officialsData: d })).catch(() => {});
      }
    } catch {
      // silently fail
    }
  },

  loadAgentConfig: async () => {
    set({ agentConfigLoading: true, agentConfigError: null });
    try {
      const cfg = await api.agentConfig();
      const log = await api.modelChangeLog();
      const agents = Array.isArray(cfg?.agents) ? cfg.agents : [];
      if (!agents.length) {
        set({
          agentConfig: null,
          changeLog: log,
          agentConfigLoading: false,
          agentConfigError: '模型配置接口已返回，但没有可用的 Agent 数据。',
        });
        return;
      }
      set({
        agentConfig: { ...cfg, agents },
        changeLog: log,
        agentConfigLoading: false,
        agentConfigError: null,
      });
    } catch (err) {
      set({
        agentConfigLoading: false,
        agentConfigError: err instanceof Error ? err.message : '模型配置加载失败',
      });
    }
  },

  loadOfficials: async () => {
    try {
      const data = await api.officialsStats();
      set({ officialsData: data });
    } catch {
      // silently fail
    }
  },

  loadAgentsStatus: async () => {
    try {
      const data = await api.agentsStatus();
      set({ agentsStatusData: data });
    } catch {
      set({ agentsStatusData: null });
    }
  },

  loadAll: async () => {
    const s = get();
    await s.loadLive();
    const now = Date.now();
    if (now - _lastAutoSchedulerScanAt >= AUTO_SCHEDULER_SCAN_MS) {
      _lastAutoSchedulerScanAt = now;
      try {
        const result = await api.schedulerScan();
        if (result.ok && (result.count || 0) > 0) {
          await s.loadLive();
        }
      } catch {
        // silently fail
      }
    }
    const tab = s.activeTab;
    if (['models', 'skills'].includes(tab)) await s.loadAgentConfig();
  },
}));

// ── Countdown & Polling ──

let _cdTimer: ReturnType<typeof setInterval> | null = null;

export function startPolling() {
  if (_cdTimer) return;
  useStore.getState().loadAll();
  _cdTimer = setInterval(() => {
    const s = useStore.getState();
    const cd = s.countdown - 1;
    if (cd <= 0) {
      s.setCountdown(5);
      s.loadAll();
    } else {
      s.setCountdown(cd);
    }
  }, 1000);
}

export function stopPolling() {
  if (_cdTimer) {
    clearInterval(_cdTimer);
    _cdTimer = null;
  }
}

// ── Utility ──

export function esc(s: string | undefined | null): string {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function timeAgo(iso: string | undefined): string {
  if (!iso) return '';
  try {
    const d = parseTimeValue(iso);
    if (!d) return '';
    if (isNaN(d.getTime())) return '';
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return mins + '分钟前';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + '小时前';
    return Math.floor(hrs / 24) + '天前';
  } catch {
    return '';
  }
}

export type SyncIndicator = {
  tone: 'ok' | 'warn' | 'err';
  label: string;
  detail: string;
};

export type AutomationIndicator = {
  tone: 'ok' | 'warn' | 'err';
  label: string;
  detail: string;
};

function automationAlertKey(liveStatus: LiveStatus | null): string {
  const alerts = liveStatus?.automation?.alerts || [];
  return alerts
    .map((job) => [job.id, job.status, job.lastRunStatus, job.lastDeliveryStatus, job.nextRunAt].join(':'))
    .join('|');
}

export function getSyncIndicator(liveStatus: LiveStatus | null): SyncIndicator {
  if (!liveStatus) {
    return {
      tone: 'warn',
      label: '⏳ 连接中…',
      detail: '正在等待看板状态返回',
    };
  }

  const syncStatus = liveStatus.syncStatus || {};
  const syncOk = typeof syncStatus.ok === 'boolean' ? syncStatus.ok : null;
  const syncError =
    typeof syncStatus.error === 'string' && syncStatus.error.trim() ? syncStatus.error.trim() : '';

  if (syncOk === true) {
    return {
      tone: 'ok',
      label: '✅ 同步正常',
      detail: '同步链路正常',
    };
  }

  if (syncError) {
    return {
      tone: 'err',
      label: '⚠️ 已连接 · 同步异常',
      detail: '同步存在异常',
    };
  }

  return {
    tone: 'warn',
    label: '🟡 已连接 · 同步待确认',
    detail: '同步状态待确认',
  };
}

export function getAutomationIndicator(liveStatus: LiveStatus | null): AutomationIndicator {
  const automation = liveStatus?.automation;
  const summary = automation?.summary;
  const jobCount = summary?.jobCount || 0;
  const criticalCount = summary?.criticalCount || 0;
  const warningCount = summary?.warningCount || 0;
  const pendingCount = summary?.pendingCount || 0;

  if (!jobCount) {
    return {
      tone: 'warn',
      label: '自动化待接入',
      detail: '暂无已纳入监测的自动化任务',
    };
  }

  if (criticalCount > 0) {
    return {
      tone: 'err',
      label: `自动化告警 ${criticalCount}`,
      detail: `${criticalCount} 个任务执行失败或连续异常`,
    };
  }

  if (warningCount > 0) {
    return {
      tone: 'warn',
      label: `自动化预警 ${warningCount}`,
      detail: `${warningCount} 个任务已超过计划执行时间`,
    };
  }

  if (pendingCount > 0) {
    return {
      tone: 'warn',
      label: `自动化待首跑 ${pendingCount}`,
      detail: `${pendingCount} 个自动化任务等待首次执行`,
    };
  }

  return {
    tone: 'ok',
    label: `自动化正常 ${jobCount}`,
    detail: `${jobCount} 个自动化任务运行正常`,
  };
}
