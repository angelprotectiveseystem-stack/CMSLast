(function(){
"use strict";

var tg = window.Telegram ? window.Telegram.WebApp : null;
if(tg){ tg.ready(); tg.expand(); try{ tg.disableVerticalSwipes(); }catch(e){} }

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
  boardEls: {}
};

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

function renderPieces(animateFrom, animateTo){
  var boardState = chess.board();
  var flip = state.myColor === "b";
  Object.keys(state.boardEls).forEach(function(sq){
    var el = state.boardEls[sq];
    var existing = el.querySelector(".piece");
    if(existing) existing.remove();
  });
  for(var r=0;r<8;r++){
    for(var c=0;c<8;c++){
      var p = boardState[r][c];
      if(!p) continue;
      var sq = FILES[c] + (8-r);
      var el = state.boardEls[sq];
      if(!el) continue;
      var span = document.createElement("div");
      span.className = "piece " + (p.color==="w" ? "white-p" : "black-p");
      span.textContent = PIECE_GLYPH[p.type];
      if(sq === animateTo) span.classList.add("landed");
      el.appendChild(span);
    }
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
  return state.status === "active" && chess.turn() === state.myColor;
}

function onSquareClick(sq){
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
  state.selected = null;
  state.legalTargets = [];
  state.lastMove = { from: from, to: to };
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
        setConnStatus(false);
      } else {
        setConnStatus(true);
        applyServerState(res.state, false);
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
    if(!res.ok){ setConnStatus(false); return; }
    setConnStatus(true);
    applyServerState(res.state, true);
  }).catch(function(){ setConnStatus(false); });
}

function applyServerState(s, fromPoll){
  if(!s) return;
  var incomingFen = s.fen;
  if(incomingFen && incomingFen !== chess.fen()){
    var prevLast = state.lastMove;
    chess.load(incomingFen);
    state.lastMove = s.last_move || prevLast;
    renderPieces(state.lastMove && state.lastMove.from, state.lastMove && state.lastMove.to);
    renderCaptured();
    renderHistory();
  }
  state.whiteTime = s.white_time;
  state.blackTime = s.black_time;
  state.turn = chess.turn();
  updateClocks();
  updateTurnBanner();
  if(s.status !== "active" && !state.gameOverShown){
    state.status = s.status;
    showGameOver(s.status, s.winner_id);
  }
}

// ─── Captured pieces / history ──────────────────────────────
function renderCaptured(){
  var history = chess.history({ verbose: true });
  var captured = { w: [], b: [] };
  history.forEach(function(m){
    if(m.captured){
      captured[m.color === "w" ? "b" : "w"].push(m.captured);
    }
  });
  var topIsWhite = state.myColor === "b";
  var order = { p:1,n:3,b:3,r:5,q:9,k:0 };
  captured.w.sort(function(a,b){ return order[a]-order[b]; });
  captured.b.sort(function(a,b){ return order[a]-order[b]; });
  $("captured-top").textContent = (topIsWhite ? captured.w : captured.b).map(function(t){ return PIECE_GLYPH[t]; }).join("");
  $("captured-bottom").textContent = (topIsWhite ? captured.b : captured.w).map(function(t){ return PIECE_GLYPH[t]; }).join("");
}

function renderHistory(){
  var list = $("history-list");
  var history = chess.history();
  list.innerHTML = "";
  for(var i=0;i<history.length;i+=2){
    var row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = '<span class="history-num">' + (i/2+1) + '.</span><span class="history-move">' + history[i] + '</span><span class="history-move">' + (history[i+1]||"") + '</span>';
    list.appendChild(row);
  }
  list.scrollTop = list.scrollHeight;
}

function updateTurnBanner(){
  var banner = $("turn-banner");
  if(state.status !== "active"){ banner.textContent = "بازی پایان یافت"; banner.className = "turn-banner"; return; }
  var mine = myTurn();
  banner.textContent = mine ? "نوبت شماست" : "در انتظار حریف...";
  banner.className = "turn-banner " + (mine ? "mine" : "theirs");
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

function showGameOver(status, winnerId){
  state.gameOverShown = true;
  clearInterval(state.clockTimer);
  var icon = $("modal-icon"), title = $("modal-title"), sub = $("modal-sub");
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

// ─── Actions ────────────────────────────────────────────────
$("btn-resign").addEventListener("click", function(){
  if(state.status !== "active") return;
  if(!confirm("مطمئنید می‌خواهید تسلیم شوید؟")) return;
  apiPost("/api/resign", {}).then(function(res){
    if(res.ok) applyServerState(res.state, false);
  });
});
$("btn-draw").addEventListener("click", function(){
  if(state.status !== "active") return;
  apiPost("/api/draw_offer", {}).then(function(res){
    if(tg) tg.HapticFeedback && tg.HapticFeedback.impactOccurred("light");
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
    state.myColor = String(s.white_id) === String(myId) ? "w" : "b";
    state.myName = state.myColor === "w" ? s.white_name : s.black_name;
    state.oppName = state.myColor === "w" ? s.black_name : s.white_name;
    $("name-top").textContent = state.oppName;
    $("name-bottom").textContent = state.myName;
    $("avatar-top").textContent = (state.oppName||"?").slice(0,1);
    $("avatar-bottom").textContent = (state.myName||"?").slice(0,1);
    if(s.fen) chess.load(s.fen);
    state.lastMove = s.last_move || null;
    state.whiteTime = s.white_time; state.blackTime = s.black_time;
    state.status = s.status;
    buildBoard();
    renderPieces();
    renderCaptured();
    renderHistory();
    updateTurnBanner();
    updateClocks();
    showScreen("screen-game");
    state.pollTimer = setInterval(pollState, 1500);
    state.clockTimer = setInterval(tickClocks, 1000);
    if(s.status !== "active"){ showGameOver(s.status, s.winner_id); }
  }).catch(function(){
    showError("اتصال به سرور برقرار نشد.");
  });
}

init();
})();
                                      
