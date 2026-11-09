import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import models as m
from .routes import r
from .routes_ext import x
from .routes_data import d
from .routes_auth import a
from .routes_parent import p

PROD = os.getenv("ENV", "development").lower() == "production"
app = FastAPI(title="EduLongView API", version="0.3.0", redoc_url=None,
              docs_url=None if PROD else "/docs", openapi_url=None if PROD else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"; resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"; resp.headers["Cache-Control"] = "no-store"
    return resp

if m.URL.startswith("sqlite"):  # PostgreSQL schemas come from `alembic upgrade head`
    m.Base.metadata.create_all(m.engine)
app.include_router(a)   # first on purpose: its /auth/login (with lockout) replaces the older one in routes.py
app.include_router(r)
app.include_router(x)
app.include_router(d)
app.include_router(p)

@app.get("/health")
def health(): return {"status": "ok"}