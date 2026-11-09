import datetime as dt
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from . import models as m, security, analytics, ai

r = APIRouter()
bearer = HTTPBearer()
WRITERS = ("teacher", "school_admin")

def db_dep():
    s = m.Session()
    try: yield s
    finally: s.close()

def current(c=Depends(bearer), db=Depends(db_dep)):
    try: uid = security.read_token(c.credentials)
    except Exception: raise HTTPException(401, "Session expired or invalid. Sign in again.")
    u = db.get(m.User, uid)
    if not u: raise HTTPException(401, "Unknown user.")
    return u

def need(*roles):
    def f(u=Depends(current)):
        if u.role not in roles: raise HTTPException(403, "Your role cannot do this.")
        return u
    return f

def visible(db, u):
    """The single place that decides which learners a user may see: own school, and own classes for teachers."""
    q = db.query(m.Learner).filter(m.Learner.school_id == u.school_id, m.Learner.archived == 0)
    if u.role == "teacher":
        q = q.join(m.Klass, m.Klass.id == m.Learner.class_id).filter(m.Klass.teacher_id == u.id)
    elif u.role == "parent":
        # Parent access is deliberately available only through the release-gated portal routes.
        q = q.filter(m.Learner.id == -1)
    return q

def get_learner(db, u, lid):
    l = visible(db, u).filter(m.Learner.id == lid).first()
    if not l: raise HTTPException(404, "Learner not found.")
    return l

def audit(db, u, action, detail=""):
    db.add(m.Audit(school_id=u.school_id, user_id=u.id, action=action, detail=detail)); db.commit()

def learner_trends(db, l):
    q = (db.query(m.Score, m.Subject, m.Term).join(m.Subject, m.Subject.id == m.Score.subject_id)
         .join(m.Term, m.Term.id == m.Score.term_id).filter(m.Score.learner_id == l.id, m.Score.school_id == l.school_id))
    return analytics.trends([dict(subject=s.name, term=t.name, ord=t.ord, value=sc.value, max=sc.max, status=sc.status) for sc, s, t in q])

def dump(d):
    return dict(id=d.id, learner_id=d.learner_id, status=d.status, provider=d.provider, content=d.content, evidence=d.evidence,
                final_content=d.final_content, note=d.note, created_at=str(d.created_at), reviewed_at=str(d.reviewed_at) if d.reviewed_at else None)

class Login(BaseModel): email: str; password: str
class NewLearner(BaseModel): name: str; code: Optional[str] = None; class_id: int
class Review(BaseModel):
    action: Literal["approve", "reject", "revise"]; content: Optional[str] = None; note: Optional[str] = None

@r.post("/auth/login")
def login(b: Login, db=Depends(db_dep)):
    u = db.query(m.User).filter(m.User.email == b.email.lower().strip()).first()
    if not u or not security.check_pw(b.password, u.pw): raise HTTPException(401, "Email or password is incorrect.")
    audit(db, u, "login")
    return {"token": security.make_token(u.id), "user": dict(id=u.id, name=u.name, role=u.role)}

@r.get("/me")
def me(u=Depends(current)): return dict(id=u.id, name=u.name, role=u.role)

@r.get("/dashboard")
def dashboard(u=Depends(current), db=Depends(db_dep)):
    ls = visible(db, u).all(); ids = [l.id for l in ls]
    sc = db.query(m.Score).filter(m.Score.learner_id.in_(ids)).all() if ids else []
    scored = [s for s in sc if s.status == "scored" and s.value is not None]
    ks = db.query(m.Klass).filter(m.Klass.school_id == u.school_id)
    if u.role == "teacher": ks = ks.filter(m.Klass.teacher_id == u.id)
    classes = []
    for k in ks.all():
        v = [s.value / s.max * 100 for s in scored if next((l for l in ls if l.id == s.learner_id and l.class_id == k.id), None)]
        classes.append(dict(name=k.name, learners=sum(1 for l in ls if l.class_id == k.id), average=round(sum(v) / len(v), 1) if v else None))
    pending = db.query(m.Draft).filter(m.Draft.learner_id.in_(ids), m.Draft.status.in_(["draft", "revision"])).count() if ids else 0
    due = db.query(m.Plan).filter(m.Plan.learner_id.in_(ids), m.Plan.status == "open", m.Plan.follow_up <= dt.date.today()).count() if ids else 0
    att = [a for a in db.query(m.Attendance).filter(m.Attendance.learner_id.in_(ids)).all() if a.status != "excused"] if ids else []
    rate = round(100 * sum(a.status in ("present", "late") for a in att) / len(att), 1) if att else None
    return dict(learners=len(ls), classes=len(classes), subjects=db.query(m.Subject).filter(m.Subject.school_id == u.school_id).count(),
                assessment_completion=round(100 * len(scored) / len(sc), 1) if sc else None, pending_reviews=pending, follow_ups_due=due, attendance_rate=rate, class_summaries=classes)

