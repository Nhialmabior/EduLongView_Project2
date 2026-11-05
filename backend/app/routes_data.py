"""Data management: setup lists, score entry grid, class attendance register, CSV import."""
import csv, io, datetime as dt
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from . import models as m
from .routes import db_dep, current, need, visible, audit, WRITERS

d = APIRouter()
STATUSES = ("scored", "absent", "unassessed", "missing")
MAX_CSV = 1_000_000

def own(db, u, model, oid, what):
    o = db.get(model, oid)
    if not o or o.school_id != u.school_id: raise HTTPException(404, f"{what} not found.")
    return o

def class_learners(db, u, cid):
    k = own(db, u, m.Klass, cid, "Class")
    if u.role == "teacher" and k.teacher_id != u.id: raise HTTPException(404, "Class not found.")
    return visible(db, u).filter(m.Learner.class_id == cid).order_by(m.Learner.name).all()

def dup(db, u, model, name, skip=None):
    for o in db.query(model).filter(model.school_id == u.school_id):
        if o.name.lower() == name.strip().lower() and o.id != skip: raise HTTPException(409, "That name is already in use.")

# ---------- setup lists ----------
class Name(BaseModel): name: str = Field(min_length=1, max_length=80)
class NewTerm(Name): ord: int = Field(ge=1, le=99)
class ClassEdit(BaseModel): name: Optional[str] = Field(default=None, min_length=1); teacher_id: Optional[int] = None
class LearnerEdit(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1); code: Optional[str] = None; class_id: Optional[int] = None

@d.get("/subjects")
def subjects(u=Depends(current), db=Depends(db_dep)):
    return [dict(id=s.id, name=s.name) for s in db.query(m.Subject).filter(m.Subject.school_id == u.school_id).order_by(m.Subject.name)]

@d.post("/subjects")
def add_subject(b: Name, u=Depends(need("school_admin")), db=Depends(db_dep)):
    dup(db, u, m.Subject, b.name); s = m.Subject(school_id=u.school_id, name=b.name.strip()); db.add(s); db.commit()
    audit(db, u, "subject.create", str(s.id)); return dict(id=s.id)

@d.put("/subjects/{sid}")
def rename_subject(sid: int, b: Name, u=Depends(need("school_admin")), db=Depends(db_dep)):
    s = own(db, u, m.Subject, sid, "Subject"); dup(db, u, m.Subject, b.name, skip=sid); s.name = b.name.strip(); db.commit()
    audit(db, u, "subject.rename", str(sid)); return dict(id=sid)

@d.get("/terms")
def terms(u=Depends(current), db=Depends(db_dep)):
    return [dict(id=t.id, name=t.name, ord=t.ord) for t in db.query(m.Term).filter(m.Term.school_id == u.school_id).order_by(m.Term.ord)]

@d.post("/terms")
def add_term(b: NewTerm, u=Depends(need("school_admin")), db=Depends(db_dep)):
    dup(db, u, m.Term, b.name); t = m.Term(school_id=u.school_id, name=b.name.strip(), ord=b.ord); db.add(t); db.commit()
    audit(db, u, "term.create", str(t.id)); return dict(id=t.id)

@d.put("/classes/{cid}")
def edit_class(cid: int, b: ClassEdit, u=Depends(need("school_admin")), db=Depends(db_dep)):
    k = own(db, u, m.Klass, cid, "Class")
    if b.teacher_id is not None:
        t = db.get(m.User, b.teacher_id)
        if not t or t.school_id != u.school_id or t.role != "teacher": raise HTTPException(404, "Teacher not found.")
        k.teacher_id = t.id
    if b.name: dup(db, u, m.Klass, b.name, skip=cid); k.name = b.name.strip()
    db.commit(); audit(db, u, "class.edit", str(cid)); return dict(id=cid)

@d.put("/learners/{lid}")
def edit_learner(lid: int, b: LearnerEdit, u=Depends(need("school_admin")), db=Depends(db_dep)):
    l = own(db, u, m.Learner, lid, "Learner")
    if b.class_id is not None: own(db, u, m.Klass, b.class_id, "Class"); l.class_id = b.class_id
    if b.name: l.name = b.name.strip()
    if b.code is not None:
        code = b.code.strip() or None
        if code and db.query(m.Learner).filter(m.Learner.school_id == u.school_id, m.Learner.code == code, m.Learner.id != lid).first():
            raise HTTPException(409, "That learner code is already used.")
        l.code = code
    db.commit(); audit(db, u, "learner.edit", str(lid)); return dict(id=lid)

@d.post("/learners/{lid}/archive")
def archive(lid: int, u=Depends(need("school_admin")), db=Depends(db_dep)):
    own(db, u, m.Learner, lid, "Learner").archived = 1; db.commit(); audit(db, u, "learner.archive", str(lid)); return {"ok": True}

@d.post("/learners/{lid}/restore")
def restore(lid: int, u=Depends(need("school_admin")), db=Depends(db_dep)):
    own(db, u, m.Learner, lid, "Learner").archived = 0; db.commit(); audit(db, u, "learner.restore", str(lid)); return {"ok": True}

