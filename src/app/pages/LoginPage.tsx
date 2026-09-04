import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import {
  AlertCircle,
  CheckCircle2,
  Fingerprint,
  Loader2,
  Lock,
  Mail,
  Shield,
  XCircle,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const terminalStates = new Set([
  "failed",
  "timeout",
  "hardware_error",
]);

export function LoginPage() {
  const { beginLogin, checkLoginChallenge } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("admin@finguard.ai");
  const [password, setPassword] = useState("Admin@1234");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [challenge, setChallenge] = useState<any>(null);

  /*
   * Support BOTH:
   *   challengeId
   * and
   *   challenge_id
   *
   * The backend currently returns challenge_id.
   * The API client normally converts it to challengeId.
   */
  const challengeId =
    challenge?.challengeId ??
    challenge?.challenge_id ??
    null;

  // ─────────────────────────────────────────────────────────────────────────
  // Biometric challenge polling
  // ─────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    console.log(
      "🔄 BIOMETRIC POLL EFFECT:",
      challenge,
    );

    console.log(
      "🔑 RESOLVED CHALLENGE ID:",
      challengeId,
    );

    if (!challengeId) {
      console.log(
        "⛔ POLLING NOT STARTED — no challenge ID",
      );
      return;
    }

    console.log(
      "✅ STARTING BIOMETRIC POLLING FOR:",
      challengeId,
    );

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        console.log(
          "📡 POLLING BIOMETRIC CHALLENGE:",
          challengeId,
        );

        const next =
          await checkLoginChallenge(
            challengeId,
          );

        console.log(
          "📥 BIOMETRIC CHALLENGE RESPONSE:",
          next,
        );

        if (cancelled) {
          return;
        }

        setChallenge(next);

        /*
         * Successful biometric verification causes
         * the backend to return access_token.
         */
        if (next?.accessToken) {
          console.log(
            "🎉 BIOMETRIC LOGIN SUCCESS — navigating to dashboard",
          );

          navigate("/");
          return;
        }

        /*
         * Handle snake_case too, just in case the API
         * response was not normalized.
         */
        if (next?.access_token) {
          console.log(
            "🎉 BIOMETRIC LOGIN SUCCESS — snake_case token received",
          );

          navigate("/");
          return;
        }

        if (
          terminalStates.has(
            next?.status,
          )
        ) {
          console.log(
            "❌ BIOMETRIC LOGIN FAILED:",
            next?.status,
            next?.message,
          );

          setError(
            next?.message ??
              "Biometric verification was not completed.",
          );

          setLoading(false);
          return;
        }

        /*
         * Continue polling while the challenge is pending,
         * finger_required, or verifying.
         */
        timer = window.setTimeout(
          poll,
          900,
        );
      } catch (err: any) {
        console.error(
          "❌ BIOMETRIC POLLING ERROR:",
          err,
        );

        if (!cancelled) {
          setError(
            err?.message ??
              "Unable to read biometric verification status.",
          );

          setLoading(false);
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;

      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [
    challengeId,
    checkLoginChallenge,
    navigate,
  ]);

  // ─────────────────────────────────────────────────────────────────────────
  // Start login
  // ─────────────────────────────────────────────────────────────────────────

  async function handleSubmit(
    event: React.FormEvent,
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      console.log(
        "🔐 STARTING LOGIN:",
        email,
      );

      const result =
        await beginLogin(
          email,
          password,
        );

      console.log(
        "📥 LOGIN RESPONSE:",
        result,
      );

      console.log(
        "🔑 challengeId:",
        result?.challengeId,
      );

      console.log(
        "🔑 challenge_id:",
        result?.challenge_id,
      );

      setChallenge(result);
    } catch (err: any) {
      console.error(
        "❌ LOGIN START ERROR:",
        err,
      );

      setError(
        err?.message ??
          "Login could not start.",
      );

      setLoading(false);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // UI state
  // ─────────────────────────────────────────────────────────────────────────

  const isBiometric =
    Boolean(challenge);

  const failed =
    terminalStates.has(
      challenge?.status,
    );

  const verified =
    challenge?.status ===
    "success";

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{
        background:
          "linear-gradient(135deg, #0d1f3c 0%, #1a3a6b 60%, #0d1f3c 100%)",
      }}
    >
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{
              background:
                "rgba(255,255,255,0.1)",
              border:
                "1px solid rgba(255,255,255,0.2)",
            }}
          >
            <Shield className="w-8 h-8 text-white" />
          </div>

          <h1 className="text-2xl font-bold text-white tracking-tight">
            FinGuard AI
          </h1>

          <p
            className="text-sm mt-1"
            style={{
              color: "#93B4D4",
            }}
          >
            Secure Investigator Access
          </p>
        </div>

        <div
          className="rounded-2xl p-8 shadow-2xl"
          style={{
            background:
              "rgba(255,255,255,0.05)",
            border:
              "1px solid rgba(255,255,255,0.12)",
            backdropFilter:
              "blur(12px)",
          }}
        >
          {error && (
            <div
              className="flex items-center gap-2 p-3 rounded-lg text-sm mb-5"
              style={{
                background:
                  "rgba(192,57,43,0.2)",
                color: "#F1948A",
                border:
                  "1px solid rgba(192,57,43,0.4)",
              }}
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          {!isBiometric ? (
            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >
              <div>
                <label
                  className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                  style={{
                    color: "#93B4D4",
                  }}
                >
                  Email
                </label>

                <div className="relative">
                  <Mail
                    className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                    style={{
                      color: "#93B4D4",
                    }}
                  />

                  <input
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(
                        event.target.value,
                      )
                    }
                    required
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm text-white outline-none"
                    style={{
                      background:
                        "rgba(255,255,255,0.07)",
                      border:
                        "1px solid rgba(255,255,255,0.15)",
                    }}
                  />
                </div>
              </div>

              <div>
                <label
                  className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                  style={{
                    color: "#93B4D4",
                  }}
                >
                  Password
                </label>

                <div className="relative">
                  <Lock
                    className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                    style={{
                      color: "#93B4D4",
                    }}
                  />

                  <input
                    type="password"
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value,
                      )
                    }
                    required
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm text-white outline-none"
                    style={{
                      background:
                        "rgba(255,255,255,0.07)",
                      border:
                        "1px solid rgba(255,255,255,0.15)",
                    }}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60"
                style={{
                  background:
                    "#1A7A4A",
                }}
              >
                {loading
                  ? "Checking credentials…"
                  : "Continue"}
              </button>
            </form>
          ) : (
            <div className="text-center py-2">
              <div
                className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{
                  background: verified
                    ? "rgba(26,122,74,0.22)"
                    : failed
                    ? "rgba(192,57,43,0.22)"
                    : "rgba(147,180,212,0.18)",
                }}
              >
                {verified ? (
                  <CheckCircle2 className="h-8 w-8 text-green-300" />
                ) : failed ? (
                  <XCircle className="h-8 w-8 text-red-300" />
                ) : challenge?.status ===
                  "verifying" ? (
                  <Loader2 className="h-8 w-8 animate-spin text-blue-200" />
                ) : (
                  <Fingerprint className="h-8 w-8 text-blue-200" />
                )}
              </div>

              <h2 className="text-lg font-semibold text-white">
                {verified
                  ? "Biometric Access Granted"
                  : "Biometric Verification Required"}
              </h2>

              <p
                className="mx-auto mt-2 max-w-xs text-sm leading-relaxed"
                style={{
                  color: "#B9CCE2",
                }}
              >
                {challenge?.message ??
                  "Place your registered finger on the local sensor."}
              </p>

              {!failed &&
                !verified && (
                  <div
                    className="mt-5 flex items-center justify-center gap-2 text-xs"
                    style={{
                      color: "#93B4D4",
                    }}
                  >
                    <span className="h-2 w-2 animate-pulse rounded-full bg-green-400" />
                    Local fingerprint sensor active
                  </div>
                )}

              {failed && (
                <button
                  type="button"
                  onClick={() => {
                    setChallenge(null);
                    setError("");
                    setLoading(false);
                  }}
                  className="mt-5 rounded-lg border border-white/20 px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
                >
                  Try again
                </button>
              )}
            </div>
          )}

          {!isBiometric && (
            <p
              className="text-center text-xs mt-6"
              style={{
                color: "#93B4D4",
              }}
            >
              Password authentication is
              followed by local fingerprint
              verification.
            </p>
          )}
        </div>

        <p
          className="text-center text-xs mt-6"
          style={{
            color: "#4A6A9B",
          }}
        >
          PMLA 2002 · FIU-IND Compliant ·
          Hardware-backed access
        </p>
      </div>
    </div>
  );
}