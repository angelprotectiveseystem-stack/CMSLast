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
    draw: function(){ tone(440, 0.14, "sine", 0.15); tone(440, 0.14, "sine", 0.15, 0.16); }
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
  myId: null, oppId: null,
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
  activeAnims: [],
  pendingAnimFrame: null,
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

// ─── Board build ────────────────────────────────────────────
function buildBoard(){
  var board = $("board");
  board.innerHTML = "";
  state.boardEls = {};
  var flip = state.myColor === "b";
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var rank = flip ? r : 7-r;
      var file = flip ? 7-c : c;
      var sq = FILES[file] + (rank+1);
      var el = document.createElement("div");
      el.className = "square " + (((r+c)%2===0) ? "light" : "dark");
      el.dataset.square = sq;
      el.addEventListener("click", function(){ onSquareClick(this.dataset.square); });
      board.appendChild(el);
      state.boardEls[sq] = el;
    }
  }
}

// ─── Piece movement / animation engine (rewritten from scratch) ─────
//
// این پیاده‌سازی قبلی جهت جابه‌جایی را از روی «اندیس ستون/ردیف در DOM»
// حساب می‌کرد (col/row * اندازه‌ی فرضی خانه). چون صفحه dir="rtl" است،
// در CSS Grid محور افقی (ستون‌ها) از راست به چپ چیده می‌شود، ولی
// transform: translateX یک آفست فیزیکی (بدون توجه به direction) است.
// نتیجه: برای هر حرکتی که مولفه‌ی افقی داشت (همه‌ی حرکات به‌جز حرکت
// روی یک ستون ثابت)، مهره در مسیر اشتباه (آینه‌شده) حرکت می‌کرد و فقط
// در فریم پایانی به‌خانه‌ی درست می‌پرید — همان «حرکت برعکس» که گزارش
// شده بود. علاوه بر این، رندر جدیدی که حین یک انیمیشن می‌رسید (مثلاً
// poll که هر ۱.۵ ثانیه بررسی می‌کند) به‌جای اعمال فوری، در صف
// (pendingRender) نگه داشته می‌شد؛ این تاخیر دقیقاً همان «سکته»/جهش
// وسط حرکت بود، و چون paintHighlights در پایان renderPieces دوباره
// اجرا می‌شد، نقطه‌های حرکت (move-dot) هم دوباره ساخته و انیمیشن
// dotpop‌شان از نو پخش می‌شد — همان سکته‌ی «نقطه‌ها بعد از کلیک».
//
// راه‌حل ریشه‌ای (به‌جای رفع مورد به مورد):
// ۱) مسافت جابه‌جایی از روی مختصات واقعی پیکسلی صفحه
//    (getBoundingClientRect) محاسبه می‌شود، نه اندیس ستون/ردیف. این
//    مقدار فیزیکی و مستقل از rtl/ltr، چرخش تخته (flip)، و هر گونه
//    گرد شدن اعشاری در اندازه‌ی خانه‌هاست — پس امکان «برعکس رفتن»
//    اصولاً وجود ندارد.
// ۲) هیچ رندری هرگز به تعویق نمی‌افتد. اگر انیمیشنی در حال اجراست و
//    رندر جدیدی لازم شد، انیمیشن‌های فعلی فوراً (بدون پرش بصری، چون
//    Animation.finish() دقیقاً کی‌فریم پایانی را اعمال می‌کند) به
//    پایان می‌رسند و بلافاصله رندر جدید روی وضعیت واقعی انجام می‌شود.
//    یعنی همیشه حداکثر یک انیمیشن روی هر مهره در جریان است و رندرها
//    هرگز صف نمی‌شوند — سکته‌ی ناشی از تاخیر یا هم‌پوشانی دو انیمیشن
//    از ریشه حذف می‌شود.
function settleActiveAnimations(){
  if(state.pendingAnimFrame){
    cancelAnimationFrame(state.pendingAnimFrame);
    state.pendingAnimFrame = null;
  }
  var anims = state.activeAnims;
  state.activeAnims = [];
  anims.forEach(function(a){
    try{ a.finish(); }catch(e){}
  });
  state.animating = false;
}

