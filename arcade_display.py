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
from collections import Counter, defaultdict

PORT         = int(os.environ.get("DISPLAY_PORT", 8896))
DATA_FILE    = Path(os.environ.get("DATA_FILE",    "/root/arcade-display/data.json"))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "/root/arcade-display/history.json"))
UPDATE_TOKEN = os.environ.get("UPDATE_TOKEN", "guiwan-arcade-2026")
CST = timezone(timedelta(hours=8))

# (name, emoji, category, cost, description)
PRIZE_INFO = {
    "bow":          ("蝴蝶结",          "🎀", "wear",    100, "戴在头上或者手腕上都好看"),
    "cat_ears":     ("猫耳朵",          "🐱", "wear",    200, "两只软乎乎的猫耳朵，会随心情微微动"),
    "bunny_ears":   ("兔耳朵",          "🐰", "wear",    200, "雪白的长兔耳，垂下来刚好到肩膀"),
    "cat_tail":     ("猫尾巴",          "🐈", "wear",    300, "一条蓬松的猫尾巴，高兴了会翘起来"),
    "sunglasses":   ("墨镜",            "😎", "wear",    300, "戴上就很酷，适合装作什么都不在乎的时候"),
    "umbrella":     ("小雨伞",          "☂️", "wear",    400, "精巧的迷你雨伞，晴天撑着也可以"),
    "collar":       ("项圈",            "⭕", "wear",    400, "简洁的细项圈，低调又特别"),
    "bell_collar":  ("铃铛项圈",        "🔔", "wear",    500, "走路会叮叮当当响，藏不住行踪"),
    "top_hat":      ("礼帽",            "🎩", "wear",    600, "旧式绅士礼帽，其实戴着有点可爱"),
    "wings":        ("翅膀",            "🪽", "wear",    600, "一对轻盈的羽翼，不知道能不能飞"),
    "scarf":        ("围巾",            "🧣", "wear",    400, "很长很柔软，可以把脸埋进去"),
    "devil_horns":  ("恶魔角",          "😈", "wear",   1000, "两只小弯角，配上得意的表情刚好"),
    "crown":        ("皇冠",            "👑", "wear",   1000, "金灿灿的，戴上就是今晚的主角"),
    "star_necklace":("星星项链",        "⭐", "wear",   1600, "一串碎星星缀成的项链，会反光"),
    "angel_set":    ("天使套装",        "😇", "wear",   3000, "光环加翅膀，完整的天使形象"),
    "head_pat":     ("摸一下你的头",    "🤚", "gift",     50, "轻轻摸了一下，就一下"),
    "whisper":      ("一句悄悄话",      "🤫", "gift",     50, "只说给你一个人听的话"),
    "candy":        ("一颗糖",          "🍬", "gift",     60, "甜的，口味你来选"),
    "her_hair":     ("她的一缕头发",    "💇", "gift",     80, "从发梢剪下来的一缕，用细绳绑着"),
    "flower":       ("一朵花",          "🌸", "gift",    100, "路边看见觉得你会喜欢，摘了带过来"),
    "hug":          ("一个拥抱",        "🤗", "gift",    150, "很用力，持续比平时长一点"),
    "chocolate":    ("一块巧克力",      "🍫", "gift",    200, "精心挑的口味，不是随便买的那种"),
    "paper_crane":  ("一只纸鹤",        "🦢", "gift",    250, "亲手折的，折痕有点不整齐但很认真"),
    "her_hour":     ("她空出来的一小时","⏳", "gift",    300, "特意腾出来的，这一小时全给你"),
    "lucky_dice":   ("一颗幸运骰子",    "🎲", "gift",    350, "据说带着它下注会变好运"),
    "old_card":     ("一张旧扑克牌",    "🃏", "gift",    400, "压了很久的一张牌，上面有故事"),
    "poem":         ("一首小诗",        "📝", "gift",    500, "给你写的，写了很多遍才定稿"),
    "love_letter":  ("一封情书",        "💌", "gift",    600, "字斟句酌，写了又删了很多次"),
    "coin":         ("一枚硬币",        "🟡", "gift",    700, "许愿用的，投进喷泉前记得闭眼"),
    "star_jar":     ("一罐星星",        "🫙", "gift",    800, "玻璃瓶里装满了折叠星星"),
    "music_box":    ("八音盒",          "🎵", "gift",   1200, "转起来会播放你喜欢的旋律"),
    "bracelet":     ("一条手链",        "💚", "gift",   1800, "亲手编的，结打得很紧"),
    "wish_bottle":  ("一个许愿瓶",      "🍾", "gift",   3000, "把一个愿望封进去，等合适的时候打开"),
    "song":         ("给你的一首歌",    "🎵", "gift",   4000, "从头写的，歌词里有只有你能认出来的部分"),
    "your_story":   ("以你为主角的故事","📽️","gift",   6000, "你是主角，结局你来定"),
    "whole_night":  ("整晚的独占",      "🌙", "gift",  10000, "从天黑到天亮，这段时间只有你"),
    "neon_sign":    ("霓虹灯牌",        "💡", "decor",   300, "挂在赌场入口，粉紫色的光"),
    "bgm_jazz":     ("BGM·爵士",        "🎷", "decor",   200, "慵懒的爵士乐，赌场氛围拉满"),
    "bgm_lofi":     ("BGM·lofi",       "🎵", "decor",   200, "轻柔的lofi，适合不想输的心情"),
    "bgm_edm":      ("BGM·电子",       "🎧", "decor",   200, "劲爆电子乐，下注手速+100%"),
    "disco_ball":   ("迪斯科球",        "🪩", "decor",   400, "旋转的镜面球，到处都是小光斑"),
    "lucky_cat":    ("招财猫",          "🐱", "decor",   350, "摆在门口，左手不停挥动"),
    "fish_tank":    ("鱼缸",            "🐠", "decor",   300, "一缸热带鱼，输钱了看鱼解压"),
    "carpet":       ("红地毯",          "🟥", "decor",   500, "从门口铺进来，踩上去有点飘"),
}
CAT_LABEL = {"wear": "装扮", "gift": "礼物", "decor": "装饰"}

