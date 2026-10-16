"""test_landing_iter6.py — Iteration 6 landing moves.

Pins the five Iter6 items, all shipped as clearly-labelled illustrative /
sample content:

1. Unit-economics card in the calculator section: the spend half, an example at
   published AI list rates, explicitly not a quote.
2. Concurrency spec + overflow rule in the deployments section, reusing the
   Iter5 read/write guard grammar (``.lp-guard``) via a modifier class.
3. "Brief your agent" — the one-paragraph setup artifact the owner writes,
   reusing the Iter5 record-card skin.
4. Copy-page-as-text utility in the footer: one click copies a plain-text digest
   so an owner can paste the page into an AI assistant.
5. Dated shipping log + last-updated stamps, riding the existing scramble
   observer.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css`` /
  ``landing.js``; the only new CSS is additive; no new ``<section>`` is added
  (which would shift the ``section:nth-child(even)`` background parity of every
  section below it); the shipping log reuses the shared scramble observer.
* Honesty: every figure is labelled an example at published rates; the log is a
  labelled sample; nothing references audio or media the page does not already
  ship; the Iter3 note count of five unmodified notes holds (new disclaimers
  reuse the component via a modifier class).
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter6. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter6.
"""

import hashlib
import os
import re
import unittest
from html.parser import HTMLParser

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter6 must not change. Same set Iter2..5
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

# Iter3 shipped 13 <section> elements; Iter4/5/6 add none (background parity).
SECTION_COUNT = 13

# Freshness stamps carry today's date (never an invented figure).
STAMP_DATE = '<time datetime="2026-10-14">14 Oct 2026</time>'


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class _BriefGrabber(HTMLParser):
    def __init__(self):
        super().__init__()
        self.brief = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-copy-brief" in d and "data-brief" in d:
            self.brief = d["data-brief"]


