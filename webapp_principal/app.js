// پنل مدیر مدرسه — کاملاً فقط‌خواندنی (بخشِ انتخابِ دستیِ نفراتِ برتر که
// قبلاً اینجا (تبِ «پنل مدیر») بود، به پنلِ ادمین‌ها منتقل شده).

const KEY = window.PRINCIPAL_KEY || "";
const viewTitleEl = document.getElementById("view-title");
const viewBodyEl = document.getElementById("view-body");
const clockEl = document.getElementById("topbar-clock");

const VIEW_TITLES = {
  home: "خانه",
  classes: "کلاس‌ها",
  players: "بازیکن‌ها",
  matches: "مسابقات",
  top: "نفرات برتر",
  assistant: "دستیار",
};

let currentView = "home";
const cache = {};
const trendsBtnEl = document.getElementById("topbar-trends-btn");

// ─── لایت/دارک‌مود (دیفالت لایت؛ انتخابِ کاربر توی همین مرورگر ذخیره می‌شه) ──
const THEME_KEY = "principal_theme";
function getStoredTheme() {
  try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
}
function applyTheme(theme) {
  if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
  else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
}
let currentTheme = getStoredTheme() === "dark" ? "dark" : "light";
applyTheme(currentTheme); // هم‌سو با اسکریپتِ ضدِ فلشِ توی <head>، برای اطمینان دوباره ست می‌شه

function syncThemeSwitchUI() {
  const sw = document.getElementById("theme-toggle-btn");
  if (!sw) return;
  sw.setAttribute("aria-checked", currentTheme === "dark" ? "true" : "false");
}

function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  applyTheme(currentTheme);
  syncThemeSwitchUI();
}

// ─── ابزار API ────────────────────────────────────────────────
async function api(path, params = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("k", KEY);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("request_failed:" + res.status);
  return res.json();
}

// ─── ناوبری ───────────────────────────────────────────────────
function setActiveNav(view) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".bn-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
}

function bindNav() {
  document.querySelectorAll(".nav-item, .bn-item").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
  if (trendsBtnEl) trendsBtnEl.addEventListener("click", toggleTrendsPanel);
}

// ─── منوی ریزِ روندها (باز/بسته‌شدنِ نرم داخلِ ویوِ «نفرات برتر») ───
async function toggleTrendsPanel() {
  const panel = document.getElementById("trends-panel");
  const body = document.getElementById("trends-panel-body");
  if (!panel || !body) return;

  const opening = !panel.classList.contains("open");
  panel.classList.toggle("open", opening);
  trendsBtnEl.classList.toggle("open", opening);
  if (!opening) return;

  if (body.dataset.loaded === "1") return; // قبلاً لود شده، دیگه دوباره درخواست نمی‌زنیم
  body.innerHTML = `<div class="loading-state"><span class="spinner"></span></div>`;
  try {
    const data = await api("/api/principal/trends");
    body.innerHTML = trendsChartsHTML(data);
    body.dataset.loaded = "1";
  } catch (e) {
    body.innerHTML = `<div class="empty-state">⚠️ خطا در دریافت اطلاعات.<br>لطفاً دوباره تلاش کنید.</div>`;
    console.error(e);
  }
}

