import workflowConfigData from '../../../shared/workflow-config.json';

export interface PipelineStage {
  key: string;
  dept: string;
  icon: string;
  action: string;
}

export interface ManualAdvanceStep {
  next: string;
  from: string;
  to: string;
  remark: string;
}

interface WorkflowConfig {
  pipeline: PipelineStage[];
  stateIndex: Record<string, number>;
  stateLabels: Record<string, string>;
  boardOrder: Record<string, number>;
  terminalStates: string[];
  stopDisabledStates: string[];
  resumableStates: string[];
  orgResolvedStates: string[];
  stateAgentMap: Record<string, string | null>;
  manualAdvance: Record<string, ManualAdvanceStep>;
  stateTransitions: Record<string, string[]>;
}

export const WORKFLOW_CONFIG = workflowConfigData as WorkflowConfig;
export const WORKFLOW_PIPE = WORKFLOW_CONFIG.pipeline;
export const WORKFLOW_STATE_INDEX = WORKFLOW_CONFIG.stateIndex;
export const WORKFLOW_STATE_LABELS = WORKFLOW_CONFIG.stateLabels;
export const WORKFLOW_BOARD_ORDER = WORKFLOW_CONFIG.boardOrder;
export const WORKFLOW_TERMINAL_STATES = WORKFLOW_CONFIG.terminalStates;
export const WORKFLOW_STOP_DISABLED_STATES = WORKFLOW_CONFIG.stopDisabledStates;
export const WORKFLOW_RESUMABLE_STATES = WORKFLOW_CONFIG.resumableStates;
export const WORKFLOW_MANUAL_ADVANCE = WORKFLOW_CONFIG.manualAdvance;
export const WORKFLOW_MANUAL_ADVANCE_STATES = Object.keys(WORKFLOW_MANUAL_ADVANCE);
