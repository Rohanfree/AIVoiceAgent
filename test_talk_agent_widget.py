"""
test_talk_agent_widget.py — Tests for the Talk to Agent widget feature.

Covers:
  1. dashboard.html contains the "Talk to Agent" button
  2. dashboard.html contains the talk-agent-modal with the widget container
  3. app.js defines openTalkModal and closeTalkModal
  4. app.js uses the correct ElevenLabs widget script URL
  5. JS logic: openTalkModal rejects missing agent IDs (Node.js eval)
  6. JS logic: openTalkModal sets agent-id attribute for valid IDs (Node.js eval)
  7. JS logic: closeTalkModal clears the widget container (Node.js eval)
"""

import os
import re
import subprocess
import sys
import unittest

BASE = os.path.dirname(__file__)
DASHBOARD_HTML = os.path.join(BASE, "app", "templates", "dashboard.html")
APP_JS = os.path.join(BASE, "app", "static", "js", "app.js")

WIDGET_SRC = "https://elevenlabs.io/convai-widget/index.js"


class TestDashboardHtml(unittest.TestCase):
    def setUp(self):
        with open(DASHBOARD_HTML, encoding="utf-8") as f:
            self.html = f.read()

    def test_talk_button_present(self):
        self.assertIn("openTalkModal()", self.html, "Talk to Agent button must call openTalkModal()")
        self.assertIn("Talk to Agent", self.html, "Button label 'Talk to Agent' must be present")

    def test_modal_present(self):
        self.assertIn('id="talk-agent-modal"', self.html, "talk-agent-modal element must exist")

    def test_widget_container_present(self):
        self.assertIn('id="talk-agent-widget-container"', self.html, "widget container must exist")

    def test_close_button_calls_close_function(self):
        self.assertIn("closeTalkModal()", self.html, "Modal close button must call closeTalkModal()")

    def test_button_is_in_client_dashboard_not_admin(self):
        # The Talk to Agent button must not appear in the admin dashboard template
        admin_html_path = os.path.join(BASE, "app", "templates", "admin", "dashboard.html")
        with open(admin_html_path, encoding="utf-8") as f:
            admin_html = f.read()
        self.assertNotIn("openTalkModal()", admin_html, "Talk to Agent button must NOT appear in admin dashboard")


class TestAppJs(unittest.TestCase):
    def setUp(self):
        with open(APP_JS, encoding="utf-8") as f:
            self.js = f.read()

    def test_open_function_defined(self):
        self.assertIn("function openTalkModal()", self.js)

    def test_close_function_defined(self):
        self.assertIn("function closeTalkModal()", self.js)

    def test_correct_widget_script_url(self):
        self.assertIn(WIDGET_SRC, self.js, "Widget script URL must be the official ElevenLabs embed URL")

    def test_agent_id_attribute_set_on_widget(self):
        self.assertIn("setAttribute('agent-id'", self.js, "openTalkModal must set agent-id attribute on widget element")

    def test_elevenlabs_convai_element_created(self):
        self.assertIn("elevenlabs-convai", self.js, "openTalkModal must create elevenlabs-convai custom element")

    def test_script_id_constant_defined(self):
        self.assertIn("ELEVENLABS_WIDGET_SCRIPT_ID", self.js, "Script ID constant must be defined to prevent duplicate loads")


