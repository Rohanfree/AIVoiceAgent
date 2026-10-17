# Automite AI Application Roadmap

**Planning source:** repository audit plus Claude Code review
**Current branch:** `redo/integration`
**Published staging branch:** `staging/demo`
**Current verified test baseline:** 224 passed, 85 subtests passed
**Scope boundary:** the blog application is separate and is not included here.

## Current state

### Already working

- FastAPI application with client, admin, auth, extraction, contact, Google OAuth, and ElevenLabs tool routes.
- Argon2 password hashing.
- JWT scopes for dashboard, tool, admin, and refresh tokens.
- Four ElevenLabs tool endpoints protected by tool-scope authorization.
- Extraction routes require authentication.
- Client and admin usage-cost rounding aligned to six decimal places.
- Google Calendar and Google Sheets integration paths.
- ElevenLabs agent setup and usage lookup.
- Non-root Docker container deployment.
- Editorial landing page with four generated two-voice call chapters.
- Endpoint inventory and security regression coverage.

### Highest-risk gaps

1. Tool tokens are scope-protected, but client binding must also be enforced so a valid token cannot request another client's data by changing `client_id`.
2. Default admin credentials and JWT secrets exist in committed configuration examples. Production startup must reject default secrets, and deployed credentials must be rotated.
3. CORS currently permits all origins with credentials enabled.
4. Refresh tokens are not revocable or rotated.
5. Google OAuth state and redirect handling need hardening; stored Google credentials need encryption.
6. Booking lacks a transactional overlap re-check and idempotency protection.
7. There is no CI test gate, request tracing, structured PII-redacted logging, or readiness check.
8. Billing, notifications, services editing, and the extraction engine are incomplete.
9. Public landing claims and sample metrics require a pre-launch evidence audit.

## Phase 0: Restore a trustworthy engineering baseline

**Goal:** make the test suite reproducible and deploy-blocking.

**Areas:**

- `requirements.txt`
- new `requirements-dev.txt`
- `pytest.ini`
- `test_comprehensive_security.py`
- shared test fixtures under `tests/conftest.py`

**Work:**

- Pin the supported FastAPI/Starlette combination consistently.
- Add `pytest-asyncio` to development dependencies.
- Move loose tests into a discoverable `tests/` structure when practical.
- Add shared Firestore fakes, auth-token factories, dependency overrides, SMTP fakes, and external-service mocks.
- Keep all tests offline. No real Firestore, ElevenLabs, Google, Gemini, WhatsApp, OAuth, or SMTP calls.

**Acceptance criteria:**

- A clean Python 3.12 environment installs the project and test dependencies.
- `pytest -q` passes without collection errors.
- CI can run the same command from a clean checkout.

## Phase 1: Close customer-impacting security gaps

**Goal:** enforce tenant isolation and remove insecure defaults.

**Areas:**

- `app/auth/dependencies.py`
- `app/auth/jwt_handler.py`
- `app/config.py`
- `app/routers/agent_tools_elevenlabs.py`
- `app/routers/auth_router.py`
- `app/routers/google_auth_router.py`
- `app/main.py`
- `.env.example`
- `README.md`
- frontend token handling in `app/static/js/app.js`

**Work:**

- Bind tool requests to the `client_id` claim in the JWT. Reject body/header client IDs that differ from the token claim. Define an explicit admin override policy.
- Reject production startup when JWT secrets or admin credentials are default, missing, or too weak.
- Rotate the currently deployed admin password and JWT secret.
- Replace wildcard CORS with an explicit configured origin list.
- Add rate limits to login, registration, and agent-availability checks.
- Stop emailing plaintext passwords. Use a set-password flow or omit the password from email.
- Replace JWT-in-query-string OAuth state with short-lived, single-use signed state.
- Validate `return_to` against an allowlist and protect or remove Google debug output.
- Encrypt stored Google tokens using the configured encryption key.
- Add refresh-token rotation and revocation.
- Add per-client tool-token rotation and revocation.
- Audit `innerHTML` insertion points for escaped Firestore-sourced content.

**Acceptance criteria:**

- Tenant A cannot read, book, or write call data for tenant B.
- Production refuses to start with default credentials.
- Repeated failed authentication attempts are rate-limited.
- No plaintext password is sent or persisted in an outbound welcome email.
- OAuth state replay and off-list redirects fail safely.

## Phase 2: Make booking and call data correct

**Goal:** prevent double bookings and preserve reliable call records.

**Areas:**

- `app/services/availability_service.py`
- `app/services/booking_service.py`
- `app/services/customer_service.py`
- `app/services/calendar_service.py`
- `app/services/sheets_service.py`
- `app/routers/agent_tools_elevenlabs.py`
- request/response schemas

**Work:**

- Replace untyped tool dictionaries with Pydantic request models.
- Validate service names, durations, phone numbers, dates, and timezone inputs.
- Re-check availability inside a Firestore transaction before booking.
- Add conflict-safe, idempotent appointment identifiers. Preserve compatibility with existing appointment records during migration.
- Normalize phone numbers to E.164.
- Use each client's timezone when interpreting naive date-times.
- Make `save-call-summary` idempotent by conversation ID.
- Persist `duration_seconds` and other call metadata consistently in Firestore and Sheets.
- Surface partial Calendar or Sheets failures instead of silently dropping them.

