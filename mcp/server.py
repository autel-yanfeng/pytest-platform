"""
MCP Server — 聚合渲染层
职责：
  1. 查询 Master API 获取结构化数据
  2. 在 AI 对话中按需聚合、渲染 HTML 报告（前端渲染模式）
  3. 不存储任何数据，纯读取 + 渲染

启动（stdio，Cursor 调用）：
  MASTER_URL=http://your-master:8080 python mcp/server.py
"""
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8080")

app = Server("pytest-platform-mcp")


# ── 工具函数 ─────────────────────────────────────────────

def _get(path: str, params: dict = None) -> dict | list:
    url = MASTER_URL + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if qs:
            url += "?" + qs
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def _render_html(runs: list, trend: list, failures_stats: list,
                 workers: list, title: str = "测试报告") -> str:
    """
    MCP 渲染层：将 JSON 数据聚合为 HTML 报告
    等效于前端渲染，无需服务端提供页面
    """
    last = runs[0] if runs else {}
    passed   = last.get("passed", 0)
    failed   = last.get("failed", 0)
    skipped  = last.get("skipped", 0)
    total    = last.get("total", 0)
    duration = last.get("duration", 0)
    pass_rate = last.get("pass_rate", 0)

    # 趋势图
    max_total = max((r.get("total", 1) for r in trend), default=1)
    trend_rows = ""
    for r in trend:
        t = r.get("total", 1) or 1
        pw = int(r.get("passed", 0) / max_total * 280)
        fw = int(r.get("failed", 0) / max_total * 280)
        trend_rows += f"""
        <tr>
          <td style="color:#888;font-size:12px">{r.get('timestamp','')[:16]}</td>
          <td><span style="display:inline-block;width:{pw}px;height:14px;background:#22c55e;border-radius:2px"></span>
              <span style="display:inline-block;width:{fw}px;height:14px;background:#ef4444;border-radius:2px"></span></td>
          <td style="font-weight:bold">{r.get('pass_rate',0)}%</td>
          <td style="color:#888">{r.get('worker_id','')}</td>
        </tr>"""

    # 失败明细
    failures_rows = ""
    for f in last.get("failures", []):
        msg = (f.get("message") or "")[:300].replace("<","&lt;").replace(">","&gt;")
        failures_rows += f"""
        <tr>
          <td style="color:#ef4444;font-size:13px">{f.get('nodeid','')}</td>
          <td><pre style="margin:0;font-size:11px;color:#666;white-space:pre-wrap">{msg}</pre></td>
        </tr>"""
    if not failures_rows:
        failures_rows = '<tr><td colspan="2" style="color:#22c55e;padding:12px">✅ 无失败用例</td></tr>'

    # 高频失败统计
    stats_rows = "".join(
        f'<tr><td style="font-weight:bold;color:#ef4444">{s["fail_count"]}</td>'
        f'<td style="font-size:13px">{s["nodeid"]}</td></tr>'
        for s in failures_stats[:10]
    ) or '<tr><td colspan="2" style="color:#22c55e">暂无数据</td></tr>'

    # Worker 状态
    worker_rows = "".join(
        f'<tr><td>{w["worker_id"]}</td><td>{w["run_count"]}</td>'
        f'<td>{round(w["avg_pass_rate"],1)}%</td><td style="color:#888">{w["last_seen"][:16]}</td></tr>'
        for w in workers
    ) or '<tr><td colspan="4" style="color:#888">暂无 Worker</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><title>{title}</title>
