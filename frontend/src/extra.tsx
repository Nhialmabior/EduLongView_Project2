import { useEffect, useState } from "react";
import { api, download } from "./api";
const canWrite = (role: string) => role === "teacher" || role === "school_admin";
const today = () => new Date().toISOString().slice(0, 10);

export function Downloads({ id }: { id: number }) {
  const [err, setErr] = useState("");
  const get = (ext: string) => download(`/reports/learner/${id}.${ext}`, `learner-${id}-report.${ext}`).catch((e) => setErr(e.message));
  return (
    <div className="card"><h2>Reports</h2>
      <div className="row"><button className="btn alt" onClick={() => get("pdf")}>Download PDF</button><button className="btn alt" onClick={() => get("xlsx")}>Download Excel</button></div>
      {err && <p className="err" role="alert">{err}</p>}
      <p className="muted">Reports include only teacher-approved profile text, never unreviewed drafts.</p>
    </div>
  );
}

export function Attendance({ id, role }: { id: number; role: string }) {
  const [a, setA] = useState<any>(null), [day, setDay] = useState(today()), [status, setStatus] = useState("present"), [err, setErr] = useState("");
  const load = () => api(`/learners/${id}/attendance`).then(setA).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]);
  const save = async () => { setErr(""); try { setA(await api(`/learners/${id}/attendance`, { method: "PUT", body: { day, status } })); } catch (e: any) { setErr(e.message); } };
  return (
    <div className="card"><h2>Attendance</h2>
      {!a ? <p>Loading attendance…</p> : a.total === 0 ? <p className="muted">No attendance recorded yet.</p> : <>
        <p><b>{a.rate ?? "—"}{a.rate != null && "%"}</b> attended across {a.total} recorded days: {a.present} present, {a.late} late, {a.absent} absent, {a.excused} excused.</p>
        {a.flag && <div className="flag">{a.flag}</div>}
        <details><summary>Latest records</summary><ul>{a.recent.map((r: any) => <li key={r.day}>{r.day}: {r.status}</li>)}</ul></details></>}
      {canWrite(role) && <div className="row" style={{ alignItems: "end" }}>
        <label>Date<input type="date" value={day} max={today()} onChange={(e) => setDay(e.target.value)} /></label>
        <label>Status<select value={status} onChange={(e) => setStatus(e.target.value)}>{["present", "late", "absent", "excused"].map((s) => <option key={s}>{s}</option>)}</select></label>
        <button className="btn" onClick={save} style={{ marginBottom: ".8rem" }}>Save attendance</button></div>}
      {err && <p className="err" role="alert">{err}</p>}
    </div>
  );
}

