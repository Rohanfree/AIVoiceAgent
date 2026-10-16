"""test_landing_iter3.py — Iteration 3 landing moves.

Pins the four Iter3 items that shipped:

1. Language grid with a spoken-preview slot per chip (disabled-honest).
2. Inline speech-tag chips inside the copy (disabled-honest).
3. Decorative glyph ornaments in the hero H1 + manifesto band.
5. One designed honest-note callout consolidating every disclaimer.

Item 4 (scroll theme flip) is deliberately NOT implemented: the light theme is
locked and the dark flip needs commander sign-off. Nothing asserts it here.

Three properties are checked:

* Wiring: the moves are present in `landing.html` / `landing.css`, and the new
  motion (the glyphs) branches on the `data-motion-flat` gate. Moves 1, 2 and 5
  are static by design, so there is no motion to gate.
* Honesty: every audio affordance Iter3 adds is a disabled slot that references
  no audio file and never autoplays; no `speechSynthesis` / `<audio src>` is
  invented. The pre-Iter3 ad-hoc disclaimers are gone, replaced by `.lp-note`.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter3. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter3.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter3 must not change. Same set Iter2 froze;
# contact/login/register/dashboard only change on purpose.
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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter3Hooks(unittest.TestCase):
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

    # ── Item 1: language grid (disabled-honest preview slots) ──────────
    def test_move1_language_grid(self):
        for hook in ('class="lp-lang"', 'class="lp-lang-grid"', "lp-lang-chip",
                     "lp-lang-auto", 'data-preview="auto"', 'lang="en"',
                     "Auto-detect", 'class="lp-lang-code"'):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-lang-grid", self.css)
        self.assertIn(".lp-lang-chip", self.css)
        self.assertIn(".lp-lang-auto", self.css)
        # Every chip is a disabled honest slot.
        chips = re.findall(r"<button[^>]*lp-lang-chip[^>]*>", self.html)
        self.assertEqual(len(chips), 11)
        for chip in chips:
            self.assertIn("disabled", chip)
            self.assertIn('aria-disabled="true"', chip)
        # The grid lives in the Voices section (second dimension, same roster).
        self.assertLess(self.html.index("lp-lang"), self.html.index('id="why"'))

    def test_move1_no_invented_spoken_preview(self):
        # No speech API, no audio element: the slots are inert, not faked.
        self.assertNotIn("speechSynthesis", self.html)
        self.assertNotIn("speechSynthesis", self.js)

    # ── Item 2: inline speech-tag chips (disabled slots) ───────────────
    def test_move2_inline_speech_tag_chips(self):
        for hook in ('class="lp-say"', 'class="lp-tag"', "[pause]",
                     "[caller cuts in]", "[handoff]", "lp-note-label"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-tag", self.css)
        self.assertIn(".lp-say", self.css)
        tags = re.findall(r"<button[^>]*lp-tag[^>]*>", self.html)
        self.assertEqual(len(tags), 3)
        for tag in tags:
            self.assertIn("disabled", tag)
            self.assertIn('aria-disabled="true"', tag)
        # Chips land in body copy, inside the demo section.
        self.assertLess(self.html.index('class="lp-say"'), self.html.index('id="voices"'))

    # ── Item 3: decorative glyph ornaments (motion-gated) ──────────────
    def test_move3_glyph_ornaments(self):
        self.assertIn('class="lp-glyph"', self.html)
        self.assertIn("lp-glyph-tail", self.html)
        self.assertIn('aria-hidden="true">✦', self.html)
        self.assertIn(".lp-glyph", self.css)
        self.assertIn("--green", self.css)
        # Rides the existing observers, no new IO added for the glyphs.
        self.assertIn(".lp-split.lp-in .lp-glyph", self.css)
        self.assertIn('class="lp-w lp-glyph"', self.html)
        # Gated: flattened under flat gate + reduced motion.
        self.assertIn("[data-motion-flat] .lp-glyph", self.css)
        self.assertIn(
            "@media (prefers-reduced-motion: reduce) {\n  .lp-glyph { transform: none; transition: none; }\n}",
            self.css)

    def test_move3_glyph_not_inside_scramble_text(self):
        # Ornament and scramble must never fight over the same node.
        for el in re.findall(r'<[^>]*data-scramble-text="[^"]*"[^>]*>', self.html):
            self.assertNotIn("lp-glyph", el)

    def test_move3_max_one_glyph_per_hero_line(self):
        h1 = self.html[self.html.index('id="hero-heading"'):
                       self.html.index("</h1>", self.html.index('id="hero-heading"'))]
        for line in re.findall(r'<span class="lp-line-in">(.*?)</span></span>', h1, re.S):
            self.assertLessEqual(line.count('class="lp-glyph'), 1)

    # ── Item 5: consolidated honest-note callout ───────────────────────
    def test_move5_honest_note_consolidates_disclaimers(self):
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertIn('class="lp-note-label"', self.html)
        self.assertIn('data-note="note"', self.html)
        self.assertIn('role="note"', self.html)
        # The five ad-hoc treatments are gone.
        for gone in ("lp-sample-note", "lp-voice-note", "lp-index-sample"):
            self.assertNotIn(gone, self.html)
            self.assertNotIn(gone, self.css)
        # Component CSS: two variants, mono label, static (no motion to gate).
        self.assertIn(".lp-note {", self.css)
        self.assertIn('.lp-note[data-note="warn"]', self.css)
        self.assertIn(".lp-note-label", self.css)

    def test_audio_demos_are_real_two_voice_assets(self):
        # Four generated samples are intentionally shipped and referenced by
        # the four editorial chapters in the lightbox.
        self.assertNotIn("data-src=", self.html)
        self.assertNotIn("new Audio(", self.js)
        self.assertEqual(self.html.count("<audio"), 4)
        self.assertEqual(self.html.count("demo-call-"), 4)
        self.assertEqual(self.html.count('class="lp-lightbox-audio"'), 4)
        self.assertIn("demo-call-plumbing-intake-two-voices-v3.mp3", self.html)
        self.assertIn("demo-call-appointment-booking-two-voices-v3.mp3", self.html)
        self.assertIn("demo-call-missed-call-callback-two-voices-v3.mp3", self.html)
        self.assertIn("demo-call-service-qualification-two-voices-v3.mp3", self.html)


class TestIter3ProtectedSurfaces(unittest.TestCase):
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