async function switchView(view) {
  const changed = currentView !== view;
  currentView = view;
  setActiveNav(view);
  viewTitleEl.textContent = VIEW_TITLES[view] || "";
  if (trendsBtnEl) {
    trendsBtnEl.classList.toggle("visible", view === "top");
    trendsBtnEl.classList.remove("open");
  }
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

  // یه فِیدِ کوتاهِ خروج/ورود بینِ ویوها، تا جابه‌جایی به‌جای «پرش» خشک، نرم و روون حس بشه.
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (changed && !reduceMotion) {
    viewBodyEl.classList.add("view-fade-out");
    await new Promise(r => setTimeout(r, 110));
  }

  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span>در حال بارگذاری…</div>`;
  try {
    await RENDERERS[view]();
  } catch (e) {
    viewBodyEl.innerHTML = `<div class="empty-state">⚠️ خطا در دریافت اطلاعات.<br>لطفاً دوباره تلاش کنید.</div>`;
    console.error(e);
  }

  if (!reduceMotion) {
    viewBodyEl.classList.remove("view-fade-out");
    viewBodyEl.classList.add("view-fade-in");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => viewBodyEl.classList.remove("view-fade-in"));
    });
  }
}

// ─── کمکی‌های نمایش ───────────────────────────────────────────
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("fa-IR", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch { return iso; }
}

// ─── خانه ─────────────────────────────────────────────────────
async function renderHome() {
  const [ov, top] = await Promise.all([api("/api/principal/overview"), api("/api/principal/top", { period: "week" })]);
  const s = ov.stats;
  viewBodyEl.innerHTML = `
    ${themeToggleCardHTML()}
    <div class="stat-grid">
      ${statCard(s.classes_total, "کلاس")}
      ${statCard(s.players_total, "بازیکن (" + s.players_active + " فعال)")}
      ${statCard(s.matches_total, "مسابقه ثبت‌شده")}
      ${statCard(s.matches_this_week, "مسابقه این هفته")}
      ${statCard(s.matches_decided, "مسابقه با نتیجه")}
      ${statCard(s.tournaments_active, "تورنومنت فعال")}
    </div>
    <div class="section-title">🏆 نفرات برتر این هفته</div>
    <div id="home-top" class="card-list"></div>
  `;
  const box = document.getElementById("home-top");
  const rows = (top.leaderboard || []).slice(0, 5);
  box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") :
    `<div class="empty-state">این هفته هنوز مسابقه‌ای با نتیجه ثبت نشده.</div>`;

  const themeBtn = document.getElementById("theme-toggle-btn");
  if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
  syncThemeSwitchUI();
}

// ─── کارتِ سوییچِ لایت/دارک (فقط توی صفحهٔ خانه) ───────────────
function themeToggleCardHTML() {
  return `
    <div class="theme-toggle-card">
      <div class="theme-toggle-info">
        <span class="theme-toggle-ic">🌗</span>
        <div>
          <div class="main-txt">حالت نمایش</div>
          <div class="sub-txt">لایت یا دارک — به دلخواه شما</div>
        </div>
      </div>
      <button id="theme-toggle-btn" class="theme-switch" type="button" role="switch"
        aria-checked="${currentTheme === "dark" ? "true" : "false"}" aria-label="تغییر بین لایت و دارک">
        <span class="theme-switch-icons"><span class="ts-sun">☀️</span><span class="ts-moon">🌙</span></span>
        <span class="theme-switch-knob"></span>
      </button>
    </div>
  `;
}

function statCard(val, lbl) {
  return `<div class="stat-card"><span class="val">${esc(val ?? 0)}</span><span class="lbl">${esc(lbl)}</span></div>`;
}

// ─── کلاس‌ها ──────────────────────────────────────────────────
async function renderClasses() {
  const data = await api("/api/principal/classes");
  const list = data.classes || [];
  if (!list.length) {
    viewBodyEl.innerHTML = `<div class="empty-state">هنوز کلاسی ثبت نشده.</div>`;
    return;
  }
  viewBodyEl.innerHTML = `<div class="card-list">${list.map(c => `
    <div class="row-card">
      <div>
        <div class="main-txt">${esc(c.name)}</div>
        <div class="sub-txt">${esc(c.player_count)} بازیکن</div>
      </div>
      <div class="badge-group">
        <span class="badge win">${esc(c.wins)} برد</span>
        <span class="badge draw">${esc(c.draws)} مساوی</span>
        <span class="badge loss">${esc(c.losses)} باخت</span>
      </div>
    </div>
  `).join("")}</div>`;
}

// ─── بازیکنان ─────────────────────────────────────────────────
async function renderPlayers() {
  const data = await api("/api/principal/players");
  const list = (data.players || []).slice().sort((a, b) => b.wins - a.wins);
  if (!list.length) {
    viewBodyEl.innerHTML = `<div class="empty-state">هنوز بازیکنی ثبت نشده.</div>`;
    return;
  }
  viewBodyEl.innerHTML = `
    <div class="search-box">
      <input type="text" id="players-search" placeholder="جستجوی نام بازیکن یا کلاس…" autocomplete="off">
      <span class="search-ic">🔍</span>
    </div>
    <div class="tabs" id="players-filter">
      <button class="tab-btn active" data-f="all">همه</button>
      <button class="tab-btn" data-f="active">فعال</button>
    </div>
    <div class="card-list" id="players-list"></div>
  `;
  const listEl = document.getElementById("players-list");
  const searchEl = document.getElementById("players-search");
  let activeFilter = "all";

  function draw() {
    let rows = activeFilter === "active" ? list.filter(p => p.status === "active") : list;
    const q = searchEl.value.trim().toLowerCase();
    if (q) {
      rows = rows.filter(p =>
        (p.full_name || "").toLowerCase().includes(q) ||
        (p.class_name || "").toLowerCase().includes(q)
      );
    }
    listEl.innerHTML = rows.length ? rows.map(p => `
      <div class="row-card">
        <div>
          <div class="main-txt">${esc(p.full_name)}${p.is_elite ? " ⭐" : ""}</div>
          <div class="sub-txt">${esc(p.class_name)} · ${esc(p.games)} بازی</div>
        </div>
        <div class="badge-group">
          <span class="badge win">${esc(p.wins)}</span>
          <span class="badge draw">${esc(p.draws)}</span>
          <span class="badge loss">${esc(p.losses)}</span>
        </div>
      </div>
    `).join("") : `<div class="empty-state">بازیکنی یافت نشد.</div>`;
  }
  document.querySelectorAll("#players-filter .tab-btn").forEach(b => {
    b.addEventListener("click", () => {
      document.querySelectorAll("#players-filter .tab-btn").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      activeFilter = b.dataset.f;
      draw();
    });
  });
  searchEl.addEventListener("input", draw);
  draw();
}

// ─── مسابقات ──────────────────────────────────────────────────
async function renderMatches(period = "all", searchTerm = "") {
  viewBodyEl.innerHTML = `
    <div class="search-box">
      <input type="text" id="matches-search" placeholder="جستجوی نام بازیکن…" autocomplete="off">
      <span class="search-ic">🔍</span>
    </div>
    <div class="tabs" id="matches-filter">
      <button class="tab-btn" data-f="all">همه</button>
      <button class="tab-btn" data-f="today">امروز</button>
      <button class="tab-btn" data-f="week">این هفته</button>
      <button class="tab-btn" data-f="month">این ماه</button>
    </div>
    <div class="card-list" id="matches-list"><div class="loading-state"><span class="spinner"></span></div></div>
  `;
  const btns = document.querySelectorAll("#matches-filter .tab-btn");
  btns.forEach(b => b.classList.toggle("active", b.dataset.f === period));
  const searchEl = document.getElementById("matches-search");
  searchEl.value = searchTerm;
  btns.forEach(b => b.addEventListener("click", () => renderMatches(b.dataset.f, searchEl.value)));

  const data = await api("/api/principal/matches", { period });
  const allMatches = data.matches || [];
  const listEl = document.getElementById("matches-list");
  const resultBadge = { white: "win", black: "loss", draw: "draw" };

  function draw() {
    const q = searchEl.value.trim().toLowerCase();
    const list = q
      ? allMatches.filter(m =>
          (m.white || "").toLowerCase().includes(q) ||
          (m.black || "").toLowerCase().includes(q)
        )
      : allMatches;
    listEl.innerHTML = list.length ? list.map(m => `
      <div class="row-card">
        <div>
          <div class="main-txt">${esc(m.white)} <span style="color:var(--ivory-dim)">در برابر</span> ${esc(m.black)}</div>
          <div class="sub-txt">${fmtDate(m.match_date || m.created_at)}</div>
        </div>
        <span class="badge ${resultBadge[m.result] || "muted"}">${esc(m.result_fa)}</span>
      </div>
    `).join("") : `<div class="empty-state">مسابقه‌ای یافت نشد.</div>`;
  }
  searchEl.addEventListener("input", draw);
  draw();
}

// ─── نفرات برتر ───────────────────────────────────────────────
function topRow(r, i) {
  return `
    <div class="top-row">
      <div class="top-rank">${i + 1}</div>
      <div class="top-info">
        <div class="main-txt">${esc(r.full_name)}</div>
        <div class="sub-txt">${esc(r.class_name)} · ${esc(r.games)} بازی (${esc(r.wins)}ب / ${esc(r.draws)}م / ${esc(r.losses)}ش)</div>
      </div>
      <div class="top-score">
        <div class="val">${esc(r.score)}</div>
        <div class="lbl">امتیاز</div>
      </div>
    </div>
  `;
}

async function renderTop(period = "week") {
  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span></div>`;
  if (trendsBtnEl) trendsBtnEl.classList.remove("open"); // پنلِ روندها با هر رندرِ تازه بسته و خالی شروع می‌شه
  const data = await api("/api/principal/top", { period });
  const rows = data.leaderboard || [];

  if (data.mode === "manual") {
    // نفرات برتر دستی‌ست — بازه‌ی زمانی معنی نداره، فهرستی که مدیر ارشد
    // خودش انتخاب کرده به همون ترتیب نشون داده می‌شه.
    viewBodyEl.innerHTML = `
      <div class="manual-note">🎯 نمایشِ نفرات برتر با دقت بالا توسط ربات محاسبه شده و نمایش داده خواهد شد.</div>
      <div id="top-list"></div>
      ${trendsPanelSkeleton()}
    `;
    const box = document.getElementById("top-list");
    box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") :
      `<div class="empty-state">هنوز هیچ‌کس به‌صورت دستی انتخاب نشده.</div>`;
    return;
  }

  viewBodyEl.innerHTML = `
    <div class="tabs" id="top-filter">
      <button class="tab-btn" data-f="week">این هفته</button>
      <button class="tab-btn" data-f="month">این ماه</button>
      <button class="tab-btn" data-f="all">کل دوران</button>
    </div>
    <div id="top-list"></div>
    ${trendsPanelSkeleton()}
  `;
  const btns = document.querySelectorAll("#top-filter .tab-btn");
  btns.forEach(b => b.classList.toggle("active", b.dataset.f === period));
  btns.forEach(b => b.addEventListener("click", () => renderTop(b.dataset.f)));
  const box = document.getElementById("top-list");
  box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") :
    `<div class="empty-state">در این بازه هنوز مسابقه‌ای با نتیجه ثبت نشده.</div>`;
}

