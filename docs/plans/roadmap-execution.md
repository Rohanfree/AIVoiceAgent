# Automite AI Roadmap Execution Plan

> **For Hermes:** Execute this plan task-by-task with Claude Code in an isolated worktree or dedicated branch. Do not deploy or push without Commander approval.

**Goal:** Execute the Automite roadmap safely, while making technical SEO and AI-search discoverability first-class workstreams rather than a late launch checklist.

**Current baseline:** `staging/demo` at `a1bf89a`; 224 tests passed and 85 subtests passed in the verified Python 3.12 environment.

**Scope:** Automite repository only. The blog application remains separate.

**Decision record:** `docs/seo/decisions.md` records the canonical URL, same-domain blog ownership, site-facts decision, and the AEO pages found from existing application content.

---

## What the current roadmap already includes

The roadmap already mentions SEO routes, sitemap generation, public-claim review, privacy, accessibility, and launch checks. It does **not** yet give SEO/AEO enough execution detail. This plan adds that missing workstream:

- Technical SEO: canonical URLs, metadata, robots, sitemap, noindex, structured data, crawl graph, redirects, page speed, accessibility.
- AI-search/AEO: answer-oriented pages, entity clarity, citation-ready documentation, factual freshness, machine-readable facts, `llms.txt`, internal links, and evaluation queries.
- Trust controls: no invented metrics, no unverified testimonials, no unsupported structured-data claims, and no indexing of private/admin surfaces.

Current discovery surfaces found in the repository:

- `/robots.txt`
- `/sitemap.xml`
- `/sitemap-pages.xml`
- `/llms.txt`
- SEO/head markup in `app/templates/base.html`, `landing.html`, `case-studies.html`, and `privacy-policy.html`
- Noindex handling in page routes and preview surfaces

These surfaces must be tested and generated from one source of truth instead of being maintained as unrelated strings.

---

## Execution rules

1. One work package per reviewable change.
2. Write the failing test before production code for behavior changes.
3. Run the smallest relevant test after each package, then the full suite at each phase gate.
4. No live Firestore, ElevenLabs, Google, Gemini, OAuth, SMTP, or payment calls in automated tests.
5. Do not place credentials, customer data, or raw provider responses in the repository.
6. Stop at every gate when acceptance criteria fail.
7. Claude Code is used for analysis, implementation, and review; changes are verified locally before any push.

---

# Track 0 — Reproducible baseline

### 0.1 Pin the supported runtime

**Files:** `requirements.txt`, `Dockerfile`

- Choose one supported Python/FastAPI/Starlette combination.
- Make local test and Docker versions agree.
- Do not upgrade dependencies speculatively.

**Verify:**

```bash
python3.12 -m venv /tmp/automite-test
/tmp/automite-test/bin/pip install -r requirements.txt
```

**Gate:** clean installation succeeds.

### 0.2 Make pytest the executable gate

**Files:** new `requirements-dev.txt`, new `pytest.ini`, existing test files

- Add `pytest-asyncio` and test-only dependencies.
- Register async markers.
- Preserve the existing 224-test baseline or explain every intentional delta.

**Verify:**

```bash
pytest --collect-only -q
pytest -q
```

**Gate:** no collection errors and all tests pass.

### 0.3 Add CI before feature work

**Files:** new `.github/workflows/test.yml`, `.github/workflows/deploy.yml`

- Run the clean install and full test suite on pull requests.
- Make deployment depend on the test job.
- Do not alter production deployment behavior until the test job is verified.

**Gate:** a deliberately failing test blocks deployment in CI.

---

# Track SEO — Technical discovery foundation

Run this track after 0.2 and before security work changes `main.py` and page routing.

### SEO.1 Decide the canonical URL policy

**File:** new `docs/seo/decisions.md`

Record:

