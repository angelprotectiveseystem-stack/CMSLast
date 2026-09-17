// پنل مدیر مدرسه — تقریباً همه‌جا فقط‌خواندنی؛ تنها استثنا بخشِ «پنل مدیر»
// (تبِ admin) هست که چند درخواستِ POST برای روشن/خاموشِ پنلِ ادمین‌ها و
// انتخابِ دستیِ نفراتِ برتر می‌فرسته.

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
  admin: "پنل مدیر",
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

async function apiPost(path, body = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("k", KEY);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span></div>`;
  const data = await api("/api/principal/top", { period });
  const rows = data.leaderboard || [];

  if (data.mode === "manual") {
    // نفرات برتر دستی‌ست — بازه‌ی زمانی معنی نداره، فهرستی که مدیر ارشد
    // خودش انتخاب کرده به همون ترتیب نشون داده می‌شه.
    viewBodyEl.innerHTML = `
      <div class="manual-note">🎯 نمایشِ نفراتِ برتر روی حالتِ دستی تنظیم شده — این فهرست را مدیر ارشد از بخشِ «پنل مدیر» انتخاب کرده است.</div>
      <div id="top-list"></div>
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
  `;
  const btns = document.querySelectorAll("#top-filter .tab-btn");
  btns.forEach(b => b.classList.toggle("active", b.dataset.f === period));
  btns.forEach(b => b.addEventListener("click", () => renderTop(b.dataset.f)));
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

// ─── پنل مدیر: فقط اجرا (انتخابِ دستیِ نفرات برتر) ─────────────
// حالتِ خودکار/دستی خودش فقط از تلگرام (منوی تنظیماتِ پیشوا) عوض می‌شه؛
// این‌جا فقط همون حالت رو نشون می‌ده و، وقتی دستی‌ست، اجرا (انتخابِ
// بازیکن‌ها) در اختیارِ مدیر مدرسه قرار می‌گیره.
async function renderAdminPanel() {
  currentView = "admin";
  viewTitleEl.textContent = VIEW_TITLES.admin;
  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span></div>`;
  const data = await api("/api/principal/settings");
  drawAdminPanel(data);
}

function drawAdminPanel(data) {
  const manualMode = data.top_players_mode === "manual";
  viewBodyEl.innerHTML = `
    <div class="section-title">🏆 نمایشِ نفرات برتر</div>
    <div class="settings-card">
      <div class="settings-row">
        <div class="settings-row-txt">
          <div class="main-txt">شیوه‌ی فعلی: ${manualMode ? "🖐️ دستی" : "⚡ خودکار"}</div>
          <div class="sub-txt">این حالت فقط از تلگرام (تنظیماتِ ربات) قابل تغییره. خودکار یعنی بر اساسِ امتیازِ مسابقات؛ دستی یعنی خودتان پنج نفر را انتخاب می‌کنید.</div>
        </div>
      </div>
      ${manualMode
        ? `<button class="big-btn" id="open-top-manual">👥 برتران — انتخاب نفرات برتر</button>`
        : `<div class="manual-note">وقتی حالت به «دستی» تغییر کند، دکمه‌ی «برتران» برای انتخابِ نفراتِ برتر همین‌جا ظاهر می‌شود.</div>`
      }
    </div>
  `;

  const openBtn = document.getElementById("open-top-manual");
  if (openBtn) openBtn.addEventListener("click", renderTopManual);
}

function manualSlot(item) {
  if (!item) return `<div class="slot-card empty">خالی</div>`;
  return `
    <div class="slot-card filled" data-pid="${item.player_id}">
      <div class="top-rank">${item.rank}</div>
      <div class="top-info">
        <div class="main-txt">${esc(item.full_name)}</div>
        <div class="sub-txt">${esc(item.class_name)}</div>
      </div>
      <button class="slot-remove" data-pid="${item.player_id}" title="حذف">✕</button>
    </div>
  `;
}

async function renderTopManual() {
  currentView = "admin";
  viewTitleEl.textContent = "برتران";
  viewBodyEl.innerHTML = `<div class="loading-state"><span class="spinner"></span></div>`;

  const [manualData, candData] = await Promise.all([
    api("/api/principal/top-manual"),
    api("/api/principal/top-candidates"),
  ]);
  drawTopManual(manualData.list || [], candData.players || []);
}

