import { Link } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { AlertTriangle, TrendingUp, Clock, ArrowRight } from "lucide-react";

interface CaseQueueProps {
  cases: any[];
}

export function CaseQueue({ cases }: CaseQueueProps) {
  const priorityConfig: Record<string, { bg: string; color: string; border: string; label: string }> = {
    critical: { bg: "#FDECEA", color: "#C0392B", border: "#F5C6C2", label: "CRITICAL" },
    high:     { bg: "#FEF3E7", color: "#D35400", border: "#FAD7A0", label: "HIGH" },
    medium:   { bg: "#FEFCE8", color: "#B7791F", border: "#FDE68A", label: "MEDIUM" },
    low:      { bg: "#E9F7EF", color: "#1A7A4A", border: "#A9DFBF", label: "LOW" },
  };
  const statusConfig: Record<string, { bg: string; color: string }> = {
    new:           { bg: "#EBF0F8", color: "#1A3A6B" },
    investigating: { bg: "#F3E8FF", color: "#6B21A8" },
    reviewed:      { bg: "#E9F7EF", color: "#1A7A4A" },
    filed:         { bg: "#E9F7EF", color: "#1A7A4A" },
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Prioritised Case Queue</CardTitle>
            <CardDescription>
              {cases.length} case{cases.length !== 1 ? "s" : ""} requiring attention · sorted by risk severity
            </CardDescription>
          </div>
          <span className="text-xs font-medium px-2.5 py-1 rounded border"
                style={{ background: "#E9F7EF", color: "#1A7A4A", borderColor: "#A9DFBF" }}>
            Auto-Prioritised
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {cases.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">
            No cases yet. Run the backend seed script and background worker to generate cases.
          </p>
        ) : (
          <div className="space-y-2.5">
            {cases.slice(0, 8).map((c: any) => {
              const priority = c.priority ?? "medium";
              const status   = c.status   ?? "new";
              const riskScore = c.riskScore ?? c.risk_score ?? 0;
              const accountName = c.accountName ?? c.account_name ?? "Unknown";
              const accountId   = c.accountId   ?? c.account_id   ?? "—";
              const fatfTypes   = c.fatfTypology ?? c.fatf_typology ?? [];
              const suspTxns    = c.suspiciousTransactions ?? c.suspicious_transactions ?? [];
              const caseId      = c.id ?? c._id ?? "";

              const pc = priorityConfig[priority] ?? priorityConfig.medium;
              const sc = statusConfig[status]     ?? statusConfig.new;

              return (
                <div
                  key={caseId}
                  className="flex items-center justify-between p-4 rounded border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-4 flex-1">
                    {/* Priority icon */}
                    <div className="flex-shrink-0">
                      {priority === "critical" && <AlertTriangle className="w-4 h-4" style={{ color: "#C0392B" }} />}
                      {priority === "high"     && <TrendingUp    className="w-4 h-4" style={{ color: "#D35400" }} />}
                      {(priority === "medium" || priority === "low") && <Clock className="w-4 h-4 text-slate-400" />}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-semibold text-slate-900 truncate">{accountName}</p>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded whitespace-nowrap"
                              style={{ background: pc.bg, color: pc.color, border: `1px solid ${pc.border}` }}>
                          {pc.label}
                        </span>
                        <span className="text-xs font-medium px-2 py-0.5 rounded whitespace-nowrap"
                              style={{ background: sc.bg, color: sc.color }}>
                          {status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mb-1">Case {String(caseId).slice(-8)} · {accountId}</p>
                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>Risk: <b className="text-slate-700">{Number(riskScore).toFixed(0)}/100</b></span>
                        <span>·</span>
                        <span>{suspTxns.length} transactions</span>
                        <span>·</span>
                        <span>{fatfTypes.length} typolog{fatfTypes.length === 1 ? "y" : "ies"}</span>
                      </div>
                    </div>

                    {/* Risk ring */}
                    <div className="flex-shrink-0">
                      <div className="relative w-14 h-14">
                        <svg className="w-14 h-14 -rotate-90">
                          <circle cx="28" cy="28" r="24" stroke="#E2E8F0" strokeWidth="5" fill="none" />
                          <circle
                            cx="28" cy="28" r="24"
                            stroke={riskScore >= 80 ? "#C0392B" : riskScore >= 60 ? "#D35400" : "#B7791F"}
                            strokeWidth="5" fill="none"
                            strokeDasharray={`${(Math.min(Number(riskScore), 100) / 100) * 150} 150`}
                            strokeLinecap="round"
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-xs font-bold text-slate-800">{Number(riskScore).toFixed(0)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Investigate button */}
                  <Link to={`/case/${caseId}`} className="ml-4">
                    <button
                      className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded border transition-colors"
                      style={{ background: "#1A3A6B", color: "#fff", border: "1px solid #1A3A6B" }}
                    >
                      Investigate
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </Link>
                </div>
              );
            })}
          </div>
        )}
        {cases.length > 8 && (
          <p className="text-xs text-slate-400 text-center mt-4">Showing 8 of {cases.length} cases</p>
        )}
      </CardContent>
    </Card>
  );
}
