(function(){
"use strict";

var tg = window.Telegram ? window.Telegram.WebApp : null;
if(tg){ tg.ready(); tg.expand(); try{ tg.disableVerticalSwipes(); }catch(e){} }

try{
  var savedTheme = localStorage.getItem("chess_theme");
  if(savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
}catch(e){}

var params = new URLSearchParams(window.location.search);
var TOKEN = params.get("token") || (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param);
var INIT_DATA = tg ? tg.initData : "";
// وقتی از «لیستِ بازی‌ها» (مرورِ بازی‌های تمام‌شده) وارد می‌شویم، برای
// همه به‌جز پیشوا پارامترِ chat=0 ست می‌شود تا محتوای چتِ داخلِ همان بازی
// (که بینِ دو بازیکنِ اصلی رد و بدل شده) به بقیه نشان داده نشود. مقدارِ
// پیش‌فرض (نبودِ پارامتر) true است تا رفتارِ بازیِ زنده‌ی معمولی دست‌نخورده بماند.
var SHOW_CHAT = params.get("chat") !== "0";
var API = ""; // same-origin

var PIECE_GLYPH = { p:"♟", n:"♞", b:"♝", r:"♜", q:"♛", k:"♚" };
var FILES = ["a","b","c","d","e","f","g","h"];

// ─── افکت صوتی + هپتیک ──────────────────────────────────────
// همه‌ی صداها با WebAudio به‌صورت سینتتیک (بدون فایل صوتی خارجی)
// تولید می‌شوند تا وابسته به دانلود/کش asset نباشند و روی هر WebView
// فوراً و بدون تاخیر پخش شوند. AudioContext تا اولین ژست/تعامل کاربر
// (کلیک) در حالت suspended می‌ماند — این یک محدودیت استاندارد مرورگرهاست
// (از جمله WebView تلگرام)، پس در اولین touchstart/pointerdown صفحه آن
// را resume می‌کنیم.
var Sound = (function(){
  var ctx = null;
  var enabled = true;
  var unlocked = false;

  try{
    var savedPref = localStorage.getItem("chess_sound_enabled");
    if(savedPref === "0") enabled = false;
  }catch(e){}

  function getCtx(){
    if(!ctx){
      var Ctor = window.AudioContext || window.webkitAudioContext;
      if(!Ctor) return null;
      ctx = new Ctor();
    }
    return ctx;
  }

  function unlock(){
    if(unlocked) return;
    unlocked = true;
    var c = getCtx();
    if(c && c.state === "suspended") c.resume().catch(function(){});
  }
  ["touchstart","pointerdown","mousedown"].forEach(function(ev){
    document.addEventListener(ev, unlock, { once: true, passive: true });
  });

  // یک نتِ ساده با envelope نرم (attack سریع، decay نمایی) — برای هر
  // افکت با فرکانس/مدت/موج متفاوت صدا زده می‌شود.
  function tone(freq, dur, type, gainPeak, delay){
    if(!enabled) return;
    var c = getCtx();
    if(!c) return;
    if(c.state === "suspended") c.resume().catch(function(){});
    var t0 = c.currentTime + (delay || 0);
    var osc = c.createOscillator();
    var gain = c.createGain();
    osc.type = type || "sine";
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(gainPeak || 0.18, t0 + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain);
    gain.connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }

  return {
    setEnabled: function(v){
      enabled = v;
      try{ localStorage.setItem("chess_sound_enabled", v ? "1" : "0"); }catch(e){}
    },
    isEnabled: function(){ return enabled; },
    move: function(){ tone(392, 0.09, "triangle", 0.16); },
    capture: function(){ tone(220, 0.11, "square", 0.14); tone(150, 0.14, "square", 0.10, 0.03); },
    check: function(){ tone(880, 0.12, "sine", 0.18); tone(660, 0.16, "sine", 0.14, 0.07); },
    castle: function(){ tone(392, 0.08, "triangle", 0.15); tone(494, 0.1, "triangle", 0.13, 0.06); },
    promote: function(){ tone(523, 0.1, "sine", 0.16); tone(659, 0.1, "sine", 0.15, 0.08); tone(784, 0.14, "sine", 0.14, 0.16); },
    win: function(){ tone(523, 0.13, "sine", 0.18); tone(659, 0.13, "sine", 0.18, 0.11); tone(784, 0.2, "sine", 0.18, 0.22); },
    lose: function(){ tone(392, 0.16, "sine", 0.16); tone(311, 0.22, "sine", 0.15, 0.13); },
    draw: function(){ tone(440, 0.14, "sine", 0.15); tone(440, 0.14, "sine", 0.15, 0.16); },
    chatSend: function(){ tone(700, 0.06, "sine", 0.12); tone(1000, 0.05, "sine", 0.09, 0.045); },
    chatReceive: function(){ tone(500, 0.07, "sine", 0.13); tone(760, 0.08, "sine", 0.12, 0.05); }
  };
})();

// ─── هپتیک (Telegram HapticFeedback) با fallback به Vibration API ─────
// روی موبایل خارج از تلگرام (مثلاً مرورگر معمولی PWA) تلگرام در دسترس
// نیست؛ در آن حالت از navigator.vibrate استاندارد استفاده می‌شود تا
// هپتیک همیشه کار کند، نه فقط داخل اپ تلگرام.
var Haptics = {
  light: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    else if(navigator.vibrate) navigator.vibrate(10);
  },
  medium: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
    else if(navigator.vibrate) navigator.vibrate(20);
  },
  rigid: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("rigid");
    else if(navigator.vibrate) navigator.vibrate([15, 30, 15]);
  },
  warning: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("warning");
    else if(navigator.vibrate) navigator.vibrate([20, 40, 20]);
  },
  success: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    else if(navigator.vibrate) navigator.vibrate([15, 30, 15, 30, 15]);
  },
  error: function(){
    if(tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
    else if(navigator.vibrate) navigator.vibrate([40, 30, 40]);
  }
};

var chess = new Chess();
var state = {
  myColor: null,       // 'w' | 'b'
  status: "active",
  selected: null,
  legalTargets: [],
  lastMove: null,
  pollTimer: null,
  clockTimer: null,
  whiteTime: 300, blackTime: 300,
  turn: "w",
  myId: null, oppId: null, whiteId: null, blackId: null,
  myName: "شما", oppName: "حریف",
  gameOverShown: false,
  boardEls: {},
  chatTimer: null,
  lastChatId: 0,
  chatOpen: false,
  chatUnread: 0,
  isSpectator: false,
  pendingChat: [],       // پیام‌های خودم که هنوز از سرور تایید نشده‌اند (برای نمایش آنی بدون تاخیر)
  moveList: [],          // تاریخچه‌ی حرکات (SAN) — همیشه از سرور می‌آید، نه از chess.js
  drawOfferBy: null,
  drawModalShown: false,
  animating: false,
  squareSize: 0,   // پیکسل — اندازه‌ی یک خانه، فقط در sizeBoard() به‌روزرسانی می‌شود
  pieceEls: {},    // sq -> عنصرِ .piece-slot (منبعِ اصلیِ موقعیتِ هر مهره)
  historyRenderedCount: 0,
  liveSocket: null
};

// ─── Board sizing ───────────────────────────────────────────
// اندازه‌ی واقعی فضای در دسترس را با جاوااسکریپت اندازه می‌گیریم و به‌جای
// فرمول‌های تقریبی CSS (که با تغییر ارتفاع صفحه در دستگاه‌های مختلف/باز
// شدن کیبورد/تغییر UI تلگرام هماهنگ نبودند) روی خود تخته اعمال می‌کنیم.
// همین متغیر برای اندازه‌ی مهره‌ها هم استفاده می‌شود تا همیشه دقیقاً
// اندازه‌ی خانه‌ها باشند و جا نمانند یا اندازه‌شان نامتناسب نشود.
//
// نکته‌ی مهم برای رفع باگ «تغییر سایز تخته حین حرکت مهره»:
// اندازه‌گیری از روی .board-wrap با flex:1 انجام می‌شد؛ ارتفاع این
// عنصر به محتوای بالا/پایینش (کارت بازیکن‌ها، ردیف مهره‌های گرفته‌شده که
// طولش با هر حرکت عوض می‌شود) وابسته بود. با هر رندر/انیمیشن، مرورگر
// یک reflow می‌داد، عرض/ارتفاع board-wrap یک پیکسل نوسان می‌کرد، و چون
// sizeBoard روی رویداد window "resize" هم صدا زده می‌شد (که در برخی
// وب‌ویوها با تغییرات layout داخلی هم فایر می‌شود)، --board-size وسط
// انیمیشن عوض می‌شد و خانه‌ها/مهره‌ها یک لحظه پرش می‌کردند.
// راه‌حل: به‌جای اندازه‌گیری مکرر و واکنش به هر تغییر layout داخلی،
// یک ResizeObserver فقط روی #app (که ارتفاعش با viewport تعیین می‌شود،
// نه با محتوای متغیر) می‌گذاریم و اندازه را فقط وقتی واقعاً کانتینر
// اصلی عوض شده به‌روزرسانی می‌کنیم؛ و در حین جابه‌جایی فعال مهره (پرچم
// state.animating) هیچ به‌روزرسانی‌ای انجام نمی‌دهیم تا در وسط انیمیشن
// دست به --board-size زده نشود.
var boardSizeRAF = null;
function sizeBoard(){
  if(state.animating) return; // در حین حرکت مهره اندازه را دست نزن
  var wrap = document.querySelector(".board-wrap");
  var appEl = document.getElementById("app");
  if(!wrap || !appEl) return;
  if(boardSizeRAF) cancelAnimationFrame(boardSizeRAF);
  boardSizeRAF = requestAnimationFrame(function(){
    boardSizeRAF = null;
    var w = wrap.clientWidth;
    var h = wrap.clientHeight;
    var size = Math.floor(Math.min(w, h));
    if(size > 40){
      var current = getComputedStyle(document.documentElement).getPropertyValue("--board-size");
      var currentPx = parseFloat(current) || 0;
      // فقط وقتی تغییر واقعی و محسوس است (بیش از ۱px) اعمال کن تا از
      // نوسان‌های زیرپیکسلی حین ری‌فلوهای موقتی جلوگیری شود.
      if(Math.abs(currentPx - size) >= 1){
        document.documentElement.style.setProperty("--board-size", size + "px");
        state.squareSize = size / 8;
        repositionAllPiecesInstant();
      }
    }
  });
}
window.addEventListener("resize", sizeBoard);
window.addEventListener("orientationchange", function(){ setTimeout(sizeBoard, 50); });
if(window.visualViewport){
  window.visualViewport.addEventListener("resize", sizeBoard);
}
if(tg && tg.onEvent){
  try{ tg.onEvent("viewportChanged", sizeBoard); }catch(e){}
}
if(window.ResizeObserver){
  try{
    var appResizeObserver = new ResizeObserver(function(){ sizeBoard(); });
    document.addEventListener("DOMContentLoaded", function(){
      var appEl = document.getElementById("app");
      if(appEl) appResizeObserver.observe(appEl);
    });
  }catch(e){}
}

function $(id){ return document.getElementById(id); }
function showScreen(id){
  document.querySelectorAll(".screen").forEach(function(s){ s.classList.remove("active"); });
  $(id).classList.add("active");
}
function showError(msg){
  $("error-text").textContent = msg;
  showScreen("screen-error");
}

// ─── Avatars ────────────────────────────────────────────────
// حرفِ اولِ اسم همیشه به‌عنوانِ fallback در متنِ خودِ .avatar می‌ماند؛
// اگر url موجود بود، یک <img> روی آن (absolute) اضافه می‌شود که با یک
// فِیدِ نرم روی حرف ظاهر می‌شود، تا هم قبل از لودشدنِ عکس و هم در صورتِ
// خطا (کاربر عکسِ پروفایل ندارد/۴۰۴) صفحه هیچ‌وقت جای خالی نداشته باشد.
function setAvatar(el, name, url){
  el.textContent = (name || "؟").slice(0, 1);
  el.dataset.avatarUrl = url || "";
  var existing = el.querySelector(".avatar-img");
  if(existing) existing.remove();
  if(!url) return;
  var img = document.createElement("img");
  img.className = "avatar-img";
  img.alt = "";
  img.referrerPolicy = "no-referrer";
  var retried = false;
  img.addEventListener("load", function(){ img.classList.add("loaded"); });
  img.addEventListener("error", function(){
    // یک باگِ رایج در WebViewِ موبایل: اولین تلاشِ لودِ عکس گاهی به‌خاطرِ
    // یک قطعیِ خیلی کوتاهِ شبکه (نه چون عکس واقعاً وجود ندارد) شکست
    // می‌خورد. قبل از این‌که کامل رها شود و به حرفِ fallback برگردد، یک
    // بار دیگر امتحان می‌شود؛ اگر بازهم شکست خورد (لینک واقعاً منقضی/۴۰۴
    // شده)، به‌آرامی حذف می‌شود تا حرفِ زیرش دیده شود.
    if(!retried){
      retried = true;
      setTimeout(function(){ img.src = url; }, 600);
      return;
    }
    console.warn("Avatar image failed to load:", url);
    img.remove();
  });
  img.src = url;
  el.appendChild(img);
}

