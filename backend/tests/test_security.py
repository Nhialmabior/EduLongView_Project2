import os
os.environ["DATABASE_URL"] = "sqlite://"
import importlib, pytest
from fastapi.testclient import TestClient
from app.main import app
from app import models as m, security, routes_auth
from app.seed import seed, PW

@pytest.fixture(scope="module")
def c():
    m.Base.metadata.drop_all(m.engine); m.Base.metadata.create_all(m.engine)
    with m.Session() as db: seed(db)
    return TestClient(app)

def login(c, email, pw=PW): return c.post("/auth/login", json={"email": email, "password": pw})
def H(c, email): return {"Authorization": "Bearer " + login(c, email).json()["token"]}
def mkuser(c, email, pw):
    assert c.post("/users", json={"email": email, "name": "T", "role": "teacher", "password": pw}, headers=H(c, "admin@demo.school")).status_code == 200

def test_lockout_after_repeated_failures(c):
    mkuser(c, "lock@demo.school", "correct-horse-1")
    for _ in range(5): assert login(c, "lock@demo.school", "wrong-password").status_code == 401
    assert login(c, "lock@demo.school", "correct-horse-1").status_code == 429   # locked even with the right password
    assert login(c, "admin@demo.school").status_code == 200                      # other accounts unaffected

def test_success_clears_earlier_failures(c):
    mkuser(c, "clear@demo.school", "correct-horse-2")
    for _ in range(4): login(c, "clear@demo.school", "nope-nope-nope")
    assert login(c, "clear@demo.school", "correct-horse-2").status_code == 200
    for _ in range(4): assert login(c, "clear@demo.school", "nope-nope-nope").status_code == 401

def test_password_reset_flow(c, monkeypatch):
    sent = []; monkeypatch.setattr(routes_auth, "send_mail", lambda to, s, b: sent.append((to, b)) or True)
    a = c.post("/auth/forgot", json={"email": "nobody@nowhere.com"}); b = c.post("/auth/forgot", json={"email": "teacher2@demo.school"})
    assert a.json() == b.json() and len(sent) == 1                              # same answer whether or not the account exists
    token = sent[0][1].split("#reset=")[1].split()[0]
    assert c.post("/auth/reset", json={"token": token, "password": "short"}).status_code == 422
    assert c.post("/auth/reset", json={"token": token, "password": "brand-new-pass-1"}).status_code == 200
    assert login(c, "teacher2@demo.school", "brand-new-pass-1").status_code == 200
    assert c.post("/auth/reset", json={"token": token, "password": "another-pass-22"}).status_code == 400   # single use
    assert c.post("/auth/reset", json={"token": "garbage", "password": "another-pass-22"}).status_code == 400

def test_reset_clears_lockout(c, monkeypatch):
    sent = []; monkeypatch.setattr(routes_auth, "send_mail", lambda to, s, b: sent.append(b) or True)
    mkuser(c, "locked2@demo.school", "correct-horse-3")
    for _ in range(5): login(c, "locked2@demo.school", "wrong-password")
    assert login(c, "locked2@demo.school", "correct-horse-3").status_code == 429
    c.post("/auth/forgot", json={"email": "locked2@demo.school"}); token = sent[0].split("#reset=")[1].split()[0]
    assert c.post("/auth/reset", json={"token": token, "password": "fresh-start-pass-4"}).status_code == 200
    assert login(c, "locked2@demo.school", "fresh-start-pass-4").status_code == 200

def test_reset_token_is_not_a_session(c):
    with m.Session() as db: t = security.make_reset_token(db.query(m.User).filter(m.User.email == "admin@demo.school").first())
    assert c.get("/me", headers={"Authorization": "Bearer " + t}).status_code == 401

def test_security_headers(c):
    h = c.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["cache-control"] == "no-store"

def test_production_refuses_weak_secret(monkeypatch):
    with monkeypatch.context() as mp:
        mp.setenv("ENV", "production"); mp.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError): importlib.reload(security)
        mp.setenv("SECRET_KEY", "short")
        with pytest.raises(RuntimeError): importlib.reload(security)
        mp.setenv("SECRET_KEY", "x" * 40); importlib.reload(security)
    importlib.reload(security)

def test_permanent_erase(c):
    a = H(c, "admin@demo.school"); l = c.get("/learners", headers=a).json()[0]; path = f"/learners/{l['id']}/permanent"
    body = {"confirm_name": l["name"]}
    assert c.request("DELETE", path, json=body, headers=a).status_code == 409                                  # must archive first
    c.post(f"/learners/{l['id']}/archive", headers=a)
    assert c.request("DELETE", path, json={"confirm_name": "wrong"}, headers=a).status_code == 422
    assert c.request("DELETE", path, json=body, headers=H(c, "teacher1@demo.school")).status_code == 403
    assert c.request("DELETE", path, json=body, headers=a).status_code == 200
    with m.Session() as db:
        for model in (m.Score, m.Attendance, m.Plan, m.Draft, m.Profile): assert db.query(model).filter(model.learner_id == l["id"]).count() == 0
        assert db.get(m.Learner, l["id"]) is None
        log = [x for x in db.query(m.Audit).filter(m.Audit.action == "learner.erase")]
        assert log and all(l["name"] not in (x.detail or "") for x in log)