/* Small enhancements for the app shell. Plain JS, no dependencies.
   Without JavaScript every page still works: tabs show their first pane, sheets are not used,
   and a flash message simply stays on screen. */
(function () {
  function all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  // Segmented tabs: <div class="seg" data-tabs><button data-t="a">..</button></div> and panes with data-pane="a".
  document.addEventListener('click', function (e) {
    var tab = e.target.closest('[data-tabs] button');
    if (tab) {
      var screen = tab.closest('.screen') || document;
      all('button', tab.parentNode).forEach(function (b) { b.setAttribute('aria-selected', b === tab ? 'true' : 'false'); });
      all('[data-pane]', screen).forEach(function (p) { p.hidden = p.dataset.pane !== tab.dataset.t; });
      all('[data-bar]', screen).forEach(function (b) { b.hidden = b.dataset.bar.split(' ').indexOf(tab.dataset.t) < 0; });   // a pinned bar per tab
      return;
    }
    // Bottom sheets: a button with data-sheet="id" opens .sheet-backdrop#id; data-close or a tap outside closes it.
    var opener = e.target.closest('[data-sheet]');
    if (opener) {
      var sheet = document.getElementById(opener.dataset.sheet);
      if (sheet) sheet.classList.add('open');
      return;
    }
    var backdrop = e.target.closest('.sheet-backdrop');
    if (e.target.closest('[data-close]') || (backdrop && e.target === backdrop)) {
      all('.sheet-backdrop.open').forEach(function (s) { s.classList.remove('open'); });
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { all('.sheet-backdrop.open').forEach(function (s) { s.classList.remove('open'); }); }
  });

  // Every toast (coming soon, saved, errors) sits centered just above the pinned button bar, never over the buttons.
  // The bar's height differs from page to page, so measure it. With no bar on screen the CSS default applies.
  function placeToast(note) {
    var main = document.querySelector('.main');
    var bars = all('.actionbar').filter(function (b) { return b.offsetParent !== null; });
    note.style.bottom = '';
    if (!main || !bars.length) { return; }
    // The pinned bar is the lowest one on screen (a wide Inbox also has buttons inside its preview card).
    var lowest = bars.reduce(function (a, b) { return b.getBoundingClientRect().bottom > a.getBoundingClientRect().bottom ? b : a; });
    note.style.bottom = Math.round(main.getBoundingClientRect().bottom - lowest.getBoundingClientRect().top + 8) + 'px';
  }

  // "Coming soon": a control that is in the design but has no feature behind it. <button data-soon="Notifications">
  // shows a short message instead of doing nothing.
  var soonTimer;
  document.addEventListener('click', function (e) {
    var soon = e.target.closest('[data-soon]');
    if (!soon) { return; }
    e.preventDefault();
    var note = document.getElementById('soon-toast');
    if (!note) {
      note = document.createElement('div');
      note.id = 'soon-toast';
      note.className = 'toast';
      note.setAttribute('role', 'status');
      document.querySelector('.main').appendChild(note);
    }
    note.textContent = soon.dataset.soon + ' is coming soon.';
    note.hidden = false;
    placeToast(note);
    clearTimeout(soonTimer);
    soonTimer = setTimeout(function () { note.hidden = true; }, 4000);
  });

  // ?tab=chat opens the tab whose button has data-tab="chat" (used after sending a chat message).
  var wantTab = new URLSearchParams(location.search).get('tab');
  if (wantTab) {
    all('[data-tabs] [data-tab]').forEach(function (b) { if (b.dataset.tab === wantTab) { b.click(); } });
  }

  // Proposal wizard (new and edit): the steps are panes inside one form. Back and Next move between them, Next checks the
  // fields on the current step first, and the last step swaps Next for the real Send button. Without JavaScript every
  // pane is shown (see the <noscript> rule in deal_form.html) and the form still posts once.
  var wiz = document.querySelector('[data-wizard]');
  if (wiz) {
    var panes = all('[data-step]', wiz), total = panes.length, current = 1;
    var prevBtn = wiz.querySelector('[data-prev]'), nextBtn = wiz.querySelector('[data-next]'), sendBtn = wiz.querySelector('[data-send]');
    var shortDate = function (iso) {
      var d = new Date(iso + 'T00:00:00');
      return isNaN(d) ? iso : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
    };
    var fillReview = function () {
      all('[data-review]', wiz).forEach(function (el) {
        var f = document.getElementById(el.dataset.review);
        el.textContent = f ? f.value + (el.dataset.suffix || '') : '';
      });
      var d = wiz.querySelector('[data-review-dates]');
      if (d) { d.textContent = shortDate(document.getElementById('id_start_date').value) + ' \u2013 ' + shortDate(document.getElementById('id_end_date').value); }
    };
    // Fairness card on the review step: the server does the math (deals/fairness.py). A failure never blocks Send.
    var fair = wiz.querySelector('[data-fairness]');
    var fairPart = function (name) { return fair.querySelector('[data-fair-' + name + ']'); };
    var fillFairness = function () {
      if (!fair) { return; }
      var val = function (id) { return document.getElementById(id).value; };
      var failed = function () {
        fairPart('label').hidden = fairPart('blockers').hidden = true;
        fairPart('profits').textContent = '';
        fairPart('text').textContent = 'Could not estimate fairness';
      };
      var body = new URLSearchParams({discount_percent: val('id_discount_percent'), cap: val('id_redemption_cap'),
                                      start_date: val('id_start_date'), end_date: val('id_end_date')});
      var csrf = document.querySelector('#deal-form [name=csrfmiddlewaretoken]').value;
      fetch(fair.dataset.fairness, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: body})
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (d) {
          var label = fairPart('label'), profits = fairPart('profits'), blockers = fairPart('blockers');
          label.textContent = d.label;
          label.className = 'badge ' + (d.label === 'balanced' ? 'ok' : d.label === 'lopsided' ? 'warn' : 'bad');
          label.hidden = false;
          profits.textContent = '';
          [d.a, d.b].forEach(function (s) {
            var dt = document.createElement('dt'), dd = document.createElement('dd');
            dt.textContent = s.name; dd.textContent = '$' + s.profit;
            profits.appendChild(dt); profits.appendChild(dd);
          });
          fairPart('text').textContent = d.explanation + (d.note ? ' ' + d.note : '');
          blockers.textContent = d.blockers.join('. ');
          blockers.hidden = !d.blockers.length;
          fairPart('assumed').hidden = !d.margin_assumed;
        })
        .catch(failed);
    };
    ['id_discount_percent', 'id_redemption_cap', 'id_start_date', 'id_end_date'].forEach(function (id) {
      var f = document.getElementById(id);
      if (f) { f.addEventListener('change', fillFairness); }
    });
    var setStep = function (n) {
      current = Math.max(1, Math.min(total, n));
      panes.forEach(function (p) { p.hidden = Number(p.dataset.step) !== current; });
      all('.stepper .step', wiz).forEach(function (st, i) {
        var k = i + 1, num = st.querySelector('.n');
        st.classList.toggle('done', k < current);
        st.classList.toggle('on', k === current);
        if (num) { num.innerHTML = k < current ? '<svg class="i sm" aria-hidden="true"><use href="#i-check"/></svg>' : String(k); }
      });
      prevBtn.hidden = current === 1;
      nextBtn.hidden = current === total;
      sendBtn.hidden = current !== total;
      if (current === total) { fillReview(); fillFairness(); }
      var pane = panes[current - 1], heading = pane.querySelector('h1');
      pane.scrollTop = 0;
      if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
    };
    prevBtn.addEventListener('click', function () { setStep(current - 1); });
    nextBtn.addEventListener('click', function () {
      var bad = all('input, textarea, select', panes[current - 1]).filter(function (el) { return !el.checkValidity(); })[0];
      if (bad) { bad.reportValidity(); return; }
      setStep(current + 1);
    });
    setStep(Number(wiz.dataset.start) || 1);
  }

  // Counter-offer: each row of the diff shows their value, struck through, and yours once you change the field.
  var diffRows = all('.diff .d');
  if (diffRows.length) {
    var shortDay = function (iso) {
      var d = new Date(iso + 'T00:00:00');
      return isNaN(d) ? iso : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
    };
    var paint = function (row, oldText, newText) {
      var label = row.firstElementChild.cloneNode(true);
      row.textContent = '';
      row.appendChild(label);
      row.classList.toggle('changed', oldText !== newText);
      if (oldText === newText) {
        var same = document.createElement('span'), tag = document.createElement('span');
        same.textContent = oldText; tag.textContent = 'same';
        row.appendChild(same); row.appendChild(tag);
      } else {
        var del = document.createElement('del'), ins = document.createElement('ins');
        del.textContent = oldText; ins.textContent = newText;
        row.appendChild(del); row.appendChild(ins);
      }
    };
    var refresh = function () {
      diffRows.forEach(function (row) {
        if (row.hasAttribute('data-diff-dates')) {
          var o = row.dataset.orig.split('|');
          var start = document.getElementById('id_start_date').value, end = document.getElementById('id_end_date').value;
          paint(row, shortDay(o[0]) + ' \u2013 ' + shortDay(o[1]), shortDay(start) + ' \u2013 ' + shortDay(end));
        } else {
          var f = document.getElementById(row.dataset.diff), suffix = row.dataset.suffix || '';
          paint(row, row.dataset.orig + suffix, f.value + suffix);
        }
      });
    };
    var dealFormEl = document.getElementById('deal-form');
    if (dealFormEl) { dealFormEl.addEventListener('input', refresh); refresh(); }
  }

  // Toast from Django messages: hides after 5 seconds, or on tap. Errors stay until tapped.
  var toast = document.querySelector('[data-toast]');
  if (toast) {
    placeToast(toast);
    toast.addEventListener('click', function () { toast.hidden = true; });
    if (!toast.hasAttribute('data-keep')) setTimeout(function () { toast.hidden = true; }, 5000);
  }

  // Shared by the two AI buttons: POST, read the JSON reply, report a failure in plain words.
  function postJson(url, csrf, body) {
    return fetch(url, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: body})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, data: d}; }); });
  }

  // Loading and error states for the AI buttons: a spinner while waiting, bold red text when it failed.
  function setStatus(el, text, state) {
    el.textContent = text;
    el.classList.toggle('busy', state === 'busy');
    el.classList.toggle('failed', state === 'failed');
  }

  // Offline: no service worker yet, so this only says so and hides again when the connection returns.
  var offlineNote = document.getElementById('offline-note');
  if (offlineNote) {
    var showOffline = function () { offlineNote.hidden = navigator.onLine; };
    window.addEventListener('online', showOffline);
    window.addEventListener('offline', showOffline);
    showOffline();
  }

  // "Draft with AI" on the new-deal form.
  var draftButton = document.getElementById('ai-draft');
  if (draftButton) {
    var draftStatus = document.getElementById('ai-status');
    var dealForm = document.getElementById('deal-form');
    draftButton.addEventListener('click', function () {
      setStatus(draftStatus, 'Drafting...', 'busy');
      var csrf = dealForm.querySelector('[name=csrfmiddlewaretoken]').value;
      postJson(draftButton.dataset.url, csrf, new URLSearchParams({recipient_id: draftButton.dataset.recipient}))
        .then(function (res) {
          if (!res.ok) { setStatus(draftStatus, res.data.error || 'Could not draft.', 'failed'); return; }
          var terms = res.data.terms;
          Object.keys(terms).forEach(function (key) {
            var el = document.getElementById('id_' + key);
            if (el) { el.value = terms[key]; }
          });
          document.getElementById('id_message').value = res.data.message;
          var src = (res.data.sources && res.data.sources.length) ? ' Grounded in playbook: ' + res.data.sources.join(', ') + '.' : '';
          setStatus(draftStatus, res.data.source === 'ai'
            ? 'Draft filled in.' + src + ' Review and edit before sending.'
            : 'Starting terms filled in (' + res.data.reason + '). Review before sending.');
        })
        .catch(function () { setStatus(draftStatus, 'Could not draft. Try again.', 'failed'); });
    });
  }

  // "Explain this deal" on the summary page.
  var coachButton = document.getElementById('coach-btn');
  if (coachButton) {
    var coachStatus = document.getElementById('coach-status');
    coachButton.addEventListener('click', function () {
      setStatus(coachStatus, 'Thinking...', 'busy');
      postJson(coachButton.dataset.url, coachButton.dataset.csrf)
        .then(function (res) {
          if (!res.ok) { setStatus(coachStatus, res.data.error || 'Could not explain.', 'failed'); return; }
          setStatus(coachStatus, '');
          document.getElementById('coach-text').textContent = res.data.explanation;
          document.getElementById('coach-source').textContent = res.data.source === 'ai'
            ? 'Written by AI from numbers the app computed. Numbers were checked.'
            : 'Built-in explanation (' + res.data.reason + ')';
          document.getElementById('coach-out').hidden = false;
        })
        .catch(function () { setStatus(coachStatus, 'Could not explain. Try again.', 'failed'); });
    });
  }

  // Copy link: <button data-copy="https://..." data-copy-status="id">. If the browser will not let the page use the
  // clipboard (some browsers on plain http), show the link selected in <input id="..." data-copy-fallback> instead.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) { return; }
    var status = document.getElementById(btn.dataset.copyStatus);
    var fallback = document.querySelector('[data-copy-fallback]');
    function done() { if (status) { status.textContent = 'Link copied.'; } }
    function manual() {
      if (fallback) {
        fallback.hidden = false;
        fallback.closest('.qr-page').classList.add('qr-manual');
        fallback.focus(); fallback.select();
      }
      if (status) { status.textContent = 'Press and hold the link to copy it.'; }
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(btn.dataset.copy).then(done, manual);
    } else { manual(); }
  });

  // Print button: <button data-print>.
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-print]')) { window.print(); }
  });

  // Counter card preview: shrink it to fit the screen so the page does not scroll. Printing is never shrunk (card.css).
  function fitCard() {
    var sheet = document.querySelector('.card-sheet');
    var area = sheet && sheet.closest('.scroll');
    if (!area) { return; }
    sheet.style.zoom = 1;
    var style = getComputedStyle(area);
    var room = area.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    if (sheet.offsetHeight > room) { sheet.style.zoom = Math.max(0.5, room / sheet.offsetHeight); }
  }
  window.addEventListener('load', fitCard);
  window.addEventListener('resize', fitCard);
})();
