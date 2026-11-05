import { useEffect, useState } from "react";
import { api } from "./api";

const today = () => new Date().toISOString().slice(0, 10);

function useAct() {
  const [msg, setMsg] = useState(""), [err, setErr] = useState("");
  const run = async (fn: () => Promise<any>, ok = "") => { setErr(""); setMsg(""); try { await fn(); if (ok) setMsg(ok); } catch (e: any) { setErr(e.message); } };
  return { msg, err, run, setErr };
}
const Msg = ({ a }: any) => <>{a.msg && <p role="status">{a.msg}</p>}{a.err && <p className="err" role="alert">{a.err}</p>}</>;
const Sel = ({ label, value, onChange, options, none }: any) => (
  <label>{label}<select value={value} onChange={(e) => onChange(e.target.value)}><option value="">{none || "Choose…"}</option>
    {options.map((o: any) => <option key={o.id ?? o} value={o.id ?? o}>{o.name ?? o}</option>)}</select></label>
);

function Scores({ L }: any) {
  const [sel, setSel] = useState({ cls: "", sub: "", term: "" }), [max, setMax] = useState("100"), [rows, setRows] = useState<any[] | null>(null), a = useAct();
  const ready = sel.cls && sel.sub && sel.term;
  const load = () => a.run(async () => {
    const g = await api(`/scores/grid?class_id=${sel.cls}&subject_id=${sel.sub}&term_id=${sel.term}`);
    setMax(String(g.max)); setRows(g.entries.map((e: any) => ({ ...e, status: e.status || "", value: e.value == null ? "" : String(e.value) })));
  });
  const upd = (i: number, p: any) => setRows(rows!.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const save = () => a.run(async () => {
    const mx = parseFloat(max); if (!(mx > 0)) throw new Error("Enter a maximum score above zero.");
    const entries = rows!.filter((r) => r.status).map((r) => {
      if (r.status === "scored" && (r.value === "" || isNaN(parseFloat(r.value)))) throw new Error(`Enter a number for ${r.name}, or choose absent, unassessed or missing.`);
      return { learner_id: r.learner_id, status: r.status, value: r.status === "scored" ? parseFloat(r.value) : null };
    });
    if (!entries.length) throw new Error("Nothing to save yet. Enter a result for at least one learner.");
    await api("/scores/grid", { method: "PUT", body: { subject_id: +sel.sub, term_id: +sel.term, max: mx, entries } });
  }, "Scores saved.");
  return (
    <div className="card"><h2>Enter scores</h2>
      <p className="muted">Pick a class, subject and term. Absent, unassessed and missing are recorded as gaps, never as zero. Type 0 only when the learner really scored zero.</p>
      <div className="row">
        <Sel label="Class" value={sel.cls} onChange={(v: string) => { setSel({ ...sel, cls: v }); setRows(null); }} options={L.classes} />
        <Sel label="Subject" value={sel.sub} onChange={(v: string) => { setSel({ ...sel, sub: v }); setRows(null); }} options={L.subjects} />
        <Sel label="Term" value={sel.term} onChange={(v: string) => { setSel({ ...sel, term: v }); setRows(null); }} options={L.terms} />
      </div>
      <button className="btn" disabled={!ready} onClick={load}>Load class</button>
      {rows && (rows.length === 0 ? <p className="muted">No learners in this class.</p> : <>
        <label style={{ maxWidth: 220, marginTop: "1rem" }}>Maximum score<input type="number" value={max} onChange={(e) => setMax(e.target.value)} /></label>
        <table><thead><tr><th>Learner</th><th>Result</th><th>Score</th></tr></thead><tbody>
          {rows.map((r, i) => <tr key={r.learner_id}><td>{r.name}</td>
            <td><select aria-label={`Result for ${r.name}`} value={r.status} onChange={(e) => upd(i, { status: e.target.value })}>
              <option value="">not entered</option><option value="scored">scored</option><option value="absent">absent</option><option value="unassessed">unassessed</option><option value="missing">missing</option></select></td>
            <td><input aria-label={`Score for ${r.name}`} type="number" min="0" disabled={r.status !== "scored"} value={r.value} style={{ width: 100, margin: 0 }}
              onChange={(e) => upd(i, { value: e.target.value, status: r.status || "scored" })} /></td></tr>)}</tbody></table>
        <p><button className="btn" onClick={save}>Save scores</button></p></>)}
      <Msg a={a} />
    </div>
  );
}

function Register({ L }: any) {
  const [cls, setCls] = useState(""), [day, setDay] = useState(today()), [rows, setRows] = useState<any[] | null>(null), a = useAct();
  const load = () => a.run(async () => { const r = await api(`/attendance/register?class_id=${cls}&day=${day}`); setRows(r.map((x: any) => ({ ...x, status: x.status || "" }))); });
  const upd = (i: number, status: string) => setRows(rows!.map((r, j) => (j === i ? { ...r, status } : r)));
  const save = () => a.run(async () => {
    const entries = rows!.filter((r) => r.status).map((r) => ({ learner_id: r.learner_id, status: r.status }));
    if (!entries.length) throw new Error("Nothing to save yet. Mark at least one learner.");
    await api("/attendance/register", { method: "PUT", body: { class_id: +cls, day, entries } });
  }, "Register saved.");
  return (
    <div className="card"><h2>Class register</h2>
      <div className="row" style={{ alignItems: "end" }}>
        <Sel label="Class" value={cls} onChange={(v: string) => { setCls(v); setRows(null); }} options={L.classes} />
        <label>Date<input type="date" value={day} max={today()} onChange={(e) => { setDay(e.target.value); setRows(null); }} /></label>
        <button className="btn" disabled={!cls || !day} onClick={load} style={{ marginBottom: ".8rem" }}>Load register</button></div>
      {rows && (rows.length === 0 ? <p className="muted">No learners in this class.</p> : <>
        <p><button className="btn alt" onClick={() => setRows(rows.map((r) => ({ ...r, status: "present" })))}>Mark everyone present</button></p>
        <table><thead><tr><th>Learner</th><th>Status</th></tr></thead><tbody>
          {rows.map((r, i) => <tr key={r.learner_id}><td>{r.name}</td><td><select aria-label={`Attendance for ${r.name}`} value={r.status} onChange={(e) => upd(i, e.target.value)}>
            <option value="">not marked</option><option>present</option><option>late</option><option>absent</option><option>excused</option></select></td></tr>)}</tbody></table>
        <p><button className="btn" onClick={save}>Save register</button></p></>)}
      <Msg a={a} />
    </div>
  );
}

function Import({ role }: { role: string }) {
  const [kind, setKind] = useState(role === "school_admin" ? "learners" : "scores"), [text, setText] = useState(""), [name, setName] = useState(""), [res, setRes] = useState<any>(null), a = useAct();
  const pick = async (e: any) => { const f = e.target.files?.[0]; if (!f) return; setName(f.name); setText(await f.text()); setRes(null); };
  const go = (dry: boolean) => a.run(async () => setRes(await api(`/import/${kind}`, { method: "POST", body: { text, dry_run: dry } })));
  const ok = res && res.dry_run && res.error_count === 0 && res.valid_rows > 0;
  return (
    <div className="card"><h2>Import from a CSV file</h2>
      <p className="muted">Check the file first. Nothing is saved until every row is valid and you click Import.</p>
      {role === "school_admin" && <label>What are you importing?<select value={kind} onChange={(e) => { setKind(e.target.value); setRes(null); }}><option value="learners">Learners</option><option value="scores">Scores</option></select></label>}
      <details open><summary>File format</summary>
        {kind === "learners" ? <pre>{"name,class,code\nAmina Yusuf,Form 1A,2001"}</pre> : <pre>{"learner_code,subject,term,value,status,max\n2001,Maths,Y1 T1,72,,100\n2001,English,Y1 T1,,absent,"}</pre>}
        <p className="muted">{kind === "learners" ? "The class must already exist. The code column is optional." : "status and max are optional. A blank value with no status is recorded as missing, never as zero."}</p></details>
      <label>CSV file<input type="file" accept=".csv,text/csv" onChange={pick} /></label>
      <div className="row"><button className="btn alt" disabled={!text} onClick={() => go(true)}>Check file</button>
        <button className="btn" disabled={!ok} onClick={() => go(false)}>Import</button></div>
      {name && <p className="muted">Selected: {name}</p>}
      {res && (res.dry_run
        ? <p role="status">{res.valid_rows} valid row(s), {res.error_count} problem(s).{res.error_count === 0 && res.valid_rows > 0 && " Ready to import."}</p>
        : <p role="status">{res.imported > 0 ? `Imported ${res.imported} row(s).` : "Nothing was imported."}</p>)}
      {res && res.errors.length > 0 && <ul className="err">{res.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul>}
      <Msg a={a} />
    </div>
  );
}

function Setup({ L, reload }: any) {
  const [users, setUsers] = useState<any[]>([]), [learners, setLearners] = useState<any[]>([]), [arch, setArch] = useState<any[]>([]), a = useAct();
  const [f, setF] = useState({ subject: "", term: "", ord: "", cls: "", teacher: "", ln: "", lc: "", lcls: "" });
  const load = () => Promise.all([api("/users"), api("/learners"), api("/archive/learners")])
    .then(([u, l, r]) => { setUsers(u.filter((x: any) => x.role === "teacher")); setLearners(l); setArch(r); }).catch((e) => a.setErr(e.message));
  useEffect(() => { load(); }, []);
  const act = (fn: () => Promise<any>, ok: string) => a.run(async () => { await fn(); await load(); reload(); }, ok);
  const ask = (q: string, cur: string) => window.prompt(q, cur)?.trim() || null;
  const classId = (n: string) => L.classes.find((c: any) => c.name === n)?.id ?? "";
  return (
    <>
      <Msg a={a} />
      <div className="card"><h2>Subjects</h2>
        <div className="row">{L.subjects.map((s: any) => <span className="badge" key={s.id}>{s.name} <button className="linkbtn" style={{ color: "var(--accent)", padding: 0 }}
          onClick={() => { const n = ask("New subject name", s.name); if (n) act(() => api(`/subjects/${s.id}`, { method: "PUT", body: { name: n } }), "Subject renamed."); }}>rename</button></span>)}</div>
        <div className="row" style={{ alignItems: "end", marginTop: ".8rem" }}><label style={{ flex: 1 }}>New subject<input value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} /></label>
          <button className="btn" style={{ marginBottom: ".8rem" }} onClick={() => act(async () => { await api("/subjects", { method: "POST", body: { name: f.subject } }); setF({ ...f, subject: "" }); }, "Subject added.")}>Add subject</button></div></div>
      <div className="card"><h2>Terms</h2>
        <div className="row">{L.terms.map((t: any) => <span className="badge" key={t.id}>{t.ord}. {t.name}</span>)}</div>
        <div className="row" style={{ alignItems: "end", marginTop: ".8rem" }}><label style={{ flex: 1 }}>Term name (for example Y2 T2)<input value={f.term} onChange={(e) => setF({ ...f, term: e.target.value })} /></label>
          <label style={{ width: 120 }}>Order<input type="number" min="1" value={f.ord} onChange={(e) => setF({ ...f, ord: e.target.value })} /></label>
          <button className="btn" style={{ marginBottom: ".8rem" }} onClick={() => act(async () => { await api("/terms", { method: "POST", body: { name: f.term, ord: +f.ord } }); setF({ ...f, term: "", ord: "" }); }, "Term added.")}>Add term</button></div></div>
      <div className="card"><h2>Classes</h2>
        <table><thead><tr><th>Class</th><th>Teacher</th><th /></tr></thead><tbody>{L.classes.map((c: any) => <tr key={c.id}><td>{c.name}</td>
          <td><select aria-label={`Teacher for ${c.name}`} value={c.teacher_id ?? ""} style={{ margin: 0 }} onChange={(e) => e.target.value && act(() => api(`/classes/${c.id}`, { method: "PUT", body: { teacher_id: +e.target.value } }), "Teacher assigned.")}>
            <option value="">unassigned</option>{users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></td>
          <td><button className="btn alt" onClick={() => { const n = ask("New class name", c.name); if (n) act(() => api(`/classes/${c.id}`, { method: "PUT", body: { name: n } }), "Class renamed."); }}>Rename</button></td></tr>)}</tbody></table>
        <div className="row" style={{ alignItems: "end", marginTop: ".8rem" }}><label style={{ flex: 1 }}>New class<input value={f.cls} onChange={(e) => setF({ ...f, cls: e.target.value })} /></label>
          <Sel label="Teacher" value={f.teacher} onChange={(v: string) => setF({ ...f, teacher: v })} options={users} none="No teacher yet" />
          <button className="btn" style={{ marginBottom: ".8rem" }} onClick={() => act(async () => { await api("/classes", { method: "POST", body: { name: f.cls, teacher_id: f.teacher ? +f.teacher : null } }); setF({ ...f, cls: "", teacher: "" }); }, "Class added.")}>Add class</button></div></div>
      <div className="card"><h2>Learners</h2>
        <table><thead><tr><th>Name</th><th>Code</th><th>Class</th><th /></tr></thead><tbody>{learners.map((l) => <tr key={l.id}><td>{l.name}</td><td>{l.code}</td>
          <td><select aria-label={`Class for ${l.name}`} value={classId(l.class_name)} style={{ margin: 0 }} onChange={(e) => e.target.value && act(() => api(`/learners/${l.id}`, { method: "PUT", body: { class_id: +e.target.value } }), "Learner moved.")}>
            {L.classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></td>
          <td className="row"><button className="btn alt" onClick={() => { const n = ask("Learner name", l.name); if (n) act(() => api(`/learners/${l.id}`, { method: "PUT", body: { name: n } }), "Learner renamed."); }}>Rename</button>
            <button className="btn alt" onClick={() => window.confirm(`Archive ${l.name}? Their records are kept and can be restored.`) && act(() => api(`/learners/${l.id}/archive`, { method: "POST" }), "Learner archived.")}>Archive</button></td></tr>)}</tbody></table>
        <h3 style={{ marginTop: "1rem" }}>Add a learner</h3>
        <div className="row" style={{ alignItems: "end" }}><label style={{ flex: 1 }}>Name<input value={f.ln} onChange={(e) => setF({ ...f, ln: e.target.value })} /></label>
          <label style={{ width: 140 }}>Code (optional)<input value={f.lc} onChange={(e) => setF({ ...f, lc: e.target.value })} /></label>
          <Sel label="Class" value={f.lcls} onChange={(v: string) => setF({ ...f, lcls: v })} options={L.classes} />
          <button className="btn" style={{ marginBottom: ".8rem" }} onClick={() => act(async () => { await api("/learners", { method: "POST", body: { name: f.ln, code: f.lc || null, class_id: +f.lcls } }); setF({ ...f, ln: "", lc: "", lcls: "" }); }, "Learner added.")}>Add learner</button></div>
        {arch.length > 0 && <><h3>Archived</h3><ul>{arch.map((l) => <li key={l.id}>{l.name} <button className="btn alt" onClick={() => act(() => api(`/learners/${l.id}/restore`, { method: "POST" }), "Learner restored.")}>Restore</button> <button className="btn bad" onClick={() => { const t = window.prompt(`This permanently deletes ${l.name} and all their scores, attendance, plans and profile. It cannot be undone. Type the learner's full name to confirm.`); if (t) act(() => api(`/learners/${l.id}/permanent`, { method: "DELETE", body: { confirm_name: t } }), "Learner permanently deleted."); }}>Delete permanently</button></li>)}</ul></>}</div>
    </>
  );
}

export function DataPage({ role }: { role: string }) {
  const [L, setL] = useState<any>(null), [err, setErr] = useState(""), [tab, setTab] = useState("scores");
  const reload = () => Promise.all([api("/classes"), api("/subjects"), api("/terms")]).then(([classes, subjects, terms]) => setL({ classes, subjects, terms })).catch((e) => setErr(e.message));
  useEffect(() => { reload(); }, []);
  const tabs = [["scores", "Enter scores"], ["register", "Class register"], ["import", "Import CSV"], ...(role === "school_admin" ? [["setup", "Setup"]] : [])];
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!L) return <p>Loading…</p>;
  return (
    <>
      <h1>Data</h1>
      <div className="tabs" role="tablist">{tabs.map(([k, t]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{t}</button>)}</div>
      {L.classes.length === 0 && tab !== "setup" && tab !== "import" && <p className="muted">No classes are assigned to you yet. Ask your school administrator.</p>}
      {tab === "scores" && <Scores L={L} />}
      {tab === "register" && <Register L={L} />}
      {tab === "import" && <Import role={role} />}
      {tab === "setup" && <Setup L={L} reload={reload} />}
    </>
  );
}