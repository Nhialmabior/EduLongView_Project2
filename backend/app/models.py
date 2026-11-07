"""Database engine and SQLAlchemy models. Every record carries school_id for tenant isolation."""
import os, datetime as dt
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, DateTime, JSON, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

URL = os.getenv("DATABASE_URL", "sqlite:///./edulongview.db")
for _p in ("postgres://", "postgresql://"):   # Render gives postgres://; SQLAlchemy 2.1 would then look for the newer psycopg driver
    if URL.startswith(_p): URL = "postgresql+psycopg2://" + URL[len(_p):]
kw = {}
if URL.startswith("sqlite"):
    kw["connect_args"] = {"check_same_thread": False}
    if URL in ("sqlite://", "sqlite:///:memory:"):
        kw["poolclass"] = StaticPool
engine = create_engine(URL, **kw)
Session = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
now = lambda: dt.datetime.utcnow()

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True); name = Column(String, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    email = Column(String, unique=True, nullable=False); name = Column(String)
    role = Column(String, nullable=False)  # platform_admin | school_admin | teacher | reviewer
    pw = Column(String, nullable=False)

class Klass(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False); teacher_id = Column(Integer, ForeignKey("users.id"))

class Learner(Base):
    __tablename__ = "learners"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id")); code = Column(String); name = Column(String, nullable=False)
    archived = Column(Integer, default=0)

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False); name = Column(String, nullable=False)

class Term(Base):
    __tablename__ = "terms"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False); ord = Column(Integer, nullable=False)

class Score(Base):
    """status: scored | absent | unassessed | missing. Only 'scored' rows hold a value; a true zero is value=0 with status scored."""
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=False)
    value = Column(Float); max = Column(Float, default=100); status = Column(String, default="scored")

class Draft(Base):
    """AI drafts live here, separate from official records (Profile)."""
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, nullable=False); learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id")); provider = Column(String)
    content = Column(Text); evidence = Column(JSON); status = Column(String, default="draft")  # draft|approved|rejected|revision
    reviewed_by = Column(Integer, ForeignKey("users.id")); reviewed_at = Column(DateTime)
    final_content = Column(Text); note = Column(Text); created_at = Column(DateTime, default=now)

class Profile(Base):
    """Official learner profile. Written only by the human approval endpoint."""
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, nullable=False); learner_id = Column(Integer, ForeignKey("learners.id"), unique=True)
    content = Column(Text); draft_id = Column(Integer, ForeignKey("drafts.id"))
    approved_by = Column(Integer, ForeignKey("users.id")); updated_at = Column(DateTime, default=now)

class Audit(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer); user_id = Column(Integer); action = Column(String); detail = Column(Text)
    at = Column(DateTime, default=now)

class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("learner_id", "day"),)
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, nullable=False); learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False)
    day = Column(Date, nullable=False); status = Column(String, nullable=False)  # present | late | absent | excused

class Plan(Base):
    """Learner support plan, written and owned by teachers."""
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, nullable=False); learner_id = Column(Integer, ForeignKey("learners.id"), nullable=False)
    title = Column(String, nullable=False); goal = Column(Text); follow_up = Column(Date)
    status = Column(String, default="open"); outcome = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id")); created_at = Column(DateTime, default=now)

class PlanNote(Base):
    """kind keeps facts (observation) apart from opinions (interpretation)."""
    __tablename__ = "plan_notes"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, nullable=False); plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    kind = Column(String, nullable=False); text = Column(Text, nullable=False)
    by = Column(Integer, ForeignKey("users.id")); at = Column(DateTime, default=now)
