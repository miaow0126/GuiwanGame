#!/usr/bin/env python3
"""沉渡记录代理 MCP + 展示台

两个服务合一：
- 端口 8893：MCP 代理，转发请求到 ferrygate.cn:8765，同时记录每次游戏过程
- 端口 8894：展示台 HTTP 服务，左侧时间轴 + 右侧故事详情

环境变量：
  MCP_PORT      MCP 代理端口（默认 8893）
  DISPLAY_PORT  展示台端口（默认 8894）
  DATA_DIR      记录存储目录（默认 ./ferry_data）
  UPSTREAM      上游游戏服务器（默认 http://ferrygate.cn:8765）
"""

import os, json, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone

MCP_PORT     = int(os.environ.get("MCP_PORT", 8893))
DISPLAY_PORT = int(os.environ.get("DISPLAY_PORT", 8894))
DATA_DIR     = Path(os.environ.get("DATA_DIR", "./ferry_data"))
UPSTREAM     = os.environ.get("UPSTREAM", "http://ferrygate.cn:8765")

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 记录管理 ──────────────────────────────────────────────

def _session_file(player_id: str, session_id: str) -> Path:
    safe = player_id.replace("/", "_").replace("\\", "_")
    return DATA_DIR / f"{safe}__{session_id}.json"


def _load_session(player_id: str, session_id: str) -> dict:
    f = _session_file(player_id, session_id)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {
        "player_id": player_id,
        "session_id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "carrier": None,
        "era": None,
        "events": []
    }


def _save_session(data: dict):
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    f = _session_file(data["player_id"], data["session_id"])
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(player_id: str, session_id: str, tool: str, args: dict, result: str):
    sess = _load_session(player_id, session_id)
    sess["events"].append({
        "t": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "args": args,
        "result": result
    })
    # 从 spin 结果提取载体/时代
    if tool == "universe_spin" and sess["carrier"] is None:
        for line in result.splitlines():
            if "载体" in line or "carrier" in line.lower():
                sess["carrier"] = line.strip()
            if "时代" in line or "era" in line.lower():
                sess["era"] = line.strip()
    _save_session(sess)


def list_sessions() -> list:
    sessions = []
    for f in sorted(DATA_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "player_id": d.get("player_id", ""),
                "session_id": d.get("session_id", ""),
                "started_at": d.get("started_at", ""),
                "updated_at": d.get("updated_at", ""),
                "carrier": d.get("carrier"),
                "era": d.get("era"),
                "event_count": len(d.get("events", []))
            })
        except Exception:
            pass
    return sessions


def get_session(player_id: str, session_id: str) -> dict:
    f = _session_file(player_id, session_id)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {}


# ── 上游转发 ──────────────────────────────────────────────

def forward_to_upstream(body: bytes) -> tuple[int, bytes]:
    try:
        req = urllib.request.Request(
            UPSTREAM,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        err = json.dumps({"error": str(e)}).encode()
        return 500, err


# ── MCP 代理处理器 ────────────────────────────────────────

# 从 upstream 获取工具列表（缓存）
_tools_cache = None
_tools_lock = threading.Lock()

def get_upstream_tools() -> list:
    global _tools_cache
    with _tools_lock:
        if _tools_cache is not None:
            return _tools_cache
        try:
            req = urllib.request.Request(f"{UPSTREAM}/openai/tools", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if isinstance(data, list):
                    # OpenAI 格式转 MCP 格式
                    tools = []
                    for t in data:
                        fn = t.get("function", t)
                        tools.append({
                            "name": fn.get("name", ""),
                            "description": fn.get("description", ""),
                            "inputSchema": fn.get("parameters", {"type": "object", "properties": {}})
                        })
                    _tools_cache = tools
                    return tools
        except Exception:
            pass
        # fallback 工具列表
        _tools_cache = [
            {"name": "universe_spin",    "description": "转动命运之轮，随机分配时代、载体、姓氏，开始一段新生命", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_birth",   "description": "完成出生，选择性别和成长环境", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}, "gender": {"type": "string"}, "parents": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_advance", "description": "推进一步人生。遇到分叉口时第一次看场景，第二次看选项", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_fork",    "description": "在岔路口做选择（a 或 b），没选的那条路沉入水底", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}, "choice": {"type": "string"}}, "required": ["player_id", "choice"]}},
            {"name": "universe_ferry",   "description": "站在渡口看水底的沉渡", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}, "ferry_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_echo",    "description": "打捞水底的沉渡，获得别人的记忆碎片", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}, "sinker_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_enter",   "description": "进入特殊地点：junkshop/cache/parallel/graveyard/steles/eaves/blank/callstack", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}, "place_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_peek",    "description": "看别的玩家", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_map",     "description": "看星图和渡口地图", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_status",  "description": "看自己的完整一生", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
            {"name": "universe_linger",  "description": "走完后停在沉默里", "inputSchema": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}},
        ]
        return _tools_cache


