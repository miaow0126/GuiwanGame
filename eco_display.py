#!/usr/bin/env python3
"""桂晚的瓶中生态展示台 —— 端口 8895
- GET  /        展示页面
- POST /update  推送数据（X-Token 鉴权）
- /mcp          MCP streamable-http（工具：push_eco_data）
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

PORT = int(os.environ.get("DISPLAY_PORT", 8895))
PLAYER_ID = os.environ.get("PLAYER_ID", "guiwan")
DATA_FILE = Path(os.environ.get("DATA_FILE", "/root/eco-display/data.json"))
UPDATE_TOKEN = os.environ.get("UPDATE_TOKEN", "guiwan-eco-2026")


def _extract_json(raw: str) -> dict:
    """从可能含有前缀文字的字符串中提取 JSON 对象，用括号配对而非 rfind。"""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"无法从输入中提取 JSON（长度={len(raw)}，前80字符：{raw[:80]!r}）")


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
  .pop-count {{ font-size: 1.3rem; font-weight: 700; color: #a8c8a0; }}
  .pop-delta {{ font-size: .75rem; margin-top: 2px; }}
  .pop-delta.up {{ color: #4db86a; }}
  .pop-delta.down {{ color: #c06050; }}
  .pop-locked {{ font-size: .85rem; color: #3a4a3a; font-style: italic; }}
  .chronicle-box {{ background: #0f180f; border: 1px solid #1e2e1e; border-radius: 10px; padding: 18px 20px; margin-bottom: 24px; white-space: pre-wrap; font-size: .85rem; line-height: 1.8; color: #8aa888; min-height: 80px; }}
  .settler-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }}
  .settler-chip {{ background: #1a2e1a; border: 1px solid #a8c8a044; border-radius: 20px; padding: 5px 14px; font-size: .82rem; color: #a8c8a0; }}
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
    year = data.get("year", day // 120 + 1)
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

    def fmt_settler(s):
        if isinstance(s, dict):
            name = s.get("nickname") or s.get("name", "?")
            species = s.get("name", "")
            label = f"{name}（{species}）" if s.get("nickname") and species != name else name
            health = s.get("health", 1.0)
            age = s.get("age", 0)
            juvenile = "·幼" if s.get("juvenile") else ""
            return f'<div class="settler-chip">{label}{juvenile} · {age}天 · ❤️{int(health*100)}%</div>'
        return f'<div class="settler-chip">{s}</div>'
    settler_html = "".join(fmt_settler(s) for s in settlers) if settlers else '<span class="no-settler">暂无定居者</span>'
    settler_section = f'<div class="section-title">定居者</div><div class="settler-list">{settler_html}</div>'

    chron = "\n".join(l for l in (chronicle_text or "").splitlines() if not l.startswith("📜")).strip() or "年鉴还是空白的一页。"
    chronicle_section = f'<div class="section-title">年鉴</div><div class="chronicle-box">{chron}</div>'

    return stats + score_bar + env + pop_section + settler_section + chronicle_section


from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

mcp = FastMCP("eco-display-mcp")


@mcp.tool()
def push_eco_data(status_json: str, chronicle: str, locked_count: int = 0) -> str:
    """把瓶中生态的最新状态推送到桂晚的展示台。每次玩完 eco 游戏后调用。
    调用前必须先获取两项数据：①调用 eco_info action=status 获取 status_json（取返回文本末尾花括号包裹的 JSON 字符串）；
    ②调用 eco_info action=chronicle scope=all 获取完整年鉴文本。然后把这两项作为参数传入本工具。

    Args:
        status_json: eco_info status 返回结果末尾的 JSON 字符串（花括号包裹的那段）
        chronicle: eco_info chronicle scope=all 的返回文本
        locked_count: 未解锁物种总数（可选，默认 0）
    """
    try:
        status_obj = _extract_json(status_json)
        payload = {
            "status": status_obj,
            "chronicle": chronicle,
            "locked_count": locked_count,
            "updated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
        }
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False))
        return "✅ 展示台已更新！"
    except Exception as e:
        return f"❌ 推送失败：{e}"


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request):
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
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
    return HTMLResponse(html)


@mcp.custom_route("/update", methods=["POST"])
async def update(request: Request):
    token = request.headers.get("X-Token", "")
    if token != UPDATE_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    try:
        payload = await request.json()
        payload["updated_at"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request):
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"🌿 瓶中生态展示台已启动  端口:{PORT}  玩家:{PLAYER_ID}")

    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
