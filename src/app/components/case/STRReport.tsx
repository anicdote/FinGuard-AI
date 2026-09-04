import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../ui/card";
import {
  FileText,
  Download,
  Printer,
  CheckCircle,
  Clock,
  Fingerprint,
  Loader2,
  Send,
} from "lucide-react";

interface STRReportProps {
  narrative: string;
  caseData: any;
  agentLog?: any[];
  explanation?: string;
}

const BASE_URL = "http://localhost:8000";

function completedAgentCount(entries: any[] = []) {
  return new Set(
    entries
      .map((entry) =>
        String(entry?.agent ?? "")
          .match(/^(?:Planner→)?Agent([1-6])(?:_|$)/)?.[1]
      )
      .filter(Boolean)
  ).size;
}

function reportDuration(entries: any[] = []) {
  const times = entries
    .map((entry) =>
      new Date(entry?.timestamp).getTime()
    )
    .filter(Number.isFinite);

  if (times.length < 2) return null;

  return (
    (Math.max(...times) -
      Math.min(...times)) /
    1000
  );
}

/*
 * Read the existing FinGuard JWT from the same
 * localStorage location used by the authentication
 * system.
 *
 * IMPORTANT:
 * This does NOT modify login or authentication.
 * It only allows the already-authenticated user
 * to authorize the STR request.
 */
function getAccessToken(): string | null {
  return localStorage.getItem("fg_access");
}

/*
 * Small STR-only API helper.
 *
 * We intentionally keep this inside STRReport rather
 * than changing the shared api.ts/authentication layer.
 *
 * That means the working biometric login flow remains
 * completely untouched.
 */
async function strRequest(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
  };

  if (token) {
    headers["Authorization"] =
      `Bearer ${token}`;
  }

  const response = await fetch(
    `${BASE_URL}${path}`,
    {
      ...options,
      headers,
    }
  );

  if (!response.ok) {
    let message =
      `Request failed (${response.status})`;

    try {
      const data = await response.json();

      if (typeof data?.detail === "string") {
        message = data.detail;
      } else if (
        Array.isArray(data?.detail)
      ) {
        message = data.detail
          .map(
            (item: any) =>
              item?.msg ??
              String(item)
          )
          .join(", ");
      }
    } catch {
      // Keep the fallback message.
    }

    throw new Error(message);
  }

  return response;
}

async function startStrBiometricChallenge(
  caseId: string
) {
  const response =
    await strRequest(
      `/api/v1/cases/${encodeURIComponent(
        caseId
      )}/str/biometric-challenge`,
      {
        method: "POST",
      }
    );

  const data = await response.json();

  return {
    ...data,

    // Normalize backend snake_case
    // for the React component.
    challengeId:
      data.challengeId ??
      data.challenge_id,

    status: data.status,
    message: data.message,
    expiresAt:
      data.expiresAt ??
      data.expires_at,
  };
}

async function checkStrBiometricChallenge(
  caseId: string,
  challengeId: string
) {
  const response =
    await strRequest(
      `/api/v1/cases/${encodeURIComponent(
        caseId
      )}/str/biometric-challenge/${encodeURIComponent(
        challengeId
      )}`
    );

  const data = await response.json();

  return {
    ...data,

    challengeId:
      data.challengeId ??
      data.challenge_id,

    status: data.status,
    message: data.message,
    expiresAt:
      data.expiresAt ??
      data.expires_at,
  };
}

async function startStrDownloadChallenge(
  caseId: string
) {
  const response =
    await strRequest(
      `/api/v1/cases/${encodeURIComponent(
        caseId
      )}/str/download-challenge`,
      {
        method: "POST",
      }
    );

  const data = await response.json();

  return {
    ...data,

    challengeId:
      data.challengeId ??
      data.challenge_id,

    status: data.status,
    message: data.message,
    expiresAt:
      data.expiresAt ??
      data.expires_at,
  };
}

