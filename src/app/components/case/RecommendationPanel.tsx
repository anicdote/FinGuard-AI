import { Card, CardContent } from "../ui/card";
import {
  ShieldAlert,
  ShieldCheck,
  Eye,
  FileWarning,
  HelpCircle,
  Ban,
  ArrowUpRight,
  Network,
  UserCheck,
  FileText,
  AlertTriangle,
  CheckCircle2,
  type LucideIcon,
} from "lucide-react";
import type {
  Recommendation,
  AnomalyScores,
} from "../../types/investigation";

interface RecommendationPanelProps {
  recommendation:
    | Recommendation
    | null
    | undefined;
  anomalyScores:
    | AnomalyScores
    | null
    | undefined;
  riskScore: number;
  disagreementFlag?: boolean;
}

const ACTION_CONFIG: Record<
  string,
  {
    label: string;
    bg: string;
    color: string;
    border: string;
    icon: LucideIcon;
  }
> = {
  BLOCK: {
    label: "BLOCK",
    bg: "#FEF2F2",
    color: "#B42318",
    border: "#FECACA",
    icon: Ban,
  },

  FILE_STR: {
    label: "FILE STR",
    bg: "#FEF2F2",
    color: "#B42318",
    border: "#FECACA",
    icon: FileWarning,
  },

  ESCALATE: {
    label: "ESCALATE",
    bg: "#FFF7ED",
    color: "#C2410C",
    border: "#FED7AA",
    icon: ShieldAlert,
  },

  MONITOR: {
    label: "MONITOR",
    bg: "#FFFBEB",
    color: "#A16207",
    border: "#FDE68A",
    icon: Eye,
  },

  REQUEST_INFO: {
    label: "REQUEST INFO",
    bg: "#EFF6FF",
    color: "#1D4ED8",
    border: "#BFDBFE",
    icon: HelpCircle,
  },

  CLOSE: {
    label: "CLOSE",
    bg: "#F0FDF4",
    color: "#15803D",
    border: "#BBF7D0",
    icon: ShieldCheck,
  },
};

const RISK_LEVEL_CONFIG: Record<
  string,
  {
    color: string;
    bg: string;
    label: string;
  }
> = {
  critical: {
    color: "#B42318",
    bg: "#FEF2F2",
    label: "Critical",
  },

  high: {
    color: "#C2410C",
    bg: "#FFF7ED",
    label: "High",
  },

  medium: {
    color: "#A16207",
    bg: "#FFFBEB",
    label: "Medium",
  },

  low: {
    color: "#15803D",
    bg: "#F0FDF4",
    label: "Low",
  },
};

function formatLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(
      /\b\w/g,
      (letter) => letter.toUpperCase()
    );
}


type ParsedReasoning = {
  modelScore?: string;
  typology?: string;
  patterns: string[];
  network?: string;
  watchlist: string[];
  topDriver?: string;
  disagreement: boolean;
};

function parseRecommendationReasoning(text: string): ParsedReasoning {
  const parsed: ParsedReasoning = {
    patterns: [],
    watchlist: [],
    disagreement: false,
  };

  const parts = text.replace(/^\s*[A-Z_]+:\s*/, "").split(/\s*\|\s*/);

  for (const part of parts) {
    const item = part.trim();
    if (!item) continue;

    if (/^XGBoost=/i.test(item)) {
      parsed.modelScore = item.replace(/^XGBoost=/i, "XGBoost probability ").trim();
    } else if (/^FATF\s+/i.test(item)) {
      parsed.typology = item.replace(/^FATF\s+/i, "").trim();
    } else if (/^Patterns:\s*/i.test(item)) {
      parsed.patterns = item
        .replace(/^Patterns:\s*/i, "")
        .split(/,\s*/)
        .map((v) => v.trim())
        .filter(Boolean);
    } else if (/^\d+-account ring/i.test(item)) {
      parsed.network = item;
    } else if (/^Watchlist:\s*/i.test(item)) {
      parsed.watchlist = item
        .replace(/^Watchlist:\s*/i, "")
        .split(/,\s*/)
        .map((v) => v.trim())
        .filter(Boolean);
    } else if (/^Top driver:\s*/i.test(item)) {
      parsed.topDriver = item.replace(/^Top driver:\s*/i, "").trim();
    } else if (/Model disagreement/i.test(item)) {
      parsed.disagreement = true;
    }
  }

  return parsed;
}

