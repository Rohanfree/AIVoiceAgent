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

  /* ── Landing Moves: demo lightbox (open/close/focus/Escape) ── */
  const lpBox = document.getElementById('demo-lightbox-slot');
  let lpLastFocus = null;
  function lpOpenBox() {
    if (!lpBox) return;
    lpLastFocus = document.activeElement;
    lpBox.classList.add('lp-open');
    document.body.style.overflow = 'hidden';
    const close = lpBox.querySelector('.lp-lightbox-close');
    if (close) close.focus();
  }
  function lpCloseBox() {
    if (!lpBox) return;
    lpBox.classList.remove('lp-open');
    document.body.style.overflow = '';
    // Pause any media in the slot (video loops and the audio player).
    lpBox.querySelectorAll('video, audio').forEach((m) => {
      try { m.pause(); } catch (_) { /* no media source yet */ }
    });
    if (lpLastFocus && lpLastFocus.focus) lpLastFocus.focus();
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
