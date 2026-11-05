"""Password hashing, JWT helpers and production safety checks."""
import os, hashlib, hmac, datetime as dt, jwt

DEFAULT_SECRET = "dev-only-change-me"
SECRET = os.getenv("SECRET_KEY", DEFAULT_SECRET)
if os.getenv("ENV", "development").lower() == "production" and (SECRET == DEFAULT_SECRET or len(SECRET) < 32):
    raise RuntimeError("SECRET_KEY must be a random value of at least 32 characters when ENV=production.")

def _exp(**kw): return dt.datetime.now(dt.timezone.utc) + dt.timedelta(**kw)

def hash_pw(p, salt=None):
    salt = salt or os.urandom(16).hex()
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000).hex()

def check_pw(p, stored):
    return hmac.compare_digest(hash_pw(p, stored.split("$")[0]), stored)

def make_token(uid):
    return jwt.encode({"sub": str(uid), "exp": _exp(hours=8)}, SECRET, "HS256")

def read_token(t):
    data = jwt.decode(t, SECRET, ["HS256"])
    if "purpose" in data: raise ValueError("Wrong token type.")   # reset tokens can never act as sessions
    return int(data["sub"])

def make_reset_token(user):
    """Single-use: bound to the tail of the current password hash, so it stops working once the password changes."""
    return jwt.encode({"sub": str(user.id), "purpose": "reset", "pw": user.pw[-12:], "exp": _exp(minutes=30)}, SECRET, "HS256")

def read_reset_token(t):
    data = jwt.decode(t, SECRET, ["HS256"])
    if data.get("purpose") != "reset": raise ValueError("Wrong token type.")
    return int(data["sub"]), data["pw"]