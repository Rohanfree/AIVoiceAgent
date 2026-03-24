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

});
