"""
MCP Server — 薄转发层
职责：将 AI 工具的调用转发到 Master API，不做任何数据处理或渲染
HTML 报告由 Master /report/html 生成（Jinja2），MCP 直接透传

启动：MASTER_URL=http://your-master:8080 python mcp/server.py
"""
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8080")
app = Server("pytest-platform-mcp")


def _get(path: str, params: dict = None):
    url = MASTER_URL + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url += "?" + qs
    with urllib.request.urlopen(url, timeout=15) as r:
        body = r.read()
        ct = r.headers.get("Content-Type", "")
        return body.decode(), "html" in ct


# ── Tools ────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_report",
            description="获取聚合 HTML 测试报告（Master Jinja2 渲染，支持按项目/Worker/分支过滤）",
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

    if name == "get_report":
        # 直接调 Master /report/html，透传结果
        params = {k: arguments[k] for k in
                  ("project", "worker_id", "branch", "trend_limit") if k in arguments}
        body, _ = _get("/report/html", params)
        return [types.TextContent(type="text", text=body)]

    elif name == "get_summary":
        params = {k: arguments[k] for k in ("project", "worker_id") if k in arguments}
        params["limit"] = arguments.get("limit", 10)
        body, _ = _get("/results", params)
        return [types.TextContent(type="text", text=body)]

    elif name == "get_workers":
        body, _ = _get("/workers")
        return [types.TextContent(type="text", text=body)]

    elif name == "get_failure_stats":
        params = {k: arguments[k] for k in ("project", "limit") if k in arguments}
        body, _ = _get("/failures/stats", params)
        return [types.TextContent(type="text", text=body)]

    return [types.TextContent(type="text",
            text=json.dumps({"error": f"未知工具: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
