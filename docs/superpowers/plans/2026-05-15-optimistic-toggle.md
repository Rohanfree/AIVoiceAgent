# Optimistic Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the freeze-then-loader when admin clicks Activate/Deactivate by using an optimistic DOM update, a spinner while the API call is in flight, and a lightweight stats refresh on success — no page reload.

**Architecture:** Three targeted edits to `app/static/js/app.js`: (1) add `data-*` anchor attributes to each row in the clients table template so DOM lookups are O(1); (2) rewrite `toggleClient` to flip badge + swap button synchronously before the async API call, then reconcile or revert on completion; (3) add `refreshAdminStats` that re-fetches only the dashboard counts.

**Tech Stack:** Vanilla JS, Fetch API, existing `animateCount()` / `showAlert()` / `apiCall()` utilities already in `app.js`.

---

## Files

| File | Change |
|---|---|
| `app/static/js/app.js` | (1) Row template: add `data-client-id`, `data-status-badge`, `data-toggle-actions`. (2) Rewrite `toggleClient`. (3) Add `refreshAdminStats`. |

---

### Task 1: Add data-* anchor attributes to the row template

**Files:**
- Modify: `app/static/js/app.js` — the `tbody.innerHTML = clientsData.clients.map(c => { ... })` block inside `initAdminDashboard` (lines ~637–674)

- [ ] **Step 1: Add `data-client-id` to `<tr>`, `data-status-badge` to the badge span, `data-toggle-actions` to the actions `<td>`**

Find this exact block (the `return \`` template literal inside the `.map` callback):

```javascript
                return `
                <tr>
                    <td>${c.business_name || 'Unnamed'}</td>
                    <td><code style="font-size:0.75rem;color:var(--color-text-secondary)">${c.id}</code></td>
                    <td>
                        <span class="badge ${c.is_active !== false ? 'badge-active' : 'badge-inactive'}">${c.is_active !== false ? 'Active' : 'Inactive'}</span>
                        ${deactReason}
                    </td>
                    <td>${c.subscription_status || 'active'}</td>
                    <td>
                        ${limitLabel}
                        <button class="btn btn-sm btn-secondary" style="margin-top:4px;font-size:0.7rem;padding:2px 8px;" onclick="openCharLimitModal('${c.id}', '${safeName}', ${limit != null ? limit : 'null'})">
                            Set / Add
                        </button>
                    </td>
                    <td style="display:flex;gap:6px;flex-wrap:wrap;">
                        <button class="btn btn-sm btn-secondary" onclick="openAdminUsageModal('${c.id}', '${safeName}')">
                            Usage
                        </button>
                        ${c.is_active === false && c.deactivation_reason === 'limit_exceeded'
                            ? `<button class="btn btn-sm btn-primary" onclick="openCharLimitModal('${c.id}', '${safeName}', ${limit != null ? limit : 'null'})" title="Limit exceeded — add characters to reactivate">Add Characters →</button>`
                            : `<button class="btn btn-sm btn-secondary" onclick="toggleClient('${c.id}', ${c.is_active === false})">${c.is_active === false ? 'Activate' : 'Deactivate'}</button>`
                        }
                        <button class="btn btn-sm" style="background:var(--color-error,#e53e3e);color:#fff;border:none;" onclick="deleteClient('${c.id}', '${safeName}')">
                            Delete
                        </button>
                    </td>
                </tr>`;
```

Replace it with:

```javascript
                return `
                <tr data-client-id="${c.id}">
                    <td>${c.business_name || 'Unnamed'}</td>
                    <td><code style="font-size:0.75rem;color:var(--color-text-secondary)">${c.id}</code></td>
                    <td>
                        <span data-status-badge class="badge ${c.is_active !== false ? 'badge-active' : 'badge-inactive'}">${c.is_active !== false ? 'Active' : 'Inactive'}</span>
                        ${deactReason}
                    </td>
                    <td>${c.subscription_status || 'active'}</td>
                    <td>
                        ${limitLabel}
                        <button class="btn btn-sm btn-secondary" style="margin-top:4px;font-size:0.7rem;padding:2px 8px;" onclick="openCharLimitModal('${c.id}', '${safeName}', ${limit != null ? limit : 'null'})">
                            Set / Add
                        </button>
                    </td>
                    <td data-toggle-actions style="display:flex;gap:6px;flex-wrap:wrap;">
                        <button class="btn btn-sm btn-secondary" onclick="openAdminUsageModal('${c.id}', '${safeName}')">
                            Usage
                        </button>
                        ${c.is_active === false && c.deactivation_reason === 'limit_exceeded'
                            ? `<button class="btn btn-sm btn-primary" onclick="openCharLimitModal('${c.id}', '${safeName}', ${limit != null ? limit : 'null'})" title="Limit exceeded — add characters to reactivate">Add Characters →</button>`
                            : `<button class="btn btn-sm btn-secondary" onclick="toggleClient('${c.id}', ${c.is_active === false})">${c.is_active === false ? 'Activate' : 'Deactivate'}</button>`
                        }
                        <button class="btn btn-sm" style="background:var(--color-error,#e53e3e);color:#fff;border:none;" onclick="deleteClient('${c.id}', '${safeName}')">
                            Delete
                        </button>
                    </td>
                </tr>`;
```

- [ ] **Step 2: Verify in browser**

Open the admin dashboard. In DevTools → Elements, expand any `<tr>` in `#clients-tbody`. Confirm:
- `<tr data-client-id="...">` is present
- The status `<span>` has `data-status-badge`
- The last `<td>` has `data-toggle-actions`