function drawTopManual(manualList, candidates) {
  const byRank = {};
  manualList.forEach(i => { byRank[i.rank] = i; });
  const slots = [1, 2, 3, 4, 5].map(r => manualSlot(byRank[r])).join("");

  viewBodyEl.innerHTML = `
    <button class="back-btn" id="top-manual-back">→ بازگشت به پنل مدیر</button>
    <div class="section-title">۵ نفر برتر فعلی</div>
    <div class="card-list slot-list" id="slot-list">${slots}</div>

    <div class="section-title">👥 انتخاب از بین بازیکن‌های فعال (به ترتیبِ پیشنهادِ ربات)</div>
    <div class="search-box">
      <input type="text" id="candidates-search" placeholder="جستجوی نام بازیکن یا کلاس…" autocomplete="off">
      <span class="search-ic">🔍</span>
    </div>
    <div class="card-list" id="candidates-list"></div>
  `;

  document.getElementById("top-manual-back").addEventListener("click", renderAdminPanel);

  document.getElementById("slot-list").addEventListener("click", async (e) => {
    const btn = e.target.closest(".slot-remove");
    if (!btn) return;
    const pid = btn.dataset.pid;
    try {
      const res = await apiPost("/api/principal/top-manual-remove", { player_id: Number(pid) });
      const [candData] = await Promise.all([api("/api/principal/top-candidates")]);
      drawTopManual(res.list || [], candData.players || []);
    } catch (e) {
      alert("خطا در حذف. دوباره تلاش کنید.");
    }
  });

  const listEl = document.getElementById("candidates-list");
  const searchEl = document.getElementById("candidates-search");
  let openPid = null;

  function candidateRow(p) {
    const taken = !!p.manual_rank;
    return `
      <div class="row-card candidate-row" data-pid="${p.id}">
        <div>
          <div class="main-txt">${taken ? "✅ " : ""}${esc(p.full_name)}${taken ? ` <span class="rank-badge">رتبه ${p.manual_rank}</span>` : ""}</div>
          <div class="sub-txt">${esc(p.class_name)} · ${esc(p.games)} بازی · امتیاز ${esc(p.score)}</div>
        </div>
        <div class="badge-group">
          <span class="badge win">${esc(p.wins)}</span>
          <span class="badge draw">${esc(p.draws)}</span>
          <span class="badge loss">${esc(p.losses)}</span>
        </div>
      </div>
      <div class="rank-picker" id="rank-picker-${p.id}" hidden>
        <span class="rank-picker-lbl">این بازیکن از پنج نفر برتر چندم باشد؟</span>
        <div class="rank-picker-btns">
          ${[1, 2, 3, 4, 5].map(r => `<button class="rank-num-btn ${p.manual_rank === r ? "active" : ""}" data-pid="${p.id}" data-rank="${r}">${r}</button>`).join("")}
        </div>
      </div>
    `;
  }

  function draw() {
    const q = searchEl.value.trim().toLowerCase();
    const rows = q
      ? candidates.filter(p => (p.full_name || "").toLowerCase().includes(q) || (p.class_name || "").toLowerCase().includes(q))
      : candidates;
    listEl.innerHTML = rows.length ? rows.map(candidateRow).join("") :
      `<div class="empty-state">بازیکنی یافت نشد.</div>`;
  }

  listEl.addEventListener("click", async (e) => {
    const rankBtn = e.target.closest(".rank-num-btn");
    if (rankBtn) {
      const pid = Number(rankBtn.dataset.pid);
      const rank = Number(rankBtn.dataset.rank);
      try {
        const res = await apiPost("/api/principal/top-manual-set", { player_id: pid, rank });
        const candData = await api("/api/principal/top-candidates");
        openPid = null;
        drawTopManual(res.list || [], candData.players || []);
      } catch (e) {
        alert("خطا در ثبتِ رتبه. دوباره تلاش کنید.");
      }
      return;
    }
    const row = e.target.closest(".candidate-row");
    if (!row) return;
    const pid = row.dataset.pid;
    const picker = document.getElementById(`rank-picker-${pid}`);
    const wasOpen = openPid === pid;
    document.querySelectorAll(".rank-picker").forEach(p => (p.hidden = true));
    openPid = wasOpen ? null : pid;
    if (picker) picker.hidden = wasOpen;
  });

  searchEl.addEventListener("input", draw);
  draw();
}

const RENDERERS = {
  home: renderHome,
  classes: renderClasses,
  players: renderPlayers,
  matches: () => renderMatches("all"),
  top: () => renderTop("week"),
  trends: renderTrends,
  admin: renderAdminPanel,
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
