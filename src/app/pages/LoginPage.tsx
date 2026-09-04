import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Shield, Lock, Mail, AlertCircle, Fingerprint, Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { beginLogin, checkLoginChallenge } = useAuth();
  const navigate    = useNavigate();
  const [email,     setEmail]    = useState("admin@finguard.ai");
  const [password,  setPassword] = useState("Admin@1234");
  const [error,     setError]    = useState("");
  const [loading,   setLoading]  = useState(false);
  const [challenge, setChallenge] = useState<any>(null);

  useEffect(() => {
    if (!challenge?.challengeId || !challenge?.challengeToken) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await checkLoginChallenge(challenge.challengeId, challenge.challengeToken);
        if (cancelled) return;
        setChallenge(next);
        if (next.accessToken) { navigate("/"); return; }
        if (["failed", "timeout", "hardware_error"].includes(next.status)) {
          setError(next.message ?? "Biometric verification was not completed.");
          setLoading(false);
          return;
        }
        timer = window.setTimeout(poll, 900);
      } catch (err: any) {
        if (!cancelled) { setError(err.message ?? "Unable to read biometric verification status."); setLoading(false); }
      }
    };
    void poll();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [challenge?.challengeId, checkLoginChallenge, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      setChallenge(await beginLogin(email, password));
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "linear-gradient(135deg, #0d1f3c 0%, #1a3a6b 60%, #0d1f3c 100%)" }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
               style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)" }}>
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">FinGuard AI</h1>
          <p className="text-sm mt-1" style={{ color: "#93B4D4" }}>
            Secure Investigator Access
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-8 shadow-2xl"
             style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", backdropFilter: "blur(12px)" }}>
          {challenge && error && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-sm mb-5"
                 style={{ background: "rgba(192,57,43,0.2)", color: "#F1948A", border: "1px solid rgba(192,57,43,0.4)" }}>
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
          {!challenge ? <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg text-sm"
                   style={{ background: "rgba(192,57,43,0.2)", color: "#F1948A", border: "1px solid rgba(192,57,43,0.4)" }}>
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                     style={{ color: "#93B4D4" }}>
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                      style={{ color: "#93B4D4" }} />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm text-white outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.07)",
                    border: "1px solid rgba(255,255,255,0.15)",
                  }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
                     style={{ color: "#93B4D4" }}>
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                      style={{ color: "#93B4D4" }} />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm text-white outline-none"
                  style={{
                    background: "rgba(255,255,255,0.07)",
                    border: "1px solid rgba(255,255,255,0.15)",
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ background: "#1A7A4A" }}
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form> : (
            <div className="text-center py-4">
              <Fingerprint className="w-10 h-10 text-white mx-auto mb-4" />
              <h2 className="text-lg font-semibold text-white">Fingerprint Verification</h2>
              <p className="text-sm mt-2" style={{ color: "#93B4D4" }}>
                {challenge.message ?? "Place your registered finger on the local sensor."}
              </p>
              <div className="flex justify-center gap-2 mt-5 text-xs" style={{ color: "#93B4D4" }}>
                <Loader2 className="w-4 h-4 animate-spin" /> Waiting for fingerprint…
              </div>
              {error && <button type="button" onClick={() => { setChallenge(null); setError(""); setLoading(false); }} className="w-full mt-6 py-2.5 rounded-lg text-sm font-semibold text-white" style={{ background: "#1A7A4A" }}>Try Again</button>}
            </div>
          )}

          <p className="text-center text-xs mt-6" style={{ color: "#93B4D4" }}>
            Demo credentials pre-filled above
          </p>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: "#4A6A9B" }}>
          PMLA 2002 &nbsp;·&nbsp; FIU-IND Compliant &nbsp;·&nbsp; FinGuard AI v2.0
        </p>
      </div>
    </div>
  );
}
