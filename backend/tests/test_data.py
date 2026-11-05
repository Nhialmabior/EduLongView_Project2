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
    return {"Authorization": "Bearer " + c.post("/auth/login", json={"email": email, "password": PW}).json()["token"]}

def ids(c, h):
    return c.get("/classes", headers=h).json()[0]["id"], c.get("/subjects", headers=h).json()[0]["id"], c.get("/terms", headers=h).json()[0]["id"]

def test_setup_lists(c):
    a, t = H(c, "admin@demo.school"), H(c, "teacher1@demo.school")
    assert c.post("/subjects", json={"name": "Art"}, headers=t).status_code == 403
    assert c.post("/subjects", json={"name": "Art"}, headers=a).status_code == 200
    assert c.post("/subjects", json={"name": "art"}, headers=a).status_code == 409
    assert c.post("/terms", json={"name": "Y2 T2", "ord": 5}, headers=a).status_code == 200
    k = c.get("/classes", headers=a).json()[0]["id"]
    assert c.put(f"/classes/{k}", json={"name": "Form 1A East"}, headers=a).status_code == 200
    assert c.put(f"/classes/{k}", json={"teacher_id": 999}, headers=a).status_code == 404

def test_learner_edit_archive_restore(c):
    a = H(c, "admin@demo.school"); l = c.get("/learners", headers=a).json()[0]
    assert c.put(f"/learners/{l['id']}", json={"name": "Renamed Learner"}, headers=a).status_code == 200
    other = c.get("/learners", headers=a).json()[1]
    assert c.put(f"/learners/{l['id']}", json={"code": other["code"]}, headers=a).status_code == 409
    n = len(c.get("/learners", headers=a).json())
    assert c.post(f"/learners/{l['id']}/archive", headers=a).status_code == 200
    assert len(c.get("/learners", headers=a).json()) == n - 1
    assert [x["id"] for x in c.get("/archive/learners", headers=a).json()] == [l["id"]]
    assert c.post(f"/learners/{l['id']}/restore", headers=a).status_code == 200
    assert len(c.get("/learners", headers=a).json()) == n

def test_score_grid(c):
    t = H(c, "teacher1@demo.school"); cid, sid, tid = ids(c, t); q = f"class_id={cid}&subject_id={sid}&term_id={tid}"
    g = c.get(f"/scores/grid?{q}", headers=t).json(); assert len(g["entries"]) == 6
    a, b = g["entries"][0]["learner_id"], g["entries"][1]["learner_id"]
    body = {"subject_id": sid, "term_id": tid, "max": 100, "entries": [{"learner_id": a, "status": "scored", "value": 0}, {"learner_id": b, "status": "absent", "value": 55}]}
    assert c.put("/scores/grid", json=body, headers=t).json()["saved"] == 2
    e = {x["learner_id"]: x for x in c.get(f"/scores/grid?{q}", headers=t).json()["entries"]}
    assert e[a]["status"] == "scored" and e[a]["value"] == 0       # a true zero stays a zero
    assert e[b]["status"] == "absent" and e[b]["value"] is None    # absent keeps no number
    bad = dict(body, entries=[{"learner_id": a, "status": "scored", "value": 150}])
    assert c.put("/scores/grid", json=bad, headers=t).status_code == 422
    assert c.put("/scores/grid", json=dict(body, entries=[{"learner_id": a, "status": "scored"}]), headers=t).status_code == 422
    assert c.put("/scores/grid", json=body, headers=H(c, "reviewer@demo.school")).status_code == 403
    assert c.get(f"/scores/grid?{q}", headers=H(c, "teacher2@demo.school")).status_code == 404
    o = H(c, "teacher@other.school")
    assert c.put("/scores/grid", json=body, headers=o).status_code == 404   # subject belongs to another school

