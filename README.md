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
Python, FastAPI, SQLAlchemy, Alembic, Pandas, NumPy, Pytest. React, TypeScript, Vite. SQLite for development and synthetic previews; PostgreSQL for durable deployments.

## Run locally (Windows PowerShell)
Backend:
```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\activate
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
cd ../frontend
npm ci
npm run build
```

## Configuration (environment variables)
| Name | Purpose |
|---|---|
| `ENV` | Set to `production` online. Requires a strong `SECRET_KEY` and hides the API docs page |
| `SECRET_KEY` | Random text of 32+ characters. Never commit it |
| `DATABASE_URL` | PostgreSQL connection string for durable deployments. If omitted, the app uses local SQLite |
| `CORS_ORIGINS` | Your frontend origin, comma-separated |
| `FRONTEND_URL` | Used in password-reset links |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Email for password recovery |
| `AI_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL` | Optional local AI model |
| `VITE_API_URL` (frontend) | Address of the deployed backend |

## Deployment

### Current free preview architecture
- **GitHub** stores the source code and runs automated checks.
- **GitHub Pages** hosts the React frontend from the `main` branch.
- **Render** hosts the FastAPI backend using the root `render.yaml` Blueprint.
- The Render service is configured for automatic deployment after commits to its connected branch.
- The free preview uses SQLite only for synthetic demo data. Render free web services have an ephemeral filesystem, so local SQLite data can disappear after a restart, spin-down or redeploy.

To create or update the Render service, connect this repository in Render and use **Blueprint** deployment. Select the intended branch and confirm the `edulongview-api` web service. Render generates `SECRET_KEY`; do not commit secrets. The backend health endpoint is `/health`.

### Important free-tier limits
Render free web services sleep after 15 minutes without inbound traffic and can take about a minute to wake. Render free PostgreSQL expires after 30 days and does not include backups. For that reason, this Blueprint deliberately does **not** create a free Render database. Free hosting is for development and synthetic demonstrations, not real learner records.

Before any real school use, configure a persistent PostgreSQL database with backups, verify migrations and restore procedures, configure transactional email, complete a security/privacy review, and use a continuously available backend. Do not place real children's data in this free preview.

### Automated quality checks
GitHub Actions runs the backend test suite and frontend production build on pushes and pull requests. GitHub Pages deployment remains restricted to `main`; feature branches are validated without replacing the live site.

## Not built yet
Academic year and assessment-type fields in the database, class-level AI summaries, frontend automated tests, error monitoring, scheduled backups, guardian accounts, parent result release, learner accounts, practice quizzes, and a live production deployment.

## Responsible use
Indicators and AI drafts are suggestions for a teacher to review. They are not diagnoses and must not be used to rank learners or limit educational opportunities. Parent access must be limited to teacher-released information for a verified guardian-child relationship. Practice quiz results must remain separate from official assessment records.
