/**
 * Types for the autonomous investigation data produced by the
 * Adaptive Planner / 6-agent pipeline (see backend/app/services/*).
 *
 * IMPORTANT: `apiFetch` in services/api.ts deep-converts every backend
 * response from snake_case to camelCase (and ISO date strings to Date
 * objects) before it reaches the UI. These types describe the data
 * AFTER that conversion — i.e. exactly what components receive.
 *
 * All fields are optional because:
 *  - older cases created before this pipeline existed may not have them
 *  - the Adaptive Planner conditionally skips Agent 3 / Agent 4, so their
 *    outputs may legitimately be empty objects/arrays
 */

// ── Agent 1 — Anomaly Detection ────────────────────────────────────────────
export interface AnomalyScores {
  xgbScore?: number;
  isoScore?: number;
  probability?: number;
  riskLevel?: "low" | "medium" | "high" | "critical" | string;
}

export interface ShapFeature {
  feature: string;
  value: number;
}

// ── Agent 2 — Evidence ──────────────────────────────────────────────────────
export interface WatchlistHit {
  list: string;
  entity: string;
  match: string;
  type: string;
}

export interface Evidence {
  patterns?: string[];
  riskBoost?: number;
  evidenceConfidence?: number;
  amount?: number;
  hour?: number;
  channel?: string;
  location?: string;
  counterparty?: string;
  oldBalance?: number;
  newBalance?: number;
  patternCount?: number;
}

// ── Agent 3 — Network ───────────────────────────────────────────────────────
export interface NetworkNode {
  accountId: string;
  riskScore: number;
  riskLevel: "low" | "medium" | "high" | "critical" | string;
  isPrimary: boolean;
  pagerank: number;
}

export interface NetworkEdge {
  from: string;
  to: string;
  amount: number;
  channel: string;
}

export interface SccCluster {
  clusterId: string;
  nodeCount: number;
  accountIds: string[];
  avgRisk: number;
}

export interface NetworkFindings {
  nodeCount?: number;
  edgeCount?: number;
  nodes?: NetworkNode[];
  edges?: NetworkEdge[];
  sccClusters?: SccCluster[];
  maxPagerank?: number;
  centralNode?: string;
}

export interface SubCase {
  accountId: string;
  riskScore: number;
  riskLevel: string;
  reason: string;
  autoCreated: boolean;
}

// ── Agent 4 — Regulatory ─────────────────────────────────────────────────────
export interface FatfTypology {
  code: string;
  name: string;
  description: string;
  confidence: number;
  severity: number;
  pmla: string;
}

export interface RegulatoryFindings {
  fatfTypologies?: FatfTypology[];
  primaryTypology?: FatfTypology | null;
  pmlaSections?: string[];
  regulatoryConfidence?: number;
  maxSeverity?: number;
  fiuIndReportable?: boolean;
  strRequired?: boolean;
}

// ── Agent 6 — Recommendation ─────────────────────────────────────────────────
export type RecommendedAction =
  | "BLOCK"
  | "MONITOR"
  | "ESCALATE"
  | "FILE_STR"
  | "REQUEST_INFO"
  | "CLOSE";

export interface Recommendation {
  action?: RecommendedAction | string;
  confidence?: number;
  confidencePct?: number;
  reasoning?: string;
  regulatoryBasis?: string;
  timestamp?: string | Date;
}

// ── Planner / agent trace ───────────────────────────────────────────────────
export interface AgentLogEntry {
  agent: string;
  detail: string;
  timestamp: string | Date;
}

export interface InvestigationFlags {
  disagreementFlag?: boolean;
  watchlistHit?: boolean;
  highRiskNetwork?: boolean;
}

export interface ConfidenceScores {
  agent1Anomaly?: number;
  agent2Evidence?: number;
  agent3Network?: number;
  agent4Regulatory?: number;
  agent5Explanation?: number;
  agent6Recommendation?: number;
}

// Full nested InvestigationContext.to_dict(), stored under case.investigation
export interface InvestigationContextData {
  primaryTransactionId?: string;
  anomalyScores?: AnomalyScores;
  evidence?: Evidence;
  watchlistHits?: WatchlistHit[];
  network?: NetworkFindings;
  subCases?: SubCase[];
  regulatory?: RegulatoryFindings;
  shapValues?: ShapFeature[];
  explanation?: string;
  strNarrative?: string;
  recommendation?: Recommendation;
  confidenceScores?: ConfidenceScores;
  agentLog?: AgentLogEntry[];
  flags?: InvestigationFlags;
}

/**
 * The full case document as returned by GET /api/v1/cases/{id},
 * after camelCase normalisation. CaseService also mirrors the key
 * investigation fields at the top level for convenience, so most
 * UI code can read caseData.recommendation directly instead of
 * caseData.investigation.recommendation.
 */
export interface CaseData {
  id?: string;
  accountId?: string;
  accountName?: string;
  status?: string;
  priority?: string;
  riskScore?: number;
  anomalyScore?: number;
  fatfTypology?: string[];
  transactionIds?: string[];
  suspiciousTransactions?: any[];
  totalAmount?: number;

  evidenceSummary?: Evidence;
  networkAnalysis?: NetworkFindings;
  strNarrative?: string;

  investigation?: InvestigationContextData;

  recommendation?: Recommendation;
  explanation?: string;
  shapValues?: ShapFeature[];
  agentLog?: AgentLogEntry[];
  subCases?: SubCase[];
  watchlistHits?: WatchlistHit[];
  regulatory?: RegulatoryFindings;
  confidenceScores?: ConfidenceScores;

  detectedAt?: string | Date;
  createdAt?: string | Date;
  updatedAt?: string | Date;
}