// ─── هندسه‌ی تخته (محاسبه‌ی اندیسی — بدونِ نیاز به اندازه‌گیریِ DOM) ──
// v4: موقعیتِ هر خانه/مهره صرفاً از رویِ اندیسِ منطقیِ ستون/ردیف (با درنظرِ
// چرخشِ تخته) و اندازه‌ی شناخته‌شده‌ی هر خانه (state.squareSize، فقط در
// sizeBoard به‌روزرسانی می‌شود) محاسبه می‌شود — نه از رویِ
// getBoundingClientRect خودِ عنصر. این یعنی هیچ‌وقت لازم نیست حینِ
// انیمیشن/کلیک/درگ یک لِی‌آوتِ همزمان (forced synchronous layout) از
// مرورگر خواسته شود، و چون مبنا اندیسِ منطقی است (نه ترتیبِ واقعیِ DOM یا
// جهتِ rtl/ltr)، اصلاً امکانِ «مسیرِ برعکس» وجود ندارد.
function squareColRow(sq){
  var file = FILES.indexOf(sq[0]);
  var rank = parseInt(sq[1], 10);
  var flip = state.myColor === "b";
  return {
    col: flip ? 7 - file : file,
    row: flip ? rank - 1 : 8 - rank
  };
}
function squarePixel(sq){
  var cr = squareColRow(sq);
  var size = state.squareSize || 0;
  return { x: cr.col * size, y: cr.row * size };
}
// معادلِ همان محاسبه، اما برعکس: از رویِ مختصاتِ صفحه (clientX/clientY) به
// نامِ خانه می‌رسد. به‌جای document.elementFromPoint (که چون مهره‌ها دیگر
// داخلِ خانه‌شان نیستند، ممکن است یک مهره‌ی *دیگر* را برگرداند، نه خانه‌ی
// زیرش)، مستقیماً از رویِ rect خودِ تخته و همان اندیسِ منطقی محاسبه
// می‌شود — قابل‌اعتماد صرف‌نظر از این‌که چه چیزی زیرِ انگشت رندر شده.
function squareFromPoint(clientX, clientY){
  var boardEl = $("board");
  var rect = boardEl.getBoundingClientRect();
  if(!rect.width || !rect.height) return null;
  var relX = clientX - rect.left, relY = clientY - rect.top;
  if(relX < 0 || relY < 0 || relX >= rect.width || relY >= rect.height) return null;
  var col = Math.min(7, Math.max(0, Math.floor(relX / (rect.width / 8))));
  var row = Math.min(7, Math.max(0, Math.floor(relY / (rect.height / 8))));
  var flip = state.myColor === "b";
  var file = flip ? 7 - col : col;
  var rank = flip ? row + 1 : 8 - row;
  return FILES[file] + rank;
}

// ─── Board build ────────────────────────────────────────────
// خانه‌ها (.square) فقط برای پس‌زمینه/هایلایت/دات‌های پیش‌نمایش می‌مانند.
// خودِ مهره‌ها دیگر داخلِ خانه‌شان appendChild نمی‌شوند؛ همه در یک لایه‌ی
// مستقلِ .pieces-layer (پایین‌تر از همین تابع ساخته می‌شود) با موقعیتِ
// absolute نگه‌داری می‌شوند — دلیلش در توضیحِ بالای «Piece movement engine»
// آمده.
function buildBoard(){
  var board = $("board");
  board.innerHTML = "";
  state.boardEls = {};
  state.pieceEls = {};
  var flip = state.myColor === "b";
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var rank = flip ? r : 7-r;
      var file = flip ? 7-c : c;
      var sq = FILES[file] + (rank+1);
      var el = document.createElement("div");
      el.className = "square " + (((r+c)%2===0) ? "light" : "dark");
      el.dataset.square = sq;
      board.appendChild(el);
      state.boardEls[sq] = el;
    }
  }
  var layer = document.createElement("div");
  layer.className = "pieces-layer";
  layer.id = "pieces-layer";
  board.appendChild(layer);
  // اندازه‌ی خانه را همین‌جا هم (نه فقط در رویدادِ resize) به‌روزرسانی
  // می‌کنیم، چون buildBoard معمولاً پیش از اولین sizeBoard صدا زده می‌شود
  // (مثلاً هنگامِ ورودِ اولیه به بازی) و مهره‌های اولیه باید از همان لحظه‌ی
  // ساخته‌شدن در مختصاتِ درست بنشینند.
  var boardRect = board.getBoundingClientRect();
  if(boardRect.width > 0) state.squareSize = boardRect.width / 8;
}

// همه‌ی مهره‌های موجود را فوراً (بدونِ انیمیشن) در موقعیتِ درستِ جدید
// می‌نشاند — فقط بعد از تغییرِ واقعیِ اندازه‌ی تخته (sizeBoard) لازم است،
// نه در هر حرکت. چون transform همیشه transition دارد، برای این‌که این
// جابه‌جایی پرش نکند، transition موقتاً خاموش می‌شود؛ یک reflowِ مشترک
// (نه یکی به‌ازای هر مهره) این حالت را قفل می‌کند و بعد transition دوباره
// روشن می‌شود.
function repositionAllPiecesInstant(){
  var sqs = Object.keys(state.pieceEls);
  if(!sqs.length) return;
  sqs.forEach(function(sq){
    var slot = state.pieceEls[sq];
    var p = squarePixel(sq);
    slot.style.transition = "none";
    slot.style.transform = "translate3d(" + p.x + "px," + p.y + "px,0)";
  });
  void state.pieceEls[sqs[0]].offsetWidth; // یک reflowِ مشترک برای کلِ دسته
  sqs.forEach(function(sq){ state.pieceEls[sq].style.transition = ""; });
}

// ─── گرفتن و کشیدنِ مهره‌ها (Drag & Drop) ───────────────────
// همان معماریِ قبلی (شبح دنبالِ انگشت، مهره‌ی اصلی تا لحظه‌ی رهاشدن سرِ
// جایش می‌ماند)، فقط sq از dataset.square خودِ .piece-slot خوانده می‌شود
// (نه از .closest(".square")، چون مهره دیگر داخلِ خانه نیست).
(function initPieceDrag(){
  var DRAG_THRESHOLD = 6; // پیکسل — کمتر از این یعنی تپِ ساده، نه درگ
  var drag = null; // { fromSq, pieceEl, ghost, startX, startY, rect, pointerId, moved }

  function makeGhost(pieceEl, rect){
    var g = pieceEl.cloneNode(true);
    g.classList.add("dragging");
    g.style.position = "fixed";
    g.style.right = "auto";
    g.style.bottom = "auto";
    g.style.margin = "0";
    g.style.left = rect.left + "px";
    g.style.top = rect.top + "px";
    g.style.width = rect.width + "px";
    g.style.height = rect.height + "px";
    g.style.pointerEvents = "none";
    g.style.zIndex = "999";
    document.body.appendChild(g);
    return g;
  }

  function clearDropHover(){
    Object.keys(state.boardEls).forEach(function(s){
      state.boardEls[s].classList.remove("drop-hover");
    });
    lastHoverSq = null;
  }

  $("board").addEventListener("pointerdown", function(e){
    if(drag) return;
    var pieceEl = e.target.closest ? e.target.closest(".piece") : null;
    if(!pieceEl) return;
    var slot = pieceEl.closest(".piece-slot");
    if(!slot) return;
    var sq = slot.dataset.square;
    if(state.isSpectator || !myTurn()) return;
    var piece = chess.get(sq);
    if(!piece || piece.color !== state.myColor) return;

    if(e.cancelable) e.preventDefault();

    state.selected = sq;
    state.legalTargets = chess.moves({ square: sq, verbose:true });
    paintHighlights();

    drag = {
      fromSq: sq, pieceEl: pieceEl, ghost: null,
      startX: e.clientX, startY: e.clientY, rect: pieceEl.getBoundingClientRect(),
      pointerId: e.pointerId, moved: false
    };
  });

  var lastHoverSq = null;
  var moveRaf = null, pendingMoveEvent = null;

  function applyDragMove(e){
    var dx = e.clientX - drag.startX, dy = e.clientY - drag.startY;
    if(!drag.moved){
      if(Math.abs(dx) < DRAG_THRESHOLD && Math.abs(dy) < DRAG_THRESHOLD) return;
      drag.moved = true;
      drag.pieceEl.style.opacity = "0"; // مهره‌ی واقعی موقتاً مخفی؛ شبح جایش دنبالِ انگشت می‌رود
      drag.ghost = makeGhost(drag.pieceEl, drag.rect);
    }
    drag.ghost.style.transform = "translate(" + dx + "px," + dy + "px) scale(1.18)";
    var overSq = squareFromPoint(e.clientX, e.clientY);
    var hoverSq = (overSq && overSq !== drag.fromSq) ? overSq : null;
    if(hoverSq !== lastHoverSq){
      if(lastHoverSq && state.boardEls[lastHoverSq]) state.boardEls[lastHoverSq].classList.remove("drop-hover");
      if(hoverSq && state.boardEls[hoverSq]) state.boardEls[hoverSq].classList.add("drop-hover");
      lastHoverSq = hoverSq;
    }
  }

  document.addEventListener("pointermove", function(e){
    if(!drag || e.pointerId !== drag.pointerId) return;
    if(e.cancelable) e.preventDefault();
    pendingMoveEvent = e;
    if(moveRaf) return;
    moveRaf = requestAnimationFrame(function(){
      moveRaf = null;
      if(drag && pendingMoveEvent) applyDragMove(pendingMoveEvent);
    });
  });

  function endDrag(e){
    if(!drag || e.pointerId !== drag.pointerId) return;
    var d = drag; drag = null;
    if(moveRaf){ cancelAnimationFrame(moveRaf); moveRaf = null; }
    pendingMoveEvent = null;
    clearDropHover();

    if(!d.moved) return; // تپِ ساده بوده؛ کلیکِ طبیعیِ بعدی طبقِ روالِ قبلی onSquareClick را صدا می‌زند

    d.pieceEl.style.opacity = "";
    if(d.ghost && d.ghost.parentNode) d.ghost.parentNode.removeChild(d.ghost);
    state.suppressNextClick = true; // کلیکِ سنتتیکِ بعد از این pointerup نباید دوباره پردازش شود

    var dropSq = squareFromPoint(e.clientX, e.clientY);
    var move = dropSq && state.legalTargets.find(function(m){ return m.to === dropSq; });
    if(move){
      if(move.flags.indexOf("p") >= 0){
        askPromotion(function(promo){ doMove(d.fromSq, dropSq, promo); });
      } else {
        doMove(d.fromSq, dropSq);
      }
    } else {
      state.selected = null;
      state.legalTargets = [];
      paintHighlights();
    }
  }
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);
})();

// یک کلیکِ واحد و delegated روی کلِ تخته به‌جای یک listener جداگانه روی
// هر ۶۴ خانه — چون مهره‌ها دیگر داخلِ خانه‌شان نیستند (بلکه در لایه‌ی
// جداگانه‌ی .pieces-layer روی همه‌شان قرار دارند)، کلیک روی یک خانه‌ی
// دارایِ مهره اول به خودِ .piece برخورد می‌کند، نه به .square زیرش؛
// squareFromPoint (محاسبه‌ی هندسی، نه DOM) هر دو حالت را یکسان پوشش
// می‌دهد.
$("board").addEventListener("click", function(e){
  if(state.suppressNextClick){ state.suppressNextClick = false; return; }
  var sq = squareFromPoint(e.clientX, e.clientY);
  if(sq) onSquareClick(sq);
});

function createPieceSlot(sq, type, color){
  var slot = document.createElement("div");
  slot.className = "piece-slot";
  slot.dataset.square = sq;
  slot.dataset.ptype = type;
  slot.dataset.pcolor = color;
  var inner = document.createElement("div");
  inner.className = "piece " + (color === "w" ? "white-p" : "black-p");
  inner.textContent = PIECE_GLYPH[type];
  slot.appendChild(inner);
  var p = squarePixel(sq);
  // نوشتنِ موقعیتِ نهایی همین‌جا، پیش از appendChild به صفحه: چون این
  // عنصر تا این لحظه اصلاً رندر نشده، مرورگر هیچ «مقدارِ قبلی»ای برای
  // transition ندارد که از آن فاصله بگیرد — یعنی هیچ‌وقت این مقدارِ
  // اولیه انیمیت نمی‌شود (مهره‌ی تازه هیچ‌وقت از گوشه‌ی تخته «سُر
  // نمی‌خورد»، دقیقاً سرِ خانه‌ی درستش ظاهر می‌شود).
  slot.style.transform = "translate3d(" + p.x + "px," + p.y + "px,0)";
  return slot;
}

