import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Activity, ArrowRight, CheckCircle2, Brain, Search, Network, ShieldCheck, FileText, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

const agents = [
  { name: "Anomaly Detection", description: "ML anomaly scoring", icon: Brain },
  { name: "Evidence Gathering", description: "Patterns & watchlists", icon: Search },
  { name: "Network Investigation", description: "Accounts & relationships", icon: Network },
  { name: "Regulatory Assessment", description: "FATF & PMLA mapping", icon: ShieldCheck },
  { name: "Explanation", description: "SHAP & audit-ready narrative", icon: FileText },
  { name: "Recommendation", description: "Action + confidence", icon: Sparkles },
];

export function AgentPipeline() {
  const [activeAgent, setActiveAgent] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setActiveAgent((prev) => (prev + 1) % agents.length), 2200);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle className="text-base">Autonomous Investigation Pipeline</CardTitle>
            <CardDescription>Six specialised agents coordinated by the Adaptive Planner</CardDescription>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border border-green-200 bg-green-50 text-green-700">
            <Activity className="w-3 h-3 animate-pulse" /> Operational
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5">
          {agents.map((agent, idx) => {
            const Icon = agent.icon;
            const active = idx === activeAgent;
            return (
              <div key={agent.name} className={`relative rounded-lg border p-3 transition-all ${active ? "border-[#1A3A6B] bg-[#F3F6FB] shadow-sm" : "border-slate-200 bg-white"}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Agent {idx + 1}</span>
                  {idx < activeAgent ? <CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> : <Icon className={`w-3.5 h-3.5 ${active ? "text-[#1A3A6B]" : "text-slate-400"}`} />}
                </div>
                <p className="text-xs font-semibold text-slate-800 leading-tight">{agent.name}</p>
                <p className="text-[11px] text-slate-500 mt-1 leading-snug">{agent.description}</p>
                {active && <div className="absolute left-3 right-3 bottom-0 h-0.5 rounded-full bg-[#1A3A6B]" />}
              </div>
            );
          })}
        </div>
        <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-slate-700">Current stage:</span>
          <span>{agents[activeAgent].name}</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-300" />
          <span>Planner decides the next relevant investigation step</span>
        </div>
      </CardContent>
    </Card>
  );
}