@r.get("/learners")
def learners(search: str = "", u=Depends(current), db=Depends(db_dep)):
    q = visible(db, u)
    if search: q = q.filter(m.Learner.name.ilike(f"%{search}%"))
    out = []
    for l in q.order_by(m.Learner.name).all():
        k = db.get(m.Klass, l.class_id)
        out.append(dict(id=l.id, name=l.name, code=l.code, class_name=k.name if k else None, attention=len(learner_trends(db, l)["flags"])))
    return out

@r.post("/learners")
def add_learner(b: NewLearner, u=Depends(need("school_admin")), db=Depends(db_dep)):
    k = db.get(m.Klass, b.class_id)
    if not k or k.school_id != u.school_id: raise HTTPException(404, "Class not found.")
    l = m.Learner(school_id=u.school_id, class_id=k.id, name=b.name.strip(), code=b.code); db.add(l); db.commit()
    audit(db, u, "learner.create", str(l.id)); return dict(id=l.id)

@r.get("/learners/{lid}")
def learner(lid: int, u=Depends(current), db=Depends(db_dep)):
    l = get_learner(db, u, lid); k = db.get(m.Klass, l.class_id)
    p = db.query(m.Profile).filter(m.Profile.learner_id == l.id).first()
    ds = db.query(m.Draft).filter(m.Draft.learner_id == l.id).order_by(m.Draft.id.desc()).all()
    return dict(id=l.id, name=l.name, code=l.code, class_name=k.name if k else None, trends=learner_trends(db, l),
                profile=dict(content=p.content, updated_at=str(p.updated_at)) if p else None, drafts=[dump(d) for d in ds])

@r.post("/learners/{lid}/drafts")
def new_draft(lid: int, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    l = get_learner(db, u, lid); res = ai.draft(l.name, learner_trends(db, l))
    d = m.Draft(school_id=u.school_id, learner_id=l.id, created_by=u.id, provider=res["provider"], content=res["text"], evidence=res["evidence"])
    db.add(d); db.commit(); audit(db, u, "draft.create", f"draft {d.id} learner {l.id} via {d.provider}")
    return dump(d)

@r.get("/drafts")
def drafts(status: str = "draft", u=Depends(current), db=Depends(db_dep)):
    ids = [l.id for l in visible(db, u).all()]
    ds = db.query(m.Draft).filter(m.Draft.learner_id.in_(ids), m.Draft.status == status).order_by(m.Draft.id.desc()).all() if ids else []
    return [dict(dump(d), learner_name=db.get(m.Learner, d.learner_id).name) for d in ds]

@r.post("/drafts/{did}/review")
def review(did: int, b: Review, u=Depends(need(*WRITERS)), db=Depends(db_dep)):
    d = db.get(m.Draft, did)
    if not d or d.school_id != u.school_id: raise HTTPException(404, "Draft not found.")
    get_learner(db, u, d.learner_id)
    if d.status not in ("draft", "revision"): raise HTTPException(409, "This draft has already been reviewed.")
    d.reviewed_by, d.reviewed_at, d.note = u.id, m.now(), b.note
    d.status = {"approve": "approved", "reject": "rejected", "revise": "revision"}[b.action]
    edited = False
    if b.action == "approve":
        d.final_content = (b.content or d.content).strip(); edited = d.final_content != d.content.strip()
        p = db.query(m.Profile).filter(m.Profile.learner_id == d.learner_id).first() or m.Profile(school_id=d.school_id, learner_id=d.learner_id)
        p.content, p.draft_id, p.approved_by, p.updated_at = d.final_content, d.id, u.id, m.now(); db.add(p)
    db.commit(); audit(db, u, f"draft.{b.action}", f"draft {d.id} edited={edited}")
    return dump(d)

@r.get("/audit")
def audit_log(u=Depends(need("school_admin")), db=Depends(db_dep)):
    return [dict(at=str(a.at), user_id=a.user_id, action=a.action, detail=a.detail)
            for a in db.query(m.Audit).filter(m.Audit.school_id == u.school_id).order_by(m.Audit.id.desc()).limit(100)]
