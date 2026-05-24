# Automite AI — Intelligent Automation Platform

> AI-powered automation platform built with FastAPI + Firebase Firestore.

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
# Docs:   http://localhost:8090/automiteaiapplication/docs
```

### Docker (Production)

```bash
docker compose up --build -d
# Access at http://localhost:8090
```

### Docker (Test Environment)

The repo includes a separate `docker-compose.test.yml` for running a test instance alongside production with no container name or port conflicts.

```bash
# 1. Add your test Firebase service account
cp firebase-service-account-test.json.example firebase-service-account-test.json
# Edit firebase-service-account-test.json with your test project credentials

# 2. Configure the test .env
cp .env.example .env
# Set FIREBASE_CREDENTIAL_PATH=./firebase-service-account-test.json
# Set APP_ENV=development
# Set BASE_URL=https://dev.auto-mite.com/

# 3. Start the test container
docker compose -f docker-compose.test.yml up --build -d
# Access at http://localhost:8091
```

| Setting | Production (`docker-compose.yml`) | Test (`docker-compose.test.yml`) |
|---|---|---|
| Container name | `ai-agent-api` | `ai-agent-api-test` |
| Host port | `8090` | `8091` |
| Firebase credentials | `firebase-service-account.json` | `firebase-service-account-test.json` |
| Public URL | `https://auto-mite.com/` | `https://dev.auto-mite.com/` |

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
│   │   ├── auth_router.py       #   /automiteaiapplication/automiteui/auth/*
│   │   ├── client_router.py     #   /automiteaiapplication/automiteui/client-portal/*
│   │   ├── admin_router.py      #   /automiteaiapplication/automiteui/mngr-sys-access-78/*
│   │   ├── extraction_router.py #   /automiteaiapplication/automiteui/extraction/*
│   │   ├── pages_router.py      #   /automiteaiapplication/automiteui/pages/*
│   │   ├── contact_router.py    #   /automiteaiapplication/automiteui/contact/*
│   │   └── google_auth_router.py#   /automiteaiapplication/client/auth/google/*
│   ├── schemas/
│   │   ├── auth_models.py       #   Auth request/response schemas
│   │   ├── extraction_models.py #   Extraction data models
│   │   ├── request_models.py    #   General request schemas
│   │   └── response_models.py   #   General response schemas
│   ├── services/
│   │   ├── availability_service.py  #   Appointment slot checking
│   │   ├── booking_service.py       #   Appointment creation & call log
│   │   ├── calendar_service.py      #   Google Calendar sync
│   │   ├── customer_service.py      #   Customer record management
│   │   ├── sheets_service.py        #   Google Sheets logging
│   │   └── whatsapp_service.py      #   WhatsApp Cloud API messaging
│   ├── legacy/
│   │   └── vapi/                # ⚠️  LEGACY — Vapi AI integration (disabled)
│   │       ├── __init__.py      #   Legacy package notice
│   │       ├── agent_tools.py   #   Was: /agent-tools/* Vapi webhook endpoints
│   │       ├── vapi_webhook.py  #   Was: /vapi/call-ended webhook handler
│   │       ├── vapi_service.py  #   Vapi assistant clone/update/toggle (no-op)
│   │       ├── call_log_service.py  #   Vapi call-end Firestore persistence
│   │       └── vapi_models.py   #   Vapi webhook payload schemas
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

> **Note on `app/legacy/vapi/`:** These files are retained as reference only.
> No routers from this package are registered in `main.py`. Do not import from
> or edit these files for new features. To re-enable Vapi, set `VAPI_ENABLED=true`
> in `.env` and restore the router registrations in `main.py`.

---

## 🌐 Context Path Routing

All routes are prefixed with `/automiteaiapplication` to support multi-application deployments on a single server:

| Path | Purpose |
|---|---|
| `/automiteaiapplication/health` | Health check |
| `/automiteaiapplication/docs` | Swagger UI |
| `/automiteaiapplication/redoc` | ReDoc UI |
| `/automiteaiapplication/automiteui/auth/*` | Authentication (login, register, refresh token) |
| `/automiteaiapplication/automiteui/client-portal/*` | Client dashboard API (profile, appointments, call logs) |
| `/automiteaiapplication/automiteui/mngr-sys-access-78/*` | Hidden admin panel (client management) |
| `/automiteaiapplication/automiteui/extraction/*` | Intelligent extraction engine (stubs) |
| `/automiteaiapplication/automiteui/pages/*` | Jinja2 HTML pages |
| `/automiteaiapplication/automiteui/static/*` | Static CSS/JS assets |
| `/automiteaiapplication/client/auth/google/*` | Google OAuth flow |

> **Legacy (disabled):** `/automiteaiapplication/agent-tools/*` and `/automiteaiapplication/vapi/call-ended`
> were Vapi AI endpoints. They are no longer registered. See `app/legacy/vapi/`.

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
| `POST` | `/automiteaiapplication/automiteui/auth/register` | — | Register user + create client record |
| `POST` | `/automiteaiapplication/automiteui/auth/login` | — | Get access + refresh tokens |
| `POST` | `/automiteaiapplication/automiteui/auth/refresh` | — | Rotate tokens |

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

