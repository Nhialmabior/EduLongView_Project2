# EduLongView

A teacher-support platform that shows how each learner develops across terms and years. Teachers stay in control: AI only prepares **drafts**, and nothing becomes an official record until an authorized person reviews and approves it.

Built with synthetic data only. Never load real learner data into a demo.

## Features
- Sign-in with roles (school admin, teacher, read-only reviewer), school-level data isolation, teachers limited to their own classes
- Login lockout, email-link password recovery, audit log, permanent learner deletion
- Learners, classes, subjects, terms, score entry grid, class attendance register, CSV import with a safe "check first" step
- Missing, absent and unassessed results are never treated as zero
- Longitudinal trends with a plain explanation of how every figure is calculated
- Transparent early-support indicators (decline, inconsistency, attendance), worded as prompts for teacher review, never as diagnoses
- AI-assisted draft summaries with a mandatory human review step (deterministic by default, optional Ollama)
- Support plans with follow-up dates, with observations kept separate from interpretations
- Reports as PDF and Excel: learner reports, score spread, term comparison, academic year comparison, subject and attendance reports. Learners are never ranked.

## Tech
Python, FastAPI, SQLAlchemy, Alembic, Pandas, NumPy, Pytest. React, TypeScript, Vite. SQLite for development, PostgreSQL for production.

## Run locally (Windows PowerShell)
Backend:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Frontend (second window):
```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```
Open the address that `npm run dev` prints (usually http://localhost:5173).

Demo accounts (password `demo-pass-123`): `teacher1@demo.school`, `teacher2@demo.school`, `admin@demo.school`, `reviewer@demo.school`.
Change or delete these accounts before any real use.

## Tests
```powershell
cd backend
python -m pytest -q
```

## Configuration (environment variables)
| Name | Purpose |
|---|---|
| `ENV` | Set to `production` online. Requires a strong `SECRET_KEY` and hides the API docs page |
| `SECRET_KEY` | Random text of 32+ characters. Never commit it |
| `DATABASE_URL` | PostgreSQL connection string in production |
| `CORS_ORIGINS` | Your frontend address, comma-separated |
| `FRONTEND_URL` | Used in password-reset links |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Email for password recovery |
| `AI_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL` | Optional local AI model |
| `VITE_API_URL` (frontend) | Address of the deployed backend |

## Deploying
1. Create a PostgreSQL database and set `DATABASE_URL`.
2. Backend: deploy the `backend` folder (see `render.yaml`), which runs `alembic upgrade head` on start.
3. Frontend: build with `npm run build` and host the `dist` folder, with `VITE_API_URL` set.
4. Check `/health`, then sign in.

Free hosting tiers may sleep when idle. Ollama cannot run on free hosting.

## Not built yet
Academic year and assessment-type fields in the database, class-level AI summaries, frontend automated tests, error monitoring, scheduled backups, and a live deployment.

## Responsible use
Indicators and AI drafts are suggestions for a teacher to review. They are not diagnoses and must not be used to rank learners or limit educational opportunities.