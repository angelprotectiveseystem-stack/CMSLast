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
  animating: false
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

function squareToRowCol(sq){
  // مختصات شبکه‌ی خانه (row, col) را از روی موقعیت واقعی‌اش در DOM
  // برمی‌گرداند — این با توجه به state.boardEls (که با رعایت چرخش
  // صفحه/flip ساخته شده) محاسبه می‌شود، پس چه بازیکن سفید باشد چه
  // سیاه، جهت حرکت درست است.
  var el = state.boardEls[sq];
  if(!el || !el.parentNode) return null;
  var idx = Array.prototype.indexOf.call(el.parentNode.children, el);
  return { row: Math.floor(idx / 8), col: idx % 8 };
}

function renderPieces(animateFrom, animateTo){
  // پیاده‌سازی FLIP سبک chess.com: مهره‌ی واقعی در DOM به خانه‌ی
  // مقصدش منتقل می‌شود و بلافاصله با transform به مکان قبلی‌اش
  // برگردانده می‌شود (بدون هیچ پرش/تغییر سایز)، سپس با یک انیمیشن
  // خطی و کوتاه (فقط translate، بدون scale یا lift) به سمت صفر
  // حرکت می‌کند — دقیقاً حسی که در chess.com هست: یک سُر خوردن صاف
  // و سریع، بدون تاب خوردن یا بالا/پایین پریدن.
  //
  // فاصله بر اساس تعداد خانه‌ها (row/col delta) محاسبه می‌شود، نه
  // pixel واقعی از getBoundingClientRect. این باعث می‌شود انیمیشن
  // کاملاً مستقل از نوسانات لحظه‌ای layout (که منبع اصلی ناهمواری
  // بود) و همیشه دقیقاً به اندازه‌ی N خانه جابه‌جا شود.
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

  // موقعیت شبکه‌ای (row/col) هر مهره‌ی جابه‌جاشونده را قبل از هر
  // تغییری در DOM ثبت می‌کنیم.
  vacated.forEach(function(v){ v.grid = squareToRowCol(v.sq); });

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
      if(a0) moves.push({ el: v0.el, toSq: a0.sq, toType: a0.type, fromGrid: v0.grid });
      else vacated.push(v0); // مقصد تغییر نکرده؛ احتمالاً همگام‌سازی عجیب — بگذار به مرحله‌ی بعد برود
    }
  }
  // ۲) بقیه‌ی مهره‌های جابه‌جا‌شده بر اساس نوع+رنگ یکسان جفت می‌شوند
  // (مثل رخ در قلعه، یا چند حرکت که با هم از سرور رسیده‌اند)
  vacated.slice().forEach(function(v){
    var a = takeArrivedByType(v.type, v.color);
    if(a){
      takeVacated(v.sq);
      moves.push({ el: v.el, toSq: a.sq, toType: a.type, fromGrid: v.grid });
    }
  });

  // LAST — همان المان مهره را فیزیکی به خانه‌ی مقصد منتقل می‌کنیم
  moves.forEach(function(m){
    var toGrid = squareToRowCol(m.toSq);
    m.toGrid = toGrid;
    state.boardEls[m.toSq].appendChild(m.el);
    if(m.el.dataset.ptype !== m.toType){ // ترفیع: نوع مهره عوض شده
      m.el.textContent = PIECE_GLYPH[m.toType];
      m.el.dataset.ptype = m.toType;
    }
  });

  // باقی‌مانده‌ی vacated یعنی واقعاً «گرفته‌شده‌اند» — فقط این‌ها محو/کوچک می‌شوند
  vacated.forEach(function(v){
    v.el.classList.add("captured-anim");
    (function(elToRemove){
      setTimeout(function(){ if(elToRemove.parentNode) elToRemove.remove(); }, 200);
    })(v.el);
  });
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

  // PLAY — بر اساس اختلاف row/col (نه pixel واقعی) مهره را به‌اندازه‌ی
  // دقیق N خانه جابه‌جا می‌کنیم. چون سایز هر خانه از روی خودِ board-size
  // متغیر CSS محاسبه می‌شود، این کار مستقل از هرگونه نوسان لحظه‌ای در
  // layout بیرونی است.
  //
  // از Web Animations API (element.animate) استفاده می‌کنیم، نه
  // دستکاری دستی style.transform/transition. دلیل: با دستکاری دستی
  // (ست‌کردن transform به مقدار جهش‌خورده، فورس‌کردن reflow، بعد ست
  // کردن transition، بعد در rAF برگرداندن به صفر) بین نوشتن استایل‌ها
  // race condition پیش می‌آمد — روی برخی وب‌ویوها (به‌خصوص WebView
  // تلگرام) مرورگر فریم شروع را می‌بلعد و مستقیم می‌پرد به مقدار نهایی،
  // پس هیچ انیمیشنی دیده نمی‌شد. Web Animations API این مشکل را ندارد
  // چون هر دو کی‌فریم (شروع و پایان) در یک فراخوانی به مرورگر داده
  // می‌شود و خود مرورگر تضمین می‌کند اولین فریم واقعاً رندر شود.
  if(moves.length){
    state.animating = true;
    var pendingAnims = moves.length;
    var animDone = function(){
      pendingAnims--;
      if(pendingAnims <= 0){
        state.animating = false;
        sizeBoard(); // اگر در این فاصله چیزی واقعاً عوض شده، حالا اعمالش کن
      }
    };
    var boardEl = $("board");
    var squarePx = boardEl.clientWidth / 8;
    moves.forEach(function(m){
      if(!m.fromGrid || !m.toGrid){ animDone(); return; }
      var dCol = m.fromGrid.col - m.toGrid.col;
      var dRow = m.fromGrid.row - m.toGrid.row;
      if(!dCol && !dRow){ animDone(); return; }
      var dx = dCol * squarePx;
      var dy = dRow * squarePx;
      var dist = Math.sqrt(dx*dx + dy*dy);
      // مدت‌زمان بلندتر و ثابت‌تر، شبیه chess.com: حرکت یک‌خانه‌ای هم
      // باید به‌قدر کافی طول بکشد که چشم آن را «سُر خوردن» ببیند، نه
      // یک ومضه‌ی چندفریمی که روی موبایل/WebView به‌نظر لگ می‌رسد.
      // فاصله‌های بلندتر (مثل حرکت وزیر از یک سر تخته به سر دیگر) کمی
      // بیشتر طول می‌کشند تا سرعت حسی طبیعی بماند.
      var dur = Math.max(260, Math.min(420, 220 + dist * 0.35));
      m.el.style.zIndex = "5";
      if(typeof m.el.animate !== "function"){
        // مرورگر/وب‌ویوی خیلی قدیمی که Web Animations API ندارد —
        // بدون انیمیشن مستقیم جابه‌جا می‌شود (بهتر از throw خطا).
        m.el.style.zIndex = "";
        animDone();
        return;
      }
      var anim = m.el.animate(
        [
          { transform: "translate(" + dx + "px," + dy + "px)" },
          { transform: "translate(0px,0px)" }
        ],
        // easing از نوع ease-out ملایم: شروع کمی سریع‌تر، پایان نرم و
        // بدون توقف ناگهانی — هیچ jank بصری در وسط راه ایجاد نمی‌کند
        // چون خودِ مرورگر (نه جاوااسکریپت) هر فریم را محاسبه می‌کند.
        { duration: dur, easing: "cubic-bezier(.22,.61,.36,1)", fill: "forwards" }
      );
      var settled = false;
      // finish() موقعیت را دقیقاً روی کی‌فریم پایانی قفل می‌کند (بدون
      // پرش) و سپس style موقت را پاک می‌کنیم. از cancel() اینجا استفاده
      // نمی‌کنیم چون cancel وسط انیمیشن باعث پرش آنی به موقعیت نهایی
      // می‌شد — دقیقاً همان «سکته» که در تست دیده شد. finish فقط وقتی
      // معنی دارد که انیمیشن واقعاً به پایان طبیعی‌اش رسیده باشد.
      var settle = function(){
        if(settled) return;
        settled = true;
        try{ anim.finish(); }catch(e){}
        // بعد از finish، effect را از استک انیمیشن پاک می‌کنیم تا در
        // رندرهای بعدی (مثلاً اگر همین مهره دوباره حرکت کند) هیچ اثر
        // باقی‌مانده‌ای تداخل ایجاد نکند. چون finish() از قبل مقدار
        // نهایی (0,0) را قفل کرده، این cancel هیچ پرش بصری‌ای ایجاد
        // نمی‌کند.
        try{ anim.cancel(); }catch(e){}
        m.el.style.zIndex = "";
        animDone();
      };
      anim.onfinish = settle;
      anim.oncancel = function(){
        if(settled) return;
        settled = true;
        m.el.style.zIndex = "";
        animDone();
      };
      // شبکه‌ی ایمنی: اگر به هر دلیلی onfinish هرگز فایر نشود (مثلاً
      // تب در پس‌زمینه رفت)، با تأخیر قابل‌توجه (نه نزدیک به dur واقعی)
      // یک‌بار settle را صدا می‌زنیم تا هرگز گیر نکنیم، بدون این‌که با
      // پایان طبیعی انیمیشن رقابت کند.
      setTimeout(settle, dur + 400);
    });
  }

  paintHighlights();
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
  if(tg) tg.HapticFeedback && tg.HapticFeedback.impactOccurred("light");
  state.selected = null;
  state.legalTargets = [];
  state.lastMove = { from: from, to: to };
  state.moveList = state.moveList.concat([move.san]);
  renderPieces(from, to);
  renderCaptured();
  renderHistory();
  updateTurnBanner();
  sendMove(move);
  checkLocalGameOver();
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
        if(state.moveList.length) state.moveList = state.moveList.slice(0, -1);
        state.selected = null;
        state.legalTargets = [];
        state.lastMove = null;
        renderPieces();
        renderCaptured();
        renderHistory();
        updateTurnBanner();
        setConnStatus(false);
        if(res.error) alert(res.error);
      } else {
        setConnStatus(true);
        applyServerState(res.state, false);
        if(res.state.moves){ state.moveList = res.state.moves; renderHistory(); }
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
    if(s.moves) state.moveList = s.moves;
    renderPieces(state.lastMove && state.lastMove.from, state.lastMove && state.lastMove.to);
    renderCaptured();
    renderHistory();
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
    return;
  }
  for(var i=0;i<moves.length;i+=2){
    var row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = '<span class="history-num">' + (i/2+1) + '.</span><span class="history-move">' + moves[i] + '</span><span class="history-move">' + (moves[i+1]||"") + '</span>';
    list.appendChild(row);
  }
  list.scrollTop = list.scrollHeight;
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
  if(tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(iWon ? "success" : (isDraw ? "warning" : "error"));
}

