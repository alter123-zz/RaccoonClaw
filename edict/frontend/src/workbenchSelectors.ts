import type { RemoteSkillItem, Task } from './api';
import { canonicalAgentId } from './agentRegistry';
import { isArchived, isEdict, isScheduledTask, isTerminalState, type Template } from './store';
import { getVisibleAgentIds, getWorkbenchMode, taskMatchesWorkbenchMode, type WorkbenchModeKey } from './workbenchModes';

export function extractSessionAgent(task: Task): string {
  const match = (task.id || '').match(/^OC-(\w+)-/);
  if (match) return match[1];
  return (task.org || '').replace(/省|部/g, '').toLowerCase();
}

function isChiefOfStaffSession(task: Task): boolean {
  const agentId = canonicalAgentId(extractSessionAgent(task));
  return agentId === 'chief_of_staff' || task.org === '总裁办';
}

export function selectWorkbenchTasks(tasks: Task[], mode: WorkbenchModeKey) {
  const visibleAgentIds = new Set(getVisibleAgentIds(mode));
  const edicts = tasks.filter((task) => isEdict(task) && taskMatchesWorkbenchMode(task, mode));
  const activeEdicts = edicts.filter(
    (task) => !isArchived(task) && !isTerminalState(task.state) && !isScheduledTask(task),
  );
  const archivedEdicts = edicts.filter((task) => isArchived(task));
  const scheduledEdicts = edicts.filter((task) => !isArchived(task) && isScheduledTask(task));
  const terminalEdicts = edicts.filter((task) => isTerminalState(task.state) && !isScheduledTask(task));
  const sessions = tasks.filter(
    (task) =>
      !isEdict(task) &&
      isChiefOfStaffSession(task) &&
      (mode === 'all'
        || visibleAgentIds.has(canonicalAgentId(extractSessionAgent(task)))
        || canonicalAgentId(extractSessionAgent(task)) === 'chief_of_staff')
  );

  return {
    modeConfig: getWorkbenchMode(mode),
    visibleAgentIds,
    edicts,
    activeEdicts,
    archivedEdicts,
    scheduledEdicts,
    terminalEdicts,
    sessions,
  };
}

export function selectVisibleAgentsByMode<T extends { id: string }>(items: T[], mode: WorkbenchModeKey): T[] {
  if (mode === 'all') return items;
  const visibleIds = new Set(getVisibleAgentIds(mode).map((item) => canonicalAgentId(item)));
  return items.filter((item) => visibleIds.has(canonicalAgentId(item.id)));
}

export function selectVisibleRemoteSkillsByMode(items: RemoteSkillItem[], mode: WorkbenchModeKey): RemoteSkillItem[] {
  if (mode === 'all') return items;
  const visibleIds = new Set(getVisibleAgentIds(mode).map((item) => canonicalAgentId(item)));
  return items.filter((item) => visibleIds.has(canonicalAgentId(item.agentId)));
}

export function selectTemplatesByMode(templates: Template[], mode: WorkbenchModeKey, category?: string): Template[] {
  let filtered = templates;
  if (category && category !== '全部') {
    filtered = filtered.filter((template) => template.cat === category);
  }
  if (mode !== 'all') {
    filtered = filtered.filter((template) => (template.modeIds || []).includes(mode));
  }
  return [...filtered].sort((a, b) => {
    const weightDiff = (b.weight || 0) - (a.weight || 0);
    if (weightDiff !== 0) return weightDiff;
    return a.name.localeCompare(b.name, 'zh-Hans-CN');
  });
}
