/* Campaign import and ElevenLabs batch-call submission. */
const CAMPAIGN_API = '/automiteaiapplication/automiteui/client-portal/campaigns';
let validatedCampaignContacts = [];

function openCampaignModal() {
    const modal = document.getElementById('campaign-modal');
    if (!modal) return;
    modal.style.display = 'block';
    document.getElementById('campaign-agent-id').textContent = 'Loading…';
    document.getElementById('campaign-agent-name').textContent = 'Loading…';
    loadCampaignAgent();
    loadCampaignPhoneNumbers();
}

function closeCampaignModal() {
    document.getElementById('campaign-modal').style.display = 'none';
}

async function campaignRequest(path, options = {}) {
    const token = localStorage.getItem('client_access_token');
    const response = await fetch(`${CAMPAIGN_API}${path}`, {
        ...options,
        headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
}

async function loadCampaignPhoneNumbers() {
    try {
        const data = await campaignRequest('/phone-numbers');
        const select = document.getElementById('campaign-phone-number');
        const previous = localStorage.getItem('campaign_phone_number_id') || '';
        select.replaceChildren(new Option(data.phone_numbers.length ? 'Select a configured number' : 'No configured phone numbers found', ''));
        for (const number of data.phone_numbers || []) select.add(new Option(`${number.label} — ${number.phone_number} (${number.provider})`, number.phone_number_id));
        select.value = (data.phone_numbers || []).some(number => number.phone_number_id === previous) ? previous : '';
        select.onchange = () => localStorage.setItem('campaign_phone_number_id', select.value);
        document.getElementById('campaign-provider-note').textContent = `${data.phone_numbers.length} configured number(s) loaded from ElevenLabs.`;
    } catch (error) {
        document.getElementById('campaign-provider-note').textContent = error.message;
    }
}

async function loadCampaignAgent() {
    try {
        const agent = await campaignRequest('/agent');
        document.getElementById('campaign-agent-id').textContent = agent.agent_id;
        document.getElementById('campaign-agent-name').textContent = agent.name;
    } catch (error) {
        document.getElementById('campaign-agent-id').textContent = 'Unavailable';
        document.getElementById('campaign-agent-name').textContent = error.message;
    }
}

async function validateCampaignUpload() {
    const file = document.getElementById('campaign-file').files[0];
    const output = document.getElementById('campaign-result');
    if (!file) { output.textContent = 'Choose a CSV or XLSX file first.'; return; }
    const form = new FormData();
    form.append('file', file);
    output.textContent = 'Validating rows…';
    try {
        const result = await campaignRequest('/upload', { method: 'POST', body: form });
        const lines = [`${result.valid_rows} valid of ${result.total_rows} rows; ${result.invalid_rows} invalid.`];
        for (const error of result.errors || []) lines.push(`Row ${error.row}: ${error.issues.join(', ')}`);
        if (result.blocker) lines.push(result.blocker);
        output.textContent = lines.join('\n');
        output.style.whiteSpace = 'pre-line';
        validatedCampaignContacts = result.contacts || [];
        document.getElementById('campaign-launch').disabled = !result.launch_available || !validatedCampaignContacts.length;
    } catch (error) {
        output.textContent = error.message;
    }
}

async function launchCampaign() {
    const output = document.getElementById('campaign-result');
    const phoneNumberId = document.getElementById('campaign-phone-number').value;
    if (!phoneNumberId || !validatedCampaignContacts.length) {
        output.textContent = 'Select a configured number and validate a contact file before submitting.';
        return;
    }
    const button = document.getElementById('campaign-launch');
    button.disabled = true;
    output.textContent = 'Submitting batch to ElevenLabs…';
    try {
        const result = await campaignRequest('/launch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone_number_id: phoneNumberId, contacts: validatedCampaignContacts }) });
        output.textContent = `Batch submitted. ID: ${result.batch_id || 'unknown'}; status: ${result.status || 'pending'}; scheduled contacts: ${result.scheduled_recipients}; do-not-call contacts excluded: ${result.excluded_do_not_call}.`;
        validatedCampaignContacts = [];
    } catch (error) {
        output.textContent = error.message;
        button.disabled = false;
    }
}