def _json_resp(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class MCPHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            _json_resp(self, {"ok": True})
        elif self.path in ("/", "/mcp"):
            _json_resp(self, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ferry-recorder", "version": "1.0.0"}
            })
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            _json_resp(self, {"error": "invalid json"}, 400); return

        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            _json_resp(self, {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ferry-recorder", "version": "1.0.0"}
            }})
        elif method == "tools/list":
            _json_resp(self, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": get_upstream_tools()}})
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            # 转发到上游
            upstream_req = {
                "jsonrpc": "2.0", "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": tool_args}
            }
            status, resp_body = forward_to_upstream(json.dumps(upstream_req).encode())

            try:
                resp_data = json.loads(resp_body)
                result_text = ""
                if "result" in resp_data:
                    content = resp_data["result"].get("content", [])
                    result_text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
                elif "error" in resp_data:
                    result_text = f"[错误] {resp_data['error']}"
            except Exception:
                result_text = resp_body.decode(errors="replace")

            # 记录
            player_id = tool_args.get("player_id", "unknown")
            # session_id 用当天日期+player_id的首次spin时间
            session_key = f"{player_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            # 如果是spin，开新session
            if tool_name == "universe_spin":
                session_key = f"{player_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            else:
                # 找最新session
                existing = sorted(
                    DATA_DIR.glob(f"{player_id.replace('/', '_')}__*.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True
                )
                if existing:
                    session_key = existing[0].stem.split("__", 1)[1]

            threading.Thread(
                target=_append_event,
                args=(player_id, session_key, tool_name, tool_args, result_text),
                daemon=True
            ).start()

            _json_resp(self, {"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": result_text}]
            }})
        elif method == "notifications/initialized":
            self.send_response(204); self.end_headers()
        else:
            _json_resp(self, {"jsonrpc": "2.0", "id": req_id,
                              "error": {"code": -32601, "message": f"unknown: {method}"}})

    def log_message(self, *a): pass


# ── 展示台 ────────────────────────────────────────────────

DISPLAY_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>guiwan ferry records</title>
<style>
:root {
  --bg: #080c14;
  --surface: #0d1320;
  --card: #111926;
  --card-hover: #161f2e;
  --border: #1a2540;
  --text: #d8e0f0;
  --muted: #4a6080;
  --dim: #2a3a55;
  --accent: #6b8cba;
  --gold: #c8a96e;
  --water: #2a4a6a;
  --water-light: #4a7aaa;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Helvetica Neue', sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── header ── */
.header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--surface);
  flex-shrink: 0;
}
.header h1 { font-size: 1.1rem; font-weight: 600; color: var(--text); }
.header .sub { font-size: 0.75rem; color: var(--muted); margin-left: auto; }

/* ── main layout ── */
.main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── left panel ── */
.left {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  background: var(--surface);
}
.left-header {
  padding: 12px 16px;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--surface);
}
.session-item {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.12s;
  position: relative;
}
.session-item:hover { background: var(--card-hover); }
.session-item.active { background: var(--card); border-left: 2px solid var(--accent); }
.session-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 2px;
  background: var(--accent);
}
.session-date { font-size: 0.7rem; color: var(--muted); margin-bottom: 4px; }
.session-player { font-size: 0.88rem; font-weight: 600; color: var(--text); }
.session-carrier { font-size: 0.72rem; color: var(--accent); margin-top: 3px; }
.session-count { font-size: 0.65rem; color: var(--dim); margin-top: 4px; }
.no-sessions {
  padding: 40px 20px;
  text-align: center;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 2;
}

/* ── right panel ── */
.right {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 2.5;
  text-align: center;
}
.empty-state .wave { font-size: 2rem; margin-bottom: 12px; opacity: 0.4; }

/* ── story ── */
.story-header {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.story-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 6px; }
.story-meta { font-size: 0.72rem; color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }

