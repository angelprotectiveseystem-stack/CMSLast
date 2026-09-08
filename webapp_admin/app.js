(function () {
  "use strict";

  var TOKEN_KEY = "chess_panel_token";
  var POLL_MS = 4000; // زنده بدون فشار به سرور: هر ۴ ثانیه فقط GET های سبک
  var state = { view: "home", timer: null, activityPage: 0 };

  // ── HTTP ──────────────────────────────────────────────
  function api(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    var token = localStorage.getItem(TOKEN_KEY);
    if (token) headers["X-Panel-Token"] = token;
    return fetch(path, Object.assign({}, opts, { headers: headers }))
      .then(function (r) {
        if (r.status === 401) {
          doLogout();
          throw new Error("unauthorized");
        }
        return r.json();
      });
  }

  function doLogout() {
    localStorage.removeItem(TOKEN_KEY);
    document.getElementById("app").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
    if (state.timer) clearInterval(state.timer);
  }

  // ── Login ─────────────────────────────────────────────
  function tryLogin() {
    var pw = document.getElementById("login-password").value;
    var errEl = document.getElementById("login-error");
    errEl.textContent = "";
    fetch("/api/panel/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          localStorage.setItem(TOKEN_KEY, data.token);
          startApp();
        } else {
          errEl.textContent = data.error || "ورود ناموفق بود.";
        }
      })
      .catch(function () { errEl.textContent = "ارتباط با سرور برقرار نشد."; });
  }

  document.getElementById("login-btn").addEventListener("click", tryLogin);
  document.getElementById("login-password").addEventListener("keydown", function (e) {
    if (e.key === "Enter") tryLogin();
  });

  // ── Nav ───────────────────────────────────────────────
  var VIEW_TITLES = {
    home: "خانه", matches: "مسابقات شطرنج", live: "شطرنج زنده",
    players: "مسابقه‌دهنده‌ها", elo: "سطح پیشرفت / ELO", admins: "مدیر‌ها",
    online: "آنلاین‌ها", messages: "پیام‌های ارسالی", activity: "فعالیت‌ها",
    charts: "نمودارها", assistant: "دستیار", settings: "تنظیمات",
  };

  document.getElementById("nav").addEventListener("click", function (e) {
    var btn = e.target.closest(".nav-item");
    if (!btn) return;
    document.querySelectorAll(".nav-item").forEach(function (n) { n.classList.remove("active"); });
    btn.classList.add("active");
    state.view = btn.getAttribute("data-view");
    document.getElementById("view-title").textContent = VIEW_TITLES[state.view];
    document.getElementById("view-body").innerHTML = '<div class="loading-state"><span class="spinner"></span>در حال بارگذاری…</div>';
    closeSidebar();
    render();
  });

  // ── Mobile toggle ─────────────────────────────────────
  function closeSidebar() {
    document.querySelector(".sidebar").classList.remove("open");
    var bd = document.getElementById("sidebar-backdrop");
    if (bd) bd.classList.remove("show");
  }
  function openSidebar() {
    document.querySelector(".sidebar").classList.add("open");
    var bd = document.getElementById("sidebar-backdrop");
    if (bd) bd.classList.add("show");
  }
  var toggleBtn = document.createElement("button");
  toggleBtn.className = "mobile-toggle";
  toggleBtn.innerHTML = "≡";
  toggleBtn.addEventListener("click", function () {
    var sb = document.querySelector(".sidebar");
    if (sb.classList.contains("open")) closeSidebar(); else openSidebar();
  });
  document.body.appendChild(toggleBtn);
  var backdropEl = document.getElementById("sidebar-backdrop");
  if (backdropEl) backdropEl.addEventListener("click", closeSidebar);

  // ── Clock ─────────────────────────────────────────────
  function tickClock() {
    var el = document.getElementById("topbar-clock");
    if (el) el.textContent = new Date().toLocaleTimeString("fa-IR");
  }

  // ── Helpers ───────────────────────────────────────────
  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return esc(iso);
      return d.toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" });
    } catch (e) { return esc(iso); }
  }
  function resultBadge(result) {
    if (!result) return '<span class="badge pending">در انتظار</span>';
    if (result === "white" || result === "black") return '<span class="badge win">' + (result === "white" ? "برد سفید" : "برد سیاه") + '</span>';
    if (result === "draw") return '<span class="badge draw">مساوی</span>';
    return '<span class="badge pending">' + esc(result) + '</span>';
  }
  function roleLabel(role) {
    var map = { pishva: "پیشوا", tournament_manager: "مدیر مسابقات", security_manager: "مدیر امنیت" };
    return map[role] || esc(role || "—");
  }

  // ── Views ─────────────────────────────────────────────
  var body;

  function render() {
    body = document.getElementById("view-body");
    var fn = VIEWS[state.view];
    if (fn) fn();
    body.classList.remove("fade-in");
    // ری‌استارت انیمیشن حتی اگر کلاس از قبل حذف نشده باشد
    void body.offsetWidth;
    body.classList.add("fade-in");
  }

  var VIEWS = {
    home: function () {
      api("/api/panel/overview").then(function (d) {
        if (!d.ok) return;
        var s = d.stats;
        var onlineList = d.online_admins.map(function (a) {
          return '<div class="msg-item"><strong>' + esc(a.name) + '</strong> <span class="msg-meta">' + roleLabel(a.role) + '</span></div>';
        }).join("") || '<div class="empty-state">هیچ مدیری آنلاین نیست</div>';

        body.innerHTML =
          '<div class="grid">' +
            statCard("مسابقه‌دهنده‌ها", s.players_total, "") +
            statCard("مدیران", s.admins_total, "") +
            statCard("مدیران آنلاین", s.admins_online, "accent-sage") +
            statCard("کل مسابقات", s.matches_total, "") +
            statCard("مسابقات در انتظار", s.matches_pending, "accent-rust") +
            statCard("تورنومنت‌های فعال", s.tournaments_active, "") +
            statCard("شطرنج‌های زنده", s.live_games, "accent-sage") +
          '</div>' +
          '<div class="section">' +
            '<div class="section-head"><h3>مدیران آنلاین اکنون</h3></div>' +
            onlineList +
          '</div>';
      });
    },

    matches: function () {
      body.innerHTML =
        '<div class="section">' +
          '<div class="tabs" id="match-tabs">' +
            tabBtn("all", "همه", true) + tabBtn("today", "امروز") + tabBtn("week", "این هفته") + tabBtn("month", "این ماه") +
          '</div>' +
          '<div id="matches-table-wrap"><div class="loading-state">در حال بارگذاری…</div></div>' +
        '</div>';

      function load(period) {
        api("/api/panel/matches?period=" + period).then(function (d) {
          var wrap = document.getElementById("matches-table-wrap");
          if (!wrap) return;
          if (!d.ok || !d.matches.length) { wrap.innerHTML = '<div class="empty-state">مسابقه‌ای ثبت نشده</div>'; return; }
          var rows = d.matches.map(function (m) {
            return '<tr><td>' + (m.is_pinned ? '<span class="pin-tag">📌</span>' : '') + esc(m.white) + '</td><td>' + esc(m.black) + '</td><td>' + resultBadge(m.result) + '</td><td>' + fmtDate(m.match_date || m.created_at) + '</td></tr>';
          }).join("");
          wrap.innerHTML = '<table><thead><tr><th>سفید</th><th>سیاه</th><th>نتیجه</th><th>تاریخ</th></tr></thead><tbody>' + rows + '</tbody></table>';
        });
      }
      document.getElementById("match-tabs").addEventListener("click", function (e) {
        var btn = e.target.closest(".tab-btn"); if (!btn) return;
        document.querySelectorAll("#match-tabs .tab-btn").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        load(btn.getAttribute("data-period"));
      });
      load("all");
    },

    live: function () {
      api("/api/panel/live-chess").then(function (d) {
        if (!d.ok) return;
        if (!d.games.length) { body.innerHTML = '<div class="section"><div class="empty-state">هیچ بازی زنده‌ای در جریان نیست</div></div>'; return; }
        var rows = d.games.map(function (g) {
          return '<tr><td>' + esc(g.white_name) + '</td><td>' + esc(g.black_name) + '</td>' +
            '<td>' + fmtClock(g.white_time) + '</td><td>' + fmtClock(g.black_time) + '</td>' +
            '<td>' + fmtDate(g.last_move_at) + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>بازی‌های زنده</h3><span class="count">' + d.games.length + ' بازی</span></div>' +
            '<table><thead><tr><th>سفید</th><th>سیاه</th><th>زمان سفید</th><th>زمان سیاه</th><th>آخرین حرکت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    players: function () {
      api("/api/panel/players").then(function (d) {
        if (!d.ok) return;
        if (!d.players.length) { body.innerHTML = '<div class="section"><div class="empty-state">بازیکنی ثبت نشده</div></div>'; return; }
        var rows = d.players.map(function (p) {
          var total = (p.wins || 0) + (p.losses || 0) + (p.draws || 0);
          var pct = total ? Math.round((p.wins / total) * 100) : 0;
          return '<tr><td class="player-name-cell">' + esc(p.full_name) + (p.is_elite ? ' ⭐' : '') + '<br><span class="class-tag">' + esc(p.class_name || "بدون کلاس") + '</span></td>' +
            '<td>' + p.wins + '/' + p.losses + '/' + p.draws + '</td>' +
            '<td>' + pct + '٪<span class="progress-mini"><span class="progress-mini-fill" style="width:' + pct + '%"></span></span></td>' +
            '<td>' + (p.status === "active" ? '<span class="badge win">فعال</span>' : '<span class="badge pending">' + esc(p.status) + '</span>') + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>مسابقه‌دهنده‌ها</h3><span class="count">' + d.players.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>برد/باخت/مساوی</th><th>درصد برد</th><th>وضعیت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    elo: function () {
      api("/api/panel/elo").then(function (d) {
        if (!d.ok) return;
        if (!d.leaderboard.length) { body.innerHTML = '<div class="section"><div class="empty-state">داده‌ای ثبت نشده</div></div>'; return; }
        var rows = d.leaderboard.map(function (r, i) {
          return '<tr><td>' + (i + 1) + '</td><td class="player-name-cell">' + esc(r.full_name) + '</td><td class="rating-cell">' + Math.round(r.rating) + '</td>' +
            '<td>' + Math.round(r.peak_rating) + '</td><td>' + r.games_played + '</td><td>' + r.wins + '/' + r.losses + '/' + r.draws + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>رده‌بندی ELO</h3><span class="count">' + d.leaderboard.length + ' بازیکن</span></div>' +
            '<table><thead><tr><th>#</th><th>نام</th><th>امتیاز</th><th>اوج</th><th>بازی‌ها</th><th>ب/ب/م</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    admins: function () {
      api("/api/panel/admins").then(function (d) {
        if (!d.ok) return;
        var rows = d.admins.map(function (a) {
          return '<tr><td>' + esc(a.name) + (a.username ? '<br><span class="class-tag">@' + esc(a.username) + '</span>' : '') + '</td>' +
            '<td>' + roleLabel(a.role) + '</td>' +
            '<td>' + (a.online ? '<span class="badge online">آنلاین</span>' : '<span class="badge pending">آفلاین</span>') + '</td>' +
            '<td>' + fmtDate(a.last_active) + '</td>' +
            '<td>' + (a.is_active ? '<span class="badge win">فعال</span>' : '<span class="badge loss">غیرفعال</span>') + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>مدیر‌ها</h3><span class="count">' + d.admins.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>نقش</th><th>وضعیت</th><th>آخرین فعالیت</th><th>حساب</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    online: function () {
      api("/api/panel/online").then(function (d) {
        if (!d.ok) return;
        if (!d.online.length) { body.innerHTML = '<div class="section"><div class="empty-state">در حال حاضر کسی آنلاین نیست</div></div>'; return; }
        var rows = d.online.map(function (a) {
          return '<tr><td>' + esc(a.name) + '</td><td>' + roleLabel(a.role) + '</td><td>' + fmtDate(a.last_active) + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>آنلاین‌های اکنون</h3><span class="count">' + d.online.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>نقش</th><th>آخرین فعالیت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    messages: function () {
      api("/api/panel/messages").then(function (d) {
        if (!d.ok) return;
        function list(items, emptyText) {
          if (!items.length) return '<div class="empty-state">' + emptyText + '</div>';
          return items.map(function (m) {
            return '<div class="msg-item">' + (m.is_pinned ? '<span class="pin-tag">📌</span>' : '') +
              '<div class="msg-text">' + esc(m.text || m.content) + '</div>' +
              '<div class="msg-meta">' + fmtDate(m.sent_at) + (m.title ? ' · ' + esc(m.title) : '') + '</div></div>';
          }).join("");
        }
        body.innerHTML =
          '<div class="two-col">' +
            '<div class="section"><div class="section-head"><h3>اطلاعیه‌ها</h3><span class="count">' + d.announcements.length + '</span></div>' + list(d.announcements, "اطلاعیه‌ای ارسال نشده") + '</div>' +
            '<div class="section"><div class="section-head"><h3>اخبار</h3><span class="count">' + d.news.length + '</span></div>' + list(d.news, "خبری ارسال نشده") + '</div>' +
          '</div>' +
          '<div class="section"><div class="section-head"><h3>بازخوردها</h3><span class="count">' + d.feedback.length + '</span></div>' + list(d.feedback, "بازخوردی ثبت نشده") + '</div>';
      });
    },

    activity: function () {
      api("/api/panel/activity?page=0").then(function (d) {
        if (!d.ok) return;
        if (!d.activity.length) { body.innerHTML = '<div class="section"><div class="empty-state">فعالیتی ثبت نشده</div></div>'; return; }
        var rows = d.activity.map(function (l) {
          return '<tr><td>' + esc(l.admin) + '</td><td>' + esc(l.action_type) + '</td><td>' + esc(l.description) + '</td><td>' + fmtDate(l.logged_at) + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>فعالیت‌های اخیر</h3><span class="count">' + d.total + ' مورد</span></div>' +
            '<table><thead><tr><th>مدیر</th><th>نوع اقدام</th><th>توضیح</th><th>زمان</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    charts: function () {
      body.innerHTML = '<div class="loading-state">در حال بارگذاری نمودارها…</div>';
      api("/api/panel/charts").then(function (d) {
        if (!d.ok) return;
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>مسابقات به تفکیک تورنومنت (میله‌ای)</h3></div>' +
            '<div class="chart-wrap">' + barChart(d.matches_by_tournament) + '</div>' +
          '</div>' +
          '<div class="section">' +
            '<div class="section-head"><h3>روند ثبت مسابقات — ۳۰ روز اخیر (خط شکسته)</h3></div>' +
            '<div class="chart-wrap">' + lineChart(d.matches_by_day) + '</div>' +
          '</div>' +
          '<div class="section">' +
            '<div class="section-head"><h3>توزیع بازیکنان بر اساس کلاس</h3></div>' +
            '<div class="chart-wrap">' + barChart(d.players_by_class) + '</div>' +
          '</div>';
      });
    },

    assistant: function () {
      api("/api/panel/assistant").then(function (d) {
        if (!d.ok) return;
        if (!d.sessions.length) { body.innerHTML = '<div class="section"><div class="empty-state">گفتگویی با دستیار ثبت نشده</div></div>'; return; }
        var rows = d.sessions.map(function (s) {
          return '<tr><td>' + esc(s.title || "بدون عنوان") + '</td><td>' + s.msg_count + '</td><td>' + fmtDate(s.last_message_at) + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>جلسات دستیار هوش مصنوعی</h3><span class="count">' + d.sessions.length + '</span></div>' +
            '<table><thead><tr><th>عنوان</th><th>تعداد پیام</th><th>آخرین پیام</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },

    settings: function () {
      api("/api/panel/settings").then(function (d) {
        if (!d.ok) return;
        if (!d.settings.length) { body.innerHTML = '<div class="section"><div class="empty-state">تنظیماتی ثبت نشده</div></div>'; return; }
        var rows = d.settings.map(function (s) {
          return '<tr><td>' + esc(s.key) + '</td><td>' + esc(s.value) + '</td></tr>';
        }).join("");
        body.innerHTML =
          '<div class="section">' +
            '<div class="section-head"><h3>تنظیمات سیستم</h3></div>' +
            '<table><thead><tr><th>کلید</th><th>مقدار</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>';
      });
    },
  };

  function statCard(label, value, accentClass) {
    return '<div class="stat-card ' + accentClass + '"><div class="stat-label">' + label + '</div><div class="stat-value">' + value + '</div></div>';
  }
  function tabBtn(period, label, active) {
    return '<button class="tab-btn' + (active ? " active" : "") + '" data-period="' + period + '">' + label + '</button>';
  }
  function fmtClock(seconds) {
    if (seconds == null) return "—";
    var m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function barChart(items) {
    if (!items || !items.length) return '<div class="empty-state">داده‌ای موجود نیست</div>';
    var max = Math.max.apply(null, items.map(function (i) { return i.value; })) || 1;
    return items.map(function (i) {
      var pct = Math.round((i.value / max) * 100);
      return '<div class="bar-row"><div class="bar-label" title="' + esc(i.label) + '">' + esc(i.label) + '</div>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="bar-value">' + i.value + '</div></div>';
    }).join("");
  }

  function lineChart(items) {
    if (!items || !items.length) return '<div class="empty-state">داده‌ای موجود نیست</div>';
    var w = 700, h = 120, pad = 10;
    var max = Math.max.apply(null, items.map(function (i) { return i.value; })) || 1;
    var stepX = items.length > 1 ? (w - pad * 2) / (items.length - 1) : 0;
    var pts = items.map(function (i, idx) {
      var x = pad + idx * stepX;
      var y = h - pad - (i.value / max) * (h - pad * 2);
      return x + "," + y;
    });
    var path = "M" + pts.join(" L");
    var dots = items.map(function (i, idx) {
      var coords = pts[idx].split(",");
      return '<circle cx="' + coords[0] + '" cy="' + coords[1] + '" r="2.5" fill="#c9922b"><title>' + esc(i.label) + ": " + i.value + '</title></circle>';
    }).join("");
    return '<svg class="sparkline" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none">' +
      '<path d="' + path + '" fill="none" stroke="#c9922b" stroke-width="2"/>' + dots + '</svg>';
  }

  // ── Poll / live update ─────────────────────────────────
  function poll() {
    var el = document.getElementById("conn-status");
    var dot = document.querySelector(".live-dot");
    api("/api/panel/overview").then(function (d) {
      if (d.ok) { el.textContent = "زنده و به‌روز"; dot.classList.remove("off"); }
      if (state.view === "home" || state.view === "live" || state.view === "online" || state.view === "admins") {
        render();
      }
    }).catch(function () {
      el.textContent = "قطع ارتباط"; dot.classList.add("off");
    });
  }

  function startApp() {
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    tickClock();
    setInterval(tickClock, 1000);
    render();
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(poll, POLL_MS);
  }

  // ── Init ──────────────────────────────────────────────
  if (localStorage.getItem(TOKEN_KEY)) {
    startApp();
  }
})();
