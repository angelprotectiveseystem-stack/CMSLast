/* ساعت شطرنج برای بازی روی صفحه‌ی واقعی (دو نفر، یک گوشی وسطِ میز)
   • زمان‌سنجی با performance.now (نه شمارنده‌ی تیک) → با افتِ فریم هم دقیق می‌ماند
   • فقط وقتی متنِ نمایشی عوض شده DOM را لمس می‌کند؛ حلقه‌ی رندر فقط هنگامِ اجرا فعال است
   • لمسِ سریع با pointerdown (بدونِ تأخیرِ click)
   • بعد از رفتن به پس‌زمینه یا بستنِ اپ، زمانِ سپری‌شده جبران می‌شود
   قانون: هر بازیکن پس از حرکتش نیمه‌ی خودش را لمس می‌کند؛ ساعتِ حریف شروع می‌شود. */
(function () {
  'use strict';

  var ctx, h, ic, hx, tg, Sheet, toast, LS;
  var K_CFG = 'hub:clock:cfg', K_ST = 'hub:clock:st';
  var PRESETS = [[1, 0], [3, 0], [3, 2], [5, 0], [5, 3], [10, 0], [10, 5], [15, 10], [30, 0]];

  var cfg = { min: 5, inc: 3, sound: true, haptic: true, awake: true };
  var st = { phase: 'idle', t: { top: 0, bot: 0 }, turn: null, last: 0, moves: { top: 0, bot: 0 }, flag: null };
  var els = {}, raf = 0, wake = null, AC = null, warned = { top: false, bot: false };
  var hidWall = 0, hidPerf = 0;

  function other(s) { return s === 'top' ? 'bot' : 'top'; }
  function base() { return cfg.min * 60000; }

  /* ─── قالب‌بندیِ زمان ─────────────────────────────────────── */
  function fmt(ms) {
    if (ms <= 0) return '0:00';
    if (ms < 10000) return (Math.ceil(ms / 100) / 10).toFixed(1);
    var s = Math.ceil(ms / 1000), hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
    var p = ss < 10 ? '0' + ss : ss;
    if (hh) return hh + ':' + (mm < 10 ? '0' + mm : mm) + ':' + p;
    return mm + ':' + p;
  }
  function remain(side, now) {
    if (st.phase === 'run' && st.turn === side) return st.t[side] - (now - st.last);
    return st.t[side];
  }

  /* ─── صدا / لرزش / بیدار ماندنِ صفحه ──────────────────────── */
  function audio() {
    if (!AC) { try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) {} }
    if (AC && AC.state === 'suspended') { try { AC.resume(); } catch (e) {} }
  }
  function beep(freq, dur, vol) {
    if (!cfg.sound || !AC) return;
    try {
      var o = AC.createOscillator(), g = AC.createGain(), t = AC.currentTime;
      o.type = 'square'; o.frequency.value = freq;
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + dur + 0.02);
    } catch (e) {}
  }
  function buzz(kind) {
    if (!cfg.haptic || !tg || !tg.HapticFeedback) return;
    try {
      if (kind === 'tap') tg.HapticFeedback.impactOccurred('rigid');
      else if (kind === 'warn') tg.HapticFeedback.notificationOccurred('warning');
      else if (kind === 'flag') tg.HapticFeedback.notificationOccurred('error');
    } catch (e) {}
  }
  function wakeOn() {
    if (!cfg.awake || wake || !navigator.wakeLock) return;
    navigator.wakeLock.request('screen').then(function (l) { wake = l; l.addEventListener('release', function () { wake = null; }); }).catch(function () {});
  }
  function wakeOff() { if (wake) { try { wake.release(); } catch (e) {} wake = null; } }
  function guard(on) {
    try { if (on) tg.enableClosingConfirmation(); else tg.disableClosingConfirmation(); } catch (e) {}
  }

  /* ─── ذخیره / بازیابی ─────────────────────────────────────── */
  function save() {
    LS.set(K_ST, { phase: st.phase, t: st.t, turn: st.turn, moves: st.moves, flag: st.flag, wall: Date.now(), min: cfg.min, inc: cfg.inc });
  }
  function restore() {
    var s = LS.get(K_ST);
    if (!s || s.min !== cfg.min || s.inc !== cfg.inc || !s.t || s.phase === 'idle') return false;
    st.phase = s.phase; st.t = s.t; st.turn = s.turn; st.moves = s.moves || { top: 0, bot: 0 }; st.flag = s.flag || null;
    if (st.phase === 'run') {
      st.t[st.turn] -= Math.max(0, Date.now() - s.wall);
      st.last = performance.now();
      if (st.t[st.turn] <= 0) { st.t[st.turn] = 0; st.phase = 'over'; st.flag = st.turn; }
    }
    return true;
  }

  /* ─── رندر ───────────────────────────────────────────────── */
  function paintSide(side, ms) {
    var e = els[side], s = fmt(ms);
    if (e.txt !== s) { e.txt = s; e.time.textContent = s; }
    var cls = st.phase === 'over' ? (st.flag === side ? 'flag' : 'lose')
      : (st.phase === 'run' && st.turn === side ? 'live' + (ms < 10000 ? ' crit' : ms < 30000 ? ' warn' : '') : '');
    if (e.cls !== cls) { e.cls = cls; e.box.className = 'half ' + side + (cls ? ' ' + cls : '') + (cfg.min >= 60 ? ' long' : ''); }
    var mv = st.phase === 'idle' ? 'لمس کنید تا ساعتِ حریف شروع شود'
      : st.phase === 'over' ? (st.flag === side ? 'زمان تمام شد' : 'برنده')
      : st.phase === 'pause' ? 'متوقف'
      : (st.moves[side] ? 'حرکت ' + st.moves[side] : '');
    if (e.mv !== mv) { e.mv = mv; e.mvEl.textContent = mv; }
  }
  function paintAll() {
    var now = performance.now();
    paintSide('top', remain('top', now)); paintSide('bot', remain('bot', now));
    els.preset.textContent = cfg.min + '+' + cfg.inc;
    var running = st.phase === 'run';
    els.play.replaceChildren(ic(running ? 'pause' : 'play'));
    els.play.disabled = st.phase === 'over';
    els.play.style.opacity = st.phase === 'over' ? '.4' : '';
    document.body.classList.toggle('clock-live', running);
  }

  function loop() {
    if (st.phase !== 'run') return;
    var now = performance.now(), side = st.turn, rem = st.t[side] - (now - st.last);
    if (rem <= 0) { st.t[side] = 0; return flag(side); }
    if (rem < 10000 && !warned[side]) { warned[side] = true; buzz('warn'); }
    paintSide(side, rem);
    raf = requestAnimationFrame(loop);
  }

  /* ─── منطقِ ساعت ─────────────────────────────────────────── */
  function startRun(turn) {
    st.phase = 'run'; st.turn = turn; st.last = performance.now();
    wakeOn(); guard(true); paintAll(); save();
    cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  }
  function press(side) {
    audio();
    if (st.phase === 'over' || st.phase === 'pause') return;
    if (st.phase === 'idle') {           // اولین لمس: حریفِ لمس‌کننده شروع می‌کند
      buzz('tap'); beep(side === 'top' ? 900 : 700, 0.04, 0.05);
      return startRun(other(side));
    }
    if (st.turn !== side) return;        // لمسِ نیمه‌ی حریف در نوبتِ او بی‌اثر است
    var now = performance.now(), rem = st.t[side] - (now - st.last);
    if (rem <= 0) { st.t[side] = 0; return flag(side); }
    st.t[side] = rem + cfg.inc * 1000;
    st.moves[side]++;
    warned[side] = st.t[side] < 10000;
    buzz('tap'); beep(side === 'top' ? 900 : 700, 0.04, 0.05);
    st.turn = other(side); st.last = now;
    paintAll(); save();
  }
  function flag(side) {
    cancelAnimationFrame(raf);
    st.phase = 'over'; st.flag = side; st.turn = null;
    buzz('flag'); beep(320, 0.7, 0.09);
    wakeOff(); guard(false); paintAll(); save();
  }
  function togglePause() {
    audio();
    if (st.phase === 'run') {
      st.t[st.turn] -= performance.now() - st.last;
      st.phase = 'pause'; cancelAnimationFrame(raf); wakeOff();
      paintAll(); save();
    } else if (st.phase === 'pause') {
      startRun(st.turn);
    } else if (st.phase === 'idle') {
      startRun('bot');
    }
    buzz('tap');
  }
  function reset() {
    cancelAnimationFrame(raf);
    st.phase = 'idle'; st.turn = null; st.flag = null; st.t = { top: base(), bot: base() }; st.moves = { top: 0, bot: 0 };
    warned = { top: false, bot: false };
    els.top.cls = els.bot.cls = null;
    wakeOff(); guard(false); paintAll(); save();
  }

  function askReset() {
    if (st.phase === 'idle' || st.phase === 'over') { reset(); return; }
    if (st.phase === 'run') togglePause();        // هنگامِ پرسش، ساعت متوقف می‌ماند
    var msg = 'بازی جاری پاک و ساعت بازنشانی شود؟';
    if (tg && tg.showConfirm) tg.showConfirm(msg, function (ok) { if (ok) reset(); });
    else if (window.confirm(msg)) reset();
  }

  /* ─── تنظیمات ────────────────────────────────────────────── */
  function openSettings() {
    var draft = { min: cfg.min, inc: cfg.inc };
    var grid = h('div', { class: 'presets' });
    var minOut = h('output', { text: draft.min }), incOut = h('output', { text: draft.inc });
    function syncGrid() {
      grid.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', +b.dataset.m === draft.min && +b.dataset.i === draft.inc); });
      minOut.textContent = draft.min; incOut.textContent = draft.inc;
    }
    PRESETS.forEach(function (p) {
      grid.append(h('button', { type: 'button', 'data-m': p[0], 'data-i': p[1], text: p[0] + '+' + p[1], onclick: function () { draft.min = p[0]; draft.inc = p[1]; hx.sel(); syncGrid(); } }));
    });
    function stepper(label, out, get, set, lo, hi, step) {
      return h('div', { class: 'stepper' }, h('span', { class: 'lbl', text: label }),
        h('div', { class: 'ctrl' },
          h('button', { type: 'button', text: '−', 'aria-label': 'کم', onclick: function () { set(Math.max(lo, get() - step)); hx.sel(); syncGrid(); } }),
          out,
          h('button', { type: 'button', text: '+', 'aria-label': 'زیاد', onclick: function () { set(Math.min(hi, get() + step)); hx.sel(); syncGrid(); } })));
    }
    function sw(label, key, after) {
      var b = h('button', { type: 'button', class: 'switch' + (cfg[key] ? ' on' : '') }, h('span', { text: label }), h('i', { class: 'tg' }));
      b.addEventListener('click', function () { cfg[key] = !cfg[key]; b.classList.toggle('on', cfg[key]); LS.set(K_CFG, cfg); hx.sel(); if (after) after(); });
      return b;
    }
    var apply = h('button', { type: 'button', class: 'btn', text: 'شروع ساعتِ جدید' });
    apply.addEventListener('click', function () {
      cfg.min = draft.min; cfg.inc = draft.inc; LS.set(K_CFG, cfg);
      reset(); Sheet.close(); toast('ساعت روی ' + cfg.min + '+' + cfg.inc + ' تنظیم شد');
    });
    var body = h('div', null,
      h('div', { class: 'sec-title', style: 'margin-top:6px' }, h('span', { text: 'زمان بازی' }), h('small', { text: 'دقیقه + ثانیه‌ی اضافه بعد از هر حرکت' })),
      grid,
      h('div', { class: 'group' },
        stepper('دقیقه‌ی هر بازیکن', minOut, function () { return draft.min; }, function (v) { draft.min = v; }, 1, 180, 1),
        stepper('ثانیه‌ی اضافه', incOut, function () { return draft.inc; }, function (v) { draft.inc = v; }, 0, 60, 1)),
      h('div', { class: 'sec-title' }, h('span', { text: 'رفتار' })),
      h('div', { class: 'group' },
        sw('صدای هر حرکت', 'sound'), sw('لرزش', 'haptic'), sw('روشن ماندنِ صفحه', 'awake', function () { if (cfg.awake) { if (st.phase === 'run') wakeOn(); } else wakeOff(); })));
    syncGrid();
    Sheet.open({ title: 'تنظیم ساعت', body: body, foot: apply });
  }

  /* ─── ساخت رابط ──────────────────────────────────────────── */
  function half(side) {
    var time = h('div', { class: 'time num', text: '0:00' });
    var mv = h('div', { class: 'mv' });
    var box = h('div', { class: 'half ' + side, role: 'button', 'aria-label': side === 'top' ? 'ساعت بازیکن بالا' : 'ساعت بازیکن پایین' }, h('div', { class: 'inner' }, time, mv));
    box.addEventListener('pointerdown', function (e) { e.preventDefault(); press(side); });
    els[side] = { box: box, time: time, mvEl: mv, txt: null, cls: null, mv: null };
    return box;
  }

  function mount(root, c) {
    ctx = c; h = c.h; ic = c.ic; hx = c.hx; tg = c.tg; Sheet = c.Sheet; toast = c.toast; LS = c.LS;
    var saved = LS.get(K_CFG); if (saved) for (var k in cfg) if (saved[k] !== undefined) cfg[k] = saved[k];
    cfg.min = Math.min(180, Math.max(1, +cfg.min || 5)); cfg.inc = Math.min(60, Math.max(0, +cfg.inc || 0));

    var top = half('top'), bot = half('bot');
    els.preset = h('button', { type: 'button', class: 'preset', onclick: openSettings, 'aria-label': 'تنظیم زمان' });
    els.play = h('button', { type: 'button', class: 'play', onclick: togglePause, 'aria-label': 'شروع یا توقف' }, ic('play'));
    var rs = h('button', { type: 'button', 'aria-label': 'بازنشانی', onclick: askReset }, ic('reset'));
    els.rs = rs;
    var ctl = h('div', { class: 'ctl' }, els.preset, els.play, rs);
    root.replaceChildren(h('div', { class: 'clock' }, top, ctl, bot));

    if (!restore()) { st.t = { top: base(), bot: base() }; }
    if (st.phase === 'run') { warned = { top: false, bot: false }; wakeOn(); guard(true); }
    paintAll();
    if (st.phase === 'run') { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); }

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { hidWall = Date.now(); hidPerf = performance.now(); save(); }
      else {
        if (st.phase === 'run' && hidWall) {
          var extra = (Date.now() - hidWall) - (performance.now() - hidPerf);
          if (extra > 50) st.last -= extra;     // زمانی که مرورگر ساعتِ monotonic را متوقف کرده بود
          wakeOn();
          cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
        }
        hidWall = 0;
      }
    });
  }

  window.HubClock = {
    mount: mount,
    onShow: function () { if (st.phase === 'run') { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); } },
    onHide: function () { save(); }
  };
})();
