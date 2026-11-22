# SEO and AI-search decisions

**Date:** 2026-10-17
**Repository:** Automite AI

## Decisions

### Canonical URL

Use the existing public domain `https://auto-mite.com` and keep the current long landing-page path as the canonical URL for now:

```text
https://auto-mite.com/automiteaiapplication/automiteui/pages/landing
```

The application root currently returns a 301 redirect to that path. Do not change canonicals to `/` until a reverse-proxy alias is intentionally created and tested. This avoids creating duplicate URLs or a canonical that does not serve the page directly.

A future friendly alias can be introduced later with:

- one permanent redirect policy;
- one canonical per page;
- sitemap URLs matching canonicals;
- redirect-chain tests;
- deployment verification.

### Blog ownership

`/blogs` is on the same public domain, but it remains a separate application and repository. The Automite repository may reference the blog sitemap from the sitemap index, but must not modify blog templates, routes, content, or tests.

### Machine-readable facts

Do not add `site-facts.json` yet. It is not required for the first SEO/AEO pass because the application already has JSON-LD, `robots.txt`, sitemaps, and `llms.txt`. First generate those from one approved page/facts registry. Add `site-facts.json` only if a real consumer or integration requires it.

### AI-search content

Create only content that can be supported by the existing application and approved claims. Do not publish new metrics, testimonials, customer names, security guarantees, or pricing promises from inference.

## Candidate pages found in the current application

### Safe first candidates, after copy review

1. **AI voice agents**
   - Source: landing page section `What Are AI Voice Agents?`
   - Purpose: define the product category in plain language.
   - Needs: remove or verify any unsupported performance promises.

2. **Inbound voice agents**
   - Source: landing page `Inbound Voice Agents` service section and the active ElevenLabs tool flows.
   - Purpose: explain intake, customer lookup, availability, booking, and call-summary behavior.
   - Needs: describe only behavior verified in code.

3. **Outbound voice agents**
   - Source: landing page `Outbound Voice Agents` section.
   - Purpose: explain callbacks and follow-up use cases.
   - Needs: confirm the outbound workflow is actually implemented before publishing as a product capability.

4. **How it works**
   - Source: landing page `How We Partner`: Strategic Audit, Custom Engineering, Seamless Handover, Everlasting Growth.
   - Purpose: explain the engagement process.
   - Needs: replace vague marketing language with approved, observable steps.

5. **Integrations**
   - Source: active Google Calendar, Google Sheets, ElevenLabs, SMTP, and authentication modules.
   - Purpose: list verified integrations and their current limits.
   - Needs: exclude WhatsApp until its launch status is decided; do not list legacy Vapi.

6. **FAQ**
   - Source: existing `Common Questions` section.
   - Purpose: consolidate answers into crawlable, citation-ready content.
   - Needs: audit every time estimate, recording statement, security statement, and retention claim.

### Defer until evidence and implementation exist

- Security and data page: wait for token encryption, retention policy, deletion/export behavior, and accurate privacy copy.
- Pricing page: wait for the billing market, currency, provider, and pricing policy decision.
- Case-study detail pages: wait for real, consented customer evidence and verified metrics.
- Review/AggregateRating markup: do not add without verifiable reviews.
- HowTo markup: add only when the visible page contains real ordered instructions.

## Required validation

For every candidate page:

- one clear H1;
- direct answer in the opening paragraph;
- visible source or last-updated date where appropriate;
- one canonical URL;
- matching JSON-LD only for visible, approved claims;
- internal links from the landing/footer or a related page;
- inclusion in the sitemap only after approval;
- no private API, admin, dashboard, or customer data.