@d.get("/archive/learners")
def archived(u=Depends(need("school_admin")), db=Depends(db_dep)):
    return [dict(id=l.id, name=l.name, code=l.code) for l in db.query(m.Learner).filter(m.Learner.school_id == u.school_id, m.Learner.archived == 1)]

# ---------- score entry grid ----------
class Entry(BaseModel): learner_id: int; status: Literal["scored", "absent", "unassessed", "missing"]; value: Optional[float] = None
class GridIn(BaseModel):
    subject_id: int; term_id: int; max: float = Field(default=100, gt=0); entries: List[Entry] = Field(max_length=500)

@d.get("/scores/grid")
def grid(class_id: int, subject_id: int, term_id: int, u=Depends(current), db=Depends(db_dep)):
    ls = class_learners(db, u, class_id); own(db, u, m.Subject, subject_id, "Subject"); own(db, u, m.Term, term_id, "Term")
    rows = {s.learner_id: s for s in db.query(m.Score).filter(m.Score.subject_id == subject_id, m.Score.term_id == term_id,
            m.Score.learner_id.in_([l.id for l in ls]))} if ls else {}
    return dict(max=next((s.max for s in rows.values()), 100.0), entries=[
        dict(learner_id=l.id, name=l.name, status=rows[l.id].status if l.id in rows else None, value=rows[l.id].value if l.id in rows else None) for l in ls])

