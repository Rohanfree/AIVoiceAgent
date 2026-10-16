"""test_landing_iter10.py — Iteration 10 landing moves (FINAL).

Pins the five Iter10 items, all shipped as clearly-labelled, honest content
over skins the page already ships (no invented audio, no invented figures):

1. Interaction sound layer: a tiny Web Audio blip on hover and press, governed
   by the Iter2 footer sound toggle (the existing ``lp-sound-on`` key) and
   skipped entirely under the Iter1 flat gate. Tones are synthesised, so no
   media byte is added, and the footer states the decision plainly.
2. The voice-activity gate as a stated row: three guard rows under the barge-in
   block state the documented ``vad_threshold`` behaviour (low for phone audio,
   background sound transcribed, the setting written down before launch).
3. Band-glitch shatter: the loader wordmark tears into four clipped bands while
   the page is still arriving, and the hero H1 does the same on hover. The
   overlay is built in JS, aria-hidden, one shatter per host, skipped under the
   flat gate.
4. The draft before it sends: an editable confirmation message with Send /
   Discard, two pre-authored scripted outcome lines over markup already in the
   DOM. Reuses the Iter5 ``.lp-record`` skin and the Iter8 two-branch pattern.
5. "Rules only get stricter": two guard rows under the role cards state that
   restrictions accumulate and a conflict resolves to the safer reading.

Three properties are checked:

* Wiring: the moves are present in ``landing.html`` / ``landing.css`` /
  ``landing.js``; the only new CSS is additive; no new ``<section>`` is added
  (which would shift the ``section:nth-child(even)`` background parity of every
  section below it); the new content reuses the shared observers and the
  ``.reveal`` entrance under the existing motion gate.
* Honesty: every new block is labelled (modifier disclaimers), nothing
  references audio or media the page does not already ship, no em-dashes sneak
  into the new copy, and the Iter3/5/6/7/8/9 counts (five bare notes, one bare
  guard, two stamps, one bare record, four bare transcript lines) hold because
  new components reuse the skins via modifier classes.
* Byte-identity: the contact / login / register / dashboard surfaces are not
  touched by Iter10. Their template digests (and the landing contact-section
  slice) must match the frozen values below.

Note: these tests read the template/asset files directly. The HTML routes are
not fetched because this environment's Starlette/Jinja versions raise on
TemplateResponse for every page route, independent of Iter10.
"""

import hashlib
import os
import re
import unittest

from app.routers import pages_router

ROOT = os.path.dirname(os.path.abspath(__file__))

# Frozen digests for the surfaces Iter10 must not change. Same set Iter2..9
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

# Iter3 shipped 13 <section> elements; Iter4..10 add none (background parity).
SECTION_COUNT = 13

