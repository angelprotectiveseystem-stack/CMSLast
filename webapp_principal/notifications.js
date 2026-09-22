// پنل مدیر مدرسه — اعلانات (زنگولهٔ بالای صفحه).
// بخش‌های این فایل:
//   ۱) توابعِ خالص: نرمال‌سازیِ متنِ فارسی، تاریخِ شمسی/تهران، فیلتر و جستجو (بدون DOM، قابل‌تست)
//   ۲) رابط: زنگوله + نشانِ تعدادِ خوانده‌نشده، ورقهٔ اعلانات، پولینگِ سبک
//   ۳) اجازهٔ اعلانِ مرورگر + اشتراکِ Web Push (sw.js)
// مستقل از app.js است (فقط window.PRINCIPAL_KEY را می‌خواند).

(function () {
  "use strict";

  // ═════════════ ۱) توابعِ خالص ═════════════
  var TZ = "Asia/Tehran";
  var DAY_MS = 86400000;

  var PERIODS = [
    ["all", "همه زمان‌ها"],
    ["today", "امروز"],
    ["yesterday", "دیروز"],
    ["week", "این هفته"],
    ["lastweek", "هفتهٔ گذشته"],
    ["month", "این ماه"],
    ["lastmonth", "ماهِ گذشته"],
  ];

  var gregFmt = new Intl.DateTimeFormat("en-US-u-ca-gregory-nu-latn", {
    timeZone: TZ, year: "numeric", month: "numeric", day: "numeric",
    hour: "numeric", minute: "numeric", hourCycle: "h23",
  });
  var persFmt = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
    timeZone: TZ, year: "numeric", month: "numeric", day: "numeric",
  });
  var persMonthFmt = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { timeZone: TZ, month: "long" });
  var weekdayFmt = new Intl.DateTimeFormat("fa-IR", { timeZone: TZ, weekday: "long" });
  var gregMonthFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, month: "long" });

  function partsOf(fmt, ms) {
    var out = {};
    fmt.formatToParts(new Date(ms)).forEach(function (p) { out[p.type] = p.value; });
    return out;
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function toFa(v) {
    return String(v).replace(/[0-9]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; });
  }

  // همه‌چیزِ لازم دربارهٔ یک لحظه، به وقتِ تهران
  function describeDate(ms) {
    var g = partsOf(gregFmt, ms);
    var j = partsOf(persFmt, ms);
    var gy = +g.year, gm = +g.month, gd = +g.day;
    var utcDay = Date.UTC(gy, gm - 1, gd);
    return {
      gy: gy, gm: gm, gd: gd,
      hh: pad2(+g.hour), mm: pad2(+g.minute),
      jy: +j.year, jm: +j.month, jd: +j.day,
      dayNum: Math.round(utcDay / DAY_MS),           // شمارهٔ روزِ تقویمیِ تهران
      dow: new Date(utcDay).getUTCDay(),              // ۰ = یکشنبه … ۶ = شنبه
      jMonthName: persMonthFmt.format(new Date(ms)),
      weekdayName: weekdayFmt.format(new Date(ms)),
      gMonthName: gregMonthFmt.format(new Date(ms)),
    };
  }

  // «دیروز» و «هفتهٔ گذشته» بر اساسِ تقویمِ ایران: هفته از شنبه شروع می‌شود.
  function periodMatch(period, d, now) {
    if (period === "all") return true;
    if (period === "today") return d.dayNum === now.dayNum;
    if (period === "yesterday") return d.dayNum === now.dayNum - 1;
    var weekStart = now.dayNum - ((now.dow + 1) % 7);
    if (period === "week") return d.dayNum >= weekStart && d.dayNum <= now.dayNum;
    if (period === "lastweek") return d.dayNum >= weekStart - 7 && d.dayNum < weekStart;
    if (period === "month") return d.jy === now.jy && d.jm === now.jm;
    if (period === "lastmonth") {
      var py = now.jm === 1 ? now.jy - 1 : now.jy;
      var pm = now.jm === 1 ? 12 : now.jm - 1;
      return d.jy === py && d.jm === pm;
    }
    return true;
  }

  // یکسان‌سازیِ متن برای جستجو: رقمِ فارسی/عربی → لاتین، ی/ک عربی → فارسی،
  // حذفِ اعراب و کشیده و نیم‌فاصله، حروفِ کوچک.
  function normalize(str) {
    return String(str == null ? "" : str)
      .replace(/[\u06F0-\u06F9]/g, function (c) { return String(c.charCodeAt(0) - 0x06F0); })
      .replace(/[\u0660-\u0669]/g, function (c) { return String(c.charCodeAt(0) - 0x0660); })
      .replace(/[\u064A\u0649]/g, "\u06CC")
      .replace(/\u0643/g, "\u06A9")
      .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
      .replace(/[\u200C\u200D\u200E\u200F]/g, "")
      .toLowerCase();
  }
  // در جستجو، «1405-07-01» و «1405.7.1» هم مثلِ «1405/07/01» فهمیده شوند.
  function normalizeQuery(q) {
    return normalize(q).replace(/(\d)[-.](?=\d)/g, "$1/").trim();
  }

  function itemMs(item) {
    if (item.created_ts) return item.created_ts * 1000;
    var t = Date.parse(String(item.created_at || "") + "+03:30");
    return isNaN(t) ? 0 : t;
  }

  // Intl کند است؛ برای هر اعلان فقط یک‌بار تاریخ و رشتهٔ جستجو ساخته می‌شود
  // (با هر بار تایپ در کادر جستجو دوباره ساخته نشود).
  var dateCache = new WeakMap();
  var hayCache = new WeakMap();
  function dateOf(item) {
    var d = dateCache.get(item);
    if (!d) { d = describeDate(itemMs(item)); dateCache.set(item, d); }
    return d;
  }

  // رشته‌ای که جستجو روی آن انجام می‌شود: عنوان + متن + تاریخِ اعلان به همهٔ
  // قالب‌های رایج (شمسی/میلادی، با و بدون صفر، نام ماه و روزِ هفته، ساعت).
  function buildHaystack(item, now) {
    var cached = hayCache.get(item);
    if (cached && cached.day === (now ? now.dayNum : null)) return cached;
    var d = dateOf(item);
    var parts = [
      item.title, item.body,
      d.jy + "/" + pad2(d.jm) + "/" + pad2(d.jd),
      d.jy + "/" + d.jm + "/" + d.jd,
      d.jd + " " + d.jMonthName + " " + d.jy,
      d.jMonthName, d.weekdayName, String(d.jy),
      d.hh + ":" + d.mm,
      d.gy + "/" + pad2(d.gm) + "/" + pad2(d.gd),
      d.gy + "/" + d.gm + "/" + d.gd,
      d.gd + " " + d.gMonthName + " " + d.gy,
      d.gMonthName,
    ];
    if (now) {
      if (d.dayNum === now.dayNum) parts.push("امروز");
      else if (d.dayNum === now.dayNum - 1) parts.push("دیروز");
    }
    if (item.updated_at) parts.push("ویرایش شده");
    var text = normalize(parts.join(" \n "));
    var hay = { text: text, compact: text.replace(/\s+/g, ""), day: now ? now.dayNum : null };
    hayCache.set(item, hay);
    return hay;
  }

  // همهٔ کلمه‌ها باید پیدا شوند؛ ترتیبشان مهم نیست.
  function matchesQuery(hay, query) {
    function has(t) { return hay.text.indexOf(t) !== -1 || hay.compact.indexOf(t) !== -1; }
    var tokens = normalize(query).split(/\s+/).filter(Boolean);
    return tokens.every(function (t) {
      // هم همان‌طور که تایپ شده (مثلاً «3.5» داخل متن)، هم به‌صورتِ قالبِ تاریخ («1405-7-1»)
      return has(t) || has(normalizeQuery(t));
    });
  }

  // keep: شناسه‌هایی که در همین نشست وضعیتِ خوانده‌شدنشان را عوض کرده‌ایم؛ تا وقتی
  // فیلترِ «خوانده‌نشده/خوانده‌شده» فعال است، کارتی که همین الان بازش کرده‌اید
  // زیرِ دستتان غیب نشود.
  function applyFilters(items, f, nowMs, keep) {
    var now = describeDate(nowMs);
    var out = items.filter(function (it) {
      if (!(keep && keep.has(it.id))) {
        if (f.status === "unread" && it.is_read) return false;
        if (f.status === "read" && !it.is_read) return false;
      }
      if (!periodMatch(f.period, dateOf(it), now)) return false;
      if (f.query && f.query.trim()) return matchesQuery(buildHaystack(it, now), f.query);
      return true;
    });
    out.sort(function (a, b) { return f.order === "old" ? a.id - b.id : b.id - a.id; });
    return out;
  }

  function timeLabel(item, nowMs) {
    var d = dateOf(item);
    var now = describeDate(nowMs);
    var hm = toFa(d.hh + ":" + d.mm);
    if (d.dayNum === now.dayNum) return "امروز، " + hm;
    if (d.dayNum === now.dayNum - 1) return "دیروز، " + hm;
    return toFa(d.jd) + " " + d.jMonthName + " " + toFa(d.jy) + "، " + hm;
  }

  var core = {
    normalize: normalize, normalizeQuery: normalizeQuery, describeDate: describeDate,
    periodMatch: periodMatch, buildHaystack: buildHaystack, matchesQuery: matchesQuery,
    applyFilters: applyFilters, timeLabel: timeLabel, toFa: toFa, PERIODS: PERIODS,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;

  // ═════════════ ۲) رابط ═════════════
  var KEY = window.PRINCIPAL_KEY || "";
  var POLL_MS = 30000;
  var PUSH_SYNC_KEY = "principal_push_sync";

  var el = {
    nt: document.getElementById("nt"),
    bell: document.getElementById("bell-btn"),
    badge: document.getElementById("bell-badge"),
    sub: document.getElementById("nt-sub"),
    list: document.getElementById("nt-list"),
    count: document.getElementById("nt-count"),
    search: document.getElementById("nt-search"),
    status: document.getElementById("nt-status"),
    period: document.getElementById("nt-period"),
    sort: document.getElementById("nt-sort"),
    readAll: document.getElementById("nt-readall"),
    banner: document.getElementById("nt-banner"),
    detail: document.getElementById("nt-detail"),
    detailClose: document.getElementById("nt-detail-close"),
    detailTime: document.getElementById("nt-detail-time"),
    detailTitle: document.getElementById("nt-detail-title"),
    detailText: document.getElementById("nt-detail-text"),
    detailToggle: document.getElementById("nt-detail-toggle"),
  };
  if (!el.nt || !el.bell) return;
  var detailId = null;

  var state = {
    items: [], loaded: false, unread: 0, total: 0, latestId: null,
    status: "all", period: "all", query: "", order: "new",
    expanded: new Set(), keep: new Set(), lastJSON: "",
    open: false,
    push: { supported: false, serverAvailable: null, publicKey: "", askedThisSession: false, showHowTo: false },
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function call(path, opts) {
    var url = new URL(path, window.location.origin);
    url.searchParams.set("k", KEY);
    opts = opts || {};
    if (opts.body && typeof opts.body !== "string") {
      opts.body = JSON.stringify(opts.body);
      opts.headers = { "Content-Type": "application/json" };
    }
    return fetch(url.toString(), opts).then(function (res) {
      if (!res.ok) throw new Error("request_failed:" + res.status);
      return res.json();
    });
  }

  // ── زنگوله ────────────────────────────────────────────────
  function paintBadge() {
    var n = state.unread;
    if (n > 0) {
      el.badge.textContent = n > 99 ? toFa(99) + "+" : toFa(n);
      el.badge.hidden = false;
    } else {
      el.badge.hidden = true;
    }
    el.bell.setAttribute("aria-label", n > 0 ? "اعلانات، " + toFa(n) + " خوانده‌نشده" : "اعلانات");
  }
  function ringBell() {
    el.bell.classList.remove("ring");
    void el.bell.offsetWidth;
    el.bell.classList.add("ring");
    setTimeout(function () { el.bell.classList.remove("ring"); }, 1400);
  }

  // ── پیامِ کوتاهِ بالای صفحه (وقتی اعلانِ تازه می‌رسد و ورقه بسته است) ──
  var toastTimer = null;
  function showToast(text) {
    var t = document.getElementById("nt-toast");
    if (!t) {
      t = document.createElement("button");
      t.id = "nt-toast";
      t.type = "button";
      t.className = "nt-toast";
      t.addEventListener("click", function () { t.classList.remove("show"); openSheet(); });
      document.body.appendChild(t);
    }
    t.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-bell"/></svg><span></span>';
    t.querySelector("span").textContent = text;
    void t.offsetWidth;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 5500);
  }

  // ── داده ─────────────────────────────────────────────────
  var inflight = null;
  function loadList() {
    if (inflight) return inflight;
    inflight = call("/api/principal/notifications").then(function (d) {
      if (!d || !d.ok) return;
      var json = JSON.stringify(d.items);
      var changed = json !== state.lastJSON;
      state.lastJSON = json;
      state.items = d.items;
      state.loaded = true;
      state.total = d.items.length;
      state.unread = d.unread;
      state.latestId = d.latest_id;
      paintBadge();
      if (state.open && changed) render();
      else if (state.open) paintSub();
    }).catch(function () {
      if (state.open && !state.loaded) {
        el.list.innerHTML = '<div class="nt-empty"><b>مشکلی پیش آمد</b><p>دریافت اعلانات با خطا مواجه شد. لطفاً لحظاتی بعد دوباره تلاش کنید.</p></div>';
      }
    }).then(function () { inflight = null; });
    return inflight;
  }

  function poll() {
    if (document.hidden) return;
    call("/api/principal/notifications/summary").then(function (s) {
      if (!s || !s.ok) return;
      var prevLatest = state.latestId;
      state.unread = s.unread;
      state.total = s.total;
      paintBadge();
      var isNew = prevLatest !== null && s.latest_id > prevLatest;
      if (prevLatest === null) state.latestId = s.latest_id;
      if (isNew || state.open) {
        var before = state.latestId;
        loadList().then(function () {
          if (!isNew) return;
          var fresh = state.items.filter(function (it) { return it.id > before && !it.is_read; });
          if (!fresh.length) return;
          ringBell();
          if (!state.open) {
            showToast(fresh.length > 1 ? toFa(fresh.length) + " اعلان تازه رسید" : fresh[0].title);
          }
        });
      }
    }).catch(function () {});
  }

  function markRead(ids, read) {
    var set = new Set(ids);
    state.items.forEach(function (it) { if (set.has(it.id)) it.is_read = read; });
    state.lastJSON = JSON.stringify(state.items);
    state.unread = state.items.filter(function (it) { return !it.is_read; }).length;
    paintBadge();
    return call("/api/principal/notifications/read", { method: "POST", body: { ids: ids, read: read } })
      .catch(function () { loadList(); });
  }

  // ── ورقهٔ اعلانات ─────────────────────────────────────────
  function paintSub() {
    if (!state.loaded) { el.sub.textContent = "در حال بارگذاری…"; return; }
    if (!state.total) el.sub.textContent = "هنوز اعلانی نرسیده است";
    else if (!state.unread) el.sub.textContent = "همهٔ اعلان‌ها خوانده شده‌اند";
    else el.sub.textContent = toFa(state.unread) + " اعلانِ خوانده‌نشده";
    el.readAll.disabled = !state.unread;
    el.readAll.style.opacity = state.unread ? "" : ".45";
  }

  function itemHTML(it, nowMs) {
    return '<article class="nt-item' + (it.is_read ? "" : " is-unread") + '" data-id="' + it.id + '">' +
      '<button class="nt-item-main" type="button">' +
        '<span class="nt-dot" aria-hidden="true"></span>' +
        '<span class="nt-item-txt">' +
          '<span class="nt-item-title">' + (it.is_read ? "" : '<span class="sr-only">خوانده‌نشده: </span>') + esc(it.title) + '</span>' +
          '<span class="nt-item-body">' + esc(it.body) + '</span>' +
          '<span class="nt-item-time">' + esc(timeLabel(it, nowMs)) +
            (it.updated_at ? ' <em>ویرایش‌شده</em>' : '') + '</span>' +
        '</span>' +
        '<svg class="ic nt-chev" aria-hidden="true"><use href="#i-chevron"/></svg>' +
      '</button>' +
    '</article>';
  }

  // ── نمایِ تمام‌صفحهٔ یک اعلان ──────────────────────────────
  function paintDetailToggle(it) {
    el.detailToggle.textContent = it.is_read ? "علامت به‌عنوان خوانده‌نشده" : "علامت به‌عنوان خوانده‌شده";
  }
  function openDetail(id) {
    var it = state.items.filter(function (x) { return x.id === id; })[0];
    if (!it) return;
    detailId = id;
    el.detailTitle.textContent = it.title;
    el.detailText.textContent = it.body;
    el.detailTime.textContent = timeLabel(it, Date.now()) + (it.updated_at ? " · ویرایش‌شده" : "");
    paintDetailToggle(it);
    el.detail.classList.add("open");
    el.detail.setAttribute("aria-hidden", "false");
    if (!it.is_read) {
      state.keep.add(id);       // در فیلترِ «خوانده‌نشده» همان‌جا بماند
      markRead([id], true);
      paintDetailToggle(it);
      paintSub();
      render();
    }
  }
  function closeDetail() {
    detailId = null;
    el.detail.classList.remove("open");
    el.detail.setAttribute("aria-hidden", "true");
  }

  function filtersActive() {
    return state.status !== "all" || state.period !== "all" || state.query.trim() !== "";
  }

  function render() {
    paintSub();
    var nowMs = Date.now();
    var shown = applyFilters(state.items, state, nowMs, state.keep);
    el.count.textContent = !state.loaded ? "" :
      (filtersActive() ? toFa(shown.length) + " اعلان از " + toFa(state.total) : toFa(state.total) + " اعلان");

    if (!state.loaded) {
      el.list.innerHTML = '<div class="sk"><i class="thin"></i><i class="thin"></i><i class="thin"></i></div>';
      return;
    }
    if (!shown.length) {
      el.list.innerHTML = state.total === 0
        ? '<div class="nt-empty"><span class="nt-empty-ic"><svg class="ic" aria-hidden="true"><use href="#i-bell"/></svg></span><b>هنوز اعلانی ندارید</b><p>هر پیامی که برایتان ارسال شود، همین‌جا نمایش داده می‌شود.</p></div>'
        : '<div class="nt-empty"><span class="nt-empty-ic"><svg class="ic" aria-hidden="true"><use href="#i-search"/></svg></span><b>اعلانی پیدا نشد</b><p>با این جستجو و فیلترها، اعلانی وجود ندارد.</p><button type="button" class="nt-clear" data-act="clear">پاک کردنِ جستجو و فیلترها</button></div>';
      return;
    }
    el.list.innerHTML = shown.map(function (it) { return itemHTML(it, nowMs); }).join("");
  }

  function renderPeriods() {
    el.period.innerHTML = PERIODS.map(function (p) {
      return '<button type="button" data-period="' + p[0] + '"' + (state.period === p[0] ? ' class="is-on"' : "") + '>' + p[1] + '</button>';
    }).join("");
  }
  function paintControls() {
    Array.prototype.forEach.call(el.status.children, function (b) {
      b.classList.toggle("is-on", b.getAttribute("data-status") === state.status);
    });
    renderPeriods();
    el.sort.textContent = state.order === "new" ? "جدیدترین اول" : "قدیمی‌ترین اول";
    el.sort.setAttribute("data-order", state.order);
    el.search.value = state.query;
  }

  function openSheet() {
    if (state.open) return;
    state.open = true;
    el.nt.classList.add("open");
    el.nt.setAttribute("aria-hidden", "false");
    el.bell.setAttribute("aria-expanded", "true");
    document.body.classList.add("nt-open");
    if (window.__lockBodyScroll) window.__lockBodyScroll();
    paintControls();
    renderBanner();
    render();
    loadList();
  }
  function closeSheet() {
    if (!state.open) return;
    closeDetail();
    state.open = false;
    state.keep.clear();
    el.nt.classList.remove("open");
    el.nt.setAttribute("aria-hidden", "true");
    el.bell.setAttribute("aria-expanded", "false");
    document.body.classList.remove("nt-open");
    if (window.__unlockBodyScroll) window.__unlockBodyScroll();
  }

  el.bell.addEventListener("click", function () { state.open ? closeSheet() : openSheet(); });
  el.nt.querySelectorAll("[data-nt-close]").forEach(function (b) { b.addEventListener("click", closeSheet); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (el.detail.classList.contains("open")) { closeDetail(); return; }
    if (state.open) closeSheet();
  });

  el.status.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-status]");
    if (!b) return;
    state.status = b.getAttribute("data-status");
    state.keep.clear();
    paintControls();
    render();
  });
  el.period.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-period]");
    if (!b) return;
    state.period = b.getAttribute("data-period");
    paintControls();
    render();
  });
  el.sort.addEventListener("click", function () {
    state.order = state.order === "new" ? "old" : "new";
    paintControls();
    render();
  });
  var searchTimer = null;
  el.search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () { state.query = el.search.value; render(); }, 120);
  });
  el.readAll.addEventListener("click", function () {
    if (!state.unread) return;
    var ids = state.items.filter(function (it) { return !it.is_read; }).map(function (it) { return it.id; });
    state.keep.clear();
    markRead(ids, true).then(function () { if (state.open) render(); });
    render();
  });

  el.list.addEventListener("click", function (e) {
    var clear = e.target.closest('[data-act="clear"]');
    if (clear) {
      state.status = "all"; state.period = "all"; state.query = ""; state.keep.clear();
      paintControls(); render();
      return;
    }
    var card = e.target.closest(".nt-item");
    if (!card) return;
    var id = +card.getAttribute("data-id");

    if (e.target.closest(".nt-item-main")) {
      openDetail(id);
    }
  });

  el.detail.addEventListener("click", function (e) {
    if (e.target.closest("#nt-detail-close")) { closeDetail(); return; }
    if (e.target.closest("#nt-detail-toggle")) {
      if (detailId == null) return;
      var it = state.items.filter(function (x) { return x.id === detailId; })[0];
      if (!it) return;
      var next = !it.is_read;
      state.keep.add(detailId);
      markRead([detailId], next).then(function () { if (state.open) render(); });
      paintDetailToggle(it);
      if (state.open) render();
    }
  });


  // ═════════════ ۳) اجازهٔ اعلان + Web Push ═════════════
  var ua = navigator.userAgent || "";
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var isStandalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true;

  state.push.supported = ("serviceWorker" in navigator) && ("PushManager" in window) && ("Notification" in window);

  function bannerKind() {
    if (!state.push.supported) return isIOS && !isStandalone ? "ios" : "unsupported";
    if (state.push.serverAvailable === false) return null;   // سرور نمی‌تواند پوش بفرستد؛ مزاحم نشویم
    if (state.push.serverAvailable === null) return null;    // هنوز نمی‌دانیم
    var p = Notification.permission;
    return p === "granted" ? null : p;                       // "default" | "denied"
  }

  function renderBanner() {
    var kind = bannerKind();
    if (!kind) { el.banner.hidden = true; el.banner.innerHTML = ""; return; }
    var html = "";
    if (kind === "default") {
      html = '<b>اعلان‌های گوشی خاموش است</b>' +
        '<p>برای اینکه هر اعلانِ تازه همان لحظه روی گوشی‌تان نمایش داده شود، لطفاً اجازهٔ ارسال اعلان را تأیید کنید.</p>' +
        '<button type="button" data-act="ask">اجازهٔ ارسال اعلان</button>';
    } else if (kind === "denied") {
      html = '<b>دسترسی اعلان‌ها تأیید نشده است</b>' +
        '<p>تا این اجازه را تأیید نکنید، اعلان‌های تازه فقط داخل همین پنل دیده می‌شوند و روی گوشی‌تان نمی‌رسند. لطفاً دسترسی را تأیید کنید تا هر پیام جدید بی‌درنگ برایتان نمایش داده شود. برای اینکه درخواست دسترسی دوباره نمایش داده شود، روی «درخواست دوباره» بزنید.</p>' +
        '<button type="button" data-act="ask">درخواست دوباره</button>' +
        (state.push.showHowTo
          ? '<p class="nt-howto">اگر پنجرهٔ درخواست ظاهر نشد، مرورگر اجازه را ثبت کرده و دیگر خودش نمی‌پرسد. در این حالت روی آیکون قفل (یا تنظیماتِ سایت) کنار نوار آدرس بزنید، گزینهٔ «اعلان‌ها» (Notifications) را روی «اجازه» (Allow) بگذارید و سپس این صفحه را دوباره باز کنید.</p>'
          : "");
    } else if (kind === "ios") {
      html = '<b>برای دریافت اعلان روی آیفون</b>' +
        '<p>ابتدا پنل را به صفحهٔ اصلیِ گوشی اضافه کنید: در Safari دکمهٔ اشتراک‌گذاری را بزنید و «Add to Home Screen» را انتخاب کنید. سپس پنل را از همان آیکون باز کنید و اجازهٔ ارسال اعلان را تأیید نمایید.</p>';
    } else {
      html = '<b>اعلان روی گوشی در دسترس نیست</b>' +
        '<p>این مرورگر ارسال اعلان به گوشی را پشتیبانی نمی‌کند؛ اعلان‌های تازه همچنان داخل همین پنل نمایش داده می‌شوند.</p>';
    }
    el.banner.innerHTML = html;
    el.banner.hidden = false;
  }

  function requestPermission() {
    return new Promise(function (resolve) {
      try {
        var r = Notification.requestPermission(resolve);   // نسخه‌های قدیمیِ Safari callback می‌گیرند
        if (r && typeof r.then === "function") r.then(resolve);
      } catch (err) { resolve(Notification.permission); }
    });
  }

  function askPermission() {
    state.push.askedThisSession = true;
    return requestPermission().then(function (result) {
      if (result === "denied") state.push.showHowTo = true;
      renderBanner();
      if (result === "granted") return syncSubscription().then(function () { showToast("اعلان‌های گوشی فعال شد"); });
    });
  }

  el.banner.addEventListener("click", function (e) {
    if (e.target.closest('[data-act="ask"]')) askPermission();
  });

  function urlB64ToBytes(b64) {
    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function sameBytes(buf, bytes) {
    if (!buf) return false;
    var a = new Uint8Array(buf);
    if (a.length !== bytes.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== bytes[i]) return false;
    return true;
  }

  function syncSubscription() {
    if (!state.push.supported || !state.push.serverAvailable || Notification.permission !== "granted") {
      return Promise.resolve();
    }
    var keyBytes = urlB64ToBytes(state.push.publicKey);
    return navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription().then(function (sub) {
        // اگر کلیدهای سرور عوض شده‌اند، اشتراکِ قدیمی بی‌فایده است.
        if (sub && !sameBytes(sub.options && sub.options.applicationServerKey, keyBytes)) {
          return sub.unsubscribe().then(function () { return null; });
        }
        return sub;
      }).then(function (sub) {
        return sub || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
      });
    }).then(function (sub) {
      var json = sub.toJSON();
      var url = window.location.pathname + window.location.search;
      var sig = json.endpoint + "|" + url;
      try {
        var last = JSON.parse(localStorage.getItem(PUSH_SYNC_KEY) || "null");
        if (last && last.sig === sig && Date.now() - last.t < DAY_MS) return;   // امروز قبلاً ثبت شده
      } catch (err) {}
      return call("/api/principal/push/subscribe", { method: "POST", body: { subscription: json, url: url } }).then(function (r) {
        if (r && r.ok) {
          try { localStorage.setItem(PUSH_SYNC_KEY, JSON.stringify({ sig: sig, t: Date.now() })); } catch (err) {}
        }
      });
    }).catch(function (err) { console.warn("push subscribe failed", err); });
  }

  function initPush() {
    if (!state.push.supported) { renderBanner(); return; }
    navigator.serviceWorker.addEventListener("message", function (e) {
      var t = e.data && e.data.type;
      if (t === "notif-refresh") poll();
      if (t === "open-notifications") openSheet();
    });
    call("/api/principal/push/key").then(function (r) {
      state.push.serverAvailable = !!(r && r.ok && r.available);
      state.push.publicKey = (r && r.public_key) || "";
      renderBanner();
      if (!state.push.serverAvailable) return;
      return navigator.serviceWorker.register("/principal-sw.js", { scope: "/principal" }).then(function () {
        if (Notification.permission === "granted") return syncSubscription();
        if (Notification.permission === "default") {
          // مرورگرها درخواستِ اجازه را فقط بعد از یک لمسِ واقعیِ کاربر می‌پذیرند؛ اولین لمس را می‌گیریم.
          var once = function () {
            document.removeEventListener("pointerup", once, true);
            if (!state.push.askedThisSession && Notification.permission === "default") askPermission();
          };
          document.addEventListener("pointerup", once, true);
        }
      });
    }).catch(function (err) { console.warn("push init failed", err); });
  }

  // ── شروع ─────────────────────────────────────────────────
  paintControls();
  paintBadge();
  poll();
  setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
  initPush();
  if (window.location.hash === "#notifications") openSheet();
})();
