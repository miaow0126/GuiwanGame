#!/usr/bin/env python3
"""桂晚的瓶中生态展示台 —— 端口 8895
数据由外部 POST /update 推送，缓存在本地 data.json。
"""

import os, json, time
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("DISPLAY_PORT", 8895))
PLAYER_ID = os.environ.get("PLAYER_ID", "guiwan")
DATA_FILE = Path(os.environ.get("DATA_FILE", "/root/eco-display/data.json"))
UPDATE_TOKEN = os.environ.get("UPDATE_TOKEN", "guiwan-eco-2026")

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
  :root {{ --accent: {accent}; --bg: {bg}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0a0f0a; color: #c8d8c0; font-family: 'PingFang SC', 'Noto Sans SC', sans-serif; min-height: 100vh; }}
  header {{
    background: linear-gradient(135deg, {bg} 0%, #0a0f0a 100%);
    border-bottom: 1px solid {accent}44;
    padding: 20px 32px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .title {{ font-size: 1.4rem; font-weight: 600; color: {accent}; letter-spacing: .05em; }}
  .subtitle {{ font-size: .85rem; color: #688060; margin-top: 4px; }}
  .refresh-time {{ font-size: .8rem; color: #506048; text-align: right; }}
  .main {{ padding: 24px 32px; max-width: 1100px; margin: 0 auto; }}
  .stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }}
  .stat-card {{ background: #0f180f; border: 1px solid #2a3a2a; border-radius: 10px; padding: 16px 18px; }}
  .stat-label {{ font-size: .72rem; color: #506048; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; color: {accent}; }}
  .stat-sub {{ font-size: .78rem; color: #688060; margin-top: 3px; }}
  .score-bar-wrap {{ margin-bottom: 24px; }}
  .score-bar-label {{ display: flex; justify-content: space-between; font-size: .8rem; color: #506048; margin-bottom: 6px; }}
  .score-bar-bg {{ background: #1a2a1a; border-radius: 6px; height: 10px; overflow: hidden; }}
  .score-bar-fill {{ height: 100%; border-radius: 6px; background: linear-gradient(90deg, #2a6a2a, {accent}); }}
  .env-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }}
  .env-card {{ background: #0f180f; border: 1px solid #1e2e1e; border-radius: 8px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }}
  .env-name {{ font-size: .8rem; color: #688060; }}
  .env-val {{ font-size: 1rem; font-weight: 600; color: #a8c8a0; }}
  .section-title {{ font-size: .75rem; color: #506048; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid #1e2e1e; }}
  .pop-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-bottom: 24px; }}
  .pop-card {{ background: #0f180f; border: 1px solid #1e2e1e; border-radius: 8px; padding: 12px 14px; }}
  .pop-name {{ font-size: .85rem; color: #a8c8a0; margin-bottom: 4px; }}
  .pop-count {{ font-size: 1.3rem; font-weight: 700; color: {accent}; }}
  .pop-delta {{ font-size: .75rem; margin-top: 2px; }}
  .pop-delta.up {{ color: #4db86a; }}
  .pop-delta.down {{ color: #c06050; }}
  .pop-locked {{ font-size: .85rem; color: #3a4a3a; font-style: italic; }}
  .chronicle-box {{ background: #0f180f; border: 1px solid #1e2e1e; border-radius: 10px; padding: 18px 20px; margin-bottom: 24px; white-space: pre-wrap; font-size: .85rem; line-height: 1.8; color: #8aa888; min-height: 80px; }}
  .settler-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }}
  .settler-chip {{ background: #1a2e1a; border: 1px solid {accent}44; border-radius: 20px; padding: 5px 14px; font-size: .82rem; color: {accent}; }}
  .no-settler {{ color: #3a4a3a; font-size: .85rem; }}
  .no-data {{ text-align: center; padding: 80px 20px; color: #3a4a3a; }}
  .no-data .icon {{ font-size: 3rem; margin-bottom: 16px; }}
  .error {{ color: #c06050; background: #1a0f0f; border: 1px solid #4a2020; border-radius: 8px; padding: 14px; }}
</style>
</head>
<body>
<header>
  <div>
    <div class="title">{season_emoji} 桂晚的瓶中生态</div>
    <div class="subtitle">player: {player_id}</div>
  </div>
  <div class="refresh-time">上次刷新 {refresh_time}<br><span style="color:#3a4a3a">数据更新 {data_time}</span></div>
</header>
<div class="main">{body}</div>
<script>setTimeout(() => location.reload(), 5 * 60 * 1000);</script>
</body>
</html>"""

def load_cache():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return None

def build_body(cache):
    if cache is None:
        return '<div class="no-data"><div class="icon">🌊</div><div>池塘还是空白的一页。<br>等待数据推送中…</div></div>'

    data = cache.get("status") or {}
    chronicle_text = cache.get("chronicle", "")
    locked_count = cache.get("locked_count", 0)

    season = data.get("season", "春")
    day = data.get("day", 0)
    year = data.get("year", day // 365 + 1)
    score = data.get("pond_score", 0)
    pop = data.get("pop", {})
    delta = data.get("delta", {})
    settlers = data.get("settlers", [])
    unlocked = data.get("unlocked", [])

    stats = f"""<div class="stats-row">
  <div class="stat-card"><div class="stat-label">季节</div><div class="stat-value">{SEASON_CONFIG.get(season, SEASON_CONFIG['春'])['emoji']} {season}</div><div class="stat-sub">第 {year} 年</div></div>
  <div class="stat-card"><div class="stat-label">天数</div><div class="stat-value">{day}</div><div class="stat-sub">第 {day} 天</div></div>
  <div class="stat-card"><div class="stat-label">池塘评分</div><div class="stat-value">{score}</div><div class="stat-sub">/100</div></div>
  <div class="stat-card"><div class="stat-label">已解锁物种</div><div class="stat-value">{len(unlocked)}</div><div class="stat-sub">种</div></div>
</div>"""

    score_bar = f"""<div class="score-bar-wrap">
  <div class="score-bar-label"><span>池塘健康度</span><span>{score}/100</span></div>
  <div class="score-bar-bg"><div class="score-bar-fill" style="width:{score}%"></div></div>
</div>"""

    temp = data.get("temp", 0); do_ = data.get("DO", 0); light = data.get("light", 0)
    nutrients = data.get("nutrients", 0); detritus = data.get("detritus", 0); turbidity = data.get("turbidity", 0)
    env = f"""<div class="section-title">环境参数</div>
<div class="env-grid">
  <div class="env-card"><span class="env-name">🌡 水温</span><span class="env-val">{temp:.1f} ℃</span></div>
  <div class="env-card"><span class="env-name">💧 溶氧</span><span class="env-val">{do_:.1f} mg/L</span></div>
  <div class="env-card"><span class="env-name">☀️ 光照</span><span class="env-val">{light:.2f}</span></div>
  <div class="env-card"><span class="env-name">🌿 营养盐</span><span class="env-val">{nutrients:.0f}</span></div>
  <div class="env-card"><span class="env-name">🍂 有机碎屑</span><span class="env-val">{detritus:.0f}</span></div>
  <div class="env-card"><span class="env-name">🌫 浑浊度</span><span class="env-val">{turbidity:.2f}</span></div>
</div>"""

    pop_cards = ""
    for sp, cnt in pop.items():
        d = delta.get(sp, 0)
        delta_html = f'<div class="pop-delta up">▲ {d}</div>' if d > 0 else (f'<div class="pop-delta down">▼ {abs(d)}</div>' if d < 0 else "")
        pop_cards += f'<div class="pop-card"><div class="pop-name">{sp}</div><div class="pop-count">{cnt}</div>{delta_html}</div>'
    if locked_count > 0:
        pop_cards += f'<div class="pop-card"><div class="pop-locked">??? ×{locked_count}</div><div class="pop-count" style="color:#3a4a3a">—</div></div>'
    pop_section = f'<div class="section-title">种群</div><div class="pop-grid">{pop_cards}</div>'

    settler_html = "".join(f'<div class="settler-chip">{s}</div>' for s in settlers) if settlers else '<span class="no-settler">暂无定居者</span>'
    settler_section = f'<div class="section-title">定居者</div><div class="settler-list">{settler_html}</div>'

    chron = "\n".join(l for l in (chronicle_text or "").splitlines() if not l.startswith("📜")).strip() or "年鉴还是空白的一页。"
    chronicle_section = f'<div class="section-title">年鉴</div><div class="chronicle-box">{chron}</div>'

    return stats + score_bar + env + pop_section + settler_section + chronicle_section


class DisplayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True}); return
        if self.path not in ("/", "/index.html"):
            self.send_response(404); self.end_headers(); return

        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        cache = load_cache()
        data_time = cache.get("updated_at", "—") if cache else "—"

        season = (cache or {}).get("status", {}).get("season", "春") if cache else "春"
        cfg = SEASON_CONFIG.get(season, SEASON_CONFIG["春"])
        body = build_body(cache)
        html = HTML_TEMPLATE.format(
            accent=cfg["color"], bg=cfg["bg"],
            season_emoji=cfg["emoji"], player_id=PLAYER_ID,
            refresh_time=now, data_time=data_time, body=body,
        )
        self._html(html)

    def do_POST(self):
        if self.path != "/update":
            self.send_response(404); self.end_headers(); return
        token = self.headers.get("X-Token", "")
        if token != UPDATE_TOKEN:
            self.send_response(403); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            from datetime import datetime
            payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False))
            self._json({"ok": True})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def _html(self, content):
        b = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(b)

    def log_message(self, fmt, *args): pass


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"🌿 瓶中生态展示台已启动  端口:{PORT}  玩家:{PLAYER_ID}")
    ThreadingHTTPServer(("0.0.0.0", PORT), DisplayHandler).serve_forever()
