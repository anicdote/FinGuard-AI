import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { ShapFeature } from "../../types/investigation";

interface ShapPanelProps {
  shapValues: ShapFeature[] | null | undefined;
}

function labelize(feature: string): string {
  return feature.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ShapPanel({ shapValues }: ShapPanelProps) {
  const values = shapValues ?? [];
  const maxAbs = Math.max(1e-6, ...values.map((v) => Math.abs(v.value)));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Why Was This Flagged? (SHAP Explanation)</CardTitle>
        <CardDescription>
          Top feature contributions from Agent 1's XGBoost model — how far each feature pushed the
          fraud probability up (↑) or down (↓)
        </CardDescription>
      </CardHeader>
      <CardContent>
        {values.length === 0 ? (
          <p className="text-sm text-slate-400 py-4 text-center">
            No SHAP values available for this case — the ML models may not have been loaded when it
            was investigated (rule-based fallback scoring was used instead).
          </p>
        ) : (
          <div className="space-y-3">
            {values.map((v, idx) => {
              const isPositive = v.value >= 0;
              const widthPct   = (Math.abs(v.value) / maxAbs) * 100;
              return (
                <div key={idx} className="flex items-center gap-3">
                  <div className="w-40 flex-shrink-0 text-sm text-slate-700 font-medium truncate">
                    {labelize(v.feature)}
                  </div>
                  <div className="flex-1 flex items-center h-6 relative">
                    <div className="w-1/2 flex justify-end pr-0.5 h-full">
                      {!isPositive && (
                        <div
                          className="h-4 self-center rounded-l"
                          style={{ width: `${widthPct / 2}%`, background: "#1A7A4A" }}
                        />
                      )}
                    </div>
                    <div className="w-px h-full bg-slate-300" />
                    <div className="w-1/2 flex justify-start pl-0.5 h-full">
                      {isPositive && (
                        <div
                          className="h-4 self-center rounded-r"
                          style={{ width: `${widthPct / 2}%`, background: "#C0392B" }}
                        />
                      )}
                    </div>
                  </div>
                  <div
                    className="w-20 flex-shrink-0 text-sm font-semibold text-right flex items-center justify-end gap-1"
                    style={{ color: isPositive ? "#C0392B" : "#1A7A4A" }}
                  >
                    {isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                    {isPositive ? "+" : ""}
                    {v.value.toFixed(3)}
                  </div>
                </div>
              );
            })}
            <p className="text-xs text-slate-500 mt-4 border-t border-slate-100 pt-3">
              Red bars (right) increased the fraud probability; green bars (left) decreased it.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
