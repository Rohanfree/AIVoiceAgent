/* landing-moves.js — preview-only interactions. No prod coupling. */
(function () {
  "use strict";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Scroll reveals: IntersectionObserver, transform + opacity only. */
  var revealEls = document.querySelectorAll(".mv-reveal");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) { el.classList.add("mv-in"); });
  } else {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("mv-in"); ro.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    revealEls.forEach(function (el) { ro.observe(el); });
  }

  /* Metric ledger count-up on first viewport enter. */
  function fmt(value, decimals, suffix) {
    if (decimals === 0) {
      return Math.round(value).toLocaleString("en-US") + suffix;
    }
    return value.toFixed(decimals) + suffix;
  }
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var suffix = el.getAttribute("data-suffix") || "";
    if (reduceMotion) {
      el.textContent = fmt(target, decimals, suffix);
      return;
    }
    var dur = 1400;
    var t0 = null;
    function frame(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased, decimals, suffix);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  var nums = document.querySelectorAll(".mv-ledger-num[data-count]");
  if (!("IntersectionObserver" in window)) {
    nums.forEach(countUp);
  } else {
    var no = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { countUp(e.target); no.unobserve(e.target); }
      });
    }, { threshold: 0.4 });
    nums.forEach(function (el) { no.observe(el); });
  }

  /* Manifesto word reveal: staggered by word index once in view. */
  var words = document.querySelectorAll(".mv-manifesto .mv-w");
  function revealWords() {
    words.forEach(function (w, i) {
      setTimeout(function () { w.classList.add("mv-on"); }, reduceMotion ? 0 : i * 90);
    });
  }
  var man = document.querySelector(".mv-manifesto");
  if (man) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      words.forEach(function (w) { w.classList.add("mv-on"); });
    } else {
      var mo = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { revealWords(); mo.disconnect(); }
        });
      }, { threshold: 0.35 });
      mo.observe(man);
    }
  }

  /* Demo lightbox: open, close, focus return, Escape. */
  var box = document.getElementById("demo-lightbox-slot");
  var lastFocus = null;
  function openBox() {
    if (!box) return;
    lastFocus = document.activeElement;
    box.classList.add("mv-open");
    document.body.style.overflow = "hidden";
    var close = box.querySelector(".mv-lightbox-close");
    if (close) close.focus();
  }
  function closeBox() {
    if (!box) return;
    box.classList.remove("mv-open");
    document.body.style.overflow = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.querySelectorAll("[data-open-demo]").forEach(function (btn) {
    btn.addEventListener("click", function (ev) { ev.preventDefault(); openBox(); });
  });
  if (box) {
    box.querySelector(".mv-lightbox-backdrop").addEventListener("click", closeBox);
    box.querySelector(".mv-lightbox-close").addEventListener("click", closeBox);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && box.classList.contains("mv-open")) closeBox();
    });
  }
})();
