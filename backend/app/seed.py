"""Synthetic demo data only. Run: python -m app.seed"""
import random, datetime as dt
from . import models as m
from .security import hash_pw
PW = "demo-pass-123"
SUBJECTS = ["Maths", "English", "Science", "History"]
TERMS = ["Y1 T1", "Y1 T2", "Y1 T3", "Y2 T1"]

def weekdays(n=40):
    d, out = dt.date.today(), []
    while len(out) < n:
        if d.weekday() < 5: out.append(d)
        d -= dt.timedelta(days=1)
    return out

def populate(db, school, klasses, rnd, forced=False):
    rnd2 = random.Random(7)
    subs = [m.Subject(school_id=school.id, name=n) for n in SUBJECTS]
    terms = [m.Term(school_id=school.id, name=n, ord=i + 1) for i, n in enumerate(TERMS)]
    db.add_all(subs + terms); db.flush()
    for ci, k in enumerate(klasses):
        for i in range(6):
            l = m.Learner(school_id=school.id, class_id=k.id, code=f"{school.id}{ci}{i:02d}", name=f"Learner {chr(65 + i)}{ci + 1}-{school.id}")
            db.add(l); db.flush()
            for s in subs:
                base, slope = rnd.uniform(45, 85), rnd.uniform(-3, 4)
                for ti, t in enumerate(terms):
                    v, st, r = min(100, max(0, base + slope * ti + rnd.gauss(0, 4))), "scored", rnd.random()
                    if r < .04: v, st = None, "absent"
                    elif r < .07: v, st = None, "missing"
                    elif r < .09: v, st = None, "unassessed"
                    if forced and ci == 0 and i == 0 and s.name == "Maths":
                        v, st = [72, 64, 57, 49][ti], "scored"
                    db.add(m.Score(school_id=school.id, learner_id=l.id, subject_id=s.id, term_id=t.id, value=v, status=st))
            for idx, day in enumerate(weekdays()):
                if forced and ci == 0 and i == 0: stt = "absent" if idx % 4 == 0 else "present"
                else: stt = rnd2.choices(["present", "late", "absent", "excused"], [88, 4, 6, 2])[0]
                db.add(m.Attendance(school_id=school.id, learner_id=l.id, day=day, status=stt))

def seed(db):
    rnd = random.Random(42)
    s1, s2 = m.School(name="Demo Secondary School"), m.School(name="Other Demo School")
    db.add_all([s1, s2]); db.flush()
    def user(s, email, name, role):
        u = m.User(school_id=s.id, email=email, name=name, role=role, pw=hash_pw(PW)); db.add(u); return u
    user(s1, "admin@demo.school", "Ada Admin", "school_admin"); rev = user(s1, "reviewer@demo.school", "Rae Reviewer", "reviewer")
    t1, t2, o = user(s1, "teacher1@demo.school", "Tom Teacher", "teacher"), user(s1, "teacher2@demo.school", "Tia Teacher", "teacher"), user(s2, "teacher@other.school", "Olu Other", "teacher")
    db.flush()
    k1, k2 = m.Klass(school_id=s1.id, name="Form 1A", teacher_id=t1.id), m.Klass(school_id=s1.id, name="Form 1B", teacher_id=t2.id)
    ko = m.Klass(school_id=s2.id, name="Other 1A", teacher_id=o.id)
    db.add_all([k1, k2, ko]); db.flush()
    populate(db, s1, [k1, k2], rnd, forced=True); populate(db, s2, [ko], rnd)
    first = db.query(m.Learner).filter(m.Learner.school_id == s1.id).first()
    p = m.Plan(school_id=s1.id, learner_id=first.id, title="Maths catch-up", goal="Rebuild confidence with fractions", follow_up=dt.date.today() - dt.timedelta(days=2), created_by=t1.id)
    db.add(p); db.flush()
    db.add_all([m.PlanNote(school_id=s1.id, plan_id=p.id, kind="observation", text="Left 3 of 5 fraction questions blank in the last test.", by=t1.id),
                m.PlanNote(school_id=s1.id, plan_id=p.id, kind="interpretation", text="May be avoiding questions after an early mistake.", by=t1.id)])
    db.commit()

if __name__ == "__main__":
    if m.URL.startswith("sqlite"): m.Base.metadata.create_all(m.engine)
    with m.Session() as db:
        if db.query(m.School).count() == 0:
            seed(db); print("Seeded synthetic data. Demo password:", PW)
        else:
            print("Database already has data; nothing seeded.")
