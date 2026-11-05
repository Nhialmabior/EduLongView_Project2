import { useState } from "react";
import { api, setToken } from "./api";

export function LoginScreen({ onDone }: { onDone: (u: any) => void }) {
  const resetToken = new URLSearchParams(window.location.hash.slice(1)).get("reset") || "";
  const [mode, setMode] = useState(resetToken ? "reset" : "login");
  const [email, setEmail] = useState(""), [password, setPassword] = useState(""), [again, setAgain] = useState("");
  const [err, setErr] = useState(""), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<any>) => { setBusy(true); setErr(""); setMsg(""); try { await fn(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const login = () => run(async () => { const r = await api("/auth/login", { method: "POST", body: { email, password } }); setToken(r.token); onDone(r.user); });
  const forgot = () => run(async () => { const r = await api("/auth/forgot", { method: "POST", body: { email } }); setMsg(r.message); });
  const reset = () => run(async () => {
    if (password !== again) throw new Error("The two passwords do not match.");
    await api("/auth/reset", { method: "POST", body: { token: resetToken, password } });
    window.history.replaceState(null, "", window.location.pathname);
    setPassword(""); setAgain(""); setMode("login"); setMsg("Password changed. Sign in with your new password.");
  });
  const enter = (fn: () => void) => (e: any) => e.key === "Enter" && fn();
  return (
    <main style={{ maxWidth: 420 }}>
      <h1>EduLongView</h1>
      <p className="muted">See each learner's progress across terms, and keep teachers in charge of what goes on the record.</p>
      <div className="card">
        {mode === "login" && <>
          <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="username" /></label>
          <label>Password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" onKeyDown={enter(login)} /></label>
          <button className="btn" onClick={login} disabled={busy}>{busy ? "Signing in" : "Sign in"}</button>{" "}
          <button className="linkbtn" style={{ color: "var(--accent)" }} onClick={() => { setMode("forgot"); setErr(""); setMsg(""); }}>Forgot password?</button></>}
        {mode === "forgot" && <>
          <h2>Reset your password</h2><p className="muted">Enter your email and we will send you a link that works for 30 minutes.</p>
          <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="username" onKeyDown={enter(forgot)} /></label>
          <button className="btn" onClick={forgot} disabled={busy || !email}>{busy ? "Sending" : "Send reset link"}</button>{" "}
          <button className="linkbtn" style={{ color: "var(--accent)" }} onClick={() => { setMode("login"); setErr(""); setMsg(""); }}>Back to sign in</button></>}
        {mode === "reset" && <>
          <h2>Choose a new password</h2><p className="muted">Use at least 10 characters.</p>
          <label>New password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="new-password" /></label>
          <label>Repeat new password<input value={again} onChange={(e) => setAgain(e.target.value)} type="password" autoComplete="new-password" onKeyDown={enter(reset)} /></label>
          <button className="btn" onClick={reset} disabled={busy}>{busy ? "Saving" : "Save new password"}</button></>}
        {msg && <p role="status">{msg}</p>}{err && <p className="err" role="alert">{err}</p>}
      </div>
    </main>
  );
}