import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { login } from "../services/api";

const initialForm = { email: "", password: "" };

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const set = (field, value) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: "" }));
  };

  const validate = () => {
    const e = {};
    if (!form.email)
      e.email = "Email is required.";
    else if (!/\S+@\S+\.\S+/.test(form.email))
      e.email = "Enter a valid email.";
    if (!form.password)
      e.password = "Password is required.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      const data = await login(form);
      console.log("login response:", data);
      const role = data.user?.role;
      console.log("role:", role); 

      if (role === "STUDENT") navigate("/home");
      else if (role === "PROFESSOR") navigate("/teacher");
      else navigate("/home");

    } catch (err) {
      if (err.response?.data) {
        const msg =
          err.response.data.non_field_errors?.[0] ||
          "Invalid email or password.";
        setErrors({ password: msg });
      } else {
        setErrors({ password: "Connection failed. Is Django running?" });
      }
    } finally {
      setLoading(false);
    }
  };

  if (localStorage.getItem("token")) {
  return <Navigate to="/home" replace />;
}

  return (
    <div className="salita-root">
      <div className="left-panel">
        <div className="aside-content">
          <div className="aside-logo">SALIT<em>A</em>yo</div>
          <div className="aside-heading">Welcome<br />back<i>.</i></div>
          <div className="aside-sub">
            Pick up right where you left off. Your words are waiting.
          </div>
          <div className="aside-pills">
            <div className="aside-pill"><span className="pill-dot" />Speech accuracy tracking</div>
            <div className="aside-pill"><span className="pill-dot" />Personalised flashcards</div>
            <div className="aside-pill"><span className="pill-dot" />Progress over time</div>
          </div>
        </div>
      </div>

      <div className="right-panel">
        <div className="card">
          <div className="eyebrow">Log in</div>
          <div className="card-title">Good to see you<i>.</i></div>
          <div className="card-sub">Enter your credentials to continue.</div>

          <div className="form">
            <Field label="Email" error={errors.email}>
              <input
                className={`finput ${errors.email ? "finput-error" : ""}`}
                type="email"
                placeholder="you@email.com"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              />
            </Field>

            <Field label="Password" error={errors.password}>
              <input
                className={`finput ${errors.password ? "finput-error" : ""}`}
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              />
            </Field>

            <button
              className="btn-primary"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? "Logging in..." : "Log in"}
            </button>
          </div>

          <div className="or-line">or</div>

          <p className="footer-text">
            No account yet?{" "}
            <a href="/signup" className="link">Sign up free</a>
          </p>
          <p className="footer-text" style={{ marginTop: "0.4rem" }}>
            Didn't get the email?{" "}
            <a href="/verify-email/resend" className="link">Resend verification</a>
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, error, children }) {
  return (
    <div className="field">
      <label className="flabel">{label}</label>
      {children}
      {error && <span className="error-msg">{error}</span>}
    </div>
  );
}