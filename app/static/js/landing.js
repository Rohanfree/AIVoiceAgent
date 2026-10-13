// ============================================================
// Automite AI — Landing Page JS
// ============================================================

document.addEventListener('DOMContentLoaded', () => {

  /* ── Navbar: hide on scroll down, show on scroll up ─── */
  const navbar = document.getElementById('navbar');
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const current = window.scrollY;
    if (current > 80) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
    lastScroll = current;
  }, { passive: true });

  /* ── Hamburger menu ─────────────────────────────────── */
  const burger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobileMenu');
  burger.addEventListener('click', () => {
    const isOpen = burger.classList.toggle('open');
    mobileMenu.classList.toggle('open', isOpen);
    burger.setAttribute('aria-expanded', isOpen);
  });
  mobileMenu.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      burger.classList.remove('open');
      mobileMenu.classList.remove('open');
      burger.setAttribute('aria-expanded', 'false');
    });
  });

  /* ── IntersectionObserver fade-in-up ────────────────── */
  const revealEls = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  revealEls.forEach(el => observer.observe(el));

  /* ── FAQ accordion ───────────────────────────────────── */
  document.querySelectorAll('.faq-item').forEach(item => {
    const q = item.querySelector('.faq-question');
    q.addEventListener('click', () => {
      const wasOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
      if (!wasOpen) item.classList.add('open');
    });
    q.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); q.click(); }
    });
  });

  /* ── Contact Form ────────────────────────────────────── */
  const form = document.getElementById('contactForm');
  const successMsg = document.getElementById('formSuccess');

  function showMsg(text, isError) {
    if (!successMsg) return;
    successMsg.textContent = text;
    successMsg.style.display = 'flex';
    successMsg.style.alignItems = 'center';
    successMsg.style.padding = '16px 20px';
    successMsg.style.borderRadius = '10px';
    successMsg.style.fontWeight = '600';
    successMsg.style.fontSize = '15px';
    successMsg.style.marginTop = '12px';
    if (isError) {
      successMsg.style.background = '#fff0f0';
      successMsg.style.border = '1px solid rgba(192,57,43,0.3)';
      successMsg.style.color = '#c0392b';
    } else {
      successMsg.style.background = '#e8f5ee';
      successMsg.style.border = '1px solid rgba(26,77,58,0.25)';
      successMsg.style.color = '#1A4D3A';
    }
    setTimeout(() => { successMsg.style.display = 'none'; }, isError ? 8000 : 6000);
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Sending…';
      const fd = new FormData(form);
      const data = Object.fromEntries(fd.entries());
      try {
        const res = await fetch('/automiteaiapplication/automiteui/api/contact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        if (res.ok) {
          form.reset();
          showMsg('✅ Message received! We\'ll respond within 24 hours.', false);
        } else {
          const err = await res.json().catch(() => ({}));
          showMsg('❌ ' + (err.detail || 'Something went wrong. Please email us at aiautomite@gmail.com'), true);
        }
      } catch (_) {
        showMsg('❌ Could not send message. Please email us at aiautomite@gmail.com', true);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Send Message';
      }
    });
  }

  /* ── ROI Calculator ──────────────────────────────────── */
  const hSlider = document.getElementById('hoursSlider');
  const wSlider = document.getElementById('wageSlider');
  
  if (hSlider && wSlider) {
    const hVal = document.getElementById('hoursVal');
    const wVal = document.getElementById('wageVal');
    const mCostRes = document.getElementById('monthlyCostRes');
    const aCostRes = document.getElementById('aiCostRes');
    const mSavRes = document.getElementById('monthlySavingsRes');
    const sPctRes = document.getElementById('savingsPercentRes');
    const ySavRes = document.getElementById('yearlySavingsRes');

    const updateCalc = () => {
      const hours = parseInt(hSlider.value);
      const wage = parseInt(wSlider.value);
      
      hVal.textContent = hours + ' hours';
      wVal.textContent = '$' + wage + '/hr';

      // Math (assuming 4 weeks a month)
      const monthlyHumanCost = hours * 4 * wage;
      // AI Cost = $0.10 per minute. Mins per month = hours * 4 * 60
      const monthlyAiCost = hours * 4 * 60 * 0.10;
      
      const monthlySavings = monthlyHumanCost - monthlyAiCost;
      const savingsPercent = Math.round((monthlySavings / monthlyHumanCost) * 100);
      const yearlySavings = monthlySavings * 12;

      mCostRes.textContent = '$' + monthlyHumanCost.toLocaleString();
      aCostRes.textContent = '$' + monthlyAiCost.toLocaleString();
      mSavRes.textContent = '$' + monthlySavings.toLocaleString();
      sPctRes.textContent = savingsPercent + '%';
      ySavRes.textContent = '$' + yearlySavings.toLocaleString();
      
      // Update slider fill tracks
      const updateSliderTrack = (slider) => {
        const min = parseInt(slider.min);
        const max = parseInt(slider.max);
        const val = parseInt(slider.value);
        const pct = ((val - min) / (max - min)) * 100;
        slider.style.background = `linear-gradient(to right, #1A4D3A ${pct}%, #E8F0EC ${pct}%)`;
      };
      updateSliderTrack(hSlider);
      updateSliderTrack(wSlider);
    };

    [hSlider, wSlider].forEach(s => s.addEventListener('input', updateCalc));
    updateCalc();
  }

  /* ── Landing Moves: metric ledger count-up (SAMPLE figures) ── */
  // Motion demotion gate (Iter 1, Move 1): the inline head script decides once
  // and sets data-motion-flat on <html>. Every animated branch below reads this,
  // so flat visitors get the final state instantly with no animation.
  const motionFlat = document.documentElement.hasAttribute('data-motion-flat');
  const reduceMotion = motionFlat || window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Iter2 Move 1: custom cursor — diamond → label pill ─────────────
     Decorative chrome for fine pointers only. The diamond is the resting
     state; when the pointer lands on a [data-cursor] target the pill wipes
     open from the left and names it (Book, Play call, Drag). Bails out
     entirely under the flat gate / reduced motion, leaving the OS cursor. */
  (function () {
    const cursor = document.querySelector('.lp-cursor');
    const label = document.querySelector('.lp-cursor-label');
    if (!cursor || !label) return;
    if (motionFlat || reduceMotion || !('requestAnimationFrame' in window)) return;
    const labelText = label.querySelector('[data-cursor-text]');
    let mx = Math.round(window.innerWidth / 2), my = Math.round(window.innerHeight / 2);
    let dx = mx, dy = my, lx = mx, ly = my, raf = 0;
    function setXY(el, x, y) { el.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)'; }
    function kick() { if (!raf) raf = requestAnimationFrame(step); }
    function step() {
      raf = 0;
      dx += (mx - dx) * 0.18; dy += (my - dy) * 0.18; // dot leads
      lx += (mx - lx) * 0.12; ly += (my - ly) * 0.12; // pill trails a little
      setXY(cursor, dx, dy);
      setXY(label, lx, ly);
      if (Math.abs(mx - dx) > 0.2 || Math.abs(my - dy) > 0.2 ||
          Math.abs(mx - lx) > 0.2 || Math.abs(my - ly) > 0.2) kick();
    }
    setXY(cursor, dx, dy); setXY(label, lx, ly);
    window.addEventListener('pointermove', (e) => {
      if (e.pointerType && e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
      mx = e.clientX; my = e.clientY; kick();
    }, { passive: true });
    document.addEventListener('pointerover', (e) => {
      const t = e.target && e.target.closest ? e.target.closest('[data-cursor]') : null;
      if (t) {
        if (labelText) labelText.textContent = t.getAttribute('data-cursor') || '';
        label.classList.add('on');
      } else {
        label.classList.remove('on');
      }
    }, { passive: true });
  })();

  /* ── Iter2 Move 2: footer sound toggle ───────────────────────────────
     Off by default and never autoplayed. One click unmutes both ambient
     looping videos (hero orb + manifesto drift); the choice is remembered.
     Under the flat gate the control is inert: it starts muted, restores
     nothing, and its CSS is hidden alongside the loops it would unmute. */
  (function () {
    const btn = document.querySelector('[data-sound-toggle]');
    if (!btn || motionFlat) return;
    const loops = document.querySelectorAll('.lp-hero-orb-video, .lp-manifesto-bg');
    const KEY = 'lp-sound-on';
    let on = false;
    try { on = localStorage.getItem(KEY) === '1'; } catch (_) { /* private mode */ }
    function apply(state, playNow) {
      on = state;
      loops.forEach((v) => {
        v.muted = !state;
        if (state && playNow) { try { const pr = v.play(); if (pr && pr.catch) pr.catch(() => {}); } catch (_) {} }
      });
      btn.setAttribute('aria-pressed', state ? 'true' : 'false');
      btn.setAttribute('aria-label', state ? 'Mute ambient sound' : 'Unmute ambient sound');
    }
    // Restore the muted flag only — playback already began muted, so this never
    // counts as an autoplay and cannot startle anyone on first paint.
    apply(on, false);
    btn.addEventListener('click', () => {
      const next = !on;
      apply(next, true);
      try { localStorage.setItem(KEY, next ? '1' : '0'); } catch (_) { /* private mode */ }
    });
  })();

  function lpFmt(value, decimals, suffix) {
    if (decimals === 0) {
      return Math.round(value).toLocaleString('en-US') + suffix;
    }
    return value.toFixed(decimals) + suffix;
  }
  function lpCountUp(el) {
    const target = parseFloat(el.getAttribute('data-count'));
    const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    const suffix = el.getAttribute('data-suffix') || '';
    if (reduceMotion || !('requestAnimationFrame' in window)) {
      el.textContent = lpFmt(target, decimals, suffix);
      return;
    }
    const dur = 1400;
    let t0 = null;
    function frame(t) {
      if (!t0) t0 = t;
      const p = Math.min((t - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = lpFmt(target * eased, decimals, suffix);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  const lpNums = document.querySelectorAll('.lp-ledger-num[data-count]');
  if (lpNums.length) {
    if (reduceMotion) {
      // Reduced motion: show the finals instantly (server already rendered them,
      // this is a belt-and-braces no-op that guarantees the exact values).
      lpNums.forEach(el => {
        const target = parseFloat(el.getAttribute('data-count'));
        const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
        el.textContent = lpFmt(target, decimals, el.getAttribute('data-suffix') || '');
      });
    } else {
      // Reset the server-rendered finals so the count-up has somewhere to run from.
      lpNums.forEach(el => { el.textContent = '0'; });
      if (!('IntersectionObserver' in window)) {
        lpNums.forEach(lpCountUp);
      } else {
        const no = new IntersectionObserver((entries) => {
          entries.forEach(e => {
            if (e.isIntersecting) { lpCountUp(e.target); no.unobserve(e.target); }
          });
        }, { threshold: 0.4 });
        lpNums.forEach(el => no.observe(el));
      }
    }
  }

  /* ── Landing Moves: manifesto word reveal ──────────────────── */
  const lpMan = document.querySelector('.lp-manifesto-text');
  if (lpMan) {
    let lpWords = lpMan.querySelectorAll('.lp-w');
    if (!lpWords.length) {
      // Client-side split fallback if the server did not wrap words.
      // The green clause is pinned by data-green-from/to so the fallback marks
      // exactly the same words as the server-rendered spans ("book every job,").
      const gf = parseInt(lpMan.getAttribute('data-green-from') || '8', 10);
      const gt = parseInt(lpMan.getAttribute('data-green-to') || '10', 10);
      const text = lpMan.textContent.trim().split(/\s+/);
      lpMan.textContent = '';
      text.forEach((word, i) => {
        const s = document.createElement('span');
        s.className = 'lp-w' + ((i >= gf && i <= gt) ? ' lp-w-mid' : '');
        s.textContent = word;
        lpMan.appendChild(s);
        lpMan.appendChild(document.createTextNode(' '));
      });
      lpWords = lpMan.querySelectorAll('.lp-w');
    }
    if (reduceMotion || !('IntersectionObserver' in window)) {
      lpWords.forEach(w => w.classList.add('lp-on'));
    } else {
      const mo = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            lpWords.forEach((w, i) => {
              setTimeout(() => w.classList.add('lp-on'), i * 90);
            });
            mo.disconnect();
          }
        });
      }, { threshold: 0.35 });
      mo.observe(lpMan);
    }
  }

  /* ── Move 3 (Iter 1): masked split-line reveals ─────────────── */
  // Each .lp-split block holds .lp-line > .lp-line-in (see CSS). One observer
  // per block; the inner lines slide up with a --i based stagger.
  const lpSplits = document.querySelectorAll('.lp-split');
  if (lpSplits.length) {
    if (reduceMotion || !('IntersectionObserver' in window)) {
      lpSplits.forEach(s => s.classList.add('lp-in'));
    } else {
      const so = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) { e.target.classList.add('lp-in'); so.unobserve(e.target); }
        });
      }, { threshold: 0.2 });
      lpSplits.forEach(s => so.observe(s));
    }
  }

  /* ── Move 5 (Iter 1): deployments drag rail ─────────────────── */
  // Horizontal pointer-drag gallery: 1:1 grab, momentum fling with friction
  // decay, infinite wrap via a 3x card buffer, and card titles that mask-reveal
  // only as a card docks near the viewport center. Degrades to native
  // overflow-x scroll under the flat gate / reduced motion.
  (function () {
    const rail = document.querySelector('[data-rail]');
    if (!rail) return;
    const track = rail.querySelector('[data-rail-track]');
    if (!track) return;

    if (motionFlat || reduceMotion || !('requestAnimationFrame' in window)) {
      rail.classList.add('lp-rail-static');
      return;
    }

    const originals = Array.prototype.slice.call(track.children);
    const base = originals.length;
    if (!base) return;

    function cloneSet() {
      const frag = document.createDocumentFragment();
      originals.forEach((node) => {
        const clone = node.cloneNode(true);
        clone.setAttribute('aria-hidden', 'true');
        clone.setAttribute('tabindex', '-1');
        frag.appendChild(clone);
      });
      return frag;
    }
    track.insertBefore(cloneSet(), track.firstChild); // leading buffer
    track.appendChild(cloneSet());                    // trailing buffer
    const all = Array.prototype.slice.call(track.children);

    let loopWidth = 0, x = 0, target = 0, velocity = 0;
    let dragging = false, settling = false, moved = false, raf = 0;
    let startX = 0, startTarget = 0, lastX = 0, lastT = 0;
    const nowMs = () => (window.performance || Date).now();

    function measure() {
      loopWidth = all[base].offsetLeft - all[0].offsetLeft;
      if (!loopWidth || loopWidth < 1) loopWidth = track.scrollWidth / 3;
    }
    function normalize() {
      if (!loopWidth) return;
      while (target <= -loopWidth) { target += loopWidth; x += loopWidth; }
      while (target > 0) { target -= loopWidth; x -= loopWidth; }
    }
    function render() {
      normalize();
      track.style.transform = 'translate3d(' + x.toFixed(2) + 'px,0,0)';
      const railW = rail.clientWidth || 1;
      const half = railW / 2, plateau = railW * 0.06, gate = railW * 0.42;
      for (let i = 0; i < all.length; i++) {
        const card = all[i];
        const inner = card.querySelector('.lp-index-name-in');
        if (!inner) continue;
        const cx = card.offsetLeft + card.offsetWidth / 2 + x;
        const d = Math.abs(cx - half);
        const p = 1 - Math.min(1, Math.max(0, d - plateau) / gate);
        inner.style.transform = 'translateY(' + ((1 - p) * 110).toFixed(2) + '%)';
      }
    }
    function step() {
      raf = 0;
      if (settling) {
        if (Math.abs(velocity) > 0.1) { target += velocity; velocity *= 0.94; }
        else { velocity = 0; settling = false; }
      }
      x += (target - x) * 0.12;
      if (Math.abs(target - x) < 0.05 && !dragging && !settling) x = target;
      render();
      if (dragging || settling || Math.abs(target - x) > 0.05) {
        raf = requestAnimationFrame(step);
      }
    }
    function kick() { if (!raf) raf = requestAnimationFrame(step); }

    function onDown(e) {
      if (!e) return;
      if (e.button != null && e.button !== 0) return;
      // Stop the browser's native link/text drag on mouse-drag; it otherwise
      // swallows the pointermove stream and the rail freezes after one frame.
      // (Touch relies on touch-action: pan-y instead, so vertical scroll survives.)
      if (e.pointerType === 'mouse' && e.cancelable) e.preventDefault();
      dragging = true; moved = false;
      startX = e.clientX; startTarget = target;
      lastX = e.clientX; lastT = nowMs(); velocity = 0;
      rail.classList.add('lp-grabbing');
      kick();
    }
    function onMove(e) {
      if (!dragging || !e) return;
      if (e.clientX == null) return;
      const dx = e.clientX - startX;
      if (Math.abs(dx) > 4) moved = true;
      target = startTarget + dx;
      x = target; // 1:1 grab tracking
      const t = nowMs();
      const dt = Math.max(1, t - lastT);
      velocity = Math.max(-80, Math.min(80, (e.clientX - lastX) / dt * 16.67));
      lastX = e.clientX; lastT = t;
      kick();
    }
    function onUp() {
      if (!dragging) return;
      dragging = false;
      rail.classList.remove('lp-grabbing');
      settling = Math.abs(velocity) > 0.1;
      kick();
    }

    // Move/up live on window so the drag survives the pointer leaving the rail.
    if (window.PointerEvent) {
      rail.addEventListener('pointerdown', onDown);
      window.addEventListener('pointermove', onMove, { passive: true });
      window.addEventListener('pointerup', onUp);
      window.addEventListener('pointercancel', onUp);
    } else {
      rail.addEventListener('mousedown', onDown);
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      rail.addEventListener('touchstart', (e) => onDown(e.touches[0]), { passive: true });
      window.addEventListener('touchmove', (e) => onMove(e.touches[0]), { passive: true });
      window.addEventListener('touchend', onUp);
    }

    // Suppress the link click that follows a drag.
    rail.addEventListener('click', (e) => {
      if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
    }, true);

    // Keyboard: bring a focused (real) card to the center.
    originals.forEach((card) => {
      card.addEventListener('focus', () => {
        target = x = rail.clientWidth / 2 - (card.offsetLeft + card.offsetWidth / 2);
        kick();
      });
    });

    let rt = 0;
    window.addEventListener('resize', () => {
      clearTimeout(rt);
      rt = setTimeout(() => { measure(); render(); }, 150);
    }, { passive: true });

    measure();
    // Start with the first real card docked at center.
    target = x = rail.clientWidth / 2 - (all[base].offsetLeft + all[base].offsetWidth / 2);
    render();
  })();

  /* ── Iter2 Move 3: arc-mask lens ────────────────────────────────────
     One --mask-arc scalar (0→1) grows the elliptical green lens. Shared by
     the loader exit and the lightbox open/close so both read as the same
     gesture. Inert under the flat gate: no tween, no lens — the lightbox
     simply shows as before. */
  const lpLensEl = document.getElementById('lp-lens');
  const lpLensOn = !motionFlat && !reduceMotion && !!lpLensEl && ('requestAnimationFrame' in window);
  function lpArcSet(v) { if (lpLensEl) lpLensEl.style.setProperty('--mask-arc', String(v)); }
  function lpArc(from, to, ms, done) {
    if (!lpLensOn) { lpArcSet(to); if (done) done(); return; }
    const t0 = performance.now();
    lpArcSet(from);
    (function frame(now) {
      const p = Math.min(1, (now - t0) / ms);
      const eased = 1 - Math.pow(1 - p, 4);
      lpArcSet(from + (to - from) * eased);
      if (p < 1) requestAnimationFrame(frame);
      else { lpArcSet(to); if (done) done(); }
    })(t0);
  }

  /* ── Landing Moves: demo lightbox (open/close/focus/Escape) ── */
  const lpBox = document.getElementById('demo-lightbox-slot');
  let lpLastFocus = null;
  function lpOpenBox() {
    if (!lpBox) return;
    lpLastFocus = document.activeElement;
    if (lpLensOn) {
      // Iris open: green lens fully closed, card mounted beneath, lens opens.
      lpArcSet(1);
      lpBox.classList.add('lp-open');
      document.body.style.overflow = 'hidden';
      lpArc(1, 0, 420);
    } else {
      lpBox.classList.add('lp-open');
      document.body.style.overflow = 'hidden';
    }
    const close = lpBox.querySelector('.lp-lightbox-close');
    if (close) close.focus();
  }
  function lpCloseBox() {
    if (!lpBox) return;
    const finish = () => {
      lpBox.classList.remove('lp-open');
      document.body.style.overflow = '';
      // Pause any media in the slot (video loops and the audio player).
      lpBox.querySelectorAll('video, audio').forEach((m) => {
        try { m.pause(); } catch (_) { /* no media source yet */ }
      });
      if (lpLastFocus && lpLastFocus.focus) lpLastFocus.focus();
    };
    if (lpLensOn) {
      // Close is ~2.5x faster than open; the asymmetry reads as deliberate.
      lpArc(0, 1, 170, () => { finish(); lpArc(1, 0, 170); });
    } else {
      finish();
    }
  }

  /* ── Iter2 Move 4: karaoke transcript ────────────────────────────────
     Honest until a real sample exists. The player is an empty slot (no src,
     preload=none), so timeupdate never fires and nothing is faked. When a
     recording is published, generate the map server-side from the TTS
     character-level timestamps and assign it to lpTimes; this same code then
     highlights word-by-word, driven purely by the audio element (no timers,
     no rAF, no drift). lpTimes stays null until then, so only the static,
     clearly-labelled illustrative text renders. */
  const lpTranscript = document.querySelector('[data-transcript]');
  const lpAudioEl = lpBox ? lpBox.querySelector('.lp-lightbox-audio') : null;
  const lpTimes = null; // { chars: [...], times: [[start, end], ...], duration: n }
  if (lpTranscript && lpAudioEl && lpTimes &&
      Array.isArray(lpTimes.chars) && Array.isArray(lpTimes.times)) {
    const words = [];
    let cur = null;
    const frag = document.createDocumentFragment();
    lpTimes.chars.forEach((c, i) => {
      if (/\s/.test(c)) { cur = null; return; }
      if (!cur) {
        cur = { el: document.createElement('span'), start: (lpTimes.times[i] && lpTimes.times[i][0]) || 0 };
        cur.el.className = 'lp-t-word';
        frag.appendChild(cur.el);
        frag.appendChild(document.createTextNode(' '));
        words.push(cur);
      }
      cur.el.textContent += c;
    });
    const body = lpTranscript.querySelector('.lp-transcript-body');
    if (body) {
      body.textContent = '';
      body.appendChild(frag);
      lpTranscript.setAttribute('aria-disabled', 'false');
      lpAudioEl.addEventListener('timeupdate', () => {
        const t = lpAudioEl.currentTime;
        for (let i = 0; i < words.length; i++) {
          const on = t >= words[i].start && (i === words.length - 1 || t < words[i + 1].start);
          words[i].el.classList.toggle('lp-t-on', on);
        }
      });
    }
  }

  document.querySelectorAll('[data-open-demo]').forEach(btn => {
    btn.addEventListener('click', (ev) => { ev.preventDefault(); lpOpenBox(); });
  });
  if (lpBox) {
    lpBox.querySelector('.lp-lightbox-backdrop').addEventListener('click', lpCloseBox);
    lpBox.querySelector('.lp-lightbox-close').addEventListener('click', lpCloseBox);
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && lpBox.classList.contains('lp-open')) lpCloseBox();
    });
  }

  /* ── Landing Moves: reduced motion — never autoplay ambient loops ── */
  if (reduceMotion) {
    document.querySelectorAll('.lp-hero-orb-video, .lp-manifesto-bg, .lp-lightbox-video video').forEach((v) => {
      v.autoplay = false;
      v.removeAttribute('autoplay');
      try { v.pause(); } catch (_) { /* no source yet */ }
    });
  }

});

/* ── Footer: dynamic copyright year (spans keep baked-in year as no-JS fallback) ── */
document.querySelectorAll('.js-year').forEach((el) => {
  el.textContent = String(new Date().getFullYear());
});
