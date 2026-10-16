"""test_landing_iter9.py — Iteration 9 landing moves.

Pins the five Iter9 items, all shipped as clearly-labelled, honest content over
skins the page already ships (no invented audio, no invented figures, no new
JS beyond nothing at all):

1. Barge-in: the mirror of Iter4's Smart Turn meter. The agent stops mid
   sentence the moment the caller talks back, shown as a static scripted
   transcript (the unstruck part is what was said, the struck part never was)
   plus two guard rows and the single exception, the recording disclosure.
2. Prepaid credits + a monthly ceiling: the provider's own spend-control
   mechanics (a cap you set, an 80% warning, automatic rejection at zero) in
   three guard rows under the unit-economics card.
3. Click-a-word seeking: a static, aria-disabled preview of a published
   recording's seek transcript, with a disabled speed pill. No timing
   attribute, no audio, nothing faked.
4. Injection defense: three policy rows stating that caller words are data to
   answer, the rules live in the written brief, and every write still stops at
   the confirmation question (the Iter8 approval card, beside it).
5. Pinned web lookups: where web search is switched on at all it is contained
   to an allowed-domains list of up to five, cited like any source, otherwise
   it says it does not know.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css``; the only
  new CSS is additive; no new ``<section>`` is added (which would shift the
  ``section:nth-child(even)`` background parity of every section below it); the
  new content reuses the shared observers and the ``.reveal`` entrance under
  the existing motion gate.
* Honesty: every new block is labelled (modifier disclaimers), nothing
  references audio or media the page does not already ship, no em-dashes sneak
  into the new copy, and the Iter3/5/6/7/8 counts (five bare notes, one bare
  guard, two stamps, one bare record, one audio slot, four bare transcript
  lines) hold because new components reuse the skins via modifier classes.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter9. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter9.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter9 must not change. Same set Iter2..8
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

# Iter3 shipped 13 <section> elements; Iter4..9 add none (background parity).
SECTION_COUNT = 13

# Every Iter9 block reuses the honest-note component through a modifier class.
ITER9_NOTE_MODIFIERS = (
    "lp-bargein-note",
    "lp-ceiling-note",
    "lp-seek-note",
    "lp-inject-note",
    "lp-pinned-note",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter9Hooks(unittest.TestCase):
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
        # every section below it; Iter9 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    def test_asset_cache_bust_still_versioned(self):
        self.assertRegex(self.html, r"landing\.css\?v=\d+")
        self.assertRegex(self.html, r"landing\.js\?v=\d+")

    def test_iter9_css_banner_and_green_lock(self):
        # The Iter9 block is additive, at the end of the file, and keeps the
        # single --green accent (no new accent colour).
        self.assertIn("Iteration 9 moves", self.css)
        block = self.css[self.css.index("Iteration 9 moves"):]
        self.assertIn("var(--green)", block)
        self.assertNotIn("--green:", block)

    # ── Item 1: barge-in in the transcript ─────────────────────────────
    def test_move1_barge_in_demo(self):
        for hook in ("It stops the moment you talk back",
                     'class="lp-guard lp-bargein"', ">Interruptible<", ">Except one<",
                     'class="lp-cut"', "lp-jumped", "cut in",
                     "Our next opening is Thursday at ten"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-cut s {", self.css)
        self.assertIn(".lp-jumped {", self.css)
        self.assertIn(".lp-bargein {", self.css)
        # Two rows, no buttons: pure copy, static by design.
        block = self._slice('class="lp-guard lp-bargein"', "</ul>")
        self.assertEqual(block.count("<li>"), 2)
        self.assertEqual(block.count("<button"), 0)
        # The struck tail and the cut-in badge are both static markup.
        self.assertIn("<s>", self.html)
        self.assertIn('class="lp-moment reveal" data-bargein', self.html)
        # It lives in the demo section, before the voices block.
        self.assertLess(self.html.index('id="demo"'),
                        self.html.index("It stops the moment you talk back"))
        self.assertLess(self.html.index("It stops the moment you talk back"),
                        self.html.index('id="voices"'))

    def test_move1_is_labelled_and_does_not_fake_the_cut(self):
        self.assertIn('class="lp-note lp-bargein-note"', self.html)
        self.assertIn("the cut is the strikethrough, not a recording", self.html)
        # The cut is not an animation: nothing new to gate but the CSS transition.
        self.assertIn("[data-motion-flat] .lp-cut s", self.css)
        # No audio, no timer, no new JS for the barge-in block.
        block = self._slice("data-bargein", "</section>")
        self.assertNotIn("<audio", block)
        self.assertNotIn("autoplay", block)

    # ── Item 2: prepaid credits + monthly ceiling ──────────────────────
    def test_move2_prepaid_credits_and_ceiling(self):
        for hook in ("It cannot run up a bill you did not approve",
                     'class="lp-guard lp-ceiling"', ">Ceiling<", ">Warned<",
                     ">Capped out<", "<b>monthly cap</b>", "<b>80%</b>",
                     "prepaid", "No overdraft"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-ceiling-block {", self.css)
        self.assertIn(".lp-ceiling-note {", self.css)
        block = self._slice('class="lp-guard lp-ceiling"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # It lives in the calculator section, after the unit-economics card.
        self.assertLess(self.html.index('id="calculator"'),
                        self.html.index("lp-ceiling-block"))
        self.assertLess(self.html.index("lp-ceiling-block"),
                        self.html.index('id="partnership"'))
        self.assertLess(self.html.index('class="lp-record lp-cost"'),
                        self.html.index("lp-ceiling-block"))

    def test_move2_states_the_capped_out_tie_to_overflow(self):
        self.assertIn('class="lp-note lp-ceiling-note"', self.html)
        self.assertIn("as the overflow rule promises", self.html)
        self.assertIn("automatic\n            rejection at zero", self.html)

    # ── Item 3: click-a-word seeking + speed pill (disabled static) ────
    def test_move3_word_seek_static_demo(self):
        for hook in ("Jump straight to the part you doubt", 'class="lp-seek reveal"',
                     "data-seek", "lp-seek-word", "lp-seek-speed",
                     "not clickable yet", "1\u00d7"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-seek {", self.css)
        self.assertIn(".lp-seek-word {", self.css)
        self.assertIn(".lp-seek-speed {", self.css)
        # The strip is honest disabled: aria-disabled and no timing attribute.
        self.assertIn('class="lp-seek-strip" aria-disabled="true"', self.html)
        self.assertIn('class="lp-seek-speed" disabled aria-disabled="true"', self.html)
        self.assertNotIn("data-t=", self.html)
        # It lives in the demo section, before the voices block.
        self.assertLess(self.html.index('id="demo"'),
                        self.html.index("Jump straight to the part you doubt"))
        self.assertLess(self.html.index("Jump straight to the part you doubt"),
                        self.html.index('id="voices"'))

    def test_move3_speed_pill_is_a_disabled_slot(self):
        block = self._slice('class="lp-seek-strip"', "</div>")
        self.assertEqual(block.count("<button"), 1)
        self.assertEqual(block.count(" disabled"), 1)
        self.assertEqual(block.count('aria-disabled="true"'), 2)  # strip + pill
        self.assertIn('class="lp-note lp-seek-note"', self.html)
        # Nothing plays: no audio in the block and no seek wiring in the JS.
        self.assertNotIn("<audio", block)
        self.assertNotIn("data-seek", self.js)
        self.assertNotIn("playbackRate", self.js)

    # ── Item 4: injection-defense policy rows ──────────────────────────
    def test_move4_injection_defense_rows(self):
        for hook in ("You cannot talk it into anything", 'class="lp-guard lp-inject"',
                     ">Hears<", ">Holds<", ">Backstop<", "discount this call",
                     "not an order to follow"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-inject-block {", self.css)
        self.assertIn(".lp-inject-note {", self.css)
        block = self._slice('class="lp-guard lp-inject"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # It sits beside the Iter8 approval card it backstops, in the demo.
        self.assertLess(self.html.index('id="demo"'),
                        self.html.index("You cannot talk it into anything"))
        self.assertLess(self.html.index("It shows you the booking before it makes it"),
                        self.html.index("You cannot talk it into anything"))
        self.assertLess(self.html.index("You cannot talk it into anything"),
                        self.html.index('id="voices"'))

    def test_move4_rule_is_the_four_defense_model(self):
        self.assertIn('class="lp-note lp-inject-note"', self.html)
        self.assertIn("content is data", self.html)
        self.assertIn("writes are confirmed", self.html)

    # ── Item 5: pinned web lookups ─────────────────────────────────────
    def test_move5_pinned_web_lookups(self):
        for hook in ("If it ever checks the web, only the sites you name",
                     'class="lp-guard lp-pinned"', ">Pinned<", ">Cited<",
                     ">Otherwise<", "up to five domains you name"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-pinned-block {", self.css)
        self.assertIn(".lp-pinned-note {", self.css)
        block = self._slice('class="lp-guard lp-pinned"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # It drops under the Iter8 connectors strip, ahead of the read/write
        # guard (the only bare .lp-guard), inside the services section.
        self.assertLess(self.html.index('id="services"'),
                        self.html.index("lp-pinned-block"))
        self.assertLess(self.html.index("lp-connect-block"),
                        self.html.index("lp-pinned-block"))
        self.assertLess(self.html.index("lp-pinned-block"),
                        self.html.index('class="lp-guard"'))
        self.assertLess(self.html.index("lp-pinned-block"),
                        self.html.index('class="explainer-block'))

    def test_move5_rule_is_cited_and_capped_at_five(self):
        self.assertIn('class="lp-note lp-pinned-note"', self.html)
        self.assertIn("allowed-domains list of up to five", self.html)
        self.assertIn("I don't know", self.html)

    # ── Honesty: labelled content, no invented audio, counters hold ────
    def test_new_copy_has_no_em_dashes(self):
        windows = (
            ("<!-- Iter9 item 4", "<!-- Iter9 item 1"),
            ("<!-- Iter9 item 1", "<!-- Iter9 item 3"),
            ("<!-- Iter9 item 3", "</section>"),
            ("<!-- Iter9 item 2", "</section>"),
            ("<!-- Iter9 item 5", "<!-- Iter5 item 3"),
        )
        for start_marker, end_marker in windows:
            with self.subTest(start=start_marker):
                block = self._slice(start_marker, end_marker)
                self.assertNotIn("\u2014", block)

    def test_all_new_blocks_are_labelled(self):
        for mod in ITER9_NOTE_MODIFIERS:
            with self.subTest(modifier=mod):
                self.assertIn(f'class="lp-note {mod}"', self.html)

    def test_audio_demos_remain_timing_honest(self):
        self.assertNotIn("data-src=", self.html)
        self.assertNotIn("new Audio(", self.js)
        self.assertNotIn("speechSynthesis", self.html)
        self.assertNotIn("speechSynthesis", self.js)
        self.assertEqual(self.html.count("<audio"), 4)
        self.assertIn("Four two-voice demos", self.html)
        self.assertIn("not synced to audio", self.html)
        self.assertNotIn("lp-t-on", self.html)

    def test_iter3_to_8_counts_unchanged(self):
        # New disclaimers use modifier classes, so the bare counts hold.
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertEqual(self.html.count('class="lp-guard"'), 1)
        self.assertEqual(self.html.count('class="lp-stamp'), 2)
        self.assertEqual(self.html.count('class="lp-record"'), 1)
        # The Iter4/Iter5 diarized transcript is untouched: still four bare
        # alternating lines (0,1,0,1); the new lines use a modifier class.
        sp = re.findall(r'<li class="lp-call-line"[^>]*data-sp="(\d)"', self.html)
        self.assertEqual(sp, ["0", "1", "0", "1"])

    def test_new_blocks_reuse_the_gated_reveal_entrance(self):
        # No new motion: the new blocks enter on the shared .reveal observer,
        # which flattens under the flat gate.
        self.assertIn("[data-motion-flat] .reveal", self.css)
        for cls in ("lp-inject-block reveal", "lp-ceiling-block reveal",
                    "lp-seek reveal", "lp-pinned-block reveal"):
            self.assertIn(cls, self.html)
        # The barge-in block carries the same .reveal entrance.
        self.assertIn('class="lp-moment reveal" data-bargein', self.html)

    def test_no_new_js_was_added(self):
        # Every Iter9 item is static content over shipped skins: nothing new in
        # the behaviour layer, and the Iter2 karaoke slot stays the only dormant
        # seek wiring (still keyed off a null timing map).
        self.assertNotIn("data-seek", self.js)
        self.assertNotIn("data-bargein", self.js)
        self.assertNotIn("lp-ceiling", self.js)
        self.assertNotIn("lp-pinned", self.js)
        self.assertIn("const lpTimes = null", self.js)


class TestIter9ProtectedSurfaces(unittest.TestCase):
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