function formatPercent(value: number): string {
  return `${(
    value <= 1
      ? value * 100
      : value
  ).toFixed(0)}%`;
}

export function RecommendationPanel({
  recommendation,
  anomalyScores,
  riskScore,
  disagreementFlag,
}: RecommendationPanelProps) {
  const action =
    recommendation?.decision ??
    recommendation?.action ??
    recommendation?.caseAction;

  /*
   * IMPORTANT:
   * Do not use:
   *
   * const cfg = (action && ACTION_CONFIG[action]) ?? null;
   *
   * because TypeScript can infer "" as a possible value.
   */
  const cfg = action
    ? ACTION_CONFIG[action] ?? null
    : null;

  const Icon = cfg?.icon ?? Eye;

  const confidencePct =
    typeof recommendation?.confidencePct ===
    "number"
      ? recommendation.confidencePct
      : typeof recommendation?.confidence ===
          "number"
        ? recommendation.confidence * 100
        : undefined;

  const riskLevel =
    anomalyScores?.riskLevel ??
    "";

  const probability =
    anomalyScores?.probability;

  const riskCfg =
    RISK_LEVEL_CONFIG[riskLevel] ??
    {
      color: "#1A3A6B",
      bg: "#EFF6FF",
      label: "Unknown",
    };

  const humanAction =
    recommendation?.caseAction ===
    "route_to_str_review_not_filed"
      ? "Route to STR Review"
      : recommendation?.caseAction;

  const structuredFields = [
    {
      label: "Decision",
      value: recommendation?.decision,
      icon: ArrowUpRight,
    },
    {
      label: "Priority",
      value: recommendation?.priority,
      icon: AlertTriangle,
    },
    {
      label: "Operational Risk",
      value:
        typeof recommendation?.operationalRiskScore ===
        "number"
          ? formatPercent(
              recommendation.operationalRiskScore
            )
          : undefined,
      icon: ShieldAlert,
    },
    {
      label: "Network Risk",
      value:
        typeof recommendation?.networkRiskScore ===
        "number"
          ? formatPercent(
              recommendation.networkRiskScore
            )
          : undefined,
      icon: Network,
    },
    {
      label: "Human Review",
      value:
        typeof recommendation?.requiresHumanReview ===
        "boolean"
          ? recommendation.requiresHumanReview
            ? "Required"
            : "Not required"
          : undefined,
      icon: UserCheck,
    },
    {
      label: "STR Status",
      value:
        recommendation?.strStatus,
      icon: FileText,
    },
  ].filter(
    (field) =>
      field.value !==
        undefined &&
      field.value !== null &&
      field.value !== ""
  );

  const compactEntries = (
    value:
      | Record<string, any>
      | undefined
  ) =>
    Object.entries(
      value ?? {}
    )
      .filter(
        ([, entry]) =>
          entry !== undefined &&
          entry !== null &&
          entry !== ""
      )
      .slice(0, 4);

  const decisionFactors =
    compactEntries(
      recommendation?.decisionFactors
    );

  const supportingEvidence =
    compactEntries(
      recommendation?.supportingEvidence
    );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">

      {/* ------------------------------------------------------------------ */}
      {/* OVERALL RISK                                                       */}
      {/* ------------------------------------------------------------------ */}

      <Card className="overflow-hidden border border-slate-200 shadow-sm">
        <CardContent className="p-0">

          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center justify-between">

              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Risk Assessment
                </p>

                <p className="text-sm text-slate-400 mt-0.5">
                  Agent 1 · Ensemble analysis
                </p>
              </div>

              {riskLevel && (
                <span
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide"
                  style={{
                    color:
                      riskCfg.color,
                    background:
                      riskCfg.bg,
                  }}
                >
                  {riskCfg.label} Risk
                </span>
              )}
            </div>
          </div>

          {/* Main score */}
          <div className="px-5 py-5">

            <div className="flex items-end justify-between">

              <div>
                <p className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                  Overall Risk Score
                </p>

                <div className="flex items-baseline gap-1.5 mt-1">

                  <span
                    className="text-5xl font-bold tracking-tight"
                    style={{
                      color:
                        riskCfg.color,
                    }}
                  >
                    {Number(
                      riskScore
                    ).toFixed(0)}
                  </span>

                  <span className="text-sm font-medium text-slate-400">
                    /100
                  </span>

                </div>
              </div>

              {typeof probability ===
                "number" && (
                <div className="text-right">

                  <p className="text-[11px] text-slate-400">
                    Anomaly probability
                  </p>

                  <p className="text-lg font-semibold text-slate-700">
                    {(
                      probability *
                      100
                    ).toFixed(1)}
                    %
                  </p>

                </div>
              )}

            </div>

            {/* Score bar */}
            <div className="mt-5">

              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">

                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(
                        0,
                        Number(
                          riskScore
                        )
                      )
                    )}%`,
                    background:
                      riskCfg.color,
                  }}
                />

              </div>

              <div className="flex justify-between mt-1.5 text-[10px] text-slate-400">
                <span>Low</span>
                <span>Medium</span>
                <span>High</span>
                <span>Critical</span>
              </div>

            </div>

            {/* Model disagreement */}
            {disagreementFlag && (
              <div className="mt-5 flex items-start gap-2.5 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2.5">

                <ShieldAlert
                  className="w-4 h-4 shrink-0 mt-0.5"
                  style={{
                    color: "#C2410C",
                  }}
                />

                <div>

                  <p className="text-xs font-semibold text-orange-800">
                    Model disagreement detected
                  </p>

                  <p className="text-[11px] text-orange-700 mt-0.5 leading-relaxed">
                    XGBoost and Isolation
                    Forest produced different
                    signals. This may indicate
                    a novel fraud pattern.
                  </p>

                </div>
              </div>
            )}

          </div>

        </CardContent>
      </Card>


      {/* ------------------------------------------------------------------ */}
      {/* AGENT 6 RECOMMENDATION                                             */}
      {/* ------------------------------------------------------------------ */}

      <Card
        className="overflow-hidden border shadow-sm"
        style={{
          borderColor:
            cfg?.border ??
            "#E2E8F0",
        }}
      >

        <CardContent className="p-0">

          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-100">

            <div className="flex items-center justify-between">

              <div>

                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  AI Recommendation
                </p>

                <p className="text-sm text-slate-400 mt-0.5">
                  Agent 6 · Decision synthesis
                </p>

              </div>

              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Final AI output
              </span>

            </div>

          </div>


          {!action ? (

            <div className="px-5 py-8 text-center">

              <p className="text-sm text-slate-400">
                No recommendation generated
                for this case.
              </p>

            </div>

          ) : (

            <div className="px-5 py-5">

              {/* Decision hero */}
              <div className="flex items-center gap-4">

                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{
                    background:
                      cfg?.bg,
                  }}
                >

                  <Icon
                    className="w-6 h-6"
                    style={{
                      color:
                        cfg?.color,
                    }}
                  />

                </div>


                <div className="min-w-0">

                  <div className="flex items-center gap-2 flex-wrap">

                    <p
                      className="text-2xl font-bold tracking-tight"
                      style={{
                        color:
                          cfg?.color,
                      }}
                    >
                      {cfg?.label ??
                        action}
                    </p>


                    {typeof confidencePct ===
                      "number" && (
                      <span
                        className="px-2 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{
                          color:
                            cfg?.color,
                          background:
                            cfg?.bg,
                        }}
                      >
                        {confidencePct.toFixed(
                          0
                        )}
                        % confidence
                      </span>
                    )}

                  </div>


                  {humanAction &&
                    humanAction !==
                      action && (
                      <p className="text-xs text-slate-500 mt-1">

                        Case action:{" "}

                        <span className="font-medium text-slate-700">

                          {formatLabel(
                            humanAction
                          )}

                        </span>

                      </p>
                    )}

                </div>

              </div>


              {/* Structured reasoning */}
              {recommendation?.reasoning && (() => {
                const parsed = parseRecommendationReasoning(recommendation.reasoning);

                return (
                  <div className="mt-5">
                    <div className="flex items-center gap-2 mb-2.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-slate-500" />
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        Why this decision
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {parsed.modelScore && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-3">
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                            Model signal
                          </p>
                          <p className="text-xs font-semibold text-slate-700 mt-1">
                            {parsed.modelScore}
                          </p>
                        </div>
                      )}

                      {parsed.typology && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-3">
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                            FATF typology
                          </p>
                          <p className="text-xs font-semibold text-slate-700 mt-1">
                            {parsed.typology}
                          </p>
                        </div>
                      )}

                      {parsed.network && (
                        <div className="rounded-lg border border-slate-200 bg-white px-3.5 py-3">
                          <div className="flex items-center gap-2">
                            <Network className="w-3.5 h-3.5 text-slate-500" />
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                              Network
                            </p>
                          </div>
                          <p className="text-xs font-medium text-slate-700 mt-1">
                            {parsed.network}
                          </p>
                        </div>
                      )}

                      {parsed.watchlist.length > 0 && (
                        <div className="rounded-lg border border-red-100 bg-red-50 px-3.5 py-3">
                          <div className="flex items-center gap-2">
                            <Eye className="w-3.5 h-3.5 text-red-600" />
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                              Watchlist
                            </p>
                          </div>
                          <div className="mt-1">
                            {parsed.watchlist.map((entity) => (
                              <p key={entity} className="text-xs font-semibold text-red-800">
                                {entity}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {parsed.patterns.length > 0 && (
                      <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3.5 py-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                          Detected patterns
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {parsed.patterns.map((pattern) => (
                            <span
                              key={pattern}
                              className="px-2 py-1 rounded-md bg-slate-50 border border-slate-200 text-[10px] font-medium text-slate-600"
                            >
                              {pattern.replace(/\w/g, (c) => c.toUpperCase())}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {parsed.topDriver && (
                      <div className="mt-3 flex items-center justify-between gap-3 rounded-lg bg-slate-50 border border-slate-100 px-3.5 py-2.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                          Top driver
                        </span>
                        <span className="text-xs font-semibold text-slate-700 text-right">
                          {parsed.topDriver}
                        </span>
                      </div>
                    )}

                    {parsed.disagreement && (
                      <div className="mt-3 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-orange-800">
                          Model disagreement detected
                        </p>
                        <p className="text-[10px] text-orange-700 mt-0.5">
                          Multiple model signals require additional investigator attention.
                        </p>
                      </div>
                    )}
                  </div>
                );
              })()}


              {/* Regulatory basis */}
              {recommendation?.regulatoryBasis && (
                <div className="mt-4 rounded-lg bg-slate-50 border border-slate-100 px-3.5 py-3">

                  <div className="flex items-start gap-2">

                    <FileText className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />

                    <div>

                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Regulatory basis
                      </p>

                      <p className="text-[11px] text-slate-600 leading-relaxed mt-0.5">
                        {
                          recommendation.regulatoryBasis
                        }
                      </p>

                    </div>

                  </div>

                </div>
              )}


              {/* Decision details */}
              {structuredFields.length >
                0 && (
                <div className="mt-5 pt-4 border-t border-slate-100">

                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    Decision details
                  </p>


                  <div className="grid grid-cols-2 gap-2">

                    {structuredFields.map(
                      ({
                        label,
                        value,
                        icon: FieldIcon,
                      }) => (

                        <div
                          key={label}
                          className="rounded-lg bg-slate-50 px-3 py-2.5"
                        >

                          <div className="flex items-center gap-1.5">

                            <FieldIcon className="w-3 h-3 text-slate-400" />

                            <p className="text-[10px] font-medium text-slate-400">
                              {label}
                            </p>

                          </div>


                          <p className="text-xs font-semibold text-slate-700 mt-1 truncate">

                            {typeof value ===
                            "string"
                              ? formatLabel(
                                  value
                                )
                              : String(
                                  value
                                )}

                          </p>

                        </div>

                      )
                    )}

                  </div>

                </div>
              )}


              {/* Supporting evidence / factors */}
              {(decisionFactors.length >
                0 ||
                supportingEvidence.length >
                  0) && (

                <div className="mt-4 space-y-2">

                  {/* Decision factors */}
                  {decisionFactors.length >
                    0 && (

                    <div>

                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                        Decision factors
                      </p>


                      <div className="flex flex-wrap gap-1.5">

                        {decisionFactors.map(
                          ([
                            key,
                            value,
                          ]) => (

                            <span
                              key={key}
                              className="px-2 py-1 rounded-md bg-slate-100 text-[10px] text-slate-600"
                            >

                              <span className="font-semibold">

                                {formatLabel(
                                  key
                                )}

                                :

                              </span>{" "}

                              {typeof value ===
                              "object"
                                ? JSON.stringify(
                                    value
                                  )
                                : String(
                                    value
                                  )}

                            </span>

                          )
                        )}

                      </div>

                    </div>
                  )}


                  {/* Supporting evidence */}
                  {supportingEvidence.length >
                    0 && (

                    <div>

                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                        Supporting evidence
                      </p>


                      <div className="flex flex-wrap gap-1.5">

                        {supportingEvidence.map(
                          ([
                            key,
                            value,
                          ]) => (

                            <span
                              key={key}
                              className="px-2 py-1 rounded-md bg-slate-100 text-[10px] text-slate-600"
                            >

                              <span className="font-semibold">

                                {formatLabel(
                                  key
                                )}

                                :

                              </span>{" "}

                              {typeof value ===
                              "object"
                                ? JSON.stringify(
                                    value
                                  )
                                : String(
                                    value
                                  )}

                            </span>

                          )
                        )}

                      </div>

                    </div>
                  )}

                </div>
              )}


              {/* Missing information */}
              {recommendation?.missingInformation &&
                recommendation
                  .missingInformation
                  .length >
                  0 && (

                  <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">

                    <p className="text-[10px] font-bold uppercase tracking-wider text-amber-700">
                      Missing information
                    </p>


                    <p className="text-[11px] text-amber-800 mt-1 leading-relaxed">

                      {[
                        ...new Map(
                          recommendation.missingInformation.map(
                            (item) => [
                              item
                                .toLowerCase()
                                .replace(
                                  /not available/g,
                                  "unavailable"
                                )
                                .replace(
                                  /customer identification information.*$/i,
                                  "customer identification information"
                                ),
                              item,
                            ]
                          )
                        ).values(),
                      ].join(
                        " · "
                      )}

                    </p>

                  </div>
                )}


              {/* Human review indicator */}
              {recommendation?.requiresHumanReview && (

                <div className="mt-4 flex items-center gap-2 text-[11px] font-medium text-slate-600">

                  <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />

                  Human compliance review is
                  required before final action.

                </div>

              )}

            </div>

          )}

        </CardContent>

      </Card>

    </div>
  );
}