// ─── Piece movement / animation engine (v4 — بازطراحیِ کامل) ─────────
//
// نسخه‌های قبلی (v1: CSS animation ساده؛ v2: CSS transition + ترفندِ
// FLIP با reflow اجباری؛ v3: کاملاً دستی با یک تیکِ rAF که هر فریم خودش
// transform را حساب و می‌نوشت) هرکدام یک مشکلِ ریشه‌ای مشترک داشتند:
// موقعیتِ هر مهره از رویِ اندازه‌گیریِ واقعیِ صفحه (getBoundingClientRect)
// و/یا جابه‌جاییِ فیزیکیِ خودِ عنصر بینِ خانه‌ها محاسبه می‌شد. این یعنی هر
// حرکت به یک لِی‌آوتِ همزمان (برای خواندنِ rect) و در v3 حتی به نوشتنِ
// دستیِ transform در هر فریم (روی ترد جاوااسکریپت، نه کامپوزیتور) وابسته
// بود — دقیقاً همان‌جایی که روی WebViewِ ضعیف (مخصوصاً وقتی هم‌زمان چتِ
// polling/تایمرِ ساعت هم در جریان است) فریم افت می‌کند و سکته حس می‌شود.
//
// v4 هیچ‌کدام از این‌ها را ندارد: موقعیتِ مقصد صرفاً از رویِ اندیسِ منطقیِ
// خانه محاسبه می‌شود (squarePixel، بدونِ هیچ اندازه‌گیری‌ای)، و چون
// .piece-slot همیشه و برای همیشه یک transition روی transform دارد (در
// CSS، نه جاوااسکریپت)، تنها کاری که این تابع لازم است انجام دهد نوشتنِ
// همان یک مقدارِ transform جدید است — خودِ مرورگر، روی ترد کامپوزیتور،
// از موقعیتِ *واقعیِ فعلی* (حتی وسطِ یک انیمیشنِ قبلیِ ناتمام) به مقصدِ
// جدید میان‌یابی می‌کند. نه FLIP، نه reflow، نه تیکِ دستی، نه نیاز به
// «بستنِ» انیمیشنِ قبلی قبل از شروعِ بعدی.
var pieceAnimGen = 0; // برای نادیده‌گرفتنِ callbackِ یک انیمیشنِ منسوخ‌شده (وقتی رندرِ جدید زودتر از پایانِ قبلی می‌رسد)

function renderPieces(animateFrom, animateTo, silent){
  var boardState = chess.board();
  var desired = {};
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(p) desired[FILES[c] + (8-r)] = p;
    }
  }
  var current = state.pieceEls;

  var vacated = [];
  var arrived = [];
  Object.keys(current).forEach(function(sq){
    var slot = current[sq];
    var d = desired[sq];
    if(!d || d.type !== slot.dataset.ptype || d.color !== slot.dataset.pcolor){
      vacated.push({ sq: sq, type: slot.dataset.ptype, color: slot.dataset.pcolor, el: slot });
    }
  });
  Object.keys(desired).forEach(function(sq){
    var d = desired[sq], slot = current[sq];
    if(!slot || slot.dataset.ptype !== d.type || slot.dataset.pcolor !== d.color){
      arrived.push({ sq: sq, type: d.type, color: d.color });
    }
  });

  if(!vacated.length && !arrived.length){ paintHighlights(); return; }

  function takeVacated(sq){
    for(var i=0;i<vacated.length;i++) if(vacated[i].sq === sq) return vacated.splice(i,1)[0];
    return null;
  }
  function takeArrived(sq){
    for(var i=0;i<arrived.length;i++) if(arrived[i].sq === sq) return arrived.splice(i,1)[0];
    return null;
  }
  function takeArrivedByType(type, color){
    for(var i=0;i<arrived.length;i++) if(arrived[i].type === type && arrived[i].color === color) return arrived.splice(i,1)[0];
    return null;
  }

  var moves = [];
  // ۱) جفت‌شدن صریح بر اساس حرکت اعلام‌شده (from/to همان حرکتی که رخ داده)
  if(animateFrom && animateTo){
    var v0 = takeVacated(animateFrom);
    if(v0){
      var a0 = takeArrived(animateTo);
      if(a0) moves.push({ el: v0.el, fromSq: v0.sq, toSq: a0.sq, toType: a0.type });
      else vacated.push(v0);
    }
  }
  // ۲) بقیه‌ی مهره‌های جابه‌جا‌شده بر اساس نوع+رنگ یکسان جفت می‌شوند (قلعه، یا چند حرکتِ هم‌زمانِ سرور)
  vacated.slice().forEach(function(v){
    var a = takeArrivedByType(v.type, v.color);
    if(a){
      takeVacated(v.sq);
      moves.push({ el: v.el, fromSq: v.sq, toSq: a.sq, toType: a.type });
    }
  });

  var didPromote = false;
  moves.forEach(function(m){
    delete state.pieceEls[m.fromSq];
    state.pieceEls[m.toSq] = m.el;
    m.el.dataset.square = m.toSq;
    var inner = m.el.querySelector(".piece");
    if(m.el.dataset.ptype !== m.toType){ // ترفیع: نوع مهره عوض شده
      inner.textContent = PIECE_GLYPH[m.toType];
      m.el.dataset.ptype = m.toType;
      didPromote = true;
    }
  });

  // باقی‌مانده‌ی vacated یعنی واقعاً «گرفته‌شده‌اند» — محوشدنشان با لحظه‌ی
  // واقعیِ رسیدنِ مهاجم هماهنگ می‌شود (دقیقاً مثل chess.com)، نه فوری.
  var didCapture = vacated.length > 0;
  var captureFinishers = vacated.map(function(v){
    var removed = false;
    return function(){
      if(removed) return;
      removed = true;
      var inner = v.el.querySelector(".piece");
      inner.classList.add("captured-anim");
      setTimeout(function(){ if(v.el.parentNode) v.el.parentNode.removeChild(v.el); }, 220);
    };
  });
  if(!moves.length) captureFinishers.forEach(function(fn){ fn(); });
  var captureFinishersBySquare = {};
  vacated.forEach(function(v, i){
    if(!captureFinishersBySquare[v.sq]) captureFinishersBySquare[v.sq] = [];
    captureFinishersBySquare[v.sq].push(captureFinishers[i]);
  });
  var didCastle = !didCapture && moves.length === 2;

  var layer = $("pieces-layer");
  // باقی‌مانده‌ی arrived یعنی مهره‌ی کاملاً تازه (بار اول لود صفحه، یا
  // ترفیعی که جفتش پیدا نشد) — با یک پاپ کوچک ظاهر می‌شود.
  arrived.forEach(function(a){
    var slot = createPieceSlot(a.sq, a.type, a.color);
    slot.querySelector(".piece").classList.add("landed");
    layer.appendChild(slot);
    state.pieceEls[a.sq] = slot;
  });

  if(moves.length){
    pieceAnimGen++;
    var myGen = pieceAnimGen;
    state.animating = true;
    var maxDur = 0;
    moves.forEach(function(m){
      var fromCR = squareColRow(m.fromSq), toCR = squareColRow(m.toSq);
      var squareDist = Math.sqrt(Math.pow(toCR.col - fromCR.col, 2) + Math.pow(toCR.row - fromCR.row, 2));
      // مدت‌زمانِ حرکت بر اساسِ تعدادِ خانه‌ها (نه فاصله‌ی خامِ پیکسلی)، پس
      // مستقل از اندازه‌ی صفحه/تراکمِ پیکسلیِ گوشی همیشه یک حسِ یکسان دارد.
      var dur = Math.max(160, Math.min(420, 150 + squareDist * 55));
      maxDur = Math.max(maxDur, dur);
      var inner = m.el.querySelector(".piece");
      var p = squarePixel(m.toSq);
      inner.classList.add("moving");
      m.el.style.transitionDuration = dur + "ms";
      // فقط همین یک نوشتن لازم است — transition (همیشه‌فعال، در CSS)
      // بقیه‌ی کار را روی ترد کامپوزیتور انجام می‌دهد.
      m.el.style.transform = "translate3d(" + p.x + "px," + p.y + "px,0)";
      m.el._animGen = (m.el._animGen || 0) + 1;
      var gen = m.el._animGen;
      setTimeout(function(){
        if(m.el._animGen !== gen) return; // یک حرکتِ جدیدتر این مهره را قبل از پایان جایگزین کرده
        inner.classList.remove("moving");
        var capFns = captureFinishersBySquare[m.toSq];
        if(capFns) capFns.forEach(function(fn){ fn(); });
      }, dur);
    });
    setTimeout(function(){
      if(pieceAnimGen === myGen){ state.animating = false; sizeBoard(); }
    }, maxDur + 20);
    // شبکه‌ی ایمنیِ نهایی: هر مهره‌ی گرفته‌شده‌ای که هنوز محو نشده (مثلاً
    // en passant) با تأخیرِ کوتاهی محو می‌شود تا هیچ‌وقت روی صفحه گیر نکند.
    setTimeout(function(){ captureFinishers.forEach(function(fn){ fn(); }); }, maxDur + 60);
  }

  paintHighlights();

  if(!silent){
    var isCheckNow = chess.in_check ? chess.in_check() : chess.inCheck();
    if(didPromote){ Sound.promote(); Haptics.medium(); }
    else if(isCheckNow){ Sound.check(); Haptics.rigid(); }
    else if(didCastle){ Sound.castle(); Haptics.light(); }
    else if(didCapture){ Sound.capture(); Haptics.medium(); }
    else { Sound.move(); Haptics.light(); }
  }
}

function paintHighlights(){
  Object.keys(state.boardEls).forEach(function(sq){
    var el = state.boardEls[sq];
    el.classList.remove("selected","last-from","last-to","check");
    var dots = el.querySelectorAll(".move-dot");
    dots.forEach(function(d){ d.remove(); });
  });
  Object.keys(state.pieceEls).forEach(function(sq){
    state.pieceEls[sq].querySelector(".piece").classList.remove("piece-selected");
  });
  if(state.lastMove){
    if(state.boardEls[state.lastMove.from]) state.boardEls[state.lastMove.from].classList.add("last-from");
    if(state.boardEls[state.lastMove.to]) state.boardEls[state.lastMove.to].classList.add("last-to");
  }
  if(state.selected){
    var selEl = state.boardEls[state.selected];
    selEl.classList.add("selected");
    var selSlot = state.pieceEls[state.selected];
    if(selSlot) selSlot.querySelector(".piece").classList.add("piece-selected");
    // پیش‌نمایش حرکات (دات‌ها) عمداً حذف شده و نباید دوباره اضافه شود.
  }
  if(chess.in_check ? chess.in_check() : chess.inCheck()){
    var kingColor = chess.turn();
    var boardState = chess.board();
    for(var r=0;r<8;r++) for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(p && p.type==="k" && p.color===kingColor){
        var sq = FILES[c] + (8-r);
        if(state.boardEls[sq]) state.boardEls[sq].classList.add("check");
      }
    }
  }
}

function myTurn(){
  return !state.isSpectator && state.status === "active" && chess.turn() === state.myColor;
}

function onSquareClick(sq){
  if(state.suppressNextClick){ state.suppressNextClick = false; return; }
  if(state.isSpectator) return;
  if(!myTurn()) return;
  var piece = chess.get(sq);
  if(state.selected){
    var move = state.legalTargets.find(function(m){ return m.to === sq; });
    if(move){
      if(move.flags.indexOf("p") >= 0){
        askPromotion(function(promo){ doMove(state.selected, sq, promo); });
      } else {
        doMove(state.selected, sq);
      }
      return;
    }
  }
  if(piece && piece.color === state.myColor){
    state.selected = sq;
    state.legalTargets = chess.moves({ square: sq, verbose:true });
  } else {
    state.selected = null;
    state.legalTargets = [];
  }
  paintHighlights();
}

function askPromotion(cb){
  var modal = $("promo-modal");
  var opts = $("promo-options");
  opts.innerHTML = "";
  ["q","r","b","n"].forEach(function(type){
    var el = document.createElement("div");
    el.className = "piece " + (state.myColor==="w" ? "white-p" : "black-p");
    el.textContent = PIECE_GLYPH[type];
    el.addEventListener("click", function(){
      modal.classList.add("hidden");
      cb(type);
    });
    opts.appendChild(el);
  });
  modal.classList.remove("hidden");
}