def test_class_register(c):
    t = H(c, "teacher1@demo.school"); cid = c.get("/classes", headers=t).json()[0]["id"]
    r = c.get(f"/attendance/register?class_id={cid}&day=2024-03-05", headers=t).json()
    assert len(r) == 6 and all(x["status"] is None for x in r)
    body = {"class_id": cid, "day": "2024-03-05", "entries": [{"learner_id": x["learner_id"], "status": "present"} for x in r]}
    assert c.put("/attendance/register", json=body, headers=t).json()["saved"] == 6
    assert all(x["status"] == "present" for x in c.get(f"/attendance/register?class_id={cid}&day=2024-03-05", headers=t).json())
    assert c.put("/attendance/register", json=dict(body, day="2999-01-01"), headers=t).status_code == 422
    assert c.put("/attendance/register", json=body, headers=H(c, "teacher2@demo.school")).status_code == 404

def test_import_learners(c):
    a = H(c, "admin@demo.school"); n = len(c.get("/learners", headers=a).json())
    bad = "name,class,code\nNew One,Form 1A East,9001\nGhost,No Such Class,9002\n"
    r = c.post("/import/learners", json={"text": bad, "dry_run": False}, headers=a).json()
    assert r["error_count"] == 1 and r["imported"] == 0 and len(c.get("/learners", headers=a).json()) == n   # nothing written
    good = "name,class,code\nNew One,Form 1A East,9001\nNew Two,Form 1B,9002\n"
    assert c.post("/import/learners", json={"text": good}, headers=a).json()["imported"] == 0                # dry run by default
    assert c.post("/import/learners", json={"text": good, "dry_run": False}, headers=a).json()["imported"] == 2
    assert len(c.get("/learners", headers=a).json()) == n + 2
    assert c.post("/import/learners", json={"text": "name\nX\n"}, headers=a).status_code == 422
    assert c.post("/import/learners", json={"text": good}, headers=H(c, "teacher1@demo.school")).status_code == 403

def test_import_blank_means_missing(c):
    t = H(c, "teacher1@demo.school"); code = c.get("/learners", headers=t).json()[0]["code"]
    assert c.post("/import/scores", json={"text": f"learner_code,subject,term,value\n{code},History,Y1 T1,\n", "dry_run": False}, headers=t).json()["imported"] == 1
    cid, _, tid = ids(c, t); hid = {x["name"]: x["id"] for x in c.get("/subjects", headers=t).json()}["History"]
    e = c.get(f"/scores/grid?class_id={cid}&subject_id={hid}&term_id={tid}", headers=t).json()["entries"][0]
    assert e["status"] == "missing" and e["value"] is None

def test_import_scores(c):
    t = H(c, "teacher1@demo.school"); code = c.get("/learners", headers=t).json()[0]["code"]
    bad = f"learner_code,subject,term,value,status\n{code},Maths,Y1 T1,,scored\n{code},Maths,Y1 T2,70,\n"
    r = c.post("/import/scores", json={"text": bad, "dry_run": False}, headers=t).json()
    assert r["error_count"] == 1 and r["imported"] == 0 and "never treated as zero" in r["errors"][0]
    good = f"learner_code,subject,term,value,status\n{code},Maths,Y1 T1,0,\n{code},English,Y1 T1,,absent\n{code},Science,Y1 T1,45,scored\n"
    assert c.post("/import/scores", json={"text": good, "dry_run": False}, headers=t).json()["imported"] == 3
    cid, _, _ = ids(c, t); subs = {s["name"]: s["id"] for s in c.get("/subjects", headers=t).json()}; tid = c.get("/terms", headers=t).json()[0]["id"]
    ent = c.get(f"/scores/grid?class_id={cid}&subject_id={subs['Maths']}&term_id={tid}", headers=t).json()["entries"][0]
    assert ent["status"] == "scored" and ent["value"] == 0
    ent = c.get(f"/scores/grid?class_id={cid}&subject_id={subs['English']}&term_id={tid}", headers=t).json()["entries"][0]
    assert ent["status"] == "absent" and ent["value"] is None
    other = "learner_code,subject,term,value\n1100,Maths,Y1 T1,50\n"   # a learner in teacher2's class
    assert c.post("/import/scores", json={"text": other}, headers=t).json()["error_count"] == 1