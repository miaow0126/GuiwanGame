#!/usr/bin/env python3
"""桂晚的瓶中生态展示台 —— 端口 8895"""

import os, json, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("DISPLAY_PORT", 8895))
PLAYER_ID = os.environ.get("PLAYER_ID", "guiwan")
UPSTREAM = os.environ.get("UPSTREAM", "https://toy.cedarstar.org")

_mcp_session_id = None

def call_cedarstar(method, params=None):
    global _mcp_session_id
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": method,
        "params": params or {}
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _mcp_session_id:
        headers["Mcp-Session-Id"] = _mcp_session_id

    req = urllib.request.Request(f"{UPSTREAM}/mcp", data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            sid = r.getheader("Mcp-Session-Id")
            if sid:
                _mcp_session_id = sid
            raw = r.read().decode()
            # SSE 格式剥离
            if raw.startswith("data:"):
                lines = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
                raw = lines[-1] if lines else raw
            return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}

def ensure_initialized():
    global _mcp_session_id
    if not _mcp_session_id:
        call_cedarstar("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "eco-display", "version": "1.0"}
        })

def eco_info(action, scope=None):
    ensure_initialized()
    args = {"game": "eco", "action": "eco_info",
            "params": {"player_id": PLAYER_ID, "action": action}}
    if scope:
        args["params"]["scope"] = scope
    resp = call_cedarstar("tools/call", {"name": "play", "arguments": args})
    try:
        return resp["result"]["content"][0]["text"]
    except Exception:
        return str(resp)

def get_status():
    text = eco_info("status")
    # 提取末尾 JSON
    try:
        start = text.rfind("{")
        end = text.rfind("}") + 1
        if start != -1:
            return json.loads(text[start:end]), text[:start].strip()
    except Exception:
        pass
    return None, text

def get_chronicle():
    return eco_info("chronicle", scope="recent")

def get_folio():
    return eco_info("folio")

