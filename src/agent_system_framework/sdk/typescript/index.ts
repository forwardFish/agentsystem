export interface AgentMeta {
  agentId: string;
  agentType: "transactional" | "business";
  plane: "build" | "runtime" | "governance";
  capabilities: string[];
}

export interface TaskEnvelope {
  taskId: string;
  runId: string;
  shardId: string;
  graphType: string;
  inputRef: string;
  ruleVersion: string;
  traceId: string;
}
