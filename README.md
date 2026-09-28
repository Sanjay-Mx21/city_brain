# City Brain

AI-powered civic complaint system for Bengaluru. Citizens describe issues in plain language (English, Kannada or Hindi, typed or spoken). The system splits the text into separate tickets, sends each ticket to the right department and tracks SLAs. Officers and admins manage everything from dashboards.

| Part | Stack |
|---|---|
| `backend/` | FastAPI, SQLAlchemy (async), PostgreSQL or SQLite, JWT auth |
| `frontend/` | React 18, Vite, Tailwind, Leaflet, Recharts |
| AI | Local LLM via Ollama (optional; falls back to a rule-based parser), faster-whisper for voice |

WhatsApp intake is **disabled** for now (`WHATSAPP_ENABLED=false`).

---

## Deploy with Docker Compose (recommended)

This runs PostgreSQL, the API and the nginx-served frontend together.

```bash
cp .env.example .env
# Fill in POSTGRES_PASSWORD, JWT_SECRET, SECRET_KEY, SEED_ADMIN_PASSWORD, SEED_OFFICER_PASSWORD
# Generate secrets:  python -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up -d --build
docker compose exec backend python scripts/seed_data.py   # first run only
```

The app is served at `http://<host>:8080`. nginx serves the SPA and proxies `/api` and `/uploads` to the backend. Put a TLS-terminating proxy (Caddy, Traefik, a cloud load balancer) in front, and set `FRONTEND_URL` to the public `https://` address.

Seeding creates departments, wards, one admin (`+919999900000`) and one officer per department (`+919999900001` …). Their passwords come from `SEED_ADMIN_PASSWORD` and `SEED_OFFICER_PASSWORD`. Set `SEED_DEMO_DATA=true` to also create demo citizens and complaints.

Persistent data is stored in the `pgdata` volume (database) and the `backend-data` volume (uploaded photos and the Whisper model cache). Back both up.

## Deploy frontend and backend separately (e.g. Vercel + Render/Railway)

**Backend** (Docker service using `backend/Dockerfile`, which respects `$PORT`). Set these environment variables:

```
APP_ENV=production
DEBUG=false
JWT_SECRET=<random 32+ chars>
SECRET_KEY=<random 32+ chars>
DATABASE_URL=<your Postgres URL>    # postgres:// URLs are accepted
FRONTEND_URL=https://your-frontend.example.com
```

Attach a persistent disk at `/app/data` so uploads survive restarts. Then run `python scripts/seed_data.py` once with `SEED_ADMIN_PASSWORD` and `SEED_OFFICER_PASSWORD` set.

**Frontend** (static build):

```
Build command:   npm run build
Output dir:      dist
Env var:         VITE_API_BASE_URL=https://your-api.example.com/api/v1
```

`frontend/vercel.json` already handles SPA routing on Vercel.

## Local development

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # Linux/macOS: .venv/bin/pip
cp .env.example .env
.venv/Scripts/python scripts/init_db.py
.venv/Scripts/python scripts/seed_data.py             # dev passwords: admin123 / officer123 / citizen123
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to :8000
```

Tests: `cd backend && .venv/Scripts/python -m pytest`

## Configuration notes

- With `APP_ENV=production`, the API **refuses to start** if `JWT_SECRET` or `SECRET_KEY` is weak or default, or if `DEBUG` is true.
- **LLM:** set `OPEN_SOURCE_LLM_URL` to an Ollama server. If it is unreachable, the built-in rule-based parser is used automatically.
- **Voice:** the first transcription downloads the Whisper model (`WHISPER_MODEL_SIZE`, default `small`, about 500 MB). It needs roughly 1–2 GB of RAM.
- **Uploads:** images are checked by file signature, stored under server-chosen names and limited to `MAX_IMAGE_UPLOAD_MB`.
- **Public tracking:** `/track/<ticket>` shows only the status. The citizen's text, GPS location and photo are visible only to the owner and to staff.

See [docs/PRODUCTION_SETUP.md](docs/PRODUCTION_SETUP.md) for more.