# Every Iter10 honesty block reuses the honest-note component through a
# modifier class (the item-1 caption is its own small label at the toggle, not
# the note component, so it is pinned separately).
ITER10_NOTE_MODIFIERS = (
    "lp-vad-note",
    "lp-draft-note",
    "lp-tighten-note",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestLandingIter10Hooks(unittest.TestCase):
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
        # every section below it; Iter10 deliberately adds none.
        self.assertEqual(self.html.count("<section"), SECTION_COUNT)

    def test_asset_cache_bust_still_versioned(self):
        self.assertRegex(self.html, r"landing\.css\?v=\d+")
        self.assertRegex(self.html, r"landing\.js\?v=\d+")

    def test_iter10_css_banner_and_green_lock(self):
        # The Iter10 block is additive, at the end of the file, and keeps the
        # single --green accent (no new accent colour).
        self.assertIn("Iteration 10 moves", self.css)
        block = self.css[self.css.index("Iteration 10 moves"):]
        self.assertIn("var(--green)", block)
        self.assertNotIn("--green:", block)

    # ── Item 1: interaction sound layer ────────────────────────────────
    def test_move1_interaction_sound_layer(self):
        for hook in ('class="lp-sound-wrap"', 'class="lp-sound-note"',
                     "data-sound-toggle", "off by default"):
            self.assertIn(hook, self.html)
        for hook in ("AudioContext", "webkitAudioContext", "lpBlip", "lpPrimeSound",
                     "lp-sound-on", "createOscillator", "createGain",
                     "(hover:hover) and (pointer:fine)", "pointerover"):
            self.assertIn(hook, self.js)
        self.assertIn(".lp-sound-wrap", self.css)
        self.assertIn(".lp-sound-note", self.css)
        self.assertIn("[data-motion-flat] .lp-sound-wrap", self.css)

    def test_move1_is_opt_in_and_gated(self):
        # Silent unless the existing toggle is on: the layer reads the same key
        # and bails out under the flat gate before it can make a sound.
        self.assertIn("localStorage.getItem('lp-sound-on')", self.js)
        self.assertIn("if (motionFlat || reduceMotion || lpSpeechActive) return;", self.js)
        self.assertIn("0.05", self.js)
        # Built inside the unmute gesture (the Safari rule the toggle documents).
        self.assertIn("if (next) lpPrimeSound();", self.js)
        # The call recordings are intentional page assets; interface tones add no media bytes.
        self.assertIn("demo-call-plumbing-intake-two-voices-v3.mp3", self.html)
        self.assertIn("other.pause()", self.js)

    # ── Item 2: voice-activity gate rows ───────────────────────────────
    def test_move2_voice_activity_gate(self):
        for hook in ("It hears you on a bad line", 'class="lp-guard lp-vad"',
                     ">Quiet caller<", ">Bad line<", ">Your setting<",
                     "vad_threshold", "0.5 batch", "0.08 streaming", "0 = off",
                     "narrowband phone audio", "rather than dropped"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-vad-block {", self.css)
        self.assertIn(".lp-vad-note {", self.css)
        block = self._slice('class="lp-guard lp-vad"', "</ul>")
        self.assertEqual(block.count("<li>"), 3)
        self.assertEqual(block.count("<button"), 0)
        # It sits under the barge-in rows it completes (audibility), still in the
        # demo section, before the voices block.
        self.assertLess(self.html.index("It stops the moment you talk back"),
                        self.html.index("It hears you on a bad line"))
        self.assertLess(self.html.index("It hears you on a bad line"),
                        self.html.index('id="voices"'))

    def test_move2_is_labelled_source_and_static(self):
        self.assertIn('class="lp-note lp-vad-note"', self.html)
        self.assertIn("Documented\n            behaviour, not a slogan.", self.html)
        self.assertIn('class="lp-guard-block lp-vad-block reveal"', self.html)

    # ── Item 3: band-glitch shatter ────────────────────────────────────
    def test_move3_band_glitch(self):
        self.assertIn("data-glitch", self.html)  # loader brand hook
        for hook in ("lpBandGlitch", "lp-glitch-layer", "BANDS = 4", "clipPath",
                     "cloneNode", "data-glitch-live", "aria-hidden",
                     "lp-loader-brand", "lp-loader-wordmark", "hero-heading",
                     "mouseenter"):
            self.assertIn(hook, self.js)
        self.assertIn(".lp-glitch-layer", self.css)
        self.assertIn("[data-motion-flat] .lp-glitch-layer", self.css)

    def test_move3_fires_on_loader_and_hero_and_is_gated(self):
        # Loader fires on its own while the page arrives, hero on hover.
        self.assertIn("setTimeout(() => lpBandGlitch(wm, 7, 90), 450)", self.js)
        self.assertIn("setTimeout(() => lpBandGlitch(wm, 7, 90), 2400)", self.js)
        self.assertIn("h1.addEventListener('mouseenter', () => lpBandGlitch(h1, 5, 80))",
                      self.js)
        # One shatter per host, and nothing at all under the flat gate.
        self.assertIn("if (motionFlat || reduceMotion || !src) return;", self.js)
        self.assertIn("data-glitch-live", self.js)
        # The overlay never enters the a11y tree.
        self.assertIn("layer.setAttribute('aria-hidden', 'true')", self.js)

    # ── Item 4: editable draft with Send / Discard ─────────────────────
    def test_move4_editable_draft(self):
        for hook in ('class="lp-moment reveal" data-draft',
                     "You see the text before your customer does",
                     'class="lp-record lp-draft"', 'class="lp-draft-status"',
                     '<textarea class="lp-draft-body"', ">Send<", ">Discard<",
                     'data-choice="send"', 'data-choice="drop"',
                     "Booked Tue 10:00 with Dr. Ellis", '"07xxx · J. Marsh"'):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-draft {", self.css)
        self.assertIn(".lp-draft-ctas", self.css)
        self.assertIn("[data-motion-flat] .lp-draft-ctas", self.css)
        # Two pre-authored outcomes exist, hidden until a choice is made.
        self.assertIn('hidden data-out="send"', self.html)
        self.assertIn('hidden data-out="drop"', self.html)

    def test_move4_client_side_swap_wiring(self):
        self.assertIn("[data-draft]", self.js)
        self.assertIn("lp-draft-status", self.js)
        self.assertIn("b.disabled = true", self.js)
        self.assertIn("line.hidden =", self.js)
        # It sits right after the Iter8 approval card and before the voices.
        self.assertLess(self.html.index("It shows you the booking before it makes it"),
                        self.html.index("You see the text before your customer does"))
        self.assertLess(self.html.index("You see the text before your customer does"),
                        self.html.index('id="voices"'))

    def test_move4_is_labelled_and_editable(self):
        self.assertIn('class="lp-note lp-draft-note"', self.html)
        self.assertIn("editable sample copy", self.html)
        # A real editable field, not a picture of one.
        self.assertIn("</textarea>", self.html)
        self.assertNotIn("<textarea class=\"lp-draft-body\" rows=\"3\" disabled", self.html)

    # ── Item 5: tighten-only guardrail rows ────────────────────────────
    def test_move5_tighten_only_rules(self):
        for hook in ("Rules only get stricter", 'class="lp-guard lp-tighten"',
                     ">Tightens<", ">Conflicts<",
                     "Nothing you add can loosen what is already there",
                     "more cautious one applies"):
            self.assertIn(hook, self.html)
        self.assertIn(".lp-tighten-block {", self.css)
        self.assertIn(".lp-tighten-note {", self.css)
        block = self._slice('class="lp-guard lp-tighten"', "</ul>")
        self.assertEqual(block.count("<li>"), 2)
        self.assertEqual(block.count("<button"), 0)
        # It closes the onboarding story in the partnership section, after the
        # role cards and before the closing CTA.
        self.assertLess(self.html.index('class="lp-roles reveal"'),
                        self.html.index("Rules only get stricter"))
        self.assertLess(self.html.index("Rules only get stricter"),
                        self.html.index('class="partnership-cta'))
        self.assertLess(self.html.index("Rules only get stricter"),
                        self.html.index('id="faq"'))

    def test_move5_is_labelled_our_practice(self):
        self.assertIn('class="lp-note lp-tighten-note"', self.html)
        self.assertIn('class="lp-guard-block lp-tighten-block reveal"', self.html)
        self.assertIn("rules accumulate", self.html)

    # ── Honesty: labelled content, no invented audio, counters hold ────
    def test_new_copy_has_no_em_dashes(self):
        windows = (
            ("<!-- Iter10 item 2", "<!-- Iter9 item 3"),
            ("<!-- Iter10 item 4", "<!-- Iter9 item 4"),
            ("<!-- Iter10 item 5", '<div class="partnership-cta'),
        )
        for start_marker, end_marker in windows:
            with self.subTest(start=start_marker):
                block = self._slice(start_marker, end_marker)
                self.assertNotIn("\u2014", block)

    def test_all_new_blocks_are_labelled(self):
        for mod in ITER10_NOTE_MODIFIERS:
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

    def test_iter3_to_9_counts_unchanged(self):
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
        # No new motion observer: the new blocks enter on the shared .reveal
        # observer, which flattens under the flat gate.
        self.assertIn("[data-motion-flat] .reveal", self.css)
        for cls in ("lp-vad-block reveal", "lp-tighten-block reveal"):
            self.assertIn(cls, self.html)
        for marker in ('class="lp-moment reveal" data-draft', "lp-vad-block"):
            self.assertIn(marker, self.html)


class TestIter10ProtectedSurfaces(unittest.TestCase):
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
