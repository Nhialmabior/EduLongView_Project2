"""Attendance, support plans, user management, password change, and PDF/Excel reports."""
import io, datetime as dt
from typing import Literal, Optional
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from . import models as m, security
from .routes import db_dep, current, need, visible, get_learner, audit, learner_trends, WRITERS

x = APIRouter()

# ---------- attendance ----------
class Att(BaseModel): day: dt.date; status: Literal["present", "late", "absent", "excused"]

def att_summary(db, l):
    rows = db.query(m.Attendance).filter(m.Attendance.learner_id == l.id, m.Attendance.school_id == l.school_id).order_by(m.Attendance.day.desc()).all()
    c = {k: sum(1 for a in rows if a.status == k) for k in ("present", "late", "absent", "excused")}
    den = len(rows) - c["excused"]
    rate = round(100 * (c["present"] + c["late"]) / den, 1) if den else None
    flag = f"Attendance is {rate}% across {len(rows)} recorded days." if rate is not None and len(rows) >= 10 and rate < 85 else None
    return dict(total=len(rows), **c, rate=rate, flag=flag, recent=[dict(day=str(a.day), status=a.status) for a in rows[:10]])

@x.get("/learners/{lid}/attendance")
def get_att(lid: int, u=Depends(current), db=Depends(db_dep)): return att_summary(db, get_learner(db, u, lid))

