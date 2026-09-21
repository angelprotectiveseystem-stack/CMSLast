// پنل مدیر مدرسه — کاملاً فقط‌خواندنی.
// این نسخه هم‌راستا با ساختار تازهٔ index.html/style.css بازنویسی شده:
// ناوبری پایین (.dock)، ورقه‌های فویلی (.sheets)، رهگشای شناور (#rg-fab/#rg)،
// و سربرگ ورودی/بقیهٔ صفحه‌ها (#hero / #page-head).

const KEY = window.PRINCIPAL_KEY || "";
const viewTitleEl = document.getElementById("view-title");
const viewBodyEl = document.getElementById("view-body");
const pageHeadEl = document.getElementById("page-head");
const heroEl = document.getElementById("hero");
const greetingEl = document.getElementById("greeting");
const todayDateEl = document.getElementById("today-date");
const clockEl = document.getElementById("topbar-clock");
const trendsBtnEl = document.getElementById("topbar-trends-btn");

const VIEW_TITLES = {
  home: "خانه",
  classes: "کلاس‌ها",
  players: "بازیکن‌ها",
  matches: "مسابقات",
  top: "برترین‌ها",
};
const VIEW_ORDER = ["home", "classes", "players", "matches", "top"];

let currentView = "home";

// ─── لایت/دارک‌مود ──────────────────────────────────────────────
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
applyTheme(currentTheme);

function syncThemeBtnUI() {
  const btn = document.getElementById("theme-btn");
  if (btn) btn.setAttribute("aria-pressed", currentTheme === "dark" ? "true" : "false");
}
function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  applyTheme(currentTheme);
  syncThemeBtnUI();
}
syncThemeBtnUI();
const themeBtnEl = document.getElementById("theme-btn");
if (themeBtnEl) themeBtnEl.addEventListener("click", toggleTheme);

// ─── ابزار API ────────────────────────────────────────────────
async function api(path, params = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("k", KEY);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("request_failed:" + res.status);
  return res.json();
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
function initials(name) {
  const s = String(name ?? "").trim();
  if (!s) return "؟";
  return s[0];
}
// چهار تن‌رنگِ آواتار (t1..t4) بر اساس نام، تا هر بازیکن رنگ ثابت خودش رو داشته باشه.
function avatarTone(name) {
  const s = String(name ?? "");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return "t" + ((h % 4) + 1);
}

// ─── اسکلت بارگذاری / حالت خالی ────────────────────────────────
function skeletonHTML(n = 3, tall = false) {
  const cls = tall ? "tall" : "";
  return `<div class="sk">${Array.from({ length: n }).map(() => `<i class="${cls}"></i>`).join("")}</div>`;
}
function emptyHTML(text, icon = "i-empty") {
  return `
    <div class="empty">
      <span class="empty-ic"><svg class="ic" aria-hidden="true"><use href="#${icon}"/></svg></span>
      <b>موردی یافت نشد</b>
      <p>${esc(text)}</p>
    </div>`;
}
function errorHTML() {
  return `
    <div class="empty">
      <span class="empty-ic"><svg class="ic" aria-hidden="true"><use href="#i-empty"/></svg></span>
      <b>مشکلی پیش آمد</b>
      <p>دریافت اطلاعات با خطا مواجه شد. لطفاً لحظاتی بعد دوباره تلاش کنید.</p>
    </div>`;
}

// ─── ناوبری (کپسول پایین) ───────────────────────────────────────
function setActiveDock(view) {
  const items = Array.from(document.querySelectorAll(".dock-item"));
  items.forEach((b, i) => {
    const on = b.dataset.view === view;
    b.classList.toggle("is-on", on);
    b.setAttribute("aria-current", on ? "page" : "false");
    if (on) document.getElementById("dock").style.setProperty("--i", i);
  });
}
function bindNav() {
  document.querySelectorAll(".dock-item").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
  if (trendsBtnEl) trendsBtnEl.addEventListener("click", toggleTrendsPanel);
}

async function switchView(view) {
  const changed = currentView !== view;
  currentView = view;
  setActiveDock(view);

  const isHome = view === "home";
  heroEl.hidden = !isHome;
  pageHeadEl.hidden = isHome;
  if (!isHome) document.getElementById("view-title").textContent = VIEW_TITLES[view] || "";
  if (trendsBtnEl) {
    trendsBtnEl.hidden = view !== "top";
    trendsBtnEl.setAttribute("aria-expanded", "false");
  }
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (changed && !reduceMotion) {
    viewBodyEl.classList.add("is-leaving");
    await new Promise(r => setTimeout(r, 140));
  }

  viewBodyEl.innerHTML = skeletonHTML(3, view === "top" || view === "classes");
  try {
    await RENDERERS[view]();
  } catch (e) {
    viewBodyEl.innerHTML = errorHTML();
    console.error(e);
  }

  viewBodyEl.classList.remove("is-leaving");
  if (!reduceMotion) {
    viewBodyEl.classList.add("is-entering");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => viewBodyEl.classList.remove("is-entering"));
    });
  }
}

