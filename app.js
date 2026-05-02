(function () {
  'use strict';

  /* ── Initial data from data.js ─────────────────────── */
  let state = window.__YT_DATA__;
  if (!state) return;

  /* ── Formatters ────────────────────────────────────── */

  function fmtSubs(n) {
    return n.toLocaleString('ja-JP');
  }

  function fmtViews(n) {
    if (n >= 100000000) return (n / 100000000).toFixed(1) + '億';
    if (n >= 10000)     return (n / 10000).toFixed(1) + '万';
    return n.toLocaleString('ja-JP');
  }

  function relAge(isoStr) {
    const days = Math.floor((Date.now() - new Date(isoStr)) / 86400000);
    if (days === 0) return 'today';
    if (days === 1) return '1 day ago';
    if (days <  7)  return days + ' days ago';
    const w = Math.floor(days / 7);
    return w === 1 ? '1 week ago' : w + ' weeks ago';
  }

  /* ── Count-up animation ────────────────────────────── */

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function countUp(el, from, to, duration) {
    const start = performance.now();
    function tick(now) {
      const t = Math.min((now - start) / duration, 1);
      el.textContent = fmtSubs(Math.round(from + (to - from) * easeOutCubic(t)));
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ── Delta display ─────────────────────────────────── */

  const deltaEl = document.getElementById('subDelta');

  function renderDelta(current, previous) {
    const d = current - previous;
    if (d > 0) {
      deltaEl.textContent = '▲ +' + d.toLocaleString('ja-JP');
      deltaEl.className = 'sub-delta delta--up';
    } else if (d < 0) {
      deltaEl.textContent = '▼ ' + Math.abs(d).toLocaleString('ja-JP');
      deltaEl.className = 'sub-delta delta--down';
    } else {
      deltaEl.textContent = '— no change';
      deltaEl.className = 'sub-delta';
    }
  }

  /* ── Video grid ────────────────────────────────────── */

  const grid = document.getElementById('videoGrid');

  function renderVideos(videos) {
    grid.innerHTML = '';
    (videos || []).slice(0, 3).forEach(function (video) {
      const card = document.createElement('div');
      card.className = 'video-card';

      const thumbWrap = document.createElement('div');
      thumbWrap.className = 'video-thumb-wrap';

      const img = document.createElement('img');
      img.className = 'video-thumb loading';
      img.alt = '';
      img.src = video.thumbnail || ('https://i.ytimg.com/vi/' + video.id + '/maxresdefault.jpg');
      img.addEventListener('load',  function () { img.classList.remove('loading'); });
      img.addEventListener('error', function () {
        img.src = 'https://i.ytimg.com/vi/' + video.id + '/hqdefault.jpg';
      });

      const overlay = document.createElement('div');
      overlay.className = 'video-thumb-overlay';

      thumbWrap.appendChild(img);
      thumbWrap.appendChild(overlay);

      const viewsWrap = document.createElement('div');
      viewsWrap.className = 'video-views-wrap';

      const views = document.createElement('div');
      views.className = 'video-views';
      views.textContent = fmtViews(video.views || 0);

      const views24h = document.createElement('div');
      views24h.className = 'video-views-sub';
      const v24 = video.views_24h;
      if (v24 == null) {
        views24h.textContent = '— / 24h';
      } else if (v24 > 0) {
        views24h.textContent = '+' + fmtViews(v24) + ' / 24h';
      } else {
        views24h.textContent = '0 / 24h';
      }

      viewsWrap.appendChild(views);
      viewsWrap.appendChild(views24h);

      const title = document.createElement('div');
      title.className = 'video-title';
      title.textContent = video.title || '';

      const age = document.createElement('div');
      age.className = 'video-age';
      age.textContent = video.published_at ? relAge(video.published_at) : '';

      card.appendChild(thumbWrap);
      card.appendChild(viewsWrap);
      card.appendChild(title);
      card.appendChild(age);
      grid.appendChild(card);
    });
  }

  /* ── Sparkline ─────────────────────────────────────── */

  const sparkLineEl   = document.getElementById('sparkLine');
  const sparkFillEl   = document.getElementById('sparkFill');
  const updatedAtEl   = document.getElementById('updatedAt');
  const flashEl       = document.getElementById('flashOverlay');
  const redLineEl     = document.querySelector('.red-line');

  function flashScreen() {
    if (!flashEl) return;
    flashEl.classList.remove('flash--active');
    void flashEl.offsetWidth;
    flashEl.classList.add('flash--active');
  }

  function renderSparkline(history) {
    if (!history || history.length < 2) return;
    const W = 200, H = 40, pad = 2;
    const vals = history.map(function (p) { return p.n; });
    const min = Math.min.apply(null, vals);
    const max = Math.max.apply(null, vals);
    const range = max - min || 1;
    function px(i) { return pad + (i / (vals.length - 1)) * (W - pad * 2); }
    function py(v) { return H - pad - ((v - min) / range) * (H - pad * 2); }
    const pts = vals.map(function (v, i) { return px(i) + ',' + py(v); }).join(' ');
    sparkLineEl.setAttribute('points', pts);
    const first = px(0) + ',' + py(vals[0]);
    const last  = px(vals.length - 1) + ',' + py(vals[vals.length - 1]);
    sparkFillEl.setAttribute('d',
      'M ' + first + ' L ' + pts.split(' ').join(' L ') +
      ' L ' + px(vals.length - 1) + ',' + (H - pad) +
      ' L ' + px(0) + ',' + (H - pad) + ' Z'
    );
  }

  function renderUpdatedAt(value) {
    if (!value || !updatedAtEl) return;
    const date = value instanceof Date ? value : new Date(value);
    updatedAtEl.textContent = 'UPDATED ' + date.toLocaleTimeString('ja-JP', {
      timeZone: 'Asia/Tokyo', hour: '2-digit', minute: '2-digit', hour12: false,
    });
  }

  /* ── Subscriber section ────────────────────────────── */

  const subEl  = document.getElementById('subCount');
  let displayedCount = state.subscribers.previous || state.subscribers.current;

  subEl.textContent = fmtSubs(displayedCount);
  countUp(subEl, displayedCount, state.subscribers.current, 800);
  displayedCount = state.subscribers.current;
  renderDelta(state.subscribers.current, state.subscribers.previous || state.subscribers.current);
  renderSparkline(state.history);
  renderUpdatedAt(state.subscribers.updated_at);

  /* ── Initial video render ──────────────────────────── */
  renderVideos(state.videos);

  /* ── Live time ─────────────────────────────────────── */

  const liveTimeEl = document.getElementById('liveTime');
  function updateTime() {
    liveTimeEl.textContent = new Date().toLocaleTimeString('ja-JP', {
      timeZone: 'Asia/Tokyo',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  }
  updateTime();
  setInterval(updateTime, 1000);

  /* ── Chime ─────────────────────────────────────────── */

  var audioCtx = null;

  function unlockAudio() {
    if (audioCtx) return;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {}
  }

  // Unlock on first user interaction
  document.addEventListener('click',    unlockAudio, { once: false });
  document.addEventListener('keydown',  unlockAudio, { once: false });
  document.addEventListener('touchend', unlockAudio, { once: false });

  function playChime() {
    if (!audioCtx) return;
    try {
      if (audioCtx.state === 'suspended') audioCtx.resume();
      const notes = [880, 1108, 1320];
      notes.forEach(function (freq, i) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = 'sine';
        osc.frequency.value = freq;
        const t = audioCtx.currentTime + i * 0.2;
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.22, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.9);
        osc.start(t);
        osc.stop(t + 0.9);
      });
    } catch (e) {}
  }

  /* ── Async polling — fetch data.json every 60 s ────── */

  function fetchAndUpdate() {
    if (updatedAtEl) {
      updatedAtEl.classList.remove('updated-at--polling');
      void updatedAtEl.offsetWidth;
      updatedAtEl.classList.add('updated-at--polling');
    }
    if (redLineEl) {
      redLineEl.classList.remove('red-line--pulse');
      void redLineEl.offsetWidth;
      redLineEl.classList.add('red-line--pulse');
    }
    const startedAt = Date.now();
    function stopGlow() {
      const wait = Math.max(0, 2600 - (Date.now() - startedAt));
      setTimeout(function () {
        if (updatedAtEl) updatedAtEl.classList.remove('updated-at--polling');
        if (redLineEl)   redLineEl.classList.remove('red-line--pulse');
      }, wait);
    }

    fetch('./data.json?t=' + Date.now())
      .then(function (r) { return r.json(); })
      .then(function (newData) {
        const newCount = newData.subscribers.current;
        scanEffect();
        const oldUpdatedAt = state.subscribers && state.subscribers.updated_at;
        const newUpdatedAt = newData.subscribers && newData.subscribers.updated_at;

        // Animate subscriber count if changed
        if (newCount !== displayedCount) {
          if (newCount > displayedCount) playChime();
          countUp(subEl, displayedCount, newCount, 1200);
          renderDelta(newCount, displayedCount);
          displayedCount = newCount;
        }

        // Re-render video grid if IDs or views changed
        const oldSig = (state.videos || []).map(function (v) { return v.id + ':' + v.views; }).join('|');
        const newSig = (newData.videos || []).map(function (v) { return v.id + ':' + v.views; }).join('|');
        if (newSig !== oldSig) {
          renderVideos(newData.videos);
        }

        renderSparkline(newData.history);
        renderUpdatedAt(new Date());

        // Kirari flash when upstream data refreshed (updated_at changed)
        if (oldUpdatedAt && newUpdatedAt && oldUpdatedAt !== newUpdatedAt) {
          flashScreen();
        }
        state = newData;
      })
      .catch(function () { /* silent — keep showing last known data */ })
      .then(stopGlow, stopGlow);
  }

  setInterval(fetchAndUpdate, 60000);

  /* ── Test helper (call window.__sim(+10) in console) ── */
  window.__sim = function (delta) {
    delta = delta || 1;
    const from = displayedCount;
    const to   = from + delta;
    unlockAudio();
    if (delta > 0) playChime();
    countUp(subEl, from, to, 1200);
    renderDelta(to, from);
    displayedCount = to;
  };
  window.__flash = flashScreen;

  /* ── Scan effect on data fetch ─────────────────────── */

  function scanEffect() {
    const el = document.createElement('div');
    el.style.cssText = `
      position: fixed; top: 0; left: -100%; width: 60%; height: 200%;
      background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.03) 45%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.03) 55%, transparent 60%);
      pointer-events: none; z-index: 9999;
      animation: scanAnim 1.2s ease-in-out forwards;
    `;
    document.body.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
  }

  /* ── Re-poll on tab focus ──────────────────────────── */

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      fetchAndUpdate();
    }
  });

})();
