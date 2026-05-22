/**
 * app.js — Automite AI Frontend JavaScript
 *
 * Handles:
 *  - Login / Register forms (fetch-based API calls)
 *  - Token management (localStorage)
 *  - Dashboard data loading
 *  - Admin panel operations
 */

const API_BASE = '/automiteaiapplication/automiteui';

// ─── Token Management ────────────────────────────────────────────────────────
// Admin and client tokens are stored under separate localStorage namespaces so
// both sessions can coexist in the same browser without overwriting each other.
//   admin  → admin_access_token / admin_refresh_token / admin_token_scope
//   client → client_access_token / client_refresh_token / client_token_scope

function _tokenPrefix() {
    return window.location.href.includes('mngr-sys-access-78') ? 'admin' : 'client';
}

function _loginUrl() {
    return window.location.href.includes('mngr-sys-access-78')
        ? `${API_BASE}/pages/mngr-sys-access-78`
        : `${API_BASE}/pages/login`;
}

function saveTokens(data) {
    // Use the scope from the server response to pick the correct namespace,
    // regardless of which page the login form is on.
    const prefix = (data.scope === 'admin:all') ? 'admin' : 'client';
    localStorage.setItem(`${prefix}_access_token`,  data.access_token);
    localStorage.setItem(`${prefix}_refresh_token`, data.refresh_token);
    localStorage.setItem(`${prefix}_token_scope`,   data.scope || 'dashboard');
}

function getAccessToken() {
    return localStorage.getItem(`${_tokenPrefix()}_access_token`);
}

function getRefreshToken() {
    return localStorage.getItem(`${_tokenPrefix()}_refresh_token`);
}

function getTokenScope() {
    return localStorage.getItem(`${_tokenPrefix()}_token_scope`) || '';
}

function clearTokens() {
    const prefix = _tokenPrefix();
    localStorage.removeItem(`${prefix}_access_token`);
    localStorage.removeItem(`${prefix}_refresh_token`);
    localStorage.removeItem(`${prefix}_token_scope`);
}

function isLoggedIn() {
    return !!getAccessToken();
}

function isAdmin() {
    return getTokenScope() === 'admin:all';
}

// ─── API Helpers ─────────────────────────────────────────────────────────────

