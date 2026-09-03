import { useDashboardStats, useCases } from "../hooks/useApi";
import { StatsCard } from "../components/dashboard/StatsCard";
import { CaseQueue } from "../components/dashboard/CaseQueue";
import { AgentPipeline } from "../components/dashboard/AgentPipeline";
import { RealtimeMonitor } from "../components/dashboard/RealtimeMonitor";
import { SystemBanner } from "../components/SystemBanner";
import { AlertTriangle, TrendingUp, Clock, FileText, Activity, Users } from "lucide-react";

export function Dashboard() {
  const { data: stats, loading: statsLoading } = useDashboardStats();
  const { data: cases, loading: casesLoading } = useCases();

  const s = stats ?? {
    criticalCases: 0, highPriorityCases: 0, avgProcessingTime: 0,
    strFilingsPending: 0, totalTransactionsAnalyzed: 0,
    averageRiskScore: 0, suspiciousAccountsIdentified: 0,
  };

  return (
    <div className="container mx-auto px-6 py-7">
      <SystemBanner />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-7">
        <StatsCard title="Critical Cases" value={statsLoading ? "…" : s.criticalCases} subtitle="Require immediate review" icon={AlertTriangle} color="red" />
        <StatsCard title="High Priority" value={statsLoading ? "…" : s.highPriorityCases} subtitle="Prioritised for investigation" icon={TrendingUp} color="orange" />
        <StatsCard title="Avg Processing" value={statsLoading ? "…" : `${s.avgProcessingTime}s`} subtitle="Measured pipeline runtime" icon={Clock} color="green" />
        <StatsCard title="STRs Pending" value={statsLoading ? "…" : s.strFilingsPending} subtitle="Awaiting compliance review" icon={FileText} color="blue" />
      </div>

      <div className="mb-7"><AgentPipeline /></div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-7">
        <div className="lg:col-span-2">
          {casesLoading
            ? <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-400">Loading investigation queue…</div>
            : <CaseQueue cases={cases ?? []} />}
        </div>
        <div className="lg:col-span-1">
          <RealtimeMonitor cases={cases ?? []} transactionsProcessed={s.totalTransactionsAnalyzed ?? 0} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Transactions Analysed", value: statsLoading ? "…" : (s.totalTransactionsAnalyzed ?? 0).toLocaleString("en-IN"), sub: "Current database total", icon: Activity },
          { label: "Average Risk Score", value: statsLoading ? "…" : `${(s.averageRiskScore ?? 0).toFixed(1)}/100`, sub: "Across flagged cases", icon: TrendingUp },
          { label: "Accounts Identified", value: statsLoading ? "…" : (s.suspiciousAccountsIdentified ?? 0).toLocaleString("en-IN"), sub: "Flagged accounts in investigations", icon: Users },
        ].map(({ label, value, sub, icon: Icon }) => (
          <div key={label} className="bg-white rounded-lg border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
              <Icon className="w-4 h-4 text-slate-400" />
            </div>
            <p className="text-3xl font-bold text-slate-900 mb-1">{value}</p>
            <p className="text-xs text-slate-500">{sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
