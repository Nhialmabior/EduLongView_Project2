import os
os.environ["DATABASE_URL"] = "sqlite://"
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import models as m
from app.seed import seed, PW

@pytest.fixture(scope="module")
def c():
    m.Base.metadata.drop_all(m.engine); m.Base.metadata.create_all(m.engine)
    with m.Session() as db: seed(db)
    return TestClient(app)

def H(c, email):
    t = c.post("/auth/login", json={"email": email, "password": PW}).json()["token"]
    return {"Authorization": "Bearer " + t}

def test_login_and_auth(c):
    assert c.post("/auth/login", json={"email": "admin@demo.school", "password": "wrong"}).status_code == 401
    assert c.get("/learners").status_code in (401, 403)

def test_teacher_sees_only_own_class(c):
    ls = c.get("/learners", headers=H(c, "teacher1@demo.school")).json()
    assert len(ls) == 6 and {l["class_name"] for l in ls} == {"Form 1A"}
    assert len(c.get("/learners", headers=H(c, "admin@demo.school")).json()) == 12

def test_school_isolation(c):
    other = c.get("/learners", headers=H(c, "teacher@other.school")).json()
    mine = c.get("/learners", headers=H(c, "teacher1@demo.school")).json()
    assert other and not ({o["id"] for o in other} & {x["id"] for x in mine})
    assert c.get(f"/learners/{mine[0]['id']}", headers=H(c, "teacher@other.school")).status_code == 404

def test_missing_is_never_zero_and_flag_raised(c):
    h = H(c, "teacher1@demo.school")
    lid = next(l["id"] for l in c.get("/learners", headers=h).json() if l["attention"] > 0)
    t = c.get(f"/learners/{lid}", headers=h).json()["trends"]
    assert any(f["type"] == "declining" for f in t["flags"])
    allpts = [p for s in c.get("/learners", headers=h).json() for p in c.get(f"/learners/{s['id']}", headers=h).json()["trends"]["subjects"] for p in p["points"]]
    assert all(p["pct"] is None for p in allpts if p["status"] != "scored")

def test_human_approval_flow(c):
    h = H(c, "teacher1@demo.school"); lid = c.get("/learners", headers=h).json()[0]["id"]
    d = c.post(f"/learners/{lid}/drafts", headers=h).json()
    assert d["status"] == "draft" and d["content"].startswith("DRAFT")
    assert c.get(f"/learners/{lid}", headers=h).json()["profile"] is None
    assert c.post(f"/learners/{lid}/drafts", headers=H(c, "reviewer@demo.school")).status_code == 403
    assert c.post(f"/drafts/{d['id']}/review", json={"action": "approve"}, headers=H(c, "reviewer@demo.school")).status_code == 403
    ok = c.post(f"/drafts/{d['id']}/review", json={"action": "approve", "content": "Edited by teacher."}, headers=h)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert c.get(f"/learners/{lid}", headers=h).json()["profile"]["content"] == "Edited by teacher."
    assert c.post(f"/drafts/{d['id']}/review", json={"action": "approve"}, headers=h).status_code == 409
    log = c.get("/audit", headers=H(c, "admin@demo.school")).json()
    assert any(a["action"] == "draft.approve" and "edited=True" in a["detail"] for a in log)

def test_dashboard_real_counts(c):
    d = c.get("/dashboard", headers=H(c, "admin@demo.school")).json()
    assert d["learners"] == 12 and d["classes"] == 2 and d["subjects"] == 4

# ---------- v0.2 ----------
def first_learner(c, email):
    h = H(c, email); return h, c.get("/learners", headers=h).json()[0]["id"]

def test_attendance_summary_and_flag(c):
    h, lid = first_learner(c, "teacher1@demo.school")
    a = c.get(f"/learners/{lid}/attendance", headers=h).json()
    assert a["total"] >= 40 and a["rate"] < 85 and a["flag"]
    assert c.put(f"/learners/{lid}/attendance", json={"day": "2999-01-01", "status": "present"}, headers=h).status_code == 422
    assert c.put(f"/learners/{lid}/attendance", json={"day": "2024-03-04", "status": "present"}, headers=H(c, "reviewer@demo.school")).status_code == 403
    assert c.put(f"/learners/{lid}/attendance", json={"day": "2024-03-04", "status": "late"}, headers=h).json()["total"] > a["total"]

def test_support_plan_flow_and_isolation(c):
    h, lid = first_learner(c, "teacher1@demo.school")
    ps = c.get(f"/learners/{lid}/plans", headers=h).json()
    assert ps and {n["kind"] for n in ps[0]["notes"]} == {"observation", "interpretation"}
    assert any(p["id"] == ps[0]["id"] for p in c.get("/plans/due", headers=h).json())
    assert c.get(f"/learners/{lid}/plans", headers=H(c, "teacher@other.school")).status_code == 404
    n = c.post(f"/plans/{ps[0]['id']}/notes", json={"kind": "observation", "text": "Completed 4 of 5 questions."}, headers=h)
    assert n.status_code == 200 and len(n.json()["notes"]) == 3
    assert c.post(f"/plans/{ps[0]['id']}/close", json={"outcome": "Improved to 60% on the follow-up quiz."}, headers=h).json()["status"] == "closed"
    assert c.post(f"/plans/{ps[0]['id']}/close", json={"outcome": "again"}, headers=h).status_code == 409
    assert c.get("/plans/due", headers=h).json() == []