async function checkStrDownloadChallenge(
  caseId: string,
  challengeId: string
) {
  const response =
    await strRequest(
      `/api/v1/cases/${encodeURIComponent(
        caseId
      )}/str/download-challenge/${encodeURIComponent(
        challengeId
      )}`
    );

  const data = await response.json();

  return {
    ...data,

    challengeId:
      data.challengeId ??
      data.challenge_id,

    status: data.status,
    message: data.message,
    expiresAt:
      data.expiresAt ??
      data.expires_at,
  };
}

async function downloadStr(
  caseId: string,
  challengeId: string
) {
  const response =
    await strRequest(
      `/api/v1/cases/${encodeURIComponent(
        caseId
      )}/str/download?challenge_id=${encodeURIComponent(
        challengeId
      )}`
    );

  const blob =
    await response.blob();

  const disposition =
    response.headers.get(
      "Content-Disposition"
    );

  let filename =
    `STR_${caseId}.txt`;

  const match =
    disposition?.match(
      /filename="?([^"]+)"?/i
    );

  if (match?.[1]) {
    filename = match[1];
  }

  return {
    blob,
    filename,
  };
}

export function STRReport({
  narrative,
  caseData,
  agentLog,
  explanation,
}: STRReportProps) {
  const caseId =
    caseData.id ??
    caseData._id ??
    "—";

  const priority =
    caseData.priority ??
    "medium";

  const riskScore = Number(
    caseData.riskScore ??
      caseData.risk_score ??
      0
  ).toFixed(0);

  const fatfTypes =
    caseData.fatfTypology ??
    caseData.fatf_typology ??
    [];

  const humanReview =
    caseData.humanReview ??
    caseData.human_review ??
    null;

  const reviewRecorded =
    Boolean(
      humanReview &&
        [
          "accepted",
          "overridden",
        ].includes(
          humanReview.status
        )
    );

  const recommendation =
    caseData.recommendation ??
    caseData.investigation
      ?.recommendation ??
    {};

  const strStatus =
    recommendation.strStatus ??
    recommendation.str_status ??
    caseData.strStatus ??
    caseData.str_status;

  const strFilingStatus =
    recommendation.strFilingStatus ??
    recommendation.str_filing_status ??
    caseData.strFilingStatus ??
    caseData.str_filing_status ??
    "not_filed";

  const formatStatus = (
    value: string
  ) =>
    value
      .replaceAll("_", " ")
      .replace(
        /\b\w/g,
        (letter) =>
          letter.toUpperCase()
      );

  const processingTime =
    caseData.processingTime ??
    caseData.processing_time ??
    null;

  const canonicalAccountId =
    caseData.accountId ??
    caseData.account_id;

  const completedAgents =
    completedAgentCount(
      agentLog ??
        caseData.agentLog ??
        caseData.agent_log ??
        []
    );

  const measuredDuration =
    processingTime ??
    reportDuration(
      agentLog ??
        caseData.agentLog ??
        caseData.agent_log ??
        []
    );

  let renderedNarrative =
    narrative ?? "";

  if (explanation) {
    renderedNarrative =
      renderedNarrative.replace(
        /^(DESCRIPTION:\s*\r?\n)(?=\s*[─-]{3,})/m,
        `$1${explanation}\n`
      );
  }

  if (canonicalAccountId) {
    renderedNarrative =
      renderedNarrative.replace(
        /^(Account:\s*).+$/m,
        `$1${canonicalAccountId}`
      );
  }

  if (completedAgents) {
    renderedNarrative =
      renderedNarrative.replace(
        /^(AGENTS RAN:\s*)\d+$/m,
        `$1${completedAgents}`
      );
  }

  const cleanNarrative =
    renderedNarrative
      .replace(
        /\n?APPROVED BY:.*(?:\n|$)/gi,
        ""
      )
      .replace(
        /\n?Biometric verification: pending hardware integration.*(?:\n|$)/gi,
        ""
      )
      .trim();

  // ---------------------------------------------------------------------------
  // STR DOWNLOAD BIOMETRIC STATE
  // ---------------------------------------------------------------------------

  const [
    downloadChallenge,
    setDownloadChallenge,
  ] = useState<any>(null);

  const [
    downloadError,
    setDownloadError,
  ] = useState("");

  const [
    downloading,
    setDownloading,
  ] = useState(false);

  // ---------------------------------------------------------------------------
  // STR SUBMISSION BIOMETRIC STATE
  // ---------------------------------------------------------------------------

  const [
    submitChallenge,
    setSubmitChallenge,
  ] = useState<any>(null);

  const [
    submissionError,
    setSubmissionError,
  ] = useState("");

  const [
    submissionMessage,
    setSubmissionMessage,
  ] = useState("");

  const [
    submitting,
    setSubmitting,
  ] = useState(false);

  // ---------------------------------------------------------------------------
  // DOWNLOAD
  // ---------------------------------------------------------------------------

  const saveDownload = (
    blob: Blob,
    filename: string
  ) => {
    const url =
      URL.createObjectURL(
        blob
      );

    const a =
      document.createElement(
        "a"
      );

    a.href = url;
    a.download = filename;

    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (
      !downloadChallenge?.challengeId
    ) {
      return;
    }

    let cancelled = false;
    let timer:
      | number
      | undefined;

    const poll = async () => {
      try {
        const next =
          await checkStrDownloadChallenge(
            caseId,
            downloadChallenge.challengeId
          );

        if (cancelled) {
          return;
        }

        setDownloadChallenge(
          next
        );

        if (
          next.status ===
          "success"
        ) {
          const file =
            await downloadStr(
              caseId,
              next.challengeId
            );

          if (!cancelled) {
            saveDownload(
              file.blob,
              file.filename
            );

            setDownloadChallenge(
              null
            );

            setDownloading(
              false
            );
          }

          return;
        }

        if (
          [
            "failed",
            "timeout",
            "hardware_error",
          ].includes(
            next.status
          )
        ) {
          setDownloadError(
            next.message ??
              "Biometric verification was not completed."
          );

          setDownloading(
            false
          );

          return;
        }

        timer =
          window.setTimeout(
            poll,
            900
          );
      } catch (err: any) {
        if (!cancelled) {
          setDownloadError(
            err?.message ??
              "Unable to authorize STR download."
          );

          setDownloading(
            false
          );
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;

      if (
        timer !== undefined
      ) {
        window.clearTimeout(
          timer
        );
      }
    };
  }, [
    downloadChallenge?.challengeId,
    caseId,
  ]);

  const handleDownload =
    async () => {
      setDownloadError("");
      setDownloading(true);

      try {
        const result =
          await startStrDownloadChallenge(
            caseId
          );

        setDownloadChallenge(
          result
        );
      } catch (err: any) {
        setDownloadError(
          err?.message ??
            "Could not start biometric authorization."
        );

        setDownloading(false);
      }
    };

  // ---------------------------------------------------------------------------
  // STR SUBMISSION
  // ---------------------------------------------------------------------------

  const handleSubmit =
    async () => {
      setSubmissionError("");
      setSubmissionMessage("");
      setSubmitting(true);

      try {
        const result =
          await startStrBiometricChallenge(
            caseId
          );

        setSubmitChallenge(
          result
        );
      } catch (err: any) {
        setSubmissionError(
          err?.message ??
            "STR biometric authorization could not start."
        );

        setSubmitting(false);
      }
    };

  useEffect(() => {
    if (
      !submitChallenge?.challengeId
    ) {
      return;
    }

    let cancelled = false;
    let timer:
      | number
      | undefined;

    const poll = async () => {
      try {
        const next =
          await checkStrBiometricChallenge(
            caseId,
            submitChallenge.challengeId
          );

        if (cancelled) {
          return;
        }

        setSubmitChallenge(
          next
        );

        if (
          next.status ===
          "success"
        ) {
          setSubmitting(
            false
          );

          setSubmissionMessage(
            next.message ??
              "Fingerprint verified. STR submission authorized."
          );

          return;
        }

        if (
          [
            "failed",
            "timeout",
            "hardware_error",
          ].includes(
            next.status
          )
        ) {
          setSubmitting(
            false
          );

          setSubmissionError(
            next.message ??
              "Fingerprint verification was not completed."
          );

          return;
        }

        timer =
          window.setTimeout(
            poll,
            900
          );
      } catch (err: any) {
        if (!cancelled) {
          setSubmitting(
            false
          );

          setSubmissionError(
            err?.message ??
              "Unable to verify STR biometric authorization."
          );
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;

      if (
        timer !== undefined
      ) {
        window.clearTimeout(
          timer
        );
      }
    };
  }, [
    submitChallenge?.challengeId,
    caseId,
  ]);

  // ---------------------------------------------------------------------------
  // CHECKLIST
  // ---------------------------------------------------------------------------

  const checklist = [
    {
      item: "Subject identification details complete",
      done: true,
    },
    {
      item: "Transaction details with dates and amounts",
      done: true,
    },
    {
      item: "Red flags and suspicious patterns documented",
      done: true,
    },
    {
      item: "FATF typology mapping included",
      done: true,
    },
    {
      item: "Risk assessment and scoring provided",
      done: true,
    },
    {
      item: "Regulatory framework cited (PMLA 2002)",
      done: true,
    },
    {
      item: "Recommendation for action included",
      done: true,
    },
    {
      item: "Compliance officer review pending",
      done: !reviewRecorded,
    },
  ];

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-5">
      {/* Action bar */}
      <Card>
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <h3 className="font-semibold text-slate-900 text-sm">
                Suspicious Transaction Report (STR)
              </h3>

              <p className="text-xs text-slate-500 mt-1">
                STR review:{" "}
                {strStatus
                  ? formatStatus(
                      strStatus
                    )
                  : "Not assessed"}{" "}
                · Filing status:{" "}
                {formatStatus(
                  strFilingStatus
                )}
              </p>

              <p className="text-xs text-slate-500 mt-0.5">
                Generated by FinGuard AI · PMLA 2002 /
                FIU-IND-aligned format
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {/* DOWNLOAD */}
              <button
                type="button"
                onClick={
                  handleDownload
                }
                disabled={
                  downloading
                }
                className="shrink-0 flex items-center gap-1.5 whitespace-nowrap text-xs font-medium px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {downloading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}

                Download
              </button>

              {/* PRINT */}
              <button
                type="button"
                onClick={() =>
                  window.print()
                }
                className="shrink-0 flex items-center gap-1.5 whitespace-nowrap text-xs font-medium px-3 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <Printer className="w-3.5 h-3.5" />
                Print
              </button>

              {/* SUBMIT STR */}
              <button
                type="button"
                onClick={
                  handleSubmit
                }
                disabled={
                  submitting ||
                  submitChallenge?.status ===
                    "pending" ||
                  submitChallenge?.status ===
                    "waiting"
                }
                className="shrink-0 inline-flex items-center justify-center gap-1.5 whitespace-nowrap text-xs font-semibold px-4 py-2 rounded-md transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                style={{
                  background:
                    "#1A3A6B",
                  color:
                    "#FFFFFF",
                  border:
                    "1px solid #1A3A6B",
                }}
              >
                {submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}

                <span>
                  {submitting
                    ? "Verify Fingerprint"
                    : "Submit STR"}
                </span>
              </button>
            </div>
          </div>

          {/* DOWNLOAD STATUS */}
          {(downloadChallenge ||
            downloadError) && (
            <div
              className="mt-3 text-xs rounded border p-3"
              style={{
                background:
                  "#F4F6F9",
                borderColor:
                  "#D5DBE3",
              }}
            >
              {downloadChallenge && (
                <span className="flex items-center gap-2">
                  <Fingerprint className="w-4 h-4" />

                  {downloadChallenge.message ??
                    "Place your registered finger on the local sensor."}
                </span>
              )}

              {downloadError && (
                <span className="text-red-700">
                  {downloadError}
                </span>
              )}
            </div>
          )}

          {/* STR SUBMISSION STATUS */}
          {(submitChallenge ||
            submissionMessage ||
            submissionError) && (
            <div
              className="mt-3 text-xs rounded border p-3"
              style={{
                background:
                  submissionError
                    ? "#FEF2F2"
                    : "#F4F6F9",
                borderColor:
                  submissionError
                    ? "#FECACA"
                    : "#D5DBE3",
              }}
            >
              {submitChallenge &&
                !submissionError &&
                submitChallenge.status !==
                  "success" && (
                  <span className="flex items-center gap-2">
                    <Fingerprint className="w-4 h-4" />

                    {submitChallenge.message ??
                      "Place your registered finger on the local sensor."}
                  </span>
                )}

              {submissionMessage && (
                <span className="flex items-center gap-2 text-green-700 font-medium">
                  <CheckCircle className="w-4 h-4" />
                  {submissionMessage}
                </span>
              )}

              {submissionError && (
                <span className="text-red-700">
                  {submissionError}
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* STR Document */}
      <Card>
        <CardHeader className="border-b border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="p-2 rounded"
                style={{
                  background:
                    "#1A3A6B",
                }}
              >
                <FileText className="w-4 h-4 text-white" />
              </div>

              <div>
                <CardTitle className="text-sm">
                  Suspicious Transaction Report
                </CardTitle>

                <CardDescription>
                  Case ID: {caseId} · Generated:{" "}
                  {new Date().toLocaleDateString(
                    "en-IN"
                  )}
                </CardDescription>
              </div>
            </div>

            <span
              className="text-xs font-medium px-2.5 py-1 rounded border"
              style={{
                background:
                  "#E9F7EF",
                color:
                  "#1A7A4A",
                borderColor:
                  "#A9DFBF",
              }}
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
            <p className="text-sm text-slate-400 text-center py-8">
              No STR narrative available for this case.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Checklist + Metadata */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Compliance Checklist
            </CardTitle>

            <CardDescription>
              PMLA 2002 &amp; FIU-IND requirements
            </CardDescription>
          </CardHeader>

          <CardContent>
            <div className="space-y-2">
              {checklist.map(
                (check, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2.5 rounded border border-slate-100 bg-slate-50"
                  >
                    <span className="text-xs text-slate-700">
                      {check.item}
                    </span>

                    {check.done ? (
                      <span
                        className="flex items-center gap-1 text-xs font-medium"
                        style={{
                          color:
                            "#1A7A4A",
                        }}
                      >
                        <CheckCircle className="w-3 h-3" />
                        Done
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
                        <Clock className="w-3 h-3" />
                        Pending
                      </span>
                    )}
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Report Metadata
            </CardTitle>

            <CardDescription>
              Audit trail and processing info
            </CardDescription>
          </CardHeader>

          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label:
                    "Generated By",
                  value:
                    "FinGuard AI v2.1",
                },
                {
                  label:
                    "Processing Time",
                  value:
                    measuredDuration !=
                    null
                      ? `${Number(
                          measuredDuration
                        ).toFixed(
                          1
                        )}s`
                      : "Not captured",
                },
                {
                  label:
                    "STR Filing",
                  value:
                    formatStatus(
                      strFilingStatus
                    ),
                },
                {
                  label:
                    "Validation",
                  value:
                    "✓ Passed",
                },
                {
                  label:
                    "Characters",
                  value:
                    cleanNarrative.length.toString(),
                },
                {
                  label:
                    "Case Priority",
                  value:
                    priority.toUpperCase(),
                },
                {
                  label:
                    "Risk Score",
                  value: `${riskScore}/100`,
                },
                {
                  label:
                    "Typologies",
                  value:
                    fatfTypes.length.toString(),
                },
                {
                  label:
                    "Version",
                  value:
                    "v2.1",
                },
              ].map(
                ({
                  label,
                  value,
                }) => (
                  <div
                    key={label}
                  >
                    <p className="text-xs text-slate-500">
                      {label}
                    </p>

                    <p className="text-sm font-semibold text-slate-800">
                      {value}
                    </p>
                  </div>
                )
              )}
            </div>

            <div className="mt-4 p-3 rounded border border-amber-200 bg-amber-50">
              <p className="text-xs font-semibold text-amber-800 mb-1">
                Human Review Required
              </p>

              <p className="text-xs text-amber-700">
                This AI-generated STR must be reviewed
                by a compliance officer before
                submission to FIU-IND under PMLA 2002.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}