class TestLandingIter6Hooks(unittest.TestCase):
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
        # every section below it; Iter6 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    def test_asset_cache_bust_still_versioned(self):
        self.assertRegex(self.html, r"landing\.css\?v=\d+")
        self.assertRegex(self.html, r"landing\.js\?v=\d+")

    # ── Item 1: unit-economics card ────────────────────────────────────
    def test_move1_unit_economics_card(self):
        for hook in ('class="lp-record lp-cost"', "One 5-minute call",
                     "$0.08 / min", "$0.20 / hr, streamed", "$0.40",
                     "≈ one call", "published AI rates"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-cost {", self.css)
        self.assertIn(".lp-cost dl > div:last-child", self.css)
        # Three typed rows, same .lp-record skin as the Iter5 record card.
        block = self._slice('class="lp-record lp-cost"', "</dl>")
        self.assertEqual(block.count("<dd"), 3)
        # Lives in the calculator section, after the savings card.
        self.assertLess(self.html.index('id="calculator"'), self.html.index('class="lp-record lp-cost"'))
        self.assertLess(self.html.index('class="lp-record lp-cost"'), self.html.index('id="partnership"'))

    def test_move1_figures_are_labelled_example_not_a_quote(self):
        self.assertIn('class="lp-note lp-cost-note"', self.html)
        self.assertIn("not your quote", self.html)
        self.assertIn("published list prices", self.html)
        # Values reuse the shared scramble observer rather than a new one.
        block = self._slice('class="lp-record lp-cost"', "</dl>")
        self.assertEqual(block.count('data-scramble-text="'), 3)

    def test_move1_does_not_disturb_iter5_record_slice(self):
        # The first bare class="lp-record" is still the deployments record.
        self.assertLess(self.html.index('class="lp-record"'),
                        self.html.index('class="lp-record lp-cost"'))

    # ── Item 2: concurrency spec + overflow rule ───────────────────────
    def test_move2_concurrency_spec_and_overflow(self):
        for hook in ("Two customers call at once", "lp-guard-conc", ">Together<",
                     ">Overflow<", "4 calls at once", "never dead air",
                     "missed call"):
            self.assertIn(hook, self.html)
        # Reuses the Iter5 guard grammar; two rows, no buttons, static copy.
        block = self._slice('class="lp-guard lp-guard-conc"', "</ul>")
        self.assertEqual(block.count("<li>"), 2)
        self.assertEqual(block.count("<button"), 0)
        # It lives in the deployments section, beside the post-call record.
        self.assertLess(self.html.index('id="deployments"'), self.html.index("lp-guard-conc"))
        self.assertLess(self.html.index("lp-guard-conc"), self.html.index('id="demo"'))

    def test_move2_leaves_the_read_write_guard_intact(self):
        # The modifier class means the FIRST bare class="lp-guard" is still the
        # services read-vs-write strip that Iter5 pins.
        self.assertEqual(self.html.count('class="lp-guard"'), 1)
        guard = self._slice('class="lp-guard"', "</ul>")
        self.assertIn(">Reads<", guard)
        self.assertIn(">Writes<", guard)
        self.assertEqual(guard.count("<li>"), 2)
        self.assertLess(self.html.index('class="lp-guard"'),
                        self.html.index('class="explainer-block'))

    # ── Item 3: brief-your-agent setup artifact ────────────────────────
    def test_move3_brief_artifact(self):
        for hook in ('class="lp-record lp-brief-card', "Your whole setup",
                     "example brief", 'class="lp-brief"', "Acme Dental",
                     "read the price back", "Hand over, do not guess",
                     'class="lp-note lp-brief-note"', "not a real client"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-brief-card {", self.css)
        self.assertIn(".lp-brief {", self.css)

    def test_move3_is_a_paragraph_not_a_typed_list(self):
        block = self._slice('class="lp-record lp-brief-card', "</div>")
        self.assertIn('class="lp-brief"', block)
        # Same record skin, but a paragraph instead of a <dl> of fields.
        self.assertNotIn("<dd", block)
        # It sits in the process section, ahead of the closing CTA.
        self.assertLess(self.html.index('id="partnership"'),
                        self.html.index('class="lp-record lp-brief-card'))
        self.assertLess(self.html.index('class="lp-record lp-brief-card'),
                        self.html.index('class="partnership-cta'))

    # ── Item 4: copy-page-as-text utility ──────────────────────────────
    def test_move4_copy_page_utility_wiring(self):
        for hook in ('class="lp-copy"', "data-copy-brief", 'class="lp-copy-label"',
                     "Ask your AI about us", "data-brief=", 'data-cursor="Copy"'):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-copy {", self.css)
        self.assertIn("[data-motion-flat] .lp-copy", self.css)
        self.assertIn("[data-copy-brief]", self.js)
        self.assertIn(".lp-copy-label", self.js)
        # Clipboard API with an execCommand fallback, and a label swap.
        self.assertIn("navigator.clipboard.writeText", self.js)
        self.assertIn("document.execCommand('copy')", self.js)
        self.assertIn("Copied", self.js)
        # It lives in the footer, beside the existing links.
        self.assertLess(self.html.index('id="footer"'), self.html.index("data-copy-brief"))

    def test_move4_digest_is_labelled_multiline_and_offline(self):
        grabber = _BriefGrabber()
        grabber.feed(self.html)
        brief = grabber.brief
        self.assertIsNotNone(brief)
        # Multi-line plain text, fit to paste into a model.
        self.assertGreaterEqual(brief.count("\n"), 4)
        # Clearly labelled illustrative sample copy, never a quote.
        self.assertIn("illustrative sample copy", brief.lower())
        self.assertIn("Not a quote".lower(), brief.lower())
        # No URL, no network call in the digest itself.
        self.assertNotIn("http", brief.lower())
        self.assertNotIn("www.", brief.lower())

    # ── Item 5: dated shipping log + last-updated stamps ───────────────
    def test_move5_dated_shipping_log(self):
        for hook in ('class="lp-ship', 'class="lp-log"', "lp-log-new",
                     "What changed lately", "sample log",
                     "Post-call records now carry", "second simultaneous caller"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-log {", self.css)
        self.assertIn(".lp-log-new", self.css)
        self.assertIn(".lp-stamp {", self.css)
        block = self._slice('class="lp-log"', "</ol>")
        self.assertEqual(block.count("<li>"), 3)
        # Newest first: the three dated rows are in descending order.
        dates = re.findall(r'data-scramble-text="(Oct 09|Sep 22|Aug 30)"', block)
        self.assertEqual(dates, ["Oct 09", "Sep 22", "Aug 30"])

    def test_move5_log_rides_existing_scramble_observer(self):
        # The two plain description rows decode via the shared observer; the
        # row carrying an inline "new" pill is not scrambled (so its span
        # survives). Three dates also decode. No new observer is added.
        block = self._slice('class="lp-log"', "</ol>")
        self.assertEqual(block.count("<p data-scramble-text="), 2)
        self.assertEqual(block.count('class="lp-log-new"'), 1)
        self.assertIn("[data-scramble-text]", self.js)
        # The log lives in the results section, beside the ledger figures.
        self.assertLess(self.html.index('id="results"'), self.html.index('class="lp-ship'))

    def test_move5_last_updated_stamps(self):
        # One stamp on the figures, one on the unit rates: both dated today.
        self.assertEqual(self.html.count('class="lp-stamp'), 2)
        self.assertEqual(self.html.count(STAMP_DATE), 2)
        self.assertIn('class="lp-stamp lp-cost-stamp"', self.html)
        self.assertIn(".lp-cost-stamp", self.css)

    # Honesty: generated audio is labeled and remains timing-honest.
    def test_audio_demos_remain_timing_honest(self):
        self.assertNotIn("data-src=", self.html)
        self.assertNotIn("new Audio(", self.js)
        self.assertNotIn("speechSynthesis", self.html)
        self.assertNotIn("speechSynthesis", self.js)
        self.assertEqual(self.html.count("<audio"), 4)
        self.assertIn("Four two-voice demos", self.html)
        self.assertIn("not synced to audio", self.html)
        self.assertNotIn("lp-t-on", self.html)

    def test_iter3_honest_note_count_unchanged(self):
        # New disclaimers use modifier classes, so the count of five
        # unmodified notes holds.
        self.assertEqual(self.html.count('class="lp-note"'), 5)
        self.assertIn('class="lp-note-label"', self.html)


class TestIter6ProtectedSurfaces(unittest.TestCase):
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
