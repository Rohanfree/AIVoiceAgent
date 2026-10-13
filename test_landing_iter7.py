"""test_landing_iter7.py — Iteration 7 landing moves.

Pins the five Iter7 items, all shipped as clearly-labelled, honest content
(no invented audio, no invented figures beyond a labelled example):

1. The truthful handoff strip in the demo section: a transfer counts only when
   a person answers, the call never drops when nobody does, and keypresses are
   captured. Reuses the Iter5 ``.lp-guard`` grammar via a modifier class.
2. The never-trains data-handling policy in the services block: never trained
   on, 30-day retention, optional zero-history. Attributed to the provider's
   published policy.
3. A measured per-call meter row inside the Iter5 post-call record, labelled an
   illustrative example. It sits outside the record ``<dl>`` so the four typed
   field rows Iter5 pins are untouched.
4. Role cards with a shared read-only onboarding ladder in the process section.
5. The recording recipe under the Iter4 clone stepper.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css``; the only
  new CSS is additive; no new ``<section>`` is added (which would shift the
  ``section:nth-child(even)`` background parity of every section below it); the
  new content reuses the shared observers (``.reveal`` entrance, scramble) under
  the existing motion gate.
* Honesty: every new block is labelled (modifier disclaimers), nothing
  references audio or media the page does not already ship, no em-dashes sneak
  into the new copy, and the Iter3/5 counts (five bare notes, one bare guard)
  hold because new components reuse the skins via modifier classes.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter7. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter7.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter7 must not change. Same set Iter2..6
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

# Iter3 shipped 13 <section> elements; Iter4/5/6/7 add none (background parity).
SECTION_COUNT = 13

# Every Iter7 block reuses the honest-note component through a modifier class.
ITER7_NOTE_MODIFIERS = (
    "lp-handoff-note",
    "lp-privacy-note",
    "lp-meter-note",
    "lp-role-note",
    "lp-recipe-note",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter7Hooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("app/templates/landing.html")
        cls.css = _read("app/static/css/landing.css")
        cls.js = _read("app/static/js/landing.js")

    def _slice(self, start_marker, end_marker):
        start = self.html.index(start_marker)
        return self.html[start:self.html.index(end_marker, start)]

    def test_landing_route_registered(self):
        paths = {getattr(r, "path", None) for r in pages_router.router.routes}
        self.assertIn("/pages/landing", paths)

    def test_flat_gate_still_present_in_head(self):
        self.assertIn("data-motion-flat", self.html)
        self.assertLess(self.html.index("data-motion-flat"), self.html.index("</head>"))

    def test_no_new_section_added(self):
        # A new <section> would shift section:nth-child(even) backgrounds for
        # every section below it; Iter7 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    def test_asset_cache_bust_still_versioned(self):
        self.assertRegex(self.html, r"landing\.css\?v=\d+")
        self.assertRegex(self.html, r"landing\.js\?v=\d+")

    def test_iter7_css_banner_and_green_lock(self):
        # The Iter7 block is additive, at the end of the file, and keeps the
        # single --green accent (no new accent colour).
        self.assertIn("Iteration 7 moves", self.css)
        block = self.css[self.css.index("Iteration 7 moves"):]
        self.assertIn("var(--green)", block)

    # ── Item 1: truthful handoff strip ─────────────────────────────────
    def test_move1_handoff_strip(self):
        for hook in ('class="lp-guard-block lp-handoff-block reveal"',
                     'class="lp-guard lp-handoff"', "When it hands you the call",
                     ">Hands over<", ">No answer<", ">Keypresses<",
                     "the person <b>answers</b>", "Never dead air",
                     "captured and logged", "post-call record"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-handoff-block {", self.css)
        self.assertIn(".lp-handoff-note {", self.css)
        block = self._slice('class="lp-guard lp-handoff"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # Lives in the demo section, before the voices block.
        self.assertLess(self.html.index('id="demo"'), self.html.index("lp-handoff-block"))
        self.assertLess(self.html.index("lp-handoff-block"), self.html.index('id="voices"'))

    def test_move1_handoff_is_labelled_behaviour(self):
        self.assertIn('class="lp-note lp-handoff-note"', self.html)
        self.assertIn("stated as behaviour", self.html)

    # ── Item 2: never-trains data-handling policy ──────────────────────
    def test_move2_privacy_policy(self):
        for hook in ('class="lp-guard-block lp-privacy-block reveal"',
                     'class="lp-guard lp-privacy"', "Your calls are not training data",
                     ">Training<", ">Retention<", ">History<",
                     "never used to train models", "30 days", "not persisted"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-privacy-block {", self.css)
        self.assertIn(".lp-privacy-note {", self.css)
        block = self._slice('class="lp-guard lp-privacy"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # It lives in the services block, ahead of the explainer.
        self.assertLess(self.html.index('id="services"'), self.html.index("lp-privacy-block"))
        self.assertLess(self.html.index("lp-privacy-block"), self.html.index('class="explainer-block'))

    def test_move2_attributed_and_not_overclaiming(self):
        self.assertIn('class="lp-note lp-privacy-note"', self.html)
        self.assertIn("published data policy", self.html)
        # Never implies zero-retention is automatic; the 30-day default is quoted.
        self.assertRegex(self.html, r"configured per\s+deployment")

    # ── Item 3: measured per-call meter row ────────────────────────────
    def test_move3_meter_row_in_record(self):
        for hook in ('class="lp-record-meter"', "<i>metered</i>",
                     'data-scramble-text="$0.40"', "per-request billing"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-record-meter {", self.css)
        self.assertIn(".lp-meter-note {", self.css)
        # It rides the shared scramble observer (no new observer), and the card
        # is unchanged in kind.
        record_start = self.html.index('class="lp-record"')
        self.assertGreater(self.html.index('class="lp-record-meter"'), record_start)
        self.assertIn("data-record", self.html)

    def test_move3_leaves_iter5_record_fields_untouched(self):
        # The Iter5 record <dl> still holds exactly four typed rows: the meter
        # row sits OUTSIDE the </dl> on purpose.
        record = self._slice('class="lp-record"', "</dl>")
        self.assertEqual(record.count("<dd"), 4)
        self.assertEqual(record.count('data-scramble-text="'), 4)
        self.assertGreater(self.html.index('class="lp-record-meter"'),
                           self.html.index("</dl>", self.html.index('class="lp-record"')))

    def test_move3_figure_is_labelled_example(self):
        self.assertIn('class="lp-note lp-meter-note"', self.html)
        self.assertIn("The figure shown is an example", self.html)

    # ── Item 4: role cards + read-only ladder ──────────────────────────
    def test_move4_role_cards(self):
        for hook in ('class="lp-roles reveal"', "One card per business",
                     'class="lp-role-grid"', 'class="lp-role-brief"',
                     'class="lp-ladder"', "read-only", "Start with:"):
            self.assertIn(hook, self.html)
        self.assertEqual(self.html.count('class="lp-record lp-role-card"'), 3)
        self.assertEqual(self.html.count('class="lp-role-brief"'), 3)
        for role in ("Dental receptionist", "Trades dispatcher", "Studio front desk"):
            self.assertIn(role, self.html)
        self.assertIn(".lp-role-grid {", self.css)
        self.assertIn(".lp-role-card {", self.css)
        self.assertIn(".lp-role-brief {", self.css)
        self.assertIn(".lp-ladder {", self.css)
        # Each card carries owns / connect / never.
        for kind in ("<dt>owns</dt>", "<dt>connect</dt>", "<dt>never</dt>"):
            self.assertEqual(self.html.count(kind), 3)

    def test_move4_read_only_ladder(self):
        block = self._slice('class="lp-ladder"', "</ol>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertIn('class="lp-note lp-role-note"', self.html)
        # Sits in the process section, ahead of the closing CTA.
        self.assertLess(self.html.index('id="partnership"'), self.html.index('class="lp-roles reveal"'))
        self.assertLess(self.html.index('class="lp-roles reveal"'), self.html.index('class="partnership-cta'))

    # ── Item 5: recording recipe ───────────────────────────────────────
    def test_move5_recording_recipe(self):
        for hook in ('class="lp-guard-block lp-recipe-block reveal"',
                     'class="lp-guard lp-recipe"', "How to record your clip",
                     ">Length<", ">Room<", ">Content<", ">Then<",
                     "90 to 120 seconds", "delivery", "the A/B above"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-recipe-block {", self.css)
        self.assertIn(".lp-recipe-note {", self.css)
        block = self._slice('class="lp-guard lp-recipe"', "</ul>")
        self.assertEqual(block.count("<li>"), 4)
        # Dropped directly under the Iter4 clone stepper, before the pron map.
        self.assertLess(self.html.index('class="lp-clone"'), self.html.index("lp-recipe-block"))
        self.assertLess(self.html.index("lp-recipe-block"), self.html.index('class="lp-pron"'))

    def test_move5_attributed_to_provider(self):
        self.assertIn('class="lp-note lp-recipe-note"', self.html)
        self.assertIn("recording guidance", self.html)

    # ── Honesty: labelled content, no invented audio, counters hold ────
    def test_new_copy_has_no_em_dashes(self):
        for marker in ("lp-handoff-block", "lp-privacy-block", "lp-record-meter",
                       'class="lp-roles reveal"', "lp-recipe-block"):
            block = self._slice(marker, "</aside>")
            self.assertNotIn("—", block)

    def test_all_new_blocks_are_labelled(self):
        for mod in ITER7_NOTE_MODIFIERS:
            with self.subTest(modifier=mod):
                self.assertIn(f'class="lp-note {mod}"', self.html)

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

    def test_iter3_and_iter5_counts_unchanged(self):
        # New disclaimers use modifier classes, so the bare counts hold.
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertEqual(self.html.count('class="lp-guard"'), 1)
        self.assertIn('class="lp-note-label"', self.html)

    def test_new_blocks_reuse_the_gated_reveal_entrance(self):
        # No new motion: the new blocks enter on the shared .reveal observer,
        # which flattens under the flat gate.
        self.assertIn("[data-motion-flat] .reveal", self.css)
        for cls in ("lp-handoff-block", "lp-privacy-block", "lp-recipe-block"):
            self.assertIn(f'{cls} reveal', self.html)
        self.assertIn("lp-roles reveal", self.html)


class TestIter7ProtectedSurfaces(unittest.TestCase):
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
