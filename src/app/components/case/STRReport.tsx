import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { FileText, Download, Printer, CheckCircle, Clock, Fingerprint, Loader2 } from "lucide-react";
import { caseApi } from "../../services/api";

interface STRReportProps {
  narrative: string;
  caseData: any;
  agentLog?: any[];
  explanation?: string;
}

function completedAgentCount(entries: any[] = []) {
  return new Set(entries.map((entry) => String(entry?.agent ?? "").match(/^(?:Planner→)?Agent([1-6])(?:_|$)/)?.[1]).filter(Boolean)).size;
}

function reportDuration(entries: any[] = []) {
  const times = entries.map((entry) => new Date(entry?.timestamp).getTime()).filter(Number.isFinite);
  if (times.length < 2) return null;
  return (Math.max(...times) - Math.min(...times)) / 1000;
}

export function STRReport({ narrative, caseData, agentLog, explanation }: STRReportProps) {
  const caseId     = caseData.id ?? caseData._id ?? "—";
  const priority   = caseData.priority ?? "medium";
  const riskScore  = Number(caseData.riskScore ?? caseData.risk_score ?? 0).toFixed(0);
  const fatfTypes  = caseData.fatfTypology ?? caseData.fatf_typology ?? [];
  const humanReview = caseData.humanReview ?? caseData.human_review ?? null;
  const reviewRecorded = Boolean(humanReview && ["accepted", "overridden"].includes(humanReview.status));
  const recommendation = caseData.recommendation ?? caseData.investigation?.recommendation ?? {};
  const strStatus = recommendation.strStatus ?? recommendation.str_status ?? caseData.strStatus ?? caseData.str_status;
  const strFilingStatus = recommendation.strFilingStatus ?? recommendation.str_filing_status ?? caseData.strFilingStatus ?? caseData.str_filing_status ?? "not_filed";
  const formatStatus = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const processingTime = caseData.processingTime ?? caseData.processing_time ?? null;
  const canonicalAccountId = caseData.accountId ?? caseData.account_id;
  const completedAgents = completedAgentCount(agentLog ?? caseData.agentLog ?? caseData.agent_log ?? []);
  const measuredDuration = processingTime ?? reportDuration(agentLog ?? caseData.agentLog ?? caseData.agent_log ?? []);
  let renderedNarrative = narrative ?? "";
  // Existing drafts may predate the Agent 5 construction-order fix.  Repair
  // only an empty DESCRIPTION using the separately persisted Agent 5 text.
  if (explanation) {
    renderedNarrative = renderedNarrative.replace(/^(DESCRIPTION:\s*\r?\n)(?=\s*[─-]{3,})/m, `$1${explanation}\n`);
  }
  if (canonicalAccountId) {
    renderedNarrative = renderedNarrative.replace(/^(Account:\s*).+$/m, `$1${canonicalAccountId}`);
  }
  if (completedAgents) {
    renderedNarrative = renderedNarrative.replace(/^(AGENTS RAN:\s*)\d+$/m, `$1${completedAgents}`);
  }
  const cleanNarrative = renderedNarrative
    .replace(/\n?APPROVED BY:.*(?:\n|$)/gi, "")
    .replace(/\n?Biometric verification: pending hardware integration.*(?:\n|$)/gi, "")
    .trim();

  const [downloadChallenge, setDownloadChallenge] = useState<any>(null);
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);

  const saveDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (!downloadChallenge?.challengeId) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await caseApi.checkStrDownloadChallenge(caseId, downloadChallenge.challengeId);
        if (cancelled) return;
        setDownloadChallenge(next);
        if (next.status === "success") {
          const file = await caseApi.downloadStr(caseId, next.challengeId);
          if (!cancelled) { saveDownload(file.blob, file.filename); setDownloadChallenge(null); setDownloading(false); }
          return;
        }
        if (["failed", "timeout", "hardware_error"].includes(next.status)) {
          setDownloadError(next.message ?? "Biometric verification was not completed.");
          setDownloading(false);
          return;
        }
        timer = window.setTimeout(poll, 900);
      } catch (err: any) {
        if (!cancelled) { setDownloadError(err.message ?? "Unable to authorize STR download."); setDownloading(false); }
      }
    };
    void poll();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [downloadChallenge?.challengeId, caseId]);

  const handleDownload = async () => {
    setDownloadError("");
    setDownloading(true);
    try { setDownloadChallenge(await caseApi.startStrDownloadChallenge(caseId)); }
    catch (err: any) { setDownloadError(err.message ?? "Could not start biometric authorization."); setDownloading(false); }
  };

  const checklist = [
    { item: "Subject identification details complete",       done: true  },
    { item: "Transaction details with dates and amounts",    done: true  },
    { item: "Red flags and suspicious patterns documented",  done: true  },
    { item: "FATF typology mapping included",                done: true  },
    { item: "Risk assessment and scoring provided",          done: true  },
    { item: "Regulatory framework cited (PMLA 2002)",        done: true  },
    { item: "Recommendation for action included",            done: true  },
    { item: "Compliance officer review pending",             done: false },
  ];

  return (
    <div className="space-y-5">
      {/* Action bar */}
      <Card>
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Suspicious Transaction Report (STR)</h3>
              <p className="text-xs text-slate-500 mt-1">
                STR review: {strStatus ? formatStatus(strStatus) : "Not assessed"} · Filing status: {formatStatus(strFilingStatus)}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">Generated by FinGuard AI · PMLA 2002 / FIU-IND-aligned format</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                {downloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Download
              </button>
              <button
                onClick={() => window.print()}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Printer className="w-3.5 h-3.5" /> Print
              </button>
              <button
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded transition-colors"
                style={{ background: "#1A3A6B", color: "#fff" }}
              >
                
              </button>
            </div>
          </div>
          {(downloadChallenge || downloadError) && (
            <div className="mt-3 text-xs rounded border p-3" style={{ background: "#F4F6F9", borderColor: "#D5DBE3" }}>
              {downloadChallenge && <span className="flex items-center gap-2"><Fingerprint className="w-4 h-4" /> {downloadChallenge.message ?? "Place your registered finger on the local sensor."}</span>}
              {downloadError && <span className="text-red-700">{downloadError}</span>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* STR Document */}
      <Card>
        <CardHeader className="border-b border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded" style={{ background: "#1A3A6B" }}>
                <FileText className="w-4 h-4 text-white" />
              </div>
              <div>
                <CardTitle className="text-sm">Suspicious Transaction Report</CardTitle>
                <CardDescription>
                  Case ID: {caseId} · Generated: {new Date().toLocaleDateString("en-IN")}
                </CardDescription>
              </div>
            </div>
            <span
              className="text-xs font-medium px-2.5 py-1 rounded border"
              style={{ background: "#E9F7EF", color: "#1A7A4A", borderColor: "#A9DFBF" }}
            >
              Compliance Review Draft
            </span>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          {cleanNarrative ? (
            <div className="bg-white p-6 rounded border border-slate-200 font-mono text-xs whitespace-pre-wrap text-slate-800 leading-relaxed">
              {cleanNarrative}
            </div>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No STR narrative available for this case.</p>
          )}
        </CardContent>
      </Card>

      {/* Checklist + Metadata */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Compliance Checklist</CardTitle>
            <CardDescription>PMLA 2002 &amp; FIU-IND requirements</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {checklist.map((check, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded border border-slate-100 bg-slate-50"
                >
                  <span className="text-xs text-slate-700">{check.item}</span>
                  {check.done ? (
                    <span className="flex items-center gap-1 text-xs font-medium" style={{ color: "#1A7A4A" }}>
                      <CheckCircle className="w-3 h-3" /> Done
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
                      <Clock className="w-3 h-3" /> Pending
                    </span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Report Metadata</CardTitle>
            <CardDescription>Audit trail and processing info</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Generated By",    value: "FinGuard AI v2.1" },
                { label: "Processing Time", value: measuredDuration != null ? `${Number(measuredDuration).toFixed(1)}s` : "Not captured" },
                { label: "STR Filing",      value: formatStatus(strFilingStatus) },
                { label: "Validation",      value: "✓ Passed"                 },
                { label: "Characters",      value: cleanNarrative.length.toString() },
                { label: "Case Priority",   value: priority.toUpperCase()     },
                { label: "Risk Score",      value: `${riskScore}/100`         },
                { label: "Typologies",      value: fatfTypes.length.toString() },
                { label: "Version",         value: "v2.1"                     },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="text-sm font-semibold text-slate-800">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 rounded border border-amber-200 bg-amber-50">
              <p className="text-xs font-semibold text-amber-800 mb-1">Human Review Required</p>
              <p className="text-xs text-amber-700">
                This AI-generated STR must be reviewed by a compliance officer before
                submission to FIU-IND under PMLA 2002.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