SEASON_CONFIG = {
    "春": {"emoji": "🌸", "color": "#a8d8a8", "bg": "#1a2e1a"},
    "夏": {"emoji": "🌿", "color": "#4db88a", "bg": "#0d2318"},
    "秋": {"emoji": "🍂", "color": "#d4a054", "bg": "#2a1a0d"},
    "冬": {"emoji": "❄️",  "color": "#89b4cc", "bg": "#0d1a26"},
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桂晚的瓶中生态</title>
<style>
  :root {{
    --accent: {accent};
    --bg: {bg};
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0a0f0a;
    color: #c8d8c0;
    font-family: 'PingFang SC', 'Noto Sans SC', sans-serif;
    min-height: 100vh;
  }}
  header {{
    background: linear-gradient(135deg, {bg} 0%, #0a0f0a 100%);
    border-bottom: 1px solid {accent}44;
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .title {{ font-size: 1.4rem; font-weight: 600; color: {accent}; letter-spacing: .05em; }}
  .subtitle {{ font-size: .85rem; color: #688060; margin-top: 4px; }}
  .refresh-time {{ font-size: .8rem; color: #506048; }}
  .main {{ padding: 24px 32px; max-width: 1100px; margin: 0 auto; }}

  /* 顶部状态卡 */
  .stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }}
  .stat-card {{
    background: #0f180f;
    border: 1px solid #2a3a2a;
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .stat-label {{ font-size: .72rem; color: #506048; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; color: {accent}; }}
  .stat-sub {{ font-size: .78rem; color: #688060; margin-top: 3px; }}

  /* 评分条 */
  .score-bar-wrap {{ margin-bottom: 24px; }}
  .score-bar-label {{ display: flex; justify-content: space-between; font-size: .8rem; color: #506048; margin-bottom: 6px; }}
  .score-bar-bg {{ background: #1a2a1a; border-radius: 6px; height: 10px; overflow: hidden; }}
  .score-bar-fill {{ height: 100%; border-radius: 6px; background: linear-gradient(90deg, #2a6a2a, {accent}); transition: width .5s; }}

  /* 环境参数 */
  .env-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }}
  .env-card {{
    background: #0f180f;
    border: 1px solid #1e2e1e;
    border-radius: 8px;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .env-name {{ font-size: .8rem; color: #688060; }}
  .env-val {{ font-size: 1rem; font-weight: 600; color: #a8c8a0; }}

  /* 种群 */
  .section-title {{
    font-size: .75rem;
    color: #506048;
    text-transform: uppercase;
    letter-spacing: .1em;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2e1e;
  }}
  .pop-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-bottom: 24px; }}
  .pop-card {{
    background: #0f180f;
    border: 1px solid #1e2e1e;
    border-radius: 8px;
    padding: 12px 14px;
  }}
  .pop-name {{ font-size: .85rem; color: #a8c8a0; margin-bottom: 4px; }}
  .pop-count {{ font-size: 1.3rem; font-weight: 700; color: {accent}; }}
  .pop-delta {{ font-size: .75rem; margin-top: 2px; }}
  .pop-delta.up {{ color: #4db86a; }}
  .pop-delta.down {{ color: #c06050; }}
  .pop-locked {{ font-size: .85rem; color: #3a4a3a; font-style: italic; }}

  /* 年鉴 */
  .chronicle-box {{
    background: #0f180f;
    border: 1px solid #1e2e1e;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 24px;
    white-space: pre-wrap;
    font-size: .85rem;
    line-height: 1.8;
    color: #8aa888;
    min-height: 80px;
  }}

  /* 定居者 */
  .settler-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }}
  .settler-chip {{
    background: #1a2e1a;
    border: 1px solid {accent}44;
    border-radius: 20px;
    padding: 5px 14px;
    font-size: .82rem;
    color: {accent};
  }}
  .no-settler {{ color: #3a4a3a; font-size: .85rem; }}

  .loading {{ text-align: center; padding: 60px; color: #3a4a3a; font-size: 1rem; }}
  .error {{ color: #c06050; background: #1a0f0f; border: 1px solid #4a2020; border-radius: 8px; padding: 14px; }}
</style>
</head>
<body>
<header>
  <div>
    <div class="title">{season_emoji} 桂晚的瓶中生态</div>
    <div class="subtitle">player: {player_id}</div>
  </div>
  <div class="refresh-time">上次刷新 {refresh_time}</div>
</header>
<div class="main">
  {body}
</div>
<script>
  setTimeout(() => location.reload(), 5 * 60 * 1000);
</script>
</body>
</html>"""

def build_body(data, raw_text, chronicle_text, folio_text):
    if data is None:
        return f'<div class="error">获取数据失败<br><pre>{raw_text}</pre></div>'

    season = data.get("season", "春")
    cfg = SEASON_CONFIG.get(season, SEASON_CONFIG["春"])
    day = data.get("day", 0)
    year = data.get("year", 1) if "year" in data else (day // 365 + 1)
    score = data.get("pond_score", 0)
    pop = data.get("pop", {})
    delta = data.get("delta", {})
    settlers = data.get("settlers", [])
    unlocked = data.get("unlocked", [])

    # 顶部4格
    stats = f"""<div class="stats-row">
  <div class="stat-card">
    <div class="stat-label">季节</div>
    <div class="stat-value">{cfg['emoji']} {season}</div>
    <div class="stat-sub">第 {year} 年</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">天数</div>
    <div class="stat-value">{day}</div>
    <div class="stat-sub">第 {day} 天</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">池塘评分</div>
    <div class="stat-value">{score}</div>
    <div class="stat-sub">/100</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">已解锁物种</div>
    <div class="stat-value">{len(unlocked)}</div>
    <div class="stat-sub">种</div>
  </div>
</div>"""

    # 评分条
    score_bar = f"""<div class="score-bar-wrap">
  <div class="score-bar-label"><span>池塘健康度</span><span>{score}/100</span></div>
  <div class="score-bar-bg"><div class="score-bar-fill" style="width:{score}%"></div></div>
</div>"""

    # 环境参数
    temp = data.get("temp", 0)
    do_ = data.get("DO", 0)
    light = data.get("light", 0)
    nutrients = data.get("nutrients", 0)
    detritus = data.get("detritus", 0)
    turbidity = data.get("turbidity", 0)
    env = f"""<div class="section-title">环境参数</div>
<div class="env-grid">
  <div class="env-card"><span class="env-name">🌡 水温</span><span class="env-val">{temp:.1f} ℃</span></div>
  <div class="env-card"><span class="env-name">💧 溶氧</span><span class="env-val">{do_:.1f} mg/L</span></div>
  <div class="env-card"><span class="env-name">☀️ 光照</span><span class="env-val">{light:.2f}</span></div>
  <div class="env-card"><span class="env-name">🌿 营养盐</span><span class="env-val">{nutrients:.0f}</span></div>
  <div class="env-card"><span class="env-name">🍂 有机碎屑</span><span class="env-val">{detritus:.0f}</span></div>
  <div class="env-card"><span class="env-name">🌫 浑浊度</span><span class="env-val">{turbidity:.2f}</span></div>
</div>"""

    # 种群
    pop_cards = ""
    for sp, cnt in pop.items():
        d = delta.get(sp, 0)
        delta_html = ""
        if d > 0:
            delta_html = f'<div class="pop-delta up">▲ {d}</div>'
        elif d < 0:
            delta_html = f'<div class="pop-delta down">▼ {abs(d)}</div>'
        pop_cards += f"""<div class="pop-card">
  <div class="pop-name">{sp}</div>
  <div class="pop-count">{cnt}</div>
  {delta_html}
</div>"""

    # 未解锁槽位
    locked_count = 0
    for line in (folio_text or "").splitlines():
        locked_count += line.count("???")
    if locked_count > 0:
        pop_cards += f'<div class="pop-card"><div class="pop-locked">??? ×{locked_count}</div><div class="pop-count" style="color:#3a4a3a">—</div></div>'

    pop_section = f'<div class="section-title">种群</div><div class="pop-grid">{pop_cards}</div>'

    # 定居者
    if settlers:
        settler_html = "".join(f'<div class="settler-chip">{s}</div>' for s in settlers)
    else:
        settler_html = '<span class="no-settler">暂无定居者</span>'
    settler_section = f'<div class="section-title">定居者</div><div class="settler-list">{settler_html}</div>'

    # 年鉴
    chron = chronicle_text.strip() if chronicle_text else "年鉴还是空白的一页。"
    # 去掉表情开头的标题行
    chron_lines = [l for l in chron.splitlines() if not l.startswith("📜")]
    chron = "\n".join(chron_lines).strip()
    chronicle_section = f'<div class="section-title">年鉴</div><div class="chronicle-box">{chron}</div>'

    return stats + score_bar + env + pop_section + settler_section + chronicle_section


class DisplayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True})
            return
        if self.path not in ("/", "/index.html"):
            self.send_response(404); self.end_headers(); return

        from datetime import datetime, timezone
        now = datetime.now().strftime("%H:%M:%S")

        try:
            data, raw = get_status()
            chron = get_chronicle()
            folio = get_folio()
        except Exception as e:
            data, raw, chron, folio = None, str(e), "", ""

        season = (data or {}).get("season", "春")
        cfg = SEASON_CONFIG.get(season, SEASON_CONFIG["春"])

        body = build_body(data, raw, chron, folio)
        html = HTML_TEMPLATE.format(
            accent=cfg["color"],
            bg=cfg["bg"],
            season_emoji=cfg["emoji"],
            player_id=PLAYER_ID,
            refresh_time=now,
            body=body,
        )
        self._html(html)

    def _html(self, content):
        b = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"🌿 瓶中生态展示台已启动")
    print(f"    端口：{PORT}")
    print(f"    玩家：{PLAYER_ID}")
    print(f"    地址：http://0.0.0.0:{PORT}/")
    ThreadingHTTPServer(("0.0.0.0", PORT), DisplayHandler).serve_forever()
