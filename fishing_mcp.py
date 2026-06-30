#!/usr/bin/env python3
"""桂晚的钓鱼 MCP — 让 Claude 通过 MCP 协议来玩钓鱼游戏

用法:  python3 fishing_mcp.py

环境变量:
  FISHING_GAME_DIR   游戏目录（默认 ~/ai-fishing-game）
  PORT               监听端口（默认 8891）"""

import os, json, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

GAME_DIR = Path(os.environ.get("FISHING_GAME_DIR", Path.home() / "ai-fishing-game"))
PORT = int(os.environ.get("PORT", 8891))

sys.path.insert(0, str(GAME_DIR))
import fishing

TOOLS = [
    {
        "name": "fishing_cast",
        "description": "Cast the fishing line. Can cast multiple times in one call (up to 20). Returns the fish caught or empty result.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "times": {
                    "type": "integer",
                    "description": "Number of casts, default 1, max 20",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 1
                }
            }
        }
    },
    {
        "name": "fishing_status",
        "description": "Check current game status: season, location, points, fish basket, map progress, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fishing_sell",
        "description": "Sell all fish in the basket to gain points.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fishing_encyclopedia",
        "description": "View the fish encyclopedia to learn about all discovered fish species.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fishing_goto",
        "description": "Move to a specified fishing location. Use status or help to see available locations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Target location ID, e.g. moonlit_pond, reed_river"
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "fishing_buy",
        "description": "Purchase items or unlock locations. Use help to see available items.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "Item or location ID to purchase"
                }
            },
            "required": ["item"]
        }
    },
    {
        "name": "fishing_help",
        "description": "View game help: all available commands and rules.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fishing_cmd",
        "description": "Execute any game command directly (advanced use).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute, e.g. 'dive', 'rest'"
                }
            },
            "required": ["command"]
        }
    }
]


def run_tool(name, args):
    if name == "fishing_cast":
        times = args.get("times", 1)
        if times == 1:
            return fishing.cmd("cast")
        else:
            return fishing.cmd(f"cast {times}")
    elif name == "fishing_status":
        return fishing.cmd("status")
    elif name == "fishing_sell":
        return fishing.cmd("sell all")
    elif name == "fishing_encyclopedia":
        return fishing.cmd("encyclopedia")
    elif name == "fishing_goto":
        return fishing.cmd(f"goto {args['location']}")
    elif name == "fishing_buy":
        return fishing.cmd(f"buy {args['item']}")
    elif name == "fishing_help":
        return fishing.cmd("help")
    elif name == "fishing_cmd":
        return fishing.cmd(args["command"])
    else:
        return f"Unknown tool: {name}"


def json_response(handler, obj, status=200):
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
            json_response(self, {"ok": True})
        elif self.path in ("/", "/mcp"):
            json_response(self, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fishing-mcp", "version": "1.0.0"}
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            json_response(self, {"error": "invalid json"}, 400)
            return

        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            json_response(self, {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fishing-mcp", "version": "1.0.0"}
                }
            })
        elif method == "tools/list":
            json_response(self, {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"tools": TOOLS}
            })
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result = run_tool(tool_name, tool_args)
            except Exception as e:
                result = f"[Error] {e}"
            json_response(self, {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            })
        elif method == "notifications/initialized":
            self.send_response(204)
            self.end_headers()
        else:
            json_response(self, {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"🎣  Fishing MCP started")
    print(f"    Port: {PORT}")
    print(f"    Game dir: {GAME_DIR}")
    print(f"    MCP URL: http://0.0.0.0:{PORT}/mcp")
    ThreadingHTTPServer(("0.0.0.0", PORT), MCPHandler).serve_forever()
