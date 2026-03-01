# AI Receptionist — FastAPI Backend

A production-ready **FastAPI** backend for an AI Receptionist system integrated with **Retell AI** and **Firebase Firestore**.

---

## Tech Stack

- Python 3.11+
- FastAPI + Uvicorn
- Firebase Admin SDK (Firestore)
- Pydantic v2
- `python-dotenv`

---

## Project Structure

```
app/
├── main.py                   # App factory, CORS, debug middleware
├── config.py                 # Pydantic Settings
├── db.py                     # Firebase init + dependency injection
├── routers/
│   └── agent_tools.py        # All 5 /agent-tools endpoints
├── schemas/
│   ├── request_models.py
│   └── response_models.py
└── services/
    ├── customer_service.py
    ├── availability_service.py
    └── booking_service.py
```

---

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set FIREBASE_CREDENTIAL_PATH and APP_ENV in .env

uvicorn app.main:app --reload
```

Swagger UI → http://localhost:8090/docs

---

## Docker Deployment

To run the application using Docker:

### 1. Build and Run with Docker Compose (Recommended)

```bash
docker-compose up --build -d
```

### 2. Manual Docker Build

```bash
# Build the image
docker build -t ai-agent-api .

# Run the container
docker run -d \
  -p 8090:8090 \
  --name ai-agent-api \
  --env-file .env \
  -v $(pwd)/firebase-service-account.json:/app/firebase-service-account.json \
  ai-agent-api
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agent-tools/get-client-by-mobile` | Look up customer by phone |
| POST | `/agent-tools/get-services-and-prices` | List services & prices |
| POST | `/agent-tools/check-availability` | Check appointment slot |
| POST | `/agent-tools/book-appointment` | Create appointment |
| POST | `/agent-tools/save-call-log` | Persist Retell AI call log |
| GET  | `/health` | Liveness check |

---

## Debug Mode

Set `APP_ENV=development` in `.env` to enable:
- Full request/response JSON logged to stdout
- HTTP middleware with headers, body, and timing per request

Set `APP_ENV=production` to suppress all debug output.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FIREBASE_CREDENTIAL_PATH` | Path to Firebase service account JSON |
| `APP_ENV` | `development` or `production` |
| `HOST` | Server bind host (default `0.0.0.0`) |
| `PORT` | Server port (default `8000`) |
