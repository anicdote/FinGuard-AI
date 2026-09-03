import { Card, CardContent } from "./ui/card";
import { Shield, Zap, Brain, Network, FileCheck, UserCheck } from "lucide-react";

export function SystemBanner() {
  const features = [
    { icon: Shield, title: "6-Agent Investigation", description: "Autonomous detection to recommendation" },
    { icon: Zap, title: "End-to-End Analysis", description: "Automated case investigation pipeline" },
    { icon: Brain, title: "ML Anomaly Detection", description: "XGBoost + Isolation Forest" },
    { icon: Network, title: "Network Investigation", description: "Connected accounts, PageRank & SCC" },
    { icon: FileCheck, title: "Explainable Outputs", description: "SHAP, regulatory mapping & STR" },
    { icon: UserCheck, title: "Human Review", description: "Officer decision with audit trail" },
  ];

  return (
    <Card className="mb-6 overflow-hidden border-slate-200" style={{ borderLeft: "4px solid #1A3A6B" }}>
      <CardContent className="pt-6 pb-5">
        <div className="mb-5 flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#1A3A6B] bg-[#EBF0F8] px-2 py-1 rounded">
                Autonomous investigation platform
              </span>
            </div>
            <h2 className="text-lg font-bold mb-1 text-slate-900">
              Autonomous Multi-Agent Financial Crime Investigation
            </h2>
            <p className="text-sm text-slate-500 max-w-3xl">
              Detect suspicious activity, gather contextual evidence, assess regulatory risk and generate an explainable action recommendation for compliance review.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {features.map((feature, idx) => {
            const Icon = feature.icon;
            return (
              <div key={idx} className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
                <div className="flex justify-center mb-2">
                  <div className="p-1.5 rounded-md bg-[#EBF0F8]">
                    <Icon className="w-4 h-4 text-[#1A3A6B]" />
                  </div>
                </div>
                <p className="text-xs font-semibold text-slate-800">{feature.title}</p>
                <p className="text-[11px] leading-snug text-slate-500 mt-1">{feature.description}</p>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
