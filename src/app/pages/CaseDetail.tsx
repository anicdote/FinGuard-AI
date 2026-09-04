import { useParams, Link, useNavigate } from "react-router";
import { useState, useEffect } from "react";
import { useCase } from "../hooks/useApi";
import { caseApi, userApi } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  ArrowLeft, AlertTriangle, Calendar, Clock, TrendingUp,
  CheckCircle, Loader2, Sparkles, ShieldAlert, UserCog,
  Info, ListChecks, Network, Eye, FileText, ShieldCheck,
} from "lucide-react";
import { NetworkGraph } from "../components/case/NetworkGraph";
import { TransactionTimeline } from "../components/case/TransactionTimeline";
import { EvidencePanel } from "../components/case/EvidencePanel";
import { STRReport } from "../components/case/STRReport";
import { RecommendationPanel } from "../components/case/RecommendationPanel";
import { ShapPanel } from "../components/case/ShapPanel";
import { RegulatoryPanel } from "../components/case/RegulatoryPanel";
import { AgentTracePanel } from "../components/case/AgentTracePanel";
import { SubCasesPanel } from "../components/case/SubCasesPanel";
import { AuditTrailPanel } from "../components/case/AuditTrailPanel";
import type { CaseData, Recommendation } from "../types/investigation";

type Agent5Explanation = {
  transactionId?: string;
  riskLevel?: string;
  riskPercent?: number;
  keyDrivers: Array<{ feature: string; value: string; positive: boolean }>;
  patterns: string[];
  network?: string;
  watchlist: string[];
  typologyName?: string;
  typologyCode?: string;
  typologyConfidence?: number;
  pmla?: string;
  fallback?: string;
};

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseAgent5Explanation(text: string): Agent5Explanation {
  const result: Agent5Explanation = {
    keyDrivers: [],
    patterns: [],
    watchlist: [],
  };

  const riskMatch = text.match(
    /^Transaction\s+(.+?)\s+flagged with\s+([A-Za-z]+)\s+risk\s+\(([\d.]+)%\)\./i
  );

  if (riskMatch) {
    result.transactionId = riskMatch[1].trim();
    result.riskLevel = riskMatch[2].toUpperCase();
    result.riskPercent = Number(riskMatch[3]);
  }

  const driverMatch = text.match(
    /Key drivers:\s*(.*?)(?:\.\s*Patterns:|$)/i
  );
  if (driverMatch) {
    result.keyDrivers = driverMatch[1]
      .split(/,\s*/)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => {
        const match = item.match(
          /^(.+?):\s*([↑↓])\s*([\d.]+)$/
        );
        if (!match) {
          return {
            feature: titleCase(item),
            value: "",
            positive: false,
          };
        }
        return {
          feature: titleCase(match[1]),
          value: `${match[2]}${match[3]}`,
          positive: match[2] === "↑",
        };
      });
  }

  const patternsMatch = text.match(
    /Patterns:\s*(.*?)(?:\.\s*Network:|\.\s*Watchlist:|\.\s*Typology:|$)/i
  );
  if (patternsMatch) {
    result.patterns = patternsMatch[1]
      .split(/,\s*/)
      .map((item) => titleCase(item.trim()))
      .filter(Boolean);
  }

  const networkMatch = text.match(
    /Network:\s*(.*?)(?:\.\s*Watchlist:|\.\s*Typology:|$)/i
  );
  if (networkMatch) {
    result.network = networkMatch[1].trim();
  }

  const watchlistMatch = text.match(
    /Watchlist:\s*(.*?)(?:\.\s*Typology:|$)/i
  );
  if (watchlistMatch) {
    result.watchlist = watchlistMatch[1]
      .split(/,\s*/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  const typologyMatch = text.match(
    /Typology:\s*(.*?)\s*\(([^)]+)\)\s*[—-]\s*([\d.]+)%\s*confidence\./i
  );
  if (typologyMatch) {
    result.typologyName = typologyMatch[1].trim();
    result.typologyCode = typologyMatch[2].trim();
    result.typologyConfidence = Number(typologyMatch[3]);
  }

  const pmlaMatch = text.match(/PMLA:\s*(.*?)(?:\.|$)/i);
  if (pmlaMatch) {
    result.pmla = pmlaMatch[1].trim();
  }

  const hasStructuredData =
    !!result.transactionId ||
    result.keyDrivers.length > 0 ||
    result.patterns.length > 0 ||
    !!result.network ||
    result.watchlist.length > 0 ||
    !!result.typologyName ||
    !!result.pmla;

  if (!hasStructuredData) {
    result.fallback = text;
  }

  return result;
}