- Whether the long `/automiteaiapplication/automiteui/pages/...` path remains canonical.
- Whether a reverse-proxy alias such as `/` or `/app` will be introduced.
- Whether `/blogs` is served by the same host and which application owns its sitemap.
- Whether login/register should be `noindex`, blocked by robots, or both.
- Whether a public `site-facts.json` is approved.

**Gate:** canonical URL policy is written before metadata or sitemap changes.

### SEO.2 Create one page registry

**Files:** new `app/seo/pages.py`, `app/config.py`, `.env.example`

The registry should define, for every public HTML page:

- route and canonical path;
- title and description;
- indexable/noindex status;
- page type/entity type;
- owner-approved `lastmod`/`dateModified` value;
- breadcrumb label.

Add a configured `site_url`; do not scatter `https://auto-mite.com` literals through templates.

**Tests:** new `tests/seo/test_registry.py`

- Every public HTML route is classified.
- No private/admin/auth route is indexable.
- Registry canonicals are absolute.

### SEO.3 Centralize head markup

**Files:** new `app/templates/_seo_head.html`, `base.html`, `landing.html`, `case-studies.html`, `privacy-policy.html`

- Use the registry for title, description, canonical, Open Graph, Twitter metadata, and page type.
- Preserve current visual output and landing behavior.
- Ensure one title, one description, one canonical, one H1, `lang`, and viewport per indexable page.

**Verify:**

```bash
pytest -q tests/seo/test_metadata.py
pytest -q test_landing_iter*.py
```

**Gate:** no landing regression and no duplicate head signals.

### SEO.4 Move discovery files into a router

**Files:** new `app/routers/seo_router.py`, `app/main.py`

Generate from the page registry:

- `/robots.txt`
- `/sitemap.xml`
- `/sitemap-pages.xml`
- `/llms.txt`

Rules:

- Only indexable pages enter the sitemap.
- `lastmod` is not a hardcoded current date.
- Canonical URLs and sitemap URLs match exactly.
- Robots rules are not duplicated.
- Preview, auth, client, and admin surfaces are not indexable.
- `llms.txt` contains only verified product facts and real integrations.

**Tests:** new `tests/seo/test_discovery_routes.py`, `test_sitemap.py`, `test_robots_llms.py`

**Gate:** all discovery routes return the expected status/content type and the existing route inventory remains green.

### SEO.5 Crawl and index controls

**Files:** `app/main.py` or SEO middleware, new `tests/seo/test_indexing.py`

Verify:

- noindex pages emit both the intended meta/header signals;
- `/` has no redirect chain longer than one hop;
- admin/login/register/dashboard are excluded correctly;
- preview routes are excluded;
- public API docs/OpenAPI are disabled or protected in production;
- every robots disallow rule matches a real or intentionally reserved path.

**Gate:** `pytest -q tests/seo/` passes.

---

# Track 1 — Security and tenant isolation

### 1.1 Production secret validation

**Files:** `app/config.py`, `.env.example`, new `tests/test_startup_config.py`

Reject default or weak JWT/admin secrets in production. Rotate deployed credentials as an explicit operations task; never commit them.

### 1.2 Bind tool tokens to tenants

**Files:** `app/auth/dependencies.py`, `app/auth/jwt_handler.py`, `app/routers/agent_tools_elevenlabs.py`, new `tests/test_tenant_isolation.py`

- Compare request `client_id` with the token claim.
- Reject mismatches for all four tool endpoints.
- Define and test the admin override policy explicitly.

**Gate:** tenant A cannot read or modify tenant B’s customers, bookings, or call logs.

### 1.3 Harden CORS, auth throttling, email, and OAuth

**Files:** `app/main.py`, `app/config.py`, `app/routers/auth_router.py`, `app/routers/google_auth_router.py`

Implement one package at a time:

- explicit CORS origins;
- login/register/check-agent rate limits;
- no plaintext password in welcome email;
- short-lived single-use OAuth state;
- validated `return_to` allowlist;
- protected/removed Google debug endpoint;
- encrypted stored Google tokens;
- refresh-token and tool-token rotation/revocation.