- [ ] **Step 3: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add data-* anchor attrs to admin clients table rows"
```

---

### Task 2: Add `refreshAdminStats()` helper

**Files:**
- Modify: `app/static/js/app.js` — add new function after `initAdminDashboard` (after line ~679)

- [ ] **Step 1: Add the function immediately after the closing `}` of `initAdminDashboard`**

Find this line:
```javascript
    hidePageLoader();
}

async function toggleClient(clientId, activate) {
```

Insert `refreshAdminStats` between `initAdminDashboard`'s closing brace and `toggleClient`:

```javascript
    hidePageLoader();
}

async function refreshAdminStats() {
    const stats = await apiCall('GET', '/mngr-sys-access-78/dashboard');
    if (!stats) return;
    animateCount(document.getElementById('total-clients'),   stats.total_clients  || 0);
    animateCount(document.getElementById('active-clients'),  stats.active_clients  || 0);
    animateCount(document.getElementById('inactive-clients'),stats.inactive_clients || 0);
    animateCount(document.getElementById('total-calls'),     stats.total_call_logs || 0);
}

async function toggleClient(clientId, activate) {
```

- [ ] **Step 2: Verify in browser console**

Open the admin dashboard, open DevTools console, type:
```javascript
refreshAdminStats()
```
Confirm: the four stat counters animate to their current values with no errors.

- [ ] **Step 3: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: add refreshAdminStats helper for lightweight count refresh"
```

---

### Task 3: Rewrite `toggleClient` with optimistic UI

**Files:**
- Modify: `app/static/js/app.js` — replace the existing `toggleClient` function

- [ ] **Step 1: Replace `toggleClient` with the optimistic version**

Find and replace this entire function:

```javascript
async function toggleClient(clientId, activate) {
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${clientId}/status`, {
        is_active: activate,
    });
    if (data) {
        showAlert('success', `Client ${data.status} successfully.`);
        setTimeout(() => location.reload(), 1000);
    }
}
```

Replace with:

```javascript
async function toggleClient(clientId, activate) {
    // ── Optimistic update (synchronous — instant feedback) ───────────────────
    const row         = document.querySelector(`tr[data-client-id="${clientId}"]`);
    const badge       = row && row.querySelector('[data-status-badge]');
    const actionsCell = row && row.querySelector('[data-toggle-actions]');

    // Snapshot current badge state for rollback
    const prevBadgeClass = badge ? badge.className   : null;
    const prevBadgeText  = badge ? badge.textContent : null;

    // Flip badge immediately
    if (badge) {
        badge.className   = activate ? 'badge badge-active' : 'badge badge-inactive';
        badge.textContent = activate ? 'Active' : 'Inactive';
    }

    // Swap toggle button with a disabled spinner
    let prevToggleHtml = null;
    if (actionsCell) {
        const toggleBtn = actionsCell.querySelector('button[onclick*="toggleClient"]');
        if (toggleBtn) {
            prevToggleHtml = toggleBtn.outerHTML;
            toggleBtn.outerHTML = `<button class="btn btn-sm btn-secondary" disabled style="min-width:80px;"><span class="spinner" style="width:13px;height:13px;border-width:2px;vertical-align:middle;margin-right:4px;"></span></button>`;
        }
    }

    // ── API call ─────────────────────────────────────────────────────────────
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${clientId}/status`, {
        is_active: activate,
    });

    // ── Reconcile ────────────────────────────────────────────────────────────
    if (data) {
        // Swap spinner for the correct new-state button
        if (actionsCell) {
            const spinner = actionsCell.querySelector('button[disabled]');
            if (spinner) {
                spinner.outerHTML = `<button class="btn btn-sm btn-secondary" onclick="toggleClient('${clientId}', ${!activate})">${activate ? 'Deactivate' : 'Activate'}</button>`;
            }
        }
        await refreshAdminStats();
    } else {
        // Revert badge
        if (badge) {
            badge.className   = prevBadgeClass;
            badge.textContent = prevBadgeText;
        }
        // Revert button
        if (actionsCell && prevToggleHtml) {
            const spinner = actionsCell.querySelector('button[disabled]');
            if (spinner) spinner.outerHTML = prevToggleHtml;
        }
        showAlert('error', 'Failed to update client status. Please try again.');
    }
}
```

- [ ] **Step 2: Verify happy path in browser**

1. Load the admin dashboard.
2. Click **Deactivate** on any active client.
3. Expected — instant: button becomes a small spinner, badge flips to "Inactive".
4. Expected — ~1 s later: spinner becomes "Activate", stats counters animate to new counts. No loader, no page reload.

- [ ] **Step 3: Verify failure path in browser**

1. In DevTools → Network, set throttling to "Offline".
2. Click **Deactivate** on any active client.
3. Expected: spinner appears briefly, then badge reverts to "Active", button reverts to "Deactivate", red error alert appears.
4. Re-enable network.

- [ ] **Step 4: Verify limit-exceeded rows are untouched**

Find a client with "Limit exceeded" shown. Confirm the "Add Characters →" button is still present and unchanged (the `toggleClient` path is never reached for these rows).

- [ ] **Step 5: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: optimistic activate/deactivate toggle — no page reload"
```

---

### Task 4: Push and smoke-test

- [ ] **Step 1: Push to remote**

```bash
git push origin main
```

- [ ] **Step 2: End-to-end smoke test on live/staging**

1. Log in as admin.
2. Deactivate a client → confirm instant feedback, no loader flash.
3. Activate the same client → confirm instant feedback, stats update.
4. Confirm ElevenLabs agent prompt was actually updated (call the client's number or check ElevenLabs console).