async function apiCall(method, path, body = null, requireAuth = true) {
    const headers = { 'Content-Type': 'application/json' };

    if (requireAuth) {
        const token = getAccessToken();
        if (!token) {
            window.location.href = _loginUrl();
            return null;
        }
        headers['Authorization'] = `Bearer ${token}`;
    }

    const opts = { method, headers };
    if (body) {
        opts.body = JSON.stringify(body);
    }

    try {
        const resp = await fetch(`${API_BASE}${path}`, opts);

        // Token expired — try refresh
        if (resp.status === 401 && requireAuth) {
            const refreshed = await tryRefreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${getAccessToken()}`;
                const retry = await fetch(`${API_BASE}${path}`, { ...opts, headers });
                return await retry.json();
            } else {
                clearTokens();
                window.location.href = _loginUrl();
                return null;
            }
        }

        return await resp.json();
    } catch (err) {
        console.error('API call failed:', err);
        showAlert('error', 'Network error. Please try again.');
        return null;
    }
}

async function tryRefreshToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
        const resp = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (resp.ok) {
            const data = await resp.json();
            saveTokens(data);
            return true;
        }
    } catch (err) {
        console.error('Token refresh failed:', err);
    }
    return false;
}

// ─── UI Helpers ──────────────────────────────────────────────────────────────

function showAlert(type, message) {
    // Find existing alert or create one
    let alert = document.querySelector('.alert');
    if (!alert) {
        alert = document.createElement('div');
        alert.className = 'alert';
        const form = document.querySelector('form') || document.querySelector('.main-content');
        if (form) form.prepend(alert);
    }
    alert.className = `alert alert-${type} show`;
    alert.textContent = message;
}

function hideAlert() {
    const alert = document.querySelector('.alert');
    if (alert) alert.classList.remove('show');
}

let _loaderTimeout = null;

function showPageLoader() {
    const el = document.getElementById('page-loader');
    if (!el) return;
    el.classList.remove('loader-hidden');
    // Safety: never block the UI for more than 8 s
    clearTimeout(_loaderTimeout);
    _loaderTimeout = setTimeout(hidePageLoader, 8000);
}

function hidePageLoader() {
    clearTimeout(_loaderTimeout);
    const el = document.getElementById('page-loader');
    if (!el) return;
    el.classList.add('loader-hidden');
}

function setLoading(btn, loading) {
    if (loading) {
        btn.dataset.originalText = btn.textContent;
        btn.innerHTML = '<span class="spinner"></span> Loading...';
        btn.disabled = true;
    } else {
        btn.textContent = btn.dataset.originalText || 'Submit';
        btn.disabled = false;
    }
}

function formatDuration(secs) {
    if (!secs) return '—';
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function formatUnixTs(unix_secs) {
    if (!unix_secs) return '—';
    const d = new Date(unix_secs * 1000);
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function localDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

function animateCount(el, target, duration = 900, fmt = null) {
    if (!el || typeof target !== 'number' || isNaN(target)) return;
    const start = performance.now();
    const format = fmt || (n => String(Math.round(n)));
    function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = format(target * eased);
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function fmtChars(n) {
    const v = Math.round(n);
    if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
    if (v >= 1000)    return (v / 1000).toFixed(1) + 'K';
    return String(v);
}

// ─── Auth Forms ──────────────────────────────────────────────────────────────

function initLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const btn = form.querySelector('button[type="submit"]');
        setLoading(btn, true);

        const username = form.querySelector('#username').value.trim();
        const password = form.querySelector('#password').value;

        const data = await apiCall('POST', '/auth/login', { username, password }, false);

        if (data && data.access_token) {
            saveTokens(data);
            if (data.scope === 'admin:all') {
                window.location.href = `${API_BASE}/pages/mngr-sys-access-78/dashboard`;
            } else {
                window.location.href = `${API_BASE}/pages/dashboard`;
            }
        } else {
            showAlert('error', (data && data.detail) || 'Login failed. Check your credentials.');
            setLoading(btn, false);
        }
    });
}

function initRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) return;

    const agentIdInput = form.querySelector('#elevenlabs_agent_id');
    if (agentIdInput) {
        agentIdInput.addEventListener('blur', async () => {
            const agentId = agentIdInput.value.trim();
            if (!agentId) return;
            const firstMsgInput = document.getElementById('first_message');
            const firstMsgLoading = document.getElementById('first-message-loading');
            try {
                if (firstMsgLoading) firstMsgLoading.style.display = 'inline';
                const resp = await fetch(`${API_BASE}/auth/check-agent?agent_id=${encodeURIComponent(agentId)}`);
                if (firstMsgLoading) firstMsgLoading.style.display = 'none';
                if (!resp.ok) return;
                const data = await resp.json();
                const existing = document.getElementById('agent-id-error');
                if (existing) existing.remove();
                if (data.taken) {
                    const errEl = document.createElement('p');
                    errEl.id = 'agent-id-error';
                    errEl.style.cssText = 'color:#ef4444;font-size:0.85rem;margin-top:0.25rem;';
                    errEl.textContent = `This agent is already registered to "${data.client_name}".`;
                    agentIdInput.parentElement.appendChild(errEl);
                    if (firstMsgInput) firstMsgInput.value = '';
                } else {
                    if (firstMsgInput && data.first_message != null) {
                        firstMsgInput.value = data.first_message;
                    }
                }
            } catch (_) {
                if (firstMsgLoading) firstMsgLoading.style.display = 'none';
            }
        });
        agentIdInput.addEventListener('input', () => {
            const existing = document.getElementById('agent-id-error');
            if (existing) existing.remove();
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const btn = form.querySelector('button[type="submit"]');
        setLoading(btn, true);

        if (document.getElementById('agent-id-error')) {
            showAlert('error', 'Please use a different Agent ID before continuing.');
            setLoading(btn, false);
            return;
        }

        const body = {
            username: form.querySelector('#username').value.trim(),
            password: form.querySelector('#password').value,
            client_name: form.querySelector('#client_name').value.trim(),
            elevenlabs_agent_id: form.querySelector('#elevenlabs_agent_id').value.trim(),
            email: form.querySelector('#email').value.trim(),
            timezone: form.querySelector('#timezone').value || 'Asia/Kolkata',
            business_info: (form.querySelector('#business_info').value || '').trim(),
            first_message: (form.querySelector('#first_message') ? form.querySelector('#first_message').value.trim() : ''),
        };

        const data = await apiCall('POST', '/auth/register', body, false);

        if (data && data.access_token) {
            saveTokens(data);
            window.location.href = `${API_BASE}/pages/dashboard`;
        } else {
            showAlert('error', (data && data.detail) || 'Registration failed.');
            setLoading(btn, false);
        }
    });
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

let currentProfile = null;

async function initDashboard() {
    const profileSection = document.getElementById('profile-data');
    if (!profileSection) return;

    if (!isLoggedIn()) {
        window.location.href = _loginUrl();
        return;
    }

    showPageLoader();

    // Load profile
    const profile = await apiCall('GET', '/client-portal/profile');
    if (profile) {
        currentProfile = profile;
        document.getElementById('business-name').textContent = profile.business_name || 'Unnamed';
        document.getElementById('client-id').textContent = profile.id || '';
        const agentIdEl = document.getElementById('assistant-agent-id-display');
        if (agentIdEl) agentIdEl.textContent = profile.elevenlabs_agent_id || '—';

        // Limit-exceeded state — show banner, tint screen, update agent card immediately
        if (profile.is_active === false && profile.deactivation_reason === 'limit_exceeded') {
            setPageTint('deactivated');
            showLimitBanner();
            updateAgentCardForLimit();
        }

        // Google Calendar Status
        const calBox = document.getElementById('calendar-status-box');
        if (calBox) {
            if (profile.google_calendar_linked) {
                calBox.innerHTML = `
                    <p style="font-size: 0.85rem; color: var(--color-text-secondary); margin-bottom: var(--space-md);">
                        <span style="color: var(--color-success)">✓</span> Linked to your Google account.
                    </p>
                    <button class="btn btn-sm btn-secondary" onclick="startGoogleAuth()">Reconnect / Sync</button>
                `;
            }
        }

    }

    // Load this month's character usage
    const now = new Date();
    const monthStart = localDateStr(new Date(now.getFullYear(), now.getMonth(), 1));
    const today = localDateStr(now);
    const usage = await apiCall('GET', `/client-portal/token-usage?start_date=${monthStart}&end_date=${today}&summary_only=true`);
    if (usage) {
        const chars = usage.total_characters || 0;
        const usageEl = document.getElementById('usage-chars-count');
        if (usageEl) animateCount(usageEl, chars, 900, fmtChars);

        const limit = currentProfile && currentProfile.monthly_character_limit;
        if (limit) {
            const pct = Math.min(100, Math.round((chars / limit) * 100));
            const barEl  = document.getElementById('usage-limit-bar');
            const fillEl = document.getElementById('usage-limit-fill');
            const textEl = document.getElementById('usage-limit-text');
            if (barEl)  barEl.style.display = 'block';
            if (fillEl) setTimeout(() => { fillEl.style.width = pct + '%'; }, 300);
            if (textEl) textEl.textContent = `${chars.toLocaleString()} / ${limit.toLocaleString()} chars (${pct}%)`;
            if (pct >= 90 && fillEl) {
                fillEl.style.background = '#e53e3e';
                fillEl.classList.add('fill-critical');
            } else if (pct >= 70 && fillEl) {
                fillEl.style.background = '#f39c12';
            }

            // Tint the screen based on usage (only if not already showing deactivated tint)
            const alreadyDeactivated = currentProfile.is_active === false
                && currentProfile.deactivation_reason === 'limit_exceeded';
            if (!alreadyDeactivated) {
                if (pct >= 90)      setPageTint('critical');
                else if (pct >= 70) setPageTint('warning');
                else                setPageTint('none');
            }
        }
    }

    // Profile + usage loaded — reveal the page
    hidePageLoader();

    // Load appointments
    const appts = await apiCall('GET', '/client-portal/appointments');
    if (appts && appts.appointments) {
        animateCount(document.getElementById('appointments-count'), appts.total || 0);
        const tbody = document.getElementById('appointments-tbody');
        if (tbody) {
            tbody.innerHTML = appts.appointments.slice(0, 10).map(a => `
                <tr>
                    <td>${a.customer_name || ''}</td>
                    <td>${a.service_name || ''}</td>
                    <td>${a.date_time || ''}</td>
                    <td><span class="badge badge-active">${a.status || ''}</span></td>
                </tr>
            `).join('');
        }
    }

    // Load call logs
    const logs = await apiCall('GET', '/client-portal/call-logs');
    if (logs && logs.call_logs) {
        animateCount(document.getElementById('calls-count'), logs.total || 0);
    }

    // Check for URL pulses (success/error from OAuth)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('google_linked') === 'success') {
        showAlert('success', '✨ Google Calendar successfully connected!');
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.get('google_linked') === 'error') {
        showAlert('error', 'Failed to connect Google Calendar. Please try again.');
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Init Edit Profile Form
    initEditProfileForm();
}

function startGoogleAuth() {
    const token = getAccessToken();
    if (!token) return;
    // Redirect to backend auth initiator (no /automiteui prefix for this specific route)
    const returnTo = encodeURIComponent(window.location.href);
    window.location.href = `/automiteaiapplication/client/auth/google/login?token=${token}&return_to=${returnTo}`;
}

// ─── Edit Profile Modal ──────────────────────────────────────────────────────

const DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function openEditProfileModal() {
    const modal = document.getElementById('edit-profile-modal');
    if (!modal) return;

    if (!currentProfile) {
        showAlert('error', 'Profile not loaded yet. Please wait a moment and try again.');
        return;
    }

    // Populate fields
    document.getElementById('edit-business-name').value = currentProfile.business_name || '';
    document.getElementById('edit-agent-id').value = currentProfile.elevenlabs_agent_id || '';
    document.getElementById('edit-new-password').value = '';

    const kbTextarea = document.getElementById('ai-parse-text');
    if (kbTextarea) kbTextarea.value = currentProfile.knowledge_base_text || '';

    // Populate Operating Hours
    const hoursContainer = document.getElementById('operating-hours-container');
    hoursContainer.innerHTML = '';
    const hours = currentProfile.operating_hours || {};
    DAYS_OF_WEEK.forEach(day => {
        hoursContainer.innerHTML += `
            <div class="hours-row">
                <div class="hours-day">${day}</div>
                <input type="text" class="hours-input" id="hours-${day}" value="${hours[day] || 'Closed'}" placeholder="09:00 - 17:00">
            </div>
        `;
    });

    modal.style.display = 'flex';
}

function closeEditProfileModal() {
    document.getElementById('edit-profile-modal').style.display = 'none';
}

// ─── Talk to Agent Modal ──────────────────────────────────────────────────────

const ELEVENLABS_WIDGET_SCRIPT_ID = 'elevenlabs-convai-script';
const ELEVENLABS_WIDGET_SRC = 'https://elevenlabs.io/convai-widget/index.js';

function openTalkModal() {
    const agentId = currentProfile && currentProfile.elevenlabs_agent_id
        ? currentProfile.elevenlabs_agent_id.trim()
        : '';

    if (!agentId) {
        showAlert('error', 'No Agent ID configured. Please add your ElevenLabs Agent ID in Edit Profile first.');
        return;
    }

    const modal = document.getElementById('talk-agent-modal');
    const container = document.getElementById('talk-agent-widget-container');
    if (!modal || !container) return;

    container.innerHTML = '';

    const widget = document.createElement('elevenlabs-convai');
    widget.setAttribute('agent-id', agentId);
    container.appendChild(widget);

    if (!document.getElementById(ELEVENLABS_WIDGET_SCRIPT_ID)) {
        const script = document.createElement('script');
        script.id = ELEVENLABS_WIDGET_SCRIPT_ID;
        script.src = ELEVENLABS_WIDGET_SRC;
        script.async = true;
        script.type = 'text/javascript';
        document.body.appendChild(script);
    }

    modal.style.display = 'flex';
}

function closeTalkModal() {
    const modal = document.getElementById('talk-agent-modal');
    const container = document.getElementById('talk-agent-widget-container');
    if (modal) modal.style.display = 'none';
    if (container) container.innerHTML = '';
}

function setDefaultHours() {
    DAYS_OF_WEEK.forEach(day => {
        const inp = document.getElementById(`hours-${day}`);
        if (inp) {
            if (day === 'Saturday' || day === 'Sunday') {
                inp.value = 'Closed';
            } else {
                inp.value = '09:00 - 17:00';
            }
        }
    });
}


function initEditProfileForm() {
    const form = document.getElementById('edit-profile-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = form.querySelector('button[type="submit"]');
        setLoading(btn, true);

        // Gather Operating Hours
        const operating_hours = {};
        DAYS_OF_WEEK.forEach(day => {
            operating_hours[day] = document.getElementById(`hours-${day}`).value.trim() || 'Closed';
        });

        const kbTextareaEl = document.getElementById('ai-parse-text');
        const updates = {
            business_name: document.getElementById('edit-business-name').value.trim(),
            operating_hours: operating_hours,
            knowledge_base_text: kbTextareaEl ? kbTextareaEl.value.trim() : '',
            elevenlabs_agent_id: document.getElementById('edit-agent-id').value.trim(),
        };

        const result = await apiCall('PUT', '/client-portal/profile', updates);

        // Handle password change if filled in
        const newPassword = document.getElementById('edit-new-password').value;
        if (newPassword) {
            const pwResult = await apiCall('POST', '/client-portal/change-password', { new_password: newPassword });
            if (!pwResult || pwResult.status !== 'password_updated') {
                showAlert('error', pwResult?.detail || 'Profile saved but password change failed.');
                setLoading(btn, false);
                return;
            }
        }

        if (result && result.status === 'updated') {
            showAlert('success', 'Profile updated successfully!');
            closeEditProfileModal();
            initDashboard();
        } else {
            showAlert('error', 'Failed to update profile.');
        }

        setLoading(btn, false);
    });
}

// ─── Admin Dashboard ─────────────────────────────────────────────────────────

async function initAdminDashboard() {
    const dashboard = document.getElementById('admin-dashboard');
    if (!dashboard) return;

    if (!isLoggedIn() || !isAdmin()) {
        window.location.href = `${API_BASE}/pages/mngr-sys-access-78`;
        return;
    }

    showPageLoader();

    // Load overview stats
    const stats = await apiCall('GET', '/mngr-sys-access-78/dashboard');
    if (stats) {
        animateCount(document.getElementById('total-clients'), stats.total_clients || 0);
        animateCount(document.getElementById('active-clients'), stats.active_clients || 0);
        animateCount(document.getElementById('inactive-clients'), stats.inactive_clients || 0);
        animateCount(document.getElementById('total-calls'), stats.total_call_logs || 0);
    }

    // Load clients table
    const clientsData = await apiCall('GET', '/mngr-sys-access-78/clients');
    if (clientsData && clientsData.clients) {
        const tbody = document.getElementById('clients-tbody');
        if (tbody) {
            tbody.innerHTML = clientsData.clients.map(c => {
                const limit = c.monthly_character_limit;
                const limitLabel = limit != null
                    ? `<span style="font-size:0.8rem;">${limit.toLocaleString()}</span>`
                    : `<span style="color:var(--color-text-secondary);font-size:0.75rem;">Unlimited</span>`;
                const deactReason = c.deactivation_reason === 'limit_exceeded'
                    ? `<span style="display:block;font-size:0.7rem;color:var(--color-magenta);">Limit exceeded</span>`
                    : '';
                const safeName = (c.business_name || 'Client').replace(/'/g, "\\'");
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
            }).join('');
        }
    }

    hidePageLoader();
}

async function refreshAdminStats() {
    const stats = await apiCall('GET', '/mngr-sys-access-78/dashboard');
    if (!stats) return;
    animateCount(document.getElementById('total-clients'),    stats.total_clients   || 0);
    animateCount(document.getElementById('active-clients'),   stats.active_clients   || 0);
    animateCount(document.getElementById('inactive-clients'), stats.inactive_clients || 0);
    animateCount(document.getElementById('total-calls'),      stats.total_call_logs  || 0);
}

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

async function deleteClient(clientId, businessName) {
    if (!confirm(`Permanently delete "${businessName}"?\n\nThis will remove the client, their user account, appointments, call logs, and customers. This cannot be undone.`)) return;
    const data = await apiCall('DELETE', `/mngr-sys-access-78/clients/${clientId}`);
    if (data) {
        showAlert('success', `Client "${businessName}" deleted.`);
        setTimeout(() => location.reload(), 1200);
    }
}

async function refreshToolTokens() {
    const data = await apiCall('POST', '/mngr-sys-access-78/refresh-tool-tokens');
    if (data) {
        showAlert('success', `Tool tokens rotated for ${data.clients_affected} client(s).`);
    }
}

// ─── Character Limit Modal ───────────────────────────────────────────────────

let _charLimitClientId = null;

function openCharLimitModal(clientId, clientName, currentLimit) {
    _charLimitClientId = clientId;
    document.getElementById('char-limit-client-name').textContent = clientName;
    document.getElementById('char-limit-input').value = currentLimit != null ? currentLimit : '';
    document.getElementById('add-chars-input').value = '';
    document.getElementById('char-limit-modal').style.display = 'flex';
}

function closeCharLimitModal() {
    _charLimitClientId = null;
    document.getElementById('char-limit-modal').style.display = 'none';
}

async function saveCharLimit() {
    if (!_charLimitClientId) return;
    const raw = document.getElementById('char-limit-input').value.trim();
    const limit = raw === '' ? null : parseInt(raw, 10);
    if (raw !== '' && (isNaN(limit) || limit < 0)) {
        showAlert('error', 'Please enter a valid non-negative number, or leave blank for unlimited.');
        return;
    }
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${_charLimitClientId}/character-limit`, {
        monthly_character_limit: limit,
    });
    if (data) {
        const base = limit != null ? `Limit set to ${limit.toLocaleString()} characters.` : 'Limit removed (unlimited).';
        showAlert('success', data.reactivated ? `${base} Client reactivated.` : base);
        closeCharLimitModal();
        setTimeout(() => location.reload(), 1000);
    }
}

async function addClientCharacters() {
    if (!_charLimitClientId) return;
    const amount = parseInt(document.getElementById('add-chars-input').value, 10);
    if (isNaN(amount) || amount <= 0) {
        showAlert('error', 'Please enter a positive number of characters to add.');
        return;
    }
    const data = await apiCall('POST', `/mngr-sys-access-78/clients/${_charLimitClientId}/add-characters`, {
        characters: amount,
    });
    if (data) {
        const msg = data.reactivated
            ? `Added ${amount.toLocaleString()} chars. New limit: ${data.new_limit.toLocaleString()}. Client reactivated.`
            : `Added ${amount.toLocaleString()} chars. New limit: ${data.new_limit.toLocaleString()}.`;
        showAlert('success', msg);
        closeCharLimitModal();
        setTimeout(() => location.reload(), 1200);
    }
}

function logout() {
    clearTokens();
    window.location.href = _loginUrl();
}

// ─── Client Token Usage Modal ────────────────────────────────────────────────

function openClientUsageModal() {
    const modal = document.getElementById('client-usage-modal');
    if (!modal) return;

    const now = new Date();
    const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    document.getElementById('client-usage-start-date').value = localDateStr(firstOfMonth);
    document.getElementById('client-usage-end-date').value = localDateStr(now);

    document.getElementById('client-usage-stats').style.display = 'none';
    document.getElementById('client-usage-loading').style.display = 'none';
    document.getElementById('client-usage-empty').style.display = 'none';
    modal.style.display = 'flex';
}

function closeClientUsageModal() {
    const modal = document.getElementById('client-usage-modal');
    if (modal) modal.style.display = 'none';
}

async function fetchClientUsage() {
    const startDate = document.getElementById('client-usage-start-date').value;
    const endDate = document.getElementById('client-usage-end-date').value;
    if (!startDate || !endDate) { showAlert('error', 'Please select a date range.'); return; }

    document.getElementById('client-usage-stats').style.display = 'none';
    document.getElementById('client-usage-empty').style.display = 'none';
    document.getElementById('client-usage-loading').style.display = 'block';

    const data = await apiCall('GET', `/client-portal/token-usage?start_date=${startDate}&end_date=${endDate}`);
    document.getElementById('client-usage-loading').style.display = 'none';

    if (!data) return;

    const convos = data.conversations || [];
    if (data.conversation_count === 0) {
        document.getElementById('client-usage-empty').style.display = 'block';
        return;
    }

    document.getElementById('client-stat-characters').textContent = (data.total_characters || 0).toLocaleString();
    document.getElementById('client-stat-conversations').textContent = data.conversation_count || 0;
    document.getElementById('client-stat-duration').textContent = formatDuration(data.total_duration_secs);
    const costLabel = `Est. Cost (${data.currency || 'USD'})`;
    document.getElementById('client-stat-cost-label').textContent = costLabel;
    document.getElementById('client-stat-cost').textContent = data.estimated_cost != null
        ? `${data.currency || ''} ${Number(data.estimated_cost).toFixed(4)}`
        : '—';

    const tbody = document.getElementById('client-usage-conversations-tbody');
    if (tbody) {
        tbody.innerHTML = convos.map(c => `
            <tr>
                <td style="white-space:nowrap;">${formatUnixTs(c.start_time_unix_secs)}</td>
                <td>${formatDuration(c.call_duration_secs)}</td>
                <td>${(c.characters || 0).toLocaleString()}</td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${(c.call_summary_title || '').replace(/"/g,'&quot;')}">${c.call_summary_title || '—'}</td>
                <td><span class="badge ${c.call_successful === 'success' ? 'badge-active' : 'badge-inactive'}">${c.call_successful || c.status || '—'}</span></td>
            </tr>
        `).join('');
    }

    document.getElementById('client-usage-stats').style.display = 'block';
}

// ─── Admin Token Usage Modal ─────────────────────────────────────────────────

let _adminUsageClientId = null;

function openAdminUsageModal(clientId, businessName) {
    _adminUsageClientId = clientId;
    document.getElementById('admin-usage-client-name').textContent = businessName || clientId;

    const now = new Date();
    const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    document.getElementById('admin-usage-start-date').value = localDateStr(firstOfMonth);
    document.getElementById('admin-usage-end-date').value = localDateStr(now);
    document.getElementById('admin-usage-price-override').value = '';

    document.getElementById('admin-usage-stats').style.display = 'none';
    document.getElementById('admin-usage-loading').style.display = 'none';
    document.getElementById('admin-usage-empty').style.display = 'none';
    document.getElementById('admin-usage-modal').style.display = 'flex';
}

function closeAdminUsageModal() {
    document.getElementById('admin-usage-modal').style.display = 'none';
    _adminUsageClientId = null;
}

async function fetchAdminUsage() {
    if (!_adminUsageClientId) return;
    const startDate = document.getElementById('admin-usage-start-date').value;
    const endDate = document.getElementById('admin-usage-end-date').value;
    if (!startDate || !endDate) { showAlert('error', 'Please select a date range.'); return; }

    document.getElementById('admin-usage-stats').style.display = 'none';
    document.getElementById('admin-usage-empty').style.display = 'none';
    document.getElementById('admin-usage-loading').style.display = 'block';

    const data = await apiCall('GET', `/mngr-sys-access-78/token-usage/${_adminUsageClientId}?start_date=${startDate}&end_date=${endDate}`);
    document.getElementById('admin-usage-loading').style.display = 'none';

    if (!data) return;

    const convos = data.conversations || [];
    if (data.conversation_count === 0) {
        document.getElementById('admin-usage-empty').style.display = 'block';
        return;
    }

    document.getElementById('admin-stat-characters').textContent = (data.total_characters || 0).toLocaleString();
    document.getElementById('admin-stat-conversations').textContent = data.conversation_count || 0;
    document.getElementById('admin-stat-duration').textContent = formatDuration(data.total_duration_secs);
    document.getElementById('admin-stat-cost-label').textContent = `Est. Cost (${data.currency || 'USD'})`;
    document.getElementById('admin-stat-cost').textContent = data.estimated_cost != null
        ? `${data.currency || ''} ${Number(data.estimated_cost).toFixed(4)}`
        : '—';
    if (data.price_per_character != null) {
        document.getElementById('admin-usage-price-override').placeholder = `Current: ${data.price_per_character}`;
    }

    const tbody = document.getElementById('admin-usage-conversations-tbody');
    if (tbody) {
        tbody.innerHTML = convos.map(c => `
            <tr>
                <td style="white-space:nowrap;">${formatUnixTs(c.start_time_unix_secs)}</td>
                <td>${formatDuration(c.call_duration_secs)}</td>
                <td>${(c.characters || 0).toLocaleString()}</td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${(c.call_summary_title || '').replace(/"/g,'&quot;')}">${c.call_summary_title || '—'}</td>
                <td><span class="badge ${c.call_successful === 'success' ? 'badge-active' : 'badge-inactive'}">${c.call_successful || c.status || '—'}</span></td>
            </tr>
        `).join('');
    }

    document.getElementById('admin-usage-stats').style.display = 'block';
}

async function saveClientPriceOverride() {
    if (!_adminUsageClientId) return;
    const val = document.getElementById('admin-usage-price-override').value.trim();
    const price = val === '' ? null : parseFloat(val);
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${_adminUsageClientId}/pricing`, { price_per_character: price });
    if (data && data.status === 'updated') {
        showAlert('success', 'Price override saved.');
    }
}

// ─── Pricing Config Modal ─────────────────────────────────────────────────────

async function openPricingModal() {
    document.getElementById('pricing-modal').style.display = 'flex';
    const data = await apiCall('GET', '/mngr-sys-access-78/pricing');
    if (!data) return;

    const g = data.global || {};
    document.getElementById('global-price-input').value = g.price_per_character != null ? g.price_per_character : '';
    const currSelect = document.getElementById('global-currency-select');
    if (currSelect && g.currency) currSelect.value = g.currency;

    const overrides = data.client_overrides || [];
    const container = document.getElementById('pricing-overrides-container');
    if (container) {
        if (overrides.length === 0) {
            container.innerHTML = '<p style="color:var(--color-text-secondary);font-size:0.85rem;">No per-client overrides set.</p>';
        } else {
            container.innerHTML = `<table class="data-table"><thead><tr><th>Business</th><th>Client ID</th><th>Price/Char</th><th>Action</th></tr></thead><tbody>
                ${overrides.map(o => `
                    <tr>
                        <td>${o.business_name || '—'}</td>
                        <td><code style="font-size:0.7rem;color:var(--color-text-secondary)">${o.client_id}</code></td>
                        <td>${o.price_per_character}</td>
                        <td><button class="btn btn-sm btn-secondary" onclick="clearClientOverride('${o.client_id}')">Clear</button></td>
                    </tr>
                `).join('')}
            </tbody></table>`;
        }
    }
}

function closePricingModal() {
    document.getElementById('pricing-modal').style.display = 'none';
}

async function savePricingConfig() {
    const price = parseFloat(document.getElementById('global-price-input').value);
    if (isNaN(price) || price < 0) { showAlert('error', 'Enter a valid price (>= 0).'); return; }
    const currency = document.getElementById('global-currency-select').value;
    const applyToAll = document.getElementById('apply-to-all-checkbox').checked;

    const data = await apiCall('PUT', '/mngr-sys-access-78/pricing', {
        price_per_character: price,
        currency,
        apply_to_all: applyToAll,
    });
    if (data && data.status === 'updated') {
        showAlert('success', applyToAll ? 'Global price saved and applied to all clients.' : 'Global price saved.');
        openPricingModal();
    }
}

async function clearClientOverride(clientId) {
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${clientId}/pricing`, { price_per_character: null });
    if (data && data.status === 'updated') {
        openPricingModal();
    }
}

