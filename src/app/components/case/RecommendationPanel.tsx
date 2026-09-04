import { Card, CardContent } from "../ui/card";
import { ShieldAlert, ShieldCheck, Eye, FileWarning, HelpCircle, Ban, type LucideIcon } from "lucide-react";
import type { Recommendation, AnomalyScores } from "../../types/investigation";

interface RecommendationPanelProps {
  recommendation: Recommendation | null | undefined;
  anomalyScores: AnomalyScores | null | undefined;
  riskScore: number;
  disagreementFlag?: boolean;
}

const ACTION_CONFIG: Record<
  string,
  { label: string; bg: string; color: string; border: string; icon: LucideIcon }
> = {
  BLOCK:        { label: "BLOCK",        bg: "#FDECEA", color: "#C0392B", border: "#F5C6C2", icon: Ban },
  FILE_STR:     { label: "FILE STR",     bg: "#FDECEA", color: "#C0392B", border: "#F5C6C2", icon: FileWarning },
  ESCALATE:     { label: "ESCALATE",     bg: "#FEF3E7", color: "#D35400", border: "#FAD7A0", icon: ShieldAlert },
  MONITOR:      { label: "MONITOR",      bg: "#FEFCE8", color: "#B7791F", border: "#FDE68A", icon: Eye },
  REQUEST_INFO: { label: "REQUEST INFO", bg: "#EBF0F8", color: "#1A3A6B", border: "#C6D3E8", icon: HelpCircle },
  CLOSE:        { label: "CLOSE",        bg: "#E9F7EF", color: "#1A7A4A", border: "#A9DFBF", icon: ShieldCheck },
};

const RISK_LEVEL_CONFIG: Record<string, { color: string }> = {
  critical: { color: "#C0392B" },
  high:     { color: "#D35400" },
  medium:   { color: "#B7791F" },
  low:      { color: "#1A7A4A" },
};