// ─── خوش‌آمدگویی بر اساس ساعت روز ───────────────────────────────
function greetingForHour(h) {
  if (h >= 5 && h < 11) return "صبح بخیر";
  if (h >= 11 && h < 15) return "ظهر بخیر";
  if (h >= 15 && h < 18) return "عصر بخیر";
  if (h >= 18 && h < 23) return "شب بخیر";
  return "آخر شب بخیر";
}
function paintGreeting() {
  const now = new Date();
  greetingEl.textContent = greetingForHour(now.getHours()) + "، خوبی داشته باشید";
  todayDateEl.textContent = now.toLocaleDateString("fa-IR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

// ─── خانه ─────────────────────────────────────────────────────
function statCard(icon, num, lbl, opts = {}) {
  const cls = ["stat"];
  if (opts.hero) cls.push("stat--hero");
  if (opts.wide) cls.push("stat--wide");
  return `
    <div class="${cls.join(" ")}">
      <span class="stat-ic"><svg class="ic" aria-hidden="true"><use href="#${icon}"/></svg></span>
      <span class="stat-num">${esc(num ?? 0)}</span>
      <span class="stat-lbl">${esc(lbl)}</span>
    </div>`;
}

async function renderHome() {
  paintGreeting();
  const [ov, top] = await Promise.all([
    api("/api/principal/overview"),
    api("/api/principal/top", { period: "week" }),
  ]);
  const s = ov.stats;
  const rows = (top.leaderboard || []).slice(0, 5);

  viewBodyEl.innerHTML = `
    <div class="stat-grid">
      ${statCard("i-school", s.classes_total, "کلاس", { hero: true })}
      ${statCard("i-pawn", s.players_total, s.players_active + " نفر فعال")}
      ${statCard("i-board", s.matches_total, "مسابقهٔ ثبت‌شده")}
      ${statCard("i-cal-week", s.matches_this_week, "مسابقهٔ این هفته")}
      ${statCard("i-flag", s.matches_decided, "مسابقهٔ با نتیجه")}
      ${statCard("i-trophy", s.tournaments_active, "تورنومنت فعال")}
    </div>
    <div class="section-head">
      <h3><svg class="ic" aria-hidden="true"><use href="#i-trophy"/></svg>نفرات برتر این هفته</h3>
      <button class="link" type="button" data-goto="top">مشاهدهٔ همه</button>
    </div>
    <ul class="board" id="home-top"></ul>
  `;
  const box = document.getElementById("home-top");
  box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") : emptyHTML("این هفته هنوز مسابقه‌ای با نتیجه ثبت نشده.", "i-trophy");
  const gotoBtn = viewBodyEl.querySelector("[data-goto]");
  if (gotoBtn) gotoBtn.addEventListener("click", () => switchView(gotoBtn.dataset.goto));
}

// ─── کلاس‌ها ──────────────────────────────────────────────────
function classCard(c) {
  const total = Math.max(1, (c.wins || 0) + (c.draws || 0) + (c.losses || 0));
  return `
    <div class="ccard">
      <div class="ccard-head">
        <span class="ccard-ic"><svg class="ic" aria-hidden="true"><use href="#i-school"/></svg></span>
        <div>
          <h4>${esc(c.name)}</h4>
          <small>${esc(c.player_count)} بازیکن</small>
        </div>
      </div>
      <div class="wdl">
        <i class="w" style="--f:${c.wins || 0}"></i>
        <i class="d" style="--f:${c.draws || 0}"></i>
        <i class="l" style="--f:${c.losses || 0}"></i>
      </div>
      <div class="tiles tiles--3">
        <div class="tile w"><b>${esc(c.wins)}</b><small>برد</small></div>
        <div class="tile d"><b>${esc(c.draws)}</b><small>تساوی</small></div>
        <div class="tile l"><b>${esc(c.losses)}</b><small>باخت</small></div>
      </div>
    </div>`;
}

async function renderClasses() {
  const data = await api("/api/principal/classes");
  const list = data.classes || [];
  if (!list.length) {
    viewBodyEl.innerHTML = emptyHTML("هنوز کلاسی ثبت نشده.", "i-school");
    return;
  }
  viewBodyEl.innerHTML = `<div class="stack">${list.map(classCard).join("")}</div>`;
}

// ─── بازیکنان ─────────────────────────────────────────────────
function playerCard(p) {
  return `
    <div class="pcard ${p.is_elite ? "is-elite" : ""}">
      <span class="avatar ${avatarTone(p.full_name)}">${esc(initials(p.full_name))}</span>
      <div class="pc-main">
        <h4>${esc(p.full_name)}${p.is_elite ? '<svg class="ic" aria-hidden="true"><use href="#i-star"/></svg>' : ""}</h4>
        <span class="chip ${p.status === "active" ? "" : "chip--off"}">${esc(p.class_name)}</span>
        <span class="chip ${p.status === "active" ? "" : "chip--off"}">${p.status === "active" ? "فعال" : "غیرفعال"}</span>
      </div>
      <div class="wdl"><i class="w" style="--f:${p.wins || 0}"></i><i class="d" style="--f:${p.draws || 0}"></i><i class="l" style="--f:${p.losses || 0}"></i></div>
      <div class="tiles">
        <div class="tile"><b>${esc(p.games)}</b><small>بازی</small></div>
        <div class="tile w"><b>${esc(p.wins)}</b><small>برد</small></div>
        <div class="tile d"><b>${esc(p.draws)}</b><small>تساوی</small></div>
        <div class="tile l"><b>${esc(p.losses)}</b><small>باخت</small></div>
      </div>
    </div>`;
}

async function renderPlayers() {
  const data = await api("/api/principal/players");
  const list = (data.players || []).slice().sort((a, b) => b.wins - a.wins);
  if (!list.length) {
    viewBodyEl.innerHTML = emptyHTML("هنوز بازیکنی ثبت نشده.", "i-pawn");
    return;
  }
  viewBodyEl.innerHTML = `
    <div class="search">
      <svg class="ic" aria-hidden="true"><use href="#i-search"/></svg>
      <input type="text" id="players-search" placeholder="جستجوی نام بازیکن یا کلاس…" autocomplete="off">
    </div>
    <div class="sheets" id="players-filter" style="--n:2">
      <span class="sheet-thumb" aria-hidden="true"></span>
      <button class="sheet is-on" type="button" data-f="all"><svg class="ic" aria-hidden="true"><use href="#i-pawn"/></svg>همه</button>
      <button class="sheet" type="button" data-f="active"><svg class="ic" aria-hidden="true"><use href="#i-flag"/></svg>فعال</button>
    </div>
    <p class="count" id="players-count"></p>
    <div class="stack" id="players-list"></div>
  `;
  const listEl = document.getElementById("players-list");
  const countEl = document.getElementById("players-count");
  const searchEl = document.getElementById("players-search");
  const sheetsEl = document.getElementById("players-filter");
  const sheetBtns = Array.from(sheetsEl.querySelectorAll(".sheet"));
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
    countEl.textContent = rows.length ? rows.length + " بازیکن" : "";
    listEl.innerHTML = rows.length ? rows.map(playerCard).join("") : emptyHTML("بازیکنی با این مشخصات یافت نشد.", "i-search");
  }
  sheetBtns.forEach((b, i) => {
    b.addEventListener("click", () => {
      sheetBtns.forEach(x => x.classList.remove("is-on"));
      b.classList.add("is-on");
      sheetsEl.style.setProperty("--i", i);
      sheetsEl.classList.add("swapped");
      activeFilter = b.dataset.f;
      draw();
    });
  });
  searchEl.addEventListener("input", draw);
  draw();
}

// ─── مسابقات ──────────────────────────────────────────────────
const MATCH_PERIODS = [
  { f: "all", label: "همه", ic: "i-infinity" },
  { f: "today", label: "امروز", ic: "i-cal-week" },
  { f: "week", label: "این هفته", ic: "i-cal-week" },
  { f: "month", label: "این ماه", ic: "i-cal-month" },
];

function matchCard(m) {
  const badgeCls = { white: "win", black: "loss", draw: "draw" }[m.result] || "";
  const whiteWin = m.result === "white";
  const blackWin = m.result === "black";
  return `
    <div class="mcard">
      <div class="mcard-body">
        <div class="side ${whiteWin ? "is-win" : ""}">
          <span class="piece pw"><svg class="ic" aria-hidden="true"><use href="#i-pawn"/></svg></span>
          <b>${esc(m.white)}</b><small>سفید</small>
        </div>
        <span class="vs">VS</span>
        <div class="side ${blackWin ? "is-win" : ""}">
          <span class="piece pb"><svg class="ic" aria-hidden="true"><use href="#i-pawn"/></svg></span>
          <b>${esc(m.black)}</b><small>سیاه</small>
        </div>
      </div>
      <div class="mcard-foot">
        <span>${fmtDate(m.match_date || m.created_at)}</span>
        <span class="badge ${badgeCls}">${esc(m.result_fa)}</span>
      </div>
    </div>`;
}

async function renderMatches(period = "all", searchTerm = "") {
  viewBodyEl.innerHTML = `
    <div class="search">
      <svg class="ic" aria-hidden="true"><use href="#i-search"/></svg>
      <input type="text" id="matches-search" placeholder="جستجوی نام بازیکن…" autocomplete="off">
    </div>
    <div class="sheets" id="matches-filter" style="--n:${MATCH_PERIODS.length}">
      <span class="sheet-thumb" aria-hidden="true"></span>
      ${MATCH_PERIODS.map(p => `<button class="sheet" type="button" data-f="${p.f}"><svg class="ic" aria-hidden="true"><use href="#${p.ic}"/></svg>${p.label}</button>`).join("")}
    </div>
    <p class="count" id="matches-count"></p>
    <div class="stack" id="matches-list">${skeletonHTML(3)}</div>
  `;
  const sheetsEl = document.getElementById("matches-filter");
  const sheetBtns = Array.from(sheetsEl.querySelectorAll(".sheet"));
  const activeIdx = Math.max(0, MATCH_PERIODS.findIndex(p => p.f === period));
  sheetBtns[activeIdx].classList.add("is-on");
  sheetsEl.style.setProperty("--i", activeIdx);

  const searchEl = document.getElementById("matches-search");
  searchEl.value = searchTerm;
  sheetBtns.forEach((b, i) => {
    b.addEventListener("click", () => renderMatches(b.dataset.f, searchEl.value));
  });

  const data = await api("/api/principal/matches", { period });
  const allMatches = data.matches || [];
  const listEl = document.getElementById("matches-list");
  const countEl = document.getElementById("matches-count");

  function draw() {
    const q = searchEl.value.trim().toLowerCase();
    const list = q
      ? allMatches.filter(m =>
          (m.white || "").toLowerCase().includes(q) ||
          (m.black || "").toLowerCase().includes(q)
        )
      : allMatches;
    countEl.textContent = list.length ? list.length + " مسابقه" : "";
    listEl.innerHTML = list.length ? list.map(matchCard).join("") : emptyHTML("مسابقه‌ای با این مشخصات یافت نشد.", "i-board");
  }
  searchEl.addEventListener("input", draw);
  draw();
}

// ─── نفرات برتر ───────────────────────────────────────────────
function topRow(r, i) {
  const rank = i + 1;
  const rankCls = rank <= 3 ? `rank-${rank}` : "";
  const crown = rank === 1 ? '<svg class="ic crown" aria-hidden="true"><use href="#i-crown"/></svg>' : "";
  return `
    <li class="top-row ${rankCls}">
      ${crown}
      <span class="seal">${rank}</span>
      <div class="top-info">
        <b>${esc(r.full_name)}</b>
        <div class="top-sub">
          <span>${esc(r.class_name)}</span>
          <span class="k w">${esc(r.wins)}</span>
          <span class="k d">${esc(r.draws)}</span>
          <span class="k l">${esc(r.losses)}</span>
        </div>
      </div>
      <div class="top-score"><b>${esc(r.score)}</b><small>امتیاز</small></div>
      <div class="wdl"><i class="w" style="--f:${r.wins || 0}"></i><i class="d" style="--f:${r.draws || 0}"></i><i class="l" style="--f:${r.losses || 0}"></i></div>
    </li>`;
}

const TOP_PERIODS = [
  { f: "week", label: "این هفته", ic: "i-cal-week" },
  { f: "month", label: "این ماه", ic: "i-cal-month" },
  { f: "all", label: "کل دوران", ic: "i-infinity" },
];

async function renderTop(period = "week") {
  closeTrendsPanel();
  const data = await api("/api/principal/top", { period });
  const rows = data.leaderboard || [];

  if (data.mode === "manual") {
    viewBodyEl.innerHTML = `
      <div class="note"><svg class="ic" aria-hidden="true"><use href="#i-flag"/></svg>نمایشِ نفرات برتر دستی است و توسط مدیر ارشد تعیین شده.</div>
      <ul class="board" id="top-list"></ul>
      ${trendsPanelSkeleton()}
    `;
    const box = document.getElementById("top-list");
    box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") : emptyHTML("هنوز هیچ‌کس به‌صورت دستی انتخاب نشده.", "i-trophy");
    return;
  }

  viewBodyEl.innerHTML = `
    <div class="sheets" id="top-filter" style="--n:${TOP_PERIODS.length}">
      <span class="sheet-thumb" aria-hidden="true"></span>
      ${TOP_PERIODS.map(p => `<button class="sheet" type="button" data-f="${p.f}"><svg class="ic" aria-hidden="true"><use href="#${p.ic}"/></svg>${p.label}</button>`).join("")}
    </div>
    <ul class="board" id="top-list"></ul>
    ${trendsPanelSkeleton()}
  `;
  const sheetsEl = document.getElementById("top-filter");
  const sheetBtns = Array.from(sheetsEl.querySelectorAll(".sheet"));
  const activeIdx = Math.max(0, TOP_PERIODS.findIndex(p => p.f === period));
  sheetBtns[activeIdx].classList.add("is-on");
  sheetsEl.style.setProperty("--i", activeIdx);
  sheetBtns.forEach(b => b.addEventListener("click", () => renderTop(b.dataset.f)));

  const box = document.getElementById("top-list");
  box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") : emptyHTML("در این بازه هنوز مسابقه‌ای با نتیجه ثبت نشده.", "i-trophy");
}

// ─── پنل روندها (کپسول «مشاهدهٔ روندها» بالای صفحه) ─────────────
function trendsPanelSkeleton() {
  return `<div id="trends-panel" class="trends"><div class="trends-inner"><div id="trends-panel-body" class="trends-body"></div></div></div>`;
}
function closeTrendsPanel() {
  if (trendsBtnEl) trendsBtnEl.setAttribute("aria-expanded", "false");
}

async function toggleTrendsPanel() {
  const panel = document.getElementById("trends-panel");
  const body = document.getElementById("trends-panel-body");
  if (!panel || !body) return;

  const opening = trendsBtnEl.getAttribute("aria-expanded") !== "true";
  trendsBtnEl.setAttribute("aria-expanded", opening ? "true" : "false");
  panel.classList.toggle("open", opening);
  if (!opening) return;

  // یک ضربان نرم برای ۱ ثانیهٔ اول، فقط بار اول که کاربر باز می‌کنه.
  trendsBtnEl.classList.add("beat");
  setTimeout(() => trendsBtnEl.classList.remove("beat"), 1000);

  if (body.dataset.loaded === "1") return;
  body.innerHTML = skeletonHTML(4, true);
  try {
    const data = await api("/api/principal/trends");
    body.innerHTML = trendsChartsHTML(data);
    body.dataset.loaded = "1";
  } catch (e) {
    body.innerHTML = errorHTML();
    console.error(e);
  }
}

// ─── نمودارهای روند (SVG دستی، بدون کتابخانه) ────────────────
const CHART_EMPTY_HTML = emptyHTML("هنوز داده‌ای برای نمایش ثبت نشده.", "i-pulse");

function shorten(s) {
  s = String(s ?? "");
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s.slice(5) : s;
}

function lineChartSVG(data) {
  if (!data || !data.length) return CHART_EMPTY_HTML;
  const w = 320, h = 150, pad = 22;
  const max = Math.max(1, ...data.map(d => d.value));
  const stepX = (w - pad * 2) / Math.max(1, data.length - 1);
  const pts = data.map((d, i) => [pad + i * stepX, h - pad - (d.value / max) * (h - pad - 20)]);
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const area = path + ` L${pts[pts.length - 1][0].toFixed(1)},${h - pad} L${pts[0][0].toFixed(1)},${h - pad} Z`;
  const dots = pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.4" fill="var(--gold)"/>`).join("");
  const lbl = `<text x="${pts[0][0]}" y="${h - 4}">${esc(shorten(data[0].label))}</text>
    <text x="${pts[pts.length - 1][0]}" y="${h - 4}" text-anchor="end">${esc(shorten(data[data.length - 1].label))}</text>`;
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    <path class="draw" d="${area}" fill="var(--gold)" fill-opacity="0.12" stroke="none"/>
    <path class="draw" d="${path}" fill="none" stroke="var(--gold)" stroke-width="2"/>
    ${dots}${lbl}
  </svg>`;
}

function barChartSVG(data) {
  if (!data || !data.length) return CHART_EMPTY_HTML;
  const w = 320, h = 150, pad = 22;
  const max = Math.max(1, ...data.map(d => d.value));
  const bw = (w - pad * 2) / data.length;
  const bars = data.map((d, i) => {
    const bh = Math.max(2, (d.value / max) * (h - pad - 24));
    const x = pad + i * bw + bw * 0.15;
    const y = h - pad - bh;
    return `<rect class="bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw * 0.7).toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="var(--crimson)"/>
            <text x="${(x + bw * 0.35).toFixed(1)}" y="${h - 6}" text-anchor="middle">${esc(shorten(d.label))}</text>
            <text class="val" x="${(x + bw * 0.35).toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="middle">${d.value}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">${bars}</svg>`;
}

function hBarChartHTML(data) {
  if (!data || !data.length) return CHART_EMPTY_HTML;
  const max = Math.max(1, ...data.map(d => d.value));
  return data.map(d => {
    const pct = d.value > 0 ? Math.max(3, Math.round((d.value / max) * 100)) : 0;
    return `<div class="hb">
      <span>${esc(d.label)}</span>
      <span class="hb-track"><span class="hb-fill" style="--w:${pct}%"></span></span>
      <span class="hb-val">${d.value}</span>
    </div>`;
  }).join("");
}

function trendsChartsHTML(data) {
  return `
    <div class="chart">
      <h4><svg class="ic" aria-hidden="true"><use href="#i-trend"/></svg>مسابقات ثبت‌شده در ۳۰ روز اخیر</h4>
      ${lineChartSVG(data.matches_by_day)}
    </div>
    <div class="chart">
      <h4><svg class="ic" aria-hidden="true"><use href="#i-cal-week"/></svg>مسابقات هفتگی (۸ هفتهٔ اخیر)</h4>
      ${barChartSVG(data.matches_by_week)}
    </div>
    <div class="chart">
      <h4><svg class="ic" aria-hidden="true"><use href="#i-school"/></svg>توزیع بازیکنان بر اساس کلاس</h4>
      ${hBarChartHTML(data.players_by_class)}
    </div>
    <div class="chart">
      <h4><svg class="ic" aria-hidden="true"><use href="#i-pawn"/></svg>توزیع نتایج مسابقات</h4>
      ${hBarChartHTML(data.results_distribution)}
    </div>
  `;
}

// ─── رندرکننده‌های ویو ───────────────────────────────────────────
const RENDERERS = {
  home: renderHome,
  classes: renderClasses,
  players: renderPlayers,
  matches: () => renderMatches("all"),
  top: () => renderTop("week"),
};

// ─── ساعت بالای صفحه ──────────────────────────────────────────
function tickClock() {
  if (clockEl) clockEl.textContent = new Date().toLocaleTimeString("fa-IR");
}
setInterval(tickClock, 1000);
tickClock();

// ─── رهگشا (دستیار هوشمند شناور) ───────────────────────────────
const ASSISTANT_SUGGESTIONS = [
  "وضعیت کلی مدرسه چطوره؟",
  "این هفته چند مسابقه ثبت شده؟",
  "نفرات برتر رو از کجا ببینم؟",
  "روند مسابقات اخیر چطور بوده؟",
];
const assistantState = { history: [], sending: false, sessionId: null, started: false };

const rgEl = document.getElementById("rg");
const rgFabEl = document.getElementById("rg-fab");
const rgLogEl = document.getElementById("assistant-log");
const rgSuggEl = document.getElementById("assistant-suggestions");
const rgFormEl = document.getElementById("assistant-form");
const rgInputEl = document.getElementById("assistant-input");

function openRg() {
  rgEl.classList.add("open");
  rgEl.setAttribute("aria-hidden", "false");
  rgFabEl.setAttribute("aria-expanded", "true");
  document.body.classList.add("rg-open");
  if (!assistantState.started) startAssistant();
  setTimeout(() => rgInputEl && rgInputEl.focus(), 300);
}
function closeRg() {
  rgEl.classList.remove("open");
  rgEl.setAttribute("aria-hidden", "true");
  rgFabEl.setAttribute("aria-expanded", "false");
  document.body.classList.remove("rg-open");
}
if (rgFabEl) rgFabEl.addEventListener("click", () => (rgEl.classList.contains("open") ? closeRg() : openRg()));
rgEl.querySelectorAll("[data-close]").forEach(el => el.addEventListener("click", closeRg));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && rgEl.classList.contains("open")) closeRg(); });

function scrollRgToEnd() { rgLogEl.scrollTop = rgLogEl.scrollHeight; }

function addBubble(role, text, animate = true) {
  const b = document.createElement("div");
  b.className = "bub " + (role === "user" ? "bub-user" : "bub-bot");
  if (!animate) b.style.animation = "none";
  b.textContent = text;
  rgLogEl.appendChild(b);
  scrollRgToEnd();
  return b;
}
function addTypingBubble() {
  const b = document.createElement("div");
  b.className = "bub bub-bot";
  b.innerHTML = `<span class="typing"><span></span><span></span><span></span></span>`;
  rgLogEl.appendChild(b);
  scrollRgToEnd();
  return b;
}

function startAssistant() {
  assistantState.started = true;
  if (assistantState.history.length) {
    assistantState.history.forEach(turn => addBubble(turn.role === "user" ? "user" : "bot", turn.text, false));
  } else {
    addBubble("bot", "سلام! من رهگشا، دستیار هوشمند این پنل هستم. هر سوالی دربارهٔ آمار یا بخش‌های پنل دارید، خوشحال می‌شوم کمک کنم.", false);
  }
  rgSuggEl.innerHTML = ASSISTANT_SUGGESTIONS.map(s => `<button type="button" class="sugg-chip">${esc(s)}</button>`).join("");
  rgSuggEl.querySelectorAll(".sugg-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      rgInputEl.value = chip.textContent;
      rgFormEl.requestSubmit();
    });
  });
  if (assistantState.history.length) rgSuggEl.classList.add("sugg-hidden");
}

async function sendAssistantMessage(text) {
  if (!text || assistantState.sending) return;
  assistantState.sending = true;
  rgInputEl.value = "";
  rgInputEl.disabled = true;
  document.getElementById("assistant-send").disabled = true;
  rgSuggEl.classList.add("sugg-hidden");

  addBubble("user", text);
  assistantState.history.push({ role: "user", text });
  const typingBubble = addTypingBubble();

  try {
    const url = new URL("/api/principal/assistant", window.location.origin);
    url.searchParams.set("k", KEY);
    const res = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: assistantState.history.slice(0, -1), session_id: assistantState.sessionId }),
    });
    const data = await res.json();
    if (data && data.session_id) assistantState.sessionId = data.session_id;
    typingBubble.remove();
    const reply = (data && data.ok && data.reply) ? data.reply : "متأسفانه پاسخی دریافت نشد. لطفاً مجدداً تلاش کنید.";
    addBubble("bot", reply);
    assistantState.history.push({ role: "model", text: reply });
  } catch (e) {
    typingBubble.remove();
    addBubble("bot", "متأسفانه ارتباط با سرور برقرار نشد. لطفاً اتصال اینترنت خود را بررسی و مجدداً تلاش کنید.");
    console.error(e);
  } finally {
    assistantState.sending = false;
    rgInputEl.disabled = false;
    document.getElementById("assistant-send").disabled = false;
    rgInputEl.focus();
  }
}
rgFormEl.addEventListener("submit", (e) => {
  e.preventDefault();
  sendAssistantMessage(rgInputEl.value.trim());
});

// ─── شروع ─────────────────────────────────────────────────────
bindNav();
switchView("home");

// ─── اسپلش خوش‌آمدگویی ─────────────────────────────────────────
(function runSplash() {
  const splashEl = document.getElementById("splash");
  const appEl = document.getElementById("app");
  if (!splashEl || !appEl) return;

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SPLASH_MS = reduceMotion ? 0 : 1400;
  const EXIT_MS = reduceMotion ? 0 : 700;

  setTimeout(() => {
    splashEl.classList.add("leaving");
    appEl.classList.add("reveal");
    document.body.classList.add("ready");
    setTimeout(() => {
      splashEl.remove();
      appEl.classList.remove("app-veil", "reveal");
    }, EXIT_MS);
  }, SPLASH_MS);
})();
