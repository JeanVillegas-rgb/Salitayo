import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { verifyEmail, resendVerification } from "../services/api";

export default function VerifyEmail() {
  const { token } = useParams();

  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendError, setResendError] = useState("");

  useEffect(() => {
    if (!token || token === "resend") {
      setStatus("error");
      setMessage("Enter your email below to resend the verification link.");
      return;
    }

    verifyEmail(token)
      .then((res) => {
        setStatus("success");
        setMessage(res.data.message);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(
          err.response?.data?.error ||
            "Verification failed or link has expired."
        );
      });
  }, [token]);

  const handleResend = async () => {
    if (!email) {
      setResendError("Please enter your email address.");
      return;
    }

    if (!/\S+@\S+\.\S+/.test(email)) {
      setResendError("Enter a valid email.");
      return;
    }

    setResendError("");
    setResending(true);

    try {
      await resendVerification(email);
      setResent(true);
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        "Failed to resend. Check your email address.";
      setResendError(msg);
    } finally {
      setResending(false);
    }
  };

  // ── Loading ─────────────────────────────────────────────
  if (status === "loading") {
    return (
      <div
        className="salita-root"
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div className="card" style={{ maxWidth: 380, textAlign: "center" }}>
          <div
            className="status-icon loading"
            style={{ margin: "0 auto 1.5rem" }}
          >
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--muted)"
              strokeWidth="1.8"
              strokeLinecap="round"
            >
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          </div>
          <div className="card-title">
            Verifying<i>...</i>
          </div>
          <div className="card-sub">
            Just a moment while we confirm your email.
          </div>
        </div>
      </div>
    );
  }

  // ── Success ─────────────────────────────────────────────
  if (status === "success") {
    return (
      <div
        className="salita-root"
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div className="card" style={{ maxWidth: 380, textAlign: "center" }}>
          <div
            className="status-icon success"
            style={{ margin: "0 auto 1.5rem" }}
          >
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#5C6E42"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>

          <div className="eyebrow">All done</div>
          <div className="card-title">
            Email verified<i>!</i>
          </div>
          <div className="card-sub" style={{ marginBottom: "1.5rem" }}>
            {message}
          </div>

          <a href="/login" className="btn-primary">
            Go to login
          </a>
        </div>
      </div>
    );
  }

  // ── Error / Resend ─────────────────────────────────────
  return (
    <div
      className="salita-root"
      style={{ alignItems: "center", justifyContent: "center" }}
    >
      <div className="card" style={{ maxWidth: 400, textAlign: "center" }}>
        <div
          className="status-icon error"
          style={{ margin: "0 auto 1.5rem" }}
        >
          <svg
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--error)"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        {!resent ? (
          <>
            <div className="eyebrow">Verification failed</div>
            <div className="card-title">
              Link expired<i>.</i>
            </div>
            <div className="card-sub" style={{ marginBottom: "1.25rem" }}>
              {message}
            </div>

            <div
              className="field"
              style={{ textAlign: "left", marginBottom: "0.75rem" }}
            >
              <label className="flabel">Your email</label>
              <input
                className={`finput ${resendError ? "finput-error" : ""}`}
                type="email"
                placeholder="you@email.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setResendError("");
                }}
                onKeyDown={(e) => e.key === "Enter" && handleResend()}
              />
              {resendError && (
                <span className="error-msg">{resendError}</span>
              )}
            </div>

            <button
              className="btn-primary"
              onClick={handleResend}
              disabled={resending}
            >
              {resending ? "Resending..." : "Resend verification email"}
            </button>
          </>
        ) : (
          <>
            <div className="eyebrow" style={{ color: "var(--fern)" }}>
              Email sent
            </div>
            <div className="card-title">
              Check your inbox<i>.</i>
            </div>
            <div className="card-sub" style={{ marginBottom: "1.5rem" }}>
              A new verification link is on its way to{" "}
              <strong style={{ color: "var(--moss)" }}>{email}</strong>.
            </div>
          </>
        )}

        <a
          href="/signup"
          className="link"
          style={{ display: "block", marginTop: "1.25rem", fontSize: "0.85rem" }}
        >
          Back to sign up
        </a>
      </div>
    </div>
  );
}