// ─── New Agent Modal ──────────────────────────────────────────────────────────

let _selectedAgentId = null;
let _agentSearchTimeout = null;

async function openNewAgentModal() {
    _selectedAgentId = null;
    document.getElementById('agent-search-input').value = '';
    document.getElementById('selected-agent-section').style.display = 'none';
    document.getElementById('new-agent-result').style.display = 'none';
    document.getElementById('new-agent-modal').style.display = 'flex';
    await loadAgentsList('');
}

function closeNewAgentModal() {
    document.getElementById('new-agent-modal').style.display = 'none';
    _selectedAgentId = null;
}

async function loadAgentsList(search) {
    const container = document.getElementById('agents-list-container');
    if (!container) return;
    container.innerHTML = '<p style="padding:var(--space-md);color:var(--color-text-secondary);font-size:0.85rem;">Loading...</p>';

    const qs = search ? `?search=${encodeURIComponent(search)}&page_size=50` : '?page_size=50';
    const data = await apiCall('GET', `/mngr-sys-access-78/elevenlabs/agents${qs}`);
    if (!data || !data.agents) {
        container.innerHTML = '<p style="padding:var(--space-md);color:var(--color-error,#f44);font-size:0.85rem;">Failed to load agents.</p>';
        return;
    }

    if (data.agents.length === 0) {
        container.innerHTML = '<p style="padding:var(--space-md);color:var(--color-text-secondary);font-size:0.85rem;">No agents found.</p>';
        return;
    }

    container.innerHTML = data.agents.map(a => {
        const safeName = (a.name || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
        const safeId   = (a.agent_id || '').replace(/"/g,'&quot;');
        return `
        <div data-agent-id="${safeId}" data-agent-name="${safeName}"
             onclick="selectAgent(this.dataset.agentId, this.dataset.agentName)"
             style="padding:10px 14px;cursor:pointer;border-bottom:1px solid rgba(26,77,58,0.10);transition:background 0.15s;"
             onmouseover="this.style.background='rgba(26,77,58,0.05)'" onmouseout="this.style.background=''">
            <p style="margin:0;font-size:0.88rem;color:var(--color-text-primary);">${a.name || '(unnamed)'}</p>
            <p style="margin:2px 0 0 0;font-size:0.72rem;color:var(--color-text-secondary);">${a.agent_id}</p>
        </div>`;
    }).join('');
}

function searchAgentsList(value) {
    clearTimeout(_agentSearchTimeout);
    _agentSearchTimeout = setTimeout(() => loadAgentsList(value), 350);
}

async function selectAgent(agentId, agentName) {
    _selectedAgentId = agentId;
    document.getElementById('selected-agent-name-label').textContent = agentName || agentId;
    document.getElementById('selected-agent-id-label').textContent = agentId;
    document.getElementById('new-agent-name-input').value = agentName ? `Copy of ${agentName}` : '';
    document.getElementById('new-agent-prompt-input').value = 'Loading prompt...';
    document.getElementById('selected-agent-section').style.display = 'block';
    document.getElementById('new-agent-result').style.display = 'none';

    const data = await apiCall('GET', `/mngr-sys-access-78/elevenlabs/agents/${agentId}`);
    if (data && data.prompt != null) {
        document.getElementById('new-agent-prompt-input').value = data.prompt;
    } else {
        document.getElementById('new-agent-prompt-input').value = '';
    }
}

async function createNewAgent() {
    if (!_selectedAgentId) return;
    const name = document.getElementById('new-agent-name-input').value.trim();
    const prompt = document.getElementById('new-agent-prompt-input').value.trim();
    const btn = document.getElementById('create-agent-btn');
    setLoading(btn, true);

    const data = await apiCall('POST', '/mngr-sys-access-78/elevenlabs/agents/duplicate', {
        source_agent_id: _selectedAgentId,
        name: name || null,
        prompt: prompt || null,
    });
    setLoading(btn, false);

    if (data && data.status === 'created') {
        document.getElementById('new-agent-result-id').textContent = data.new_agent_id;
        document.getElementById('new-agent-result').style.display = 'block';
        document.getElementById('selected-agent-section').style.display = 'none';
    } else {
        showAlert('error', (data && data.detail) || 'Failed to create agent.');
    }
}

// ─── Limit Banner & Coming Soon ──────────────────────────────────────────────

function setPageTint(level) {
    const el = document.getElementById('page-tint');
    if (!el) return;
    el.className = level === 'none' ? '' : `tint-${level}`;
}

function showLimitBanner() {
    const banner = document.getElementById('limit-banner');
    if (banner) banner.style.display = 'block';
}

function dismissLimitBanner() {
    const banner = document.getElementById('limit-banner');
    if (!banner) return;
    banner.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    banner.style.opacity = '0';
    banner.style.transform = 'translateY(-16px)';
    setTimeout(() => { banner.style.display = 'none'; }, 300);
}

function updateAgentCardForLimit() {
    const card = document.getElementById('ai-assistant-card');
    if (card) card.classList.add('agent-card--paused');

    const badgeContainer = document.getElementById('assistant-badge-container');
    if (badgeContainer) {
        badgeContainer.innerHTML = `
            <span class="badge badge-inactive" style="font-size:0.75rem;">⚠️ Agent Paused</span>
            <button class="btn btn-sm limit-banner-topup" onclick="showComingSoon()" style="margin-top:4px;">💳 Top Up Credits</button>
        `;
    }
}

function showComingSoon() {
    const existing = document.querySelector('.coming-soon-toast');
    if (existing) return;

    const toast = document.createElement('div');
    toast.className = 'coming-soon-toast';
    toast.innerHTML = `<span class="toast-emoji">😊</span> Payment gateway coming soon!`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 320);
    }, 2800);
}