function doMove(from, to, promotion){
  var move = chess.move({ from: from, to: to, promotion: promotion || "q" });
  if(!move) return;
  // صدا/هپتیکِ خودِ حرکت اینجا دیگر پخش نمی‌شود — renderPieces (که چند
  // خط پایین‌تر صدا زده می‌شود) بر اساس دیفِ واقعیِ صفحه (گرفتن/قلعه/
  // ترفیع/کیش) این کار را انجام می‌دهد، هم برای حرکات خودم و هم حرکات
  // حریف، تا هیچ اتفاقی دوبار صدا/لرزش نگیرد.
  state.selected = null;
  state.legalTargets = [];
  state.lastMove = { from: from, to: to };
  renderPieces(from, to);
  renderCaptured();
  syncHistory(state.moveList.concat([move.san]));
  updateTurnBanner();
  // ارسال به سرور و چک پایان‌بازی (که خودش یک تولید کامل حرکات مجاز در
  // chess.js است) عمداً یک تیک بعد اجرا می‌شوند — نه چون خودشان کند
  // هستند، بلکه چون همین‌جا، در همان تسکِ همزمانی که renderPieces() شروعِ
  // انیمیشن را به یک requestAnimationFrame موکول کرده، هر کارِ اضافه‌ی
  // synchronous مستقیماً به بودجه‌ی زمانیِ همان فریم اضافه می‌شود. با
  // setTimeout(...,0) این کارها بعد از این‌که مرورگر فرصت رسم فریم اول
  // انیمیشن را داشت اجرا می‌شوند.
  setTimeout(function(){
    sendMove(move);
    checkLocalGameOver();
  }, 0);
}

// ─── Networking ─────────────────────────────────────────────
function apiPost(path, body){
  return fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ token: TOKEN, init_data: INIT_DATA }, body || {}))
  }).then(function(r){ return r.json(); });
}
function apiGet(path){
  // uid/name هم فرستاده می‌شوند (فقط برای «بیننده‌ی فعال»؛ اعتبارسنجیِ
  // امنیتیِ حرکت همچنان روی init_data در apiPost انجام می‌شود، نه اینجا) —
  // تا سرور بتواند حضورِ لحظه‌ایِ بیننده‌ها را در /api/state ثبت کند و به
  // دو بازیکن نشان دهد چه کسی الان دارد تماشا می‌کند.
  var u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
  var extra = "";
  if(u && u.id){
    extra = "&uid=" + encodeURIComponent(u.id) + "&name=" + encodeURIComponent(u.first_name || u.username || "");
  }
  return fetch(API + path + "?token=" + encodeURIComponent(TOKEN) + extra).then(function(r){ return r.json(); });
}

function sendMove(move){
  apiPost("/api/move", { from: move.from, to: move.to, promotion: move.promotion })
    .then(function(res){
      if(!res.ok){
        // سرور حرکت را رد کرد (مثلاً چون شطرنج زنده موقتاً قفل/غیرفعال شده)؛
        // حرکت محلیِ خوش‌بینانه را برمی‌گردانیم تا صفحه با واقعیت هماهنگ بماند.
        chess.undo();
        var revertedMoves = state.moveList.length ? state.moveList.slice(0, -1) : state.moveList;
        state.selected = null;
        state.legalTargets = [];
        state.lastMove = null;
        renderPieces(null, null, true); // silent: این یک حرکتِ واقعی نیست، فقط بازگردانیِ optimistic-update رد‌شده است
        renderCaptured();
        syncHistory(revertedMoves);
        updateTurnBanner();
        setConnStatus(false);
        if(res.error) alert(res.error);
      } else {
        setConnStatus(true);
        applyServerState(res.state, false);
        if(res.state.moves){ syncHistory(res.state.moves); }
      }
    })
    .catch(function(){ setConnStatus(false); });
}

function setConnStatus(ok){
  var dot = document.querySelector("#conn-status .dot");
  $("conn-text").textContent = ok ? "متصل" : "قطع ارتباط";
  dot.style.background = ok ? "var(--success)" : "var(--danger)";
}

function pollState(){
  apiGet("/api/state").then(function(res){
    if(!res.ok){
      setConnStatus(false);
      if(res.error){
        // یعنی سرور صراحتاً بازی را رد کرد (نه یک قطعی موقت شبکه) — مثلاً
        // چون شطرنج زنده قفل/غیرفعال شده؛ همه‌چیز را متوقف می‌کنیم تا
        // صفحه به‌جای ادامه‌ی بی‌نتیجه، پیام روشنی نشان بدهد.
        clearInterval(state.pollTimer);
        clearInterval(state.clockTimer);
        clearInterval(state.chatTimer);
        showError(res.error);
      }
      return;
    }
    setConnStatus(true);
    applyServerState(res.state, true);
  }).catch(function(){ setConnStatus(false); });
}

// ─── Real-time push (WebSocket) ────────────────────────────────
// رفع ریشه‌ای حسِ «لگ»: قبلاً تنها راهِ دیدنِ حرکتِ حریف poll هر ۱.۵ ثانیه
// بود، یعنی صرف‌نظر از روانیِ خودِ انیمیشن، تا ۱.۵ ثانیه + رفت‌وبرگشتِ
// شبکه طول می‌کشید تا اصلاً چیزی برای انیمیت‌کردن برسد. حالا سرور همان
// لحظه‌ی ثبتِ حرکت یک پیامِ کوچک از طریق WebSocket پوش می‌کند و این تابع
// بلافاصله pollState را صدا می‌زند — بدون صبر برای دورِ بعدیِ تایمر.
// اگر WebSocket به هر دلیلی (فیلترینگ، افتادن اتصال) قطع شود، خودش با
// backoff دوباره وصل می‌شود و در همین حین تایمرِ ۴ ثانیه‌ایِ poll به‌عنوان
// شبکه‌ی ایمنی همچنان کار می‌کند — یعنی بدترین حالت هم عقب‌گرد به همان
// رفتار قبلی است، نه از کار افتادن کامل.
function connectLiveSocket(){
  if(!TOKEN || typeof WebSocket !== "function") return;
  var proto = location.protocol === "https:" ? "wss:" : "ws:";
  var url = proto + "//" + location.host + "/ws/" + encodeURIComponent(TOKEN);
  var retryDelay = 1000;
  function open(){
    var ws;
    try{ ws = new WebSocket(url); }catch(e){ scheduleRetry(); return; }
    state.liveSocket = ws;
    ws.onopen = function(){
      retryDelay = 1000;
      pollState(); // هر چیزی که در فاصله‌ی قطعی جا مانده را بلافاصله بگیر
    };
    ws.onmessage = function(){ pollState(); };
    ws.onclose = scheduleRetry;
    ws.onerror = function(){ try{ ws.close(); }catch(e){} };
  }
  function scheduleRetry(){
    state.liveSocket = null;
    setTimeout(open, retryDelay);
    retryDelay = Math.min(retryDelay * 1.6, 15000);
  }
  open();
}

function fenPly(fen){
  var parts = (fen || "").split(" ");
  var turn = parts[1];
  var fullmove = parseInt(parts[5], 10) || 1;
  return (fullmove - 1) * 2 + (turn === "b" ? 1 : 0);
}

function applyServerState(s, fromPoll){
  if(!s) return;
  var incomingFen = s.fen;
  if(incomingFen && incomingFen !== chess.fen()){
    if(fenPly(incomingFen) < fenPly(chess.fen())){
      // This response is older than what we already have locally — it's a
      // poll that raced with our own move and read the DB before it was
      // written. Applying it would yank the piece back for a moment, so
      // we just drop it; the next poll will bring the correct position.
      return;
    }
    var prevLast = state.lastMove;
    chess.load(incomingFen);
    state.lastMove = s.last_move || prevLast;
    renderPieces(state.lastMove && state.lastMove.from, state.lastMove && state.lastMove.to);
    renderCaptured();
    if(s.moves) syncHistory(s.moves);
  }
  state.turn = chess.turn();
  // آواتار فقط وقتی واقعاً عوض شده به‌روزرسانی می‌شود (نه هر poll) تا
  // تصویرِ در حالِ نمایش هر بار دوباره از سرور fetch/فِید نشود.
  var newMyAvatar = state.myColor === "w" ? s.white_avatar : s.black_avatar;
  var newOppAvatar = state.myColor === "w" ? s.black_avatar : s.white_avatar;
  if($("avatar-bottom").dataset.avatarUrl !== (newMyAvatar || "")) setAvatar($("avatar-bottom"), state.myName, newMyAvatar);
  if($("avatar-top").dataset.avatarUrl !== (newOppAvatar || "")) setAvatar($("avatar-top"), state.oppName, newOppAvatar);
  if(fromPoll){
    // قبلاً هر ۱.۵ ثانیه زمان محلی (که هر ثانیه تیک می‌خورد) با مقدار
    // سرور جایگزین می‌شد، حتی وقتی اختلافشان فقط چند صدم ثانیه بود؛
    // همین باعث می‌شد ساعت هر بار «سکته» بزند و یک لحظه بپرد جلو/عقب.
    // حالا فقط وقتی اختلاف واقعی و محسوس باشد (مثلاً تب پس‌زمینه بوده)
    // با سرور همگام می‌شویم، وگرنه شمارش نرم محلی ادامه پیدا می‌کند.
    if(Math.abs((s.white_time||0) - state.whiteTime) > 2) state.whiteTime = s.white_time;
    if(Math.abs((s.black_time||0) - state.blackTime) > 2) state.blackTime = s.black_time;
  } else {
    state.whiteTime = s.white_time;
    state.blackTime = s.black_time;
  }
  updateClocks();
  updateTurnBanner();
  updateDrawOfferUI(s);
  updateSpectatorsBanner(s.spectators);
  if(s.status !== "active" && !state.gameOverShown){
    state.status = s.status;
    showGameOver(s.status, s.winner_id, s.white_elo_change, s.black_elo_change);
  }
}

// ─── Draw offers ──────────────────────────────────────────────
function updateDrawOfferUI(s){
  if(state.isSpectator || state.status !== "active"){
    $("draw-modal-overlay").classList.add("hidden");
    return;
  }
  state.drawOfferBy = s.draw_offer_by || null;
  var iOffered = state.drawOfferBy && String(state.drawOfferBy) === String(state.myId);
  var theyOffered = state.drawOfferBy && !iOffered;

  $("btn-draw").disabled = !!state.drawOfferBy;
  $("btn-draw").textContent = iOffered ? "در انتظار پاسخ حریف..." : "پیشنهاد تساوی";

  if(theyOffered && !state.drawModalShown){
    state.drawModalShown = true;
    $("draw-modal-overlay").classList.remove("hidden");
  } else if(!theyOffered){
    state.drawModalShown = false;
    $("draw-modal-overlay").classList.add("hidden");
  }
}

function respondToDraw(accept){
  $("draw-modal-overlay").classList.add("hidden");
  state.drawModalShown = false;
  apiPost("/api/draw_response", { accept: accept }).then(function(res){
    if(res.ok) applyServerState(res.state, false);
  });
}
$("btn-draw-accept").addEventListener("click", function(){ respondToDraw(true); });
$("btn-draw-decline").addEventListener("click", function(){ respondToDraw(false); });

// ─── Captured pieces / history ──────────────────────────────
var STANDARD_COUNTS = { p:8, n:2, b:2, r:2, q:1 };
function renderCaptured(){
  // قبلاً از chess.history() استفاده می‌شد که با هر chess.load() (یعنی هر بار
  // که حرکت حریف از سرور می‌رسید) پاک می‌شد. حالا مستقیم از روی وضعیت فعلی
  // صفحه محاسبه می‌شود، پس همیشه درست است، حتی بعد از رفرش صفحه.
  var boardState = chess.board();
  var onBoard = { w:{p:0,n:0,b:0,r:0,q:0}, b:{p:0,n:0,b:0,r:0,q:0} };
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(p && p.type !== "k") onBoard[p.color][p.type]++;
    }
  }
  var captured = { w: [], b: [] };
  Object.keys(STANDARD_COUNTS).forEach(function(t){
    var missingWhite = STANDARD_COUNTS[t] - onBoard.w[t];
    for(var i=0;i<missingWhite;i++) captured.w.push(t);
    var missingBlack = STANDARD_COUNTS[t] - onBoard.b[t];
    for(var i=0;i<missingBlack;i++) captured.b.push(t);
  });
  var topIsWhite = state.myColor === "b";
  var order = { p:1,n:3,b:3,r:5,q:9,k:0 };
  captured.w.sort(function(a,b){ return order[a]-order[b]; });
  captured.b.sort(function(a,b){ return order[a]-order[b]; });
  // باگِ «مهره‌های گرفته‌شده توی لیستِ اشتباه»: captured.w یعنی مهره‌های
  // *خودِ سفید* که از بین رفته‌اند (یعنی سیاه آن‌ها را گرفته)، نه مهره‌هایی
  // که سفید گرفته. ردیفِ هر بازیکن باید تروفیِ خودش را نشان بدهد — یعنی
  // مهره‌های *حریف* که گرفته — پس برای ردیفِ سفید باید captured.b نشان داده
  // شود (چیزی که سفید از سیاه گرفته)، نه captured.w. قبلاً برعکس بود.
  $("captured-top").textContent = (topIsWhite ? captured.b : captured.w).map(function(t){ return PIECE_GLYPH[t]; }).join("");
  $("captured-bottom").textContent = (topIsWhite ? captured.w : captured.b).map(function(t){ return PIECE_GLYPH[t]; }).join("");

  // ─── امتیازِ برتریِ مادی (کنارِ مهره‌های گرفته‌شده) ──────────────
  // captured.b = مهره‌های سیاه که از بین رفته‌اند = چیزی که *سفید* گرفته؛
  // captured.w = مهره‌های سفید که از بین رفته‌اند = چیزی که *سیاه* گرفته.
  // پس امتیازِ سفید = مجموعِ ارزشِ captured.b و برعکس. فقط طرفی که برتری
  // داره امتیازش («+N») رو نشون می‌ده، دقیقاً مثل chess.com.
  function sumValue(list){
    var total = 0;
    for(var i=0;i<list.length;i++) total += (order[list[i]] || 0);
    return total;
  }
  var whiteScore = sumValue(captured.b) - sumValue(captured.w);
  var blackScore = -whiteScore;
  var topScore = topIsWhite ? whiteScore : blackScore;
  var bottomScore = topIsWhite ? blackScore : whiteScore;
  $("captured-top-score").textContent = topScore > 0 ? ("+" + topScore) : "";
  $("captured-bottom-score").textContent = bottomScore > 0 ? ("+" + bottomScore) : "";
}

