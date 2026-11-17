/* Behavior for the design reference pages (shell-demo.html, public-demo.html).
   Plain JS, no dependencies. In the real app this maps to: links (data-go), htmx or small
   fetch handlers (tabs, sheets), and a Django form wizard or one view per step (data-wizard).
   Exposed as window.SM so design/check_design.py can visit every screen, tab, step and sheet. */
(function () {
  var toastTimer;
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function show(name, opts) {
    var target = null;
    $all('.screen').forEach(function (s) {
      var on = s.id === 's-' + name;
      s.classList.toggle('active', on);
      if (on) target = s;
    });
    if (!target) return;
    var nav = target.dataset.nav || name;
    $all('.nav-item').forEach(function (n) {
      if (n.dataset.go === nav) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current');
    });
    $all('.sheet-backdrop').forEach(function (s) { s.classList.remove('open'); });
    if (target.hasAttribute('data-wizard')) setStep(target, (opts && opts.step) || 1);
    var first = target.querySelector('[data-tabs] button');
    if (first && !(opts && opts.keepTab)) selectTab(first);
  }

  function selectTab(btn) {
    var seg = btn.parentNode, scr = seg.closest('.screen');
    $all('button', seg).forEach(function (b) { b.setAttribute('aria-selected', b === btn ? 'true' : 'false'); });
    $all('[data-pane]', scr).forEach(function (p) { p.hidden = p.dataset.pane !== btn.dataset.t; });
    $all('[data-bar]', scr).forEach(function (b) { b.hidden = b.dataset.bar.split(' ').indexOf(btn.dataset.t) < 0; });
  }

  function setStep(scr, n) {
    var panes = $all('[data-step]', scr), total = panes.length;
    n = Math.max(1, Math.min(total, n));
    scr.dataset.current = n;
    panes.forEach(function (p) { p.hidden = Number(p.dataset.step) !== n; });
    $all('.stepper .step', scr).forEach(function (st, i) {
      var k = i + 1;
      st.classList.toggle('done', k < n);
      st.classList.toggle('on', k === n);
      var num = st.querySelector('.n'); if (num) num.textContent = k < n ? '✓' : String(k);
    });
    var prev = scr.querySelector('[data-prev]'), next = scr.querySelector('[data-next]');
    if (prev) prev.hidden = n === 1;
    if (next) next.textContent = n === total ? (next.dataset.last || 'Finish') : (next.dataset.label || 'Next');
  }

  function toast(msg) {
    var scr = document.querySelector('.screen.active') || document.body;
    var t = document.getElementById('toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.querySelector('.main').appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 2600);
  }

  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-next]');
    if (el) {
      var scr = el.closest('.screen'), cur = Number(scr.dataset.current || 1), total = $all('[data-step]', scr).length;
      if (cur >= total) { if (scr.dataset.done) show(scr.dataset.done); } else setStep(scr, cur + 1);
      return;
    }
    el = e.target.closest('[data-prev]');
    if (el) { var s2 = el.closest('.screen'); setStep(s2, Number(s2.dataset.current || 1) - 1); return; }
    el = e.target.closest('[data-go]');
    if (el) { show(el.dataset.go); if (el.dataset.toast) toast(el.dataset.toast); return; }
    el = e.target.closest('[data-tabs] button');
    if (el) { selectTab(el); return; }
    el = e.target.closest('[data-chips] .chip');
    if (el) { var grp = el.parentNode; $all('.chip', grp).forEach(function (c) { c.setAttribute('aria-pressed', c === el ? 'true' : 'false'); }); return; }
    el = e.target.closest('[data-multi] .chip');
    if (el) { el.setAttribute('aria-pressed', el.getAttribute('aria-pressed') === 'true' ? 'false' : 'true'); return; }
    el = e.target.closest('[data-sheet]');
    if (el) { document.getElementById(el.dataset.sheet).classList.add('open'); return; }
    if (e.target.closest('[data-close]') || e.target.classList.contains('sheet-backdrop')) {
      $all('.sheet-backdrop').forEach(function (s) { s.classList.remove('open'); });
      return;
    }
    el = e.target.closest('[data-toast]');
    if (el) { toast(el.dataset.toast); $all('.sheet-backdrop').forEach(function (s) { s.classList.remove('open'); }); }
  });

  window.SM = { show: show, selectTab: selectTab, setStep: setStep, toast: toast };
  var q = new URLSearchParams(location.search);
  show(q.get('screen') || location.hash.slice(1) || document.body.dataset.start || 'inbox', { step: Number(q.get('step')) || 1 });
})();
