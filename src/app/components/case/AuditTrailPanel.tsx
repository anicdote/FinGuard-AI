import { useEffect, useState } from "react";
import { Clock3, FileText, ShieldCheck, User } from "lucide-react";
import { caseApi } from "../../services/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";

function formatAction(action: string) {
  return action.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(value: any) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatMetadata(metadata: Record<string, any>) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!entries.length) return "No additional details recorded.";
  return entries.map(([key, value]) => `${formatAction(key)}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join("\n");
}

export function AuditTrailPanel({ caseId }: { caseId: string }) {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    caseApi.audit(caseId)
      .then((data) => {
        if (active) setEvents(data ?? []);
      })
      .catch((e: any) => {
        if (active) setError(e?.message ?? "Unable to load audit trail");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [caseId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-slate-600" />
          Audit Trail
        </CardTitle>
        <CardDescription>
          Read-only record of significant investigation and compliance actions.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-slate-400">Loading audit history…</p>
        ) : error ? (
          <p className="text-sm text-red-500">{error}</p>
        ) : events.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">
            No audit events recorded for this case yet.
          </div>
        ) : (
          <div className="relative space-y-4">
            {events.map((event) => {
              const actor = event.performedBy ?? {};
              const metadata = event.metadata ?? {};
              return (
                <div key={event._id} className="relative pl-8">
                  <div className="absolute left-0 top-0.5 w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center">
                    <Clock3 className="w-3.5 h-3.5 text-slate-500" />
                  </div>
                  <div className="border border-slate-200 rounded-lg p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">
                        {formatAction(event.action ?? "event")}
                      </p>
                      <span className="text-xs text-slate-400">
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {actor.name ?? "FinGuard AI"}
                      </span>
                      {actor.role && <span>Role: {actor.role}</span>}
                    </div>
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-medium text-slate-600">
                        <span className="inline-flex items-center gap-1">
                          <FileText className="w-3 h-3" /> Event details
                        </span>
                      </summary>
                      <pre className="mt-2 overflow-auto rounded bg-slate-50 p-2 text-[11px] leading-5 text-slate-600 whitespace-pre-wrap">
                        {formatMetadata(metadata)}
                      </pre>
                    </details>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