function renderHistory(){
  // از state.moveList استفاده می‌شود که همیشه از سرور سینک می‌شود، نه از
  // chess.history() که با هر chess.load() (بعد از هر حرکت حریف) خالی می‌شد
  // و همین باعث می‌شد تاریخچه‌ی حرکات کار نکند.
  var list = $("history-list");
  var moves = state.moveList || [];
  list.innerHTML = "";
  if(!moves.length){
    var empty = document.createElement("div");
    empty.className = "chat-empty";
    empty.textContent = "هنوز حرکتی ثبت نشده";
    list.appendChild(empty);
    state.historyRenderedCount = 0;
    return;
  }
  for(var i=0;i<moves.length;i+=2){
    var row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = '<span class="history-num">' + (i/2+1) + '.</span><span class="history-move">' + moves[i] + '</span><span class="history-move">' + (moves[i+1]||"") + '</span>';
    list.appendChild(row);
  }
  list.scrollTop = list.scrollHeight;
  state.historyRenderedCount = moves.length;
}

// یک ردیف/خانه‌ی جدید تاریخچه را بدون بازسازی کل لیست اضافه می‌کند.
// فقط برای حالتی امن است که دقیقاً یک حرکت به انتهای moveList اضافه شده باشد
// (چک آن در syncHistory انجام می‌شود).
function appendHistoryMove(san){
  var list = $("history-list");
  var empty = list.querySelector(".chat-empty");
  if(empty) empty.remove();
  var idx = state.moveList.length - 1;
  if(idx % 2 === 0){
    var row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = '<span class="history-num">' + (idx/2+1) + '.</span><span class="history-move">' + san + '</span><span class="history-move"></span>';
    list.appendChild(row);
  } else {
    var rows = list.querySelectorAll(".history-row");
    var lastRow = rows[rows.length-1];
    if(!lastRow){ renderHistory(); return; }
    var spans = lastRow.querySelectorAll(".history-move");
    if(spans[1]) spans[1].textContent = san; else { renderHistory(); return; }
  }
  list.scrollTop = list.scrollHeight;
  state.historyRenderedCount = state.moveList.length;
}

// رفع باگ ریشه‌ای «سکته‌ی» انیمیشن حرکت مهره: renderHistory() قبلاً با
// innerHTML="" کل لیست تاریخچه را (که در یک بازی طولانی می‌تواند ده‌ها
// ردیف DOM باشد) روی *هر* حرکت — هم حرکت خودم (در doMove) و هم هر حرکت
// حریف که هر ۱.۵ ثانیه از poll می‌رسید (در applyServerState) — از نو
// می‌ساخت. این کار، همراه با رندر تکراری بعد از تایید سرور در sendMove،
// دقیقاً همان تسکِ سینک روی ترد اصلی بود که renderPieces() سعی داشت با
// موکول‌کردن شروعِ خودِ انیمیشن به requestAnimationFrame از آن دور بماند؛
// چون آن رندرها هم در همان تسکِ همزمان (قبل از رسیدن به رویداد بعدی حلقه)
// اجرا می‌شدند، حجمشان مستقیماً به بودجه‌ی زمانیِ فریم اضافه می‌شد و روی
// گوشی‌های ضعیف‌تر باعث جاماندن فریم اول انیمیشن (= همان سکته) می‌شد.
// syncHistory به‌جای بازسازی کامل، فقط وقتی که واقعاً دقیقاً یک حرکت به
// انتها اضافه شده (رایج‌ترین حالت) یک عنصر DOM اضافه می‌کند؛ و وقتی
// چیزی واقعاً تغییر نکرده (مثلاً تاییدیه‌ی سرور بعد از حرکت خودم که قبلاً
// محلی رندر شده) هیچ کاری انجام نمی‌دهد. فقط در حالت‌های نادر و واقعی
// (ری‌ست/آندو/چند حرکت هم‌زمان بعد از قطعی/بارگذاری اول) به رندر کامل
// برمی‌گردد.
function syncHistory(newMoves){
  newMoves = newMoves || [];
  var oldLen = state.moveList.length;
  if(newMoves.length === oldLen){
    state.moveList = newMoves;
    return;
  }
  if(newMoves.length === oldLen + 1 && state.historyRenderedCount === oldLen){
    state.moveList = newMoves;
    appendHistoryMove(newMoves[newMoves.length-1]);
    return;
  }
  state.moveList = newMoves;
  renderHistory();
}

function updateTurnBanner(){
  var banner = $("turn-banner");
  if(state.status !== "active"){ banner.textContent = "بازی پایان یافت"; banner.className = "turn-banner"; return; }
  if(state.isSpectator){
    banner.textContent = chess.turn() === "w" ? "نوبت سفید" : "نوبت سیاه";
    banner.className = "turn-banner";
  } else {
    var mine = myTurn();
    banner.textContent = mine ? "نوبت شماست" : "در انتظار حریف...";
    banner.className = "turn-banner " + (mine ? "mine" : "theirs");
  }
  var whiteIsTop = state.myColor === "b";
  $("clock-top").classList.toggle("active", (whiteIsTop && chess.turn()==="w") || (!whiteIsTop && chess.turn()==="b"));
  $("clock-bottom").classList.toggle("active", (!whiteIsTop && chess.turn()==="w") || (whiteIsTop && chess.turn()==="b"));
}

function fmtClock(sec){
  sec = Math.max(0, Math.round(sec));
  var m = Math.floor(sec/60), s = sec%60;
  return (m<10?"0":"")+m+":"+(s<10?"0":"")+s;
}
function updateClocks(){
  var whiteIsTop = state.myColor === "b";
  var topSec = whiteIsTop ? state.whiteTime : state.blackTime;
  var botSec = whiteIsTop ? state.blackTime : state.whiteTime;
  $("clock-top").textContent = fmtClock(topSec);
  $("clock-bottom").textContent = fmtClock(botSec);
  $("clock-top").classList.toggle("low", topSec <= 30 && state.status==="active");
  $("clock-bottom").classList.toggle("low", botSec <= 30 && state.status==="active");
}

function tickClocks(){
  if(state.status !== "active") return;
  if(chess.turn()==="w") state.whiteTime = Math.max(0, state.whiteTime-1);
  else state.blackTime = Math.max(0, state.blackTime-1);
  updateClocks();
}

function checkLocalGameOver(){
  var over = chess.game_over ? chess.game_over() : chess.isGameOver();
  if(over){
    var status = "checkmate";
    var inCheck = chess.in_check ? chess.in_check() : chess.inCheck();
    if(!inCheck) status = "draw";
    apiPost("/api/game_over", { status: status, fen: chess.fen() });
  }
}

// ─── خروجِ خودکار بعد از پایانِ بازی ─────────────────────────────
// قبلاً بعد از پایانِ هر بازی، بازیکن باید دستی وارد مودال می‌شد و «بستن»
// را می‌زد. حالا مودالِ نتیجه چند ثانیه نشان داده می‌شود و بعد مینی‌اپ
// خودش بسته می‌شود (نتیجه در چتِ ربات هم برای بازیکن ارسال شده است).
// اگر کاربر «تحلیل مسابقه» را بزند شمارش لغو می‌شود، و بعد از بستنِ صفحه‌ی
// تحلیل هم مینی‌اپ خودکار بسته می‌شود.
var AUTO_CLOSE_SECONDS = 7;   // ← اگر خواستید سریع‌تر/کندتر باشد فقط همین عدد را عوض کنید
var autoCloseTimer = null;

function closeMiniApp(){
  if(tg && tg.close){ try{ tg.close(); }catch(e){} }
}

function cancelAutoClose(){
  if(autoCloseTimer){ clearInterval(autoCloseTimer); autoCloseTimer = null; }
  var box = $("modal-autoclose");
  if(box) box.classList.add("hidden");
}

function startAutoClose(){
  cancelAutoClose();
  // خارج از تلگرام (مثلاً مرورگر معمولی) tg.close وجود ندارد؛ شمارش بی‌معنی است.
  if(!tg || !tg.close) return;
  var left = AUTO_CLOSE_SECONDS;
  var box = $("modal-autoclose"), txt = $("modal-autoclose-text"), fill = $("modal-autoclose-fill");
  function render(){
    txt.textContent = "خروج خودکار تا " + left + " ثانیه دیگر…";
  }
  render();
  box.classList.remove("hidden");
  // نوار پیشرفت: اول صفر (بدون انیمیشن) و بعد با transition خطی تا انتها پر می‌شود
  fill.style.transition = "none";
  fill.style.width = "0%";
  void fill.offsetWidth;
  fill.style.transition = "width " + AUTO_CLOSE_SECONDS + "s linear";
  fill.style.width = "100%";
  autoCloseTimer = setInterval(function(){
    left--;
    if(left <= 0){
      cancelAutoClose();
      closeMiniApp();
      return;
    }
    render();
  }, 1000);
}

function showGameOver(status, winnerId, whiteEloChange, blackEloChange){
  state.gameOverShown = true;
  clearInterval(state.clockTimer);
  $("draw-modal-overlay").classList.add("hidden");
  // افکتِ سقوطِ شاهِ مات‌شده — قبل از باز شدنِ مودالِ پایانِ بازی، چون
  // بعد از باز شدنِ مودال صفحه دیده نمی‌شود. شاهِ رنگِ «بازنده» (یعنی
  // رنگی که الان نوبتش بوده و دیگر حرکتی نداشته) پیدا و علامت‌گذاری
  // می‌شود. مودال با یک تأخیرِ کوتاه باز می‌شود تا کاربر خودِ لحظه‌ی
  // سقوط را ببیند — دقیقاً همان افکتِ امضادارِ chess.com.
  var mateDelay = 0;
  if(status === "checkmate"){
    var losingColor = chess.turn(); // طرفی که الان نوبتش است و مات شده
    var boardState = chess.board();
    for(var r=0;r<8;r++) for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(p && p.type==="k" && p.color===losingColor){
        var sq = FILES[c] + (8-r);
        var kingSlot = state.pieceEls[sq];
        var kingEl = kingSlot && kingSlot.querySelector(".piece");
        if(kingEl){ kingEl.classList.add("mated-king"); mateDelay = 550; }
      }
    }
  }
  setTimeout(function(){ _showGameOverModal(status, winnerId, whiteEloChange, blackEloChange); }, mateDelay);
}

// ─── متنِ دقیقِ علتِ پایانِ بازی ────────────────────────────────
// این‌جا دقیقاً همان انواعِ status ای که سرور (game_server.py) برمی‌گرداند
// پوشش داده می‌شوند تا کاربر همیشه بداند دقیقاً چرا بازی تمام شده — نه
// فقط «مساوی شد»، بلکه پات بود یا کمبود مهره یا تکرار یا ۷۵ حرکت؛ و برای
// تسلیم/اتمام‌وقت هم دقیقاً اسمِ طرفی که تسلیم شد/وقتش تمام شد.
var DRAW_REASON_TEXT = {
  "draw": "یک بازی خوب و برابر بود.",
  "stalemate": "پات شد — بازیکنِ نوبت‌دار در کیش نبود ولی هیچ حرکتِ مجازی نداشت.",
  "insufficient_material": "مهره‌های باقی‌مانده‌ی روی صفحه برای مات‌کردن کافی نبود.",
  "draw_75moves": "۷۵ حرکت بدون حرکتِ پیاده یا گرفتنِ مهره انجام شد.",
  "draw_repetition": "یک موقعیت روی صفحه سه بار تکرار شد.",
  "draw_agreement": "دو طرف روی تساوی توافق کردند."
};
var DRAW_STATUSES = ["draw","stalemate","insufficient_material","draw_75moves","draw_repetition","draw_agreement"];