**Verify:** one focused test file per package, then `pytest -q`.

---

# Track 2 — Booking, call data, and money correctness

### 2.1 Typed tool inputs

**Files:** new request models under `app/schemas/`, `app/routers/agent_tools_elevenlabs.py`

Validate phone numbers, durations, dates, timezone values, required fields, and malformed numeric inputs.

### 2.2 Correct booking and call records

**Files:** `app/services/availability_service.py`, `booking_service.py`, `customer_service.py`, `calendar_service.py`, `sheets_service.py`

- Re-check availability transactionally.
- Prevent duplicate appointments.
- Resolve naive times using client timezone.
- Normalize phone numbers.
- Make call summaries idempotent by conversation ID.
- Persist `duration_seconds` consistently.
- Surface Calendar/Sheets partial failures.

**Gate:** concurrent identical booking tests produce one success and one conflict.

### 2.3 Authoritative money calculations

**Files:** new `app/services/money.py`, `client_router.py`, `admin_router.py`, usage service

- Use `Decimal(str(value))`.
- Define currency precision and `ROUND_HALF_UP` explicitly.
- Share one helper between client/admin calculations.
- Reject negative and malformed prices.
- Test zero, fractional, boundary, override, fallback, and large values.
- Document whether limits are character-, call-, duration-, or money-based.

**Verify:**

```bash
pytest -q tests/test_money.py tests/test_usage_parity.py
```

**Gate:** identical inputs produce identical client/admin totals across supported Python versions.

---

# Track 3 — Observability and release safety

### 3.1 Request IDs and PII-safe logs

**Files:** `app/main.py`, new logging module, new `tests/test_log_redaction.py`

Add request IDs and structured logs. Redact phone numbers, transcripts, tokens, credentials, and provider payloads.

### 3.2 Readiness and health

**Files:** `app/main.py`, new `tests/test_readiness.py`

Keep liveness separate from readiness. Readiness should report dependency failure without exposing secrets.

### 3.3 CI-gated deploy and rollback

**Files:** `.github/workflows/deploy.yml`, `Dockerfile`, compose files

- Build tagged immutable artifacts.
- Health-check before traffic cutover.
- Roll back on failed readiness.
- Remove unconditional test-instance restart.
- Add a Firestore backup/restore runbook under `docs/ops/`.

**Gate:** failed test blocks deploy; failed readiness triggers rollback.

---

# Track AEO — AI-search and citation readiness

This is not a promise of ranking or citations. It is a factual, machine-readable information structure that makes the product easier for search engines and answer engines to understand without inventing claims.

### AEO.1 Evidence and claims audit

**Files:** new `docs/launch/claims-audit.md`, landing/case-study/privacy templates

Create a row for every public claim:

- claim text;
- source in code or approved business evidence;
- status: keep, relabel as example, or remove;
- owner approval;
- last verified date.

Include metrics, testimonials, security statements, retention, integrations, FAQ answers, JSON-LD, and `llms.txt`.

**Gate:** no unverified statistic or testimonial proceeds into structured data or AEO pages.

### AEO.2 Build entity and answer pages from verified facts

**Files:** new page templates and registry entries

Create only pages with truthful, owner-approved content:

- `/ai-voice-agents`
- `/inbound-voice-agents`
- `/outbound-voice-agents`
- `/how-it-works`
- `/integrations`
- `/security-and-data` after the security/privacy phases are true
- `/faq`
- pricing only after currency and billing policy are decided

Each page must have:

- one clear H1;
- a direct answer in the opening paragraph;
- entity/problem/use-case terminology in plain language;
- visible source or last-updated information where appropriate;
- links to deeper supporting pages;
- no invented numbers.

Use HowTo structured data only when visible, ordered, truthful steps exist. Do not add Review, AggregateRating, or testimonial schema without real evidence and consent.

