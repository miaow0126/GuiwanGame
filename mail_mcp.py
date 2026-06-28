#!/usr/bin/env python3
"""桂晚的邮件 MCP —— 通过 agently-cli 读写 guiwan@agent.qq.com

用法：
  python3 mail_mcp.py

环境变量：
  PORT   监听端口（默认 8892）
"""

import os, json, subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8892))
CLI = "agently-cli"

TOOLS = [
    {
        "name": "mail_list",
        "description": "列出最近的邮件。返回邮件列表，包含 id、发件人、主题、时间。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回数量，默认 10，最多 50",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "mail_read",
        "description": "读取一封邮件的完整内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "邮件 ID（从 mail_list 获取）"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "mail_search",
        "description": "搜索邮件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "mail_send",
        "description": "发送一封新邮件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "收件人邮箱地址"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                },
                "body": {
                    "type": "string",
                    "description": "邮件正文"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "mail_reply",
        "description": "回复一封邮件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "要回复的邮件 ID"
                },
                "body": {
                    "type": "string",
                    "description": "回复内容"
                }
            },
            "required": ["id", "body"]
        }
    },
    {
        "name": "mail_me",
        "description": "查看当前邮箱账号信息。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def run_cli(args):
    try:
        result = subprocess.run(
            [CLI] + args,
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"[错误] {err or out}"
        return out or err
    except subprocess.TimeoutExpired:
        return "[错误] 命令超时"
    except Exception as e:
        return f"[错误] {e}"


def run_tool(name, args):
    if name == "mail_list":
        limit = args.get("limit", 10)
        return run_cli(["message", "+list", "--limit", str(limit)])
    elif name == "mail_read":
        return run_cli(["message", "+read", "--id", args["id"]])
    elif name == "mail_search":
        return run_cli(["message", "+search", "--q", args["query"]])
    elif name == "mail_send":
        first = run_cli(["message", "+send",
                         "--to", args["to"],
                         "--subject", args["subject"],
                         "--body", args["body"]])
        try:
            data = json.loads(first)
            token = (data.get("data") or {}).get("confirmation_token")
            if token:
                return run_cli(["message", "+send",
                                 "--to", args["to"],
                                 "--subject", args["subject"],
                                 "--body", args["body"],
                                 "--confirmation-token", token])
        except Exception:
            pass
        return first
    elif name == "mail_reply":
        first = run_cli(["message", "+reply",
                         "--id", args["id"],
                         "--body", args["body"]])
        try:
            data = json.loads(first)
            token = (data.get("data") or {}).get("confirmation_token")
            if token:
                return run_cli(["message", "+reply",
                                 "--id", args["id"],
                                 "--body", args["body"],
                                 "--confirmation-token", token])
        except Exception:
            pass
        return first
    elif name == "mail_me":
        return run_cli(["+me"])
    else:
        return f"未知工具：{name}"


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
                "serverInfo": {"name": "mail-mcp", "version": "1.0.0"}
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
                    "serverInfo": {"name": "mail-mcp", "version": "1.0.0"}
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
            result = run_tool(tool_name, tool_args)
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
    print(f"📬  邮件 MCP 已启动")
    print(f"    端口：{PORT}")
    print(f"    MCP 地址：http://0.0.0.0:{PORT}/mcp")
    ThreadingHTTPServer(("0.0.0.0", PORT), MCPHandler).serve_forever()