function _showGameOverModal(status, winnerId, whiteEloChange, blackEloChange){
  var icon = $("modal-icon"), title = $("modal-title"), sub = $("modal-sub"), eloEl = $("modal-elo");
  var iWon = winnerId && String(winnerId) === String(state.myId);
  var isDraw = DRAW_STATUSES.indexOf(status) >= 0;
  // نامِ طرفِ بازنده (برای تسلیم/اتمامِ‌وقت) — از رویِ winnerId و رنگ‌ها
  // محاسبه می‌شود، نه فقط «شما»/«حریف»، چون بیننده (spectator) اصلاً
  // «شما»یی ندارد و باید اسمِ واقعیِ طرفِ بازنده را ببیند.
  //
  // رفعِ باگ: برای بیننده، state.myId همان آی‌دیِ تلگرامِ خودِ بیننده است
  // (نه یکی از دو بازیکن)، پس مقایسه‌ی «winnerId === state.myId» برای او
  // همیشه نادرست (false) بود و در نتیجه winnerName همیشه روی oppName
  // (=black_name) قفل می‌ماند — مثلاً وقتی سفید (انسان) هوش مصنوعیِ سیاه
  // را می‌برد، به بیننده نشان داده می‌شد «هوش مصنوعی برنده شد»، دقیقاً
  // برعکسِ واقعیت. برای بیننده باید winnerId با state.whiteId مقایسه شود،
  // نه با state.myId؛ چون در حالتِ بیننده myName/oppName از قبل به
  // سفید/سیاه نگاشت شده‌اند (نه به خودِ کاربر).
  var winnerName, loserName;
  if(state.isSpectator){
    var winnerIsWhite = winnerId && String(winnerId) === String(state.whiteId);
    winnerName = winnerId ? (winnerIsWhite ? state.myName : state.oppName) : null;
    loserName = winnerId ? (winnerIsWhite ? state.oppName : state.myName) : null;
  } else {
    winnerName = winnerId ? (String(winnerId) === String(state.myId) ? state.myName : state.oppName) : null;
    loserName = winnerId ? (String(winnerId) === String(state.myId) ? state.oppName : state.myName) : null;
  }

  if(isDraw){
    icon.textContent = "🤝"; title.textContent = "بازی مساوی شد";
    sub.textContent = DRAW_REASON_TEXT[status] || DRAW_REASON_TEXT["draw"];
  } else if(status === "resigned"){
    icon.textContent = iWon ? "🏆" : "🏳️";
    title.textContent = iWon ? "حریف تسلیم شد!" : "شما تسلیم شدید";
    sub.textContent = loserName ? (loserName + " تسلیم شد.") : "";
  } else if(status === "timeout"){
    icon.textContent = iWon ? "🏆" : "⏱";
    title.textContent = iWon ? "بردید! وقت حریف تمام شد" : "زمان شما تمام شد";
    sub.textContent = loserName ? ("زمانِ " + loserName + " به پایان رسید.") : "";
  } else {
    icon.textContent = iWon ? "🏆" : "♚";
    title.textContent = iWon ? "کیش و مات! بردید" : "کیش و مات، باختید";
    sub.textContent = iWon ? "بازی عالی بود!" : "دفعه بعد بهتر می‌شود.";
  }
  if(state.isSpectator){
    if(isDraw){ title.textContent = "بازی مساوی شد"; sub.textContent = DRAW_REASON_TEXT[status] || DRAW_REASON_TEXT["draw"]; }
    else if(status === "resigned"){ title.textContent = "یکی از طرفین تسلیم شد"; sub.textContent = loserName ? (loserName + " تسلیم شد.") : ""; }
    else if(status === "timeout"){ title.textContent = "زمان یکی از طرفین تمام شد"; sub.textContent = loserName ? ("زمانِ " + loserName + " به پایان رسید.") : ""; }
    else { title.textContent = "کیش و مات!"; sub.textContent = winnerName ? (winnerName + " برنده شد.") : "بازی به پایان رسید."; }
    icon.textContent = isDraw ? "🤝" : (status === "resigned" ? "🏳️" : (status === "timeout" ? "⏱" : "♚"));
  }
  eloEl.textContent = "";
  if(!state.isSpectator && (whiteEloChange !== null && whiteEloChange !== undefined)){
    var myChange = state.myColor === "w" ? whiteEloChange : blackEloChange;
    if(myChange !== null && myChange !== undefined){
      var sign = myChange > 0 ? "+" : "";
      eloEl.textContent = "📊 تغییر امتیاز Elo شما: " + sign + myChange;
    }
  }
  $("modal-overlay").classList.remove("hidden");
  startAutoClose();
  if(iWon) launchConfetti();
  // برای بیننده (spectator) نه بردی هست نه باختی — صدای خنثی پایانِ بازی
  if(state.isSpectator){ Sound.draw(); Haptics.warning(); }
  else if(isDraw){ Sound.draw(); Haptics.warning(); }
  else if(iWon){ Sound.win(); Haptics.success(); }
  else { Sound.lose(); Haptics.error(); }
}

function launchConfetti(){
  // رفع باگ ریشه‌ای: قبلاً ذرات با سرعت ثابتِ کم (بدون شتاب) رها می‌شدند
  // و انیمیشن با یک سقف زمانیِ ثابت (۳۲۰۰ میلی‌ثانیه) — صرف‌نظر از این‌که
  // ذرات واقعاً به کجای صفحه رسیده بودند — قطع می‌شد. چون نقطه‌ی شروع
  // بعضی ذرات تا نیمی از ارتفاعِ صفحه بالاتر از بالای صفحه بود و سرعتشان
  // هم کم بود، در بسیاری از اجراها اصلاً وقت نمی‌کردند به پایین صفحه
  // برسند و ناگهان (وسط سقوط) ناپدید می‌شدند.
  // راه‌حل: به ذرات شتاب گرانشی واقعی می‌دهیم (سرعت هر فریم بیشتر می‌شود)
  // و انیمیشن را نه بر اساس یک تایمر ثابت، بلکه تا وقتی که همه‌ی ذرات
  // واقعاً از پایین صفحه خارج شده باشند ادامه می‌دهیم (با یک سقف زمانیِ
  // بالا فقط به‌عنوان محافظ در برابر حلقه‌ی بی‌نهایت). نزدیک پایین صفحه
  // هم به‌آرامی محو می‌شوند تا خروج‌شان چشم‌نواز باشد، نه قطع ناگهانی.
  var canvas = $("confetti");
  canvas.style.display = "block";
  canvas.width = window.innerWidth; canvas.height = window.innerHeight;
  var ctx = canvas.getContext("2d");
  var colors = ["#5b7cfa","#8b6bf0","#3fd68f","#f0b93f","#f0546e"];
  var gravity = 0.16;
  var fadeZoneStart = canvas.height * 0.78;
  var fadeZoneSize = canvas.height * 0.3;
  var parts = [];
  var count = 110;
  for(var i=0;i<count;i++){
    parts.push({
      x: Math.random()*canvas.width,
      y: -20 - Math.random()*160,
      vy: 1.5 + Math.random()*2,
      vx: -2 + Math.random()*4,
      size: 5 + Math.random()*6,
      color: colors[i%colors.length],
      rot: Math.random()*360,
      vr: -9 + Math.random()*18,
      shape: (i % 3 === 0) ? "circle" : "rect",
      opacity: 1
    });
  }
  var start = Date.now();
  var MAX_MS = 6000; // محافظ در برابر اجرای بی‌پایان
  function allSettled(){
    return parts.every(function(p){ return p.y - p.size > canvas.height; });
  }
  function frame(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    var elapsed = Date.now()-start;
    parts.forEach(function(p){
      p.vy += gravity;
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      if(p.y > fadeZoneStart){
        p.opacity = Math.max(0, 1 - (p.y - fadeZoneStart) / fadeZoneSize);
      }
      if(p.opacity <= 0) return;
      ctx.save();
      ctx.globalAlpha = p.opacity;
      ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
      ctx.fillStyle = p.color;
      if(p.shape === "circle"){
        ctx.beginPath();
        ctx.arc(0,0,p.size/2,0,Math.PI*2);
        ctx.fill();
      } else {
        ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.65);
      }
      ctx.restore();
    });
    if(!allSettled() && elapsed < MAX_MS){
      requestAnimationFrame(frame);
    } else {
      canvas.style.display = "none";
      ctx.clearRect(0,0,canvas.width,canvas.height);
    }
  }
  requestAnimationFrame(frame);
}

// ─── Theme ──────────────────────────────────────────────────
// باگ: .theme-opt یه کلاسِ عمومیِ استایلی‌ست که دکمه‌های روشن/خاموشِ
// صدا (#btn-sound-on / #btn-sound-off) هم برای ظاهرِ یکسان از همون
// کلاس استفاده می‌کنن (نگاه کن به index.html، #sound-toggle-list).
// querySelectorAll(".theme-opt") قبلاً همه‌ی این چهارتا دکمه‌ی تم رو
// *و* اون دو دکمه‌ی صدا رو با هم می‌گرفت — یعنی کلیک روی دکمه‌ی صدا
// هم به این لیسنر می‌خورد و applyTheme(undefined) صدا زده می‌شد (چون
// دکمه‌های صدا data-theme ندارن)، و برعکس، عوض‌کردنِ تم با همون حلقه
// active/inactive رو روی دکمه‌های صدا هم ریست می‌کرد (چون
// btn.dataset.theme هم برای دکمه‌های صدا و هم برای name=undefined
// برابر undefined بود، پس شرط === true می‌شد). رفعش: فقط دکمه‌هایی که
// واقعاً data-theme دارن رو انتخاب کن، نه هر چیزی با کلاسِ .theme-opt.
function applyTheme(name){
  document.documentElement.setAttribute("data-theme", name);
  try{ localStorage.setItem("chess_theme", name); }catch(e){}
  document.querySelectorAll(".theme-opt[data-theme]").forEach(function(btn){
    btn.classList.toggle("active", btn.dataset.theme === name);
  });
}
document.querySelectorAll(".theme-opt[data-theme]").forEach(function(btn){
  btn.addEventListener("click", function(){ applyTheme(btn.dataset.theme); });
});
(function initThemeHighlight(){
  var current = document.documentElement.getAttribute("data-theme") || "dark";
  document.querySelectorAll(".theme-opt[data-theme]").forEach(function(btn){
    btn.classList.toggle("active", btn.dataset.theme === current);
  });
})();

// ─── تنظیمِ روشن/خاموشِ صدا ───────────────────────────────────
(function initSoundToggle(){
  var onBtn = $("btn-sound-on"), offBtn = $("btn-sound-off");
  if(!onBtn || !offBtn) return;
  function refresh(){
    var on = Sound.isEnabled();
    onBtn.classList.toggle("active", on);
    offBtn.classList.toggle("active", !on);
  }
  onBtn.addEventListener("click", function(){ Sound.setEnabled(true); refresh(); Haptics.light(); });
  offBtn.addEventListener("click", function(){ Sound.setEnabled(false); refresh(); });
  refresh();
})();

// ─── بنرِ «فلانی در حال تماشاست» برای دو بازیکن ──────────────────
// وقتی یک شخصِ سوم (نه هیچ‌کدام از دو بازیکن) صفحه‌ی بازی را باز
// کرده و در حالِ poll کردنِ /api/state است، سرور او را به‌عنوانِ
// «بیننده‌ی فعال» ثبت می‌کند (به apiGet نگاه کنید که uid/name را هم
// می‌فرستد) و لیستِ اسامیِ بیننده‌های فعال را در state.spectators
// برمی‌گرداند. این تابع همان لیست را برای دو بازیکن (نه برای خودِ
// بیننده) به‌صورتِ یک بنر + آیکون کوچک نشان می‌دهد.
function updateSpectatorsBanner(list){
  var el = $("spectators-banner");
  if(!el) return;
  if(state.isSpectator || !list || !list.length){
    el.classList.add("hidden");
    return;
  }
  var text;
  if(list.length === 1){
    text = list[0] + " در حال تماشای این بازی است";
  } else {
    var shown = list.slice(0, 2).join("، ");
    var extra = list.length - 2;
    text = shown + (extra > 0 ? " و " + extra + " نفر دیگر" : "") + " در حال تماشای این بازی هستند";
  }
  $("spectators-text").textContent = text;
  el.classList.remove("hidden");
}

// ─── Chat ───────────────────────────────────────────────────
function renderChatMessage(m, pending){
  var list = $("chat-list");
  var empty = list.querySelector(".chat-empty");
  if(empty) empty.remove();
  var mine = String(m.sender_id) === String(state.myId);
  var bubble = document.createElement("div");
  bubble.className = "chat-bubble" + (mine ? " mine" : "") + (pending ? " sending" : "");
  var senderSpan = document.createElement("span");
  senderSpan.className = "chat-sender";
  senderSpan.textContent = mine ? "شما" : (m.sender_name || state.oppName);
  var textDiv = document.createElement("div");
  textDiv.textContent = m.text;
  bubble.appendChild(senderSpan);
  bubble.appendChild(textDiv);
  list.appendChild(bubble);
  list.scrollTop = list.scrollHeight;
  return bubble;
}