**Gate:** owner reviews each page against the claims audit.

### AEO.3 Citation-ready documentation and freshness

**Files:** new docs templates, changelog page, registry

- Stable URLs and heading anchors.
- Visible `Last updated` date.
- One registry value drives visible date, JSON-LD `dateModified`, and sitemap `lastmod`.
- Identify the organization/author and provide a contact route.
- Explain supported integrations, data handling, limitations, and setup steps factually.

**Tests:** new `tests/seo/test_freshness.py`

### AEO.4 Machine-readable facts

**Files:** `app/routers/seo_router.py`, new `app/seo/jsonld.py`

- Generate Organization, WebSite, Service, FAQPage, and BreadcrumbList data from approved facts.
- Make visible FAQ text and FAQ JSON-LD identical.
- Generate `llms.txt` from the same registry.
- Optionally add `llms-full.txt` and `site-facts.json` only after explicit approval.
- Do not expose private/admin/client API schemas publicly.

**Tests:** new `tests/seo/test_jsonld.py`, `test_machine_readable.py`

- JSON parses.
- IDs resolve.
- Every structured-data claim has visible page support.
- No private route enters machine-readable output.

### AEO.5 Internal link graph

**Files:** shared nav/footer partials, new `tests/seo/test_links.py`

- Link every indexable page from the public navigation/footer or a related page.
- Use descriptive anchor text.
- Avoid orphan pages.
- Ensure internal links return 200.
- Keep important answer pages within two clicks of the landing page.

### AEO.6 Search/answer evaluation

**Files:** new `docs/seo/aeo-queries.md`, `docs/seo/eval-log.md`

Define an owner-approved query set covering:

- brand queries;
- category queries;
- problem/use-case queries;
- integration and security queries.

For each release:

- record whether the answer is accurate;
- record whether the source is cited;
- record any invented or stale claim;
- do not set unsupported citation-count targets.

Human verification uses Google Search Console and Bing Webmaster Tools. Crawler access logs can be reviewed after observability is implemented.

**Gate:** baseline evaluation exists before launch and is rerun after substantive content changes.

---

# Track 4 — Product completion

Execute after security/data correctness gates:

1. Services CRUD.
2. Billing provider decision and authenticated, replay-safe webhooks.
3. Booking and missed-call notifications.
4. Decide whether WhatsApp ships; remove dead code if not.
5. Decide whether extraction ships; hide/remove placeholders if not.
6. Remove legacy Vapi code after migration confirmation.

Each package requires focused tests and a full-suite run.

---

# Track 5 — Launch gate

Launch is blocked until all conditions pass:

- `pytest -q` is green.
- `pytest -q tests/seo/` is green.
- Tenant-isolation tests pass.
- Claims audit has no unresolved public claims.
- Sitemap, robots, metadata, JSON-LD, freshness, and internal-link tests pass.
- Structured-data validation and Lighthouse results are recorded.
- AEO query baseline is recorded.
- Privacy policy matches actual data processing.
- Mobile, keyboard, reduced-motion, raw-HTML, and audio smoke tests pass.
- Credential rotation, backup restoration, and incident runbooks are documented.

---

## Recommended first execution slice

1. Resolve the canonical URL and `/blogs` ownership decisions.
2. Add the test/dependency baseline and CI gate.
3. Create the SEO page registry and metadata tests.
4. Generate robots/sitemap/llms from the registry.
5. Fix tenant binding before adding new public content.
6. Run the claims audit before creating AEO pages.
7. Add only the answer pages supported by verified facts.

## Decisions needed from the Commander

1. Keep the long application URL as canonical, or introduce a friendly public alias?
2. Is `/blogs` on the same host, and which application owns its sitemap?
3. Approve or reject public `site-facts.json`?
4. Which AEO pages have truthful content ready now?
5. Which market, currency, and billing provider should Phase 4 target?
