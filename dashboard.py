#!/usr/bin/env python3
"""MC-STRIKE v3 Dashboard — python3 dashboard.py → http://localhost:8080"""
import sys,os,json,time,threading,argparse
sys.path.insert(0,os.path.dirname(__file__))
from http.server import HTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from engine import Engine,STATS,ping_server,Mode,PROTOCOL_MAP

_engine=None; _engine_thread=None
_srv_status={}; _srv_poller=None; _current_cfg={}

def _ts_ticker():
    while True: STATS.tick(); time.sleep(1)
threading.Thread(target=_ts_ticker,daemon=True).start()

def _start_poller(host,port,proto):
    global _srv_poller,_srv_status
    def poll():
        while True:
            r=ping_server(host,port,proto); _srv_status.update(r)
            _srv_status["ts"]=time.time(); time.sleep(4)
    if _srv_poller and _srv_poller.is_alive(): return
    _srv_poller=threading.Thread(target=poll,daemon=True)
    _srv_poller.start()

HTML = open(__file__).read()  # placeholder - see below

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _j(self,d,c=200):
        b=json.dumps(d,default=str).encode()
        self.send_response(c); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(b)); self.end_headers(); self.wfile.write(b)
    def _h(self,b):
        self.send_response(200); self.send_header("Content-Type","text/html;charset=utf-8")
        self.send_header("Content-Length",len(b)); self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
    def do_GET(self):
        p=urlparse(self.path).path; qs=parse_qs(urlparse(self.path).query)
        if p in("/","index.html"): self._h(DASHBOARD.encode())
        elif p=="/api/stats": self._j(STATS.snap())
        elif p=="/api/server": self._j(_srv_status)
        elif p=="/api/modes": self._j(MODES_META)
        elif p=="/api/ping":
            host=qs.get("host",["localhost"])[0]; port=int(qs.get("port",["25565"])[0])
            proto=int(qs.get("proto",["769"])[0])
            r=ping_server(host,port,proto)
            if r.get("online"): _start_poller(host,port,proto); _srv_status.update(r)
            self._j(r)
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        global _engine,_engine_thread,_current_cfg
        p=urlparse(self.path).path
        l=int(self.headers.get("Content-Length",0))
        body=json.loads(self.rfile.read(l)) if l else {}
        if p=="/api/start":
            STATS.reset(); _current_cfg=body
            cfg={
                "host":          body.get("host","localhost"),
                "port":          int(body.get("port",25565)),
                "total_bots":    int(body.get("total_bots",100)),
                "concurrent":    int(body.get("concurrent",50)),
                "spawn_delay":   float(body.get("spawn_delay",0.05)),
                "spawn_jitter":  float(body.get("spawn_jitter",0.02)),
                "stay":          int(body.get("stay",120)),
                "username_mode": body.get("username_mode","realistic"),
                "username_prefix":body.get("username_prefix",""),
                "mc_version":    body.get("mc_version","auto"),
                "mode":          body.get("mode",Mode.FULL_BYPASS),
                "timeout":       int(body.get("timeout",10)),
                "move":          bool(body.get("move",True)),
                "move_interval": float(body.get("move_interval",0.5)),
                "spam":          bool(body.get("spam",False)),
                "respawn":       bool(body.get("respawn",True)),
                "send_play_settings": bool(body.get("send_play_settings",True)),
                "flood_cycles":  int(body.get("flood_cycles",5)),
                "ping_cycles":   int(body.get("ping_cycles",8)),
                "reconnect_cycles": int(body.get("reconnect_cycles",10)),
                "reconnect_delay":  float(body.get("reconnect_delay",0.3)),
            }
            proto=PROTOCOL_MAP.get(cfg["mc_version"],769)
            _start_poller(cfg["host"],cfg["port"],proto)
            _engine=Engine(cfg)
            _engine_thread=threading.Thread(target=_engine.start,daemon=True)
            _engine_thread.start()
            self._j({"ok":True})
        elif p=="/api/stop":
            if _engine: _engine.stop()
            self._j({"ok":True})
        elif p=="/api/reset":
            if _engine: _engine.stop()
            STATS.reset(); self._j({"ok":True})
        else: self.send_response(404); self.end_headers()

MODES_META = {
    Mode.FULL_BYPASS:  {"label":"FULL BYPASS","icon":"🛡️","color":"#00ff9d","desc":"Complete 1.20.2+ protocol: Login Ack, Config phase, Client Info, Brand, movement. Bypasses most anti-bot plugins."},
    Mode.LOGIN_STAY:   {"label":"LOGIN & STAY","icon":"🔗","color":"#00d4ff","desc":"Full login handshake + stay connected, respond to keep-alive. Good for testing player capacity."},
    Mode.PACKET_SPAM:  {"label":"PACKET SPAM","icon":"⚡","color":"#ffd60a","desc":"Login then flood server with position, look, chat packets. Maximum CPU stress on server."},
    Mode.TCP_FLOOD:    {"label":"TCP FLOOD","icon":"🌊","color":"#ff6b35","desc":"Maximum raw TCP connection throughput without login. Tests connection handler."},
    Mode.SLOW_LORIS:   {"label":"SLOW LORIS","icon":"🐌","color":"#a855f7","desc":"Byte-by-byte slow connections held open for minutes. Exhausts server connection pool."},
    Mode.RECONNECT:    {"label":"RECONNECT STORM","icon":"🔄","color":"#ec4899","desc":"Rapid connect/disconnect cycles. Stresses session creation and cleanup."},
    Mode.PING_STORM:   {"label":"PING STORM","icon":"📡","color":"#06b6d4","desc":"Rapid status pings with no login. Tests status protocol handler."},
    Mode.HYBRID:       {"label":"HYBRID MIX","icon":"🎲","color":"#f59e0b","desc":"Random mix of all modes per bot. Unpredictable load, hardest to protect against."},
}