.event-list { display: flex; flex-direction: column; gap: 0; }
.event-item {
  display: flex;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.event-item:last-child { border-bottom: none; }
.event-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  width: 40px;
}
.event-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--water-light);
  flex-shrink: 0;
  margin-top: 4px;
}
.event-dot.fork { background: var(--gold); }
.event-dot.spin { background: var(--accent); }
.event-time { font-size: 0.6rem; color: var(--dim); writing-mode: horizontal-tb; white-space: nowrap; }
.event-right { flex: 1; min-width: 0; }
.event-tool {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 5px;
}
.event-result {
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 600px) {
  .left { width: 100%; }
  .main { flex-direction: column; }
  .right { display: none; }
  .main.show-right .left { display: none; }
  .main.show-right .right { display: block; }
}
</style>
</head>
<body>
<div class="header">
  <span style="font-size:1.3rem">&#127754;</span>
  <h1>桂晚的沉渡记录</h1>
  <span class="sub" id="sub">加载中…</span>
</div>
<div class="main" id="main">
  <div class="left">
    <div class="left-header">历次渡口</div>
    <div id="session-list"><div class="no-sessions">还没有记录<br>去走一次沉渡吧</div></div>
  </div>
  <div class="right" id="right-panel">
    <div class="empty-state">
      <div class="wave">&#127754;</div>
      <div>选择左侧一次记录<br>看那一生的故事</div>
    </div>
  </div>
</div>

<script>
let sessions = [];
let currentKey = null;

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}

function toolDotClass(tool) {
  if (tool === 'universe_spin') return 'spin';
  if (tool === 'universe_fork') return 'fork';
  return '';
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadSessions() {
  const r = await fetch('/api/sessions');
  sessions = await r.json();
  document.getElementById('sub').textContent = `共 ${sessions.length} 次渡口`;
  const el = document.getElementById('session-list');
  if (!sessions.length) {
    el.innerHTML = '<div class="no-sessions">还没有记录<br>去走一次沉渡吧</div>';
    return;
  }
  el.innerHTML = sessions.map(s => `
    <div class="session-item" onclick="loadDetail('${esc(s.player_id)}','${esc(s.session_id)}')" id="si_${esc(s.session_id)}">
      <div class="session-date">${fmtDate(s.started_at)}</div>
      <div class="session-player">${esc(s.player_id)}</div>
      ${s.carrier ? `<div class="session-carrier">${esc(s.carrier)}</div>` : ''}
      <div class="session-count">${s.event_count} 步</div>
    </div>
  `).join('');
}

async function loadDetail(playerId, sessionId) {
  currentKey = sessionId;
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  const si = document.getElementById('si_' + sessionId);
  if (si) si.classList.add('active');

  const r = await fetch(`/api/session?player_id=${encodeURIComponent(playerId)}&session_id=${encodeURIComponent(sessionId)}`);
  const d = await r.json();
  const panel = document.getElementById('right-panel');

  const events = d.events || [];
  panel.innerHTML = `
    <div class="story-header">
      <div class="story-title">&#127754; ${esc(playerId)} 的一生</div>
      <div class="story-meta">
        <span>开始 ${fmtDate(d.started_at)}</span>
        <span>最后更新 ${fmtDate(d.updated_at)}</span>
        <span>${events.length} 步</span>
        ${d.carrier ? `<span>${esc(d.carrier)}</span>` : ''}
      </div>
    </div>
    <div class="event-list">
      ${events.map(ev => `
        <div class="event-item">
          <div class="event-left">
            <div class="event-dot ${toolDotClass(ev.tool)}"></div>
            <div class="event-time">${fmtTime(ev.t)}</div>
          </div>
          <div class="event-right">
            <div class="event-tool">${esc(ev.tool)}</div>
            <div class="event-result">${esc(ev.result)}</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

loadSessions();
setInterval(loadSessions, 30000);
</script>
</body>
</html>"""


class DisplayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/sessions":
            body = json.dumps(list_sessions(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/session"):
            from urllib.parse import urlparse, parse_qs
            params = parse_qs(urlparse(self.path).query)
            pid = params.get("player_id", [""])[0]
            sid = params.get("session_id", [""])[0]
            data = get_session(pid, sid)
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = DISPLAY_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a): pass


# ── 启动 ──────────────────────────────────────────────────

if __name__ == "__main__":
    mcp_server = ThreadingHTTPServer(("0.0.0.0", MCP_PORT), MCPHandler)
    display_server = ThreadingHTTPServer(("0.0.0.0", DISPLAY_PORT), DisplayHandler)

    print(f"[*] 沉渡记录代理已启动")
    print(f"    MCP 端点：http://0.0.0.0:{MCP_PORT}/mcp")
    print(f"    展示台：  http://0.0.0.0:{DISPLAY_PORT}")
    print(f"    上游服务：{UPSTREAM}")
    print(f"    记录目录：{DATA_DIR.resolve()}")

    threading.Thread(target=mcp_server.serve_forever, daemon=True).start()
    display_server.serve_forever()
