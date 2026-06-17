# Production Setup

City Brain runs locally with SQLite for demos, but the report architecture targets PostgreSQL.

## Backend

1. Create a PostgreSQL database named `citybrain`.
2. Copy `backend/.env.example` to `backend/.env`.
3. Set:

```env
DATABASE_URL=postgresql+asyncpg://citybrain_user:strong_password@localhost:5432/citybrain
DATABASE_URL_SYNC=postgresql://citybrain_user:strong_password@localhost:5432/citybrain
DEBUG=false
JWT_SECRET=replace-with-a-long-random-secret
SECRET_KEY=replace-with-a-different-long-random-secret
```

4. Install dependencies and seed:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\init_db.py
.\.venv\Scripts\python.exe scripts\seed_data.py
```

5. Run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## WhatsApp

Set Twilio credentials in `.env`, then configure the Twilio Sandbox inbound webhook:

```text
POST https://your-api-domain/api/v1/whatsapp/webhook
```

Users can send a natural-language complaint or a ticket ID such as `CB-2026-00001`.

## Image Verification

The current verifier is a local lightweight evidence check. Replace
`backend/app/services/image_verification_service.py` with a YOLO/Faster R-CNN implementation when a trained model is available.
