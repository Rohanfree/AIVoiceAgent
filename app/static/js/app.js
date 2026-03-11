/**
 * app.js — Automite AI Frontend JavaScript
 *
 * Handles:
 *  - Login / Register forms (fetch-based API calls)
 *  - Token management (localStorage)
 *  - Dashboard data loading
 *  - Admin panel operations
 */

const API_BASE = '/automiteui';

// ─── Token Management ────────────────────────────────────────────────────────

function saveTokens(data) {
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_scope', data.scope || 'dashboard');
}

function getAccessToken() {
    return localStorage.getItem('access_token');
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

function getTokenScope() {
    return localStorage.getItem('token_scope') || '';
}

function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_scope');
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
            window.location.href = `${API_BASE}/pages/login`;
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
                window.location.href = `${API_BASE}/pages/login`;
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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlert();

        const btn = form.querySelector('button[type="submit"]');
        setLoading(btn, true);

        const body = {
            username: form.querySelector('#username').value.trim(),
            password: form.querySelector('#password').value,
            client_name: form.querySelector('#client_name').value.trim(),
            assistant_name: form.querySelector('#assistant_name').value.trim(),
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

async function initDashboard() {
    const profileSection = document.getElementById('profile-data');
    if (!profileSection) return;

    if (!isLoggedIn()) {
        window.location.href = `${API_BASE}/pages/login`;
        return;
    }

    // Load profile
    const profile = await apiCall('GET', '/client-portal/profile');
    if (profile) {
        document.getElementById('business-name').textContent = profile.business_name || 'Unnamed';
        document.getElementById('client-id').textContent = profile.id || '';

        // Services table
        const tbody = document.getElementById('services-tbody');
        if (tbody && profile.services) {
            tbody.innerHTML = profile.services.map(svc => `
                <tr>
                    <td>${svc.name || ''}</td>
                    <td>${svc.category || '-'}</td>
                    <td>${svc.duration || 0} min</td>
                    <td>${profile.currency || 'INR'} ${svc.price || 0}</td>
                </tr>
            `).join('');
        }
    }

    // Load appointments
    const appts = await apiCall('GET', '/client-portal/appointments');
    if (appts && appts.appointments) {
        document.getElementById('appointments-count').textContent = appts.total;
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
        document.getElementById('calls-count').textContent = logs.total;
    }
}

// ─── Admin Dashboard ─────────────────────────────────────────────────────────

async function initAdminDashboard() {
    const dashboard = document.getElementById('admin-dashboard');
    if (!dashboard) return;

    if (!isLoggedIn() || !isAdmin()) {
        window.location.href = `${API_BASE}/pages/mngr-sys-access-78`;
        return;
    }

    // Load overview stats
    const stats = await apiCall('GET', '/mngr-sys-access-78/dashboard');
    if (stats) {
        document.getElementById('total-clients').textContent = stats.total_clients || 0;
        document.getElementById('active-clients').textContent = stats.active_clients || 0;
        document.getElementById('inactive-clients').textContent = stats.inactive_clients || 0;
        document.getElementById('total-calls').textContent = stats.total_call_logs || 0;
    }

    // Load clients table
    const clientsData = await apiCall('GET', '/mngr-sys-access-78/clients');
    if (clientsData && clientsData.clients) {
        const tbody = document.getElementById('clients-tbody');
        if (tbody) {
            tbody.innerHTML = clientsData.clients.map(c => `
                <tr>
                    <td>${c.business_name || 'Unnamed'}</td>
                    <td><code style="font-size:0.75rem;color:var(--color-text-secondary)">${c.id}</code></td>
                    <td><span class="badge ${c.is_active !== false ? 'badge-active' : 'badge-inactive'}">${c.is_active !== false ? 'Active' : 'Inactive'}</span></td>
                    <td>${c.subscription_status || 'active'}</td>
                    <td>
                        <button class="btn btn-sm btn-secondary" onclick="toggleClient('${c.id}', ${c.is_active === false})">
                            ${c.is_active === false ? 'Activate' : 'Deactivate'}
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    }
}

async function toggleClient(clientId, activate) {
    const data = await apiCall('PATCH', `/mngr-sys-access-78/clients/${clientId}/status`, {
        is_active: activate,
    });
    if (data) {
        showAlert('success', `Client ${data.status} successfully.`);
        setTimeout(() => location.reload(), 1000);
    }
}

async function refreshToolTokens() {
    const data = await apiCall('POST', '/mngr-sys-access-78/refresh-tool-tokens');
    if (data) {
        showAlert('success', `Tool tokens rotated for ${data.clients_affected} client(s).`);
    }
}

function logout() {
    clearTokens();
    window.location.href = `${API_BASE}/pages/login`;
}

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initLoginForm();
    initRegisterForm();
    initDashboard();
    initAdminDashboard();
});
