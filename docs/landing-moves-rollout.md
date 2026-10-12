# Landing Moves — Rollout Plan (prototype to prod)

Source: branch `design/landing-moves` (prototype only, never pushed).
Preview: `/automiteaiapplication/automiteui/pages/landing-moves-preview` (route hidden from schema, `noindex`).
Verified 2026-10-11 with headless Chromium: desktop 1440x900 + mobile 390x844,
zero console errors, count-up/word-reveal/lightbox end-states confirmed.

## Prototype files (NEW, no live behavior touched)

- `app/templates/landing_moves_preview.html`
- `app/static/css/landing-moves.css`
- `app/static/js/landing-moves.js`
- Route `GET /pages/landing-moves-preview` in `app/routers/pages_router.py`
  (additive only; remove it if the preview should not ship).

## What the 7 moves are

1. Mono-eyebrow rhythm: 2 total (`AI voice agents for business`, `Deployments`).
   Rule going forward: max 1 eyebrow per 3 sections.
2. Hero tightening: H1 2 lines, sub 12 words, both CTAs above the fold both viewports.
3. Metric ledger with count-up (`48,200+`, `38%`, `99.9%`, grouped thousands).
4. Manifesto band with per-word scroll reveal, one green clause.
5. Marquee footer crown (the ONE marquee allowed on the page).
6. AUTOMITE scroll wordmark (scroll-driven outline type, CSS `animation-timeline: view()`).
7. Demo lightbox slot (`#demo-lightbox-slot`, opens via `[data-open-demo]`, closes on
   backdrop, button, and Escape, returns focus).
Plus one restrained ambient visual: CSS-only voice orb in the hero (no images, no GPU).

## Rollout steps (prod `landing.html` / `landing.css` / `landing.js`)

Do these in order. Each step is independently shippable and reviewable.

1. **Copy + hero tightening (no CSS risk).** Shorten prod H1/sub to the preview wording
   (or approved variant). Cap: H1 2 lines desktop, sub 20 words, CTAs above fold.
2. **Eyebrows.** Add the mono eyebrow style to `landing.css` (mono stack, 12px,
   0.22em tracking, `--green`). Apply to hero + one more section max.
3. **Metric ledger.** Port `.mv-ledger*` styles under prod class names; port the
   `countUp` + `fmt` logic into `landing.js`. Numbers use the brand display face
   (proportional), not mono: full-cell mono punctuation reads as a defect at
   display sizes. Mono voice lives in eyebrows/labels instead. Replace placeholder
   numbers with real aggregates before shipping (current values are mock).
4. **Manifesto band.** New section after metrics. Server-render words wrapped in
   `.mv-w` spans (or split client-side once on load). Keep to one sentence.
5. **Deployments index.** Optional: only if 3+ real client outcomes are publishable.
   Otherwise skip; do not ship with invented client names.
6. **Demo lightbox.** Port slot markup + open/close/focus logic. Wire the real call
   recording `<audio>` element where the placeholder bars are.
7. **Wordmark + marquee crown (last).** Port together; keep exactly one marquee.
   Provide the `prefers-reduced-motion` static fallback (already in prototype CSS).
   Check `animation-timeline: view()` support in target browsers; fallback is static
   outline type, which is acceptable.

## Guardrails

- Keep the light theme, Montserrat, and single `--green` accent lock.
- Pills for interactive elements, 16px radius for cards. No new accent colors.
- Zero em-dashes in any new copy. No section-number eyebrows. No scroll cues.
- Delete the preview route + template before, or with, the prod rollout if it should
  not remain public. If it remains, add auth or keep `noindex`.
- Re-run the full unit suite (`pytest`) before and after; new deps: none.
- Commander approvals still required for: push, deploy, any spend, prod secrets.