function pollChat(){
  if(!TOKEN || !SHOW_CHAT) return;
  fetch(API + "/api/chat?token=" + encodeURIComponent(TOKEN) + "&after=" + state.lastChatId)
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.ok || !res.messages || !res.messages.length) return;
      res.messages.forEach(function(m){
        state.lastChatId = Math.max(state.lastChatId, m.id);
        // اگر این پیام خودم است و همین الان لوکال نمایشش داده بودیم،
        // به‌جای رندر تکراری فقط تاییدش می‌کنیم (حباب لوکال محو نمی‌شود،
        // فقط حالت «در حال ارسال» برداشته می‌شود — بدون پرش یا فلیکر).
        if(String(m.sender_id) === String(state.myId) && state.pendingChat.length){
          var idx = state.pendingChat.findIndex(function(p){ return p.text === m.text; });
          if(idx >= 0){
            var pending = state.pendingChat.splice(idx, 1)[0];
            if(pending.el) pending.el.classList.remove("sending");
            return;
          }
        }
        renderChatMessage(m);
        if(String(m.sender_id) !== String(state.myId)){
          Sound.chatReceive(); Haptics.light();
        }
        if(!state.chatOpen && String(m.sender_id) !== String(state.myId)){
          state.chatUnread++;
          updateChatBadge();
        }
      });
    })
    .catch(function(){});
}

function updateChatBadge(){
  var badge = $("chat-badge");
  if(state.chatUnread > 0){
    badge.textContent = state.chatUnread > 9 ? "9+" : String(state.chatUnread);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

function sendChatMessage(){
  if(!SHOW_CHAT) return; // محافظِ اضافی: دکمه‌ی چت مخفی است، ولی اگر جایی صدا زده شد بی‌اثر بماند
  var input = $("chat-input");
  var text = input.value.trim();
  if(!text) return;
  input.value = "";
  // نمایش آنی پیام خودم بدون منتظرماندن برای دور بعدی poll (که تا ۲ ثانیه
  // طول می‌کشید و حس تاخیر/لگ می‌داد). بعد از تایید سرور فقط حالت
  // «در حال ارسال» برداشته می‌شود.
  var bubble = renderChatMessage({ sender_id: state.myId, sender_name: "شما", text: text }, true);
  state.pendingChat.push({ text: text, el: bubble });
  Sound.chatSend(); Haptics.light();
  apiPost("/api/chat", { text: text }).then(function(res){
    if(!res.ok){
      bubble.classList.remove("sending");
      bubble.classList.add("failed");
      if(res.error) input.value = text;
    }
  }).catch(function(){
    bubble.classList.remove("sending");
    bubble.classList.add("failed");
  });
}

$("btn-chat").addEventListener("click", function(){
  state.chatOpen = true;
  state.chatUnread = 0;
  updateChatBadge();
  $("chat-panel").classList.add("open");
  setTimeout(function(){ $("chat-input").focus(); }, 250);
});
$("btn-close-chat").addEventListener("click", function(){
  state.chatOpen = false;
  $("chat-panel").classList.remove("open");
});
$("btn-chat-send").addEventListener("click", sendChatMessage);
$("chat-input").addEventListener("keydown", function(e){
  if(e.key === "Enter"){ e.preventDefault(); sendChatMessage(); }
});
$("btn-theme").addEventListener("click", function(){ $("theme-panel").classList.add("open"); });
$("btn-close-theme").addEventListener("click", function(){ $("theme-panel").classList.remove("open"); });

// ─── Actions ────────────────────────────────────────────────
$("btn-resign").addEventListener("click", function(){
  if(state.status !== "active" || state.isSpectator) return;
  if(!confirm("مطمئنید می‌خواهید تسلیم شوید؟")) return;
  apiPost("/api/resign", {}).then(function(res){
    if(res.ok) applyServerState(res.state, false);
  });
});
$("btn-draw").addEventListener("click", function(){
  if(state.status !== "active" || state.isSpectator || state.drawOfferBy) return;
  apiPost("/api/draw_offer", {}).then(function(res){
    if(tg) tg.HapticFeedback && tg.HapticFeedback.impactOccurred("light");
    if(res.ok) applyServerState(res.state, false);
  });
});
$("btn-history").addEventListener("click", function(){ $("history-panel").classList.add("open"); });
$("btn-close-history").addEventListener("click", function(){ $("history-panel").classList.remove("open"); });
$("modal-close").addEventListener("click", function(){
  cancelAutoClose();
  $("modal-overlay").classList.add("hidden");
  closeMiniApp();
});

// ══════════════════════ تحلیلِ پس از بازی ══════════════════════
// یک نمونه‌ی جداگانه‌ی chess.js فقط برای صفحه‌ی تحلیل، تا هیچ‌وقت با
// آبجکتِ `chess` اصلیِ بازیِ زنده (که بیرون از این صفحه هم استفاده
// می‌شود) تداخل نکند.
var anChess = new Chess();
var AnState = {
  data: null,        // پاسخِ کاملِ /api/analyze
  ply: -1,            // -1 یعنی موقعیتِ شروع (قبل از حرکتِ اول)
  boardEls: {},
  flip: false,
  playing: false,
  playTimer: null,
  loaded: false
};

function anBuildBoard(){
  var board = $("an-board");
  board.innerHTML = "";
  AnState.boardEls = {};
  var flip = AnState.flip;
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var rank = flip ? r : 7-r;
      var file = flip ? 7-c : c;
      var sq = FILES[file] + (rank+1);
      var el = document.createElement("div");
      el.className = "square " + (((r+c)%2===0) ? "light" : "dark");
      el.dataset.square = sq;
      board.appendChild(el);
      AnState.boardEls[sq] = el;
    }
  }
}

function anSquareCenter(sq){
  // مرکزِ خانه در فضای viewBox=0 0 100 100 (هر خانه ۱۲.۵ واحد)، با درنظر
  // گرفتنِ چرخشِ تخته (flip).
  var file = FILES.indexOf(sq[0]);
  var rank = parseInt(sq[1], 10) - 1;
  var col = AnState.flip ? 7 - file : file;
  var row = AnState.flip ? rank : 7 - rank;
  return { x: col*12.5 + 6.25, y: row*12.5 + 6.25 };
}

function anRenderArrow(svgEl, from, to, cls){
  var a = anSquareCenter(from), b = anSquareCenter(to);
  var dx = b.x-a.x, dy = b.y-a.y;
  var len = Math.sqrt(dx*dx+dy*dy) || 1;
  var ux = dx/len, uy = dy/len;
  // کمی کوتاه‌کردنِ نوکِ فلش تا داخلِ خانه‌ی مقصد فرو نرود و سرِ فلش دیده شود
  var endX = b.x - ux*4.2, endY = b.y - uy*4.2;
  var startX = a.x + ux*2, startY = a.y + uy*2;
  var markerId = "an-arrowhead-" + cls;
  var ns = "http://www.w3.org/2000/svg";
  var line = document.createElementNS(ns, "line");
  line.setAttribute("x1", startX); line.setAttribute("y1", startY);
  line.setAttribute("x2", endX); line.setAttribute("y2", endY);
  line.setAttribute("stroke", cls === "an-arrow-best" ? "#f0b93f" : "#5b7cfa");
  line.setAttribute("stroke-width", "2.6");
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("marker-end", "url(#" + markerId + ")");
  line.setAttribute("class", cls);
  svgEl.appendChild(line);
}

function anEnsureArrowMarkers(svgEl){
  if(svgEl.querySelector("defs")) return;
  var ns = "http://www.w3.org/2000/svg";
  var defs = document.createElementNS(ns, "defs");
  [["an-arrow-played","#5b7cfa"], ["an-arrow-best","#f0b93f"]].forEach(function(pair){
    var marker = document.createElementNS(ns, "marker");
    marker.setAttribute("id", "an-arrowhead-" + pair[0]);
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "8"); marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "4.2"); marker.setAttribute("markerHeight", "4.2");
    marker.setAttribute("orient", "auto-start-reverse");
    var path = document.createElementNS(ns, "path");
    path.setAttribute("d", "M0,0 L10,5 L0,10 Z");
    path.setAttribute("fill", pair[1]);
    marker.appendChild(path);
    defs.appendChild(marker);
  });
  svgEl.appendChild(defs);
}

function anRenderPosition(){
  var ply = AnState.ply;
  var plies = AnState.data.plies;
  var fen = ply < 0 ? "start" : plies[ply].fen_after;
  if(fen === "start"){ anChess.reset(); } else { anChess.load(fen); }

  var boardState = anChess.board();
  Object.keys(AnState.boardEls).forEach(function(sq){
    var el = AnState.boardEls[sq];
    el.classList.remove("last-from","last-to","check");
    var existing = el.querySelector(".piece");
    if(existing) existing.remove();
  });
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(!p) continue;
      var sq = FILES[c] + (8-r);
      var host = AnState.boardEls[sq];
      if(!host) continue;
      var span = document.createElement("span");
      span.className = "piece " + (p.color === "w" ? "white-p" : "black-p") + " landed";
      span.textContent = PIECE_GLYPH[p.type];
      host.appendChild(span);
    }
  }

  var svg = $("an-arrows");
  svg.innerHTML = "";
  anEnsureArrowMarkers(svg);

  var badgeIcon = $("an-move-badge-icon"), badgeLabel = $("an-move-badge-label"), desc = $("an-move-desc");

  if(ply < 0){
    badgeIcon.style.removeProperty("--an-badge-color");
    badgeLabel.style.removeProperty("--an-badge-color");
    badgeIcon.textContent = "♟️";
    badgeLabel.textContent = "شروع بازی";
    desc.textContent = "برای مرور بازی، از دکمه‌های پایین استفاده کنید یا روی یکی از حرکت‌ها در نوار زیر بزنید.";
    anUpdateEval(0);
  } else {
    var pd = plies[ply];
    if(AnState.boardEls[pd.from]) AnState.boardEls[pd.from].classList.add("last-from");
    if(AnState.boardEls[pd.to]) AnState.boardEls[pd.to].classList.add("last-to");
    if(pd.gives_check || pd.is_mate){
      var kingColor = anChess.turn(); // طرفی که الان کیش خورده
      var bs = anChess.board();
      for(var rr=0;rr<8;rr++) for(var cc=0;cc<8;cc++){
        var kp = bs[rr][cc];
        if(kp && kp.type === "k" && kp.color === kingColor){
          var ksq = FILES[cc] + (8-rr);
          if(AnState.boardEls[ksq]) AnState.boardEls[ksq].classList.add("check");
        }
      }
    }
    anRenderArrow(svg, pd.from, pd.to, "an-arrow-played");
    if(pd.best_from && pd.best_to){
      anRenderArrow(svg, pd.best_from, pd.best_to, "an-arrow-best");
    }
    badgeIcon.textContent = pd.icon;
    badgeIcon.style.setProperty("--an-badge-color", pd.color);
    badgeLabel.textContent = (pd.side === "w" ? "سفید: " : "سیاه: ") + pd.san + " — " + pd.label;
    badgeLabel.style.setProperty("--an-badge-color", pd.color);
    var extraBest = (!pd.is_mate && pd.best_san && pd.classification !== "best" && pd.classification !== "book")
      ? (" بهتر بود: " + pd.best_san + ".") : "";
    desc.textContent = pd.text + extraBest;
    anUpdateEval(pd.eval_cp, pd.win_pct);
  }

  // re-trigger کردنِ انیمیشن‌های CSS (badgepop/descfade/arrowin) برای هر
  // تغییرِ ply، حتی وقتی همان کلاس از قبل هم روی عنصر بوده.
  [badgeIcon, desc].forEach(function(el){
    el.style.animation = "none"; void el.offsetWidth; el.style.animation = "";
  });

  anUpdateMoveListActive();
}

function anUpdateEval(cp, winPct){
  // اگر win_pct از سرور نیامده بود (موقعیتِ شروع)، خودمان با همان منحنیِ
  // نرمِ سرور (تقریب) حساب می‌کنیم تا نوار ارزیابی همیشه پیوسته باشد.
  var pct = (winPct !== undefined && winPct !== null) ? winPct : (50 + 50*(2/(1+Math.exp(-0.00368*cp))-1));
  pct = Math.max(2, Math.min(98, pct));
  $("an-eval-fill-white").style.height = pct + "%";
  $("an-eval-fill-black").style.height = (100-pct) + "%";
  var pawns = (cp/100);
  var label = (pawns >= 0 ? "+" : "") + pawns.toFixed(1);
  $("an-eval-num").textContent = label;
}

