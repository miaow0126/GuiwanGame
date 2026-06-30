#!/usr/bin/env python3
"""桂晚的赌场展示台
- GET  /        展示页面
- GET  /health  健康检查
- POST /update  推送数据（X-Token 鉴权）
"""

import os, json
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

PORT        = int(os.environ.get("DISPLAY_PORT", 8896))
DATA_FILE   = Path(os.environ.get("DATA_FILE", "/root/arcade-display/data.json"))
UPDATE_TOKEN = os.environ.get("UPDATE_TOKEN", "guiwan-arcade-2026")

HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桂晚的赌场</title>
<style>
:root { --accent: #f0a040; --bg: #1a0f00; --surface: #120a00; --card: #1e1200; --border: #3a2010; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0a0800; color: #d8c8a0; font-family: 'PingFang SC','Noto Sans SC',sans-serif; min-height: 100vh; }
header {
  background: linear-gradient(135deg, #2a1500 0%, #0a0800 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
  display: flex; align-items: center; justify-content: space-between;
}
.title { font-size: 1.4rem; font-weight: 700; color: var(--accent); letter-spacing: .05em; }
.subtitle { font-size: .85rem; color: #806040; margin-top: 4px; }
.refresh-time { font-size: .8rem; color: #604830; text-align: right; }
.main { padding: 24px 32px; max-width: 1000px; margin: 0 auto; }

.stats-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 24px; }
.stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.stat-label { font-size: .72rem; color: #806040; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }
.stat-value { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
.stat-sub { font-size: .78rem; color: #a08060; margin-top: 3px; }

.section-title { font-size: .75rem; color: #806040; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }

.games-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; margin-bottom: 24px; }
.game-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.game-name { font-size: 1rem; font-weight: 600; margin-bottom: 10px; color: var(--accent); }
.game-stat { display: flex; justify-content: space-between; font-size: .82rem; padding: 3px 0; color: #a08060; }
.game-stat span:last-child { color: #d8c8a0; }

.prizes-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
.prize-chip { background: #2a1a00; border: 1px solid #f0a04044; border-radius: 20px; padding: 5px 14px; font-size: .82rem; color: var(--accent); }
.no-prize { color: #604830; font-size: .85rem; }

.log-box { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; white-space: pre-wrap; font-size: .85rem; line-height: 1.8; color: #a08060; min-height: 60px; margin-bottom: 24px; }
.no-data { text-align: center; padding: 80px 20px; color: #604830; }
.no-data .icon { font-size: 3rem; margin-bottom: 16px; }
</style>
</head>
<body>
<header>
  <div>
    <div class="title">🎰 桂晚的赌场</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="refresh-time">上次刷新 {refresh_time}<br><span style="color:#3a2510">数据更新 {data_time}</span></div>
</header>
<div class="main">{body}</div>
<script>setTimeout(() => location.reload(), 5 * 60 * 1000);</script>
</body>
</html>"""


def load_cache():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def build_body(cache):
    if cache is None:
        return '<div class="no-data"><div class="icon">🎰</div><div>赌场还没开张。<br>等待数据推送中…</div></div>'

    arc  = cache.get("arcade", {})
    slots = cache.get("slots", {})
    log  = cache.get("log", "")

    chips    = arc.get("chips", 0)
    winnings = arc.get("winnings", 0)
    visits   = arc.get("visits", 0)
    total_bought = arc.get("total_bought", 0)
    total_cashed = arc.get("total_cashed", 0)
    net = total_cashed - total_bought

    stats = f"""<div class="stats-row">
  <div class="stat-card"><div class="stat-label">当前筹码</div><div class="stat-value">🪙 {chips}</div><div class="stat-sub">可用余额</div></div>
  <div class="stat-card"><div class="stat-label">累计赢利</div><div class="stat-value">💰 {winnings}</div><div class="stat-sub">用于兑奖</div></div>
  <div class="stat-card"><div class="stat-label">净盈亏</div><div class="stat-value" style="color:{'#4db86a' if net>=0 else '#c06050'}">{'+' if net>=0 else ''}{net}</div><div class="stat-sub">提现-投入</div></div>
  <div class="stat-card"><div class="stat-label">到访次数</div><div class="stat-value">🎪 {visits}</div><div class="stat-sub">次</div></div>
</div>"""

    s_spins   = slots.get("spins", 0)
    s_wagered = slots.get("wagered", 0)
    s_won     = slots.get("won", 0)
    s_net     = s_won - s_wagered
    s_biggest = slots.get("biggest", 0)
    s_jackpots = slots.get("jackpots", 0)

    games = f"""<div class="section-title">游戏战绩</div>
<div class="games-grid">
  <div class="game-card">
    <div class="game-name">🎰 老虎机</div>
    <div class="game-stat"><span>拉杆次数</span><span>{s_spins}</span></div>
    <div class="game-stat"><span>总下注</span><span>{s_wagered}</span></div>
    <div class="game-stat"><span>总赢取</span><span>{s_won}</span></div>
    <div class="game-stat"><span>净盈亏</span><span style="color:{'#4db86a' if s_net>=0 else '#c06050'}">{'+' if s_net>=0 else ''}{s_net}</span></div>
    <div class="game-stat"><span>最大单次</span><span>{s_biggest}</span></div>
    <div class="game-stat"><span>JACKPOT</span><span>🎊 {s_jackpots}次</span></div>
  </div>
  <div class="game-card">
    <div class="game-name">🃏 二十一点</div>
    <div class="game-stat"><span>数据</span><span>推进中…</span></div>
  </div>
  <div class="game-card">
    <div class="game-name">🎡 轮盘</div>
    <div class="game-stat"><span>数据</span><span>推进中…</span></div>
  </div>
</div>"""

    owned  = arc.get("owned", [])
    gifts  = arc.get("gifts", [])
    decor  = arc.get("decor", [])
    all_prizes = owned + gifts + decor
    if all_prizes:
        prize_html = "".join(f'<div class="prize-chip">{p}</div>' for p in all_prizes)
    else:
        prize_html = '<span class="no-prize">还没有奖品</span>'
    prizes = f'<div class="section-title">已获奖品</div><div class="prizes-wrap">{prize_html}</div>'

    log_section = f'<div class="section-title">最近记录</div><div class="log-box">{log or "暂无记录"}</div>'

    return stats + games + prizes + log_section


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True}); return
        if self.path not in ("/", "/index.html"):
            self.send_response(404); self.end_headers(); return

        now = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
        cache = load_cache()
        data_time = cache.get("updated_at", "—") if cache else "—"
        subtitle = f"player: {cache.get('player','guiwan')}" if cache else "等待开张…"

        html = HTML.format(
            subtitle=subtitle,
            refresh_time=now,
            data_time=data_time,
            body=build_body(cache),
        )
        b = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        if self.path != "/update":
            self.send_response(404); self.end_headers(); return
        if self.headers.get("X-Token", "") != UPDATE_TOKEN:
            self.send_response(403); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            payload["updated_at"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
            DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self._json({"ok": True})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(b)

    def log_message(self, *a): pass


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"🎰 赌场展示台已启动  端口:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
