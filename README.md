# EduLongView v0.2

A teacher-support platform that shows learner progress across terms and keeps teachers in control:
AI only prepares **drafts**; nothing reaches the official profile until a teacher approves it.
Synthetic data only.

## What is built
- **Access:** login, hashed passwords, JWT sessions, roles (school_admin, teacher, reviewer), school-level isolation,
  teachers limited to their own classes (one rule: `backend/app/routes.py::visible`), user management, admin password reset,
  change-own-password, audit log.
- **Records:** learners, classes, subjects, terms, scores. Status separates scored / absent / unassessed / missing; a true zero is a real score.
- **Analytics (Pandas/NumPy):** percentage normalisation, per-subject trends, "how this is calculated" note, indicators for decline,
  inconsistency and low attendance, all worded as prompts for teacher review.
- **AI drafts + approval:** drafts stored apart from official profiles; teacher edits, approves, rejects or requests revision; reviewer and date recorded.
  Deterministic generator by default; optional Ollama (`AI_PROVIDER=ollama`) with automatic fallback.
- **Attendance** recording and summaries; **support plans** with follow-up dates, outcomes, and notes that separate observations from interpretations.
- **Dashboard** from real database rows (learners, classes, subjects, assessment completion, drafts to review, follow-ups due, attendance).
- **Reports:** learner PDF and Excel, class Excel. Only teacher-approved profile text is exported; never unreviewed drafts.
- **Frontend:** React + TypeScript + Vite (login, dashboard, learners, learner profile with chart, attendance, plans, reports, review queue, admin).
- **Database:** SQLite for development, PostgreSQL for production, Alembic baseline migration.
- **Tests:** 10 Pytest tests (auth, isolation, missing data, approval flow, attendance, plans, reports, users).

## Not built yet (honest list)
Tailwind (plain CSS is used), frontend automated tests, LangGraph and MCP workflows, scikit-learn models (indicators are rule-based on purpose),
email-based password recovery (admin reset only), term/academic-year report types beyond the learner and class reports, rate limiting, error monitoring.
Nothing is deployed yet.

## Run locally
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # set SECRET_KEY to a long random string
python -m app.seed                                     # synthetic data
uvicorn app.main:app --reload                          # API docs: http://localhost:8000/docs
python -m pytest -q                                    # tests
```
```bash
cd frontend
cp .env.example .env
npm install && npm run dev                             # http://localhost:5173
```
Demo logins (password `demo-pass-123`): teacher1@demo.school, teacher2@demo.school, admin@demo.school, reviewer@demo.school, teacher@other.school.
Open the first learner in Form 1A: it shows a maths decline, low attendance and an overdue support plan.
Change or remove demo accounts before real use.

## Deploy
1. Create a PostgreSQL database (Render, Neon or Supabase). Free tiers may sleep or expire; check current terms.
2. Backend on Render using `render.yaml` (runs `alembic upgrade head`). Set `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`.
   For a demo only, run `python -m app.seed` once in the Render shell. Never load real learner data into a demo.
3. Frontend on Netlify: base `frontend`, build `npm run build`, publish `dist`, env `VITE_API_URL` = backend URL.
4. Check `<backend>/health`, then sign in from the deployed frontend.
5. Backups: enable your database provider's automated backups. Rollback: redeploy the previous Render/Netlify build and, if needed, `alembic downgrade -1`.
Free backends sleep when idle, so the first request can be slow. Ollama cannot run on free hosting; the live site uses deterministic drafts.