# ─── DASHBOARD HTML ───────────────────────────────────────────────────────────
DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MC-STRIKE v3 · Bypass Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --bg:#030508;--s1:#07090f;--s2:#0a0e1a;--s3:#0f1525;--s4:#141c30;
  --acc:#00ff9d;--acc2:#00d4ff;--pur:#7c3aed;--red:#ff3b5c;--yel:#ffd60a;--ora:#ff6b35;
  --txt:#ccd6f6;--dim:#4a5568;--brd:rgba(255,255,255,.07);
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--txt);font-family:'Syne',sans-serif;font-size:14px;display:flex;flex-direction:column}

/* PARTICLES */
#bg{position:fixed;inset:0;z-index:0;pointer-events:none}

/* TOPBAR */
.topbar{
  position:relative;z-index:10;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;height:52px;
  background:rgba(7,9,15,.95);
  border-bottom:1px solid var(--brd);
  backdrop-filter:blur(16px);
  flex-shrink:0;
}
.brand{display:flex;align-items:center;gap:10px}
.brand-hex{
  width:30px;height:30px;
  background:linear-gradient(135deg,var(--pur),var(--acc2));
  clip-path:polygon(50% 0,100% 25,100% 75,50% 100,0 75,0 25);
  animation:spin 10s linear infinite;
}
@keyframes spin{to{transform:rotate(360deg)}}
.brand-name{font-size:1.1rem;font-weight:800;letter-spacing:.1em;
  background:linear-gradient(90deg,var(--acc),var(--acc2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.brand-v{font-size:.6rem;color:var(--dim);letter-spacing:.2em;font-family:'IBM Plex Mono',monospace;margin-top:-2px}
.topbar-right{display:flex;align-items:center;gap:10px}
.badge{
  display:flex;align-items:center;gap:6px;
  background:var(--s2);border:1px solid var(--brd);
  border-radius:20px;padding:4px 12px;
  font-size:.68rem;letter-spacing:.12em;font-family:'IBM Plex Mono',monospace;
}
.dot{width:6px;height:6px;border-radius:50%;background:var(--dim);flex-shrink:0}
.dot.on{background:var(--acc);box-shadow:0 0 6px var(--acc);animation:pulse 1.2s infinite}
.dot.run{background:var(--acc2);box-shadow:0 0 8px var(--acc2);animation:pulse .6s infinite}
.dot.err{background:var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* LAYOUT */
.layout{position:relative;z-index:1;display:grid;grid-template-columns:300px 1fr;flex:1;overflow:hidden}

/* SIDEBAR */
.sb{
  background:rgba(7,9,15,.92);
  border-right:1px solid var(--brd);
  overflow-y:auto;display:flex;flex-direction:column;gap:1px;
}
.sb::-webkit-scrollbar{width:3px}
.sb::-webkit-scrollbar-thumb{background:var(--s4)}

/* Accordion sections */
.sec{border-bottom:1px solid var(--brd)}
.sec-hd{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 14px;cursor:pointer;
  font-size:.68rem;font-weight:700;letter-spacing:.18em;color:var(--dim);
  font-family:'IBM Plex Mono',monospace;
  transition:color .2s;user-select:none;
}
.sec-hd:hover{color:var(--acc2)}
.sec-hd .chevron{transition:transform .2s;font-size:.8rem}
.sec-hd.open .chevron{transform:rotate(180deg)}
.sec-body{padding:0 14px 12px;display:none}
.sec-body.open{display:block}

/* Fields */
.f{margin-bottom:8px}
.f label{display:block;font-size:.62rem;letter-spacing:.14em;color:var(--dim);margin-bottom:3px;font-family:'IBM Plex Mono',monospace}
.f input,.f select{
  width:100%;background:var(--s2);border:1px solid var(--brd);
  color:var(--txt);font-family:'IBM Plex Mono',monospace;font-size:.78rem;
  padding:7px 9px;border-radius:5px;outline:none;
  transition:border-color .2s,box-shadow .2s;
}
.f input:focus,.f select:focus{border-color:var(--acc2);box-shadow:0 0 0 2px rgba(0,212,255,.1)}
.f select option{background:var(--s1)}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:6px}

/* Toggle switches */
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:4px 0}
.toggle-lbl{font-size:.72rem;color:var(--txt)}
.toggle-sub{font-size:.6rem;color:var(--dim);display:block;margin-top:1px}
.sw{position:relative;width:36px;height:20px;flex-shrink:0}
.sw input{opacity:0;width:0;height:0}
.sw-track{
  position:absolute;inset:0;background:var(--s3);border-radius:20px;
  border:1px solid var(--brd);cursor:pointer;transition:.2s;
}
.sw-track::after{
  content:'';position:absolute;top:2px;left:2px;
  width:14px;height:14px;border-radius:50%;
  background:var(--dim);transition:.2s;
}
input:checked + .sw-track{background:rgba(0,255,157,.15);border-color:var(--acc)}
input:checked + .sw-track::after{transform:translateX(16px);background:var(--acc)}

/* Mode cards */
.mode-list{display:flex;flex-direction:column;gap:4px}
.mode-card{
  background:var(--s2);border:1px solid var(--brd);border-radius:6px;
  padding:8px 10px;cursor:pointer;transition:all .15s;
}
.mode-card:hover{border-color:rgba(255,255,255,.15)}
.mode-card.sel{border-color:var(--sel-color,var(--acc));background:rgba(0,255,157,.06)}
.mc-top{display:flex;align-items:center;gap:7px;margin-bottom:3px}
.mc-icon{font-size:1rem;width:22px;text-align:center}
.mc-label{font-size:.75rem;font-weight:700;letter-spacing:.06em}
.mc-desc{font-size:.62rem;color:var(--dim);line-height:1.45;padding-left:29px}

/* Buttons */
.btn{
  font-family:'Syne',sans-serif;font-weight:700;font-size:.82rem;
  letter-spacing:.1em;padding:10px;border:none;border-radius:6px;
  cursor:pointer;width:100%;transition:all .18s;
}
.btn-launch{
  background:linear-gradient(135deg,#0d47a1 0%,#00d4ff 100%);
  color:#fff;box-shadow:0 4px 20px rgba(0,212,255,.2);
}
.btn-launch:hover:not(:disabled){box-shadow:0 6px 30px rgba(0,212,255,.45);transform:translateY(-1px)}
.btn-launch:disabled{opacity:.35;cursor:not-allowed;transform:none}
.btn-stop{background:linear-gradient(135deg,#7c0019,var(--red));color:#fff}
.btn-stop:disabled{opacity:.35;cursor:not-allowed}
.btn-ping{background:rgba(124,58,237,.12);color:#a78bfa;border:1px solid rgba(124,58,237,.3)}
.btn-ping:hover{background:rgba(124,58,237,.25)}
.btn-sm{font-size:.7rem;padding:7px;background:var(--s2);color:var(--dim);border:1px solid var(--brd)}
.btn-sm:hover{border-color:var(--brd);color:var(--txt)}
.btns2{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}
.mt6{margin-top:6px}

/* MAIN CONTENT */
.content{display:flex;flex-direction:column;overflow:hidden}

/* Server banner */
.srv-banner{
  padding:12px 18px;
  background:rgba(7,9,15,.85);
  border-bottom:1px solid var(--brd);
  display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;
  flex-shrink:0;
}
.srv-icon{
  width:42px;height:42px;border-radius:8px;
  background:var(--s3);border:1px solid var(--brd);
  display:flex;align-items:center;justify-content:center;font-size:1.4rem;
}
.srv-grid{display:flex;gap:0;overflow:hidden}
.srv-item{padding:0 14px;border-right:1px solid var(--brd);min-width:90px}
.srv-item:first-child{padding-left:0}
.srv-item:last-child{border-right:none}
.srv-lbl{font-size:.57rem;letter-spacing:.16em;color:var(--dim);font-family:'IBM Plex Mono',monospace;margin-bottom:2px}
.srv-val{font-size:.88rem;font-weight:700}
.srv-val.ok{color:var(--acc)}
.srv-val.no{color:var(--red)}
.srv-motd{font-size:.7rem;color:var(--dim);font-family:'IBM Plex Mono',monospace;margin-top:4px}
.player-chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
.chip{
  background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.15);
  border-radius:3px;padding:1px 7px;font-size:.62rem;
  font-family:'IBM Plex Mono',monospace;color:var(--acc2);
}
.srv-right{text-align:right;font-size:.65rem;font-family:'IBM Plex Mono',monospace}
.srv-refresh{color:var(--acc);font-size:.8rem;font-weight:700}

/* SCROLL AREA */
.scroll{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:12px}
.scroll::-webkit-scrollbar{width:4px}
.scroll::-webkit-scrollbar-thumb{background:var(--s4)}

/* STAT CARDS */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.sc{
  background:var(--s2);border:1px solid var(--brd);border-radius:8px;
  padding:14px 16px;position:relative;overflow:hidden;
}
.sc::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(circle at 0% 100%, var(--glow,transparent) 0%, transparent 60%);
  pointer-events:none;
}
.sc-val{
  font-family:'IBM Plex Mono',monospace;font-size:1.7rem;font-weight:700;
  line-height:1;margin-bottom:4px;color:var(--vc,var(--acc2));
}
.sc-lbl{font-size:.58rem;letter-spacing:.18em;color:var(--dim)}
.sc-sub{font-size:.66rem;color:var(--dim);margin-top:3px}
.sc-bar{position:absolute;bottom:0;left:0;right:0;height:2px;background:var(--vc,var(--acc2));opacity:.6;transform-origin:left;animation:grow 1s ease forwards}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.vc-g{--vc:var(--acc);--glow:rgba(0,255,157,.05)}
.vc-b{--vc:var(--acc2);--glow:rgba(0,212,255,.05)}
.vc-y{--vc:var(--yel);--glow:rgba(255,214,10,.04)}
.vc-r{--vc:var(--red);--glow:rgba(255,59,92,.04)}
.vc-p{--vc:var(--pur);--glow:rgba(124,58,237,.04)}
.vc-o{--vc:var(--ora);--glow:rgba(255,107,53,.04)}

/* BYPASS PANEL */
.bypass-panel{
  background:var(--s2);border:1px solid rgba(0,255,157,.15);border-radius:8px;
  padding:14px 16px;
}
.bypass-title{
  font-size:.62rem;letter-spacing:.2em;color:var(--acc);
  font-family:'IBM Plex Mono',monospace;
  display:flex;align-items:center;gap:8px;margin-bottom:12px;
}
.bypass-title::before{content:'';width:3px;height:9px;background:var(--acc);border-radius:2px}
.bypass-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.bp-item{
  background:var(--s3);border:1px solid var(--brd);border-radius:5px;
  padding:8px 10px;
}
.bp-icon{font-size:.85rem;margin-bottom:4px}
.bp-name{font-size:.62rem;font-weight:700;letter-spacing:.06em;margin-bottom:2px}
.bp-desc{font-size:.58rem;color:var(--dim);line-height:1.4}
.bp-item.active{border-color:rgba(0,255,157,.25);background:rgba(0,255,157,.04)}
.bp-item.active .bp-name{color:var(--acc)}

/* CHARTS */
.charts-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.cc{background:var(--s2);border:1px solid var(--brd);border-radius:8px;padding:12px 14px}
.cc-title{font-size:.6rem;letter-spacing:.18em;color:var(--dim);font-family:'IBM Plex Mono',monospace;margin-bottom:10px}
.cc-wrap{position:relative;height:110px}

/* BOTTOM */
.bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.panel{background:var(--s2);border:1px solid var(--brd);border-radius:8px;padding:12px 14px}
.panel-title{font-size:.6rem;letter-spacing:.2em;color:var(--dim);font-family:'IBM Plex Mono',monospace;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.panel-title::before{content:'';width:2px;height:8px;background:var(--acc2);border-radius:1px}

/* Progress bars */
.pb-item{margin-bottom:9px}
.pb-hd{display:flex;justify-content:space-between;margin-bottom:4px;font-size:.66rem}
.pb-l{color:var(--dim)}
.pb-v{font-family:'IBM Plex Mono',monospace;color:var(--txt)}
.pb-track{height:4px;background:var(--s4);border-radius:3px;overflow:hidden}
.pb-fill{height:100%;border-radius:3px;transition:width .5s;position:relative;overflow:hidden}
.pb-fill::after{content:'';position:absolute;top:0;right:0;bottom:0;width:30px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.2));animation:sh 1.5s infinite}
@keyframes sh{0%,100%{opacity:0}50%{opacity:1}}

/* Error table */
.et{width:100%;border-collapse:collapse;font-size:.68rem}
.et th{text-align:left;padding:5px 8px;font-size:.57rem;letter-spacing:.15em;color:var(--dim);border-bottom:1px solid var(--brd);font-family:'IBM Plex Mono',monospace}
.et td{padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.03)}
.et tr:hover td{background:rgba(255,255,255,.02)}
.et-cnt{color:var(--red);text-align:right;font-family:'IBM Plex Mono',monospace;font-weight:700}
.et-bar{height:2px;background:var(--red);opacity:.4;border-radius:1px;margin-top:2px;transition:width .4s}

/* Log */
.log{
  background:var(--s1);border:1px solid var(--brd);border-radius:5px;
  height:110px;overflow-y:auto;padding:8px;
  font-family:'IBM Plex Mono',monospace;font-size:.65rem;line-height:1.85;
  margin-top:10px;
}
.log::-webkit-scrollbar{width:2px}
.log::-webkit-scrollbar-thumb{background:var(--s4)}
.log-row{display:flex;gap:8px}
.log-ts{color:var(--dim);flex-shrink:0}
.log-m{color:#4a6080}
.log-m.s{color:var(--acc)}.log-m.w{color:var(--yel)}.log-m.e{color:var(--red)}.log-m.i{color:var(--acc2)}

/* Detail stats */
.detail-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}
.dg-item{background:var(--s3);border-radius:5px;padding:8px 10px}
.dg-val{font-size:1rem;font-weight:700;font-family:'IBM Plex Mono',monospace;color:var(--acc2)}
.dg-lbl{font-size:.58rem;letter-spacing:.12em;color:var(--dim);margin-top:1px}

@media(max-width:1200px){
  .layout{grid-template-columns:1fr}
  .sb{display:none}
  .stats-row{grid-template-columns:repeat(2,1fr)}
  .charts-grid{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="topbar">
  <div class="brand">
    <div class="brand-hex"></div>
    <div>
      <div class="brand-name">MC-STRIKE</div>
      <div class="brand-v">BYPASS EDITION v3</div>
    </div>
  </div>
  <div class="topbar-right">
    <div class="badge"><div class="dot" id="srvDot"></div><span id="srvTxt">SERVER —</span></div>
    <div class="badge"><div class="dot" id="runDot"></div><span id="runTxt">IDLE</span></div>
    <div class="badge" style="font-family:'IBM Plex Mono',monospace;color:var(--acc2)" id="uptBadge">0s</div>
  </div>
</div>

<div class="layout">
<!-- ══ SIDEBAR ══════════════════════════════════════════════════════════ -->
<div class="sb">

  <!-- TARGET -->
  <div class="sec">
    <div class="sec-hd open" onclick="toggle(this)">TARGET<span class="chevron">▾</span></div>
    <div class="sec-body open">
      <div class="row2">
        <div class="f"><label>HOST / IP</label><input id="host" value="localhost"></div>
        <div class="f"><label>PORT</label><input id="port" type="number" value="25565"></div>
      </div>
      <div class="row2">
        <div class="f">
          <label>MC VERSION</label>
          <select id="mcver">
            <option value="auto">Auto (1.21.4)</option>
            <option value="1.21.4">1.21.4</option>
            <option value="1.21.1">1.21.1</option>
            <option value="1.20.6">1.20.6</option>
            <option value="1.20.4">1.20.4</option>
            <option value="1.20.2">1.20.2</option>
            <option value="1.20.1">1.20.1</option>
            <option value="1.19.4">1.19.4</option>
          </select>
        </div>
        <div class="f"><label>TIMEOUT (s)</label><input id="timeout" type="number" value="10"></div>
      </div>
      <button class="btn btn-ping mt6" onclick="doPing()">◈ PING SERVER</button>
    </div>
  </div>

  <!-- ATTACK MODE -->
  <div class="sec">
    <div class="sec-hd open" onclick="toggle(this)">ATTACK MODE<span class="chevron">▾</span></div>
    <div class="sec-body open">
      <div class="mode-list" id="modeList">Loading...</div>
    </div>
  </div>

  <!-- BOT CONFIG -->
  <div class="sec">
    <div class="sec-hd open" onclick="toggle(this)">BOT CONFIG<span class="chevron">▾</span></div>
    <div class="sec-body open">
      <div class="row2">
        <div class="f"><label>TOTAL BOTS</label><input id="totalBots" type="number" value="200"></div>
        <div class="f"><label>CONCURRENT</label><input id="concurrent" type="number" value="100"></div>
      </div>
      <div class="row2">
        <div class="f"><label>SPAWN DELAY (s)</label><input id="spawnDelay" type="number" value="0.03" step="0.01"></div>
        <div class="f"><label>JITTER (s)</label><input id="spawnJitter" type="number" value="0.02" step="0.01"></div>
      </div>
      <div class="f"><label>STAY DURATION (s)</label><input id="stay" type="number" value="120"></div>
      <div class="row2">
        <div class="f">
          <label>NAME MODE</label>
          <select id="nameMode">
            <option value="realistic">Realistic</option>
            <option value="random">Random</option>
            <option value="prefix">Prefix</option>
          </select>
        </div>
        <div class="f"><label>PREFIX</label><input id="namePrefix" placeholder="Bot"></div>
      </div>
    </div>
  </div>

  <!-- BYPASS TOGGLES -->
  <div class="sec">
    <div class="sec-hd open" onclick="toggle(this)">BYPASS OPTIONS<span class="chevron">▾</span></div>
    <div class="sec-body open">
      <div class="toggle-row">
        <div><div class="toggle-lbl">Player Movement</div><span class="toggle-sub">Send realistic position packets</span></div>
        <label class="sw"><input type="checkbox" id="tMove" checked><div class="sw-track"></div></label>
      </div>
      <div class="toggle-row">
        <div><div class="toggle-lbl">Chat Spam</div><span class="toggle-sub">Send periodic chat messages</span></div>
        <label class="sw"><input type="checkbox" id="tSpam"><div class="sw-track"></div></label>
      </div>
      <div class="toggle-row">
        <div><div class="toggle-lbl">Auto Respawn</div><span class="toggle-sub">Respawn bots after death</span></div>
        <label class="sw"><input type="checkbox" id="tRespawn" checked><div class="sw-track"></div></label>
      </div>
      <div class="toggle-row">
        <div><div class="toggle-lbl">Play-phase Brand</div><span class="toggle-sub">Send minecraft:brand in play</span></div>
        <label class="sw"><input type="checkbox" id="tBrand" checked><div class="sw-track"></div></label>
      </div>
      <div class="f mt6"><label>MOVE INTERVAL (s)</label><input id="moveInterval" type="number" value="0.5" step="0.1"></div>
    </div>
  </div>

  <!-- FLOOD CONFIG -->
  <div class="sec">
    <div class="sec-hd" onclick="toggle(this)">FLOOD SETTINGS<span class="chevron">▾</span></div>
    <div class="sec-body">
      <div class="row2">
        <div class="f"><label>FLOOD CYCLES</label><input id="floodCycles" type="number" value="5"></div>
        <div class="f"><label>PING CYCLES</label><input id="pingCycles" type="number" value="8"></div>
      </div>
      <div class="row2">
        <div class="f"><label>RECONNECT CYCLES</label><input id="reconnectCycles" type="number" value="10"></div>
        <div class="f"><label>RECONNECT DELAY</label><input id="reconnectDelay" type="number" value="0.3" step="0.1"></div>
      </div>
    </div>
  </div>

  <!-- LAUNCH -->
  <div style="padding:14px;margin-top:auto">
    <button class="btn btn-launch" id="btnLaunch" onclick="launch()">▶ LAUNCH ATTACK</button>
    <div class="btns2">
      <button class="btn btn-stop" id="btnStop" onclick="stop()" disabled>■ STOP</button>
      <button class="btn btn-sm" onclick="reset()">↺ RESET</button>
    </div>
  </div>

</div><!-- /sb -->

<!-- ══ CONTENT ══════════════════════════════════════════════════════════ -->
<div class="content">

  <!-- Server Banner -->
  <div class="srv-banner">
    <div class="srv-icon" id="srvIcon">⬛</div>
    <div style="overflow:hidden">
      <div class="srv-grid">
        <div class="srv-item">
          <div class="srv-lbl">STATUS</div>
          <div class="srv-val no" id="si-status">OFFLINE</div>
        </div>
        <div class="srv-item">
          <div class="srv-lbl">PLAYERS</div>
          <div class="srv-val" id="si-players">— / —</div>
        </div>
        <div class="srv-item">
          <div class="srv-lbl">VERSION</div>
          <div class="srv-val" id="si-version">—</div>
        </div>
        <div class="srv-item">
          <div class="srv-lbl">LATENCY</div>
          <div class="srv-val" id="si-latency">—</div>
        </div>
        <div class="srv-item">
          <div class="srv-lbl">BOTS/SEC</div>
          <div class="srv-val" id="si-bps" style="color:var(--yel)">0</div>
        </div>
      </div>
      <div class="srv-motd" id="si-motd">Ping server to see status</div>
      <div class="player-chips" id="playerChips"></div>
    </div>
    <div class="srv-right">
      <div class="srv-lbl">AUTO REFRESH</div>
      <div class="srv-refresh" id="refCountdown">—</div>
    </div>
  </div>

  <div class="scroll">

    <!-- Bypass Status Panel -->
    <div class="bypass-panel">
      <div class="bypass-title">ACTIVE BYPASS TECHNIQUES</div>
      <div class="bypass-grid" id="bypassGrid">
        <div class="bp-item active"><div class="bp-icon">🔐</div><div class="bp-name">FULL PROTOCOL</div><div class="bp-desc">Complete 1.20.2+ login→config→play flow</div></div>
        <div class="bp-item active"><div class="bp-icon">✅</div><div class="bp-name">LOGIN ACK</div><div class="bp-desc">Login Acknowledged (0x03) sent</div></div>
        <div class="bp-item active"><div class="bp-icon">📋</div><div class="bp-name">CLIENT INFO</div><div class="bp-desc">Client Information in config phase</div></div>
        <div class="bp-item active"><div class="bp-icon">🏷️</div><div class="bp-name">BRAND PKT</div><div class="bp-desc">minecraft:brand = vanilla sent</div></div>
        <div class="bp-item" id="bp-move"><div class="bp-icon">🚶</div><div class="bp-name">MOVEMENT</div><div class="bp-desc">Realistic position/rotation packets</div></div>
        <div class="bp-item active"><div class="bp-icon">💓</div><div class="bp-name">KEEP-ALIVE</div><div class="bp-desc">Responds to all keep-alive IDs</div></div>
        <div class="bp-item" id="bp-respawn"><div class="bp-icon">💀</div><div class="bp-name">RESPAWN</div><div class="bp-desc">Auto-respawn on death</div></div>
        <div class="bp-item active"><div class="bp-icon">⏱️</div><div class="bp-name">JITTER</div><div class="bp-desc">Randomized timing, human patterns</div></div>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="sc vc-g"><div class="sc-val" id="st-active">0</div><div class="sc-lbl">ACTIVE BOTS</div><div class="sc-sub" id="st-spawned">0 spawned</div><div class="sc-bar"></div></div>
      <div class="sc vc-b"><div class="sc-val" id="st-connected">0</div><div class="sc-lbl">CONNECTED</div><div class="sc-sub" id="st-cr">0% rate</div><div class="sc-bar"></div></div>
      <div class="sc vc-y"><div class="sc-val" id="st-loginok">0</div><div class="sc-lbl">LOGIN OK</div><div class="sc-sub" id="st-lr">0% rate</div><div class="sc-bar"></div></div>
      <div class="sc vc-r"><div class="sc-val" id="st-failed">0</div><div class="sc-lbl">FAILED</div><div class="sc-sub" id="st-kicked">0 kicked</div><div class="sc-bar"></div></div>
    </div>

    <!-- Charts -->
    <div class="charts-grid">
      <div class="cc">
        <div class="cc-title">◈ ACTIVE BOTS</div>
        <div class="cc-wrap"><canvas id="cActive"></canvas></div>
      </div>
      <div class="cc">
        <div class="cc-title">⚡ CONNECTIONS / SEC</div>
        <div class="cc-wrap"><canvas id="cCps"></canvas></div>
      </div>
      <div class="cc">
        <div class="cc-title">◎ AVG LATENCY ms</div>
        <div class="cc-wrap"><canvas id="cLat"></canvas></div>
      </div>
    </div>

    <!-- Bottom Row -->
    <div class="bottom-row">
      <div class="panel">
        <div class="panel-title">PERFORMANCE METRICS</div>
        <div class="pb-item">
          <div class="pb-hd"><span class="pb-l">CONNECTION RATE</span><span class="pb-v" id="pv-cr">0%</span></div>
          <div class="pb-track"><div class="pb-fill" id="pb-cr" style="width:0%;background:linear-gradient(90deg,#00d4ff,#00ff9d)"></div></div>
        </div>
        <div class="pb-item">
          <div class="pb-hd"><span class="pb-l">LOGIN SUCCESS RATE</span><span class="pb-v" id="pv-lr">0%</span></div>
          <div class="pb-track"><div class="pb-fill" id="pb-lr" style="width:0%;background:linear-gradient(90deg,#7c3aed,#00d4ff)"></div></div>
        </div>
        <div class="pb-item">
          <div class="pb-hd"><span class="pb-l">DEPLOYMENT PROGRESS</span><span class="pb-v" id="pv-prog">0%</span></div>
          <div class="pb-track"><div class="pb-fill" id="pb-prog" style="width:0%;background:linear-gradient(90deg,#ffd60a,#ff6b35)"></div></div>
        </div>
        <div class="detail-grid">
          <div class="dg-item"><div class="dg-val" id="dg-pkts">0</div><div class="dg-lbl">PACKETS SENT</div></div>
          <div class="dg-item"><div class="dg-val" id="dg-bytes">0B</div><div class="dg-lbl">DATA SENT</div></div>
          <div class="dg-item"><div class="dg-val" id="dg-lat">0ms</div><div class="dg-lbl">AVG LATENCY</div></div>
          <div class="dg-item"><div class="dg-val" id="dg-attempts">0</div><div class="dg-lbl">ATTEMPTS</div></div>
          <div class="dg-item"><div class="dg-val" id="dg-loginfail">0</div><div class="dg-lbl">LOGIN FAIL</div></div>
          <div class="dg-item"><div class="dg-val" id="dg-uptime">0s</div><div class="dg-lbl">UPTIME</div></div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">ERROR BREAKDOWN</div>
        <table class="et">
          <thead><tr><th style="width:78%">ERROR</th><th style="text-align:right">COUNT</th></tr></thead>
          <tbody id="errTb"></tbody>
        </table>
        <div class="panel-title" style="margin-top:10px">ACTIVITY LOG</div>
        <div class="log" id="logEl"></div>
      </div>
    </div>

  </div><!-- /scroll -->
</div><!-- /content -->
</div><!-- /layout -->

<script>
// ── PARTICLES ──────────────────────────────────────────────────────────────
(()=>{
  const c=document.getElementById('bg'),ctx=c.getContext('2d');
  let W,H,pts=[];
  const resize=()=>{W=c.width=innerWidth;H=c.height=innerHeight};
  resize();window.addEventListener('resize',resize);
  for(let i=0;i<60;i++)pts.push({x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.25,vy:(Math.random()-.5)*.25,r:Math.random()*1.2+.4});
  const frame=()=>{
    ctx.clearRect(0,0,W,H);
    pts.forEach(p=>{
      p.x+=p.vx;p.y+=p.vy;
      if(p.x<0)p.x=W;if(p.x>W)p.x=0;
      if(p.y<0)p.y=H;if(p.y>H)p.y=0;
      ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle='rgba(0,212,255,.4)';ctx.fill();
    });
    pts.forEach((a,i)=>pts.slice(i+1).forEach(b=>{
      const d=Math.hypot(a.x-b.x,a.y-b.y);
      if(d<100){ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);
        ctx.strokeStyle=`rgba(0,212,255,${.12*(1-d/100)})`;ctx.lineWidth=.5;ctx.stroke()}
    }));
    requestAnimationFrame(frame);
  };
  frame();
})();

// ── ACCORDION ──────────────────────────────────────────────────────────────
function toggle(hd){
  hd.classList.toggle('open');
  const body=hd.nextElementSibling;
  body.classList.toggle('open');
}

// ── STATE ──────────────────────────────────────────────────────────────────
let running=false,selMode='full_bypass',totalBots=200;
let logs=[],maxLogs=80;

// ── CHARTS ─────────────────────────────────────────────────────────────────
const N=90;
const charts={};
const mkChart=(id,color,fill)=>{
  const ctx=document.getElementById(id).getContext('2d');
  return new Chart(ctx,{
    type:'line',
    data:{labels:Array(N).fill(''),datasets:[{data:Array(N).fill(null),borderColor:color,backgroundColor:fill,borderWidth:1.5,pointRadius:0,tension:.4,fill:true}]},
    options:{
      responsive:true,maintainAspectRatio:false,animation:{duration:300},
      plugins:{legend:{display:false},tooltip:{enabled:false}},
      scales:{x:{display:false},y:{display:true,grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'rgba(100,130,170,.6)',font:{family:'IBM Plex Mono',size:8},maxTicksLimit:4}}}
    }
  });
};
charts.active =mkChart('cActive','#00ff9d','rgba(0,255,157,.06)');
charts.cps    =mkChart('cCps','#00d4ff','rgba(0,212,255,.06)');
charts.latency=mkChart('cLat','#ffd60a','rgba(255,214,10,.06)');

function pushChart(ch,data){
  const padded=[...Array(N-data.length).fill(null),...data];
  ch.data.datasets[0].data=padded;ch.update('none');
}

// ── LOG ────────────────────────────────────────────────────────────────────
function lg(msg,t=''){
  const ts=new Date().toTimeString().slice(0,8);
  logs.push({ts,msg,t});if(logs.length>maxLogs)logs.shift();
  const el=document.getElementById('logEl');
  el.innerHTML=logs.map(l=>`<div class="log-row"><span class="log-ts">${l.ts}</span><span class="log-m ${l.t}">${l.msg}</span></div>`).join('');
  el.scrollTop=el.scrollHeight;
}

// ── MODES ──────────────────────────────────────────────────────────────────
async function loadModes(){
  try{
    const d=await (await fetch('/api/modes')).json();
    const list=document.getElementById('modeList');list.innerHTML='';
    Object.entries(d).forEach(([key,{label,icon,color,desc}])=>{
      const el=document.createElement('div');
      el.className='mode-card'+(key===selMode?' sel':'');
      el.style.setProperty('--sel-color',color);
      el.innerHTML=`<div class="mc-top"><span class="mc-icon">${icon}</span><span class="mc-label" style="color:${key===selMode?color:'inherit'}">${label}</span></div><div class="mc-desc">${desc}</div>`;
      el.onclick=()=>{
        selMode=key;
        document.querySelectorAll('.mode-card').forEach(c=>{
          c.classList.remove('sel');
          c.querySelector('.mc-label').style.color='';
        });
        el.classList.add('sel');
        el.querySelector('.mc-label').style.color=color;
        lg(`Mode: ${label}`,'i');
        // update bypass panel highlights
        document.querySelectorAll('.bp-item').forEach(b=>b.classList.remove('active'));
        const always=['bp-item:nth-child(6)','bp-item:nth-child(8)'];
        document.querySelectorAll('.bypass-panel .bp-item').forEach((b,i)=>{
          if([Mode.FULL_BYPASS,'full_bypass'].includes(key)){b.classList.add('active')}
          else if(i<2)b.classList.add('active');
        });
      };
      list.appendChild(el);
    });
  }catch(e){lg('Failed to load modes','e')}
}
loadModes();

// ── SYNC BYPASS INDICATORS ────────────────────────────────────────────────
document.getElementById('tMove').addEventListener('change',e=>{
  document.getElementById('bp-move').classList.toggle('active',e.target.checked);
});
document.getElementById('tRespawn').addEventListener('change',e=>{
  document.getElementById('bp-respawn').classList.toggle('active',e.target.checked);
});

// ── SERVER STATUS ─────────────────────────────────────────────────────────
let refTimer=null,refCountdown=0;
function updateSrvBanner(d){
  const on=d.online;
  document.getElementById('si-status').textContent=on?'ONLINE':'OFFLINE';
  document.getElementById('si-status').className='srv-val '+(on?'ok':'no');
  document.getElementById('si-players').textContent=on?`${d.players_online} / ${d.players_max}`:'— / —';
  document.getElementById('si-version').textContent=on?d.version:'—';
  document.getElementById('si-latency').textContent=on?`${d.latency_ms}ms`:'—';
  document.getElementById('si-motd').textContent=on?d.motd:'Ping server to see status';
  document.getElementById('srvIcon').textContent=on?'🟢':'⬛';
  document.getElementById('srvDot').className='dot'+(on?' on':'');
  document.getElementById('srvTxt').textContent=on?`${d.players_online}/${d.players_max} players`:'SERVER OFFLINE';
  const pc=document.getElementById('playerChips');
  pc.innerHTML=(d.player_sample||[]).map(n=>`<div class="chip">${n}</div>`).join('');
  // auto-refresh countdown
  refCountdown=4;
  if(refTimer)clearInterval(refTimer);
  refTimer=setInterval(()=>{
    refCountdown=Math.max(0,refCountdown-1);
    document.getElementById('refCountdown').textContent=refCountdown+'s';
  },1000);
}

// Poll server status from backend
setInterval(async()=>{
  try{
    const d=await(await fetch('/api/server')).json();
    if(d.online!==undefined)updateSrvBanner(d);
  }catch{}
},1000);

async function doPing(){
  const host=document.getElementById('host').value,port=document.getElementById('port').value;
  lg(`Pinging ${host}:${port}...`,'i');
  try{
    const d=await(await fetch(`/api/ping?host=${encodeURIComponent(host)}&port=${port}&proto=769`)).json();
    updateSrvBanner(d);
    if(d.online)lg(`Online! ${d.players_online}/${d.players_max} players | ${d.version} | ${d.latency_ms}ms`,'s');
    else lg(`Offline: ${d.error}`,'e');
  }catch(e){lg('Ping error: '+e,'e')}
}

// ── LAUNCH ─────────────────────────────────────────────────────────────────
async function launch(){
  if(running)return;
  totalBots=parseInt(document.getElementById('totalBots').value)||100;
  const cfg={
    host:             document.getElementById('host').value,
    port:             parseInt(document.getElementById('port').value),
    mc_version:       document.getElementById('mcver').value,
    mode:             selMode,
    total_bots:       totalBots,
    concurrent:       parseInt(document.getElementById('concurrent').value),
    spawn_delay:      parseFloat(document.getElementById('spawnDelay').value),
    spawn_jitter:     parseFloat(document.getElementById('spawnJitter').value),
    stay:             parseInt(document.getElementById('stay').value),
    username_mode:    document.getElementById('nameMode').value,
    username_prefix:  document.getElementById('namePrefix').value,
    timeout:          parseInt(document.getElementById('timeout').value),
    move:             document.getElementById('tMove').checked,
    move_interval:    parseFloat(document.getElementById('moveInterval').value),
    spam:             document.getElementById('tSpam').checked,
    respawn:          document.getElementById('tRespawn').checked,
    send_play_settings:document.getElementById('tBrand').checked,
    flood_cycles:     parseInt(document.getElementById('floodCycles').value),
    ping_cycles:      parseInt(document.getElementById('pingCycles').value),
    reconnect_cycles: parseInt(document.getElementById('reconnectCycles').value),
    reconnect_delay:  parseFloat(document.getElementById('reconnectDelay').value),
  };
  lg(`Launching ${totalBots} bots [${selMode}] → ${cfg.host}:${cfg.port}`,'w');
  try{
    const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
    const d=await r.json();
    if(d.ok){running=true;setRunning(true);lg('Attack started!','s')}
    else lg('Failed: '+d.error,'e');
  }catch(e){lg('Error: '+e,'e')}
}

async function stop(){
  await fetch('/api/stop',{method:'POST'}).catch(()=>{});
  running=false;setRunning(false);lg('Stopped.','w');
}

async function reset(){
  await fetch('/api/reset',{method:'POST'}).catch(()=>{});
  running=false;setRunning(false);lg('Reset.','i');
}

function setRunning(r){
  document.getElementById('btnLaunch').disabled=r;
  document.getElementById('btnStop').disabled=!r;
  document.getElementById('runDot').className='dot'+(r?' run':'');
  document.getElementById('runTxt').textContent=r?'RUNNING':'IDLE';
}

// ── FORMAT ─────────────────────────────────────────────────────────────────
const fmt=n=>{n=Math.floor(n||0);return n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':n.toString()};
const fmtB=b=>{return b>=1048576?(b/1048576).toFixed(1)+'MB':b>=1024?(b/1024).toFixed(1)+'KB':b+'B'};
const fmtT=s=>{s=Math.floor(s);return s<60?s+'s':Math.floor(s/60)+'m '+s%60+'s'};

// ── STATS POLL ─────────────────────────────────────────────────────────────
async function pollStats(){
  if(!running)return;
  try{
    const d=await(await fetch('/api/stats')).json();
    document.getElementById('st-active').textContent=fmt(d.active);
    document.getElementById('st-spawned').textContent=fmt(d.spawned)+' spawned';
    document.getElementById('st-connected').textContent=fmt(d.tcp_ok);
    document.getElementById('st-cr').textContent=d.connect_rate+'% rate';
    document.getElementById('st-loginok').textContent=fmt(d.login_ok);
    document.getElementById('st-lr').textContent=d.login_rate+'% rate';
    document.getElementById('st-failed').textContent=fmt(d.tcp_fail);
    document.getElementById('st-kicked').textContent=fmt(d.kicked)+' kicked';
    document.getElementById('si-bps').textContent=d.bps;
    document.getElementById('uptBadge').textContent=fmtT(d.uptime);

    // Progress bars
    const cr=d.connect_rate||0,lr=d.login_rate||0,prog=Math.min(100,Math.round(d.attempts/totalBots*100));
    document.getElementById('pb-cr').style.width=cr+'%';document.getElementById('pv-cr').textContent=cr+'%';
    document.getElementById('pb-lr').style.width=lr+'%';document.getElementById('pv-lr').textContent=lr+'%';
    document.getElementById('pb-prog').style.width=prog+'%';document.getElementById('pv-prog').textContent=prog+'%';

    // Detail grid
    document.getElementById('dg-pkts').textContent=fmt(d.pkts);
    document.getElementById('dg-bytes').textContent=fmtB(d.bytes);
    document.getElementById('dg-lat').textContent=d.avg_lat+'ms';
    document.getElementById('dg-attempts').textContent=fmt(d.attempts);
    document.getElementById('dg-loginfail').textContent=fmt(d.login_fail);
    document.getElementById('dg-uptime').textContent=fmtT(d.uptime);

    // Charts
    pushChart(charts.active,d.ts_active||[]);
    pushChart(charts.cps,d.ts_cps||[]);
    pushChart(charts.latency,d.ts_lat||[]);

    // Errors
    const errs=d.top_errors||{};
    const mx=Math.max(...Object.values(errs),1);
    document.getElementById('errTb').innerHTML=Object.entries(errs).slice(0,6).map(([e,c])=>`
      <tr>
        <td>${e.substring(0,52)}<div class="et-bar" style="width:${Math.round(c/mx*100)}%"></div></td>
        <td class="et-cnt">${c}</td>
      </tr>`).join('');

    // Auto-stop
    if(d.attempts>=totalBots&&d.active===0&&running){
      running=false;setRunning(false);
      lg(`Done! TCP:${d.tcp_ok} Login:${d.login_ok} Failed:${d.tcp_fail} Kicked:${d.kicked}`,'s');
    }
  }catch{}
}

setInterval(pollStats,800);
lg('MC-STRIKE v3 ready. Configure target and launch.','i');
</script>
</body>
</html>"""


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8080)
    a=p.parse_args()
    print(f"\n  MC-STRIKE v3 Dashboard → http://localhost:{a.port}\n")
    HTTPServer(("0.0.0.0",a.port),H).serve_forever()

if __name__=="__main__":
    main()
