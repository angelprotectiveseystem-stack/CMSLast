(function () {
  "use strict";

  var TOKEN_KEY = "chess_panel_token";
  var POLL_MS = 4000; // زنده بدون فشار به سرور: هر ۴ ثانیه فقط GET های سبک
  var state = { view: "home", timer: null, activityPage: 0, topManualView: false,
                assistantSession: null, assistantSource: "all", assistantQuery: "",
                principalDeviceOpen: null,
                statHistory: {}, prevOnlineNames: null, prevFeedbackCount: null, pollTick: 0,
                assistantPanelSession: null };

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
    "principal-devices": "ورودهای مدیر مدرسه", notifications: "ارسال اعلان",
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
    closeMoreSheet();
    updateNavIndicator();
    updateBnIndicator();
    updateAssistantFabVisibility();

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
        if (document.getElementById("more-sheet").classList.contains("show")) closeMoreSheet(); else openMoreSheet();
        return;
      }
      var btn = e.target.closest(".bn-item[data-view]");
      if (!btn) return;
      goToView(btn.getAttribute("data-view"));
    });
  }

  // ── منوی «بیشتر»: شیت پایین با گروه‌بندی، جای درآور کاملِ سایدبار ──
  var moreSheetEl = document.getElementById("more-sheet");
  var moreBackdropEl = document.getElementById("more-backdrop");
  function openMoreSheet() {
    if (!moreSheetEl) return;
    moreSheetEl.classList.add("show");
    moreBackdropEl.classList.add("show");
    document.body.classList.add("no-scroll");
    var moreBtn = document.querySelector(".bn-more");
    if (moreBtn) moreBtn.classList.add("menu-open");
  }
  function closeMoreSheet() {
    if (!moreSheetEl) return;
    moreSheetEl.classList.remove("show");
    moreBackdropEl.classList.remove("show");
    document.body.classList.remove("no-scroll");
    var moreBtn = document.querySelector(".bn-more");
    if (moreBtn) moreBtn.classList.remove("menu-open");
    // با هر بار بسته‌شدن، انیمیشنِ ورودِ کاشی‌ها دوباره ری‌ست بشه تا
    // دفعه‌ی بعد که باز می‌شه دوباره پلکانی و زنده اجرا بشه.
    document.querySelectorAll(".more-tile").forEach(function (t) {
      t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
    });
  }
  if (moreSheetEl) {
    moreSheetEl.addEventListener("click", function (e) {
      var actionTile = e.target.closest(".more-tile[data-action]");
      if (actionTile) {
        var action = actionTile.getAttribute("data-action");
        if (action === "toggle-theme") toggleTheme();
        if (action === "toggle-sound") toggleSound();
        return;
      }
      var tile = e.target.closest(".more-tile[data-view]");
      if (!tile) return;
      goToView(tile.getAttribute("data-view"));
    });
  }
  if (moreBackdropEl) moreBackdropEl.addEventListener("click", closeMoreSheet);

  // ── دکمه‌ی جمع/بازکردنِ منوی اول (فقط دسکتاپ) ────────────────
  var sidebarCollapseBtn = document.getElementById("sidebar-collapse-btn");
  if (sidebarCollapseBtn) sidebarCollapseBtn.addEventListener("click", toggleSidebarCollapsed);

  // ── دکمه‌های پوسته/صدا در پایینِ سایدبار ─────────────────────
  var themeToggleBtn = document.getElementById("theme-toggle-btn");
  if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);
  var soundToggleBtn = document.getElementById("sound-toggle-btn");
  if (soundToggleBtn) soundToggleBtn.addEventListener("click", toggleSound);

  // ── دکمه‌ی شناور رهگشا + پنل کناری سریع ──────────────────────
  var assistantFab = document.getElementById("assistant-fab");
  var assistantPanel = document.getElementById("assistant-panel");
  var assistantPanelBackdrop = document.getElementById("assistant-panel-backdrop");
  var assistantPanelBody = document.getElementById("assistant-panel-body");
  var assistantPanelBack = document.getElementById("assistant-panel-back");
  var assistantPanelTitle = document.querySelector(".assistant-panel-title");

  function updateAssistantFabVisibility() {
    if (assistantFab) assistantFab.classList.toggle("hidden-fab", state.view === "assistant");
  }
  function openAssistantPanel() {
    if (!assistantPanel) return;
    assistantPanel.classList.add("show");
    assistantPanelBackdrop.classList.add("show");
    document.body.classList.add("no-scroll");
    renderAssistantPanelList();
  }
  function closeAssistantPanel() {
    if (!assistantPanel) return;
    assistantPanel.classList.remove("show");
    assistantPanelBackdrop.classList.remove("show");
    document.body.classList.remove("no-scroll");
    state.assistantPanelSession = null;
  }
  function renderAssistantPanelList() {
    state.assistantPanelSession = null;
    assistantPanelBack.classList.add("hidden");
    assistantPanelTitle.textContent = "🤖 رهگشا — گفتگوهای اخیر";
    assistantPanelBody.innerHTML = '<div class="loading-state"><span class="spinner"></span></div>';
    api("/api/panel/assistant?source=all&q=").then(function (d) {
      if (!d.ok) return;
      var sessions = d.sessions.slice(0, 8);
      if (!sessions.length) {
        assistantPanelBody.innerHTML = '<div class="empty-state">گفتگویی با رهگشا ثبت نشده</div>';
        return;
      }
      assistantPanelBody.innerHTML = sessions.map(function (x) {
        return '<button class="assistant-panel-item" data-sid="' + x.id + '">' +
          '<div class="assistant-panel-item-title">' + esc(x.title || "بدون عنوان") + '</div>' +
          '<div class="assistant-panel-item-meta">' + esc(x.owner) + ' · ' + fmtDate(x.last_message_at) + ' · ' + x.msg_count + ' پیام</div>' +
        '</button>';
      }).join("");
    }).catch(function () {
      assistantPanelBody.innerHTML = '<div class="empty-state">خطا در دریافتِ گفتگوها</div>';
    });
  }
  function renderAssistantPanelChat(sid) {
    state.assistantPanelSession = sid;
    assistantPanelBack.classList.remove("hidden");
    assistantPanelBody.innerHTML = '<div class="loading-state"><span class="spinner"></span></div>';
    api("/api/panel/assistant/" + sid).then(function (d) {
      if (!d.ok) { renderAssistantPanelList(); return; }
      var sess = d.session;
      assistantPanelTitle.textContent = esc(sess.title || "گفتگو");
      assistantPanelBody.innerHTML = (d.messages || []).map(assistantBubble).join("") ||
        '<div class="empty-state">پیامی ثبت نشده</div>';
      assistantPanelBody.scrollTop = assistantPanelBody.scrollHeight;
    }).catch(function () {
      assistantPanelBody.innerHTML = '<div class="empty-state">خطا در دریافتِ گفتگو</div>';
    });
  }
  if (assistantFab) assistantFab.addEventListener("click", openAssistantPanel);
  var assistantPanelClose = document.getElementById("assistant-panel-close");
  if (assistantPanelClose) assistantPanelClose.addEventListener("click", closeAssistantPanel);
  if (assistantPanelBackdrop) assistantPanelBackdrop.addEventListener("click", closeAssistantPanel);
  if (assistantPanelBack) assistantPanelBack.addEventListener("click", renderAssistantPanelList);
  if (assistantPanelBody) {
    assistantPanelBody.addEventListener("click", function (e) {
      var item = e.target.closest(".assistant-panel-item[data-sid]");
      if (!item) return;
      renderAssistantPanelChat(Number(item.getAttribute("data-sid")));
    });
  }
  var assistantPanelFullBtn = document.getElementById("assistant-panel-full");
  if (assistantPanelFullBtn) {
    assistantPanelFullBtn.addEventListener("click", function () {
      if (state.assistantPanelSession) state.assistantSession = state.assistantPanelSession;
      closeAssistantPanel();
      goToView("assistant");
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && assistantPanel && assistantPanel.classList.contains("show")) closeAssistantPanel();
  });

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
    if (e.key === "Escape") { closeSidebar(); closeMoreSheet(); }
  });
  // اگر صفحه بزرگ‌تر از حالت موبایل شد (چرخش صفحه یا تغییر اندازه)،
  // هر باقیمانده‌ای از حالت باز/بک‌دراپ رو پاک کن تا قفل چیدمان دسکتاپ رو نگیره
  window.addEventListener("resize", function () {
    if (window.innerWidth > 860) { closeSidebar(); closeMoreSheet(); }
    updateNavIndicator();
    updateBnIndicator();
  });

  // ── نشانگرهای لغزان: هایلایتِ آیتم فعال در «منوی اول» و نوار کپسولی ──
  // به‌جای رنگ‌آمیزیِ لحظه‌ای، یک پیل/نوار همراه با انتقال نرم (transform)
  // بین آیتم‌ها جابه‌جا می‌شود تا حس یک ناوبری زنده و یک‌پارچه بدهد.
  function updateNavIndicator() {
    var nav = document.getElementById("nav");
    var indicator = nav ? nav.querySelector(".nav-indicator") : null;
    if (!nav || !indicator) return;
    var active = nav.querySelector(".nav-item.active");
    if (!active || nav.classList.contains("filtering")) { indicator.classList.remove("ready"); return; }
    var y = active.offsetTop, h = active.offsetHeight;
    indicator.style.transform = "translateY(" + y + "px)";
    indicator.style.height = h + "px";
    indicator.classList.add("ready");
  }
  function updateBnIndicator() {
    var bar = document.getElementById("bottom-nav");
    var indicator = bar ? bar.querySelector(".bn-indicator") : null;
    if (!bar || !indicator) return;
    var active = bar.querySelector(".bn-item.active[data-view]");
    if (!active) { indicator.classList.remove("ready"); return; }
    var x = active.offsetLeft, w = active.offsetWidth;
    var barBox = bar.getBoundingClientRect();
    if (barBox.width === 0) { indicator.classList.remove("ready"); return; } // پنهانه (دسکتاپ)، محاسبه بی‌فایده‌ست
    indicator.style.transform = "translateX(" + x + "px)";
    indicator.style.width = w + "px";
    indicator.classList.add("ready");
  }

  // ── جستجوی سریع بخش‌ها در «منوی اول» ─────────────────────────────
  var navSearchEl = document.getElementById("nav-search");
  if (navSearchEl) {
    navSearchEl.addEventListener("input", function () {
      var q = navSearchEl.value.trim().toLowerCase();
      var nav = document.getElementById("nav");
      var emptyEl = document.getElementById("nav-empty");
      nav.classList.toggle("filtering", !!q);
      updateNavIndicator();
      if (!q) {
        document.querySelectorAll(".nav-item, .nav-group-label").forEach(function (n) { n.classList.remove("hidden"); });
        if (emptyEl) emptyEl.classList.add("hidden");
        return;
      }
      var anyVisible = false;
      var groups = document.querySelectorAll(".nav-group-label");
      groups.forEach(function (g) {
        var groupVisible = false;
        var el = g.nextElementSibling;
        while (el && el.classList.contains("nav-item")) {
          var match = el.textContent.toLowerCase().indexOf(q) !== -1;
          el.classList.toggle("hidden", !match);
          if (match) { groupVisible = true; anyVisible = true; }
          el = el.nextElementSibling;
        }
        g.classList.toggle("hidden", !groupVisible);
      });
      if (emptyEl) emptyEl.classList.toggle("hidden", anyVisible);
    });
    // میانبر «/» برای فوکوس سریع روی جستجو (وقتی داخل ورودی دیگه‌ای نیستیم)
    document.addEventListener("keydown", function (e) {
      if (e.key !== "/") return;
      var tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      if (window.innerWidth <= 860) return; // روی موبایل سایدبار پنهانه
      e.preventDefault();
      navSearchEl.focus();
    });
    navSearchEl.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { navSearchEl.value = ""; navSearchEl.dispatchEvent(new Event("input")); navSearchEl.blur(); }
    });
  }

  // ── بج‌های زنده: تعداد مدیرانِ آنلاین کنار آیتم «آنلاین‌ها» ─────────
  function updateOnlineBadge(count) {
    [document.getElementById("nav-badge-online"), document.getElementById("more-badge-online")].forEach(function (b) {
      if (!b) return;
      b.textContent = count;
      b.classList.toggle("hidden", !count);
    });
  }

  // ── پوسته‌ی روشن/تاریک ──────────────────────────────────
  var THEME_KEY = "panel_theme";
  function applyTheme(theme) {
    if (theme === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
  }
  function getTheme() {
    try { return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"; } catch (e) { return "dark"; }
  }
  function toggleTheme() {
    var next = getTheme() === "light" ? "dark" : "light";
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    applyTheme(next);
    syncMoreTiles();
  }

  // ── صدا و لرزش برای اعلان‌های لحظه‌ای ────────────────────
  // به‌جای فایل صوتی، یک «دینگِ» خیلی کوتاه با Web Audio می‌سازیم؛
  // این‌طوری هیچ دانلود/دارایی اضافه‌ای لازم نیست.
  var SOUND_KEY = "panel_sound_on";
  function isSoundOn() {
    try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch (e) { return true; }
  }
  function toggleSound() {
    var next = isSoundOn() ? "off" : "on";
    try { localStorage.setItem(SOUND_KEY, next); } catch (e) {}
    syncSoundBtn();
  }
  function syncSoundBtn() {
    var btn = document.getElementById("sound-toggle-btn");
    if (btn) btn.classList.toggle("is-off", !isSoundOn());
    syncMoreTiles();
  }
  function syncMoreTiles() {
    var themeTile = document.getElementById("more-tile-theme");
    if (themeTile) {
      var light = getTheme() === "light";
      themeTile.querySelector(".more-tile-ic").textContent = light ? "☀️" : "🌙";
      themeTile.querySelector(".more-tile-label").textContent = light ? "پوسته‌ی تاریک" : "پوسته‌ی روشن";
    }
    var soundTile = document.getElementById("more-tile-sound");
    if (soundTile) {
      var on = isSoundOn();
      soundTile.querySelector(".more-tile-ic").textContent = on ? "🔔" : "🔕";
      soundTile.querySelector(".more-tile-label").textContent = on ? "صدا و لرزش: روشن" : "صدا و لرزش: خاموش";
    }
  }
  var audioCtx = null;
  function playChime() {
    if (!isSoundOn()) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      var t = audioCtx.currentTime;
      var osc = audioCtx.createOscillator();
      var gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(830, t);
      osc.frequency.exponentialRampToValueAtTime(1100, t + 0.11);
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.09, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
      osc.connect(gain); gain.connect(audioCtx.destination);
      osc.start(t); osc.stop(t + 0.34);
    } catch (e) {}
  }
  function buzz() {
    if (!isSoundOn()) return;
    if (navigator.vibrate) { try { navigator.vibrate(18); } catch (e) {} }
  }

  // ── نوتیف‌های لحظه‌ای (Toast) ─────────────────────────────
  function showToast(text, opts) {
    opts = opts || {};
    var stack = document.getElementById("toast-stack");
    if (!stack) return;
    var el = document.createElement("div");
    el.className = "toast" + (opts.tone ? " toast-" + opts.tone : "");
    el.innerHTML = '<span class="toast-ic">' + (opts.icon || "🔔") + '</span><span class="toast-txt"></span>';
    el.querySelector(".toast-txt").textContent = text;
    stack.appendChild(el);
    playChime(); buzz();
    setTimeout(function () {
      el.classList.add("toast-leaving");
      setTimeout(function () { el.remove(); }, 240);
    }, opts.duration || 4200);
    // حداکثر ۴ تا هم‌زمان؛ قدیمی‌ترین‌ها زودتر جمع می‌شن
    while (stack.children.length > 4) stack.removeChild(stack.firstChild);
  }

  // ── اسکلتون لودینگ ────────────────────────────────────────
  // بسته به نوعِ صفحه (کارت‌های آماری، لیست، یا جدول)، یک قالبِ
  // نزدیک به شکلِ محتوای واقعی نشون می‌ده تا حسِ سریع‌تر بارگذاری بده.
  function skeletonGrid(n) {
    var cards = "";
    for (var i = 0; i < n; i++) {
      cards += '<div class="skeleton-card"><div class="skeleton-line"></div><div class="skeleton-block"></div></div>';
    }
    return '<div class="skeleton-grid">' + cards + '</div>';
  }
  function skeletonRows(n) {
    var rows = "";
    for (var i = 0; i < n; i++) {
      rows += '<div class="skeleton-row"><div class="skeleton-block skeleton-avatar"></div><div class="skeleton-lines"><div class="skeleton-line"></div><div class="skeleton-line"></div></div></div>';
    }
    return '<div class="skeleton-section">' + rows + '</div>';
  }
  var SKELETON_BY_VIEW = {
    home: function () { return skeletonGrid(7) + skeletonRows(3); },
    matches: skeletonRows.bind(null, 6), players: skeletonRows.bind(null, 6),
    elo: skeletonRows.bind(null, 6), admins: skeletonRows.bind(null, 5),
    online: skeletonRows.bind(null, 4), messages: skeletonRows.bind(null, 5),
    activity: skeletonRows.bind(null, 7), live: skeletonRows.bind(null, 4),
    notifications: skeletonRows.bind(null, 4),
    charts: function () { return skeletonRows(1) + skeletonRows(1) + skeletonRows(1); },
  };
  function skeletonFor(view) {
    var fn = SKELETON_BY_VIEW[view];
    return fn ? fn() : skeletonRows(5);
  }

  // ── تاریخچه‌ی محلیِ آمار برای ریز-نمودارِ روند (Sparkline) ────
  // چون بک‌اندی برای تاریخچه‌ی این آمارها نداریم، همون مقادیرِ
  // زنده‌ای که هرچند ثانیه از پولینگ می‌رسه رو محلی نگه می‌داریم.
  var SPARK_MAX_POINTS = 16;
  function pushStatHistory(key, value) {
    var h = state.statHistory[key] || (state.statHistory[key] = []);
    h.push(value);
    if (h.length > SPARK_MAX_POINTS) h.shift();
  }
  function sparkSVG(values) {
    if (!values || values.length < 2) return "";
    var w = 100, h = 22, pad = 2;
    var max = Math.max.apply(null, values), min = Math.min.apply(null, values);
    var range = (max - min) || 1;
    var stepX = (w - pad * 2) / (values.length - 1);
    var pts = values.map(function (v, i) {
      var x = pad + i * stepX;
      var y = h - pad - ((v - min) / range) * (h - pad * 2);
      return [x, y];
    });
    var line = "M" + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" L");
    var fill = line + " L" + pts[pts.length - 1][0].toFixed(1) + "," + h + " L" + pts[0][0].toFixed(1) + "," + h + " Z";
    return '<div class="stat-spark"><svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none">' +
      '<path class="spark-fill" d="' + fill + '"/><path class="spark-line" d="' + line + '"/></svg></div>';
  }

  // ── جمع/بازکردنِ منوی اول (سایدبار دسکتاپ) ────────────────
  var SIDEBAR_COLLAPSE_KEY = "panel_sidebar_collapsed";
  function applySidebarCollapsed(collapsed) {
    var sb = document.querySelector(".sidebar");
    if (sb) sb.classList.toggle("collapsed", !!collapsed);
  }
  function toggleSidebarCollapsed() {
    var sb = document.querySelector(".sidebar");
    var next = sb ? !sb.classList.contains("collapsed") : false;
    applySidebarCollapsed(next);
    try { localStorage.setItem(SIDEBAR_COLLAPSE_KEY, next ? "1" : "0"); } catch (e) {}
    requestAnimationFrame(function () { updateNavIndicator(); });
  }

  // ── میانبرهای کیبورد به‌سبکِ «g سپس یک حرف» (مثل گیت‌هاب) ────
  var KBD_CHORDS = {
    h: ["home", "خانه"], m: ["matches", "مسابقات"], p: ["players", "مسابقه‌دهنده‌ها"],
    l: ["live", "شطرنج زنده"], o: ["online", "آنلاین‌ها"], a: ["admins", "مدیر‌ها"],
    e: ["elo", "سطح پیشرفت"], c: ["charts", "نمودارها"], s: ["settings", "تنظیمات"],
  };
  var kbdHintEl = null, kbdChordActive = false, kbdChordTimer = null;
  function showKbdHint() {
    hideKbdHint();
    kbdHintEl = document.createElement("div");
    kbdHintEl.className = "kbd-hint";
    kbdHintEl.innerHTML = Object.keys(KBD_CHORDS).map(function (k) {
      return '<span><kbd>' + k + '</kbd>' + KBD_CHORDS[k][1] + '</span>';
    }).join("");
    document.body.appendChild(kbdHintEl);
  }
  function hideKbdHint() { if (kbdHintEl) { kbdHintEl.remove(); kbdHintEl = null; } }
  function initKeyboardChords() {
    document.addEventListener("keydown", function (e) {
      var tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (kbdChordActive) {
        clearTimeout(kbdChordTimer);
        var entry = KBD_CHORDS[e.key.toLowerCase()];
        kbdChordActive = false; hideKbdHint();
        if (entry) { e.preventDefault(); goToView(entry[0]); }
        return;
      }
      if (e.key.toLowerCase() === "g") {
        kbdChordActive = true;
        showKbdHint();
        kbdChordTimer = setTimeout(function () { kbdChordActive = false; hideKbdHint(); }, 1600);
      }
    });
  }

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

    // یک placeholder سبک که شکلِ محتوای واقعیِ همون صفحه رو تقلید
    // می‌کنه (اسکلتون) به‌جای فقط یک اسپینرِ خام — حسِ بارگذاریِ
    // سریع‌تر می‌ده و پرش کمتری با محتوای نهایی داره.
    body.classList.remove("fade-in");
    body.innerHTML = skeletonFor(state.view);

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
        updateOnlineBadge(s.admins_online);
        var onlineList = d.online_admins.map(function (a) {
          return '<div class="msg-item"><strong>' + esc(a.name) + '</strong> <span class="msg-meta">' + roleLabel(a.role) + '</span></div>';
        }).join("") || '<div class="empty-state">هیچ مدیری آنلاین نیست</div>';

        setBody(
          welcomeBanner() +
          '<div class="grid">' +
            statCard("مسابقه‌دهنده‌ها", s.players_total, "") +
            statCard("مدیران", s.admins_total, "") +
            statCard("مدیران آنلاین", s.admins_online, "accent-sage", state.statHistory.admins_online) +
            statCard("کل مسابقات", s.matches_total, "") +
            statCard("مسابقات در انتظار", s.matches_pending, "accent-rust", state.statHistory.matches_pending) +
            statCard("تورنومنت‌های فعال", s.tournaments_active, "") +
            statCard("شطرنج‌های زنده", s.live_games, "accent-sage", state.statHistory.live_games) +
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
        updateOnlineBadge(d.online.length);
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
    notifications: function () { renderNotifications(); },

    charts: function () {
      setBody(skeletonFor("charts"));
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
        requestAnimationFrame(function () { animateCharts(body); });
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

  // ── ارسال اعلان به پنل مدیر مدرسه ────────────────────────────────
  // فرمِ ساخت/ویرایش + فهرستِ اعلان‌های ارسال‌شده (با ویرایش و حذف).
  var notifState = { editingId: null, sending: false };

  function notifCard(n) {
    return (
      '<div class="row-card notif-card" data-nid="' + n.id + '">' +
        '<div class="chat-row-main">' +
          '<div class="main-txt chat-row-title">' + esc(n.title) + '</div>' +
          '<div class="sub-txt">' + esc(n.body) + '</div>' +
          '<div class="sub-txt">' + fmtDate(n.created_at) + (n.updated_at ? ' · ویرایش‌شده' : '') +
            ' · ' + (n.is_read ? '<span class="badge win">خوانده‌شده</span>' : '<span class="badge pending">خوانده‌نشده</span>') + '</div>' +
        '</div>' +
        '<div class="device-actions">' +
          '<button class="tab-btn" data-act="edit">✏️ ویرایش</button>' +
          '<button class="tab-btn device-btn-delete" data-act="delete">🗑 حذف</button>' +
        '</div>' +
      '</div>'
    );
  }

  function renderNotifications() {
    var maxTitle = 120, maxBody = 2000; // مقادیرِ واقعی بعد از اولین بارگذاری از سرور می‌آید
    setBody(
      '<div class="section">' +
        '<div class="section-head"><h3 id="notif-form-title">ارسال اعلان به پنل مدیر مدرسه</h3></div>' +
        '<form id="notif-form" class="notif-form">' +
          '<label class="notif-field">' +
            '<span>عنوان</span>' +
            '<input type="text" id="notif-title" maxlength="' + maxTitle + '" placeholder="مثلاً: تعطیلی فردا" autocomplete="off">' +
          '</label>' +
          '<label class="notif-field">' +
            '<span>متن اعلان</span>' +
            '<textarea id="notif-body" maxlength="' + maxBody + '" rows="4" placeholder="متنِ کامل اعلان را اینجا بنویسید…"></textarea>' +
          '</label>' +
          '<div id="notif-error" class="notif-error" hidden></div>' +
          '<div class="notif-form-actions">' +
            '<button type="submit" id="notif-submit">ارسال اعلان</button>' +
            '<button type="button" id="notif-cancel" hidden>انصراف از ویرایش</button>' +
          '</div>' +
          '<div id="notif-push-note" class="sub-txt notif-push-note"></div>' +
        '</form>' +
      '</div>' +
      '<div class="section">' +
        '<div class="section-head"><h3>اعلان‌های ارسال‌شده</h3><span class="count" id="notif-count"></span></div>' +
        '<div class="card-list" id="notif-list"><div class="loading-state"><span class="spinner"></span></div></div>' +
      '</div>'
    );

    var formEl = document.getElementById("notif-form");
    var titleEl = document.getElementById("notif-title");
    var bodyEl = document.getElementById("notif-body");
    var errEl = document.getElementById("notif-error");
    var submitEl = document.getElementById("notif-submit");
    var cancelEl = document.getElementById("notif-cancel");
    var listEl = document.getElementById("notif-list");
    var countEl = document.getElementById("notif-count");
    var pushNoteEl = document.getElementById("notif-push-note");
    var formTitleEl = document.getElementById("notif-form-title");

    function setEditing(n) {
      notifState.editingId = n ? n.id : null;
      titleEl.value = n ? n.title : "";
      bodyEl.value = n ? n.body : "";
      formTitleEl.textContent = n ? "ویرایش اعلان" : "ارسال اعلان به پنل مدیر مدرسه";
      submitEl.textContent = n ? "ذخیره‌ی ویرایش" : "ارسال اعلان";
      cancelEl.hidden = !n;
      errEl.hidden = true;
      if (n) titleEl.focus();
    }

    cancelEl.addEventListener("click", function () { setEditing(null); });

    var currentItems = [];
    // یک شنوندهٔ ثابت (نه یکی به‌ازای هر بارگذاری) که همیشه به آخرین فهرست نگاه می‌کند.
    listEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-act]");
      if (!btn) return;
      var card = btn.closest(".notif-card");
      var nid = +card.getAttribute("data-nid");
      var act = btn.getAttribute("data-act");
      if (act === "edit") {
        var n = currentItems.filter(function (x) { return x.id === nid; })[0];
        if (n) setEditing(n);
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (act === "delete") {
        if (!confirm("این اعلان حذف شود؟ از پنل مدیر مدرسه هم پاک می‌شود.")) return;
        apiPost("/api/panel/notifications/delete", { id: nid }).then(function (res) {
          if (!res.ok) { alert(res.error || "خطا در حذف اعلان."); return; }
          if (notifState.editingId === nid) setEditing(null);
          load();
        }).catch(function () { alert("ارتباط با سرور برقرار نشد."); });
      }
    });

    function load() {
      api("/api/panel/notifications").then(function (d) {
        if (!d.ok) return;
        titleEl.maxLength = d.max_title;
        bodyEl.maxLength = d.max_body;
        pushNoteEl.textContent = d.push_available
          ? (d.subscribers
              ? "اعلان روی گوشیِ " + d.subscribers + " دستگاهِ مدیرِ مدرسه هم ارسال می‌شود."
              : "مدیر مدرسه هنوز اجازه‌ی ارسال اعلان روی گوشی را تأیید نکرده؛ فعلاً اعلان فقط داخل پنل او دیده می‌شود.")
          : "ارسال به گوشی روی این سرور فعال نیست؛ اعلان همچنان داخل پنل مدیر مدرسه دیده می‌شود.";

        currentItems = d.items;
        countEl.textContent = d.items.length + " مورد";
        listEl.innerHTML = d.items.length
          ? d.items.map(notifCard).join("")
          : '<div class="empty-state">هنوز اعلانی ارسال نشده</div>';
        if (notifState.editingId && !d.items.some(function (n) { return n.id === notifState.editingId; })) {
          setEditing(null); // اعلانی که در حال ویرایشش بودیم از جای دیگری حذف شده
        }
      }).catch(function () { listEl.innerHTML = '<div class="empty-state">خطا در بارگذاری</div>'; });
    }

    formEl.addEventListener("submit", function (e) {
      e.preventDefault();
      if (notifState.sending) return;
      var title = titleEl.value.trim();
      var body = bodyEl.value.trim();
      if (!title || !body) {
        errEl.textContent = !title ? "عنوانِ اعلان را وارد کنید." : "متنِ اعلان را وارد کنید.";
        errEl.hidden = false;
        return;
      }
      notifState.sending = true;
      submitEl.disabled = true;
      var editingId = notifState.editingId;
      var path = editingId ? "/api/panel/notifications/update" : "/api/panel/notifications/send";
      var payload = editingId ? { id: editingId, title: title, body: body } : { title: title, body: body };
      apiPost(path, payload).then(function (res) {
        if (!res.ok) { errEl.textContent = res.error || "ارسال با خطا مواجه شد."; errEl.hidden = false; return; }
        showToast(editingId ? "اعلان ویرایش شد" : "اعلان ارسال شد", { icon: "🔔" });
        setEditing(null);
        load();
      }).catch(function () { errEl.textContent = "ارتباط با سرور برقرار نشد."; errEl.hidden = false; })
        .then(function () { notifState.sending = false; submitEl.disabled = false; });
    });

    setEditing(null);
    load();
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

  function statCard(label, value, accentClass, sparkValues) {
    return '<div class="stat-card ' + accentClass + '"><div class="stat-label">' + label + '</div><div class="stat-value">' + value + '</div>' +
      (sparkValues ? sparkSVG(sparkValues) : '') + '</div>';
  }
  function tabBtn(period, label, active) {
    return '<button class="tab-btn' + (active ? " active" : "") + '" data-period="' + period + '">' + label + '</button>';
  }
  function fmtClock(seconds) {
    if (seconds == null) return "—";
    var m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function animateCharts(root) {
    if (!root) return;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    root.querySelectorAll(".chart-wrap").forEach(function (wrap) {
      var bars = wrap.querySelectorAll(".bar-fill");
      bars.forEach(function (b) {
        var target = b.style.width;
        if (reduce) return;
        b.style.width = "0%";
        void b.offsetWidth;
        requestAnimationFrame(function () { b.style.width = target; });
      });
      var linePath = wrap.querySelector(".sparkline path");
      if (linePath && !reduce) {
        try {
          var len = linePath.getTotalLength();
          linePath.style.strokeDasharray = len;
          linePath.style.strokeDashoffset = len;
          void linePath.offsetWidth;
          requestAnimationFrame(function () { linePath.style.strokeDashoffset = 0; });
        } catch (e) {}
      }
      wrap.classList.add("charts-animate");
    });
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
    state.pollTick++;
    api("/api/panel/overview").then(function (d) {
      if (d.ok) { el.textContent = "زنده و به‌روز"; dot.classList.remove("off"); }
      if (d.ok && d.stats) {
        pushStatHistory("admins_online", d.stats.admins_online);
        pushStatHistory("live_games", d.stats.live_games);
        pushStatHistory("matches_pending", d.stats.matches_pending);
        updateOnlineBadge(d.stats.admins_online);

        // تشخیصِ مدیرِ تازه‌آنلاین‌شده برای نمایشِ toast
        var names = (d.online_admins || []).map(function (a) { return a.name; });
        if (state.prevOnlineNames) {
          names.forEach(function (n) {
            if (state.prevOnlineNames.indexOf(n) === -1) {
              showToast(n + " آنلاین شد", { icon: "🟢", tone: "sage" });
            }
          });
        }
        state.prevOnlineNames = names;
      }
      if (state.view === "home" || state.view === "live" || state.view === "online" || state.view === "admins") {
        render(true);
      }
    }).catch(function () {
      el.textContent = "قطع ارتباط"; dot.classList.add("off");
    });

    // هر ۴ تیک (~۱۶ ثانیه) یه سرِ سبک به تعدادِ بازخوردهای جدید می‌زنیم
    // تا بدونِ فشار به سرور، از بازخوردِ تازه هم toast نشون بدیم.
    if (state.pollTick % 4 === 0 && state.view !== "messages") {
      api("/api/panel/messages").then(function (d) {
        if (!d.ok || !d.feedback) return;
        if (state.prevFeedbackCount != null && d.feedback.length > state.prevFeedbackCount) {
          showToast("بازخورد جدید دریافت شد", { icon: "💬" });
        }
        state.prevFeedbackCount = d.feedback.length;
      }).catch(function () {});
    }
  }

  function startApp() {
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    tickClock();
    setInterval(tickClock, 1000);
    render();
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(poll, POLL_MS);

    // ── وضعیت‌های ذخیره‌شده (پوسته، صدا، جمع‌بودنِ منو) رو اعمال کن ──
    applyTheme(getTheme());
    syncSoundBtn();
    try {
      if (localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === "1") applySidebarCollapsed(true);
    } catch (e) {}
    updateAssistantFabVisibility();
    initKeyboardChords();

    // بعد از این‌که app از حالت hidden درومد و چیدمانش قطعی شد، اندازه‌ی
    // واقعیِ آیتم‌ها رو بخون تا نشانگرهای لغزان از همون اول جای درستی باشن.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        updateNavIndicator();
        updateBnIndicator();
      });
    });
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
