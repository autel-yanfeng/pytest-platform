"""
MCP Server
职责：将测试平台能力标准化暴露给 AI 工具（Cursor / Claude / GPT 等）
平台能力不依赖此层，此层仅作接口适配

启动方式（stdio，Cursor 调用）：
  python mcp/server.py

依赖：
  pip install mcp
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from core import TestRunner, TestStorage, Reporter

app = Server("pytest-platform")
runner = TestRunner()
storage = TestStorage()
reporter = Reporter()


# ── Tool 定义 ────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_tests",
            description="执行 pytest 测试，返回通过/失败数量、耗时、通过率",
            inputSchema={
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "测试路径，默认 tests/"},
                    "markers": {"type": "string", "description": "marker 表达式，如 'smoke' / 'not slow'"},
                    "test_id": {"type": "string", "description": "单个测试 nodeid"},
                },
            },
        ),
        types.Tool(
            name="get_last_report",
            description="获取最近一次测试结果摘要（通过/失败/耗时/通过率）",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_failures",
            description="获取最近一次失败用例列表及堆栈信息",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_trend",
            description="获取最近 N 次测试通过率趋势",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "条数，默认10"},
                },
            },
        ),
        types.Tool(
            name="get_failure_stats",
            description="统计最近多次运行中失败频率最高的测试用例",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "扫描最近多少次记录，默认50"},
                },
            },
        ),
    ]


# ── Tool 实现 ────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    def ok(data) -> list[types.TextContent]:
        return [types.TextContent(
            type="text",
            text=json.dumps(data, ensure_ascii=False, indent=2)
        )]

    if name == "run_tests":
        result = runner.run(
            path=arguments.get("path", "tests/"),
            markers=arguments.get("markers"),
            test_id=arguments.get("test_id"),
        )
        if "error" not in result:
            storage.save(result)
            reporter.generate_html(result, storage.get_trend())
        return ok(result)

    elif name == "get_last_report":
        data = storage.get_last()
        return ok(data or {"message": "暂无测试记录"})

    elif name == "get_failures":
        data = storage.get_last()
        if not data:
            return ok({"message": "暂无测试记录"})
        return ok({"failures": data.get("failures", [])})

    elif name == "get_trend":
        limit = arguments.get("limit", 10)
        return ok(storage.get_trend(limit))

    elif name == "get_failure_stats":
        limit = arguments.get("limit", 50)
        return ok(storage.get_failure_stats(limit))

    return ok({"error": f"未知工具: {name}"})


# ── 入口 ─────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