### Client Portal (requires `dashboard` JWT)

| Method | Path | Description |
|---|---|---|
| `GET` | `/automiteaiapplication/automiteui/client-portal/profile` | Get client profile |
| `PUT` | `/automiteaiapplication/automiteui/client-portal/profile` | Update services/timings |
| `GET` | `/automiteaiapplication/automiteui/client-portal/appointments` | List appointments |
| `GET` | `/automiteaiapplication/automiteui/client-portal/call-logs` | List call logs |

### Admin (**hidden** — requires `admin:all` JWT)

| Method | Path | Description |
|---|---|---|
| `GET` | `/automiteaiapplication/automiteui/mngr-sys-access-78/dashboard` | System overview |
| `GET` | `/automiteaiapplication/automiteui/mngr-sys-access-78/clients` | List all clients |
| `PATCH` | `/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{id}/status` | Activate/deactivate |
| `PATCH` | `/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{id}/subscription` | Change tier |
| `POST` | `/automiteaiapplication/automiteui/mngr-sys-access-78/clients` | Manual client add |
| `POST` | `/automiteaiapplication/automiteui/mngr-sys-access-78/refresh-tool-tokens` | Rotate M2M tokens |

### Extraction Engine (stubs — coming soon)

| Method | Path | Status |
|---|---|---|
| `POST` | `/automiteaiapplication/automiteui/extraction/parse-text` | 🚧 Coming soon |
| `POST` | `/automiteaiapplication/automiteui/extraction/upload-file` | 🚧 Coming soon |
| `POST` | `/automiteaiapplication/automiteui/extraction/confirm` | 🚧 Coming soon |

### Legacy — Vapi Agent Tools (disabled)

> These endpoints existed when Vapi was active. They are **not registered** and will return 404.
> Source: `app/legacy/vapi/agent_tools.py`

| Method | Path | Description |
|---|---|---|
| `POST` | `/automiteaiapplication/agent-tools/get-client-by-mobile` | Customer lookup by phone |
| `POST` | `/automiteaiapplication/agent-tools/get-services-and-prices` | List services for a client |
| `POST` | `/automiteaiapplication/agent-tools/check-availability` | Check appointment slot |
| `POST` | `/automiteaiapplication/agent-tools/book-appointment` | Book an appointment |
| `POST` | `/automiteaiapplication/agent-tools/save-call-log` | Save call log |

---

## 🎨 UI Pages

| URL | Description |
|---|---|
| `/automiteaiapplication/automiteui/pages/landing` | Landing page |
| `/automiteaiapplication/automiteui/pages/login` | Client login page |
| `/automiteaiapplication/automiteui/pages/register` | Client registration |
| `/automiteaiapplication/automiteui/pages/dashboard` | Client dashboard |
| `/automiteaiapplication/automiteui/pages/mngr-sys-access-78` | Admin login (hidden) |
| `/automiteaiapplication/automiteui/pages/mngr-sys-access-78/dashboard` | Admin dashboard (hidden) |

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
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | — |
| `SECRET_KEY` | Fernet encryption key | — |
| `BASE_URL` | Public base URL for callbacks | `http://localhost:8090` |
| `WHATSAPP_ACCESS_TOKEN` | Meta WhatsApp Cloud API access token | — |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta Phone Number ID | — |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | Meta Business Account ID | — |
| `SMTP_HOST` / `SMTP_PORT` | Email SMTP server | `smtp.gmail.com:587` |
| `SMTP_USER` / `SMTP_PASSWORD` | Gmail SMTP credentials (App Password) | — |
| `CONTACT_EMAIL` | Where contact form submissions are sent | `aiautomite@gmail.com` |
| `GOOGLE_SHEET_ID` | Google Sheets spreadsheet ID | — |
| `GOOGLE_SHEET_TAB` | Worksheet tab name for call logs | `Call Logs` |
| `GEMINI_API_KEY` | Google Gemini API key | — |

### Legacy Vapi Variables (inactive — only needed if re-enabling Vapi)

| Variable | Description | Default |
|---|---|---|
| `VAPI_ENABLED` | Set to `true` to re-activate Vapi integration | `false` |
| `VAPI_API_KEY` | Vapi API bearer token | — |
| `VAPI_TEMPLATE_ASSISTANT_ID` | Template assistant ID to clone from | — |

---

## 🗄️ Firestore Collections

| Collection | Document ID Strategy |
|---|---|
| `clients` | `{uuid4}` |
| `users` | `{uuid4}` (admin = `"admin"`) |
| `customers` | `{client_id}_{phone}` |
| `appointments` | `{client_id}_{phone}_{datetime}` |
| `call_logs` | `{client_id}_{call_id}` (existing records unaffected) |
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
