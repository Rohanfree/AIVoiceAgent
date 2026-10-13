"""test_landing_iter5.py — Iteration 5 landing moves.

Pins the five Iter5 items that shipped:

1. Inline media chips inside the manifesto display sentence, reusing media the
   page already owns (the chips add no new asset).
2. The ``force_message`` disclosure as a locked, verbatim first transcript line.
3. The read-vs-write tool boundary strip in the services block.
4. A pronunciation replace map that reuses the Iter4 raw/clean swap.
5. The post-call record card in the deployments section.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css`` /
  ``landing.js``, the only new motion (the media chips) branches on
  ``data-motion-flat``, and the pronunciation map reuses the shared scramble
  routine.
* Honesty: nothing references media the page does not already ship, no audio
  element / ``new Audio(`` / ``speechSynthesis`` is invented, the Iter3 note
  count holds (new disclaimers reuse the component via a modifier class), and
  no ``<section>`` is added (which would shift the ``section:nth-child(even)``
  background parity of every section below it).
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter5. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter5.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter5 must not change. Same set Iter2/3/4
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

# Iter3 shipped 13 <section> elements; Iter4 and Iter5 add none (parity).
SECTION_COUNT = 13

# Media the Iter5 chips reference. Every one must already exist on disk: the
# chips reuse the page's own assets and ship nothing new.
CHIP_MEDIA = (
    "manifesto-accent.png",
    "demo-poster.png",
    "demo-wave-loop.mp4",
    "manifesto-drift-loop.mp4",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter5Hooks(unittest.TestCase):
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
        # every section below it; Iter5 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    # ── Item 1: inline media chips in the manifesto sentence ───────────
    def test_move1_inline_media_chips(self):
        for hook in ('class="lp-chip"', "data-chip=", "lp-chip-poster", "lp-chip-video"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-chip", self.css)
        self.assertIn(".lp-chip.in", self.css)
        self.assertIn(".lp-chip-poster, .lp-chip-video", self.css)
        # The chips sit inside the manifesto display sentence.
        man = self.html[self.html.index('class="lp-manifesto-text"'):self.html.index("</p>", self.html.index('class="lp-manifesto-text"'))]
        self.assertGreaterEqual(man.count('class="lp-chip"'), 2)
        # Multiple distinct scroll thresholds, one per chip (auge's p0-N idea).
        thresholds = re.findall(r'class="lp-chip" data-chip="([\d.]+)"', self.html)
        self.assertGreaterEqual(len(thresholds), 2)
        self.assertEqual(len(set(thresholds)), len(thresholds))

    def test_move1_chips_are_decorative_and_never_autoplay(self):
        chips = re.findall(r"<span class=\"lp-chip\".*?</span>", self.html, re.S)
        self.assertGreaterEqual(len(chips), 2)
        for chip in chips:
            self.assertIn('aria-hidden="true"', chip)
            self.assertNotIn("autoplay", chip)
            self.assertIn('preload="none"', chip)
            # The sentence reads identically: no text content inside a chip.
            self.assertEqual(re.sub(r"<[^>]+>", "", chip).strip(), "")

    def test_move1_chips_reuse_existing_media_only(self):
        for name in CHIP_MEDIA:
            self.assertIn(name, self.html)
            self.assertTrue(
                os.path.exists(os.path.join(ROOT, "app/static/media", name)),
                f"chip references missing media: {name}")

    def test_move1_chip_motion_is_gated(self):
        self.assertIn("[data-motion-flat] .lp-chip", self.css)
        self.assertIn("[data-motion-flat] .lp-chip-video", self.css)
        self.assertIn(".lp-chip", self.js)
        self.assertIn("IntersectionObserver", self.js)
        self.assertIn("data-chip", self.js)

    # ── Item 2: force_message disclosure line ──────────────────────────
    def test_move2_locked_verbatim_disclosure(self):
        for hook in ('class="lp-lock-line"', "data-locked", 'class="lp-lock"',
                     "This call is being recorded", "verbatim",
                     "not a generated one"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-lock-line", self.css)
        self.assertIn(".lp-lock", self.css)
        self.assertIn("border-left: 2px solid var(--green)", self.css)
        # It is the first (--t:0) utterance, ahead of the diarized lines.
        self.assertIn('class="lp-lock-line" data-sp="1" data-locked style="--t:0"', self.html)
        self.assertLess(self.html.index('class="lp-lock-line"'),
                        self.html.index('class="lp-call-line"'))

    def test_move2_rule_note_reuses_component_without_changing_count(self):
        # The rule is stated in the shared honest-note component via a modifier
        # class, so the Iter3 count of exactly five unmodified notes holds.
        self.assertIn('class="lp-note lp-lock-note"', self.html)
        self.assertIn("fixed line", self.html)
        self.assertEqual(self.html.count('class="lp-note"'), 5)

    def test_move2_locked_line_is_distinct_from_diarized_lines(self):
        # The locked line must not be counted as one of the four diarized
        # alternating lines that test_landing_iter4 pins.
        sp = re.findall(r'<li class="lp-call-line"[^>]*data-sp="(\d)"', self.html)
        self.assertEqual(sp, ["0", "1", "0", "1"])

    # ── Item 3: read-vs-write tool boundary ────────────────────────────
    def test_move3_read_vs_write_boundary(self):
        for hook in ('class="lp-guard"', "lp-guard-kind", ">Reads<", ">Writes<",
                     "Always confirms first", "no asking"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-guard {", self.css)
        self.assertIn(".lp-guard-kind", self.css)
        # Two rows, no buttons: pure copy, static by design.
        guard = self.html[self.html.index('class="lp-guard"'):
                          self.html.index("</ul>", self.html.index('class="lp-guard"'))]
        self.assertEqual(guard.count('<li>'), 2)
        self.assertEqual(guard.count("<button"), 0)
        # It lives in the Services block, ahead of the explainer.
        self.assertLess(self.html.index('class="lp-guard"'), self.html.index('class="explainer-block'))

    # ── Item 4: pronunciation replace map ──────────────────────────────
    def test_move4_pronunciation_replace_map(self):
        for hook in ('class="lp-pron"', "data-pron", 'class="lp-pron-toggle"',
                     'aria-pressed="false"', 'data-pron-line="fixed"',
                     'data-pron-line="raw"', "Acme Mobull", "Ack-mee Mob-you-el",
                     "Example configuration", "not a recording"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-pron", self.css)
        self.assertIn(".lp-pron-toggle", self.css)
        # The unmatched wording is hidden by default.
        self.assertIn('data-pron-line="raw" hidden', self.html)

    def test_move4_reuses_scramble_and_is_client_side(self):
        self.assertIn("[data-pron]", self.js)
        self.assertIn("[data-pron-line]", self.js)
        self.assertIn("lpScramble", self.js)
        # The swap is instant under the flat gate (shared routine early-returns).
        self.assertIn(
            "if (reduceMotion || !('requestAnimationFrame' in window)) { el.textContent = final; return; }",
            self.js)
        # It sits in the Voices section, before the Why block.
        self.assertLess(self.html.index('class="lp-pron"'), self.html.index('id="why"'))

    # ── Item 5: post-call record ───────────────────────────────────────
    def test_move5_post_call_record(self):
        for hook in ('class="lp-record"', "data-record", 'class="lp-record-head"',
                     "example record", "<dt>caller</dt>", "<dt>intent</dt>",
                     "<dt>slot</dt>", "<dt>crm</dt>"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-record {", self.css)
        self.assertIn(".lp-record dl", self.css)
        self.assertIn(".lp-record dt", self.css)

    def test_move5_record_rides_existing_observer(self):
        # Each value reuses the Iter2 scramble-on-reveal hook, so no new
        # observer is added for the record.
        record = self.html[self.html.index('class="lp-record"'):
                           self.html.index("</dl>", self.html.index('class="lp-record"'))]
        self.assertEqual(record.count('data-scramble-text="'), 4)
        self.assertEqual(record.count("<dd"), 4)
        # Lives in the deployments section and is labelled an example.
        self.assertLess(self.html.index('id="deployments"'), self.html.index('class="lp-record"'))
        self.assertLess(self.html.index('class="lp-record"'), self.html.index('id="demo"'))
        self.assertIn('class="lp-note lp-record-note"', self.html)
        self.assertIn("not a real customer", self.html)

    # ── Honesty: no invented audio, the Iter3 note count holds ─────────
    def test_no_new_audio_anything(self):
        self.assertNotIn("data-src=", self.html)
        self.assertNotIn("new Audio(", self.js)
        self.assertNotIn(".mp3", self.html)
        self.assertNotIn("speechSynthesis", self.html)
        self.assertNotIn("speechSynthesis", self.js)
        # The only audio element is still the pre-existing empty lightbox slot.
        self.assertEqual(self.html.count("<audio"), 1)
        self.assertIn('<audio class="lp-lightbox-audio" controls preload="none"', self.html)
        # The Iter2 karaoke slot stays dormant: no fake per-word timing in HTML.
        self.assertNotIn("lp-t-on", self.html)

    def test_iter3_honest_note_count_unchanged(self):
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertIn('class="lp-note-label"', self.html)


class TestIter5ProtectedSurfaces(unittest.TestCase):
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