function launchConfetti(){
  var canvas = $("confetti");
  canvas.style.display = "block";
  canvas.width = window.innerWidth; canvas.height = window.innerHeight;
  var ctx = canvas.getContext("2d");
  var colors = ["#5b7cfa","#8b6bf0","#3fd68f","#f0b93f","#f0546e"];
  var parts = [];
  for(var i=0;i<80;i++){
    parts.push({
      x: Math.random()*canvas.width, y: -20 - Math.random()*canvas.height*0.5,
      vy: 2+Math.random()*3, vx: -1.5+Math.random()*3,
      size: 4+Math.random()*5, color: colors[i%colors.length],
      rot: Math.random()*360, vr: -6+Math.random()*12
    });
  }
  var start = Date.now();
  function frame(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    var elapsed = Date.now()-start;
    parts.forEach(function(p){
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size);
      ctx.restore();
    });
    if(elapsed < 3200) requestAnimationFrame(frame);
    else { canvas.style.display = "none"; ctx.clearRect(0,0,canvas.width,canvas.height); }
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
    renderPieces();
    renderCaptured();
    renderHistory();
    updateTurnBanner();
    updateClocks();
    updateDrawOfferUI(s);
    showScreen("screen-game");
    sizeBoard();
    setTimeout(sizeBoard, 100); // اجرای دوباره بعد از استقرار کامل layout (رفع باگ سایز اشتباه در بار اول)
    state.pollTimer = setInterval(pollState, 1500);
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
                                      