<style>
  *{{box-sizing:border-box}} body{{font-family:-apple-system,sans-serif;margin:0;background:#f5f5f5;color:#333}}
  .hd{{background:#1a1a2e;color:#fff;padding:20px 32px}}
  .hd h1{{margin:0;font-size:20px}} .hd p{{margin:4px 0 0;opacity:.6;font-size:13px}}
  .wrap{{max-width:1000px;margin:20px auto;padding:0 16px}}
  .cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
  .card{{background:#fff;border-radius:8px;padding:18px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
  .card .n{{font-size:32px;font-weight:700}} .card .l{{font-size:12px;color:#888;margin-top:4px}}
  .green{{color:#22c55e}} .red{{color:#ef4444}} .amber{{color:#f59e0b}} .blue{{color:#3b82f6}}
  .sec{{background:#fff;border-radius:8px;padding:18px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
  .sec h2{{margin:0 0 14px;font-size:15px;border-bottom:1px solid #eee;padding-bottom:8px}}
  table{{width:100%;border-collapse:collapse}} td{{padding:8px 10px;border-bottom:1px solid #f0f0f0;vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
</style>
</head>
<body>
<div class="hd">
  <h1>🧪 {title}</h1>
  <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 数据来源：{MASTER_URL}</p>
</div>
<div class="wrap">
  <div class="cards">
    <div class="card"><div class="n green">{passed}</div><div class="l">通过</div></div>
    <div class="card"><div class="n red">{failed}</div><div class="l">失败</div></div>
    <div class="card"><div class="n amber">{skipped}</div><div class="l">跳过</div></div>
    <div class="card"><div class="n blue">{pass_rate}%</div><div class="l">通过率</div></div>
  </div>
  <div class="sec">
    <h2>⏱ 执行概况</h2>
    <table><tr><td>总用例</td><td>{total}</td>
    <td>耗时</td><td>{duration}s</td></tr></table>
  </div>
  <div class="sec">
    <h2>❌ 失败用例</h2>
    <table>{failures_rows}</table>
  </div>
  <div class="sec">
    <h2>📈 历史趋势</h2>
    <table>{trend_rows}</table>
  </div>
  <div class="sec">
    <h2>🔥 高频失败</h2>
    <table><tr><th style="text-align:left">次数</th><th style="text-align:left">用例</th></tr>
    {stats_rows}</table>
  </div>
  <div class="sec">
    <h2>🖥 Worker 状态</h2>
    <table><tr><th style="text-align:left">Worker</th><th>运行次数</th>
    <th>平均通过率</th><th>最后上报</th></tr>
    {worker_rows}</table>
  </div>
</div>
</body></html>"""


# ── MCP Tools ────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_report",
            description="从 Master 获取最新测试结果，渲染为 HTML 报告返回",
            inputSchema={
                "type": "object",
                "properties": {
                    "project":   {"type": "string", "description": "项目名过滤"},
                    "worker_id": {"type": "string", "description": "Worker 过滤"},
                    "branch":    {"type": "string", "description": "分支过滤"},
                },
            },
        ),
        types.Tool(
            name="get_summary",
            description="获取最新测试结果摘要（JSON，不渲染 HTML）",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "limit":   {"type": "integer", "description": "返回条数，默认10"},
                },
            },
        ),
        types.Tool(
            name="get_trend",
            description="获取通过率趋势数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "limit":   {"type": "integer", "description": "最近N次，默认10"},
                },
            },
        ),
        types.Tool(
            name="get_failures",
            description="获取最近一次运行的失败用例列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "project":   {"type": "string"},
                    "worker_id": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="get_workers",
            description="获取所有 Worker 状态（运行次数、通过率、最后上报时间）",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_failure_stats",
            description="统计高频失败用例排行",
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
async def call_tool(name: str, arguments: dict) -> list[types.TextContent | types.EmbeddedResource]:

    def json_resp(data) -> list:
        return [types.TextContent(type="text",
                text=json.dumps(data, ensure_ascii=False, indent=2))]

    if name == "get_report":
        params = {k: arguments[k] for k in ("project", "worker_id", "branch") if k in arguments}
        runs   = _get("/results", {**params, "limit": 1})
        trend  = _get("/trend",   {"project": arguments.get("project"), "limit": 10})
        stats  = _get("/failures/stats", {"project": arguments.get("project"), "limit": 20})
        workers = _get("/workers")
        title  = f"{arguments.get('project', '全部项目')} 测试报告"
        html   = _render_html(runs, trend, stats, workers, title)
        # 将 HTML 作为资源返回，AI 可直接展示或保存
        return [types.TextContent(type="text", text=html)]

    elif name == "get_summary":
        params = {"project": arguments.get("project"), "limit": arguments.get("limit", 10)}
        return json_resp(_get("/results", params))

    elif name == "get_trend":
        return json_resp(_get("/trend", {
            "project": arguments.get("project"),
            "limit": arguments.get("limit", 10),
        }))

    elif name == "get_failures":
        params = {k: arguments[k] for k in ("project", "worker_id") if k in arguments}
        params["limit"] = 1
        runs = _get("/results", params)
        if not runs:
            return json_resp({"message": "暂无记录"})
        detail = _get(f"/results/{runs[0]['run_id']}")
        return json_resp({"failures": detail.get("failures", [])})

    elif name == "get_workers":
        return json_resp(_get("/workers"))

    elif name == "get_failure_stats":
        return json_resp(_get("/failures/stats", {
            "project": arguments.get("project"),
            "limit": arguments.get("limit", 50),
        }))

    return json_resp({"error": f"未知工具: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
