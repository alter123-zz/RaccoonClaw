import type { Task } from './api';
import { canonicalAgentId } from './agentRegistry';
import workbenchModesJson from '../../../shared/workbench-modes.json';

export type WorkbenchModeKey =
  | 'all'
  | 'app_dev'
  | 'content_creation'
  | 'marketing_consulting'
  | 'tech_service'
  | 'education_training';

export interface WorkbenchMode {
  key: WorkbenchModeKey;
  icon: string;
  label: string;
  desc: string;
  defaultTargetDept: string;
  agentIds: string[];
  depts: string[];
  specialistDepts: string[];
  workflow: string[];
  templateIds: string[];
}

export const WORKBENCH_MODES: WorkbenchMode[] = workbenchModesJson as WorkbenchMode[];

export const WORKBENCH_MODE_MAP = WORKBENCH_MODES.reduce<Record<WorkbenchModeKey, WorkbenchMode>>((acc, mode) => {
  acc[mode.key] = mode;
  return acc;
}, {} as Record<WorkbenchModeKey, WorkbenchMode>);

export function getWorkbenchMode(mode: WorkbenchModeKey): WorkbenchMode {
  return WORKBENCH_MODE_MAP[mode] || WORKBENCH_MODE_MAP.all;
}

export function getVisibleAgentIds(mode: WorkbenchModeKey): string[] {
  return getWorkbenchMode(mode).agentIds;
}

export function getVisibleDeptLabels(mode: WorkbenchModeKey): string[] {
  return getWorkbenchMode(mode).depts;
}

export function getDefaultTargetDept(mode: WorkbenchModeKey): string {
  return getWorkbenchMode(mode).defaultTargetDept;
}

export function taskModeKey(task: Task): WorkbenchModeKey | null {
  const explicit = String(task.modeId || task.templateParams?.modeId || task.templateParams?.workbenchMode || task.sourceMeta?.modeId || task.sourceMeta?.workbenchMode || '').trim() as WorkbenchModeKey;
  if (explicit && explicit in WORKBENCH_MODE_MAP) return explicit;

  const templateId = String(task.templateId || '').trim();
  if (!templateId) return null;

  for (const mode of WORKBENCH_MODES) {
    if (mode.key === 'all') continue;
    if (mode.templateIds.includes(templateId)) return mode.key;
  }
  return null;
}

export function taskMatchesWorkbenchMode(task: Task, mode: WorkbenchModeKey): boolean {
  if (mode === 'all') return true;

  const explicitMode = taskModeKey(task);
  if (explicitMode) return explicitMode === mode;

  const cfg = getWorkbenchMode(mode);
  const specialistSet = new Set(cfg.specialistDepts);
  if (specialistSet.has(task.targetDept || '')) return true;
  if (specialistSet.has(task.org || '')) return true;

  const flow = task.flow_log || [];
  return flow.some((entry) => specialistSet.has(entry.from) || specialistSet.has(entry.to));
}

export function agentVisibleInMode(agentId: string, mode: WorkbenchModeKey): boolean {
  return mode === 'all' || getVisibleAgentIds(mode).map((id) => canonicalAgentId(id)).includes(canonicalAgentId(agentId));
}

export function deptVisibleInMode(label: string, mode: WorkbenchModeKey): boolean {
  return mode === 'all' || getVisibleDeptLabels(mode).includes(label);
}
