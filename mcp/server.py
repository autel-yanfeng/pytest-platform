"""
MCP Server — 薄转发层
职责：将 AI 工具的调用转发到 Master API，不做任何渲染逻辑
包含 Master 不可用时的错误反馈，让 AI 能收到有意义的错误信息

启动：MASTER_URL=http://your-master:8080 python mcp/server.py
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8080")
TIMEOUT    = int(os.environ.get("MCP_TIMEOUT", "15"))

app = Server("pytest-platform-mcp")


# ── HTTP 工具 ─────────────────────────────────────────────

def _request(path: str, params: dict = None) -> tuple[str, bool]:
    """
    向 Master 发起 GET 请求。
    返回 (body_str, is_html)。
    失败时抛出 RuntimeError，携带可读错误描述。
    """
    url = MASTER_URL + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url += "?" + qs

    req = urllib.request.Request(url, headers={"Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode(errors="replace")
            is_html = "html" in r.headers.get("Content-Type", "")
            return body, is_html

    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Master 返回 HTTP {e.code}：{detail}") from e

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"无法连接到 Master（{MASTER_URL}）：{e.reason}\n"
            f"请确认 Master 服务已启动，环境变量 MASTER_URL 配置正确。"
        ) from e

    except TimeoutError:
        raise RuntimeError(f"Master 请求超时（{TIMEOUT}s）：{url}")


def _err(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"⚠️ 错误：{msg}")]


# ── Tools ────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_report",
            description="获取聚合 HTML 测试报告（Master Jinja2 渲染），支持按项目/Worker/分支过滤",
            inputSchema={
                "type": "object",
                "properties": {
                    "project":     {"type": "string", "description": "项目名"},
                    "worker_id":   {"type": "string", "description": "Worker ID"},
                    "branch":      {"type": "string", "description": "分支名"},
                    "trend_limit": {"type": "integer", "description": "趋势条数，默认10"},
                },
            },
        ),
        types.Tool(
            name="get_summary",
            description="获取最近 N 次运行摘要（JSON）",
            inputSchema={
                "type": "object",
                "properties": {
                    "project":   {"type": "string"},
                    "worker_id": {"type": "string"},
                    "limit":     {"type": "integer", "description": "条数，默认10"},
                },
            },
        ),
        types.Tool(
            name="get_workers",
            description="获取所有 Worker 状态（JSON）",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_failure_stats",
            description="获取高频失败用例排行（JSON）",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "limit":   {"type": "integer"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "get_report":
            params = {k: arguments[k] for k in
                      ("project", "worker_id", "branch", "trend_limit") if k in arguments}
            body, _ = _request("/report/html", params)
            return [types.TextContent(type="text", text=body)]

        elif name == "get_summary":
            params = {k: arguments[k] for k in ("project", "worker_id") if k in arguments}
            params["limit"] = arguments.get("limit", 10)
            body, _ = _request("/results", params)
            return [types.TextContent(type="text", text=body)]

        elif name == "get_workers":
            body, _ = _request("/workers")
            return [types.TextContent(type="text", text=body)]

        elif name == "get_failure_stats":
            params = {k: arguments[k] for k in ("project", "limit") if k in arguments}
            body, _ = _request("/failures/stats", params)
            return [types.TextContent(type="text", text=body)]

        else:
            return _err(f"未知工具: {name}")

    except RuntimeError as e:
        # Master 连接失败、HTTP 错误等，返回可读错误给 AI
        return _err(str(e))
    except Exception as e:
        return _err(f"MCP 内部错误: {type(e).__name__}: {e}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
