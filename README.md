# 🧠 City Brain — AI-Powered Unified Civic Intelligence System

> One platform. Every civic problem. Any language. Zero confusion.

City Brain is a full-stack, AI-powered civic intelligence platform that unifies fragmented government complaint systems into a single, conversational, multilingual interface for citizens of Bengaluru.

## 🏗️ Architecture

```
city-brain/
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── api/routes/       # API endpoint handlers
│   │   ├── core/             # Config, DB, security
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic (LLM, classification, etc.)
│   │   └── utils/            # Helpers, constants
│   ├── scripts/              # Seed data, migrations
│   └── tests/                # Test suite
├── frontend/                 # React.js frontend
│   └── src/
│       ├── components/       # UI components (citizen, admin, officer)
│       ├── pages/            # Page-level components
│       ├── services/         # API client, WebSocket
│       └── utils/            # Helpers
└── docs/                     # Documentation
```

## 🚀 Quick Start (Windows — No Docker)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (install via https://www.postgresql.org/download/windows/)
- Redis (use Memurai for Windows: https://www.memurai.com/ OR use Upstash free cloud Redis)
- Git

### 1. Clone & Setup Environment

```bash
git clone https://github.com/yourusername/city-brain.git
cd city-brain
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Create .env file (copy from .env.example)
copy .env.example .env
# Fill in your API keys in .env

# Initialize database
python scripts/init_db.py
python scripts/seed_data.py

# Run backend
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 4. Access Points
- **Citizen Portal**: http://localhost:5173
- **Admin Dashboard**: http://localhost:5173/admin
- **Officer Portal**: http://localhost:5173/officer
- **API Docs**: http://localhost:8000/docs

## 🔑 Environment Variables

See `backend/.env.example` for all required variables.

## 📚 Tech Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| Frontend | React.js + TailwindCSS | Citizen portal + Admin dashboard |
| Backend | FastAPI (Python) | REST API, LLM orchestration |
| LLM | GPT-4 Turbo (OpenAI) | Complaint understanding + classification |
| Translation | Bhashini API | Kannada/Hindi → English |
| Speech-to-Text | OpenAI Whisper | Voice input transcription |
| WhatsApp | Twilio API | Citizen messaging |
| Database | PostgreSQL | Complaint storage, user data |
| Cache | Redis | Real-time updates, queues |
| Maps | Leaflet.js + OpenStreetMap | Heatmaps, location picker |

## 📄 License

Academic project — Ramaiah University of Applied Sciences, 2026
