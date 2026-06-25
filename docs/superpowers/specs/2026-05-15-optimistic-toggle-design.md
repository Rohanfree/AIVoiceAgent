# Optimistic Toggle — Design Spec
**Date:** 2026-05-15  
**Scope:** Admin dashboard — Activate/Deactivate client button UX

---

## Problem

Pressing Deactivate/Activate causes a ~1 s freeze (the backend awaits an ElevenLabs API call) with zero button feedback. On success the page does `location.reload()`, triggering the full-page loader. Two separate pain points: the freeze and the unnecessary reload.

---

## Solution

Optimistic UI update on the affected row, followed by a lightweight stats refresh. No page reload.

---

## Components

### 1. Row template attributes (in `initAdminDashboard` innerHTML)

Add three anchors to each `<tr>`:

| Attribute | Element | Purpose |
|---|---|---|
| `data-client-id="${c.id}"` | `<tr>` | Row lookup without DOM scan |
| `data-status-badge` | status `<span class="badge ...">` | Optimistic badge flip target |
| `data-toggle-actions` | last `<td>` (actions cell) | Toggle button swap target |

### 2. `toggleClient(clientId, activate)` — rewrite

**Step 1 — Synchronous (instant on click):**
- Find `tr[data-client-id="${clientId}"]`
- Snapshot the badge's current `className` and `textContent` for rollback
- Flip badge class (`badge-active` ↔ `badge-inactive`) and text (`Active` ↔ `Inactive`) optimistically
- Replace the toggle button inside `[data-toggle-actions]` with a disabled spinner button

**Step 2 — Async:**
- Fire `apiCall('PATCH', /mngr-sys-access-78/clients/${clientId}/status, { is_active: activate })`

**Step 3a — Success:**
- Render the correct toggle button back into `[data-toggle-actions]` (Activate or Deactivate label matching the new state)
- Call `refreshAdminStats()`

**Step 3b — Failure:**
- Revert badge `className` and `textContent` to snapshot
- Restore the original toggle button HTML
- Call `showAlert('error', ...)`

### 3. `refreshAdminStats()` — new helper

- `GET /mngr-sys-access-78/dashboard`
- On success: call `animateCount()` on `#total-clients`, `#active-clients`, `#inactive-clients`, `#total-calls`
- On failure: silently ignore (counts are cosmetic; a stale count is acceptable)

---

## What does NOT change

- **Limit-exceeded hard-block path** (`Add Characters →` button): untouched — that row never reaches `toggleClient`
- **`deleteClient`**: keeps `location.reload()` — a deleted row can't be patched in-place
- **`openCharLimitModal`**, **`openAdminUsageModal`**: untouched
- All other admin functions: untouched

---

## Error handling

| Scenario | Behaviour |
|---|---|
| API returns non-2xx | Revert optimistic changes, `showAlert('error', ...)` |
| Network failure | `apiCall` returns `null`; same revert path |
| Row not found in DOM | Toggle still fires, no optimistic update; success/failure handled normally |
| `refreshAdminStats` fails | Silently ignored — stale counts are acceptable |

---

## Files touched

| File | Change |
|---|---|
| `app/static/js/app.js` | Add `data-*` attrs to row template; rewrite `toggleClient`; add `refreshAdminStats` |

No backend changes required.
