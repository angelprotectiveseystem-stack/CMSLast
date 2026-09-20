(function () {
  "use strict";

  var TOKEN_KEY = "chess_panel_token";
  var POLL_MS = 4000; // زنده بدون فشار به سرور: هر ۴ ثانیه فقط GET های سبک
  var state = { view: "home", timer: null, activityPage: 0, topManualView: false,
                assistantSession: null, assistantSource: "all", assistantQuery: "",
                principalDeviceOpen: null };

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

  function apiPost(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
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
    "principal-devices": "ورودهای مدیر مدرسه",
    charts: "نمودارها", assistant: "رهگشا", settings: "تنظیمات",
  };

  // مرکز فعال‌سازی ویو: چه از ساید‌بار بیاد چه از نوار پایین موبایل،
  // هر دو ناوبری و عنوان بالای صفحه با هم هماهنگ می‌مونن.
  function goToView(view) {
    if (!VIEW_TITLES[view]) return;
    // کلیک دوباره روی «دستیار» وقتی وسطِ یک گفتگو هستیم = برگشت به فهرست.
    var reopenAssistant = view === "assistant" && state.view === "assistant" && state.assistantSession;
    if (reopenAssistant) state.assistantSession = null;
    if (state.view === view && !document.querySelector(".sidebar.open") && !reopenAssistant) return; // از رندر تکراری/بی‌مورد جلوگیری می‌کنه
    // با خروج از تبِ «تنظیمات»، اگه وسطِ ویرایشِ دستیِ نفراتِ برتر بودیم،
    // دفعه‌ی بعد که دوباره وارد تنظیمات بشیم از اول (لیستِ اصلی) شروع بشه.
    if (state.view === "settings" && view !== "settings") state.topManualView = false;
    // همین الگو برای «دستیار»: با خروج از تب، دفعه‌ی بعد از فهرست گفتگوها شروع بشه.
    if (state.view === "assistant" && view !== "assistant") state.assistantSession = null;
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

    "principal-devices": function () { renderPrincipalDevices(); },

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
      if (state.assistantSession) { renderAssistantChat(state.assistantSession); return; }
      renderAssistantList();
    },

    settings: function () {
      if (state.topManualView) { renderTopManual(); return; }
      Promise.all([api("/api/panel/settings"), api("/api/panel/top-mode")]).then(function (results) {
        var d = results[0], modeData = results[1];
        if (!d.ok) return;
        var tableHtml;
        if (!d.settings.length) {
          tableHtml = '<div class="section"><div class="empty-state">تنظیماتی ثبت نشده</div></div>';
        } else {
          var rows = d.settings.map(function (s) {
            return '<tr><td class="cell-primary">' + esc(s.key) + '</td><td data-label="مقدار">' + esc(s.value) + '</td></tr>';
          }).join("");
          tableHtml =
            '<div class="section table-as-cards">' +
              '<div class="section-head"><h3>تنظیمات سیستم</h3></div>' +
              '<table><thead><tr><th>کلید</th><th>مقدار</th></tr></thead><tbody>' + rows + '</tbody></table>' +
            '</div>';
        }

        var manualMode = !!(modeData && modeData.ok && modeData.top_players_mode === "manual");
        var topCardHtml =
          '<div class="section-title">🏆 نمایشِ نفرات برتر</div>' +
          '<div class="settings-card">' +
            '<div class="settings-row">' +
              '<div class="settings-row-txt">' +
                '<div class="main-txt">شیوه‌ی فعلی: ' + (manualMode ? "🖐️ دستی" : "⚡ خودکار") + '</div>' +
                '<div class="sub-txt">این حالت فقط از تلگرام (تنظیماتِ ربات) قابل تغییره. خودکار یعنی بر اساسِ امتیازِ مسابقات؛ دستی یعنی خودتان پنج نفر را انتخاب می‌کنید.</div>' +
              '</div>' +
            '</div>' +
            (manualMode
              ? '<button class="big-btn" id="open-top-manual">👥 برتران — انتخاب نفرات برتر</button>'
              : '<div class="manual-note">وقتی حالت به «دستی» تغییر کند، دکمه‌ی «برتران» برای انتخابِ نفراتِ برتر همین‌جا ظاهر می‌شود.</div>') +
          '</div>';

        setBody(tableHtml + topCardHtml);

        var openBtn = document.getElementById("open-top-manual");
        if (openBtn) {
          openBtn.addEventListener("click", function () {
            state.topManualView = true;
            document.getElementById("view-title").textContent = "برتران";
            render();
          });
        }
      });
    },
  };

  // ── ورودهای مدیر مدرسه: دستگاه‌ها + لاگِ ورود (بلاک/آنبلاک/حذف) ──────
  // برخلافِ بقیه‌ی تب‌ها، این یکی می‌نویسه (بلاک/آنبلاک/حذفِ سوابق)، پس
  // «دستگاه» رو با ترکیبِ IP+User-Agent می‌شناسه (principal_panel.py این
  // شناسه رو ساخته)، نه با حسابِ کاربری — چون پنل مدیر مدرسه حساب نداره.
  function deviceIcon(type) {
    if (type === "mobile") return "📱";
    if (type === "tablet") return "📱";
    return "🖥️";
  }
  function deviceLocation(d) {
    var parts = [d.city, d.region, d.country].filter(Boolean);
    return parts.length ? parts.join("، ") : "نامشخص";
  }
  function deviceCard(d) {
    var open = state.principalDeviceOpen === d.device_id;
    return (
      '<div class="row-card device-card' + (d.is_blocked ? ' device-blocked' : '') + '" data-did="' + esc(d.device_id) + '">' +
        '<div class="device-card-top">' +
          '<div class="main-txt">' + deviceIcon(d.device_type) + ' ' + esc(d.browser) + ' روی ' + esc(d.os) + '</div>' +
          '<div class="badge-group">' + (d.is_blocked ? '<span class="badge loss">بلاک‌شده</span>' : '<span class="badge win">آزاد</span>') + '</div>' +
        '</div>' +
        '<div class="sub-txt">🌐 ' + esc(d.ip || "نامشخص") + ' · 📍 ' + esc(deviceLocation(d)) + '</div>' +
        '<div class="sub-txt">' + d.visits + ' بازدید · آخرین: ' + fmtDate(d.last_seen) + ' · اولین: ' + fmtDate(d.first_seen) + '</div>' +
        (d.is_blocked ? '<div class="sub-txt device-block-reason">دلیلِ بلاک: ' + esc(d.block_reason || "—") + '</div>' : '') +
        '<div class="device-actions">' +
          '<button class="tab-btn device-btn-detail" data-act="detail">' + (open ? '▲ بستن جزئیات' : '▼ بازدیدهای اخیر') + '</button>' +
          (d.is_blocked
            ? '<button class="tab-btn device-btn-unblock" data-act="unblock">✅ آنبلاک</button>'
            : '<button class="tab-btn device-btn-block" data-act="block">🚫 بلاک دستگاه</button>') +
          '<button class="tab-btn device-btn-delete" data-act="delete">🗑 حذف دسترسی</button>' +
        '</div>' +
        (open ? '<div class="device-detail" id="device-detail-' + esc(d.device_id) + '"><div class="loading-state"><span class="spinner"></span></div></div>' : '') +
      '</div>'
    );
  }

  function loadPrincipalDeviceDetail(deviceId) {
    var el = document.getElementById("device-detail-" + deviceId);
    if (!el) return;
    api("/api/panel/principal-log?device_id=" + encodeURIComponent(deviceId) + "&page=0").then(function (d) {
      if (!d.ok) return;
      if (!d.log.length) { el.innerHTML = '<div class="empty-state">بازدیدی ثبت نشده</div>'; return; }
      el.innerHTML = '<table><thead><tr><th>زمان</th><th>مسیر</th><th>وضعیت</th></tr></thead><tbody>' +
        d.log.map(function (l) {
          return '<tr><td data-label="زمان">' + fmtDate(l.created_at) + '</td>' +
            '<td data-label="مسیر">' + esc(l.path || "—") + '</td>' +
            '<td data-label="وضعیت">' + (l.allowed ? '<span class="badge win">موفق</span>' : '<span class="badge loss">ناموفق</span>') + '</td></tr>';
        }).join("") + '</tbody></table>';
    }).catch(function () { el.innerHTML = '<div class="empty-state">خطا در بارگذاری</div>'; });
  }

  function renderPrincipalDevices() {
    api("/api/panel/principal-devices").then(function (d) {
      if (!d.ok) return;
      if (!d.devices.length) { setBody('<div class="section"><div class="empty-state">هنوز ورودی از پنل مدیر مدرسه ثبت نشده</div></div>'); return; }
      var blockedCount = d.devices.filter(function (x) { return x.is_blocked; }).length;
      var cards = d.devices.map(deviceCard).join("");
      setBody(
        '<div class="section">' +
          '<div class="section-head"><h3>دستگاه‌های واردشده به پنل مدیر مدرسه</h3>' +
            '<span class="count">' + d.devices.length + ' دستگاه' + (blockedCount ? ' · ' + blockedCount + ' بلاک‌شده' : '') + '</span></div>' +
          '<div class="card-list">' + cards + '</div>' +
        '</div>'
      );
      var listEl = document.querySelector(".view-body .card-list") || body;
      listEl.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-act]");
        if (!btn) return;
        var card = btn.closest(".device-card");
        var did = card.getAttribute("data-did");
        var act = btn.getAttribute("data-act");

        if (act === "detail") {
          state.principalDeviceOpen = state.principalDeviceOpen === did ? null : did;
          renderPrincipalDevices();
          if (state.principalDeviceOpen === did) {
            // بارگذاریِ جزئیات بعد از رندرِ مجددِ کارت‌ها انجام می‌شه
            setTimeout(function () { loadPrincipalDeviceDetail(did); }, 0);
          }
          return;
        }
        if (act === "block") {
          var reason = prompt("دلیلِ بلاک‌کردنِ این دستگاه (اختیاری):", "");
          if (reason === null) return; // انصراف
          apiPost("/api/panel/principal-devices/block", { device_id: did, reason: reason })
            .then(function (res) {
              if (!res.ok) { alert("خطا در بلاک‌کردن دستگاه."); return; }
              renderPrincipalDevices();
            }).catch(function () { alert("ارتباط با سرور برقرار نشد."); });
          return;
        }
        if (act === "unblock") {
          if (!confirm("این دستگاه دوباره به پنل مدیر مدرسه دسترسی پیدا کند؟")) return;
          apiPost("/api/panel/principal-devices/unblock", { device_id: did })
            .then(function (res) {
              if (!res.ok) { alert("خطا در آنبلاک‌کردن دستگاه."); return; }
              renderPrincipalDevices();
            }).catch(function () { alert("ارتباط با سرور برقرار نشد."); });
          return;
        }
        if (act === "delete") {
          if (!confirm("سوابقِ ورودِ این دستگاه از فهرست حذف شود؟ (این دستگاه بلاک نمی‌شود و در صورتِ بازدیدِ دوباره، از نو ثبت می‌شود)")) return;
          apiPost("/api/panel/principal-devices/delete", { device_id: did })
            .then(function (res) {
              if (!res.ok) { alert("خطا در حذف سوابق."); return; }
              state.principalDeviceOpen = null;
              renderPrincipalDevices();
            }).catch(function () { alert("ارتباط با سرور برقرار نشد."); });
          return;
        }
      });
      if (state.principalDeviceOpen) loadPrincipalDeviceDetail(state.principalDeviceOpen);
    });
  }

  // ── دستیار: فهرست گفتگوها + نمای هر گفتگو (فقط‌خواندنی) ──────────
  var ASSISTANT_SOURCES = [
    ["all", "همه"], ["principal", "🏫 مدیر مدرسه"], ["admins", "👤 مدیران"],
  ];

  function assistantSourceBadge(source) {
    return source === "principal"
      ? '<span class="badge draw">🏫 مدیر مدرسه</span>'
      : '<span class="badge pending">👤 مدیران</span>';
  }

  function renderAssistantList() {
    setBody(
      '<div class="section">' +
        '<div class="tabs" id="assistant-tabs">' +
          ASSISTANT_SOURCES.map(function (t) {
            return tabBtn(t[0], t[1], state.assistantSource === t[0]);
          }).join("") +
        '</div>' +
        '<div class="search-box">' +
          '<input type="text" id="assistant-search" placeholder="جستجو در عنوان و متن گفتگوها…" autocomplete="off" value="' + esc(state.assistantQuery) + '">' +
          '<span class="search-ic">🔍</span>' +
        '</div>' +
        '<div class="section-head"><h3>گفتگوهای رهگشا</h3><span class="count" id="assistant-count"></span></div>' +
        '<div class="card-list" id="assistant-list"><div class="loading-state"><span class="spinner"></span></div></div>' +
      '</div>');

    var listEl = document.getElementById("assistant-list");
    var countEl = document.getElementById("assistant-count");
    var searchEl = document.getElementById("assistant-search");
    var seq = 0;

    function load() {
      var mySeq = ++seq;
      var url = "/api/panel/assistant?source=" + encodeURIComponent(state.assistantSource) +
                "&q=" + encodeURIComponent(state.assistantQuery);
      api(url).then(function (d) {
        if (mySeq !== seq || !document.body.contains(listEl)) return; // جواب کهنه
        if (!d.ok) return;
        countEl.textContent = d.sessions.length + " گفتگو";
        if (!d.sessions.length) {
          listEl.innerHTML = '<div class="empty-state">' +
            (state.assistantQuery ? "گفتگویی با این جستجو پیدا نشد" : "گفتگویی با رهگشا ثبت نشده") + '</div>';
          return;
        }
        listEl.innerHTML = d.sessions.map(function (x) {
          return '<div class="row-card chat-row" data-sid="' + x.id + '">' +
            '<div class="chat-row-main">' +
              '<div class="main-txt chat-row-title">' + esc(x.title || "بدون عنوان") + '</div>' +
              '<div class="sub-txt">' + esc(x.owner) + ' · ' + fmtDate(x.last_message_at) + ' · ' + x.msg_count + ' پیام</div>' +
            '</div>' +
            assistantSourceBadge(x.source) +
          '</div>';
        }).join("");
      }).catch(function () {});
    }

    document.getElementById("assistant-tabs").addEventListener("click", function (e) {
      var btn = e.target.closest(".tab-btn"); if (!btn) return;
      state.assistantSource = btn.getAttribute("data-period");
      document.querySelectorAll("#assistant-tabs .tab-btn").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
      load();
    });

    var debounce = null;
    searchEl.addEventListener("input", function () {
      clearTimeout(debounce);
      debounce = setTimeout(function () {
        state.assistantQuery = searchEl.value.trim();
        load();
      }, 250);
    });

    listEl.addEventListener("click", function (e) {
      var row = e.target.closest(".chat-row"); if (!row) return;
      state.assistantSession = Number(row.getAttribute("data-sid"));
      render();
    });

    load();
  }

  function assistantBubble(m) {
    var when = '<div class="chat-time">' + fmtDate(m.sent_at) + '</div>';
    if (m.sender === "tool") {
      var text = String(m.text || "");
      var cut = text.indexOf(" → ");
      var head = cut === -1 ? text : text.slice(0, cut);
      if (head.length > 70) head = head.slice(0, 70) + "…";
      return '<div class="chat-msg chat-tool"><details><summary>' + esc(head) + '</summary>' +
        '<div class="chat-tool-body">' + esc(text) + '</div></details>' + when + '</div>';
    }
    if (m.sender === "user") {
      return '<div class="chat-msg chat-user"><div class="chat-bubble-txt">' + esc(m.text) + '</div>' + when + '</div>';
    }
    if (m.sender === "system") {
      return '<div class="chat-msg chat-system"><div class="chat-bubble-txt">' + esc(m.text) + '</div>' + when + '</div>';
    }
    return '<div class="chat-msg chat-ai"><div class="chat-bubble-txt">🤖 ' + esc(m.text) + '</div>' + when + '</div>';
  }

  function renderAssistantChat(sid) {
    body.innerHTML = '<div class="loading-state"><span class="spinner"></span></div>';
    api("/api/panel/assistant/" + sid).then(function (d) {
      if (!d.ok) { state.assistantSession = null; render(); return; }
      var sess = d.session;
      document.getElementById("view-title").textContent = "گفتگوی رهگشا";
      setBody(
        '<button class="back-btn" id="assistant-back">→ بازگشت به فهرست گفتگوها</button>' +
        '<div class="settings-card chat-head">' +
          '<div class="main-txt">' + esc(sess.title || "بدون عنوان") + '</div>' +
          '<div class="sub-txt">' + assistantSourceBadge(sess.source) + ' ' + esc(sess.owner) +
            ' · شروع: ' + fmtDate(sess.started_at) + ' · ' + d.messages.length + ' پیام</div>' +
        '</div>' +
        '<div class="chat-thread">' +
          (d.messages.length ? d.messages.map(assistantBubble).join("") : '<div class="empty-state">پیامی ثبت نشده</div>') +
        '</div>' +
        '<button class="tab-btn chat-refresh" id="assistant-refresh">🔄 به‌روزرسانی</button>'
      );
      document.getElementById("assistant-back").addEventListener("click", function () {
        state.assistantSession = null;
        document.getElementById("view-title").textContent = VIEW_TITLES.assistant;
        render();
      });
      document.getElementById("assistant-refresh").addEventListener("click", function () {
        renderAssistantChat(sid);
      });
    }).catch(function () {});
  }

  function manualSlot(item) {
    if (!item) return '<div class="slot-card empty">خالی</div>';
    return (
      '<div class="slot-card filled" data-pid="' + item.player_id + '">' +
        '<div class="top-rank">' + item.rank + '</div>' +
        '<div class="top-info">' +
          '<div class="main-txt">' + esc(item.full_name) + '</div>' +
          '<div class="sub-txt">' + esc(item.class_name) + '</div>' +
        '</div>' +
        '<button class="slot-remove" data-pid="' + item.player_id + '" title="حذف">✕</button>' +
      '</div>'
    );
  }

  function renderTopManual() {
    body.innerHTML = '<div class="loading-state"><span class="spinner"></span></div>';
    Promise.all([api("/api/panel/top-manual"), api("/api/panel/top-candidates")]).then(function (results) {
      var manualData = results[0], candData = results[1];
      drawTopManual(manualData.list || [], candData.players || []);
    });
  }

  function drawTopManual(manualList, candidates) {
    var byRank = {};
    manualList.forEach(function (i) { byRank[i.rank] = i; });
    var slots = [1, 2, 3, 4, 5].map(function (r) { return manualSlot(byRank[r]); }).join("");

    setBody(
      '<button class="back-btn" id="top-manual-back">→ بازگشت به تنظیمات</button>' +
      '<div class="section-title">۵ نفر برتر فعلی</div>' +
      '<div class="card-list slot-list" id="slot-list">' + slots + '</div>' +
      '<div class="section-title">👥 انتخاب از بین بازیکن‌های فعال (به ترتیبِ پیشنهادِ ربات)</div>' +
      '<div class="search-box">' +
        '<input type="text" id="candidates-search" placeholder="جستجوی نام بازیکن یا کلاس…" autocomplete="off">' +
        '<span class="search-ic">🔍</span>' +
      '</div>' +
      '<div class="card-list" id="candidates-list"></div>'
    );

    document.getElementById("top-manual-back").addEventListener("click", function () {
      state.topManualView = false;
      document.getElementById("view-title").textContent = VIEW_TITLES.settings;
      render();
    });

    document.getElementById("slot-list").addEventListener("click", function (e) {
      var btn = e.target.closest(".slot-remove");
      if (!btn) return;
      var pid = btn.getAttribute("data-pid");
      apiPost("/api/panel/top-manual-remove", { player_id: Number(pid) }).then(function (res) {
        return api("/api/panel/top-candidates").then(function (candData) {
          drawTopManual(res.list || [], candData.players || []);
        });
      }).catch(function () { alert("خطا در حذف. دوباره تلاش کنید."); });
    });

    var listEl = document.getElementById("candidates-list");
    var searchEl = document.getElementById("candidates-search");
    var openPid = null;

    function candidateRow(p) {
      var taken = !!p.manual_rank;
      return (
        '<div class="row-card candidate-row" data-pid="' + p.id + '">' +
          '<div>' +
            '<div class="main-txt">' + (taken ? "✅ " : "") + esc(p.full_name) +
              (taken ? ' <span class="rank-badge">رتبه ' + p.manual_rank + '</span>' : "") + '</div>' +
            '<div class="sub-txt">' + esc(p.class_name) + ' · ' + esc(p.games) + ' بازی · امتیاز ' + esc(p.score) + '</div>' +
          '</div>' +
          '<div class="badge-group">' +
            '<span class="badge win">' + esc(p.wins) + '</span>' +
            '<span class="badge draw">' + esc(p.draws) + '</span>' +
            '<span class="badge loss">' + esc(p.losses) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="rank-picker" id="rank-picker-' + p.id + '" hidden>' +
          '<span class="rank-picker-lbl">این بازیکن از پنج نفر برتر چندم باشد؟</span>' +
          '<div class="rank-picker-btns">' +
            [1, 2, 3, 4, 5].map(function (r) {
              return '<button class="rank-num-btn' + (p.manual_rank === r ? " active" : "") +
                '" data-pid="' + p.id + '" data-rank="' + r + '">' + r + '</button>';
            }).join("") +
          '</div>' +
        '</div>'
      );
    }

    function draw() {
      var q = searchEl.value.trim().toLowerCase();
      var rows = q
        ? candidates.filter(function (p) {
            return (p.full_name || "").toLowerCase().indexOf(q) !== -1 ||
                   (p.class_name || "").toLowerCase().indexOf(q) !== -1;
          })
        : candidates;
      listEl.innerHTML = rows.length ? rows.map(candidateRow).join("") : '<div class="empty-state">بازیکنی یافت نشد.</div>';
    }

    listEl.addEventListener("click", function (e) {
      var rankBtn = e.target.closest(".rank-num-btn");
      if (rankBtn) {
        var pid = Number(rankBtn.getAttribute("data-pid"));
        var rank = Number(rankBtn.getAttribute("data-rank"));
        apiPost("/api/panel/top-manual-set", { player_id: pid, rank: rank }).then(function (res) {
          return api("/api/panel/top-candidates").then(function (candData) {
            openPid = null;
            drawTopManual(res.list || [], candData.players || []);
          });
        }).catch(function () { alert("خطا در ثبتِ رتبه. دوباره تلاش کنید."); });
        return;
      }
      var row = e.target.closest(".candidate-row");
      if (!row) return;
      var pid = row.getAttribute("data-pid");
      var picker = document.getElementById("rank-picker-" + pid);
      var wasOpen = openPid === pid;
      document.querySelectorAll(".rank-picker").forEach(function (p) { p.hidden = true; });
      openPid = wasOpen ? null : pid;
      if (picker) picker.hidden = wasOpen;
    });

    searchEl.addEventListener("input", draw);
    draw();
  }

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