export function RecommendationPanel({
  recommendation,
  anomalyScores,
  riskScore,
  disagreementFlag,
}: RecommendationPanelProps) {
  const action        = recommendation?.decision ?? recommendation?.action ?? recommendation?.caseAction;
  const cfg            = (action && ACTION_CONFIG[action]) ?? null;
  const Icon           = cfg?.icon ?? Eye;
  const confidencePct  = recommendation?.confidencePct ?? (recommendation?.confidence ? recommendation.confidence * 100 : undefined);
  const riskLevel      = anomalyScores?.riskLevel ?? "";
  const probability    = anomalyScores?.probability;
  const riskColor      = RISK_LEVEL_CONFIG[riskLevel]?.color ?? "#1A3A6B";
  const formatLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const formatPercent = (value: number) => `${(value <= 1 ? value * 100 : value).toFixed(0)}%`;
  const humanAction = recommendation?.caseAction === "route_to_str_review_not_filed"
    ? "Route to STR Review — Not Filed"
    : recommendation?.caseAction;
  const structuredFields = [
    ["Decision", recommendation?.decision],
    ["Decision Category", recommendation?.decisionCategory],
    ["Priority", recommendation?.priority],
    ["Operational Risk Score", typeof recommendation?.operationalRiskScore === "number" ? formatPercent(recommendation.operationalRiskScore) : undefined],
    ["Network Risk Score", typeof recommendation?.networkRiskScore === "number" ? formatPercent(recommendation.networkRiskScore) : undefined],
    ["Human Review Required", typeof recommendation?.requiresHumanReview === "boolean" ? (recommendation.requiresHumanReview ? "Yes" : "No") : undefined],
    ["Case Action", humanAction],
    ["STR Review Status", recommendation?.strStatus],
    ["STR Filing Status", recommendation?.strFilingStatus],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "") as [string, string][];
  const compactEntries = (value: Record<string, any> | undefined) =>
    Object.entries(value ?? {}).filter(([, entry]) => entry !== undefined && entry !== null && entry !== "").slice(0, 4);
  const decisionFactors = compactEntries(recommendation?.decisionFactors);
  const supportingEvidence = compactEntries(recommendation?.supportingEvidence);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
      {/* Overall Risk */}
      <Card className="border-2" style={{ borderColor: riskColor + "40" }}>
        <CardContent className="pt-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Overall Risk</p>
          <div className="flex items-end gap-3">
            <p className="text-4xl font-bold" style={{ color: riskColor }}>
              {Number(riskScore).toFixed(0)}
              <span className="text-lg text-slate-400">/100</span>
            </p>
            {riskLevel && (
              <span
                className="text-xs font-bold px-2.5 py-1 rounded mb-1.5 uppercase"
                style={{ background: riskColor + "1A", color: riskColor }}
              >
                {riskLevel}
              </span>
            )}
          </div>
          {typeof probability === "number" && (
            <p className="text-xs text-slate-500 mt-2">
              Anomaly probability (Agent 1 ensemble): {(probability * 100).toFixed(1)}%
            </p>
          )}
          {disagreementFlag && (
            <div className="flex items-center gap-1.5 mt-3 text-xs font-medium" style={{ color: "#D35400" }}>
              <ShieldAlert className="w-3.5 h-3.5" />
              XGBoost and Isolation Forest disagree — possible novel fraud pattern
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Recommendation */}
      <Card className="border-2" style={{ borderColor: cfg ? cfg.border : "#e2e8f0" }}>
        <CardContent className="pt-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">AI Recommendation (Agent 6)</p>
          {!action ? (
            <p className="text-sm text-slate-400">No recommendation generated for this case.</p>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg" style={{ background: cfg?.bg }}>
                  <Icon className="w-6 h-6" style={{ color: cfg?.color }} />
                </div>
                <div>
                  <p className="text-2xl font-bold" style={{ color: cfg?.color }}>
                    {cfg?.label ?? action}
                  </p>
                  {typeof confidencePct === "number" && (
                    <p className="text-xs text-slate-500">{confidencePct.toFixed(0)}% confidence</p>
                  )}
                </div>
              </div>
              {recommendation?.reasoning && (
                <p className="text-xs text-slate-600 mt-3 leading-relaxed">{recommendation.reasoning}</p>
              )}
              {recommendation?.regulatoryBasis && (
                <p className="text-xs text-slate-500 mt-2 border-t border-slate-100 pt-2">
                  <span className="font-semibold">Regulatory basis:</span> {recommendation.regulatoryBasis}
                </p>
              )}
              {structuredFields.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Agent 6 Decision Details</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
                    {structuredFields.map(([label, value]) => (
                      <p key={label} className="text-xs text-slate-600">
                        <span className="font-semibold text-slate-700">{label}:</span> {formatLabel(value)}
                      </p>
                    ))}
                  </div>
                </div>
              )}
              {(decisionFactors.length > 0 || supportingEvidence.length > 0) && (
                <div className="mt-3 grid grid-cols-1 gap-2 text-xs">
                  {decisionFactors.length > 0 && (
                    <div className="rounded bg-slate-50 p-2.5 text-slate-600">
                      <span className="font-semibold text-slate-700">Decision factors:</span>{" "}
                      {decisionFactors.map(([key, value]) => `${formatLabel(key)}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}
                    </div>
                  )}
                  {supportingEvidence.length > 0 && (
                    <div className="rounded bg-slate-50 p-2.5 text-slate-600">
                      <span className="font-semibold text-slate-700">Supporting evidence:</span>{" "}
                      {supportingEvidence.map(([key, value]) => `${formatLabel(key)}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}
                    </div>
                  )}
                </div>
              )}
              {recommendation?.missingInformation && recommendation.missingInformation.length > 0 && (
                <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800">
                  <span className="font-semibold">Missing information:</span> {[...new Map(recommendation.missingInformation.map((item) => [item.toLowerCase().replace(/not available/g, "unavailable").replace(/customer identification information.*$/i, "customer identification information"), item])).values()].join(" · ")}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
