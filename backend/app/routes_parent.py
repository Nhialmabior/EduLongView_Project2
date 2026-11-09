"""Parent portal and teacher-controlled results release."""
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from . import models as m
from .routes import db_dep, current, need, audit

p = APIRouter()


class GuardianLinkIn(BaseModel):
    guardian_user_id: int
    learner_id: int
    relationship: str = Field(min_length=2, max_length=40)
    consent_confirmed: bool = False


def _class_for_teacher(db, u, class_id):
    k = db.get(m.Klass, class_id)
    if not k or k.school_id != u.school_id or (u.role == "teacher" and k.teacher_id != u.id):
        raise HTTPException(404, "Class not found.")
    return k


@p.post("/guardian-links")
def create_guardian_link(b: GuardianLinkIn, u=Depends(need("school_admin")), db=Depends(db_dep)):
    if not b.consent_confirmed:
        raise HTTPException(422, "Record guardian consent before creating this link.")
    guardian = db.get(m.User, b.guardian_user_id)
    learner = db.get(m.Learner, b.learner_id)
    if not guardian or guardian.school_id != u.school_id or guardian.role != "parent":
        raise HTTPException(404, "Parent/guardian account not found.")
    if not learner or learner.school_id != u.school_id or learner.archived:
        raise HTTPException(404, "Learner not found.")
    if not learner.class_id:
        raise HTTPException(409, "Assign the learner to a class before linking a guardian.")
    existing = db.query(m.GuardianLink).filter_by(guardian_user_id=guardian.id, learner_id=learner.id).first()
    if existing:
        if existing.status != "revoked":
            raise HTTPException(409, "A guardian link already exists for this learner.")
        existing.relationship = b.relationship.strip()
        existing.status = "pending"
        existing.consent_recorded = 1
        existing.consent_recorded_by = u.id
        existing.consent_recorded_at = m.now()
        existing.approved_by = existing.approved_at = existing.revoked_by = existing.revoked_at = None
        link = existing
    else:
        link = m.GuardianLink(school_id=u.school_id, guardian_user_id=guardian.id, learner_id=learner.id,
            relationship=b.relationship.strip(), status="pending", consent_recorded=1,
            consent_recorded_by=u.id, consent_recorded_at=m.now())
        db.add(link)
    db.commit()
    audit(db, u, "guardian_link.create", f"link {link.id} learner {learner.id} guardian {guardian.id}")
    return {"id": link.id, "status": link.status}


@p.post("/guardian-links/{link_id}/approve")
def approve_guardian_link(link_id: int, u=Depends(need("school_admin")), db=Depends(db_dep)):
    link = db.get(m.GuardianLink, link_id)
    if not link or link.school_id != u.school_id:
        raise HTTPException(404, "Guardian link not found.")
    if link.status != "pending" or not link.consent_recorded:
        raise HTTPException(409, "Only pending links with recorded consent can be approved.")
    link.status, link.approved_by, link.approved_at = "approved", u.id, m.now()
    db.commit()
    audit(db, u, "guardian_link.approve", f"link {link.id} learner {link.learner_id}")
    return {"id": link.id, "status": link.status}


@p.post("/guardian-links/{link_id}/revoke")
def revoke_guardian_link(link_id: int, u=Depends(need("school_admin")), db=Depends(db_dep)):
    link = db.get(m.GuardianLink, link_id)
    if not link or link.school_id != u.school_id:
        raise HTTPException(404, "Guardian link not found.")
    if link.status != "approved":
        raise HTTPException(409, "Only approved links can be revoked.")
    link.status, link.revoked_by, link.revoked_at = "revoked", u.id, m.now()
    db.commit()
    audit(db, u, "guardian_link.revoke", f"link {link.id} learner {link.learner_id}")
    return {"id": link.id, "status": link.status}


@p.get("/parent/children")
def parent_children(u=Depends(need("parent")), db=Depends(db_dep)):
    links = db.query(m.GuardianLink).filter_by(school_id=u.school_id, guardian_user_id=u.id, status="approved").all()
    out = []
    for link in links:
        learner = db.get(m.Learner, link.learner_id)
        if not learner or learner.archived:
            continue
        klass = db.get(m.Klass, learner.class_id) if learner.class_id else None
        out.append({"id": learner.id, "name": learner.name, "class_name": klass.name if klass else None,
                    "relationship": link.relationship})
    return out


@p.get("/parent/children/{learner_id}/results")
def parent_results(learner_id: int, term_id: int, u=Depends(need("parent")), db=Depends(db_dep)):
    link = db.query(m.GuardianLink).filter_by(school_id=u.school_id, guardian_user_id=u.id,
        learner_id=learner_id, status="approved").first()
    if not link:
        raise HTTPException(404, "Released results not found.")
    learner = db.get(m.Learner, learner_id)
    if not learner or learner.archived or not learner.class_id:
        raise HTTPException(404, "Released results not found.")
    release = db.query(m.ResultRelease).filter_by(school_id=u.school_id, class_id=learner.class_id,
        term_id=term_id, status="released").first()
    if not release:
        raise HTTPException(404, "Released results not found.")
    term = db.get(m.Term, term_id)
    if not term or term.school_id != u.school_id:
        raise HTTPException(404, "Released results not found.")
    rows = (db.query(m.Score, m.Subject).join(m.Subject, m.Subject.id == m.Score.subject_id)
        .filter(m.Score.school_id == u.school_id, m.Score.learner_id == learner.id, m.Score.term_id == term.id)
        .order_by(m.Subject.name).all())
    return {"learner": {"id": learner.id, "name": learner.name}, "term": {"id": term.id, "name": term.name},
        "released_at": str(release.released_at),
        "results": [{"subject": subject.name, "value": score.value, "max": score.max, "status": score.status}
                    for score, subject in rows]}


@p.post("/classes/{class_id}/terms/{term_id}/release")
def release_results(class_id: int, term_id: int, u=Depends(need("teacher", "school_admin")), db=Depends(db_dep)):
    klass = _class_for_teacher(db, u, class_id)
    term = db.get(m.Term, term_id)
    if not term or term.school_id != u.school_id:
        raise HTTPException(404, "Term not found.")
    release = db.query(m.ResultRelease).filter_by(class_id=klass.id, term_id=term.id).first()
    if release and release.status == "released":
        raise HTTPException(409, "Results for this class and term are already released.")
    if release:
        release.status, release.released_by, release.released_at = "released", u.id, m.now()
        release.withdrawn_by = release.withdrawn_at = None
    else:
        release = m.ResultRelease(school_id=u.school_id, class_id=klass.id, term_id=term.id,
            status="released", released_by=u.id, released_at=m.now())
        db.add(release)
    db.commit()
    audit(db, u, "results.release", f"class {klass.id} term {term.id}")
    return {"class_id": klass.id, "term_id": term.id, "status": release.status, "released_at": str(release.released_at)}


@p.post("/classes/{class_id}/terms/{term_id}/withdraw-release")
def withdraw_results(class_id: int, term_id: int, u=Depends(need("teacher", "school_admin")), db=Depends(db_dep)):
    klass = _class_for_teacher(db, u, class_id)
    release = db.query(m.ResultRelease).filter_by(school_id=u.school_id, class_id=klass.id, term_id=term_id).first()
    if not release or release.status != "released":
        raise HTTPException(409, "There is no active release to withdraw.")
    release.status, release.withdrawn_by, release.withdrawn_at = "withdrawn", u.id, m.now()
    db.commit()
    audit(db, u, "results.withdraw", f"class {klass.id} term {term_id}")
    return {"class_id": klass.id, "term_id": term_id, "status": release.status}