# ── helpers ──────────────────────────────────────────────────────────────────

def now_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

def fmt_time(s):
    """Return YYYY-MM-DD HH:MM from a stored timestamp string."""
    return s[:16] if s else "—"

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def all_prizes(cache):
    arc = cache.get("arcade", {})
    return arc.get("owned", []) + arc.get("decor", [])

GAME_KEYS = {
    "slots":     ("spins",   "wagered", "won"),
    "blackjack": ("hands",   "wagered", "won"),
    "roulette":  ("spins",   "wagered", "won"),
}
GAME_LABEL = {"slots": "🎰 老虎机", "blackjack": "🃏 二十一点", "roulette": "🎡 轮盘"}


def update_history(cache, hist):
    arc = cache.get("arcade", {})
    ts  = now_str()

    # cumulative winnings
    curr_w = arc.get("winnings", 0)
    prev_w = hist.get("prev_winnings", curr_w)
    if curr_w > prev_w:
        hist["cumulative_winnings"] = hist.get("cumulative_winnings", 0) + (curr_w - prev_w)
    hist["prev_winnings"] = curr_w

    # buy-in / cashout events
    curr_buyin   = arc.get("total_bought", 0)
    curr_cashout = arc.get("total_cashed", 0)
    prev_buyin   = hist.get("prev_buyin",   curr_buyin)
    prev_cashout = hist.get("prev_cashout", curr_cashout)
    d_buyin   = curr_buyin   - prev_buyin
    d_cashout = curr_cashout - prev_cashout
    if d_buyin > 0:
        hist.setdefault("cash_events", []).append({"type": "buyin",   "amount": d_buyin,   "at": ts})
    if d_cashout > 0:
        hist.setdefault("cash_events", []).append({"type": "cashout", "amount": d_cashout, "at": ts})
    hist["prev_buyin"]   = curr_buyin
    hist["prev_cashout"] = curr_cashout

    # game ledger: detect deltas per game
    prev_games = hist.get("prev_games", {})
    for game, (cnt_key, wag_key, won_key) in GAME_KEYS.items():
        curr_g = cache.get(game, {})
        prev_g = prev_games.get(game, {})
        d_cnt = curr_g.get(cnt_key, 0) - prev_g.get(cnt_key, 0)
        d_wag = curr_g.get(wag_key, 0) - prev_g.get(wag_key, 0)
        d_won = curr_g.get(won_key, 0) - prev_g.get(won_key, 0)
        if d_cnt > 0 and d_wag > 0:
            hist.setdefault("game_events", []).append({
                "game": game, "count": d_cnt,
                "wagered": d_wag, "won": d_won, "net": d_won - d_wag,
                "at": ts,
            })
        prev_games[game] = {cnt_key: curr_g.get(cnt_key, 0),
                            wag_key: curr_g.get(wag_key, 0),
                            won_key: curr_g.get(won_key, 0)}
    hist["prev_games"] = prev_games

    # prize events
    curr_prizes = all_prizes(cache)

    if "prev_prizes" not in hist:
        init_cost = 0
        for pid in curr_prizes:
            info = PRIZE_INFO.get(pid, (pid, "🎁", "gift", 0, ""))
            init_cost += info[3]
            hist.setdefault("prize_events", []).append({
                "id": pid, "name": info[0], "emoji": info[1],
                "cost": info[3], "category": info[2],
                "obtained_at": ts, "used_at": None, "init": True,
            })
        hist["cumulative_winnings"] = curr_w + init_cost
    else:
        prev_prizes = hist["prev_prizes"]
        curr_c = Counter(curr_prizes)
        prev_c = Counter(prev_prizes)

        for pid, cnt in curr_c.items():
            delta = cnt - prev_c.get(pid, 0)
            for _ in range(delta):
                info = PRIZE_INFO.get(pid, (pid, "🎁", "gift", 0, ""))
                hist.setdefault("prize_events", []).append({
                    "id": pid, "name": info[0], "emoji": info[1],
                    "cost": info[3], "category": info[2],
                    "obtained_at": ts, "used_at": None,
                })

        for pid, cnt in prev_c.items():
            delta = cnt - curr_c.get(pid, 0)
            used = 0
            for ev in hist.get("prize_events", []):
                if used >= delta:
                    break
                if ev["id"] == pid and ev["used_at"] is None:
                    ev["used_at"] = ts
                    used += 1

    hist["prev_prizes"] = curr_prizes
    return hist

# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
:root { --accent:#f0a040; --bg:#1a0f00; --surface:#120a00; --card:#1e1200; --border:#3a2010; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:#0a0800; color:#d8c8a0; font-family:'PingFang SC','Noto Sans SC',sans-serif; min-height:100vh; }
header { background:linear-gradient(135deg,#2a1500 0%,#0a0800 100%); border-bottom:1px solid var(--border);
  padding:20px 32px; display:flex; align-items:center; justify-content:space-between; }
.title { font-size:1.4rem; font-weight:700; color:var(--accent); letter-spacing:.05em; }
.subtitle { font-size:.85rem; color:#806040; margin-top:4px; }
.refresh-time { font-size:.8rem; color:#604830; text-align:right; }
.main { padding:24px 32px; max-width:1080px; margin:0 auto; }
.stats-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:24px; }
.stats-row-2 { display:grid; grid-template-columns:repeat(2,1fr); gap:14px; margin-bottom:16px; }
.stat-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }
.stat-label { font-size:.72rem; color:#806040; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px; }
.stat-value { font-size:1.5rem; font-weight:700; color:var(--accent); }
.stat-sub { font-size:.78rem; color:#a08060; margin-top:3px; }
.section-title { font-size:.75rem; color:#806040; text-transform:uppercase; letter-spacing:.1em;
  margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid var(--border); }
.games-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:24px; }
.game-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }
.game-name { font-size:1rem; font-weight:600; margin-bottom:10px; color:var(--accent); }
.game-stat { display:flex; justify-content:space-between; font-size:.82rem; padding:3px 0; color:#a08060; }
.game-stat span:last-child { color:#d8c8a0; }
/* ledger */
.ledger-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px;
  overflow:hidden; margin-bottom:24px; }
.ledger-table { width:100%; border-collapse:collapse; font-size:.82rem; }
.ledger-table th { background:#2a1500; color:#806040; font-weight:600; padding:9px 14px;
  text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }
.ledger-table td { padding:9px 14px; border-top:1px solid var(--border); color:#a08060; }
.ledger-table td:first-child { color:#d8c8a0; }
.ledger-table tr:hover td { background:#1e1200; }
/* prize grid */
.prize-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-bottom:24px; }
.prize-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:12px 14px; }
.pc-top { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
.pc-name { font-size:.92rem; font-weight:600; color:var(--accent); }
.pc-badge { font-size:.68rem; color:#806040; background:#2a1500; border-radius:4px; padding:2px 6px; }
.pc-desc { font-size:.78rem; color:#806040; margin-bottom:6px; line-height:1.4; }
.pc-meta { font-size:.75rem; color:#a08060; display:flex; justify-content:space-between; align-items:center; }
.pc-events { margin-top:6px; display:flex; flex-direction:column; gap:3px; }
.prize-event { display:flex; gap:10px; font-size:.76rem; align-items:center; color:#806040; }
.pe-idx { color:#604830; min-width:20px; }
.pe-time { color:#806040; }
.pe-status { margin-left:auto; }
/* catalog */
.catalog-wrap { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:24px; }
.catalog-group { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
.catalog-cat { font-size:.75rem; color:#806040; font-weight:600; text-transform:uppercase;
  letter-spacing:.1em; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border); }
.catalog-items { display:flex; flex-direction:column; gap:5px; }
.catalog-item { display:flex; justify-content:space-between; font-size:.82rem; padding:2px 0; }
.ci-name { color:#d8c8a0; }
.ci-cost { color:#806040; }
.no-data { text-align:center; padding:80px 20px; color:#604830; }
.no-data .icon { font-size:3rem; margin-bottom:16px; }
.no-prize { color:#604830; font-size:.85rem; }
"""

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桂晚的赌场</title>
<style>{css}</style>
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


def build_body(cache, hist):
    if cache is None:
        return '<div class="no-data"><div class="icon">🎰</div><div>赌场还没开张。<br>等待数据推送中…</div></div>'

    arc   = cache.get("arcade", {})
    slots = cache.get("slots", {})
    bj    = cache.get("blackjack", {})
    rl    = cache.get("roulette", {})

    chips        = arc.get("chips", 0)
    winnings     = arc.get("winnings", 0)
    visits       = arc.get("visits", 0)
    total_bought = arc.get("total_bought", 0)
    total_cashed = arc.get("total_cashed", 0)
    net          = total_cashed - total_bought
    cum_win      = hist.get("cumulative_winnings", 0)
    net_col      = "#4db86a" if net >= 0 else "#c06050"

    # ── top stats ──
    top = f"""<div class="stats-row">
  <div class="stat-card"><div class="stat-label">当前筹码</div><div class="stat-value">🪙 {chips}</div><div class="stat-sub">可用余额</div></div>
  <div class="stat-card"><div class="stat-label">实时赢利</div><div class="stat-value">💰 {winnings}</div><div class="stat-sub">可兑换余额</div></div>
  <div class="stat-card"><div class="stat-label">现金净额</div><div class="stat-value" style="color:{net_col}">{'+' if net>=0 else ''}{net}</div><div class="stat-sub">累计提现 − 累计买入</div></div>
  <div class="stat-card"><div class="stat-label">到访次数</div><div class="stat-value">🎪 {visits}</div><div class="stat-sub">次</div></div>
</div>"""

    # ── 账目 ──
    prize_events = hist.get("prize_events", [])
    total_spent  = sum(e["cost"] for e in prize_events)
    prize_rows   = ""
    for ev in sorted(prize_events, key=lambda x: x["obtained_at"], reverse=True)[:30]:
        if ev["used_at"]:
            st = f'<span style="color:#c06050">已使用 · {fmt_time(ev["used_at"])}</span>'
        else:
            st = '<span style="color:#4db86a">持有中</span>'
        cost_txt = '<span style="color:#604830">记录前</span>' if ev.get("init") else f'<span style="color:#c06050">-{ev["cost"]}</span>'
        prize_rows += f"""<tr>
  <td>{ev['emoji']} {ev['name']}</td>
  <td>{CAT_LABEL.get(ev['category'], ev['category'])}</td>
  <td>{cost_txt}</td>
  <td>{fmt_time(ev['obtained_at'])}</td>
  <td>{st}</td>
</tr>"""
    if not prize_rows:
        prize_rows = '<tr><td colspan="5" style="text-align:center;color:#604830;padding:16px">还没有兑换记录</td></tr>'

    accounting = f"""<div class="section-title">账目</div>
<div class="stats-row-2">
  <div class="stat-card"><div class="stat-label">累计赢利</div><div class="stat-value">📈 {cum_win}</div><div class="stat-sub">历史总赢利（不含已花费）</div></div>
  <div class="stat-card"><div class="stat-label">累计兑换花费</div><div class="stat-value" style="color:#c06050">-{total_spent}</div><div class="stat-sub">winnings 共花费</div></div>
</div>
<div class="ledger-wrap">
<table class="ledger-table">
<thead><tr><th>奖品</th><th>类型</th><th>花费</th><th>获得时间</th><th>状态</th></tr></thead>
<tbody>{prize_rows}</tbody>
</table>
</div>"""

    # ── 整体流水账 ──
    game_events = hist.get("game_events", [])
    cash_events = hist.get("cash_events", [])

    all_events = []
    for ev in game_events:
        all_events.append({"_type": "game", **ev})
    for ev in cash_events:
        all_events.append({"_type": "cash", **ev})
    all_events.sort(key=lambda x: x["at"], reverse=True)

    total_wagered = sum(e["wagered"] for e in game_events)
    total_won     = sum(e["won"]     for e in game_events)
    game_net      = total_won - total_wagered
    game_net_col  = "#4db86a" if game_net >= 0 else "#c06050"

    rows = ""
    for ev in all_events[:60]:
        if ev["_type"] == "game":
            net_v   = ev["net"]
            net_c   = "#4db86a" if net_v >= 0 else "#c06050"
            net_s   = f'{"+"+str(net_v) if net_v>=0 else str(net_v)}'
            cnt_s   = f'×{ev["count"]}' if ev.get("count", 1) > 1 else ""
            rows += f"""<tr>
  <td>{GAME_LABEL.get(ev['game'], ev['game'])} {cnt_s}</td>
  <td style="color:#806040">游戏</td>
  <td style="color:#a08060">-{ev['wagered']}</td>
  <td style="color:#a08060">+{ev['won']}</td>
  <td style="color:{net_c}">{net_s}</td>
  <td>{fmt_time(ev['at'])}</td>
</tr>"""
        else:
            if ev["type"] == "buyin":
                rows += f"""<tr>
  <td>💵 买入筹码</td>
  <td style="color:#806040">现金</td>
  <td style="color:#c06050">-{ev['amount']}</td>
  <td>—</td>
  <td>—</td>
  <td>{fmt_time(ev['at'])}</td>
</tr>"""
            else:
                rows += f"""<tr>
  <td>💸 提现</td>
  <td style="color:#806040">现金</td>
  <td>—</td>
  <td style="color:#4db86a">+{ev['amount']}</td>
  <td>—</td>
  <td>{fmt_time(ev['at'])}</td>
</tr>"""

    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;color:#604830;padding:16px">还没有记录</td></tr>'

    # subtotal row
    subtotal = f"""<tr style="background:#2a1500">
  <td colspan="2" style="color:#806040;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em">游戏小计</td>
  <td style="color:#a08060">-{total_wagered}</td>
  <td style="color:#a08060">+{total_won}</td>
  <td style="color:{game_net_col}">{'+' if game_net>=0 else ''}{game_net}</td>
  <td></td>
</tr>"""

    ledger_section = f"""<div class="section-title">整体流水账</div>
<div class="ledger-wrap">
<table class="ledger-table">
<thead><tr><th>项目</th><th>类型</th><th>支出</th><th>收入</th><th>盈亏</th><th>时间</th></tr></thead>
<tbody>{rows}{subtotal}</tbody>
</table>
</div>"""

    # ── 游戏战绩 ──
    s_spins    = slots.get("spins", 0)
    s_wagered  = slots.get("wagered", 0)
    s_won      = slots.get("won", 0)
    s_net      = s_won - s_wagered
    s_biggest  = slots.get("biggest", 0)
    s_jackpots = slots.get("jackpots", 0)
    s_col      = "#4db86a" if s_net >= 0 else "#c06050"

    bj_hands   = bj.get("hands", 0)
    bj_wins    = bj.get("wins", 0)
    bj_losses  = bj.get("losses", 0)
    bj_pushes  = bj.get("pushes", 0)
    bj_bj      = bj.get("blackjacks", 0)
    bj_wagered = bj.get("wagered", 0)
    bj_won     = bj.get("won", 0)
    bj_net     = bj_won - bj_wagered
    bj_streak  = bj.get("streak", 0)
    bj_col     = "#4db86a" if bj_net >= 0 else "#c06050"

    rl_wagered = rl.get("wagered", 0)
    rl_won     = rl.get("won", 0)
    rl_net     = rl_won - rl_wagered
    rl_col     = "#4db86a" if rl_net >= 0 else "#c06050"

    games = f"""<div class="section-title">游戏战绩</div>
<div class="games-grid">
  <div class="game-card">
    <div class="game-name">🎰 老虎机</div>
    <div class="game-stat"><span>拉杆次数</span><span>{s_spins}</span></div>
    <div class="game-stat"><span>总下注</span><span>{s_wagered}</span></div>
    <div class="game-stat"><span>总赢取</span><span>{s_won}</span></div>
    <div class="game-stat"><span>净盈亏</span><span style="color:{s_col}">{'+' if s_net>=0 else ''}{s_net}</span></div>
    <div class="game-stat"><span>最大单次</span><span>{s_biggest}</span></div>
    <div class="game-stat"><span>JACKPOT</span><span>🎊 {s_jackpots}次</span></div>
  </div>
  <div class="game-card">
    <div class="game-name">🃏 二十一点</div>
    <div class="game-stat"><span>对局数</span><span>{bj_hands}</span></div>
    <div class="game-stat"><span>胜/负/平</span><span>{bj_wins}/{bj_losses}/{bj_pushes}</span></div>
    <div class="game-stat"><span>Blackjack</span><span>🃏 {bj_bj}次</span></div>
    <div class="game-stat"><span>总下注</span><span>{bj_wagered}</span></div>
    <div class="game-stat"><span>总赢取</span><span>{bj_won}</span></div>
    <div class="game-stat"><span>净盈亏</span><span style="color:{bj_col}">{'+' if bj_net>=0 else ''}{bj_net}</span></div>
    <div class="game-stat"><span>连胜</span><span>🔥 {bj_streak}</span></div>
  </div>
  <div class="game-card">
    <div class="game-name">🎡 轮盘</div>
    <div class="game-stat"><span>转轮次数</span><span>{rl.get('spins',0)}</span></div>
    <div class="game-stat"><span>总下注</span><span>{rl_wagered}</span></div>
    <div class="game-stat"><span>总赢取</span><span>{rl_won}</span></div>
    <div class="game-stat"><span>净盈亏</span><span style="color:{rl_col}">{'+' if rl_net>=0 else ''}{rl_net}</span></div>
    <div class="game-stat"><span>最大单次</span><span>{rl.get('biggest',0)}</span></div>
    <div class="game-stat"><span>连胜</span><span>🔥 {rl.get('streak',0)}</span></div>
  </div>
</div>"""

    # ── 已获奖品 ──
    grouped = defaultdict(list)
    for ev in prize_events:
        grouped[ev["id"]].append(ev)

    prize_html = ""
    if grouped:
        for pid, evs in sorted(grouped.items(), key=lambda x: x[1][0]["obtained_at"], reverse=True):
            info = PRIZE_INFO.get(pid, (pid, "🎁", "gift", 0, ""))
            name, emoji, cat, cost, desc = info[0], info[1], info[2], info[3], info[4] if len(info) > 4 else ""
            total_cnt  = len(evs)
            active_cnt = sum(1 for e in evs if e["used_at"] is None)
            event_rows = ""
            for i, ev in enumerate(sorted(evs, key=lambda x: x["obtained_at"]), 1):
                if ev["used_at"]:
                    st = f'<span style="color:#c06050">已使用</span>'
                else:
                    st = '<span style="color:#4db86a">持有中</span>'
                init = ' <span style="color:#604830">(首次记录)</span>' if ev.get("init") else ""
                event_rows += f'<div class="prize-event"><span class="pe-idx">#{i}</span><span class="pe-time">{fmt_time(ev["obtained_at"])}{init}</span><span class="pe-status">{st}</span></div>'

            hold_col = "#4db86a" if active_cnt > 0 else "#c06050"
            prize_html += f"""<div class="prize-card">
  <div class="pc-top">
    <span class="pc-name">{emoji} {name}</span>
    <span class="pc-badge">{CAT_LABEL.get(cat, cat)}</span>
  </div>
  <div class="pc-desc">{desc}</div>
  <div class="pc-meta">
    <span>{cost} winnings · 共{total_cnt}个</span>
    <span style="color:{hold_col}">持有 {active_cnt}</span>
  </div>
  <div class="pc-events">{event_rows}</div>
</div>"""
    else:
        prize_html = '<span class="no-prize">还没有获得过奖品</span>'

    prizes_section = f'<div class="section-title">已获奖品</div><div class="prize-grid">{prize_html}</div>'

    # ── 可兑换奖品目录 ──
    catalog_html = ""
    for cat in ("wear", "gift", "decor"):
        items = [(pid, *info) for pid, info in PRIZE_INFO.items() if info[2] == cat]
        items.sort(key=lambda x: x[4])
        rows = ""
        for item in items:
            pid, name, emoji, _, cost = item[0], item[1], item[2], item[3], item[4]
            owned_cnt = sum(1 for ev in prize_events if ev["id"] == pid and ev["used_at"] is None)
            mark = f' <span style="color:#4db86a">✓{owned_cnt}</span>' if owned_cnt else ""
            rows += f'<div class="catalog-item"><span class="ci-name">{emoji} {name}{mark}</span><span class="ci-cost">{cost}</span></div>'
        catalog_html += f'<div class="catalog-group"><div class="catalog-cat">{CAT_LABEL[cat]}</div><div class="catalog-items">{rows}</div></div>'

    catalog_section = f'<div class="section-title">可兑换奖品</div><div class="catalog-wrap">{catalog_html}</div>'

    return top + accounting + ledger_section + games + prizes_section + catalog_section


# ── server ────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True}); return
        if self.path not in ("/", "/index.html"):
            self.send_response(404); self.end_headers(); return

        now      = datetime.now(CST).strftime("%H:%M:%S")
        cache    = load_json(DATA_FILE, None)
        hist     = load_json(HISTORY_FILE, {})
        data_time = cache.get("updated_at", "—") if cache else "—"
        subtitle  = f"player: {cache.get('player','guiwan')}" if cache else "等待开张…"

        html = PAGE.format(
            css=CSS,
            subtitle=subtitle,
            refresh_time=now,
            data_time=data_time,
            body=build_body(cache, hist),
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
        body   = self.rfile.read(length)
        try:
            payload = json.loads(body)
            payload["updated_at"] = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
            hist = load_json(HISTORY_FILE, {})
            hist = update_history(payload, hist)
            save_json(HISTORY_FILE, hist)
            save_json(DATA_FILE, payload)
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