def test_reports_and_access(c):
    h, lid = first_learner(c, "teacher1@demo.school")
    pdf = c.get(f"/reports/learner/{lid}.pdf", headers=h); xl = c.get(f"/reports/learner/{lid}.xlsx", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and xl.content[:2] == b"PK"
    assert c.get(f"/reports/learner/{lid}.pdf", headers=H(c, "reviewer@demo.school")).status_code == 200
    assert c.get(f"/reports/learner/{lid}.pdf", headers=H(c, "teacher@other.school")).status_code == 404
    cid = c.get("/classes", headers=h).json()[0]["id"]
    assert c.get(f"/reports/class/{cid}.xlsx", headers=h).content[:2] == b"PK"
    assert c.get(f"/reports/class/{cid}.xlsx", headers=H(c, "teacher2@demo.school")).status_code == 404

def test_user_management_and_password(c):
    a = H(c, "admin@demo.school"); body = {"email": "new@demo.school", "name": "New T", "role": "teacher", "password": "long-enough-pw1"}
    assert c.post("/users", json=body, headers=H(c, "teacher1@demo.school")).status_code == 403
    assert c.post("/users", json=body, headers=a).status_code == 200 and c.post("/users", json=body, headers=a).status_code == 409
    assert c.post("/users", json=dict(body, email="x@demo.school", password="short"), headers=a).status_code == 422
    assert c.post("/auth/login", json={"email": "new@demo.school", "password": "long-enough-pw1"}).status_code == 200
    h = {"Authorization": "Bearer " + c.post("/auth/login", json={"email": "new@demo.school", "password": "long-enough-pw1"}).json()["token"]}
    assert c.post("/auth/change-password", json={"old": "nope", "new": "another-long-pw2"}, headers=h).status_code == 403
    assert c.post("/auth/change-password", json={"old": "long-enough-pw1", "new": "another-long-pw2"}, headers=h).status_code == 200
    uid = next(u["id"] for u in c.get("/users", headers=a).json() if u["email"] == "new@demo.school")
    assert c.post(f"/users/{uid}/reset-password", json={"password": "reset-by-admin-3"}, headers=H(c, "teacher@other.school")).status_code in (403,)
    assert c.post(f"/users/{uid}/reset-password", json={"password": "reset-by-admin-3"}, headers=a).status_code == 200


def test_parent_portal_requires_approved_link_and_teacher_release(c):
    admin = H(c, "admin@demo.school")
    teacher = H(c, "teacher1@demo.school")
    parent_body = {"email": "guardian@demo.school", "name": "Demo Guardian", "role": "parent", "password": PW}
    assert c.post("/users", json=parent_body, headers=admin).status_code == 200
    parent = H(c, "guardian@demo.school")
    learner = c.get("/learners", headers=teacher).json()[0]
    terms = c.get("/terms", headers=admin).json()
    term_id = terms[0]["id"]
    link = {"guardian_user_id": c.get("/users", headers=admin).json()[-1]["id"],
            "learner_id": learner["id"], "relationship": "Parent", "consent_confirmed": True}
    assert c.post("/guardian-links", json=dict(link, consent_confirmed=False), headers=admin).status_code == 422
    pending = c.post("/guardian-links", json=link, headers=admin)
    assert pending.status_code == 200 and pending.json()["status"] == "pending"
    assert c.get("/parent/children", headers=parent).json() == []
    assert c.post(f"/guardian-links/{pending.json()['id']}/approve", headers=admin).json()["status"] == "approved"
    assert len(c.get("/parent/children", headers=parent).json()) == 1
    assert c.get(f"/parent/children/{learner['id']}/results?term_id={term_id}", headers=parent).status_code == 404
    assert c.get("/learners", headers=parent).json() == []
    assert c.get(f"/learners/{learner['id']}", headers=parent).status_code == 404
    class_id = c.get("/classes", headers=teacher).json()[0]["id"]
    assert c.post(f"/classes/{class_id}/terms/{term_id}/release", headers=H(c, "teacher2@demo.school")).status_code == 404
    assert c.post(f"/classes/{class_id}/terms/{term_id}/release", headers=teacher).status_code == 200
    assert c.get(f"/classes/{class_id}/terms/{term_id}/release-status", headers=teacher).json()["status"] == "released"
    result = c.get(f"/parent/children/{learner['id']}/results?term_id={term_id}", headers=parent)
    assert result.status_code == 200 and len(result.json()["results"]) == 4
    assert c.post(f"/classes/{class_id}/terms/{term_id}/withdraw-release", headers=teacher).status_code == 200
    assert c.get(f"/classes/{class_id}/terms/{term_id}/release-status", headers=teacher).json()["status"] == "withdrawn"
    assert c.get(f"/parent/children/{learner['id']}/results?term_id={term_id}", headers=parent).status_code == 404
    log = c.get("/audit", headers=admin).json()
    assert any(x["action"] == "results.release" for x in log)
    assert any(x["action"] == "results.withdraw" for x in log)
