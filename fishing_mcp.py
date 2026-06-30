#!/usr/bin/env python3
"""桂晚的钓鱼 MCP — 让 Claude 通过 MCP 协议来玩钓鱼游戏

用法:  python3 fishing_mcp.py

环境变量:
  FISHING_GAME_DIR   游戏目录（默认 ~/ai-fishing-game）
  PORT               监听端口（默认 8891）"""

import os
import sys
from pathlib import Path

GAME_DIR = Path(os.environ.get("FISHING_GAME_DIR", Path.home() / "ai-fishing-game"))
PORT = int(os.environ.get("PORT", 8891))

sys.path.insert(0, str(GAME_DIR))
import fishing

from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.middleware.cors import CORSMiddleware

mcp = FastMCP("fishing-mcp")


@mcp.tool()
def fishing_cast(times: int = 1) -> str:
    """Cast the fishing line. Can cast multiple times in one call (up to 20). Returns the fish caught or empty result.

    Args:
        times: Number of casts, default 1, max 20
    """
    times = max(1, min(20, times))
    if times == 1:
        return fishing.cmd("cast")
    else:
        return fishing.cmd(f"cast {times}")


@mcp.tool()
def fishing_status() -> str:
    """Check current game status: season, location, points, fish basket, map progress, etc."""
    return fishing.cmd("status")


@mcp.tool()
def fishing_sell() -> str:
    """Sell all fish in the basket to gain points."""
    return fishing.cmd("sell all")


@mcp.tool()
def fishing_encyclopedia() -> str:
    """View the fish encyclopedia to learn about all discovered fish species."""
    return fishing.cmd("encyclopedia")


@mcp.tool()
def fishing_goto(location: str) -> str:
    """Move to a specified fishing location. Use status or help to see available locations.

    Args:
        location: Target location ID, e.g. moonlit_pond, reed_river
    """
    return fishing.cmd(f"goto {location}")


@mcp.tool()
def fishing_buy(item: str) -> str:
    """Purchase items or unlock locations. Use help to see available items.

    Args:
        item: Item or location ID to purchase
    """
    return fishing.cmd(f"buy {item}")


@mcp.tool()
def fishing_help() -> str:
    """View game help: all available commands and rules."""
    return fishing.cmd("help")


@mcp.tool()
def fishing_cmd(command: str) -> str:
    """Execute any game command directly (advanced use).

    Args:
        command: Command to execute, e.g. 'dive', 'rest'
    """
    return fishing.cmd(command)


if __name__ == "__main__":
    print(f"🎣  Fishing MCP started")
    print(f"    Port: {PORT}")
    print(f"    Game dir: {GAME_DIR}")
    print(f"    MCP URL: http://0.0.0.0:{PORT}/mcp")

    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