// جایگاهِ خالیِ پنلِ روندها — با دکمهٔ ریزِ بالای صفحه (topbar-trends-btn) باز/بسته می‌شه.
function trendsPanelSkeleton() {
  return `<div id="trends-panel" class="trends-panel"><div id="trends-panel-body" class="trends-panel-body"></div></div>`;
}

// ─── نمودارهای روند (SVG دستی، بدون کتابخانه) ────────────────
function barChartSVG(data, opts = {}) {
  const w = 320, h = 150, pad = 22;
  const max = Math.max(1, ...data.map(d => d.value));
  const bw = (w - pad * 2) / data.length;
  const bars = data.map((d, i) => {
    const bh = Math.max(2, (d.value / max) * (h - pad - 24));
    const x = pad + i * bw + bw * 0.15;
    const y = h - pad - bh;
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw * 0.7).toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="${opts.color || 'var(--amber)'}"/>
            <text x="${(x + bw * 0.35).toFixed(1)}" y="${h - 6}" font-size="8" fill="var(--ivory-dim)" text-anchor="middle">${esc(shorten(d.label))}</text>
            <text x="${(x + bw * 0.35).toFixed(1)}" y="${(y - 4).toFixed(1)}" font-size="8" fill="var(--ivory)" text-anchor="middle">${d.value}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">${bars}</svg>`;
}

function lineChartSVG(data, opts = {}) {
  const w = 320, h = 150, pad = 22;
  const max = Math.max(1, ...data.map(d => d.value));
  const stepX = (w - pad * 2) / Math.max(1, data.length - 1);
  const pts = data.map((d, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (d.value / max) * (h - pad - 20);
    return [x, y];
  });
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const area = path + ` L${pts[pts.length - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
  const dots = pts.map((p, i) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.4" fill="${opts.color || 'var(--sage)'}"/>`).join("");
  const lbl = data.length ? `<text x="${pts[0][0]}" y="${h - 4}" font-size="8" fill="var(--ivory-dim)">${esc(shorten(data[0].label))}</text>
    <text x="${pts[pts.length - 1][0]}" y="${h - 4}" font-size="8" fill="var(--ivory-dim)" text-anchor="end">${esc(shorten(data[data.length - 1].label))}</text>` : "";
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    <path d="${area}" fill="${opts.color || 'var(--sage)'}" fill-opacity="0.12" stroke="none"/>
    <path d="${path}" fill="none" stroke="${opts.color || 'var(--sage)'}" stroke-width="2"/>
    ${dots}${lbl}
  </svg>`;
}

function shorten(s) {
  s = String(s ?? "");
  return s.length > 6 ? s.slice(5) : s; // برای تاریخ‌های ISO فقط روز/ماه رو نشون بده
}

function trendsChartsHTML(data) {
  return `
    <div class="chart-card">
      <h4>📈 تعداد مسابقات ثبت‌شده در ۳۰ روز اخیر</h4>
      ${lineChartSVG(data.matches_by_day, { color: "var(--amber)" })}
    </div>
    <div class="chart-card">
      <h4>📊 تعداد مسابقات هفتگی (۸ هفته اخیر)</h4>
      ${barChartSVG(data.matches_by_week, { color: "var(--sage)" })}
    </div>
    <div class="chart-card">
      <h4>🏫 توزیع بازیکنان بر اساس کلاس</h4>
      ${barChartSVG(data.players_by_class, { color: "var(--amber)" })}
    </div>
    <div class="chart-card">
      <h4>♟️ توزیع نتایج مسابقات</h4>
      ${barChartSVG(data.results_distribution, { color: "var(--brick)" })}
    </div>
  `;
}

// ─── اندازه‌گیریِ دقیقِ ارتفاعِ باکسِ چتِ دستیار (رفعِ گپِ خالیِ زیرِ اینترو) ──
function sizeAssistantWrap() {
  const wrap = document.querySelector(".assistant-wrap");
  if (!wrap) return;
  const isDesktop = window.matchMedia("(min-width: 880px)").matches;
  const bottomNavH = isDesktop ? 0 : (document.getElementById("bottom-nav")?.offsetHeight || 0);
  const safeBottomRaw = getComputedStyle(document.documentElement).getPropertyValue("--safe-bottom");
  const safeBottom = parseFloat(safeBottomRaw) || 0;
  const viewportH = window.visualViewport ? window.visualViewport.height : window.innerHeight;
  const top = wrap.getBoundingClientRect().top;
  const breathingRoom = 16; // کمی فاصله‌ی نفس، تا چسبیده به لبه نباشه
  const available = viewportH - top - bottomNavH - safeBottom - breathingRoom;
  wrap.style.height = Math.max(320, Math.round(available)) + "px";
}

// ─── دستیار هوشمند (فقط مشاوره/راهنما — پنل کاملاً فقط‌خواندنی می‌مونه) ─
const ASSISTANT_SUGGESTIONS = [
  "وضعیت کلی مدرسه چطوره؟",
  "این هفته چند مسابقه ثبت شده؟",
  "نفرات برتر رو از کجا ببینم؟",
  "روند مسابقات اخیر چطور بوده؟",
];

// تاریخچه‌ی گفتگو فقط توی حافظه‌ی همین صفحه می‌مونه (نه دیتابیس، نه سرور) —
// با رفرش صفحه پاک می‌شه، دقیقاً هم‌راستا با فقط‌خواندنی‌بودنِ کل این پنل.
const assistantState = { history: [], sending: false };

function renderAssistant() {
  viewBodyEl.innerHTML = `
    <div class="assistant-wrap">
      <div class="assistant-intro">
        <span class="assistant-avatar">🤖</span>
        <div>
          <div class="main-txt">دستیار پنل مدیر</div>
          <div class="sub-txt">راهنما و مشاورِ شماست؛ فقط دربارهٔ وضعیت و بخش‌های همین پنل توضیح می‌دهد.</div>
        </div>
      </div>
      <div id="assistant-log" class="assistant-log"></div>
      <div id="assistant-suggestions" class="assistant-suggestions"></div>
      <form id="assistant-form" class="assistant-form">
        <input type="text" id="assistant-input" placeholder="سوالتان را بنویسید…" autocomplete="off">
        <button type="submit" id="assistant-send" class="assistant-send" aria-label="ارسال">
          <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.5 12 4.5 5l2.6 7-2.6 7 15-7Z"/></svg>
        </button>
      </form>
    </div>
  `;

  const logEl = document.getElementById("assistant-log");
  const formEl = document.getElementById("assistant-form");
  const inputEl = document.getElementById("assistant-input");
  const suggEl = document.getElementById("assistant-suggestions");

  // ارتفاعِ واقعیِ باقی‌مونده‌ی صفحه رو اندازه می‌گیره و مستقیم روی .assistant-wrap
  // ست می‌کنه — به‌جای اتکا به یه calc(100dvh - عددِ ثابت) که با اندازه‌ی واقعیِ
  // topbar/اینترو هم‌خوان نبود و یه فضای خالیِ بزرگ زیرِ کارتِ معرفی می‌ذاشت.
  sizeAssistantWrap();
  requestAnimationFrame(sizeAssistantWrap); // یه بار دیگه بعد از اولین پینت، برای لِی‌آوتِ نهایی
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(sizeAssistantWrap);
  window.addEventListener("resize", sizeAssistantWrap);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", sizeAssistantWrap);

  function scrollLogToEnd() {
    logEl.scrollTop = logEl.scrollHeight;
  }

  function addBubble(role, text, animate = true) {
    const b = document.createElement("div");
    b.className = "chat-bubble " + (role === "user" ? "chat-user" : "chat-bot") + (animate ? " bubble-in" : "");
    if (role !== "user") {
      b.innerHTML = `<span class="bubble-ic">🤖</span><span class="bubble-txt"></span>`;
      b.querySelector(".bubble-txt").textContent = text;
    } else {
      b.textContent = text;
    }
    logEl.appendChild(b);
    scrollLogToEnd();
    return b;
  }

  function addTypingBubble() {
    const b = document.createElement("div");
    b.className = "chat-bubble chat-bot bubble-in";
    b.innerHTML = `<span class="bubble-ic">🤖</span><span class="typing-dots"><span></span><span></span><span></span></span>`;
    logEl.appendChild(b);
    scrollLogToEnd();
    return b;
  }

  // بازسازی گفتگوی قبلی (اگه مدیر قبلاً بین ویوها رفت‌وبرگشت کرده)
  if (assistantState.history.length) {
    assistantState.history.forEach(turn => addBubble(turn.role === "user" ? "user" : "bot", turn.text, false));
  } else {
    addBubble("bot", "سلام! من دستیار همین پنل هستم. هر سوالی درباره‌ی آمار یا بخش‌های پنل دارید، خوشحال می‌شوم کمک کنم 🙌", false);
  }

  suggEl.innerHTML = ASSISTANT_SUGGESTIONS.map(s => `<button type="button" class="sugg-chip">${esc(s)}</button>`).join("");
  suggEl.querySelectorAll(".sugg-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      inputEl.value = chip.textContent;
      formEl.requestSubmit();
    });
  });
  // اگه از قبل گفتگویی شروع شده، پیشنهادها رو از همون اول مخفی نگه دار
  if (assistantState.history.length) suggEl.classList.add("sugg-hidden");

  async function sendMessage(text) {
    if (!text || assistantState.sending) return;
    assistantState.sending = true;
    inputEl.value = "";
    inputEl.disabled = true;
    suggEl.classList.add("sugg-hidden");

    addBubble("user", text);
    assistantState.history.push({ role: "user", text });
    const typingBubble = addTypingBubble();

    try {
      const url = new URL("/api/principal/assistant", window.location.origin);
      url.searchParams.set("k", KEY);
      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: assistantState.history.slice(0, -1) }),
      });
      const data = await res.json();
      typingBubble.remove();
      const reply = (data && data.ok && data.reply) ? data.reply : "⚠️ پاسخی دریافت نشد. لطفاً دوباره تلاش کنید.";
      addBubble("bot", reply);
      assistantState.history.push({ role: "model", text: reply });
    } catch (e) {
      typingBubble.remove();
      addBubble("bot", "⚠️ ارتباط برقرار نشد. لطفاً اتصال اینترنت را بررسی و دوباره تلاش کنید.");
      console.error(e);
    } finally {
      assistantState.sending = false;
      inputEl.disabled = false;
      inputEl.focus();
    }
  }

  formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(inputEl.value.trim());
  });
}

// ─── پنل مدیر: فقط اجرا (انتخابِ دستیِ نفرات برتر) ─────────────
const RENDERERS = {
  home: renderHome,
  classes: renderClasses,
  players: renderPlayers,
  matches: () => renderMatches("all"),
  top: () => renderTop("week"),
  assistant: renderAssistant,
};

// ─── ساعت بالای صفحه ──────────────────────────────────────────
function tickClock() {
  clockEl.textContent = new Date().toLocaleTimeString("fa-IR");
}
setInterval(tickClock, 1000);
tickClock();

// ─── شروع ─────────────────────────────────────────────────────
bindNav();
switchView("home"); // داده‌های خانه همزمان با پخش اسپلش لود می‌شن

// ─── اسپلش خوش‌آمدگویی ─────────────────────────────────────────
(function runSplash() {
  const splashEl = document.getElementById("splash");
  const appEl = document.getElementById("app");
  if (!splashEl || !appEl) return;

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SPLASH_MS = reduceMotion ? 0 : 2200;
  // FIX: قبلاً اینجا ۶۵۰ بود ولی ترنزیشنِ واقعیِ .app-veil.reveal توی CSS
  // ۷۰۰ میلی‌ثانیه‌ست؛ یعنی کلاس‌ها ۵۰ میلی‌ثانیه زودتر از تمومِ ترنزیشن پاک
  // می‌شدن. الان با همون عددِ CSS (۷۰۰) هماهنگ شده.
  const EXIT_MS = reduceMotion ? 0 : 700;

  setTimeout(() => {
    splashEl.classList.add("leaving");
    appEl.classList.add("reveal");
    setTimeout(() => {
      splashEl.remove();
      // مهم: بعد از پایان انیمیشن، کلاس‌های veil/reveal (که transform دارن) رو
      // کامل حذف می‌کنیم. تا وقتی #app یه transform فعال داشته باشه، خودش
      // یه "containing block" جدید می‌سازه و باعث می‌شه بچه‌های position:fixed
      // داخلش (مثل ناوبری پایین صفحه) دیگه نسبت به کل صفحه فیکس نمونن، بلکه
      // نسبت به #app فیکس بشن — که باعث میشه منو فقط با اسکرول تا ته دیده بشه.
      appEl.classList.remove("app-veil", "reveal");
    }, EXIT_MS);
  }, SPLASH_MS);
})();