@d.put("/scores/grid")
def save_grid(b: GridIn, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    own(db, u, m.Subject, b.subject_id, "Subject"); own(db, u, m.Term, b.term_id, "Term")
    vis = {l.id for l in visible(db, u).all()}; errs = []
    for e in b.entries:
        if e.learner_id not in vis: errs.append(f"Learner {e.learner_id} is not available to you.")
        elif e.status == "scored" and (e.value is None or not 0 <= e.value <= b.max):
            errs.append(f"Learner {e.learner_id}: a scored result needs a number from 0 to {b.max:g}.")
    if errs: raise HTTPException(422, " ".join(errs[:5]))
    for e in b.entries:
        row = db.query(m.Score).filter(m.Score.learner_id == e.learner_id, m.Score.subject_id == b.subject_id, m.Score.term_id == b.term_id).first() \
            or m.Score(school_id=u.school_id, learner_id=e.learner_id, subject_id=b.subject_id, term_id=b.term_id)
        row.status, row.max = e.status, b.max; row.value = e.value if e.status == "scored" else None; db.add(row)
    db.commit(); audit(db, u, "scores.save", f"{len(b.entries)} entries, subject {b.subject_id}, term {b.term_id}")
    return dict(saved=len(b.entries))

# ---------- class attendance register ----------
class RegEntry(BaseModel): learner_id: int; status: Literal["present", "late", "absent", "excused"]
class RegIn(BaseModel): class_id: int; day: dt.date; entries: List[RegEntry] = Field(max_length=500)

@d.get("/attendance/register")
def register(class_id: int, day: dt.date, u=Depends(current), db=Depends(db_dep)):
    ls = class_learners(db, u, class_id); ids = [l.id for l in ls]
    rows = {a.learner_id: a.status for a in db.query(m.Attendance).filter(m.Attendance.day == day, m.Attendance.learner_id.in_(ids))} if ids else {}
    return [dict(learner_id=l.id, name=l.name, status=rows.get(l.id)) for l in ls]

@d.put("/attendance/register")
def save_register(b: RegIn, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    if b.day > dt.date.today(): raise HTTPException(422, "Attendance cannot be recorded for a future date.")
    ids = {l.id for l in class_learners(db, u, b.class_id)}
    if any(e.learner_id not in ids for e in b.entries): raise HTTPException(422, "One or more learners are not in this class.")
    for e in b.entries:
        a = db.query(m.Attendance).filter(m.Attendance.learner_id == e.learner_id, m.Attendance.day == b.day).first() \
            or m.Attendance(school_id=u.school_id, learner_id=e.learner_id, day=b.day)
        a.status = e.status; db.add(a)
    db.commit(); audit(db, u, "attendance.register", f"class {b.class_id} {b.day} ({len(b.entries)} learners)"); return dict(saved=len(b.entries))

# ---------- CSV import (validate everything first; write nothing if any row is wrong) ----------
class Imp(BaseModel): text: str; dry_run: bool = True

def rows_of(text, want):
    if len(text) > MAX_CSV: raise HTTPException(413, "File too large (1 MB maximum).")
    rd = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not rd.fieldnames: raise HTTPException(422, "The file is empty.")
    rd.fieldnames = [f.strip().lower() for f in rd.fieldnames]
    missing = [c for c in want if c not in rd.fieldnames]
    if missing: raise HTTPException(422, "Missing column(s): " + ", ".join(missing))
    rows = list(rd)
    if len(rows) > 5000: raise HTTPException(422, "Too many rows (5000 maximum per file).")
    return rows

def result(errs, ok, dry):
    wrote = bool(ok) and not errs and not dry
    return dict(valid_rows=len(ok), error_count=len(errs), errors=errs[:50], dry_run=dry, imported=len(ok) if wrote else 0), wrote

@d.post("/import/learners")
def import_learners(b: Imp, u=Depends(need("school_admin")), db=Depends(db_dep)):
    rows = rows_of(b.text, ["name", "class"])
    classes = {k.name.lower(): k for k in db.query(m.Klass).filter(m.Klass.school_id == u.school_id)}
    codes = {l.code for l in db.query(m.Learner).filter(m.Learner.school_id == u.school_id) if l.code}
    errs, ok = [], []
    for i, r in enumerate(rows, start=2):
        name, code = (r.get("name") or "").strip(), ((r.get("code") or "").strip() or None)
        k = classes.get((r.get("class") or "").strip().lower())
        if not name: errs.append(f"Row {i}: name is empty.")
        elif not k: errs.append(f"Row {i}: class '{r.get('class')}' does not exist. Create it first.")
        elif code and code in codes: errs.append(f"Row {i}: code '{code}' is already used.")
        else:
            if code: codes.add(code)
            ok.append((name, code, k.id))
    res, wrote = result(errs, ok, b.dry_run)
    if wrote:
        db.add_all([m.Learner(school_id=u.school_id, name=n, code=c, class_id=k) for n, c, k in ok]); db.commit()
        audit(db, u, "import.learners", f"{len(ok)} learners")
    return res

@d.post("/import/scores")
def import_scores(b: Imp, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    rows = rows_of(b.text, ["learner_code", "subject", "term"])
    learners = {l.code: l for l in visible(db, u).all() if l.code}
    subs = {s.name.lower(): s for s in db.query(m.Subject).filter(m.Subject.school_id == u.school_id)}
    terms_ = {t.name.lower(): t for t in db.query(m.Term).filter(m.Term.school_id == u.school_id)}
    errs, ok, seen = [], [], set()
    for i, r in enumerate(rows, start=2):
        l = learners.get((r.get("learner_code") or "").strip()); s = subs.get((r.get("subject") or "").strip().lower()); t = terms_.get((r.get("term") or "").strip().lower())
        if not l: errs.append(f"Row {i}: learner code '{r.get('learner_code')}' was not found or is not available to you."); continue
        if not s: errs.append(f"Row {i}: subject '{r.get('subject')}' does not exist."); continue
        if not t: errs.append(f"Row {i}: term '{r.get('term')}' does not exist."); continue
        vtxt = (r.get("value") or "").strip(); status = (r.get("status") or "").strip().lower() or ("scored" if vtxt else "missing")
        if status not in STATUSES: errs.append(f"Row {i}: status must be one of {', '.join(STATUSES)}."); continue
        try: mx = float((r.get("max") or "").strip() or 100)
        except ValueError: errs.append(f"Row {i}: max must be a number."); continue
        if mx <= 0: errs.append(f"Row {i}: max must be above zero."); continue
        value = None
        if status == "scored":
            try: value = float(vtxt)
            except ValueError: errs.append(f"Row {i}: a scored result needs a number (a blank is never treated as zero)."); continue
            if not 0 <= value <= mx: errs.append(f"Row {i}: value {value:g} is outside 0 to {mx:g}."); continue
        if (l.id, s.id, t.id) in seen: errs.append(f"Row {i}: this learner, subject and term appear twice in the file."); continue
        seen.add((l.id, s.id, t.id)); ok.append((l.id, s.id, t.id, value, status, mx))
    res, wrote = result(errs, ok, b.dry_run)
    if wrote:
        have = {(x.learner_id, x.subject_id, x.term_id): x for x in db.query(m.Score).filter(m.Score.learner_id.in_({o[0] for o in ok}))}
        for lid, sid, tid, v, st, mx in ok:
            row = have.get((lid, sid, tid)) or m.Score(school_id=u.school_id, learner_id=lid, subject_id=sid, term_id=tid)
            row.value, row.status, row.max = v, st, mx; db.add(row)
        db.commit(); audit(db, u, "import.scores", f"{len(ok)} results")
    return res

# ---------- permanent deletion (privacy: right to erasure) ----------
class Erase(BaseModel): confirm_name: str

@d.delete("/learners/{lid}/permanent")
def erase(lid: int, b: Erase, u=Depends(need("school_admin")), db=Depends(db_dep)):
    l = own(db, u, m.Learner, lid, "Learner")
    if not l.archived: raise HTTPException(409, "Archive the learner first, then delete permanently.")
    if b.confirm_name.strip() != l.name: raise HTTPException(422, "The name you typed does not match.")
    plan_ids = [p.id for p in db.query(m.Plan).filter(m.Plan.learner_id == lid)]
    if plan_ids: db.query(m.PlanNote).filter(m.PlanNote.plan_id.in_(plan_ids)).delete(synchronize_session=False)
    for model in (m.Plan, m.Score, m.Attendance, m.Profile, m.Draft):   # Profile before Draft: it points at a draft
        db.query(model).filter(model.learner_id == lid).delete(synchronize_session=False)
    db.delete(l); db.commit(); audit(db, u, "learner.erase", f"learner id {lid}")   # the log keeps the id only, never the name
    return {"ok": True}