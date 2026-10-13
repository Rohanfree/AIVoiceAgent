"""test_landing_iter2.py — Iteration 2 landing moves.

Two things are pinned here:

1. Wiring: the five Iter2 moves are present in `landing.html` / `landing.css` /
   `landing.js`, and every motion move branches on the `data-motion-flat` gate.
2. Byte-identity: the contact / login / register / dashboard surfaces are not
   touched by Iter2. Their template digests (and the landing contact-section
   slice) must match the frozen values below; update them deliberately if one
   of those surfaces is ever meant to change.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route (login included), independent of Iter2.

The landing page's figures/assets stay visibly SAMPLE placeholders and the
transcript slot stays disabled-honest, so nothing here asserts invented data.
"""

import hashlib
import os
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter2 must not change. Captured at the Iter2
# branch tip; contact/login/register/dashboard only change on purpose.
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


class TestLandingIter2Hooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("app/templates/landing.html")
        cls.css = _read("app/static/css/landing.css")
        cls.js = _read("app/static/js/landing.js")

    def test_landing_route_registered(self):
        paths = {getattr(r, "path", None) for r in pages_router.router.routes}
        self.assertIn("/pages/landing", paths)

    def test_flat_gate_present_in_head(self):
        self.assertIn("data-motion-flat", self.html)
        self.assertIn("(prefers-reduced-motion: reduce)", self.html)
        # Guard runs before paint, inside <head>.
        self.assertLess(self.html.index("data-motion-flat"), self.html.index("</head>"))

    def test_move1_custom_cursor(self):
        for hook in ('class="lp-cursor"', "lp-cursor-dot", 'class="lp-cursor-label"',
                     "data-cursor-text", 'data-cursor="Book"', 'data-cursor="Play call"',
                     'data-cursor="Drag"'):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-cursor-label.on span", self.css)
        # Gated: hidden under flat, and the JS bails out before wiring it up.
        self.assertIn("[data-motion-flat] .lp-cursor", self.css)
        self.assertIn("if (motionFlat || reduceMotion", self.js)

    def test_move2_sound_toggle(self):
        for hook in ("data-sound-toggle", "data-sound-wave", "data-sound-cross",
                     'aria-pressed="false"'):
            self.assertIn(hook, self.html)
        # Two-state crossfade driven purely by aria-pressed.
        self.assertIn("[data-sound-toggle]", self.js)
        self.assertIn('.lp-sound[aria-pressed="true"] [data-sound-wave]', self.css)
        self.assertIn("[data-motion-flat] .lp-sound", self.css)

    def test_move3_arc_mask_lens(self):
        self.assertIn('id="lp-lens"', self.html)
        self.assertIn('class="lp-lens"', self.html)
        self.assertIn("--mask-arc", self.css)
        self.assertIn("--mask-arc", self.js)
        self.assertIn("[data-motion-flat] .lp-lens", self.css)
        # Both the loader exit and the lightbox ride the same scalar.
        self.assertIn("lpArc(", self.js)

    def test_move4_karaoke_transcript_disabled_honest(self):
        self.assertIn("data-transcript", self.html)
        self.assertIn('aria-disabled="true"', self.html)
        self.assertIn("not synced to audio", self.html)
        self.assertIn("lp-transcript-note", self.html)
        # The highlighter exists but is dormant: no timing map is invented.
        self.assertIn("timeupdate", self.js)
        self.assertIn("const lpTimes = null", self.js)
        self.assertIn(".lp-t-on", self.css)
        # No fake per-word timing claims rendered server-side.
        self.assertNotIn("lp-t-on", self.html)

    def test_move5_scramble_on_reveal(self):
        self.assertIn('data-scramble-text="', self.html)
        self.assertIn("data-scramble-text", self.js)
        self.assertIn("IntersectionObserver", self.js)
        # Ledger numerals keep tabular figures so widths never jitter.
        self.assertIn("font-variant-numeric: tabular-nums", self.css)
        self.assertIn(".lp-ledger-num,", self.css)

    def test_contact_section_label_is_not_scrambled(self):
        # Deliberate: the contact block stays byte-identical, so its label is
        # the one section-label left without a scramble hook.
        self.assertIn('<p class="section-label">Get In Touch</p>', self.html)


class TestIter2ProtectedSurfaces(unittest.TestCase):
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