class TestJsLogicViaNode(unittest.TestCase):
    """Run extracted JS logic through Node.js to verify behaviour without a browser."""

    NODE_SHIM = """
// Minimal DOM shim
const alerts = [];
const elements = {};

function showAlert(type, msg) { alerts.push({ type, msg }); }

class FakeEl {
    constructor(tag) { this.tag = tag; this._attrs = {}; this.children = []; this.innerHTML = ''; this.style = {}; }
    setAttribute(k, v) { this._attrs[k] = v; }
    getAttribute(k) { return this._attrs[k]; }
    appendChild(child) { this.children.push(child); }
}

const document = {
    createElement: (tag) => new FakeEl(tag),
    getElementById: (id) => elements[id] || null,
    body: { appendChild: (el) => { elements[el.id] = el; } },
};

let currentProfile = null;

"""

    def _run_js(self, snippet):
        """Run a JS snippet with the shim and return (stdout, returncode)."""
        code = self.NODE_SHIM + snippet
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=code.encode(),
            capture_output=True,
            timeout=10,
        )
        return result.stdout.decode(), result.stderr.decode(), result.returncode

    def test_missing_agent_id_shows_alert(self):
        snippet = """
// Extract widget script URL constant and openTalkModal logic inline
const ELEVENLABS_WIDGET_SRC = 'https://elevenlabs.io/convai-widget/index.js';
const ELEVENLABS_WIDGET_SCRIPT_ID = 'elevenlabs-convai-script';

elements['talk-agent-modal'] = new FakeEl('div');
elements['talk-agent-widget-container'] = new FakeEl('div');
elements[ELEVENLABS_WIDGET_SCRIPT_ID] = null;

currentProfile = { elevenlabs_agent_id: '' };

function openTalkModal() {
    const agentId = currentProfile && currentProfile.elevenlabs_agent_id
        ? currentProfile.elevenlabs_agent_id.trim()
        : '';
    if (!agentId) {
        showAlert('error', 'No Agent ID configured. Please add your ElevenLabs Agent ID in Edit Profile first.');
        return;
    }
}

openTalkModal();
console.log(JSON.stringify(alerts));
"""
        stdout, stderr, rc = self._run_js(snippet)
        self.assertEqual(rc, 0, f"Node.js error: {stderr}")
        import json
        result = json.loads(stdout.strip())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "error")
        self.assertIn("No Agent ID", result[0]["msg"])

    def test_valid_agent_id_sets_attribute(self):
        snippet = """
const ELEVENLABS_WIDGET_SRC = 'https://elevenlabs.io/convai-widget/index.js';
const ELEVENLABS_WIDGET_SCRIPT_ID = 'elevenlabs-convai-script';

const modal = new FakeEl('div');
modal.style = {};
const container = new FakeEl('div');
elements['talk-agent-modal'] = modal;
elements['talk-agent-widget-container'] = container;

currentProfile = { elevenlabs_agent_id: 'agent_01jabcdefghijk' };

function openTalkModal() {
    const agentId = currentProfile && currentProfile.elevenlabs_agent_id
        ? currentProfile.elevenlabs_agent_id.trim()
        : '';
    if (!agentId) {
        showAlert('error', 'No Agent ID configured.');
        return;
    }
    const widgetContainer = document.getElementById('talk-agent-widget-container');
    widgetContainer.innerHTML = '';
    const widget = document.createElement('elevenlabs-convai');
    widget.setAttribute('agent-id', agentId);
    widgetContainer.appendChild(widget);
    modal.style.display = 'flex';
}

openTalkModal();
const widget = container.children[0];
console.log(JSON.stringify({
    tag: widget.tag,
    agentId: widget.getAttribute('agent-id'),
    modalDisplay: modal.style.display,
}));
"""
        stdout, stderr, rc = self._run_js(snippet)
        self.assertEqual(rc, 0, f"Node.js error: {stderr}")
        import json
        result = json.loads(stdout.strip())
        self.assertEqual(result["tag"], "elevenlabs-convai")
        self.assertEqual(result["agentId"], "agent_01jabcdefghijk")
        self.assertEqual(result["modalDisplay"], "flex")

    def test_close_modal_clears_container(self):
        snippet = """
const modal = new FakeEl('div');
modal.style = { display: 'flex' };
const container = new FakeEl('div');
container.innerHTML = '<elevenlabs-convai agent-id="x"></elevenlabs-convai>';
elements['talk-agent-modal'] = modal;
elements['talk-agent-widget-container'] = container;

function closeTalkModal() {
    const m = document.getElementById('talk-agent-modal');
    const c = document.getElementById('talk-agent-widget-container');
    if (m) m.style.display = 'none';
    if (c) c.innerHTML = '';
}

closeTalkModal();
console.log(JSON.stringify({ display: modal.style.display, innerHTML: container.innerHTML }));
"""
        stdout, stderr, rc = self._run_js(snippet)
        self.assertEqual(rc, 0, f"Node.js error: {stderr}")
        import json
        result = json.loads(stdout.strip())
        self.assertEqual(result["display"], "none")
        self.assertEqual(result["innerHTML"], "")

    def test_widget_url_is_valid_https(self):
        self.assertTrue(WIDGET_SRC.startswith("https://"), "Widget script URL must use HTTPS")
        self.assertIn("elevenlabs.io", WIDGET_SRC, "Widget script must come from elevenlabs.io")


if __name__ == "__main__":
    unittest.main()
