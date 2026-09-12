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

  // مرکز فعال‌سازی ویو: چه از ساید‌بار بیاد چه از نوار پایین موبایل،
  // هر دو ناوبری و عنوان بالای صفحه با هم هماهنگ می‌مونن.
  function goToView(view) {
    if (!VIEW_TITLES[view]) return;
    if (state.view === view && !document.querySelector(".sidebar.open")) return; // از رندر تکراری/بی‌مورد جلوگیری می‌کنه
    state.view = view;

    // ۱) فیدبک فوری: فقط هایلایت آیتم‌ها و عنوان بالای صفحه عوض بشه.
    //    این کار سبک و بی‌درنگه، پس کلیک روی نوار پایین بلافاصله پاسخ می‌ده
    //    و منتظر بارگذاری داده نمی‌مونه.
    document.querySelectorAll(".nav-item").forEach(function (n) {
      n.classList.toggle("active", n.getAttribute("data-view") === view);
    });
    document.querySelectorAll(".bn-item[data-view]").forEach(function (n) {
      n.classList.toggle("active", n.getAttribute("data-view") === view);
    });
    document.getElementById("view-title").textContent = VIEW_TITLES[view];
    closeSidebar();

    // ۲) بارگذاری محتوا در فریم بعدی: با یک تیک فاصله از تغییرات بالا،
    //    ریفلوی سنگین (تعویض کامل view-body + شروع انیمیشن) با
    //    ریفلوی سبک بالا قاطی نمی‌شه و حس لگ/سکته از بین می‌ره.
    requestAnimationFrame(function () {
      render();
    });
  }

  document.getElementById("nav").addEventListener("click", function (e) {
    var btn = e.target.closest(".nav-item");
    if (!btn) return;
    goToView(btn.getAttribute("data-view"));
  });

  var bottomNavEl = document.getElementById("bottom-nav");
  if (bottomNavEl) {
    bottomNavEl.addEventListener("click", function (e) {
      var moreBtn = e.target.closest(".bn-more");
      if (moreBtn) {
        var sb = document.querySelector(".sidebar");
        if (sb.classList.contains("open")) closeSidebar(); else openSidebar();
        return;
      }
      var btn = e.target.closest(".bn-item[data-view]");
      if (!btn) return;
      goToView(btn.getAttribute("data-view"));
    });
  }

  // ── Mobile toggle / سایدبار موبایل (باز می‌شود از دکمه «بیشتر») ──
  function closeSidebar() {
    var sb = document.querySelector(".sidebar");
    if (sb) sb.classList.remove("open");
    var bd = document.getElementById("sidebar-backdrop");
    if (bd) bd.classList.remove("show");
    document.body.classList.remove("no-scroll");
    var moreBtn = document.querySelector(".bn-more");
    if (moreBtn) moreBtn.classList.remove("menu-open");
  }
  function openSidebar() {
    var sb = document.querySelector(".sidebar");
    if (sb) sb.classList.add("open");
    var bd = document.getElementById("sidebar-backdrop");
    if (bd) bd.classList.add("show");
    document.body.classList.add("no-scroll");
    var moreBtn = document.querySelector(".bn-more");
    if (moreBtn) moreBtn.classList.add("menu-open");
  }
  var backdropEl = document.getElementById("sidebar-backdrop");
  if (backdropEl) backdropEl.addEventListener("click", closeSidebar);

  // بستن با کلید Escape
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeSidebar();
  });
  // اگر صفحه بزرگ‌تر از حالت موبایل شد (چرخش صفحه یا تغییر اندازه)،
  // هر باقیمانده‌ای از حالت باز/بک‌دراپ رو پاک کن تا قفل چیدمان دسکتاپ رو نگیره
  window.addEventListener("resize", function () {
    if (window.innerWidth > 860) closeSidebar();
  });

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
  function greeting() {
    var h = new Date().getHours();
    if (h < 5) return "شب بخیر 🌙";
    if (h < 12) return "صبح بخیر ☀️";
    if (h < 17) return "ظهر بخیر ☀️";
    if (h < 20) return "عصر بخیر 🌇";
    return "شب بخیر 🌙";
  }
  function welcomeBanner() {
    return '<div class="welcome-banner">' +
      '<span class="welcome-emoji">👋</span>' +
      '<div class="welcome-text"><h3>' + greeting() + '</h3>' +
      '<p>خلاصه‌ای از وضعیت این لحظه‌ی مسابقات، پیش روی شماست.</p></div>' +
    '</div>';
  }

  // ── به‌روزرسانی هوشمند DOM (برای پولینگ زنده) ───────────
  // به‌جای innerHTML کامل (که هر بار انیمیشن‌های ورود عناصر رو از نو
  // پخش می‌کنه و باعث «سکته»ی بصری می‌شد)، این تابع محتوای container
  // رو با html جدید مقایسه می‌کنه: اگر تعداد و نوع فرزندان یکی بود،
  // فقط متن/HTML داخلی هر فرزند در صورت تغییر آپدیت می‌شه و خود
  // نودها (و انیمیشن روی آن‌ها) دست‌نخورده می‌مونن. اگر ساختار واقعاً
  // فرق داشت (مثلاً تعداد ردیف عوض شده)، به‌صورت کامل جایگزین می‌شه.
  function diffUpdate(container, newHTML) {
    var temp = document.createElement("div");
    temp.innerHTML = newHTML;
    var oldNodes = container.children;
    var newNodes = temp.children;

    if (oldNodes.length !== newNodes.length) {
      container.innerHTML = newHTML;
      return;
    }
    for (var i = 0; i < oldNodes.length; i++) {
      diffNode(oldNodes[i], newNodes[i]);
    }
  }
  function diffNode(oldEl, newEl) {
    if (oldEl.tagName !== newEl.tagName) { oldEl.replaceWith(newEl); return; }
    // اگر فرزند مستقیمی نداره (برگ درخت)، صرفاً innerHTML رو در صورت تغییر عوض کن
    if (oldEl.children.length === 0 && newEl.children.length === 0) {
      if (oldEl.innerHTML !== newEl.innerHTML) oldEl.innerHTML = newEl.innerHTML;
    } else if (oldEl.children.length === newEl.children.length) {
      for (var i = 0; i < oldEl.children.length; i++) diffNode(oldEl.children[i], newEl.children[i]);
    } else {
      oldEl.innerHTML = newEl.innerHTML;
    }
    // ویژگی‌های ساده (کلاس، data-*) هم سینک بشن بدون اینکه نود عوض بشه
    if (oldEl.className !== newEl.className) oldEl.className = newEl.className;
  }

  // ── Views ─────────────────────────────────────────────
  var body;

  function render(silent) {
    body = document.getElementById("view-body");
    state.silent = !!silent;

    if (silent) {
      var fn = VIEWS[state.view];
      if (fn) fn();
      // در حالت خاموش عمداً fade-in رو دست نمی‌زنیم تا محتوا چشمک
      // نزنه و کل بخش محو/ظاهر نشه.
      return;
    }

    // یک placeholder خیلی سبک و بدون انیمیشن (چون به‌محض رسیدن داده‌ی
    // واقعی جایگزین می‌شه و پخش انیمیشن روش صرفاً لگ اضافه می‌کنه).
    body.classList.remove("fade-in");
    body.innerHTML = '<div class="loading-state"><span class="spinner"></span>در حال بارگذاری…</div>';

    var fn2 = VIEWS[state.view];
    if (fn2) fn2();
  }

  // نوشتن محتوای ویو: در حالت عادی مستقیم جایگزین می‌شه و انیمیشن
  // ورود روی محتوای واقعی (نه روی placeholder لودینگ) پخش می‌شه.
  // در حالت پولینگ خاموش، به‌جای پاک‌کردن کامل DOM (که باعث
  // ری‌استارت انیمیشن‌ها و پرش/لگ صفحه می‌شد)، فقط تفاوت‌ها اعمال
  // می‌شن تا هیچ‌چیزی تکون نخوره.
  function setBody(html) {
    if (state.silent) {
      diffUpdate(body, html);
    } else {
      body.innerHTML = html;
      // انیمیشن ورود فقط همین یک‌بار، روی محتوای واقعی نهایی پخش می‌شه.
      body.classList.add("fade-in");
    }
  }

  var VIEWS = {
    home: function () {
      api("/api/panel/overview").then(function (d) {
        if (!d.ok) return;
        var s = d.stats;
        var onlineList = d.online_admins.map(function (a) {
          return '<div class="msg-item"><strong>' + esc(a.name) + '</strong> <span class="msg-meta">' + roleLabel(a.role) + '</span></div>';
        }).join("") || '<div class="empty-state">هیچ مدیری آنلاین نیست</div>';

        setBody(
          welcomeBanner() +
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
          '</div>');
      });
    },

    matches: function () {
      setBody(
        '<div class="section">' +
          '<div class="tabs" id="match-tabs">' +
            tabBtn("all", "همه", true) + tabBtn("today", "امروز") + tabBtn("week", "این هفته") + tabBtn("month", "این ماه") +
          '</div>' +
          '<div id="matches-table-wrap"><div class="loading-state">در حال بارگذاری…</div></div>' +
        '</div>');

      function load(period) {
        api("/api/panel/matches?period=" + period).then(function (d) {
          var wrap = document.getElementById("matches-table-wrap");
          if (!wrap) return;
          if (!d.ok || !d.matches.length) { wrap.innerHTML = '<div class="empty-state">مسابقه‌ای ثبت نشده</div>'; return; }
          var rows = d.matches.map(function (m) {
            return '<tr>' +
              '<td class="cell-primary">' + (m.is_pinned ? '<span class="pin-tag">📌</span>' : '') + esc(m.white) + ' ⚪ / ⚫ ' + esc(m.black) + '</td>' +
              '<td data-label="سفید">' + esc(m.white) + '</td>' +
              '<td data-label="سیاه">' + esc(m.black) + '</td>' +
              '<td data-label="نتیجه">' + resultBadge(m.result) + '</td>' +
              '<td data-label="تاریخ">' + fmtDate(m.match_date || m.created_at) + '</td></tr>';
          }).join("");
          wrap.innerHTML = '<table><thead><tr><th>سفید</th><th>سیاه</th><th>نتیجه</th><th>تاریخ</th></tr></thead><tbody>' + rows + '</tbody></table>';
          wrap.parentElement.classList.add("table-as-cards");
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
        if (!d.games.length) { setBody('<div class="section"><div class="empty-state">هیچ بازی زنده‌ای در جریان نیست</div></div>'); return; }
        var rows = d.games.map(function (g) {
          return '<tr>' +
            '<td class="cell-primary">🔴 ' + esc(g.white_name) + ' ⚪ / ⚫ ' + esc(g.black_name) + '</td>' +
            '<td data-label="سفید">' + esc(g.white_name) + '</td><td data-label="سیاه">' + esc(g.black_name) + '</td>' +
            '<td data-label="زمان سفید">' + fmtClock(g.white_time) + '</td><td data-label="زمان سیاه">' + fmtClock(g.black_time) + '</td>' +
            '<td data-label="آخرین حرکت">' + fmtDate(g.last_move_at) + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>بازی‌های زنده</h3><span class="count">' + d.games.length + ' بازی</span></div>' +
            '<table><thead><tr><th>سفید</th><th>سیاه</th><th>زمان سفید</th><th>زمان سیاه</th><th>آخرین حرکت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    players: function () {
      api("/api/panel/players").then(function (d) {
        if (!d.ok) return;
        if (!d.players.length) { setBody('<div class="section"><div class="empty-state">بازیکنی ثبت نشده</div></div>'); return; }
        var rows = d.players.map(function (p) {
          var total = (p.wins || 0) + (p.losses || 0) + (p.draws || 0);
          var pct = total ? Math.round((p.wins / total) * 100) : 0;
          return '<tr>' +
            '<td class="cell-primary player-name-cell">' + esc(p.full_name) + (p.is_elite ? ' ⭐' : '') + '<br><span class="class-tag">' + esc(p.class_name || "بدون کلاس") + '</span></td>' +
            '<td data-label="برد/باخت/مساوی">' + p.wins + '/' + p.losses + '/' + p.draws + '</td>' +
            '<td data-label="درصد برد">' + pct + '٪<span class="progress-mini"><span class="progress-mini-fill" style="width:' + pct + '%"></span></span></td>' +
            '<td data-label="وضعیت">' + (p.status === "active" ? '<span class="badge win">فعال</span>' : '<span class="badge pending">' + esc(p.status) + '</span>') + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>مسابقه‌دهنده‌ها</h3><span class="count">' + d.players.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>برد/باخت/مساوی</th><th>درصد برد</th><th>وضعیت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    elo: function () {
      api("/api/panel/elo").then(function (d) {
        if (!d.ok) return;
        if (!d.leaderboard.length) { setBody('<div class="section"><div class="empty-state">داده‌ای ثبت نشده</div></div>'); return; }
        var rows = d.leaderboard.map(function (r, i) {
          return '<tr>' +
            '<td class="cell-primary">#' + (i + 1) + ' — ' + esc(r.full_name) + '</td>' +
            '<td data-label="امتیاز" class="rating-cell">' + Math.round(r.rating) + '</td>' +
            '<td data-label="اوج">' + Math.round(r.peak_rating) + '</td>' +
            '<td data-label="بازی‌ها">' + r.games_played + '</td>' +
            '<td data-label="ب/ب/م">' + r.wins + '/' + r.losses + '/' + r.draws + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>رده‌بندی ELO</h3><span class="count">' + d.leaderboard.length + ' بازیکن</span></div>' +
            '<table><thead><tr><th>#</th><th>نام</th><th>امتیاز</th><th>اوج</th><th>بازی‌ها</th><th>ب/ب/م</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    admins: function () {
      api("/api/panel/admins").then(function (d) {
        if (!d.ok) return;
        var rows = d.admins.map(function (a) {
          return '<tr>' +
            '<td class="cell-primary">' + esc(a.name) + (a.username ? ' <span class="class-tag">@' + esc(a.username) + '</span>' : '') + '</td>' +
            '<td data-label="نقش">' + roleLabel(a.role) + '</td>' +
            '<td data-label="وضعیت اتصال">' + (a.online ? '<span class="badge online">آنلاین</span>' : '<span class="badge pending">آفلاین</span>') + '</td>' +
            '<td data-label="آخرین فعالیت">' + fmtDate(a.last_active) + '</td>' +
            '<td data-label="حساب">' + (a.is_active ? '<span class="badge win">فعال</span>' : '<span class="badge loss">غیرفعال</span>') + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>مدیر‌ها</h3><span class="count">' + d.admins.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>نقش</th><th>وضعیت</th><th>آخرین فعالیت</th><th>حساب</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    online: function () {
      api("/api/panel/online").then(function (d) {
        if (!d.ok) return;
        if (!d.online.length) { setBody('<div class="section"><div class="empty-state">در حال حاضر کسی آنلاین نیست</div></div>'); return; }
        var rows = d.online.map(function (a) {
          return '<tr>' +
            '<td class="cell-primary">🟢 ' + esc(a.name) + '</td>' +
            '<td data-label="نقش">' + roleLabel(a.role) + '</td>' +
            '<td data-label="آخرین فعالیت">' + fmtDate(a.last_active) + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>آنلاین‌های اکنون</h3><span class="count">' + d.online.length + ' نفر</span></div>' +
            '<table><thead><tr><th>نام</th><th>نقش</th><th>آخرین فعالیت</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
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
        setBody(
          '<div class="two-col">' +
            '<div class="section"><div class="section-head"><h3>اطلاعیه‌ها</h3><span class="count">' + d.announcements.length + '</span></div>' + list(d.announcements, "اطلاعیه‌ای ارسال نشده") + '</div>' +
            '<div class="section"><div class="section-head"><h3>اخبار</h3><span class="count">' + d.news.length + '</span></div>' + list(d.news, "خبری ارسال نشده") + '</div>' +
          '</div>' +
          '<div class="section"><div class="section-head"><h3>بازخوردها</h3><span class="count">' + d.feedback.length + '</span></div>' + list(d.feedback, "بازخوردی ثبت نشده") + '</div>');
      });
    },

    activity: function () {
      api("/api/panel/activity?page=0").then(function (d) {
        if (!d.ok) return;
        if (!d.activity.length) { setBody('<div class="section"><div class="empty-state">فعالیتی ثبت نشده</div></div>'); return; }
        var rows = d.activity.map(function (l) {
          return '<tr>' +
            '<td class="cell-primary">' + esc(l.admin) + '</td>' +
            '<td data-label="نوع اقدام">' + esc(l.action_type) + '</td>' +
            '<td data-label="توضیح">' + esc(l.description) + '</td>' +
            '<td data-label="زمان">' + fmtDate(l.logged_at) + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>فعالیت‌های اخیر</h3><span class="count">' + d.total + ' مورد</span></div>' +
            '<table><thead><tr><th>مدیر</th><th>نوع اقدام</th><th>توضیح</th><th>زمان</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    charts: function () {
      setBody('<div class="loading-state">در حال بارگذاری نمودارها…</div>');
      api("/api/panel/charts").then(function (d) {
        if (!d.ok) return;
        setBody(
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
          '</div>');
      });
    },

    assistant: function () {
      api("/api/panel/assistant").then(function (d) {
        if (!d.ok) return;
        if (!d.sessions.length) { setBody('<div class="section"><div class="empty-state">گفتگویی با دستیار ثبت نشده</div></div>'); return; }
        var rows = d.sessions.map(function (s) {
          return '<tr>' +
            '<td class="cell-primary">' + esc(s.title || "بدون عنوان") + '</td>' +
            '<td data-label="تعداد پیام">' + s.msg_count + '</td>' +
            '<td data-label="آخرین پیام">' + fmtDate(s.last_message_at) + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>جلسات دستیار هوش مصنوعی</h3><span class="count">' + d.sessions.length + '</span></div>' +
            '<table><thead><tr><th>عنوان</th><th>تعداد پیام</th><th>آخرین پیام</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
      });
    },

    settings: function () {
      api("/api/panel/settings").then(function (d) {
        if (!d.ok) return;
        if (!d.settings.length) { setBody('<div class="section"><div class="empty-state">تنظیماتی ثبت نشده</div></div>'); return; }
        var rows = d.settings.map(function (s) {
          return '<tr><td class="cell-primary">' + esc(s.key) + '</td><td data-label="مقدار">' + esc(s.value) + '</td></tr>';
        }).join("");
        setBody(
          '<div class="section table-as-cards">' +
            '<div class="section-head"><h3>تنظیمات سیستم</h3></div>' +
            '<table><thead><tr><th>کلید</th><th>مقدار</th></tr></thead><tbody>' + rows + '</tbody></table>' +
          '</div>');
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
        render(true);
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

  // ── نشانگر موس سفارشی (فقط دسکتاپ با موس واقعی) ────────
  // pointer:fine یعنی وسیله‌ی اشاره‌گر دقیقه (موس)، hover:hover یعنی
  // می‌تونه واقعاً هاور کنه (نه لمسی). فقط این ترکیب رو فعال می‌کنیم
  // تا روی گوشی/تبلت هیچ چیزی عوض نشه و لمس با انگشت دست نخوره.
  function initCustomCursor() {
    if (!window.matchMedia || !window.matchMedia("(pointer: fine) and (hover: hover)").matches) return;
    var dot = document.getElementById("cursor-dot");
    var ring = document.getElementById("cursor-ring");
    if (!dot || !ring) return;

    var html = document.documentElement;
    html.classList.add("custom-cursor");

    var mouseX = 0, mouseY = 0;   // موقعیت واقعی موس
    var ringX = 0, ringY = 0;     // موقعیت حلقه، با یه تاخیر نرم دنبال موس میاد
    var ringScale = 1;            // فشردگی لحظه‌ی کلیک
    var ringScaleTarget = 1;
    var started = false;

    function paintDot() {
      dot.style.transform = "translate(" + mouseX + "px," + mouseY + "px) translate(-50%,-50%)";
    }
    function loop() {
      // انیمیشن روون: هر فریم فقط بخشی از فاصله رو طی می‌کنه (lerp)
      ringX += (mouseX - ringX) * 0.22;
      ringY += (mouseY - ringY) * 0.22;
      ringScale += (ringScaleTarget - ringScale) * 0.3;
      ring.style.transform = "translate(" + ringX + "px," + ringY + "px) translate(-50%,-50%) scale(" + ringScale + ")";
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);

    document.addEventListener("mousemove", function (e) {
      mouseX = e.clientX; mouseY = e.clientY;
      if (!started) { started = true; ringX = mouseX; ringY = mouseY; }
      paintDot();
      html.classList.remove("cursor-hidden");
    });
    document.addEventListener("mouseleave", function () { html.classList.add("cursor-hidden"); });
    document.addEventListener("mouseenter", function () { html.classList.remove("cursor-hidden"); });
    document.addEventListener("mousedown", function () { ringScaleTarget = .82; });
    document.addEventListener("mouseup", function () { ringScaleTarget = 1; });

    // روی چه چیزهایی شکل نشانگر عوض می‌شه:
    var POINTER_SEL = 'a, button, [role="button"], .nav-item, .bn-item, .tab-btn, label, input[type="checkbox"], input[type="radio"]';
    var TEXT_SEL = 'input:not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"]), textarea';
    document.addEventListener("mouseover", function (e) {
      if (e.target.closest && e.target.closest(POINTER_SEL)) {
        html.classList.add("cursor-pointer"); html.classList.remove("cursor-text");
      } else if (e.target.closest && e.target.closest(TEXT_SEL)) {
        html.classList.add("cursor-text"); html.classList.remove("cursor-pointer");
      } else {
        html.classList.remove("cursor-pointer", "cursor-text");
      }
    });
  }
  initCustomCursor();

  // ── Init ──────────────────────────────────────────────
  if (localStorage.getItem(TOKEN_KEY)) {
    startApp();
  }
})();
