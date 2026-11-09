import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import { Attendance, Plans, Downloads, Admin } from "./extra";
import { DataPage } from "./data";
import { LoginScreen } from "./auth";

const COLORS = ["#1d6b5a", "#b86e00", "#4338ca", "#a3262b"];

function Chart({ subjects }: { subjects: any[] }) {
  const W = 560, H = 250, P = 38, n = Math.max(...subjects.map((s) => s.points.length), 1);
  const x = (i: number) => P + (n > 1 ? (i * (W - 2 * P)) / (n - 1) : 0);
  const y = (v: number) => H - P - (v / 100) * (H - 2 * P);
  const longest = subjects.find((s) => s.points.length === n);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Scores by subject across terms">
        {[0, 25, 50, 75, 100].map((g) => (<g key={g}><line x1={P} x2={W - P} y1={y(g)} y2={y(g)} stroke="#d5e0dd" /><text x={6} y={y(g) + 4} fontSize="11" fill="#5b6f6b">{g}%</text></g>))}
        {longest?.points.map((p: any, i: number) => (<text key={i} x={x(i)} y={H - 12} fontSize="11" textAnchor="middle" fill="#5b6f6b">{p.term}</text>))}
        {subjects.map((s, si) => (
          <g key={s.subject} stroke={COLORS[si % 4]} fill={COLORS[si % 4]}>
            {s.points.map((p: any, i: number) => i > 0 && p.pct != null && s.points[i - 1].pct != null && (
              <line key={"l" + i} x1={x(i - 1)} y1={y(s.points[i - 1].pct)} x2={x(i)} y2={y(p.pct)} strokeWidth="2" />))}
            {s.points.map((p: any, i: number) => p.pct != null
              ? <circle key={i} cx={x(i)} cy={y(p.pct)} r="4"><title>{s.subject} {p.term}: {p.pct}%</title></circle>
              : <text key={i} x={x(i)} y={H - P + 14} fontSize="13" textAnchor="middle" stroke="none"><title>{s.subject} {p.term}: {p.status} (not counted as zero)</title>×</text>)}
          </g>))}
      </svg>
      <div className="legend">{subjects.map((s, i) => <span key={s.subject}><i style={{ background: COLORS[i % 4] }} />{s.subject}</span>)}<span className="muted">× = no scored result (absent, missing or unassessed)</span></div>
    </>
  );
}

function Login({ onDone }: { onDone: (u: any) => void }) {
  const [email, setEmail] = useState("teacher1@demo.school"), [password, setPassword] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true); setErr("");
    try { const r = await api("/auth/login", { method: "POST", body: { email, password } }); setToken(r.token); onDone(r.user); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <main style={{ maxWidth: 420 }}>
      <h1>EduLongView</h1><p className="muted">See each learner's progress across terms, and keep teachers in charge of what goes on the record.</p>
      <div className="card">
        <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="username" /></label>
        <label>Password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" onKeyDown={(e) => e.key === "Enter" && go()} /></label>
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn" onClick={go} disabled={busy}>{busy ? "Signing in" : "Sign in"}</button>
      </div>
    </main>
  );
}