// Safe date helper — works whether value is a Date object or an ISO string
function safeDate(val: any): Date {
  if (!val) return new Date();
  if (val instanceof Date) return val;
  return new Date(val);
}

export function CaseDetail() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: caseData, loading, error, refetch } = useCase(caseId ?? "");
  const [updating, setUpdating] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [reviewMode, setReviewMode] = useState<"override" | "evidence" | null>(null);
  const [overrideDecision, setOverrideDecision] = useState("MONITOR");
  const [reviewReason, setReviewReason] = useState("");

  // Phase 9 — false-positive feedback
  const [falsePositiveOpen, setFalsePositiveOpen] = useState(false);
  const [falsePositiveReason, setFalsePositiveReason] = useState("");
  const [falsePositiveNotes, setFalsePositiveNotes] = useState("");
  const [falsePositiveSubmitting, setFalsePositiveSubmitting] = useState(false);
  const [falsePositiveStats, setFalsePositiveStats] = useState<any>(null);

  // Phase 8 — case assignment (manager/admin only)
  const role = user?.role === "analyst" ? "officer" : user?.role;
  const canAssign = role === "manager" || role === "admin";
  const [officers, setOfficers] = useState<any[]>([]);
  const [selectedOfficerId, setSelectedOfficerId] = useState("");
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (canAssign) {
      userApi.listOfficers().then(setOfficers).catch(() => setOfficers([]));
    }
    caseApi.falsePositiveStats().then(setFalsePositiveStats).catch(() => setFalsePositiveStats(null));
  }, [canAssign]);

  if (loading) {
    return (
      <div className="container mx-auto px-6 py-16 flex flex-col items-center gap-3 text-slate-400">
        <Loader2 className="w-7 h-7 animate-spin" />
        <p className="text-sm">Loading case…</p>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="container mx-auto px-6 py-8 text-center">
        <AlertTriangle className="w-14 h-14 text-slate-300 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-slate-800 mb-2">Case Not Found</h2>
        <p className="text-slate-500 mb-4 text-sm">
          {error ?? "The case ID does not exist in the current dataset."}
        </p>
        <Link to="/">
          <button className="text-sm font-semibold px-4 py-2 rounded" style={{ background: "#1A3A6B", color: "#fff" }}>
            Return to Dashboard
          </button>
        </Link>
      </div>
    );
  }

  const c = caseData as CaseData;

  // ── Safely access all fields (handle both camelCase from API and direct fields) ──
  const accountId   = c.accountId   ?? (caseData as any).account_id   ?? "—";
  const accountName = c.accountName ?? (caseData as any).account_name ?? "Unknown";
  const riskScore   = c.riskScore   ?? (caseData as any).risk_score   ?? 0;
  const anomalyScore = c.anomalyScore ?? (caseData as any).anomaly_score ?? 0;
  const detectedAt  = safeDate(c.detectedAt ?? (caseData as any).detected_at);
  const fatfTypology = c.fatfTypology ?? (caseData as any).fatf_typology ?? [];
  const persistedStrNarrative = c.strNarrative ?? (caseData as any).str_narrative ?? "";

  const suspiciousTxns: any[] = c.suspiciousTransactions
    ?? (caseData as any).suspicious_transactions
    ?? [];

  // ── New autonomous-investigation fields. CaseService mirrors these at the
  //    top level of the case document, so we read them directly rather than
  //    diving into `investigation` (kept as a fallback for older cases). ──
  const investigation = c.investigation ?? {};
  // The full Agent 6 recommendation is authoritative. CaseService also mirrors
  // selected fields at the case level, which remain a fallback for older data.
  const storedRecommendation = c.recommendation ?? investigation.recommendation ?? {};
  const recommendation: Recommendation = {
    ...storedRecommendation,
    decision: storedRecommendation.decision ?? c.decision,
    decisionCategory: storedRecommendation.decisionCategory ?? c.decisionCategory,
    caseAction: storedRecommendation.caseAction ?? c.caseAction,
    requiresHumanReview: storedRecommendation.requiresHumanReview ?? c.requiresHumanReview,
    missingInformation: storedRecommendation.missingInformation ?? c.missingInformation,
    strStatus: storedRecommendation.strStatus ?? c.strStatus,
    strFilingStatus: storedRecommendation.strFilingStatus ?? c.strFilingStatus,
  };
  // Agent 6 preserves Agent 5's draft for compatibility.  Prefer the original
  // case field, then use that persisted compatible field for older cases.
  const strNarrative = persistedStrNarrative
    || storedRecommendation.agent5StrDraft
    || (storedRecommendation as any).agent5_str_draft
    || investigation.strNarrative
    || "";
  const recommendationAction = recommendation.caseAction ?? recommendation.decision ?? recommendation.action;
  const explanation    = c.explanation    ?? investigation.explanation    ?? "";
  const shapValues      = c.shapValues      ?? investigation.shapValues      ?? [];
  const agentLog         = c.agentLog         ?? investigation.agentLog         ?? [];
  const subCases          = c.subCases          ?? investigation.subCases          ?? [];
  const watchlistHits       = c.watchlistHits       ?? investigation.watchlistHits       ?? [];
  const regulatory            = c.regulatory            ?? investigation.regulatory            ?? {};
  const confidenceScores        = c.confidenceScores        ?? investigation.confidenceScores        ?? {};
  const anomalyScores             = investigation.anomalyScores ?? {};
  const disagreementFlag           = investigation.flags?.disagreementFlag ?? false;
  const humanReview = (c as any).humanReview ?? (caseData as any).human_review ?? null;
  const falsePositive = (c as any).falsePositive ?? (caseData as any).false_positive ?? false;
  const falsePositiveFeedback = (c as any).falsePositiveFeedback ?? (caseData as any).false_positive_feedback ?? null;
  const assignedOfficerId   = (c as any).assignedOfficerId   ?? (caseData as any).assigned_officer_id   ?? null;
  const assignedOfficerName = (c as any).assignedOfficerName ?? (caseData as any).assigned_officer_name ?? null;

  const evidence = c.evidenceSummary ?? (caseData as any).evidence_summary ?? {};
  const networkAnalysis = c.networkAnalysis ?? (caseData as any).network_analysis ?? {};

  // ── Time period calculation (safe) ────────────────────────────────────────
  let timePeriodDays = 0;
  if (suspiciousTxns.length >= 2) {
    const times = suspiciousTxns.map((t: any) => safeDate(t.timestamp).getTime()).filter(Boolean);
    if (times.length >= 2) {
      timePeriodDays = Math.ceil(Math.abs(Math.max(...times) - Math.min(...times)) / (1000 * 60 * 60 * 24));
    }
  }

  const priorityConfig: Record<string, { bg: string; color: string; border: string }> = {
    critical: { bg: "#FDECEA", color: "#C0392B", border: "#F5C6C2" },
    high:     { bg: "#FEF3E7", color: "#D35400", border: "#FAD7A0" },
    medium:   { bg: "#FEFCE8", color: "#B7791F", border: "#FDE68A" },
    low:      { bg: "#E9F7EF", color: "#1A7A4A", border: "#A9DFBF" },
  };
  const statusConfig: Record<string, { bg: string; color: string }> = {
    new:           { bg: "#EBF0F8", color: "#1A3A6B" },
    investigating: { bg: "#F3E8FF", color: "#6B21A8" },
    reviewed:      { bg: "#E9F7EF", color: "#1A7A4A" },
    filed:         { bg: "#E9F7EF", color: "#1A7A4A" },
  };

  const priority = caseData.priority ?? "medium";
  const status   = caseData.status   ?? "new";
  const pc = priorityConfig[priority] ?? priorityConfig.medium;
  const sc = statusConfig[status]     ?? statusConfig.new;

  async function handleAcceptRecommendation() {
    setReviewing(true);
    try {
      await caseApi.acceptRecommendation(caseId!);
      setStatusMsg("AI recommendation accepted successfully");
      await refetch();
    } catch (e: any) {
      setStatusMsg(e.message ?? "Unable to accept recommendation");
    } finally {
      setReviewing(false);
      setTimeout(() => setStatusMsg(""), 4000);
    }
  }

  async function handleReviewSubmit() {
    if (!reviewReason.trim()) {
      setStatusMsg(reviewMode === "override" ? "Override reason is required" : "Evidence request is required");
      return;
    }
    setReviewing(true);
    try {
      if (reviewMode === "override") {
        await caseApi.overrideRecommendation(caseId!, overrideDecision, reviewReason.trim());
        setStatusMsg("Recommendation overridden successfully");
      } else {
        await caseApi.requestMoreEvidence(caseId!, reviewReason.trim());
        setStatusMsg("Additional evidence requested");
      }
      setReviewMode(null);
      setReviewReason("");
      await refetch();
    } catch (e: any) {
      setStatusMsg(e.message ?? "Review action failed");
    } finally {
      setReviewing(false);
      setTimeout(() => setStatusMsg(""), 4000);
    }
  }

  async function handleFalsePositiveSubmit() {
    if (!falsePositiveReason.trim()) {
      setStatusMsg("False-positive reason is required");
      return;
    }
    setFalsePositiveSubmitting(true);
    try {
      await caseApi.markFalsePositive(caseId!, falsePositiveReason.trim(), falsePositiveNotes.trim());
      setStatusMsg("Case marked as false positive");
      setFalsePositiveOpen(false);
      setFalsePositiveReason("");
      setFalsePositiveNotes("");
      await refetch();
      caseApi.falsePositiveStats().then(setFalsePositiveStats).catch(() => {});
    } catch (e: any) {
      setStatusMsg(e.message ?? "Unable to record false-positive feedback");
    } finally {
      setFalsePositiveSubmitting(false);
      setTimeout(() => setStatusMsg(""), 4000);
    }
  }

  async function handleMarkReviewed() {
    setUpdating(true);
    try {
      await caseApi.updateStatus(caseId!, "reviewed");
      setStatusMsg("STR marked as reviewed");
      refetch();
    } catch (e: any) {
      setStatusMsg(e.message ?? "Update failed");
    } finally {
      setUpdating(false);
      setTimeout(() => setStatusMsg(""), 3000);
    }
  }

  async function handleAssign() {
    if (!selectedOfficerId) return;
    setAssigning(true);
    try {
      await caseApi.assign(caseId!, selectedOfficerId);
      setStatusMsg("Case assigned successfully");
      await refetch();
    } catch (e: any) {
      setStatusMsg(e.message ?? "Assignment failed");
    } finally {
      setAssigning(false);
      setTimeout(() => setStatusMsg(""), 3000);
    }
  }

  // Sub-cases only carry an account_id, not a case_id (Agent 3 doesn't file a
  // separate case document per sub-case). Best-effort: search existing cases
  // for a matching account and navigate there if one exists.
  async function handleOpenAccount(subAccountId: string): Promise<boolean> {
    try {
      const cases = await caseApi.list({ limit: 200 });
      const match = (cases ?? []).find(
        (cs: any) => (cs.accountId ?? cs.account_id) === subAccountId
      );
      if (match) {
        const targetId = match.id ?? match._id;
        navigate(`/case/${targetId}`);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  return (
    <div className="container mx-auto px-6 py-7">
      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 mb-5">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </Link>

      {statusMsg && (
        <div className="mb-4 px-4 py-2 rounded text-sm font-medium" style={{ background: "#E9F7EF", color: "#1A7A4A" }}>
          {statusMsg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-900">Case {caseData.id}</h1>
            <span className="text-xs font-semibold px-2.5 py-1 rounded border"
                  style={{ background: pc.bg, color: pc.color, borderColor: pc.border }}>
              {priority.toUpperCase()} PRIORITY
            </span>
            <span className="text-xs font-medium px-2.5 py-1 rounded"
                  style={{ background: sc.bg, color: sc.color }}>
              {status.toUpperCase()}
            </span>
            {watchlistHits.length > 0 && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1"
                    style={{ background: "#FDECEA", color: "#C0392B" }}>
                <ShieldAlert className="w-3 h-3" /> WATCHLIST HIT
              </span>
            )}
            <span className="text-xs font-medium px-2.5 py-1 rounded flex items-center gap-1 text-slate-500 bg-slate-100">
              <Sparkles className="w-3 h-3" /> Investigated by 6-agent pipeline
            </span>
          </div>
          <p className="text-sm text-slate-500">
            Account: {accountName} &nbsp;·&nbsp; {accountId}
          </p>
        </div>
        <div className="flex gap-2.5">
          <button
            onClick={handleMarkReviewed}
            disabled={updating}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            {updating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
            Mark STR Reviewed
          </button>
        </div>
      </div>

      {/* Case Assignment — Phase 8 */}
      <Card className="mb-6 border border-slate-200">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <UserCog className="w-4 h-4 text-slate-500" />
              <p className="text-sm text-slate-700">
                {assignedOfficerName ? (
                  <>Assigned to <b>{assignedOfficerName}</b></>
                ) : (
                  <span className="text-slate-400">Unassigned</span>
                )}
              </p>
            </div>
            {canAssign ? (
              <div className="flex items-center gap-2">
                <select
                  value={selectedOfficerId}
                  onChange={(e) => setSelectedOfficerId(e.target.value)}
                  className="text-xs border border-slate-300 rounded px-2 py-1.5"
                >
                  <option value="">Select officer…</option>
                  {officers.map((o) => (
                    <option key={o._id} value={o._id}>{o.name ?? o.email}</option>
                  ))}
                </select>
                <button
                  onClick={handleAssign}
                  disabled={assigning || !selectedOfficerId}
                  className="text-xs font-semibold px-3 py-1.5 rounded text-white disabled:opacity-50"
                  style={{ background: "#1A3A6B" }}
                >
                  {assigning ? "Assigning…" : assignedOfficerName ? "Reassign" : "Assign"}
                </button>
              </div>
            ) : (
              <span className="text-xs text-slate-400">Only managers/admins can assign cases</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Risk + Recommendation — always visible, most important info for a quick read */}
      <RecommendationPanel
        recommendation={recommendation}
        anomalyScores={anomalyScores}
        riskScore={riskScore}
        disagreementFlag={disagreementFlag}
      />

      {/* Human-in-the-loop compliance review */}
      <Card className="mb-6 border-2 border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-slate-600" /> Compliance Officer Review
          </CardTitle>
          <CardDescription>
            AI completes the investigation; the compliance officer makes the final accountable decision.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {humanReview ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2 mb-4">
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <span><b>Review:</b> {humanReview.status?.replaceAll("_", " ")}</span>
                <span><b>Reviewer:</b> {humanReview.reviewerName ?? "—"}</span>
                <span><b>Final decision:</b> {humanReview.finalDecision ?? "Pending"}</span>
              </div>
              {humanReview.reason && <p className="text-sm text-slate-600"><b>Reason:</b> {humanReview.reason}</p>}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button onClick={handleAcceptRecommendation} disabled={reviewing || !!humanReview && humanReview.status !== "more_evidence_requested"}
              className="px-3 py-2 rounded text-xs font-semibold text-white disabled:opacity-50" style={{ background: "#1A7A4A" }}>
              {reviewing ? "Processing…" : "Accept AI Recommendation"}
            </button>
            <button onClick={() => { setReviewMode("override"); setReviewReason(""); }} disabled={reviewing}
              className="px-3 py-2 rounded text-xs font-semibold border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50">
              Override
            </button>
            <button onClick={() => { setReviewMode("evidence"); setReviewReason(""); }} disabled={reviewing}
              className="px-3 py-2 rounded text-xs font-semibold border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50">
              Request More Evidence
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Phase 9 — false-positive feedback */}
      <Card className="mb-6 border-2 border-amber-100">
        <CardHeader>
          <CardTitle className="text-sm">Investigator Feedback</CardTitle>
          <CardDescription>
            Record when an investigation was ultimately determined to be a false positive. This is collected for model/system monitoring; it does not retrain the model automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {falsePositive ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-2">
              <p className="text-sm font-semibold text-amber-900">Marked as False Positive</p>
              <p className="text-sm text-slate-700"><b>Reason:</b> {falsePositiveFeedback?.reason ?? "—"}</p>
              {falsePositiveFeedback?.notes && <p className="text-sm text-slate-600"><b>Notes:</b> {falsePositiveFeedback.notes}</p>}
              <p className="text-xs text-slate-400">Recorded by {falsePositiveFeedback?.reviewerName ?? falsePositiveFeedback?.reviewer_name ?? "—"}</p>
            </div>
          ) : (
            <button
              onClick={() => setFalsePositiveOpen(true)}
              disabled={falsePositiveSubmitting}
              className="px-3 py-2 rounded text-xs font-semibold border border-amber-300 text-amber-800 hover:bg-amber-50 disabled:opacity-50"
            >
              Mark as False Positive
            </button>
          )}
          {falsePositiveStats && (
            <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
              <span><b>{falsePositiveStats.falsePositiveCount ?? falsePositiveStats.false_positive_count ?? 0}</b> false positives</span>
              <span><b>{Number(falsePositiveStats.falsePositiveRate ?? falsePositiveStats.false_positive_rate ?? 0).toFixed(1)}%</b> of cases</span>
            </div>
          )}
        </CardContent>
      </Card>

      {reviewMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white shadow-xl p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-1">
              {reviewMode === "override" ? "Override AI Recommendation" : "Request More Evidence"}
            </h2>
            <p className="text-sm text-slate-500 mb-5">
              AI recommendation: <b>{recommendationAction ?? "—"}</b>
            </p>
            {reviewMode === "override" && (
              <label className="block mb-4">
                <span className="text-xs font-semibold text-slate-600">New decision</span>
                <select value={overrideDecision} onChange={(e) => setOverrideDecision(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm">
                  {['BLOCK','MONITOR','ESCALATE','FILE_STR','REQUEST_INFO','CLOSE'].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </label>
            )}
            <label className="block mb-5">
              <span className="text-xs font-semibold text-slate-600">{reviewMode === "override" ? "Reason (required)" : "Evidence requested (required)"}</span>
              <textarea value={reviewReason} onChange={(e) => setReviewReason(e.target.value)} rows={4}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm resize-none" placeholder={reviewMode === "override" ? "Why are you overriding the AI?" : "What additional evidence should be investigated?"} />
            </label>
            <div className="flex justify-end gap-2">
              <button onClick={() => setReviewMode(null)} className="px-3 py-2 rounded text-sm border border-slate-300">Cancel</button>
              <button onClick={handleReviewSubmit} disabled={reviewing || !reviewReason.trim()} className="px-3 py-2 rounded text-sm font-semibold text-white disabled:opacity-50" style={{ background: "#1A3A6B" }}>
                {reviewing ? "Saving…" : reviewMode === "override" ? "Confirm Override" : "Request Evidence"}
              </button>
            </div>
          </div>
        </div>
      )}

      {falsePositiveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white shadow-xl p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-1">Mark Case as False Positive</h2>
            <p className="text-sm text-slate-500 mb-5">Record why the investigation was determined to be legitimate or non-suspicious.</p>
            <label className="block mb-4">
              <span className="text-xs font-semibold text-slate-600">Reason (required)</span>
              <select value={falsePositiveReason} onChange={(e) => setFalsePositiveReason(e.target.value)} className="mt-1 w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">Select a reason</option>
                <option value="Legitimate customer activity">Legitimate customer activity</option>
                <option value="Known business transaction">Known business transaction</option>
                <option value="Expected account behaviour">Expected account behaviour</option>
                <option value="Model false positive">Model false positive</option>
                <option value="Insufficient evidence of suspicious activity">Insufficient evidence of suspicious activity</option>
                <option value="Other">Other</option>
              </select>
            </label>
            <label className="block mb-5">
              <span className="text-xs font-semibold text-slate-600">Additional notes (optional)</span>
              <textarea value={falsePositiveNotes} onChange={(e) => setFalsePositiveNotes(e.target.value)} rows={4}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm resize-none" placeholder="Add supporting context for future monitoring…" />
            </label>
            <div className="flex justify-end gap-2">
              <button onClick={() => setFalsePositiveOpen(false)} className="px-3 py-2 rounded text-sm border border-slate-300">Cancel</button>
              <button onClick={handleFalsePositiveSubmit} disabled={falsePositiveSubmitting || !falsePositiveReason.trim()} className="px-3 py-2 rounded text-sm font-semibold text-white disabled:opacity-50" style={{ background: "#B7791F" }}>
                {falsePositiveSubmitting ? "Saving…" : "Confirm False Positive"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Structured AI explanation (Agent 5) */}
      {explanation && (() => {
        const parsed = parseAgent5Explanation(explanation);
        const riskColor =
          parsed.riskLevel === "CRITICAL" || parsed.riskLevel === "HIGH"
            ? "#C0392B"
            : parsed.riskLevel === "MEDIUM"
              ? "#B7791F"
              : "#1A7A4A";

        return (
          <Card className="mb-6 border border-slate-200 shadow-sm overflow-hidden">
            <CardHeader className="px-5 py-4 border-b border-slate-100">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                    <Info className="w-4 h-4 text-slate-600" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-semibold text-slate-800">
                      AI Investigation Explanation
                    </CardTitle>
                    <CardDescription className="text-xs mt-0.5">
                      Agent 5 · Evidence synthesis and model explanation
                    </CardDescription>
                  </div>
                </div>

                {parsed.riskLevel && (
                  <div className="text-right shrink-0">
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide"
                      style={{
                        color: riskColor,
                        background:
                          riskColor === "#C0392B" ? "#FDECEA" :
                          riskColor === "#B7791F" ? "#FEF3C7" : "#E9F7EF",
                      }}
                    >
                      {parsed.riskLevel} RISK
                    </span>
                    {typeof parsed.riskPercent === "number" && (
                      <p className="text-[11px] text-slate-400 mt-1">
                        {parsed.riskPercent.toFixed(1)}% model probability
                      </p>
                    )}
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent className="px-5 py-5">
              {parsed.fallback ? (
                <div className="rounded-lg bg-slate-50 border border-slate-100 px-4 py-3">
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {parsed.fallback}
                  </p>
                </div>
              ) : (
                <div className="space-y-5">
                  {parsed.transactionId && (
                    <div className="rounded-lg bg-slate-50 border border-slate-100 px-3.5 py-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        Investigated transaction
                      </p>
                      <p className="text-xs font-semibold text-slate-700 mt-1 font-mono break-all">
                        {parsed.transactionId}
                      </p>
                    </div>
                  )}

                  {parsed.keyDrivers.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2.5">
                        <TrendingUp className="w-3.5 h-3.5 text-slate-500" />
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                          Key model drivers
                        </p>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {parsed.keyDrivers.map((driver) => (
                          <div
                            key={driver.feature}
                            className="rounded-lg border px-3 py-2.5"
                            style={{
                              background: driver.positive ? "#FEF2F2" : "#F0FDF4",
                              borderColor: driver.positive ? "#FECACA" : "#BBF7D0",
                            }}
                          >
                            <p className="text-[10px] font-medium text-slate-500">
                              {driver.feature}
                            </p>
                            <p
                              className="text-sm font-bold mt-1"
                              style={{ color: driver.positive ? "#B42318" : "#15803D" }}
                            >
                              {driver.value}
                            </p>
                            <p
                              className="text-[10px] mt-0.5"
                              style={{ color: driver.positive ? "#B42318" : "#15803D" }}
                            >
                              {driver.positive ? "Increases risk" : "Decreases risk"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {parsed.patterns.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2.5">
                        <ListChecks className="w-3.5 h-3.5 text-slate-500" />
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                          Detected patterns
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {parsed.patterns.map((pattern) => (
                          <span
                            key={pattern}
                            className="px-2.5 py-1.5 rounded-md bg-slate-50 border border-slate-200 text-[11px] font-medium text-slate-700"
                          >
                            {pattern}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {(parsed.network || parsed.watchlist.length > 0) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {parsed.network && (
                        <div className="rounded-lg border border-slate-200 bg-white px-3.5 py-3">
                          <div className="flex items-center gap-2">
                            <Network className="w-3.5 h-3.5 text-slate-500" />
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                              Network findings
                            </p>
                          </div>
                          <p className="text-xs font-medium text-slate-700 mt-1.5">
                            {parsed.network}
                          </p>
                        </div>
                      )}

                      {parsed.watchlist.length > 0 && (
                        <div className="rounded-lg border border-red-100 bg-red-50 px-3.5 py-3">
                          <div className="flex items-center gap-2">
                            <Eye className="w-3.5 h-3.5 text-red-600" />
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                              Watchlist hit
                            </p>
                          </div>
                          <div className="mt-1.5 space-y-1">
                            {parsed.watchlist.map((entity) => (
                              <p key={entity} className="text-xs font-semibold text-red-800">
                                {entity}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {(parsed.typologyName || parsed.pmla) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {parsed.typologyName && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <FileText className="w-3.5 h-3.5 text-slate-500" />
                              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                FATF typology
                              </p>
                            </div>
                            {parsed.typologyCode && (
                              <span className="px-2 py-0.5 rounded bg-white border border-slate-200 text-[10px] font-bold text-slate-600">
                                {parsed.typologyCode}
                              </span>
                            )}
                          </div>
                          <p className="text-xs font-semibold text-slate-700 mt-1.5">
                            {parsed.typologyName}
                          </p>
                          {typeof parsed.typologyConfidence === "number" && (
                            <p className="text-[10px] text-slate-500 mt-1">
                              {parsed.typologyConfidence.toFixed(1)}% confidence
                            </p>
                          )}
                        </div>
                      )}

                      {parsed.pmla && (
                        <div className="rounded-lg border border-blue-100 bg-blue-50 px-3.5 py-3">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-3.5 h-3.5 text-blue-700" />
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-600">
                              Regulatory reference
                            </p>
                          </div>
                          <p className="text-xs font-semibold text-blue-900 mt-1.5">
                            PMLA · {parsed.pmla}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* Quick stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Risk Score",    value: `${Number(riskScore).toFixed(0)}/100`,      icon: TrendingUp, color: "#C0392B" },
          { label: "Anomaly Score", value: Number(anomalyScore).toFixed(2),            icon: AlertTriangle, color: "#D35400" },
          { label: "Transactions",  value: suspiciousTxns.length,                       icon: Clock, color: "#1A3A6B" },
          { label: "Detected",      value: detectedAt.toLocaleDateString("en-IN"),     icon: Calendar, color: "#1A7A4A" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="pt-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                  <p className="text-xl font-bold" style={{ color }}>{value}</p>
                </div>
                <Icon className="w-6 h-6 text-slate-300" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-5">
        <TabsList className="bg-slate-100 border border-slate-200 p-1 rounded-lg flex-wrap h-auto">
          {["overview", "evidence", "network", "regulatory", "trace", "audit", "transactions", "str"].map((tab) => (
            <TabsTrigger
              key={tab}
              value={tab}
              className="data-[state=active]:bg-[#1A3A6B] data-[state=active]:text-white data-[state=active]:shadow-sm rounded-md text-sm font-medium transition-all capitalize"
            >
              {tab === "str" ? "STR Report"
                : tab === "network" ? "Network"
                : tab === "trace" ? "Investigation Trace"
                : tab === "audit" ? "Audit Trail"
                : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview" className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* FATF */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">FATF Typology Mapping</CardTitle>
                <CardDescription>Detected regulatory typologies</CardDescription>
              </CardHeader>
              <CardContent>
                {fatfTypology.length === 0 ? (
                  <p className="text-sm text-slate-400">No typologies detected</p>
                ) : (
                  <div className="space-y-2.5">
                    {fatfTypology.map((typology: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-2.5 p-3 rounded border"
                           style={{ background: "#FDECEA", borderColor: "#F5C6C2" }}>
                        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: "#C0392B" }} />
                        <p className="text-sm font-medium" style={{ color: "#7B241C" }}>{typology}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Sub-cases */}
            <SubCasesPanel subCases={subCases} onOpenAccount={handleOpenAccount} />
          </div>

          {/* SHAP */}
          <ShapPanel shapValues={shapValues} />

          {/* Transaction summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Transaction Summary</CardTitle>
              <CardDescription>{suspiciousTxns.length} suspicious transactions identified</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Total Amount</p>
                  <p className="text-2xl font-bold text-slate-900">
                    ₹{suspiciousTxns.reduce((s: number, t: any) => s + (t.amount ?? 0), 0).toLocaleString("en-IN")}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Time Period</p>
                  <p className="text-xl font-bold text-slate-900">{timePeriodDays} days</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Connected Accounts</p>
                  <p className="text-xl font-bold text-slate-900">{networkAnalysis.nodeCount ?? 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evidence">
          <EvidencePanel evidence={evidence} watchlistHits={watchlistHits} />
        </TabsContent>
        <TabsContent value="network">
          <NetworkGraph networkData={networkAnalysis} accountName={accountName} />
        </TabsContent>
        <TabsContent value="regulatory">
          <RegulatoryPanel regulatory={regulatory} />
        </TabsContent>
        <TabsContent value="trace">
          <AgentTracePanel agentLog={agentLog} confidenceScores={confidenceScores} />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTrailPanel caseId={caseId!} />
        </TabsContent>
        <TabsContent value="transactions">
          <TransactionTimeline transactions={suspiciousTxns} />
        </TabsContent>
        <TabsContent value="str">
          <STRReport narrative={strNarrative} caseData={caseData} agentLog={agentLog} explanation={explanation} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