// ─── Page Animations ─────────────────────────────────────────────────────────

function initAnimations() {
    // Navbar deepens shadow on scroll
    const nav = document.querySelector('.navbar');
    if (nav) {
        window.addEventListener('scroll', () => {
            nav.classList.toggle('scrolled', window.scrollY > 20);
        }, { passive: true });
    }

    // Staggered scroll-reveal for main page cards
    if (!('IntersectionObserver' in window)) return;

    const cards = [];
    document.querySelectorAll('.container').forEach(container => {
        // Skip containers inside modals
        if (container.closest('.modal-overlay')) return;
        container.querySelectorAll(':scope > .glass-card, :scope > .dashboard-grid > .glass-card').forEach(el => {
            cards.push(el);
        });
    });

    if (!cards.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -24px 0px' });

    cards.forEach((el, i) => {
        el.classList.add('reveal');
        el.style.transitionDelay = `${i * 0.07}s`;
        observer.observe(el);
    });
}

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initAnimations();
    initLoginForm();
    initRegisterForm();
    // On non-dashboard pages (login, register) hide the loader immediately
    const hasDashboard = document.getElementById('profile-data') || document.getElementById('admin-dashboard');
    if (!hasDashboard) hidePageLoader();
    initDashboard();
    initAdminDashboard();
});