function renderPieces(animateFrom, animateTo, silent){
  // هر رندر جدید، هر انیمیشن قبلی را فوراً (بدون پرش) می‌بندد؛ هرگز
  // به تعویق نمی‌افتد — این خودِ تضمینِ نبودِ سکته/هم‌پوشانی است.
  settleActiveAnimations();
  var boardState = chess.board();
  var desired = {};
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(p) desired[FILES[c] + (8-r)] = p;
    }
  }
  var current = {};
  Object.keys(state.boardEls).forEach(function(sq){
    var el = state.boardEls[sq].querySelector(".piece");
    if(el) current[sq] = { type: el.dataset.ptype, color: el.dataset.pcolor, el: el };
  });

  var vacated = [];
  var arrived = [];
  Object.keys(current).forEach(function(sq){
    var c = current[sq], d = desired[sq];
    if(!d || d.type !== c.type || d.color !== c.color){
      vacated.push({ sq: sq, type: c.type, color: c.color, el: c.el });
    }
  });
  Object.keys(desired).forEach(function(sq){
    var d = desired[sq], c = current[sq];
    if(!c || c.type !== d.type || c.color !== d.color){
      arrived.push({ sq: sq, type: d.type, color: d.color });
    }
  });

  if(!vacated.length && !arrived.length){ paintHighlights(); return; }

  // موقعیت واقعی پیکسلی (getBoundingClientRect) هر مهره‌ی جابه‌جاشونده
  // را قبل از هر تغییری در DOM ثبت می‌کنیم — این مقدار فیزیکی صفحه
  // است، مستقل از rtl/ltr و چرخش تخته.
  vacated.forEach(function(v){ v.rect = v.el.getBoundingClientRect(); });

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
      if(a0) moves.push({ el: v0.el, toSq: a0.sq, toType: a0.type, fromRect: v0.rect });
      else vacated.push(v0); // مقصد تغییر نکرده؛ احتمالاً همگام‌سازی عجیب — بگذار به مرحله‌ی بعد برود
    }
  }
  // ۲) بقیه‌ی مهره‌های جابه‌جا‌شده بر اساس نوع+رنگ یکسان جفت می‌شوند
  // (مثل رخ در قلعه، یا چند حرکت که با هم از سرور رسیده‌اند)
  vacated.slice().forEach(function(v){
    var a = takeArrivedByType(v.type, v.color);
    if(a){
      takeVacated(v.sq);
      moves.push({ el: v.el, toSq: a.sq, toType: a.type, fromRect: v.rect });
    }
  });

  // LAST — همان المان مهره را فیزیکی به خانه‌ی مقصد منتقل می‌کنیم
  var didPromote = false;
  moves.forEach(function(m){
    state.boardEls[m.toSq].appendChild(m.el);
    if(m.el.dataset.ptype !== m.toType){ // ترفیع: نوع مهره عوض شده
      m.el.textContent = PIECE_GLYPH[m.toType];
      m.el.dataset.ptype = m.toType;
      didPromote = true;
    }
  });

  // باقی‌مانده‌ی vacated یعنی واقعاً «گرفته‌شده‌اند» — فقط این‌ها محو/کوچک می‌شوند
  var didCapture = vacated.length > 0;
  vacated.forEach(function(v){
    v.el.classList.add("captured-anim");
    (function(elToRemove){
      setTimeout(function(){ if(elToRemove.parentNode) elToRemove.remove(); }, 200);
    })(v.el);
  });
  // قلعه: دو مهره با هم جابه‌جا شدند (شاه + رخ) بدون گرفته‌شدنِ هیچ‌کدام
  var didCastle = !didCapture && moves.length === 2;
  // باقی‌مانده‌ی arrived یعنی مهره‌ی کاملاً تازه (بار اول لود صفحه، یا
  // ترفیعی که جفتش پیدا نشد) — با یک پاپ کوچک ظاهر می‌شود
  arrived.forEach(function(a){
    var span = document.createElement("div");
    span.className = "piece " + (a.color==="w" ? "white-p" : "black-p");
    span.textContent = PIECE_GLYPH[a.type];
    span.dataset.ptype = a.type;
    span.dataset.pcolor = a.color;
    span.classList.add("landed");
    state.boardEls[a.sq].appendChild(span);
  });

  // PLAY — مسافت جابه‌جایی از روی مختصات واقعیِ پیکسلی صفحه محاسبه
  // می‌شود (rect مبدا که پیش از جابه‌جایی گرفتیم، در برابر rect مقصد
  // که همین الان بعد از appendChild گرفته می‌شود). این عدد فیزیکی است
  // و به rtl/ltr، چرخش تخته، یا گرد شدن اعشاری اندازه‌ی خانه‌ها کاری
  // ندارد؛ پس مهره همیشه دقیقاً در مسیر واقعی‌اش حرکت می‌کند.
  //
  // رویکرد عوض شد: به‌جای Web Animations API (`el.animate()` با چند
  // keyframe و یک offset میانی)، از یک CSS transition ساده‌ی دو-نقطه‌ای
  // روی transform استفاده می‌شود. دلیل تعویض: `el.animate()` با
  // keyframeهای دارای offset (مثل ۰٫۸۲ این‌جا) روی برخی WebViewهای
  // اندرویدِ قدیمی/داخل تلگرام به‌صورت غیریکنواخت تفسیر می‌شود — بعضی
  // نسخه‌ها بین دو keyframe درون‌یابی نرم انجام نمی‌دهند و رسماً می‌پرند،
  // که خودش یک نوع «سکته» است که نمی‌شود از کدِ سطح بالا حدس زد چون در
  // مرورگرهای دسکتاپ دیده نمی‌شود. CSS transition روی transform قدیمی‌ترین
  // و پایدارترین قابلیتِ انیمیشنِ شتاب‌گرفته‌با-GPU در وب است و در همه‌ی
  // نسخه‌های WebView (از اندروید ۴ به بعد) یکسان و بدون‌جهش کار می‌کند.
  //
  // ترفند دو-مرحله‌ای برای اجرای درست: ۱) مهره فوراً (بدون transition) به
  // موقعیت قبلی‌اش منتقل می‌شود (یعنی چون appendChild همین الان آن را در
  // خانه‌ی مقصد نشانده، این‌جا transform معکوسِ فاصله اعمال می‌شود تا
  // دوباره سرِ جای قبلی‌اش دیده شود) ۲) با یک reflow اجباری (خواندن
  // offsetWidth) این حالت را «قفل» می‌کنیم تا مرورگر مطمئن این را یک
  // فریم واقعی رسم‌شده بداند، نه چیزی که می‌شود با نوشتنِ بعدی ادغامش کرد
  // ۳) بعد transition را وصل و مقصد را روی صفر می‌گذاریم — همین یک
  // تغییر است که مرورگر بین دو مقدار transform به‌طور تضمینی و یکنواخت
  // میان‌یابی می‌کند.
  if(moves.length){
    state.animating = true;
    moves.forEach(function(m){ m.el.classList.add("moving"); });
    state.pendingAnimFrame = requestAnimationFrame(function(){
      state.pendingAnimFrame = null;
      moves.forEach(function(m){
        var toRect = state.boardEls[m.toSq].getBoundingClientRect();
        if(!m.fromRect){ m.el.classList.remove("moving"); return; }
        var dx = m.fromRect.left - toRect.left;
        var dy = m.fromRect.top - toRect.top;
        if(!dx && !dy){ m.el.classList.remove("moving"); return; }
        var dist = Math.sqrt(dx*dx + dy*dy);
        // مدت‌زمان بلندتر و ثابت‌تر، شبیه chess.com: حرکت یک‌خانه‌ای هم
        // باید به‌قدر کافی طول بکشد که چشم آن را «سُر خوردن» ببیند.
        var dur = Math.max(220, Math.min(420, 180 + dist * 0.35));
        var el = m.el;
        el.style.transition = "none";
        el.style.transform = "translate(" + dx + "px," + dy + "px) scale(1.05)";
        void el.offsetWidth; // reflow اجباری — نقطه‌ی شروع را قفل می‌کند
        // یک requestAnimationFrame دوم و تودرتو لازم است: reflow فقط
        // layout را محاسبه می‌کند، نه اینکه تضمین کند مرورگر واقعاً یک
        // فریم را رسم (paint) کرده باشد. اگر وصل‌کردن transition و
        // نوشتنِ مقصد در همان تسکِ همزمانِ جاوااسکریپت انجام شود، روی
        // بعضی WebViewها (به‌خصوص اندرویدِ داخلِ تلگرام) هر دو تغییر با
        // هم در یک فریم ادغام می‌شوند و مرورگر مستقیم به state نهایی
        // می‌پرد. با این rAF دوم، موقعیتِ شروع تضمین می‌شود که واقعاً
        // رسم شده باشد، و فقط بعد از آن transition وصل و مقصد نوشته شود.
        requestAnimationFrame(function(){
          el.style.transition = "transform " + dur + "ms cubic-bezier(.19,1,.22,1)";
          el.style.transform = "translate(0px,0px) scale(1)";
        });

        var entry = { el: el, done: false };
        var finish = function(){
          if(entry.done) return;
          entry.done = true;
          el.removeEventListener("transitionend", onEnd);
          clearTimeout(fallbackTimer);
          el.style.transition = "";
          el.style.transform = "";
          el.classList.remove("moving");
          var i = state.activeAnims.indexOf(entry);
          if(i >= 0) state.activeAnims.splice(i, 1);
          if(!state.activeAnims.length){
            state.animating = false;
            sizeBoard(); // اگر در این فاصله چیزی واقعاً عوض شده، حالا اعمالش کن
          }
        };
        function onEnd(ev){ if(ev.target === el && ev.propertyName === "transform") finish(); }
        el.addEventListener("transitionend", onEnd);
        // محافظ: اگر به هر دلیلی (مثل قطع‌شدن transition وسط راه توسط
        // یک رندر جدید که خودش settleActiveAnimations را صدا می‌زند)
        // transitionend هرگز نرسد، حداکثر کمی بعد از پایانِ مدتِ مورد
        // انتظار خودمان finish را صدا می‌زنیم تا مهره هیچ‌وقت گیر نکند.
        var fallbackTimer = setTimeout(finish, dur + 150); // ۵۰ms اضافه برای تأخیرِ rAF دوم
        entry.finish = finish;
        state.activeAnims.push(entry);
      });
      if(!state.activeAnims.length) state.animating = false;
    });
  }

  paintHighlights();

  // افکت صوتی/هپتیکِ خودِ حرکت — بر اساس دیفِ واقعی صفحه تعیین می‌شود
  // (didCapture/didCastle/didPromote)، نه بر اساس san یا flags، چون این
  // دیف هم برای حرکات محلی و هم حرکات هم‌گام‌سازی‌شده از سرور یکسان و
  // قابل‌اعتماد است. کیش با اولویتِ بالاتر از حرکت/گرفتنِ ساده پخش
  // می‌شود چون معنادارتر است.
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
  if(state.lastMove){
    if(state.boardEls[state.lastMove.from]) state.boardEls[state.lastMove.from].classList.add("last-from");
    if(state.boardEls[state.lastMove.to]) state.boardEls[state.lastMove.to].classList.add("last-to");
  }
  if(state.selected){
    state.boardEls[state.selected].classList.add("selected");
    state.legalTargets.forEach(function(m){
      var el = state.boardEls[m.to];
      if(!el) return;
      var dot = document.createElement("div");
      dot.className = "move-dot" + (m.captured || m.flags.indexOf("e")>=0 ? " capture" : "");
      el.appendChild(dot);
    });
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
  return fetch(API + path + "?token=" + encodeURIComponent(TOKEN)).then(function(r){ return r.json(); });
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
  $("captured-top").textContent = (topIsWhite ? captured.w : captured.b).map(function(t){ return PIECE_GLYPH[t]; }).join("");
  $("captured-bottom").textContent = (topIsWhite ? captured.b : captured.w).map(function(t){ return PIECE_GLYPH[t]; }).join("");
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

function showGameOver(status, winnerId, whiteEloChange, blackEloChange){
  state.gameOverShown = true;
  clearInterval(state.clockTimer);
  $("draw-modal-overlay").classList.add("hidden");
  var icon = $("modal-icon"), title = $("modal-title"), sub = $("modal-sub"), eloEl = $("modal-elo");
  var iWon = winnerId && String(winnerId) === String(state.myId);
  var isDraw = status === "draw" || status === "stalemate";
  if(isDraw){
    icon.textContent = "🤝"; title.textContent = "بازی مساوی شد";
    sub.textContent = "یک بازی خوب و برابر بود.";
  } else if(status === "resigned"){
    icon.textContent = iWon ? "🏆" : "🏳️";
    title.textContent = iWon ? "حریف تسلیم شد!" : "شما تسلیم شدید";
    sub.textContent = iWon ? "بازی به نفع شما تمام شد." : "";
  } else if(status === "timeout"){
    icon.textContent = iWon ? "🏆" : "⏱";
    title.textContent = iWon ? "بردید! وقت حریف تمام شد" : "زمان شما تمام شد";
    sub.textContent = "";
  } else {
    icon.textContent = iWon ? "🏆" : "♚";
    title.textContent = iWon ? "کیش و مات! بردید" : "کیش و مات، باختید";
    sub.textContent = iWon ? "بازی عالی بود!" : "دفعه بعد بهتر می‌شود.";
  }
  if(state.isSpectator){
    if(isDraw){ title.textContent = "بازی مساوی شد"; sub.textContent = "یک بازی خوب و برابر بود."; }
    else if(status === "resigned"){ title.textContent = "یکی از طرفین تسلیم شد"; sub.textContent = ""; }
    else if(status === "timeout"){ title.textContent = "زمان یکی از طرفین تمام شد"; sub.textContent = ""; }
    else { title.textContent = "کیش و مات!"; sub.textContent = "بازی به پایان رسید."; }
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
function applyTheme(name){
  document.documentElement.setAttribute("data-theme", name);
  try{ localStorage.setItem("chess_theme", name); }catch(e){}
  document.querySelectorAll(".theme-opt").forEach(function(btn){
    btn.classList.toggle("active", btn.dataset.theme === name);
  });
}
document.querySelectorAll(".theme-opt").forEach(function(btn){
  btn.addEventListener("click", function(){ applyTheme(btn.dataset.theme); });
});
(function initThemeHighlight(){
  var current = document.documentElement.getAttribute("data-theme") || "dark";
  document.querySelectorAll(".theme-opt").forEach(function(btn){
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
  if(!TOKEN) return;
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
  var input = $("chat-input");
  var text = input.value.trim();
  if(!text) return;
  input.value = "";
  // نمایش آنی پیام خودم بدون منتظرماندن برای دور بعدی poll (که تا ۲ ثانیه
  // طول می‌کشید و حس تاخیر/لگ می‌داد). بعد از تایید سرور فقط حالت
  // «در حال ارسال» برداشته می‌شود.
  var bubble = renderChatMessage({ sender_id: state.myId, sender_name: "شما", text: text }, true);
  state.pendingChat.push({ text: text, el: bubble });
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
  $("modal-overlay").classList.add("hidden");
  if(tg) tg.close();
});

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
    $("avatar-top").textContent = (state.oppName||"?").slice(0,1);
    $("avatar-bottom").textContent = (state.myName||"?").slice(0,1);
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
    showScreen("screen-game");
    sizeBoard();
    setTimeout(sizeBoard, 100); // اجرای دوباره بعد از استقرار کامل layout (رفع باگ سایز اشتباه در بار اول)
    // ۱.۵ ثانیه‌ای فقط شبکه‌ی ایمنی است (اگر WebSocket وصل نشد/قطع شد)؛
    // مسیر اصلی و بی‌تاخیرِ کشفِ حرکت حریف، connectLiveSocket پایین‌تر است.
    state.pollTimer = setInterval(pollState, 4000);
    connectLiveSocket();
    state.clockTimer = setInterval(tickClocks, 1000);
    state.chatTimer = setInterval(pollChat, 2000);
    pollChat();
    if(s.status !== "active"){ showGameOver(s.status, s.winner_id, s.white_elo_change, s.black_elo_change); }
  }).catch(function(){
    showError("اتصال به سرور برقرار نشد.");
  });
}

init();
})();
                                      
