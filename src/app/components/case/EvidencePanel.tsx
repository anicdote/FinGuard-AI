import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { AlertTriangle, ShieldAlert, User } from "lucide-react";
import type { Evidence, WatchlistHit } from "../../types/investigation";

interface EvidencePanelProps {
  evidence: Evidence | null | undefined;
  watchlistHits?: WatchlistHit[] | null;
}

function labelize(pattern: string): string {
  return pattern.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function EvidencePanel({ evidence, watchlistHits }: EvidencePanelProps) {
  const patterns   = evidence?.patterns ?? [];
  const confidence = evidence?.evidenceConfidence ?? 0;
  const riskBoost  = evidence?.riskBoost ?? 0;
  const hits       = watchlistHits ?? [];

  const hasEvidence = patterns.length > 0 || Object.keys(evidence ?? {}).length > 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Evidence confidence */}
      <Card>
        <CardHeader>
          <CardTitle>Evidence Confidence (Agent 2)</CardTitle>
          <CardDescription>How confident the evidence-gathering agent is in its findings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-900">Evidence Confidence</span>
              <span className="text-2xl font-bold text-blue-600">{(confidence * 100).toFixed(0)}</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-3">
              <div className="bg-blue-600 h-3 rounded-full transition-all" style={{ width: `${Math.min(confidence * 100, 100)}%` }} />
            </div>
            <p className="text-sm text-slate-500 mt-2">Derived from the patterns matched and their weighting.</p>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-900">Risk Boost Contributed</span>
              <span className="text-2xl font-bold text-orange-600">+{(riskBoost * 100).toFixed(0)}</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-3">
              <div className="bg-orange-600 h-3 rounded-full transition-all" style={{ width: `${Math.min(riskBoost * 100, 100)}%` }} />
            </div>
            <p className="text-sm text-slate-500 mt-2">How much Agent 2's findings raised the overall risk assessment.</p>
          </div>

          {evidence?.counterparty && (
            <div className="p-3 rounded-lg border border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                <User className="w-3.5 h-3.5" /> Counterparty
              </div>
              <p className="text-sm font-semibold text-slate-800">{evidence.counterparty}</p>
              {evidence.location && <p className="text-xs text-slate-500 mt-0.5">Location: {evidence.location}</p>}
              {evidence.channel && <p className="text-xs text-slate-500">Channel: {evidence.channel}</p>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Suspicious Patterns */}
      <Card>
        <CardHeader>
          <CardTitle>Suspicious Patterns Detected</CardTitle>
          <CardDescription>
            {patterns.length} pattern{patterns.length !== 1 ? "s" : ""} identified by Agent 2
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!hasEvidence ? (
            <p className="text-sm text-slate-400 py-4 text-center">
              No evidence data available for this case.
            </p>
          ) : patterns.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">No suspicious patterns flagged.</p>
          ) : (
            <div className="space-y-3">
              {patterns.map((pattern, idx) => (
                <div key={idx} className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-red-900 font-medium">{labelize(pattern)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Watchlist / PEP / Sanctions */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Watchlist / PEP / Sanctions Screening</CardTitle>
          <CardDescription>Counterparty screening results from Agent 2</CardDescription>
        </CardHeader>
        <CardContent>
          {hits.length === 0 ? (
            <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <ShieldAlert className="w-5 h-5 text-green-700 flex-shrink-0" />
              <p className="text-sm text-green-800">No watchlist, PEP, or sanctions hits found for this counterparty.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {hits.map((hit, idx) => (
                <div key={idx} className="flex items-start gap-3 p-4 bg-red-50 border border-red-300 rounded-lg">
                  <ShieldAlert className="w-5 h-5 text-red-700 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-red-900 font-semibold">{hit.entity}</p>
                      <Badge variant="destructive" className="text-[10px]">{hit.list}</Badge>
                    </div>
                    <p className="text-xs text-red-800 mt-1">
                      Matched on {hit.type} · counterparty field: "{hit.match}"
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
