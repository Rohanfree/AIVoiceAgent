# Automite AI — Intelligent Automation Platform

> AI-powered voice assistant management platform built with FastAPI + Firebase Firestore.

---

## 🚀 Quick Start

```bash
# 1. Clone and install
cd "AI Agent"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Firebase credentials, JWT secret, etc.

# 3. Seed Firestore (test client + admin user)
python3 seed_firestore.py

# 4. Run
python3 -m app.main
# Server: http://localhost:8090
# Docs:   http://localhost:8090/docs
```

### Docker

```bash
docker compose up --build -d
# Access at http://localhost:8090
```

---

## 🗂️ Project Structure

```
.
├── app/
│   ├── auth/                    # Authentication module
│   │   ├── jwt_handler.py       #   JWT creation + verification (dual-scope)
│   │   ├── password.py          #   Argon2 password hashing
│   │   └── dependencies.py      #   FastAPI Depends() for auth guards
│   ├── routers/
│   │   ├── agent_tools.py       #   /agent-tools/*  — Vapi tool-call endpoints
│   │   ├── vapi_webhook.py      #   /vapi/*         — Vapi webhooks
│   │   ├── auth_router.py       #   /automiteui/auth/*       — Login, register, refresh
│   │   ├── client_router.py     #   /automiteui/client-portal/* — Client dashboard API
│   │   ├── admin_router.py      #   /automiteui/mngr-sys-access-78/* — Hidden admin API
│   │   ├── extraction_router.py #   /automiteui/extraction/* — Extraction stubs
│   │   └── pages_router.py      #   /automiteui/pages/*      — HTML page serving
│   ├── schemas/
│   │   ├── auth_models.py       #   Auth request/response schemas
│   │   ├── extraction_models.py #   Extraction data models (future use)
│   │   ├── request_models.py    #   Agent-tools request schemas
│   │   ├── response_models.py   #   Agent-tools response schemas
│   │   └── vapi_models.py       #   Vapi webhook payload schemas
│   ├── services/
│   │   ├── availability_service.py
│   │   ├── booking_service.py
│   │   ├── call_log_service.py
│   │   ├── customer_service.py
│   │   └── vapi_service.py      #   Vapi assistant clone/update/toggle
│   ├── static/
│   │   ├── css/automite.css     #   Brand design system
│   │   └── js/app.js            #   Frontend JavaScript
│   ├── templates/
│   │   ├── base.html            #   Base layout
│   │   ├── login.html           #   Client login
│   │   ├── register.html        #   Client registration
│   │   ├── dashboard.html       #   Client dashboard
│   │   └── admin/
│   │       ├── login.html       #   Admin login
│   │       └── dashboard.html   #   Admin dashboard
│   ├── config.py                #   Pydantic Settings (loads .env)
│   ├── db.py                    #   Firebase Firestore client
│   └── main.py                  #   FastAPI app factory
├── .env.example                 #   Environment variable template
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── seed_firestore.py            #   Seeds test data + admin user
└── test_api.sh                  #   Curl-based API tests
```

---

## 🌐 Context Path Routing

All new routes live under `/automiteui` for easy nginx proxying:

| Context Path | Purpose |
|---|---|
| `/agent-tools/*` | Vapi AI tool-call endpoints (existing) |
| `/vapi/*` | Vapi webhook handler (existing) |
| `/automiteui/auth/*` | Authentication (login, register, refresh token) |
| `/automiteui/client-portal/*` | Client dashboard API (profile, appointments, call logs) |
| `/automiteui/mngr-sys-access-78/*` | Hidden admin panel (client management) |
| `/automiteui/extraction/*` | Intelligent extraction engine (stubs) |
| `/automiteui/pages/*` | Jinja2 HTML pages |
| `/automiteui/static/*` | Static CSS/JS assets |

### Nginx Example

```nginx
server {
    listen 80;
    server_name api.automite.ai;

    # Existing AI tool endpoints
    location /agent-tools/ {
        proxy_pass http://localhost:8090;
    }

    location /vapi/ {
        proxy_pass http://localhost:8090;
    }

    # All new Automite UI features
    location /automiteui/ {
        proxy_pass http://localhost:8090;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8090;
    }
}
```

---

## 🔐 Authentication

### Dual-Scope JWT

| Scope | Lifespan | Usage |
|---|---|---|
| `dashboard` | 15 min | Human sessions (client portal) |
| `tool` | 7 days | M2M communication (AI tool auth) |
| `admin:all` | 15 min | Admin panel |
| `refresh` | 7 days | Token rotation |

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/automiteui/auth/register` | — | Register user + clone Vapi assistant |
| `POST` | `/automiteui/auth/login` | — | Get access + refresh tokens |
| `POST` | `/automiteui/auth/refresh` | — | Rotate tokens |

### Admin Credentials (Change in Production!)

```
Username: automite_admin
Password: Aut0m!te@Secure#2026
```

Update in `.env`:
```env
ADMIN_USERNAME=your_secure_admin_name
ADMIN_PASSWORD=YourStr0ng!Pa$$word
```

Then re-run `python3 seed_firestore.py` to update Firestore.

---

## 📡 API Reference

### Agent Tools (existing — unchanged)

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent-tools/get-client-by-mobile` | Customer lookup by phone |
| `POST` | `/agent-tools/get-services-and-prices` | List services for a client |
| `POST` | `/agent-tools/check-availability` | Check appointment slot |
| `POST` | `/agent-tools/book-appointment` | Book an appointment |
| `POST` | `/agent-tools/save-call-log` | Save call log (legacy) |

