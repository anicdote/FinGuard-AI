import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Activity, AlertTriangle, CheckCircle, Eye, Clock3 } from "lucide-react";

interface RealtimeMonitorProps {
  cases: any[];
  transactionsProcessed: number;
}

export function RealtimeMonitor({ cases, transactionsProcessed }: RealtimeMonitorProps) {
  const safeCases = cases ?? [];
  const critical = safeCases.filter((c) => c.priority === "critical").length;
  const high = safeCases.filter((c) => c.priority === "high").length;

  const recent = safeCases.slice(0, 6).map((c: any, idx: number) => {
    const priority = c.priority ?? "medium";
    const name = c.accountName ?? c.account_name ?? "Unknown account";
    const risk = Number(c.riskScore ?? c.risk_score ?? 0).toFixed(0);
    const id = c.id ?? c._id ?? idx;
    return {
      id,
      type: priority === "critical" ? "alert" : priority === "high" ? "analysis" : "detection",
      message: `${priority === "critical" ? "Critical case" : priority === "high" ? "High-risk case" : "Case detected"}: ${name} · risk ${risk}/100`,
    };
  });

  const config: Record<string, { icon: any; bg: string; color: string }> = {
    detection: { icon: Eye, bg: "#EBF0F8", color: "#1A3A6B" },
    analysis: { icon: Activity, bg: "#F3E8FF", color: "#6B21A8" },
    alert: { icon: AlertTriangle, bg: "#FDECEA", color: "#C0392B" },
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Live Investigation Monitor</CardTitle>
            <CardDescription>Current activity from the investigation queue</CardDescription>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700">
            <span className="w-2 h-2 rounded-full bg-green-500" /> Connected
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2.5 mb-5">
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
            <p className="text-[11px] text-slate-500">Transactions</p>
            <p className="text-lg font-bold text-[#1A3A6B]">{transactionsProcessed.toLocaleString("en-IN")}</p>
          </div>
          <div className="p-3 rounded-lg bg-red-50 border border-red-100">
            <p className="text-[11px] text-red-600">Critical</p>
            <p className="text-lg font-bold text-[#C0392B]">{critical}</p>
          </div>
          <div className="p-3 rounded-lg bg-orange-50 border border-orange-100">
            <p className="text-[11px] text-orange-700">High</p>
            <p className="text-lg font-bold text-[#D35400]">{high}</p>
          </div>
        </div>

        <div className="flex items-center justify-between mb-2.5">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Recent cases</p>
          <span className="text-[11px] text-slate-400">Current dashboard snapshot</span>
        </div>
        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
          {recent.map((event) => {
            const { icon: Icon, bg, color } = config[event.type];
            return (
              <div key={event.id} className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-100 bg-white">
                <div className="p-1.5 rounded-md flex-shrink-0" style={{ background: bg }}>
                  <Icon className="w-3.5 h-3.5" style={{ color }} />
                </div>
                <p className="text-xs text-slate-700 leading-snug pt-1">{event.message}</p>
              </div>
            );
          })}
          {recent.length === 0 && (
            <div className="text-center py-8 text-slate-400">
              <Clock3 className="w-6 h-6 mx-auto mb-2" />
              <p className="text-xs">No recent cases</p>
            </div>
          )}
        </div>
        <div className="mt-4 flex items-center gap-1.5 text-[11px] text-slate-400 border-t border-slate-100 pt-3">
          <CheckCircle className="w-3.5 h-3.5 text-green-600" />
          Queue data is sourced from the backend case API.
        </div>
      </CardContent>
    </Card>
  );
}