function Dashboard() {
  const [d, setD] = useState<any>(null), [err, setErr] = useState("");
  useEffect(() => { api("/dashboard").then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!d) return <p>Loading dashboard…</p>;
  return (
    <>
      <h1>Dashboard</h1>
      <div className="stats">
        {[["Learners", d.learners], ["Classes", d.classes], ["Subjects", d.subjects], ["Assessments recorded", d.assessment_completion == null ? "—" : d.assessment_completion + "%"], ["Drafts to review", d.pending_reviews], ["Follow-ups due", d.follow_ups_due], ["Attendance", d.attendance_rate == null ? "—" : d.attendance_rate + "%"]].map(([k, v]) => (
          <div className="card stat" key={k as string}><b>{v}</b><span>{k}</span></div>))}
      </div>
      <div className="card"><h2>Classes</h2>
        {d.class_summaries.length === 0 ? <p className="muted">No classes assigned to you yet.</p> :
          <table><thead><tr><th>Class</th><th>Learners</th><th>Average score</th></tr></thead><tbody>
            {d.class_summaries.map((c: any) => <tr key={c.name}><td>{c.name}</td><td>{c.learners}</td><td>{c.average ?? "—"}{c.average != null && "%"}</td></tr>)}</tbody></table>}
      </div>
    </>
  );
}

function Learners({ open }: { open: (id: number) => void }) {
  const [list, setList] = useState<any[] | null>(null), [q, setQ] = useState(""), [err, setErr] = useState("");
  useEffect(() => { const t = setTimeout(() => api("/learners?search=" + encodeURIComponent(q)).then(setList).catch((e) => setErr(e.message)), 200); return () => clearTimeout(t); }, [q]);
  return (
    <>
      <h1>Learners</h1>
      <label>Search by name<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Start typing a name" /></label>
      {err && <p className="err" role="alert">{err}</p>}
      {!list ? <p>Loading learners…</p> : list.length === 0 ? <p className="muted">No learners match. Try a different name.</p> :
        <div className="card"><table><thead><tr><th>Name</th><th>Class</th><th>Worth a look</th><th /></tr></thead><tbody>
          {list.map((l) => <tr key={l.id}><td>{l.name}</td><td>{l.class_name}</td>
            <td>{l.attention > 0 ? <span className="badge warn">{l.attention} indicator{l.attention > 1 ? "s" : ""}</span> : <span className="muted">None</span>}</td>
            <td><button className="btn alt" onClick={() => open(l.id)}>Open profile</button></td></tr>)}</tbody></table></div>}
    </>
  );
}

function LearnerPage({ id, role, back }: { id: number; role: string; back: () => void }) {
  const [l, setL] = useState<any>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const load = () => api("/learners/" + id).then(setL).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]);
  const draft = async () => { setBusy(true); setErr(""); try { await api(`/learners/${id}/drafts`, { method: "POST" }); await load(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  if (err && !l) return <p className="err" role="alert">{err}</p>;
  if (!l) return <p>Loading profile…</p>;
  const canDraft = role === "teacher" || role === "school_admin";
  return (
    <>
      <button className="btn alt" onClick={back}>Back to learners</button>
      <h1 style={{ marginTop: "1rem" }}>{l.name}</h1><p className="muted">{l.class_name}</p>
      <div className="card"><h2>Progress across terms</h2>
        {l.trends.subjects.length ? <Chart subjects={l.trends.subjects} /> : <p className="muted">No results recorded yet.</p>}
        <details><summary>How these figures are calculated</summary><p>{l.trends.method}</p></details>
      </div>
      <div className="card"><h2>Worth a teacher's attention</h2>
        {l.trends.flags.length ? l.trends.flags.map((f: any, i: number) => <div className="flag" key={i}>{f.text}</div>) : <p className="muted">No indicators raised from the recorded results.</p>}
        <p className="muted">These are prompts for your review, not diagnoses or decisions.</p>
      </div>
      <div className="card"><h2>Official profile</h2>
        {l.profile ? <><pre>{l.profile.content}</pre><p className="muted">Teacher-approved on {l.profile.updated_at.slice(0, 10)}</p></> : <p className="muted">Nothing approved yet. Draft a summary, review it, then approve it to add it here.</p>}
      </div>
      <div className="card"><h2>AI drafts</h2>
        {canDraft && <button className="btn" onClick={draft} disabled={busy}>{busy ? "Drafting…" : "Draft progress summary"}</button>}
        {err && <p className="err" role="alert">{err}</p>}
        {l.drafts.length === 0 ? <p className="muted">No drafts yet.</p> : l.drafts.map((d: any) => (
          <div key={d.id} style={{ marginTop: "1rem" }}><span className="badge">{d.status}</span> <span className="muted">{d.created_at.slice(0, 16)} · {d.provider}</span></div>))}
        <p className="muted">Review pending drafts under Reviews.</p>
      </div>
      <Attendance id={id} role={role} />
      <Plans id={id} role={role} />
      <Downloads id={id} />
    </>
  );
}

function Reviews({ role }: { role: string }) {
  const [list, setList] = useState<any[] | null>(null), [err, setErr] = useState(""), [text, setText] = useState<Record<number, string>>({}), [msg, setMsg] = useState("");
  const load = () => api("/drafts").then(setList).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const act = async (d: any, action: string) => {
    setErr(""); setMsg("");
    try { await api(`/drafts/${d.id}/review`, { method: "POST", body: { action, content: text[d.id] ?? d.content } }); setMsg(action === "approve" ? "Approved and added to the official profile." : action === "reject" ? "Draft rejected." : "Draft kept for revision."); load(); }
    catch (e: any) { setErr(e.message); }
  };
  const can = role === "teacher" || role === "school_admin";
  return (
    <>
      <h1>Reviews</h1>
      {msg && <p role="status">{msg}</p>}{err && <p className="err" role="alert">{err}</p>}
      {!list ? <p>Loading drafts…</p> : list.length === 0 ? <p className="muted">Nothing waiting. Open a learner and choose "Draft progress summary" to start.</p> :
        list.map((d) => (
          <div className="card" key={d.id}>
            <h2>{d.learner_name}</h2>
            <div className="draftbanner">AI draft, not yet reviewed. It becomes part of the record only when you approve it.</div>
            <details><summary>Source evidence used</summary><ul>{d.evidence.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul></details>
            <label>Draft text (edit before approving)<textarea value={text[d.id] ?? d.content} onChange={(e) => setText({ ...text, [d.id]: e.target.value })} readOnly={!can} /></label>
            {can ? <div className="row"><button className="btn" onClick={() => act(d, "approve")}>Approve</button><button className="btn alt" onClick={() => act(d, "revise")}>Request revision</button><button className="btn bad" onClick={() => act(d, "reject")}>Reject</button></div>
              : <p className="muted">Your role can read drafts but not approve them.</p>}
          </div>))}
    </>
  );
}


function ParentPortal() {
  const [children, setChildren] = useState<any[]>([]);
  const [terms, setTerms] = useState<any[]>([]);
  const [childId, setChildId] = useState("");
  const [termId, setTermId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api("/parent/children"), api("/terms")]).then(([cs, ts]) => {
      setChildren(cs); setTerms(ts);
      if (cs.length) setChildId(String(cs[0].id));
      if (ts.length) setTermId(String(ts[0].id));
    }).catch((e: any) => setErr(e.message));
  }, []);

  const loadResults = async () => {
    if (!childId || !termId) return;
    setBusy(true); setErr(""); setResult(null);
    try { setResult(await api(`/parent/children/${childId}/results?term_id=${termId}`)); }
    catch (e: any) {
      setErr(e.message === "Released results not found." ? "Results for this term have not been released by the teacher yet." : e.message);
    } finally { setBusy(false); }
  };

  return (
    <>
      <h1>Parent / Guardian Portal</h1>
      <p className="muted">You can only view children linked and approved by the school, and results their teacher has released.</p>
      <div className="card">
        <label>Child
          <select value={childId} onChange={(e) => { setChildId(e.target.value); setResult(null); setErr(""); }}>
            {children.map((c) => <option key={c.id} value={c.id}>{c.name}{c.class_name ? ` · ${c.class_name}` : ""}</option>)}
          </select>
        </label>
        <label>Term
          <select value={termId} onChange={(e) => { setTermId(e.target.value); setResult(null); setErr(""); }}>
            {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <button className="btn" onClick={loadResults} disabled={busy || !childId || !termId}>{busy ? "Checking…" : "View released results"}</button>
      </div>
      {err && <p className="muted" role="status">{err}</p>}
      {children.length === 0 && <div className="card"><p>No approved learner links are available for this account. Please contact the school office.</p></div>}
      {result && <div className="card">
        <h2>{result.learner.name} · {result.term.name}</h2>
        <p className="muted">Released by the school on {result.released_at.slice(0, 10)}.</p>
        {result.results.length === 0 ? <p className="muted">No results have been recorded for this term.</p> :
          <table><thead><tr><th>Subject</th><th>Result</th><th>Status</th></tr></thead><tbody>
            {result.results.map((r: any) => <tr key={r.subject}><td>{r.subject}</td><td>{r.status === "scored" && r.value != null ? `${r.value} / ${r.max}` : "—"}</td><td>{r.status}</td></tr>)}
          </tbody></table>}
      </div>}
    </>
  );
}

function ResultsRelease() {
  const [classes, setClasses] = useState<any[]>([]);
  const [terms, setTerms] = useState<any[]>([]);
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [status, setStatus] = useState("not_released");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api("/classes"), api("/terms")]).then(([cs, ts]) => {
      setClasses(cs); setTerms(ts);
      if (cs.length) setClassId(String(cs[0].id));
      if (ts.length) setTermId(String(ts[0].id));
    }).catch((e: any) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!classId || !termId) return;
    api(`/classes/${classId}/terms/${termId}/release-status`)
      .then((r) => setStatus(r.status)).catch((e: any) => setErr(e.message));
  }, [classId, termId]);

  const changeRelease = async () => {
    setBusy(true); setErr(""); setMsg("");
    const action = status === "released" ? "withdraw-release" : "release";
    try {
      const r = await api(`/classes/${classId}/terms/${termId}/${action}`, { method: "POST" });
      setStatus(r.status); setMsg(action === "release" ? "Results released to approved guardians." : "Results access withdrawn.");
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <>
      <h1>Results release</h1>
      <p className="muted">Review your class results before releasing them. Only approved guardians linked to learners in this class can view released results.</p>
      <div className="card">
        <label>Class<select value={classId} onChange={(e) => setClassId(e.target.value)}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select></label>
        <label>Term<select value={termId} onChange={(e) => setTermId(e.target.value)}>
          {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></label>
        <p>Current status: <span className="badge">{status.replace("_", " ")}</span></p>
        <button className={status === "released" ? "btn bad" : "btn"} onClick={changeRelease} disabled={busy || !classId || !termId}>
          {busy ? "Saving…" : status === "released" ? "Withdraw results release" : "Release results to guardians"}
        </button>
        {msg && <p role="status">{msg}</p>}
        {err && <p className="err" role="alert">{err}</p>}
      </div>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState<any>(null), [view, setView] = useState("dash"), [lid, setLid] = useState<number | null>(null), [ready, setReady] = useState(!getToken());
  useEffect(() => { if (getToken()) api("/me").then(setUser).catch(() => setToken("")).finally(() => setReady(true)); }, []);
  if (!ready) return <p style={{ padding: "1rem" }}>Loading…</p>;
if (!user) return <LoginScreen onDone={setUser} />;
  const nav = (v: string) => { setView(v); setLid(null); };
  return (
    <>
      <header className="bar">
        <span className="brand">EduLongView</span>
        <nav aria-label="Main">{(user.role === "parent" ? [["parent", "Parent portal"]] : [["dash", "Dashboard"], ["learners", "Learners"], ["reviews", "Reviews"], ...(user.role !== "reviewer" ? [["data", "Data"]] : []), ...(user.role === "teacher" || user.role === "school_admin" ? [["release", "Results release"]] : []), ...(user.role === "school_admin" ? [["admin", "Admin"]] : [])]).map(([k, t]) => <button key={k} className={view === k ? "on" : ""} onClick={() => nav(k)}>{t}</button>)}</nav>
        <span>{user.name} <button className="linkbtn" onClick={() => { setToken(""); setUser(null); }}>Sign out</button></span>
      </header>
      <main>
        {user.role === "parent" ? <ParentPortal /> : <>
        {view === "dash" && <Dashboard />}
        {view === "learners" && (lid ? <LearnerPage id={lid} role={user.role} back={() => setLid(null)} /> : <Learners open={setLid} />)}
        {view === "reviews" && <Reviews role={user.role} />}
        {view === "admin" && <Admin />}
        {view === "data" && <DataPage role={user.role} />}
        {view === "release" && <ResultsRelease />}
        </>}
      </main>
    </>
  );
}
