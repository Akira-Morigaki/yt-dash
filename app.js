(function () {
  'use strict';

  const data = window.__YT_DATA__;
  if (!data) {
    setTimeout(() => location.reload(), 5000);
    return;
  }

  /* ── Formatters ────────────────────────────────────────── */

  function fmtSubs(n) {
    return n.toLocaleString('ja-JP');
  }

  function fmtViews(n) {
    if (n >= 100000000) return (n / 100000000).toFixed(1).replace(/\.0$/, '') + '億';
    if (n >= 10000)     return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    if (n >= 1000)      return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    return n.toLocaleString('ja-JP');
  }

  function relAge(isoStr) {
    const pub  = new Date(isoStr);
    const now  = new Date();
    const days = Math.floor((now - pub) / 86400000);
    if (days === 0) return 'today';
    if (days === 1) return '1 day ago';
    if (days <  7)  return days + ' days ago';
    const w = Math.floor(days / 7);
    return w === 1 ? '1 week ago' : w + ' weeks ago';
  }

  /* ── Count-up animation ────────────────────────────────── */

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

  /* ── Subscriber section ────────────────────────────────── */

  const sub     = data.subscribers || {};
  const current = sub.current  || 0;
  const prev    = sub.previous || current;
  const subEl   = document.getElementById('subCount');
  const deltaEl = document.getElementById('subDelta');

  countUp(subEl, prev, current, 800);

  const delta = current - prev;
  if (delta > 0) {
    deltaEl.textContent = '▲ +' + delta.toLocaleString('ja-JP') + ' since last update';
    deltaEl.style.color = '#7CB87C';
  } else if (delta < 0) {
    deltaEl.textContent = '▼ ' + Math.abs(delta).toLocaleString('ja-JP') + ' since last update';
    deltaEl.style.color = '#B87C7C';
  } else {
    deltaEl.textContent = 'no change since last update';
  }

  /* ── Video grid ────────────────────────────────────────── */

  const grid = document.getElementById('videoGrid');
  (data.videos || []).slice(0, 3).forEach(function (video) {
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
    thumbWrap.appendChild(img);

    const views = document.createElement('div');
    views.className = 'video-views';
    views.textContent = fmtViews(video.views || 0);

    const title = document.createElement('div');
    title.className = 'video-title';
    title.textContent = video.title || '';

    const age = document.createElement('div');
    age.className = 'video-age';
    age.textContent = video.published_at ? relAge(video.published_at) : '';

    card.appendChild(thumbWrap);
    card.appendChild(views);
    card.appendChild(title);
    card.appendChild(age);
    grid.appendChild(card);
  });

  /* ── Live time ─────────────────────────────────────────── */

  const liveTimeEl = document.getElementById('liveTime');

  function updateTime() {
    liveTimeEl.textContent = new Date().toLocaleTimeString('ja-JP', {
      timeZone: 'Asia/Tokyo',
      hour:     '2-digit',
      minute:   '2-digit',
      hour12:   false,
    }) + ' JST';
  }
  updateTime();
  setInterval(updateTime, 1000);

  /* ── Auto reload every 60 s ─────────────────────────────── */
  setTimeout(function () { location.reload(); }, 60000);
})();