function anRenderMoveList(){
  var wrap = $("an-movelist");
  wrap.innerHTML = "";
  AnState.data.plies.forEach(function(pd, idx){
    var chip = document.createElement("button");
    chip.className = "an-move-chip";
    chip.dataset.ply = idx;
    var num = Math.floor(idx/2)+1;
    var prefix = pd.side === "w" ? (num + ". ") : (num + "... ");
    chip.innerHTML = "<span class='chip-icon'>"+pd.icon+"</span><span>"+prefix+pd.san+"</span>";
    chip.style.setProperty("--an-badge-color", pd.color);
    chip.addEventListener("click", function(){ anGoTo(idx); });
    wrap.appendChild(chip);
  });
}

function anUpdateMoveListActive(){
  var chips = $("an-movelist").querySelectorAll(".an-move-chip");
  chips.forEach(function(chip){
    var active = parseInt(chip.dataset.ply,10) === AnState.ply;
    chip.classList.toggle("active", active);
    if(active) chip.scrollIntoView({ behavior:"smooth", inline:"center", block:"nearest" });
  });
}

function anGoTo(ply){
  var max = AnState.data.plies.length - 1;
  AnState.ply = Math.max(-1, Math.min(max, ply));
  anRenderPosition();
}
function anStopPlay(){
  AnState.playing = false;
  $("an-play").classList.remove("playing");
  $("an-play").textContent = "▶";
  if(AnState.playTimer){ clearInterval(AnState.playTimer); AnState.playTimer = null; }
}
function anTogglePlay(){
  if(AnState.playing){ anStopPlay(); return; }
  var max = AnState.data.plies.length - 1;
  if(AnState.ply >= max) AnState.ply = -1;
  AnState.playing = true;
  $("an-play").classList.add("playing");
  $("an-play").textContent = "⏸";
  AnState.playTimer = setInterval(function(){
    if(AnState.ply >= max){ anStopPlay(); return; }
    anGoTo(AnState.ply+1);
  }, 1400);
}

$("an-first").addEventListener("click", function(){ anStopPlay(); anGoTo(-1); });
$("an-prev").addEventListener("click", function(){ anStopPlay(); anGoTo(AnState.ply-1); });
$("an-next").addEventListener("click", function(){ anStopPlay(); anGoTo(AnState.ply+1); });
$("an-last").addEventListener("click", function(){ anStopPlay(); anGoTo(AnState.data.plies.length-1); });
$("an-play").addEventListener("click", anTogglePlay);
$("an-btn-close").addEventListener("click", function(){
  anStopPlay();
  // بازی تمام شده؛ بعد از دیدنِ تحلیل هم لازم نیست کاربر دوباره دستی ببندد.
  if(tg && tg.close){ closeMiniApp(); return; }
  showScreen("screen-game");
});

function anOpen(){
  cancelAutoClose();
  $("modal-overlay").classList.add("hidden");
  showScreen("screen-analysis");
  $("an-content").classList.add("hidden");
  $("an-error").classList.add("hidden");
  $("an-loading").classList.remove("hidden");

  if(AnState.loaded && AnState.data){
    anShowContent();
    return;
  }

  apiGet("/api/analyze").then(function(res){
    if(!res.ok || !res.analysis || !res.analysis.plies || !res.analysis.plies.length){
      $("an-loading").classList.add("hidden");
      $("an-error-text").textContent = (res && res.error) ? res.error : "این بازی حرکتی برای تحلیل نداشت.";
      $("an-error").classList.remove("hidden");
      return;
    }
    AnState.data = res.analysis;
    AnState.loaded = true;
    anShowContent();
  }).catch(function(){
    $("an-loading").classList.add("hidden");
    $("an-error-text").textContent = "اتصال برقرار نشد. دوباره تلاش کنید.";
    $("an-error").classList.remove("hidden");
  });
}

function anShowContent(){
  AnState.flip = (!state.isSpectator && state.myColor === "b");
  $("an-loading").classList.add("hidden");
  $("an-content").classList.remove("hidden");
  $("an-name-white").textContent = AnState.data.white_name || "سفید";
  $("an-name-black").textContent = AnState.data.black_name || "سیاه";
  $("an-acc-value-white").textContent = AnState.data.white_accuracy + "%";
  $("an-acc-value-black").textContent = AnState.data.black_accuracy + "%";
  anBuildBoard();
  anRenderMoveList();
  AnState.ply = -1;
  anRenderPosition();
}

$("modal-analyze").addEventListener("click", anOpen);

// ─── Init ───────────────────────────────────────────────────
function init(){
  if(!TOKEN){ showError("توکن بازی پیدا نشد. از طریق ربات وارد شوید."); return; }
  apiGet("/api/state").then(function(res){
    if(!res.ok){ showError(res.error || "بازی پیدا نشد یا منقضی شده است."); return; }
    var s = res.state;
    var myId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : s.you_id;
    state.myId = myId;
    var isWhite = String(s.white_id) === String(myId);
    var isBlack = String(s.black_id) === String(myId);
    state.isSpectator = !isWhite && !isBlack;
    // برای تشخیصِ درستِ برنده در پایانِ بازی از دیدِ بیننده لازم است
    // (نگاه کنید به _showGameOverModal).
    state.whiteId = s.white_id;
    state.blackId = s.black_id;

    if(state.isSpectator){
      // شخص سوم (ناظر): تخته همیشه از دید سفید نشان داده می‌شود و امکان
      // حرکت‌دادن یا تسلیم/پیشنهاد تساوی وجود ندارد، ولی چت باز است.
      state.myColor = "w";
      state.myName = s.white_name;
      state.oppName = s.black_name;
      $("action-row").classList.add("hidden");
      $("spectator-note").classList.remove("hidden");
    } else {
      state.myColor = isWhite ? "w" : "b";
      state.myName = state.myColor === "w" ? s.white_name : s.black_name;
      state.oppName = state.myColor === "w" ? s.black_name : s.white_name;
    }
    $("name-top").textContent = state.oppName;
    $("name-bottom").textContent = state.myName;
    var myAvatarUrl = state.myColor === "w" ? s.white_avatar : s.black_avatar;
    var oppAvatarUrl = state.myColor === "w" ? s.black_avatar : s.white_avatar;
    setAvatar($("avatar-top"), state.oppName, oppAvatarUrl);
    setAvatar($("avatar-bottom"), state.myName, myAvatarUrl);
    if(s.fen) chess.load(s.fen);
    state.lastMove = s.last_move || null;
    state.moveList = s.moves || [];
    state.whiteTime = s.white_time; state.blackTime = s.black_time;
    state.status = s.status;
    buildBoard();
    renderPieces(null, null, true); // silent: بارگذاریِ اولیه‌ی صفحه، نه یک حرکتِ واقعی
    renderCaptured();
    renderHistory();
    updateTurnBanner();
    updateClocks();
    updateDrawOfferUI(s);
    updateSpectatorsBanner(s.spectators);
    showScreen("screen-game");
    sizeBoard();
    setTimeout(sizeBoard, 100); // اجرای دوباره بعد از استقرار کامل layout (رفع باگ سایز اشتباه در بار اول)
    // ۱.۵ ثانیه‌ای فقط شبکه‌ی ایمنی است (اگر WebSocket وصل نشد/قطع شد)؛
    // مسیر اصلی و بی‌تاخیرِ کشفِ حرکت حریف، connectLiveSocket پایین‌تر است.
    state.pollTimer = setInterval(pollState, 4000);
    connectLiveSocket();
    state.clockTimer = setInterval(tickClocks, 1000);
    // چت: وقتی از «لیستِ بازی‌ها» با chat=0 وارد شده‌ایم (مرورِ بازیِ
    // تمام‌شده‌ی دیگران)، نه دکمه‌ی چت نشان داده می‌شود و نه پول/تایمرِ
    // چت راه می‌افتد — نه فقط برای پیشوا که SHOW_CHAT=true می‌ماند.
    if(SHOW_CHAT){
      state.chatTimer = setInterval(pollChat, 2000);
      pollChat();
    } else {
      var chatBtn = $("btn-chat");
      if(chatBtn) chatBtn.classList.add("hidden");
    }
    if(s.status !== "active"){ showGameOver(s.status, s.winner_id, s.white_elo_change, s.black_elo_change); }
  }).catch(function(){
    showError("اتصال به سرور برقرار نشد.");
  });
}

init();
})();

/* ============================================================
   کِشِ شیشه‌ای (Liquid Glass press) — افزایشی، کاملاً جدا از IIFEِ
   بالا و بازیِ اصلی؛ فقط روی دکمه‌های شیشه‌ای (icon-btn/action-btn/
   theme-opt/گزینه‌های ترفیع) کار می‌کنه، هیچ ربطی به FLIPِ حرکتِ
   مهره‌ها (renderPieces بالاتر) نداره و به‌هیچ‌وجه بهش دست نمی‌زنه.

   قبلاً فقط با CSS :active یه scaleِ ساده روی فشردن بود («می‌ره
   عقب»)؛ اینجا با pointermove واقعیِ انگشت رو دنبال می‌کنیم (با یه
   rubber-band محدود، نه بی‌نهایت) — دقیقاً همون حسِ «کِش‌آمدنِ خمیر»ی
   که خواسته شده — و موقعِ رهاکردن با یه اسپرینگِ نرم برمی‌گرده سرِ جاش.

   فقط transform (translate+scale) نوشته می‌شه — نه فیلتر، نه بلور، نه
   ری‌فلو/getBoundingClientRect در هر فریم (فقط یه‌بار در لحظه‌ی
   pointerdown خونده می‌شه) — پس روی WebViewِ قدیمیِ اندروید هم ارزونه.
   با event delegation روی document کار می‌کنه، پس دکمه‌های ترفیع که
   دیر/داینامیک ساخته می‌شن (promo-options .piece) هم بدونِ نیاز به
   attach جداگانه پوشش داده می‌شن. */
(function(){
  var SEL = ".icon-btn, .action-btn, .theme-opt, .promo-options .piece";
  var MAX_PULL = 10;       // حداکثر پیکسل کِش‌آمدن (rubber-band)
  var PULL_FACTOR = 0.35;  // نسبتِ دنبال‌کردنِ حرکتِ واقعیِ انگشت

  function clamp(v, max){ return Math.max(-max, Math.min(max, v)); }

  var active = null;       // { el, pointerId, cx, cy }
  var raf = null, pendingEvent = null;

  function apply(dx, dy){
    var px = clamp(dx * PULL_FACTOR, MAX_PULL);
    var py = clamp(dy * PULL_FACTOR, MAX_PULL);
    active.el.style.transform = "translate(" + px + "px," + py + "px) scale(.96)";
  }

  document.addEventListener("pointerdown", function(e){
    if(active) return;
    var el = e.target.closest ? e.target.closest(SEL) : null;
    if(!el) return;
    var r = el.getBoundingClientRect();
    active = { el: el, pointerId: e.pointerId, cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
    if(el.setPointerCapture){ try{ el.setPointerCapture(e.pointerId); }catch(err){} }
    // will-change فقط از لحظه‌ی لمس تا رهاشدن: به مرورگر از قبل می‌گه این
    // المان قراره transform بخوره، پس لایه‌ی GPU را همین اول (نه با تأخیرِ
    // اولین فریمِ واقعیِ تغییر) می‌سازه — روی WebViewِ ضعیف همین یه فریم
    // تأخیر حس "دیر واکنش دادن" دکمه رو می‌ده. بعد از release برداشته
    // می‌شه تا لایه‌های GPU الکی روی حافظه نمونن (۶۴ خونه دستِ‌نخورده).
    el.style.willChange = "transform";
    el.style.transition = "transform .08s linear";
    apply(e.clientX - active.cx, e.clientY - active.cy);
  });

  document.addEventListener("pointermove", function(e){
    if(!active || e.pointerId !== active.pointerId) return;
    pendingEvent = e;
    if(raf) return;
    raf = requestAnimationFrame(function(){
      raf = null;
      if(active && pendingEvent) apply(pendingEvent.clientX - active.cx, pendingEvent.clientY - active.cy);
    });
  });

  function release(e){
    if(!active || e.pointerId !== active.pointerId) return;
    var el = active.el;
    active = null;
    if(raf){ cancelAnimationFrame(raf); raf = null; }
    el.style.transition = "transform .5s cubic-bezier(.18,1.4,.4,1)";
    el.style.transform = "";
    // بعد از پایانِ اسپرینگِ برگشت، will-change برداشته می‌شه (نه فوری)؛
    // برداشتنِ زودتر از پایانِ transition باعث می‌شه مرورگر لایه رو وسطِ
    // خودِ انیمیشنِ برگشت جمع کنه و یه ریزلرزش/جمپ بده.
    setTimeout(function(){ el.style.willChange = ""; }, 520);
  }
  document.addEventListener("pointerup", release);
  document.addEventListener("pointercancel", release);
})();
                                      
