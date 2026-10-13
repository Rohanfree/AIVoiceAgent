"""test_landing_iter8.py — Iteration 8 landing moves.

Pins the five Iter8 items, all shipped as clearly-labelled, honest content over
reused skins (no invented audio, no invented figures beyond a labelled example):

1. The approval card demo in a call transcript: the proposed write is shown with
   its target and values, with Allow once / Deny revealing one of two
   pre-authored outcome lines. Reuses the Iter5 ``.lp-record`` skin and the
   diarized utterance skin.
2. Caller recognition + the field-minimized lookup: a read-only CRM lookup
   resolves the number before the greeting, and two guard rows state the
   privacy rule. Reuses the Iter5 ``.lp-lock`` badge and guard grammar.
3. The missed-call callback routine: the Iter5 ``.lp-record`` skin carrying the
   agreed fields, plus a shared note for the stale-data rule.
4. Cited answers: the Iter5 ``.lp-record`` skin carrying quoted / source /
   unknown, so a quoted number can be checked against the owner's sheet.
5. The connect-and-revoke integrations strip: a type-only chip list of the
   systems we can connect, plus guard rows for how access is granted and revoked.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css`` /
  ``landing.js``; the only new CSS is additive; no new ``<section>`` is added
  (which would shift the ``section:nth-child(even)`` background parity of every
  section below it); the new content reuses the shared observers and the
  ``.reveal`` entrance under the existing motion gate.
* Honesty: every new block is labelled (modifier disclaimers), nothing
  references audio or media the page does not already ship, no em-dashes sneak
  into the new copy, and the Iter3/5/6/7 counts (five bare notes, one bare
  guard, two stamps, four bare transcript lines) hold because new components
  reuse the skins via modifier classes.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter8. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter8.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter8 must not change. Same set Iter2..7
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

# Iter3 shipped 13 <section> elements; Iter4..8 add none (background parity).
SECTION_COUNT = 13

# Every Iter8 block reuses the honest-note component through a modifier class.
ITER8_NOTE_MODIFIERS = (
    "lp-approve-note",
    "lp-known-note",
    "lp-routine-note",
    "lp-cite-note",
    "lp-connect-note",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter8Hooks(unittest.TestCase):
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
        # every section below it; Iter8 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    def test_asset_cache_bust_still_versioned(self):
        self.assertRegex(self.html, r"landing\.css\?v=\d+")
        self.assertRegex(self.html, r"landing\.js\?v=\d+")

    def test_iter8_css_banner_and_green_lock(self):
        # The Iter8 block is additive, at the end of the file, and keeps the
        # single --green accent (no new accent colour).
        self.assertIn("Iteration 8 moves", self.css)
        block = self.css[self.css.index("Iteration 8 moves"):]
        self.assertIn("var(--green)", block)
        self.assertNotIn("--green:", block)

    # ── Item 1: approval card demo in a transcript ─────────────────────
    def test_move1_approval_card_demo(self):
        for hook in ("It shows you the booking before it makes it",
                     'class="lp-approve-status"', ">Allow once<", ">Deny<",
                     'data-choice="yes"', 'data-choice="no"',
                     ">book_appointment<", '"Tue 10:00 · cleaning"',
                     "No answer in 10 minutes"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-approve {", self.css)
        self.assertIn(".lp-approve-ctas", self.css)
        # Both pre-authored outcomes exist, hidden until a choice is made.
        self.assertIn('data-out="yes"', self.html)
        self.assertIn('data-out="no"', self.html)
        self.assertIn('data-sp="1" hidden data-out="yes"', self.html)
        self.assertIn('data-sp="1" hidden data-out="no"', self.html)
        # It lives in the demo section, before the voices block.
        self.assertLess(self.html.index('id="demo"'),
                        self.html.index("It shows you the booking before it makes it"))
        self.assertLess(self.html.index("It shows you the booking before it makes it"),
                        self.html.index('id="voices"'))

    def test_move1_is_labelled_example_and_has_two_branches(self):
        self.assertIn('class="lp-note lp-approve-note"', self.html)
        self.assertIn("scripted outcomes", self.html)
        # The card reuses the Iter5 record skin via a modifier class.
        self.assertIn('class="lp-record lp-approve"', self.html)

    def test_move1_client_side_swap_wiring(self):
        self.assertIn("[data-approve]", self.js)
        self.assertIn("data-choice", self.js)
        self.assertIn("data-out", self.js)
        self.assertIn("lp-approve-status", self.js)
        # Disables both buttons and hides the non-matching outcome line.
        self.assertIn("b.disabled = true", self.js)
        self.assertIn("line.hidden =", self.js)
        # No timer, no new autoplay, no audio: the two branches are the demo.
        self.assertIn("[data-motion-flat] .lp-approve-ctas", self.css)

    # ── Item 2: caller recognition + field-minimized lookup ────────────
    def test_move2_caller_recognition_and_lookup(self):
        for hook in ("It knows who's calling", 'class="lp-lock">known caller',
                     "Morning, Ms. Okafor", 'class="lp-guard lp-lookup"',
                     ">Looks up<", ">Stays yours<", "name and history only",
                     "read-only until you switch writes"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-lookup {", self.css)
        block = self._slice('class="lp-guard lp-lookup"', "</ul>")
        self.assertEqual(block.count("<li>"), 2)
        self.assertEqual(block.count("<button"), 0)
        # It reuses the Iter5 lock badge grammar and sits in the demo section.
        self.assertIn('class="lp-lock"', self.html)
        self.assertLess(self.html.index('id="demo"'), self.html.index("It knows who's calling"))
        self.assertLess(self.html.index("It knows who's calling"), self.html.index('id="voices"'))

    def test_move2_is_labelled_example(self):
        self.assertIn('class="lp-note lp-known-note"', self.html)
        self.assertIn("not a real caller", self.html)

    # ── Item 3: missed-call callback routine ───────────────────────────
    def test_move3_routine_card(self):
        for hook in ("It calls back when you miss the call", 'class="lp-record lp-routine"',
                     "Missed-call callback", "<dt>runs</dt>", "<dt>input</dt>",
                     "<dt>may</dt>", "<dt>limits</dt>",
                     "Today's missed calls", "runs on stale data"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-routine {", self.css)
        self.assertIn(".lp-routine-note {", self.css)
        block = self._slice('class="lp-record lp-routine"', "</dl>")
        self.assertEqual(block.count("<dd"), 4)
        # It lives in the deployments section, after the overflow rule.
        self.assertLess(self.html.index('id="deployments"'), self.html.index("Missed-call callback"))
        self.assertLess(self.html.index("lp-guard-conc"), self.html.index("Missed-call callback"))
        self.assertLess(self.html.index("Missed-call callback"), self.html.index('id="demo"'))

    def test_move3_stale_data_rule_is_stated(self):
        self.assertIn('class="lp-note lp-routine-note"', self.html)
        self.assertIn("reports the failure", self.html)
        self.assertIn("run by hand for a week", self.html)

    # ── Item 4: cited-answers source row ───────────────────────────────
    def test_move4_cited_answers(self):
        for hook in ("Every quoted price carries its source", 'class="lp-record lp-cite"',
                     "Quoted answers", "<dt>quoted</dt>", "<dt>source</dt>",
                     "<dt>unknown</dt>", "new patient cleaning",
                     "price sheet you gave us", "never estimated"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-cite {", self.css)
        self.assertIn(".lp-cite-note {", self.css)
        block = self._slice('class="lp-record lp-cite"', "</dl>")
        self.assertEqual(block.count("<dd"), 3)
        # Each value rides the shared scramble-on-reveal observer (no new one).
        self.assertEqual(block.count('data-scramble-text="'), 3)
        # It lives in the deployments section, beside the post-call record.
        self.assertLess(self.html.index('id="deployments"'), self.html.index("Quoted answers"))
        self.assertLess(self.html.index("Quoted answers"), self.html.index('id="demo"'))

    def test_move4_rule_is_no_source_no_answer(self):
        self.assertIn('class="lp-note lp-cite-note"', self.html)
        self.assertIn("No source, no answer", self.html)

    # ── Item 5: connect-and-revoke integrations strip ──────────────────
    def test_move5_integrations_strip(self):
        for hook in ("Connects to the systems you already run", 'class="lp-connect"',
                     'aria-label="Systems we can connect"', ">Google Calendar<",
                     ">Outlook<", ">HubSpot<", ">Salesforce<", "your dialer",
                     'class="lp-guard lp-connect-guard"', ">Granted<", ">Revoked<",
                     "no master key"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-connect {", self.css)
        self.assertIn(".lp-connect li", self.css)
        self.assertEqual(self.html.count('class="lp-connect"'), 1)
        chips = self._slice('class="lp-connect"', "</ul>")
        self.assertEqual(chips.count("<li>"), 6)
        self.assertEqual(chips.count("<button"), 0)
        guard = self._slice('class="lp-guard lp-connect-guard"', "</ul>")
        self.assertEqual(guard.count("<li>"), 2)
        # It lives in the services block, ahead of the read/write guard.
        self.assertLess(self.html.index('id="services"'), self.html.index("Connects to the systems"))
        self.assertLess(self.html.index("Connects to the systems"),
                        self.html.index('class="explainer-block'))

    def test_move5_is_type_only_and_labelled(self):
        # No logo assets: the chips are text only.
        self.assertNotIn("logo", self._slice('class="lp-connect"', "</ul>").lower())
        self.assertIn('class="lp-note lp-connect-note"', self.html)
        self.assertIn("no logos, no implied partnership", self.html)

    # ── Honesty: labelled content, no invented audio, counters hold ────
    def test_new_copy_has_no_em_dashes(self):
        windows = (
            ("<!-- Iter8 item 5", "<!-- Iter5 item 3"),
            ("<!-- Iter8 item 4", "<!-- Iter6 item 2"),
            ("<!-- Iter8 item 3", "</section>"),
            ("<!-- Iter8 item 2", "<!-- Iter8 item 1"),
            ("<!-- Iter8 item 1", "</section>"),
        )
        for start_marker, end_marker in windows:
            with self.subTest(start=start_marker):
                block = self._slice(start_marker, end_marker)
                self.assertNotIn("—", block)

    def test_all_new_blocks_are_labelled(self):
        for mod in ITER8_NOTE_MODIFIERS:
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

    def test_iter3_to_7_counts_unchanged(self):
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
        for cls in ("lp-approve-note", "lp-moment", "lp-routine-block",
                    "lp-cite-block", "lp-connect-block"):
            self.assertIn(cls, self.html)
        for marker in ("data-approve", "It knows who's calling"):
            self.assertIn(marker, self.html)
        # The approval moment and the recognition moment both carry .reveal.
        self.assertIn('class="lp-moment reveal" data-approve', self.html)
        self.assertIn('class="lp-moment reveal"', self.html)


class TestIter8ProtectedSurfaces(unittest.TestCase):
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
