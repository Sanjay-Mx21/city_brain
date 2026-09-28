# Production Setup

City Brain runs locally on SQLite for demos. Production uses PostgreSQL.
The quickest way to deploy is Docker Compose, described in the [README](../README.md).

## Manual backend setup (without Docker)

1. Create a PostgreSQL database named `citybrain`.
2. Copy `backend/.env.example` to `backend/.env`.
3. Set:

```env
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://citybrain_user:strong_password@localhost:5432/citybrain
DATABASE_URL_SYNC=postgresql://citybrain_user:strong_password@localhost:5432/citybrain
JWT_SECRET=<long random secret, 32+ chars>
SECRET_KEY=<different long random secret, 32+ chars>
FRONTEND_URL=https://your-frontend-domain
```

The API refuses to start in production if these secrets are missing or weak.

4. Install dependencies and seed:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\init_db.py
$env:SEED_ADMIN_PASSWORD="..."; $env:SEED_OFFICER_PASSWORD="..."
.\.venv\Scripts\python.exe scripts\seed_data.py
```

5. Run it behind a reverse proxy (nginx or Caddy) that handles TLS:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

## Frontend

```bash
cd frontend
npm ci
npm run build        # outputs dist/
```

Serve `dist/` with SPA fallback to `index.html`, and proxy `/api/` and `/uploads/` to the backend.
`frontend/nginx/default.conf.template` is a ready-made config. If the API is on a different domain, build with `VITE_API_BASE_URL=https://api-domain/api/v1` and add the frontend's origin to `FRONTEND_URL` or `CORS_ORIGINS` on the backend.

## Database schema changes

Tables are created automatically at startup (`create_all`). This covers a fresh database, but it does **not** alter existing tables. Before changing models on a live database, add Alembic migrations.

## WhatsApp (currently disabled)

To enable, set `WHATSAPP_ENABLED=true` and the Twilio credentials, then point the Twilio inbound webhook at:

```text
POST https://your-api-domain/api/v1/whatsapp/webhook
```

Before enabling it in production, the webhook needs Twilio request-signature validation, and WhatsApp-created accounts must not share a fixed password.

## Image Verification

The current verifier is a lightweight local evidence check. Replace
`backend/app/services/image_verification_service.py` with a YOLO/Faster R-CNN implementation when a trained model is available.
