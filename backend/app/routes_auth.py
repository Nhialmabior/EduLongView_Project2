"""Sign-in with lockout, and email-based password recovery."""
import os, smtplib, datetime as dt
from email.message import EmailMessage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from . import models as m, security
from .routes import db_dep, audit

a = APIRouter()
MAX_FAILS, WINDOW = 5, dt.timedelta(minutes=15)
DUMMY = security.hash_pw("not-a-real-password")   # makes unknown emails take as long as real ones

class Login(BaseModel): email: str; password: str
class Forgot(BaseModel): email: str
class Reset(BaseModel): token: str; password: str = Field(min_length=10)

def recent_fails(db, email):
    """Failed sign-ins in the last 15 minutes, counted only since the last success or password reset."""
    since = m.now() - WINDOW
    ok = db.query(m.Audit).filter(m.Audit.action.in_(["login", "lock.clear"]), m.Audit.detail == email).order_by(m.Audit.id.desc()).first()
    if ok and ok.at > since: since = ok.at
    return db.query(m.Audit).filter(m.Audit.action == "login.fail", m.Audit.detail == email, m.Audit.at > since).count()

@a.post("/auth/login")
def login(b: Login, db=Depends(db_dep)):
    email = b.email.lower().strip()[:200]
    if recent_fails(db, email) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Wait 15 minutes, or use Forgot password.")
    u = db.query(m.User).filter(m.User.email == email).first()
    if not u or not security.check_pw(b.password, u.pw):
        if not u: security.check_pw(b.password, DUMMY)
        db.add(m.Audit(school_id=u.school_id if u else None, user_id=u.id if u else None, action="login.fail", detail=email)); db.commit()
        raise HTTPException(401, "Email or password is incorrect.")
    db.add(m.Audit(school_id=u.school_id, user_id=u.id, action="login", detail=email)); db.commit()
    return {"token": security.make_token(u.id), "user": dict(id=u.id, name=u.name, role=u.role)}

def send_mail(to, subject, body):
    host = os.getenv("SMTP_HOST")
    if not host:
        if os.getenv("ENV", "development").lower() != "production": print(f"\n[email not configured; showing it here]\nTo: {to}\n{subject}\n{body}\n")
        return False
    msg = EmailMessage(); msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")); msg["To"] = to; msg["Subject"] = subject; msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        s.starttls()
        if os.getenv("SMTP_USER"): s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True

@a.post("/auth/forgot")
def forgot(b: Forgot, db=Depends(db_dep)):
    u = db.query(m.User).filter(m.User.email == b.email.lower().strip()).first()
    if u:
        link = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/#reset={security.make_reset_token(u)}"
        try: send_mail(u.email, "Reset your EduLongView password", f"Open this link within 30 minutes to choose a new password:\n\n{link}\n\nIf you did not ask for this, ignore this email.")
        except Exception: pass   # never reveal whether an account exists or whether sending worked
        audit(db, u, "password.reset_requested")
    return {"message": "If that email has an account, a reset link has been sent."}

@a.post("/auth/reset")
def reset(b: Reset, db=Depends(db_dep)):
    bad = HTTPException(400, "This reset link is invalid or has expired. Ask for a new one.")
    try: uid, tail = security.read_reset_token(b.token)
    except Exception: raise bad
    u = db.get(m.User, uid)
    if not u or u.pw[-12:] != tail: raise bad
    u.pw = security.hash_pw(b.password); db.add(m.Audit(school_id=u.school_id, user_id=u.id, action="lock.clear", detail=u.email)); db.commit()
    audit(db, u, "password.reset"); return {"ok": True}