**Acceptance criteria:**

- Concurrent identical bookings produce one success and one conflict.
- Repeating the same call-summary request does not duplicate data.
- DST and client-timezone cases produce the intended appointment time.
- Call logs and Sheets rows contain the same required fields.

## Phase 3: Make money and usage accounting authoritative

**Goal:** one precise calculation path for character usage and cost.

**Areas:**

- client/admin token-usage routes
- pricing routes
- ElevenLabs usage service
- shared money utility, preferably a new `app/services/money.py`

**Work:**

- Use `Decimal(str(value))`, not binary float multiplication, for currency calculations.
- Define one quantization policy, such as six decimal places for per-character estimates.
- Define rounding mode explicitly, such as `ROUND_HALF_UP`.
- Test zero, fractional, negative, missing, client-override, global-fallback, and large-character-count cases.
- Return currency consistently from client and admin usage endpoints.
- Share the same calculation helper between client and admin routes.
- Decide whether billing is based on characters, calls, duration, or a combination. Align usage limits with that decision.
- Add cache freshness and pagination tests for usage summaries.

**Acceptance criteria:**

- Client and admin cost outputs are identical for identical inputs.
- Fractional prices have deterministic results across Python versions.
- Negative prices and invalid pricing payloads are rejected.
- Large usage values do not overflow or lose precision.
- Every cost result has a declared currency and rounding policy.

## Phase 4: Observability and safe releases

**Goal:** detect failures and deploy without avoidable downtime.

**Areas:**

- `app/main.py`
- all router modules
- `.github/workflows/`
- `Dockerfile`
- `docker-compose*.yml`
- deployment scripts and server configuration

**Work:**

- Add request IDs and structured JSON logs.
- Redact phone numbers, transcripts, tokens, and credentials from logs.
- Add a readiness endpoint that checks required dependencies separately from liveness.
- Add error tracking and alerts for tool failures, OAuth failures, usage-job failures, and integration failures.
- Require tests in CI before deploy.
- Build immutable tagged artifacts.
- Add health-check gating and rollback instead of stopping the running service before a replacement is ready.
- Remove unconditional test-instance restarts from production workflow.
- Add Firestore backup and restore-drill procedures.

**Acceptance criteria:**

- A failed test blocks deployment.
- A failed readiness check triggers rollback.
- A tool failure can be traced by request ID without exposing PII.
- Backup restoration is exercised and documented.

## Phase 5: Complete the paying-customer product

**Goal:** a customer can configure and operate the service without manual engineering support.

**Areas:**

- `app/routers/client_router.py`
- dashboard templates and frontend JavaScript
- `app/routers/admin_router.py`
- new billing and notification modules
- integrations configuration

**Work:**

- Build services CRUD in the client dashboard.
- Select and implement one billing provider for the launch market.
- Add subscription limits, usage enforcement, invoices, webhook signature validation, and webhook replay protection.
- Add booking confirmations, missed-call notifications, and operational alerts.
- Decide whether WhatsApp is launch scope. If not, remove its dead code and configuration.
- Decide whether the extraction engine is launch scope. If not, hide or remove the placeholder endpoints.
- Remove legacy Vapi code when the migration is confirmed complete.

**Acceptance criteria:**

- A new customer can register, configure services, connect Google, complete a test call, and see the resulting record without admin intervention.
- Billing events are idempotent and authenticated.
- Customer-facing limits and admin usage views agree.

## Phase 6: Launch readiness and trust

**Goal:** ensure the public website says only what the application can prove.

**Areas:**

- landing and case-study templates
- privacy policy
- SEO routes and sitemap generation
- landing JavaScript/CSS and media
- `docs/`

**Work:**

- Audit every metric, testimonial, customer name, security statement, retention statement, and integration claim.
- Replace mock figures before launch or label them unmistakably as examples.
- Ensure generated demo calls are never presented as real customer recordings.
- Update privacy policy for phone numbers, transcripts, Google tokens, retention, deletion, and export.
- Add data deletion/export workflows.
- Gate or remove preview-only routes.
- Add Lighthouse, accessibility, keyboard, mobile, reduced-motion, and audio smoke tests.
- Document incident response, credential rotation, backup restoration, and customer-data deletion.

**Acceptance criteria:**

- Every public claim maps to a verified code path or is removed.
- Legal copy matches actual storage and processing behavior.
- The public demo passes desktop, mobile, keyboard, reduced-motion, and audio checks.

## Recommended execution order

1. **Phase 0:** green, reproducible tests and CI gate.
2. **Phase 1:** tenant isolation, secret rotation, OAuth hardening, rate limits.
3. **Phase 2:** booking, timezone, idempotency, and call-log correctness.
4. **Phase 3:** authoritative Decimal-based money and usage accounting.
5. **Phase 4:** observability, readiness, backups, and zero-downtime deploys.
6. **Phase 5:** billing, notifications, services editing, and launch-scope cleanup.
7. **Phase 6:** public-claim, privacy, accessibility, and launch audit.

## Decisions required before Phase 5

- Which market and currency should the initial billing flow target?
- Should WhatsApp ship or be removed from the launch codebase?
- Should the extraction engine ship or remain out of scope?
- Who owns the production VPS and credential rotation process?
- Are existing long-lived ElevenLabs tool tokens active in production?