@x.put("/learners/{lid}/attendance")
def set_att(lid: int, b: Att, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    l = get_learner(db, u, lid)
    if b.day > dt.date.today(): raise HTTPException(422, "Attendance cannot be recorded for a future date.")
    a = db.query(m.Attendance).filter(m.Attendance.learner_id == l.id, m.Attendance.day == b.day).first() or m.Attendance(school_id=l.school_id, learner_id=l.id, day=b.day)
    a.status = b.status; db.add(a); db.commit(); audit(db, u, "attendance.set", f"learner {l.id} {b.day} {b.status}")
    return att_summary(db, l)

# ---------- support plans ----------
class NewPlan(BaseModel): title: str = Field(min_length=1); goal: Optional[str] = None; follow_up: Optional[dt.date] = None
class NoteIn(BaseModel): kind: Literal["observation", "interpretation"]; text: str = Field(min_length=1)
class Close(BaseModel): outcome: str = Field(min_length=1)

def plan_dump(db, p):
    ns = db.query(m.PlanNote).filter(m.PlanNote.plan_id == p.id).order_by(m.PlanNote.id).all()
    return dict(id=p.id, title=p.title, goal=p.goal, follow_up=str(p.follow_up) if p.follow_up else None, status=p.status, outcome=p.outcome,
                notes=[dict(kind=n.kind, text=n.text, at=str(n.at)[:16]) for n in ns])

def get_plan(db, u, pid):
    p = db.get(m.Plan, pid)
    if not p or p.school_id != u.school_id: raise HTTPException(404, "Plan not found.")
    get_learner(db, u, p.learner_id); return p

@x.get("/learners/{lid}/plans")
def plans(lid: int, u=Depends(current), db=Depends(db_dep)):
    l = get_learner(db, u, lid)
    return [plan_dump(db, p) for p in db.query(m.Plan).filter(m.Plan.learner_id == l.id).order_by(m.Plan.id.desc())]

@x.post("/learners/{lid}/plans")
def new_plan(lid: int, b: NewPlan, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    l = get_learner(db, u, lid)
    p = m.Plan(school_id=l.school_id, learner_id=l.id, title=b.title.strip(), goal=b.goal, follow_up=b.follow_up, created_by=u.id)
    db.add(p); db.commit(); audit(db, u, "plan.create", f"plan {p.id} learner {l.id}"); return plan_dump(db, p)

@x.post("/plans/{pid}/notes")
def add_note(pid: int, b: NoteIn, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    p = get_plan(db, u, pid)
    db.add(m.PlanNote(school_id=p.school_id, plan_id=p.id, kind=b.kind, text=b.text.strip(), by=u.id)); db.commit()
    audit(db, u, "plan.note", f"plan {p.id} {b.kind}"); return plan_dump(db, p)

@x.post("/plans/{pid}/close")
def close_plan(pid: int, b: Close, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    p = get_plan(db, u, pid)
    if p.status != "open": raise HTTPException(409, "This plan is already closed.")
    p.status, p.outcome = "closed", b.outcome.strip(); db.commit(); audit(db, u, "plan.close", f"plan {p.id}"); return plan_dump(db, p)

@x.get("/plans/due")
def due(u=Depends(current), db=Depends(db_dep)):
    ids = [l.id for l in visible(db, u).all()]
    ps = db.query(m.Plan).filter(m.Plan.learner_id.in_(ids), m.Plan.status == "open", m.Plan.follow_up <= dt.date.today()).all() if ids else []
    return [dict(plan_dump(db, p), learner_name=db.get(m.Learner, p.learner_id).name) for p in ps]

# ---------- classes and users ----------
class NewClass(BaseModel): name: str = Field(min_length=1); teacher_id: Optional[int] = None
class NewUser(BaseModel):
    email: str; name: str; role: Literal["school_admin", "teacher", "reviewer"]; password: str = Field(min_length=10)
class PwReset(BaseModel): password: str = Field(min_length=10)
class PwChange(BaseModel): old: str; new: str = Field(min_length=10)

@x.get("/classes")
def classes(u=Depends(current), db=Depends(db_dep)):
    q = db.query(m.Klass).filter(m.Klass.school_id == u.school_id)
    if u.role == "teacher": q = q.filter(m.Klass.teacher_id == u.id)
    return [dict(id=k.id, name=k.name, teacher_id=k.teacher_id) for k in q]

@x.post("/classes")
def new_class(b: NewClass, u=Depends(need("school_admin")), db=Depends(db_dep)):
    if b.teacher_id:
        t = db.get(m.User, b.teacher_id)
        if not t or t.school_id != u.school_id: raise HTTPException(404, "Teacher not found.")
    k = m.Klass(school_id=u.school_id, name=b.name.strip(), teacher_id=b.teacher_id); db.add(k); db.commit()
    audit(db, u, "class.create", str(k.id)); return dict(id=k.id)

@x.get("/users")
def users(u=Depends(need("school_admin")), db=Depends(db_dep)):
    return [dict(id=a.id, name=a.name, email=a.email, role=a.role) for a in db.query(m.User).filter(m.User.school_id == u.school_id)]

@x.post("/users")
def new_user(b: NewUser, u=Depends(need("school_admin")), db=Depends(db_dep)):
    email = b.email.lower().strip()
    if "@" not in email: raise HTTPException(422, "Enter a valid email address.")
    if db.query(m.User).filter(m.User.email == email).first(): raise HTTPException(409, "That email is already in use.")
    n = m.User(school_id=u.school_id, email=email, name=b.name.strip(), role=b.role, pw=security.hash_pw(b.password)); db.add(n); db.commit()
    audit(db, u, "user.create", f"user {n.id} role {n.role}"); return dict(id=n.id)

@x.post("/users/{uid}/reset-password")
def reset_pw(uid: int, b: PwReset, u=Depends(need("school_admin")), db=Depends(db_dep)):
    t = db.get(m.User, uid)
    if not t or t.school_id != u.school_id: raise HTTPException(404, "User not found.")
    t.pw = security.hash_pw(b.password); db.commit(); audit(db, u, "user.reset_password", f"user {t.id}"); return {"ok": True}

@x.post("/auth/change-password")
def change_pw(b: PwChange, u=Depends(current), db=Depends(db_dep)):
    if not security.check_pw(b.old, u.pw): raise HTTPException(403, "Current password is incorrect.")
    u.pw = security.hash_pw(b.new); db.commit(); audit(db, u, "user.change_password"); return {"ok": True}

# ---------- reports (approved profile text only; unreviewed drafts are never exported) ----------
def send(buf, name, mt):
    buf.seek(0); return StreamingResponse(buf, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{name}"'})

def grid(t, numeric):
    terms = []
    for s in t["subjects"]:
        for p in s["points"]:
            if p["term"] not in terms: terms.append(p["term"])
    rows = []
    for s in t["subjects"]:
        by = {p["term"]: p for p in s["points"]}
        cell = lambda p: None if p is None else (p["pct"] if p["pct"] is not None else p["status"]) if numeric else ("not recorded" if p is None else f"{p['pct']}%" if p["pct"] is not None else p["status"])
        rows.append([s["subject"]] + [cell(by.get(tm)) for tm in terms] + [s["average"] if numeric else (f"{s['average']}%" if s["average"] is not None else "-")])
    return terms, rows

def profile_text(db, l):
    p = db.query(m.Profile).filter(m.Profile.learner_id == l.id).first(); return p.content if p else None

@x.get("/reports/learner/{lid}.xlsx")
def learner_xlsx(lid: int, u=Depends(current), db=Depends(db_dep)):
    from openpyxl import Workbook
    l = get_learner(db, u, lid); t = learner_trends(db, l); terms, rows = grid(t, True)
    wb = Workbook(); ws = wb.active; ws.title = "Scores (%)"; ws.append(["Subject"] + terms + ["Average"])
    for r_ in rows: ws.append(r_)
    n = wb.create_sheet("Notes"); n.append(["Learner", l.name]); n.append(["Method", t["method"]])
    for f in t["flags"]: n.append(["Indicator (for review)", f["text"]])
    a = att_summary(db, l); n.append(["Attendance rate %", a["rate"]]); n.append(["Approved profile", profile_text(db, l) or "None approved yet"])
    audit(db, u, "report.export", f"learner {l.id} xlsx"); b = io.BytesIO(); wb.save(b)
    return send(b, f"learner-{l.id}-report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@x.get("/reports/learner/{lid}.pdf")
def learner_pdf(lid: int, u=Depends(current), db=Depends(db_dep)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    l = get_learner(db, u, lid); t = learner_trends(db, l); terms, rows = grid(t, False); a = att_summary(db, l)
    st = getSampleStyleSheet(); P = lambda s, sty="BodyText": Paragraph(escape(s).replace("\n", "<br/>"), st[sty])
    S = [P(f"Progress report: {l.name}", "Title"), P(f"Generated {dt.date.today()}. Confidential learner information."), Spacer(1, 12)]
    if rows:
        tb = Table([["Subject"] + terms + ["Average"]] + rows, repeatRows=1)
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d5e0dd")), ("FONTSIZE", (0, 0), (-1, -1), 8)])); S.append(tb)
    S += [Spacer(1, 10), P("Indicators for teacher review (not diagnoses)", "Heading3")] + [P("- " + f["text"]) for f in t["flags"]] or [P("None raised.")]
    S += [P("Attendance", "Heading3"), P(f"Rate: {a['rate']}% over {a['total']} recorded days." if a["rate"] is not None else "No attendance recorded.")]
    S += [P("Support plans", "Heading3")]
    for p in db.query(m.Plan).filter(m.Plan.learner_id == l.id):
        S.append(P(f"- {p.title} ({p.status})" + (f": {p.outcome}" if p.outcome else "")))
    S += [P("Teacher-approved profile", "Heading3"), P(profile_text(db, l) or "None approved yet."), Spacer(1, 8), P("Method: " + t["method"])]
    b = io.BytesIO(); SimpleDocTemplate(b, pagesize=A4, title=f"Progress report {l.name}").build(S)
    audit(db, u, "report.export", f"learner {l.id} pdf"); return send(b, f"learner-{l.id}-report.pdf", "application/pdf")

@x.get("/reports/class/{cid}.xlsx")
def class_xlsx(cid: int, u=Depends(current), db=Depends(db_dep)):
    from openpyxl import Workbook
    k = db.get(m.Klass, cid)
    if not k or k.school_id != u.school_id or (u.role == "teacher" and k.teacher_id != u.id): raise HTTPException(404, "Class not found.")
    ls = visible(db, u).filter(m.Learner.class_id == cid).order_by(m.Learner.name).all()
    wb = Workbook(); ws = wb.active; ws.title = k.name[:30]; head = None
    for l in ls:
        t = learner_trends(db, l)
        if head is None: head = [s["subject"] for s in t["subjects"]]; ws.append(["Learner"] + head + ["Attendance %", "Indicators"])
        av = {s["subject"]: s["average"] for s in t["subjects"]}
        ws.append([l.name] + [av.get(h) for h in head] + [att_summary(db, l)["rate"], len(t["flags"])])
    audit(db, u, "report.export", f"class {cid} xlsx"); b = io.BytesIO(); wb.save(b)
    return send(b, f"class-{cid}-report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
