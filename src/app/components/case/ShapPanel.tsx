import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../ui/card";
import {
  TrendingUp,
  TrendingDown,
  Sparkles,
} from "lucide-react";
import type { ShapFeature } from "../../types/investigation";

interface ShapPanelProps {
  shapValues:
    | ShapFeature[]
    | null
    | undefined;
}

function labelize(
  feature: string
): string {
  return feature
    .replace(/_/g, " ")
    .replace(
      /\b\w/g,
      (c) => c.toUpperCase()
    );
}

export function ShapPanel({
  shapValues,
}: ShapPanelProps) {
  const values = (shapValues ?? []).slice(0, 5);

  const maxAbs = Math.max(
    1e-6,
    ...values.map((v) => Math.abs(v.value))
  );

  return (
    <Card className="border border-slate-200 shadow-sm overflow-hidden">
      <CardHeader className="px-5 py-4 border-b border-slate-100">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-sm font-semibold text-slate-800">
              Why This Was Flagged? (SHAP Explanation)
            </CardTitle>
            <CardDescription className="text-xs mt-1">
              Top feature contributions from Agent 1's XGBoost model — how far each feature pushed the fraud probability up (↑) or down (↓)
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-5 py-5">
        {values.length === 0 ? (
          <div className="py-7 text-center">
            <Sparkles className="w-6 h-6 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-400">
              No SHAP values available for this case.
            </p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-md mx-auto leading-relaxed">
              The ML explanation may not have been available when this case was investigated, so rule-based fallback scoring may have been used.
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-3.5">
              {values.map((v, idx) => {
                const isPositive = v.value >= 0;
                const widthPct = (Math.abs(v.value) / maxAbs) * 50;

                return (
                  <div key={`${v.feature}-${idx}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-slate-700">
                        {labelize(v.feature)}
                      </span>

                      <span
                        className="flex items-center gap-1 text-xs font-semibold"
                        style={{
                          color: isPositive ? "#B42318" : "#15803D",
                        }}
                      >
                        {isPositive ? (
                          <TrendingUp className="w-3 h-3" />
                        ) : (
                          <TrendingDown className="w-3 h-3" />
                        )}
                        {isPositive ? "+" : ""}
                        {v.value.toFixed(3)}
                      </span>
                    </div>

                    <div className="relative h-2.5 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="absolute top-0 bottom-0 rounded-full"
                        style={{
                          width: `${Math.max(2, widthPct)}%`,
                          left: isPositive ? "50%" : "auto",
                          right: isPositive ? "auto" : "50%",
                          transform: isPositive ? "none" : "translateX(0)",
                          background: isPositive ? "#C0392B" : "#218C5A",
                        }}
                      />
                      <div className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-300" />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between gap-3">
              <p className="text-[10px] text-slate-400">
                Red bars (right) increased the fraud probability; green bars (left) decreased it.
              </p>
              <div className="hidden sm:flex items-center gap-3 text-[10px] text-slate-400 shrink-0">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  Increases risk
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Decreases risk
                </span>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
