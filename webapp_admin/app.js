// پنل مدیر مدرسه — فقط‌خواندنی. هیچ درخواست POST/PUT/DELETE‌ای در این فایل وجود ندارد.

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
  trends: "روندها",
};

let currentView = "home";
const cache = {};

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
}

async function switchView(view) {
  currentView = view;
  setActiveNav(view);
  viewTitleEl.textContent = VIEW_TITLES[view] || "";
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span>در حال بارگذاری…</div>`;
  try {
    await RENDERERS[view]();
  } catch (e) {
    viewBodyEl.innerHTML = `<div class="empty-state">⚠️ خطا در دریافت اطلاعات.<br>لطفاً دوباره تلاش کنید.</div>`;
    console.error(e);
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
  viewBodyEl.innerHTML = `
    <div class="tabs" id="top-filter">
      <button class="tab-btn" data-f="week">این هفته</button>
      <button class="tab-btn" data-f="month">این ماه</button>
      <button class="tab-btn" data-f="all">کل دوران</button>
    </div>
    <div id="top-list"><div class="loading-state"><span class="spinner"></span></div></div>
  `;
  const btns = document.querySelectorAll("#top-filter .tab-btn");
  btns.forEach(b => b.classList.toggle("active", b.dataset.f === period));
  btns.forEach(b => b.addEventListener("click", () => renderTop(b.dataset.f)));

  const data = await api("/api/principal/top", { period });
  const rows = data.leaderboard || [];
  const box = document.getElementById("top-list");
  box.innerHTML = rows.length ? rows.map((r, i) => topRow(r, i)).join("") :
    `<div class="empty-state">در این بازه هنوز مسابقه‌ای با نتیجه ثبت نشده.</div>`;
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

async function renderTrends() {
  const data = await api("/api/principal/trends");
  viewBodyEl.innerHTML = `
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

const RENDERERS = {
  home: renderHome,
  classes: renderClasses,
  players: renderPlayers,
  matches: () => renderMatches("all"),
  top: () => renderTop("week"),
  trends: renderTrends,
};

// ─── ساعت بالای صفحه ──────────────────────────────────────────
function tickClock() {
  clockEl.textContent = new Date().toLocaleTimeString("fa-IR");
}
setInterval(tickClock, 1000);
tickClock();

// ─── خوش‌آمدگویی اولیه ────────────────────────────────────────
function typeWelcomeWord() {
  const word = "خوش آمدید";
  const wrap = document.getElementById("welcome-word");
  if (!wrap) return;
  [...word].forEach((ch, i) => {
    const span = document.createElement("span");
    span.className = "wl-char";
    span.style.setProperty("--i", i);
    span.textContent = ch === " " ? "\u00A0" : ch;
    wrap.appendChild(span);
  });
}

function playWelcome() {
  return new Promise(resolve => {
    const screen = document.getElementById("welcome-screen");
    if (!screen) { resolve(); return; }
    typeWelcomeWord();
    setTimeout(() => {
      screen.classList.add("wl-hide");
      screen.addEventListener("transitionend", () => {
        screen.remove();
        resolve();
      }, { once: true });
    }, 2200);
  });
}

// ─── شروع ─────────────────────────────────────────────────────
bindNav();
playWelcome().then(() => switchView("home"));
