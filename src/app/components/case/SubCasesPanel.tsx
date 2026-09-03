import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { GitBranch, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import type { SubCase } from "../../types/investigation";

interface SubCasesPanelProps {
  subCases: SubCase[] | null | undefined;
  /** Attempts to locate & navigate to an existing case for this account. */
  onOpenAccount: (accountId: string) => Promise<boolean>;
}

const RISK_COLOR: Record<string, string> = {
  critical: "#C0392B",
  high:     "#D35400",
  medium:   "#B7791F",
  low:      "#1A7A4A",
};

export function SubCasesPanel({ subCases, onOpenAccount }: SubCasesPanelProps) {
  const items = subCases ?? [];
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [notFoundId, setNotFoundId] = useState<string | null>(null);

  async function handleClick(accountId: string) {
    setNotFoundId(null);
    setLoadingId(accountId);
    try {
      const found = await onOpenAccount(accountId);
      if (!found) setNotFoundId(accountId);
    } finally {
      setLoadingId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Sub-Cases (Agent 3)</CardTitle>
            <CardDescription>Connected accounts automatically escalated during network investigation</CardDescription>
          </div>
          <Badge variant="outline">
            <GitBranch className="w-3 h-3 mr-1" />
            {items.length}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-slate-400 py-4 text-center">
            No sub-cases were auto-created for this investigation.
          </p>
        ) : (
          <div className="space-y-2.5">
            {items.map((sc) => {
              const color = RISK_COLOR[sc.riskLevel] ?? "#1A3A6B";
              const isLoading = loadingId === sc.accountId;
              return (
                <button
                  key={sc.accountId}
                  onClick={() => handleClick(sc.accountId)}
                  disabled={isLoading}
                  className="w-full flex items-center justify-between gap-3 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors text-left disabled:opacity-60"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-800 truncate">{sc.accountId}</p>
                      <span
                        className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase flex-shrink-0"
                        style={{ background: color + "1A", color }}
                      >
                        {sc.riskLevel}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{sc.reason}</p>
                    {notFoundId === sc.accountId && (
                      <p className="text-xs mt-0.5" style={{ color: "#D35400" }}>
                        No filed case exists yet for this account.
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-sm font-bold" style={{ color }}>
                      {(sc.riskScore * 100).toFixed(0)}
                    </span>
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
