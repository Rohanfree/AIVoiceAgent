"""test_landing_iter4.py — Iteration 4 landing moves.

Pins the four Iter4 items that shipped:

1. Diarized two-speaker transcript in the demo lightbox (illustrative static).
2. Scripted "Smart Turn" confidence meter — an honest, labelled visual demo.
3. Client-side raw / clean transcript toggle (two inlined strings, no audio).
5. Custom-voice capture stepper whose A/B control is a disabled-honest slot.

Item 4 (the sticky dark showreel curtain) is deliberately NOT implemented: it
is a dark surface and the dark treatment is held pending a Commander brand
decision. NOTHING dark ships in Iter4 and no ``<section>`` is added (which
would shift the ``section:nth-child(even)`` background parity of every section
below it). Nothing here asserts it; instead the absence is pinned.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css`` /
  ``landing.js``, the smart-turn demo branches on ``data-motion-flat``, and the
  raw/clean swap reuses the shared scramble routine.
* Honesty: every audio affordance Iter4 adds is an inert, clearly-labelled
  slot. No audio element is added (the lightbox keeps its one empty slot), no
  ``new Audio(`` / ``speechSynthesis`` / ``<audio src>`` is invented, and the
  five-strong Iter3 honest-note callout is neither added to nor removed.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter4. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter4.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter4 must not change. Same set Iter2/Iter3
# froze; contact/login/register/dashboard only change on purpose.
PROTECTED_FILES = {
    "app/templates/login.html": "5d524d8f9c8b03b9ea90afc0bf587b8bbf8a74b81d348c4ef8a1f8e0623a71c7",
    "app/templates/register.html": "5f54264ae25c90baef6101a6494a1d5557e13910d8b52c8e663569180a443778",
    "app/templates/dashboard.html": "d9a62ea2d616ae6b10c1e548d52a174fd69b3e5111e0ddb59e26151f4442fafa",
    "app/templates/admin/dashboard.html": "c2b1c558490d1a66e3c4c21b5d5a2999061c94f238d4e6ea9aedd96a1ef32a47",
    "app/templates/admin/login.html": "9495e85b7cb71ddfdee487233c63846ce3dc512a4d5b23753af8ae4da712a0d7",
    "app/routers/contact_router.py": "8ac11928b49242d319be3249fea13a26fbb8cb5ca47dcac433092c2b3cbf8870",
}

CONTACT_SECTION_SHA256 = "7da6f81a80d86919b5fcf59197a44b352c8e9933d825534af0cf24a84de338b5"

CONTACT_START = '<section id="contact" aria-labelledby="contact-heading">'
CONTACT_END = "</main>"

# Iter3 shipped 13 <section> elements; Iter4 adds none (background parity).
SECTION_COUNT = 13


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter4Hooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("app/templates/landing.html")
        cls.css = _read("app/static/css/landing.css")
        cls.js = _read("app/static/js/landing.js")

    def test_landing_route_registered(self):
        paths = {getattr(r, "path", None) for r in pages_router.router.routes}
        self.assertIn("/pages/landing", paths)

    def test_flat_gate_still_present_in_head(self):
        self.assertIn("data-motion-flat", self.html)
        self.assertLess(self.html.index("data-motion-flat"), self.html.index("</head>"))

    def test_no_new_section_added(self):
        # A new <section> would shift section:nth-child(even) backgrounds for
        # every section below it; Iter4 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    # ── Item 1: diarized two-speaker transcript (lightbox) ─────────────
    def test_move1_diarized_two_speaker_transcript(self):
        for hook in ('class="lp-call"', "data-call", 'class="lp-call-list"',
                     "lp-call-line", 'data-sp="0"', 'data-sp="1"',
                     "two speakers", "not a real call"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-call", self.css)
        self.assertIn(".lp-call-line", self.css)
        self.assertIn('.lp-call-line[data-sp="1"]', self.css)
        self.assertIn("[data-motion-flat] .lp-call-line", self.css)
        # The transcript lives inside the lightbox, after the karaoke slot.
        self.assertLess(self.html.index('id="demo-lightbox-slot"'),
                        self.html.index('class="lp-call"'))
        self.assertLess(self.html.index("data-transcript"), self.html.index("data-call"))

    def test_move1_speakers_alternate_in_timestamp_order(self):
        # Caller and agent as separate columns, in call order: 0,1,0,1.
        sp = re.findall(r'<li class="lp-call-line"[^>]*data-sp="(\d)"', self.html)
        self.assertEqual(sp, ["0", "1", "0", "1"])
        # Disabled-honest: static illustrative text, never a live highlight.
        self.assertIn('<div class="lp-call" data-call aria-disabled="true">', self.html)

    # ── Item 2: scripted Smart Turn confidence meter ───────────────────
    def test_move2_smart_turn_confidence_meter(self):
        for hook in ('class="lp-turn"', "data-turn", "data-turn-play",
                     'class="lp-conf-bar"', 'class="lp-conf-val"', "data-reply",
                     "lp-turn-reply on", "End-of-turn confidence",
                     "Scripted demo", "not a live API call"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-turn", self.css)
        self.assertIn(".lp-conf-bar b", self.css)
        self.assertIn("[data-motion-flat] .lp-turn-reply", self.css)
        # Pre-authored samples replayed on click by one rAF timeline.
        self.assertIn("const KEYS =", self.js)
        self.assertIn("requestAnimationFrame", self.js)
        # The reply gate IS the demo: it only trips above the 0.9 threshold.
        self.assertIn("c > 0.9", self.js)

    def test_move2_demo_never_autoplays_and_has_no_audio(self):
        block = self.html[self.html.index('class="lp-turn"'):self.html.index('class="lp-raw"')]
        self.assertNotIn("autoplay", block)
        self.assertNotIn("<audio", block)
        self.assertIn("<button type=\"button\" class=\"lp-turn-play\" data-turn-play>", block)

    # ── Item 3: raw / clean transcript toggle ──────────────────────────
    def test_move3_raw_clean_toggle(self):
        for hook in ('class="lp-raw"', "data-raw", 'class="lp-raw-toggle"',
                     'aria-pressed="false"', 'data-raw-line="clean"',
                     'data-raw-line="raw"', "Raw capture", "What we store",
                     "$167,983.15", "one hundred", "dollars and fifteen cents"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-raw", self.css)
        self.assertIn(".lp-raw-toggle", self.css)
        # Both strings stay in the DOM; the raw capture is hidden by default.
        self.assertIn('data-raw-line="raw" hidden', self.html)

    def test_move3_is_client_side_and_reuses_scramble(self):
        self.assertIn("lpScramble", self.js)
        self.assertIn('[data-raw-line]', self.js)
        # The swap is instant under the flat gate (shared routine early-returns).
        self.assertIn(
            "if (reduceMotion || !('requestAnimationFrame' in window)) { el.textContent = final; return; }",
            self.js)

    # ── Item 5: custom-voice A/B stepper (disabled-honest) ─────────────
    def test_move5_custom_voice_ab_stepper(self):
        for hook in ('class="lp-clone"', "<i>01</i>", "<i>02</i>", "<i>03</i>",
                     'class="lp-ab"', "data-ab", "Sample coming",
                     "Your recording", "The agent"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-clone", self.css)
        self.assertIn(".lp-ab", self.css)

    def test_move5_ab_buttons_are_disabled_honest_slots(self):
        start = self.html.index('class="lp-ab"')
        block = self.html[start:self.html.index("</span>", start)]
        self.assertEqual(block.count("<button"), 2)
        self.assertEqual(block.count(" disabled"), 2)
        self.assertEqual(block.count('aria-disabled="true"'), 2)
        # The stepper sits in the Voices section, before the Why block.
        self.assertLess(self.html.index('class="lp-clone"'), self.html.index('id="why"'))

    # ── Item 4 deliberately held: no dark curtain, nothing dark ────────
    def test_item4_dark_curtain_deliberately_absent(self):
        for gone in ("lp-curtain", "lp-curtain-sec", "lp-curtain-under", "--night"):
            self.assertNotIn(gone, self.html)
            self.assertNotIn(gone, self.css)
        self.assertNotIn("lp-curtain", self.js)

    # Honesty: four generated voice demos are labeled and coordinated.
    def test_audio_demos_are_labeled_and_coordinated(self):
        self.assertNotIn("data-src=", self.html)
        self.assertNotIn("new Audio(", self.js)
        self.assertNotIn("speechSynthesis", self.html)
        self.assertNotIn("speechSynthesis", self.js)
        self.assertEqual(self.html.count("<audio"), 4)
        self.assertIn("lp-call-library", self.html)
        self.assertIn("lp-call-demo", self.html)
        self.assertIn("lpSpeechActive", self.js)
        self.assertIn("other.pause()", self.js)
        # The dormant illustrative timing slot remains free of fake highlights.
        self.assertNotIn("lp-t-on", self.html)

    def test_iter3_honest_note_count_unchanged(self):
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertIn('class="lp-note-label"', self.html)


class TestIter4ProtectedSurfaces(unittest.TestCase):
    def test_protected_files_byte_identical(self):
        for rel, digest in PROTECTED_FILES.items():
            with self.subTest(path=rel):
                self.assertEqual(_sha256(_read(rel)), digest, f"{rel} changed")

    def test_landing_contact_section_byte_identical(self):
        html = _read("app/templates/landing.html")
        start = html.index(CONTACT_START)
        end = html.index(CONTACT_END, start)
        self.assertEqual(_sha256(html[start:end]), CONTACT_SECTION_SHA256)


if __name__ == "__main__":
    unittest.main()
