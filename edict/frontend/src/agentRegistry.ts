import agentRegistryData from '../../../shared/agent-registry.json';

export interface AgentRegistryEntry {
  id: string;
  label: string;
  emoji: string;
  displayRole: string;
  rank: string;
  duty: string;
  apiRole: string;
}

export const AGENT_REGISTRY = agentRegistryData as AgentRegistryEntry[];

export const MONITOR_DEPTS = AGENT_REGISTRY.map((agent) => ({
  id: agent.id,
  label: agent.label,
  emoji: agent.emoji,
  role: agent.displayRole,
  rank: agent.rank,
}));

export const AGENT_LABELS = AGENT_REGISTRY.reduce<Record<string, string>>((acc, agent) => {
  acc[agent.id] = agent.label;
  return acc;
}, {});

export const AGENT_DISPLAY_LABELS: Record<string, string> = {
  chief_of_staff: '总裁办',
  planning: '产品规划部',
  review_control: '评审质控部',
  delivery_ops: '交付运营部',
  brand_content: '品牌内容部',
  business_analysis: '经营分析部',
  secops: '安全运维部',
  compliance_test: '合规测试部',
  engineering: '工程研发部',
  people_ops: '人力组织部',
};

export const AGENT_CANONICAL_IDS: Record<string, string> = {
  chief_of_staff: 'chief_of_staff',
  planning: 'planning',
  review_control: 'review_control',
  delivery_ops: 'delivery_ops',
  brand_content: 'brand_content',
  business_analysis: 'business_analysis',
  secops: 'secops',
  compliance_test: 'compliance_test',
  engineering: 'engineering',
  people_ops: 'people_ops',
};

export function canonicalAgentId(agentId: string): string {
  return AGENT_CANONICAL_IDS[agentId] || agentId;
}

export function displayAgentLabel(agentId: string): string {
  return AGENT_LABELS[agentId] || AGENT_DISPLAY_LABELS[agentId] || agentId;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const LEGACY_TEXT_LABELS: Record<string, string> = {
  chief_of_staff: '总裁办',
  ChiefOfStaff: '总裁办',
  planning: '产品规划部',
  Planning: '产品规划部',
  review_control: '评审质控部',
  ReviewControl: '评审质控部',
  delivery_ops: '交付运营部',
  brand_content: '品牌内容部',
  business_analysis: '经营分析部',
  secops: '安全运维部',
  compliance_test: '合规测试部',
  engineering: '工程研发部',
  people_ops: '人力组织部',
};

const LEGACY_TEXT_PATTERN = new RegExp(
  Object.keys(LEGACY_TEXT_LABELS)
    .sort((a, b) => b.length - a.length)
    .map((item) => escapeRegExp(item))
    .join('|'),
  'g'
);

export function sanitizeAgentText(text: string): string {
  if (!text) return '';
  return text.replace(LEGACY_TEXT_PATTERN, (matched) => LEGACY_TEXT_LABELS[matched] || matched);
}
