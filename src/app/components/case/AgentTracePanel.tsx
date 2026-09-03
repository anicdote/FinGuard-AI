import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Bot, ArrowDown, SkipForward, CheckCircle2, AlertCircle, Network, Search, ShieldCheck, FileText, Sparkles, Brain } from "lucide-react";
import type { AgentLogEntry, ConfidenceScores } from "../../types/investigation";

interface AgentTracePanelProps { agentLog: AgentLogEntry[] | null | undefined; confidenceScores?: ConfidenceScores | null; }

function safeDate(val: any): Date | null { if (!val) return null; const d = val instanceof Date ? val : new Date(val); return isNaN(d.getTime()) ? null : d; }
function entryKind(entry: AgentLogEntry): "planner" | "skipped" | "error" | "agent" { if (entry.agent.startsWith("Planner→")) return "planner"; if (/^SKIPPED/i.test(entry.detail)) return "skipped"; if (/^ERROR/i.test(entry.detail)) return "error"; return "agent"; }

const AGENT_META: Record<string, { label: string; icon: any }> = {
  Agent1: { label: "Anomaly Detection", icon: Brain }, Agent2: { label: "Evidence Gathering", icon: Search },
  Agent3: { label: "Network Investigation", icon: Network }, Agent4: { label: "Regulatory Assessment", icon: ShieldCheck },
  Agent5: { label: "Explanation Generator", icon: FileText }, Agent6: { label: "Action Recommendation", icon: Sparkles },
};
const CONFIDENCE_LABELS: Record<string, string> = { agent1Anomaly:"Anomaly Detection", agent2Evidence:"Evidence Gathering", agent3Network:"Network Investigation", agent4Regulatory:"Regulatory Assessment", agent5Explanation:"Explanation Generator", agent6Recommendation:"Action Recommendation" };

function formatDetail(entry: AgentLogEntry): string {
  const d = entry.detail ?? "";
  if (/^Invoking\. Reason:/i.test(d)) return d.replace(/^Invoking\. Reason:\s*/i, "Why this step ran: ");
  let m = d.match(/XGB=([\d.]+)\s+IF=([\d.]+)\s+prob=([\d.]+)\s+disagreement=(\w+)/i);
  if (m) return `XGBoost ${(Number(m[1]) * 100).toFixed(1)}% · Isolation Forest ${(Number(m[2]) * 100).toFixed(1)}% · Combined anomaly ${(Number(m[3]) * 100).toFixed(1)}%${m[4] === "True" ? " · model disagreement flagged" : ""}`;
  m = d.match(/patterns=\[(.*?)\]\s+watchlist=([\d]+)/i);
  if (m) { const patterns = m[1].replace(/['"]/g, "").split(",").map(x => x.trim().replaceAll("_", " ")).filter(Boolean); return `${patterns.length} behavioural patterns detected${Number(m[2]) ? ` · ${m[2]} watchlist hit${Number(m[2]) > 1 ? "s" : ""}` : " · no watchlist hits"}`; }
  m = d.match(/nodes=(\d+)\s+sub_cases=(\d+)/i); if (m) return `${m[1]} connected entities analysed · ${m[2]} sub-case${Number(m[2]) === 1 ? "" : "s"} created`;
  m = d.match(/typologies=\[(.*?)\].*?pmla=\[(.*?)\]/i); if (m) { const types = m[1].replace(/['"]/g, "").split(",").map(x => x.trim()).filter(Boolean); return `${types.length} regulatory typolog${types.length === 1 ? "y" : "ies"} mapped · PMLA considerations identified`; }
  m = d.match(/STR narrative generated \((\d+) chars\)/i); if (m) return `Audit-ready STR narrative generated · ${m[1]} characters`;
  m = d.match(/action=([A-Z_]+)\s+confidence=([\d.]+)/i); if (m) return `Recommended action: ${m[1].replaceAll("_", " ")} · confidence ${(Number(m[2]) * 100).toFixed(0)}%`;
  return d.replaceAll("_", " ").replace(/\b(Planner→)/g, "");
}

export function AgentTracePanel({ agentLog, confidenceScores }: AgentTracePanelProps) {
  const entries = agentLog ?? [];
  const confEntries = Object.entries(confidenceScores ?? {}).filter(([, v]) => typeof v === "number");
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Investigation Reasoning Trace</CardTitle>
          <CardDescription>A human-readable record of what the Adaptive Planner ran and why.</CardDescription>
        </CardHeader>
        <CardContent>
          {entries.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center">No investigation trace recorded for this case.</p> : (
            <div className="space-y-0">
              {entries.map((entry, idx) => {
                const kind = entryKind(entry); const ts = safeDate(entry.timestamp); const last = idx === entries.length - 1;
                const agentKey = Object.keys(AGENT_META).find(k => entry.agent.startsWith(k));
                const meta = agentKey ? AGENT_META[agentKey] : { label: entry.agent.replace("Planner→", "Planner → ").replaceAll("_", " "), icon: kind === "planner" ? ArrowDown : Bot };
                const Icon = kind === "error" ? AlertCircle : kind === "skipped" ? SkipForward : meta.icon;
                const color = kind === "error" ? "#C0392B" : kind === "skipped" ? "#B7791F" : kind === "planner" ? "#64748B" : "#1A3A6B";
                const bg = kind === "error" ? "#FDECEA" : kind === "skipped" ? "#FEFCE8" : kind === "planner" ? "#F1F5F9" : "#EBF0F8";
                return <div key={idx} className="flex gap-3">
                  <div className="flex flex-col items-center"><div className="p-1.5 rounded-full" style={{background:bg}}><Icon className="w-3.5 h-3.5" style={{color}} /></div>{!last && <div className="w-px flex-1 bg-slate-200 my-0.5" style={{minHeight:18}} />}</div>
                  <div className="pb-4 flex-1">
                    <div className="flex items-center gap-2 flex-wrap"><p className="text-sm font-semibold text-slate-800">{meta.label}</p>{ts && <span className="text-[10px] text-slate-400">{ts.toLocaleTimeString("en-IN", {hour12:false})}</span>}</div>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">{formatDetail(entry)}</p>
                  </div>
                </div>;
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm">Agent Confidence</CardTitle><CardDescription>Confidence reported by each completed investigation stage.</CardDescription></CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {confEntries.length === 0 ? <p className="text-sm text-slate-400">No confidence scores available.</p> : confEntries.map(([key,value]) => {
            const pct = Math.max(0, Math.min(100, Number(value) * 100));
            return <div key={key} className="rounded-lg border border-slate-200 p-3"><div className="flex items-center justify-between mb-2"><span className="text-xs font-medium text-slate-600">{CONFIDENCE_LABELS[key] ?? key}</span><span className="text-xs font-bold text-slate-800">{pct.toFixed(0)}%</span></div><div className="w-full bg-slate-100 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-[#1A3A6B]" style={{width:`${pct}%`}} /></div></div>;
          })}
        </CardContent>
      </Card>
    </div>
  );
}