### Client Portal (requires `dashboard` JWT)

| Method | Path | Description |
|---|---|---|
| `GET` | `/automiteui/client-portal/profile` | Get client profile |
| `PUT` | `/automiteui/client-portal/profile` | Update services/timings |
| `GET` | `/automiteui/client-portal/appointments` | List appointments |
| `GET` | `/automiteui/client-portal/call-logs` | List call logs |

### Admin (**hidden** — requires `admin:all` JWT)

| Method | Path | Description |
|---|---|---|
| `GET` | `/automiteui/mngr-sys-access-78/dashboard` | System overview |
| `GET` | `/automiteui/mngr-sys-access-78/clients` | List all clients |
| `PATCH` | `/automiteui/mngr-sys-access-78/clients/{id}/status` | Activate/deactivate |
| `PATCH` | `/automiteui/mngr-sys-access-78/clients/{id}/subscription` | Change tier |
| `POST` | `/automiteui/mngr-sys-access-78/clients` | Manual client add |
| `POST` | `/automiteui/mngr-sys-access-78/refresh-tool-tokens` | Rotate M2M tokens |

### Extraction Engine (stubs — coming soon)

| Method | Path | Status |
|---|---|---|
| `POST` | `/automiteui/extraction/parse-text` | 🚧 Coming soon |
| `POST` | `/automiteui/extraction/upload-file` | 🚧 Coming soon |
| `POST` | `/automiteui/extraction/confirm` | 🚧 Coming soon |

---

## 🎨 UI Pages

| URL | Description |
|---|---|
| `/automiteui/pages/login` | Client login page |
| `/automiteui/pages/register` | Client registration |
| `/automiteui/pages/dashboard` | Client dashboard |
| `/automiteui/pages/mngr-sys-access-78` | Admin login (hidden) |
| `/automiteui/pages/mngr-sys-access-78/dashboard` | Admin dashboard (hidden) |

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FIREBASE_CREDENTIAL_PATH` | Firebase service account JSON | `./firebase-service-account.json` |
| `CLIENT_ID` | Default business client ID | `default-client` |
| `APP_ENV` | `development` or `production` | `production` |
| `HOST` / `PORT` | Server binding | `0.0.0.0:8090` |
| `JWT_SECRET_KEY` | JWT signing key (64 char hex) | — |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan | `7` |
| `ADMIN_USERNAME` | Admin login identifier | `automite_admin` |
| `ADMIN_PASSWORD` | Admin login password | `Aut0m!te@Secure#2026` |
| `VAPI_API_KEY` | Vapi platform API key | — |
| `VAPI_TEMPLATE_ASSISTANT_ID` | Template assistant to clone | `e8595039-...` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | — |
| `SECRET_KEY` | Fernet encryption key | — |
| `BASE_URL` | Public base URL for callbacks | `http://localhost:8090` |

---

## 🗄️ Firestore Collections

| Collection | Document ID Strategy |
|---|---|
| `clients` | `{vapi_assistant_id}` or `{uuid4}` |
| `users` | `{uuid4}` (admin = `"admin"`) |
| `customers` | `{client_id}_{phone}` |
| `appointments` | `{client_id}_{phone}_{datetime}` |
| `call_logs` | `{client_id}_{call_id}` |
| `tokens` | `{uuid4}` (audit log for M2M tokens) |

---

## 📋 TODO — Future Tasks

### Intelligent Extraction Engine (Phase 5)
- [ ] Integrate OpenAI / Gemini API for document parsing
- [ ] Implement multi-stage LLM pipeline with schema enforcement
- [ ] Add human-in-the-loop verification UI
- [ ] Build OCR support for PDF/image uploads
- [ ] Add confidence scoring and field highlighting

### Security Enhancements
- [ ] Implement refresh token revocation list (redis/firestore)
- [ ] Add rate limiting on auth endpoints
- [ ] Implement IP-based login anomaly detection
- [ ] Add TOTP/2FA for admin access

### Platform Features
- [ ] Google Calendar sync (OAuth flow exists in config)
- [ ] Subscription billing integration (Stripe/Razorpay)
- [ ] Email/SMS notification system
- [ ] Real-time call monitoring dashboard (WebSocket)
- [ ] Client-side service management UI (add/edit/delete services)

### Infrastructure
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Production docker-compose with nginx reverse proxy
- [ ] Monitoring with Prometheus + Grafana
- [ ] Firestore backup automation

---

## 📜 License

Proprietary — Automite AI. All rights reserved.