export function Plans({ id, role }: { id: number; role: string }) {
  const [ps, setPs] = useState<any[] | null>(null), [f, setF] = useState({ title: "", goal: "", follow_up: "" }), [err, setErr] = useState("");
  const [n, setN] = useState<Record<number, any>>({}), [out, setOut] = useState<Record<number, string>>({});
  const load = () => api(`/learners/${id}/plans`).then(setPs).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]);
  const run = async (fn: () => Promise<any>) => { setErr(""); try { await fn(); await load(); } catch (e: any) { setErr(e.message); } };
  const w = canWrite(role);
  return (
    <div className="card"><h2>Support plans</h2>
      {!ps ? <p>Loading plans…</p> : ps.length === 0 ? <p className="muted">No support plans yet.</p> : ps.map((p) => (
        <div key={p.id} style={{ borderTop: "1px solid var(--line)", paddingTop: ".6rem", marginTop: ".6rem" }}>
          <h3>{p.title} <span className={"badge" + (p.status === "open" ? " warn" : "")}>{p.status}</span></h3>
          {p.goal && <p>{p.goal}</p>}{p.follow_up && <p className="muted">Follow-up date: {p.follow_up}</p>}
          <ul>{p.notes.map((x: any, i: number) => <li key={i}><span className="badge">{x.kind}</span> {x.text} <span className="muted">{x.at}</span></li>)}</ul>
          {p.outcome && <p><b>Outcome:</b> {p.outcome}</p>}
          {w && p.status === "open" && <>
            <div className="row" style={{ alignItems: "end" }}>
              <label>Note type<select value={n[p.id]?.kind || "observation"} onChange={(e) => setN({ ...n, [p.id]: { ...n[p.id], kind: e.target.value } })}><option>observation</option><option>interpretation</option></select></label>
              <label style={{ flex: 1 }}>Note<input value={n[p.id]?.text || ""} onChange={(e) => setN({ ...n, [p.id]: { ...n[p.id], text: e.target.value } })} placeholder="Observations are facts; interpretations are your judgement" /></label>
              <button className="btn alt" style={{ marginBottom: ".8rem" }} onClick={() => run(async () => { await api(`/plans/${p.id}/notes`, { method: "POST", body: { kind: n[p.id]?.kind || "observation", text: n[p.id]?.text || "" } }); setN({ ...n, [p.id]: {} }); })}>Add note</button></div>
            <div className="row" style={{ alignItems: "end" }}>
              <label style={{ flex: 1 }}>Outcome<input value={out[p.id] || ""} onChange={(e) => setOut({ ...out, [p.id]: e.target.value })} placeholder="What happened after the support?" /></label>
              <button className="btn" style={{ marginBottom: ".8rem" }} onClick={() => run(() => api(`/plans/${p.id}/close`, { method: "POST", body: { outcome: out[p.id] || "" } }))}>Close plan</button></div></>}
        </div>))}
      {w && <div style={{ borderTop: "1px solid var(--line)", marginTop: "1rem", paddingTop: ".8rem" }}><h3>New plan</h3>
        <label>Title<input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
        <label>Goal<input value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value })} /></label>
        <label>Follow-up date<input type="date" value={f.follow_up} onChange={(e) => setF({ ...f, follow_up: e.target.value })} /></label>
        <button className="btn" onClick={() => run(async () => { await api(`/learners/${id}/plans`, { method: "POST", body: { title: f.title, goal: f.goal || null, follow_up: f.follow_up || null } }); setF({ title: "", goal: "", follow_up: "" }); })}>Create plan</button></div>}
      {err && <p className="err" role="alert">{err}</p>}
    </div>
  );
}

export function Admin() {
  const [users, setUsers] = useState<any[] | null>(null), [log, setLog] = useState<any[]>([]), [err, setErr] = useState(""), [msg, setMsg] = useState("");
  const [f, setF] = useState({ name: "", email: "", role: "teacher", password: "" });
  const load = () => Promise.all([api("/users"), api("/audit")]).then(([u, a]) => { setUsers(u); setLog(a); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const create = async () => { setErr(""); setMsg(""); try { await api("/users", { method: "POST", body: f }); setMsg("User created."); setF({ name: "", email: "", role: "teacher", password: "" }); load(); } catch (e: any) { setErr(e.message); } };
  const reset = async (u: any) => { const p = window.prompt(`New password for ${u.name} (at least 10 characters)`); if (!p) return; setErr(""); try { await api(`/users/${u.id}/reset-password`, { method: "POST", body: { password: p } }); setMsg("Password reset."); } catch (e: any) { setErr(e.message); } };
  return (
    <>
      <h1>Administration</h1>{msg && <p role="status">{msg}</p>}{err && <p className="err" role="alert">{err}</p>}
      <div className="card"><h2>Staff accounts</h2>
        {!users ? <p>Loading users…</p> : <table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th /></tr></thead><tbody>
          {users.map((u) => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td><button className="btn alt" onClick={() => reset(u)}>Reset password</button></td></tr>)}</tbody></table>}
        <h3 style={{ marginTop: "1rem" }}>Add a user</h3>
        <label>Name<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label>Email<input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        <label>Role<select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option>teacher</option><option>reviewer</option><option>school_admin</option></select></label>
        <label>Temporary password (10+ characters)<input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" /></label>
        <button className="btn" onClick={create}>Create user</button></div>
      <div className="card"><h2>Recent activity</h2>
        {log.length === 0 ? <p className="muted">No activity yet.</p> : <table><thead><tr><th>When</th><th>Action</th><th>Detail</th></tr></thead><tbody>
          {log.map((a, i) => <tr key={i}><td>{a.at.slice(0, 16)}</td><td>{a.action}</td><td>{a.detail}</td></tr>)}</tbody></table>}</div>
    </>
  );
}
