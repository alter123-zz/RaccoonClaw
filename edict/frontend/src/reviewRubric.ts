import reviewRubricJson from '../../../shared/review-rubric.json';
import type { Task } from './api';
import { taskModeKey, type WorkbenchModeKey } from './workbenchModes';

type FindingLevel = {
  key: string;
  label: string;
  decision: string;
  description: string;
};

type ReviewCheck = {
  key: string;
  label: string;
  aliases: string[];
  prompt: string;
};

type ReviewProfileConfig = {
  label: string;
  requiredChecks: string[];
  readinessChecks: string[];
  focus: string[];
};

type DynamicSignal = {
  match: string[];
  addChecks: string[];
};

type ReviewRubricConfig = {
  findingLevels: FindingLevel[];
  checks: ReviewCheck[];
  profiles: Record<string, ReviewProfileConfig>;
  dynamicSignals: DynamicSignal[];
};

export type ReviewProfile = {
  key: string;
  label: string;
  requiredChecks: ReviewCheck[];
  readinessChecks: ReviewCheck[];
  focus: string[];
  findingLevels: FindingLevel[];
};

const REVIEW_RUBRIC = reviewRubricJson as ReviewRubricConfig;
const CHECK_MAP = REVIEW_RUBRIC.checks.reduce<Record<string, ReviewCheck>>((acc, item) => {
  acc[item.key] = item;
  return acc;
}, {});

function dynamicChecks(requirement: string): string[] {
  const lowered = String(requirement || '').toLowerCase();
  const selected: string[] = [];
  REVIEW_RUBRIC.dynamicSignals.forEach((item) => {
    if (item.match.some((signal) => lowered.includes(signal.toLowerCase()))) {
      item.addChecks.forEach((key) => {
        if (!selected.includes(key)) selected.push(key);
      });
    }
  });
  return selected;
}

export function getReviewProfile(mode: WorkbenchModeKey | 'default' | null | undefined, requirement = ''): ReviewProfile {
  const key = mode && REVIEW_RUBRIC.profiles[mode] ? mode : 'default';
  const merged = {
    ...REVIEW_RUBRIC.profiles.default,
    ...(REVIEW_RUBRIC.profiles[key] || {}),
  };
  const requiredKeys = [...merged.requiredChecks];
  const readinessKeys = [...merged.readinessChecks];
  dynamicChecks(requirement).forEach((check) => {
    if (!requiredKeys.includes(check)) requiredKeys.push(check);
    if (['security', 'testing', 'delivery'].includes(check) && !readinessKeys.includes(check)) {
      readinessKeys.push(check);
    }
  });
  return {
    key,
    label: merged.label,
    requiredChecks: requiredKeys.map((item) => CHECK_MAP[item]).filter(Boolean),
    readinessChecks: readinessKeys.map((item) => CHECK_MAP[item]).filter(Boolean),
    focus: merged.focus || [],
    findingLevels: REVIEW_RUBRIC.findingLevels,
  };
}

export function getTaskReviewProfile(task: Task | null | undefined): ReviewProfile {
  const mode = task ? taskModeKey(task) : null;
  return getReviewProfile(mode, String(task?.title || ''));
}
