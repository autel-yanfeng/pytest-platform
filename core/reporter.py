"""
报告生成器
职责：基于存储数据生成 HTML 报告（无 AI 依赖）
"""
import json
from datetime import datetime
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>测试报告</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 0; background: #f5f5f5; color: #333; }}
  .header {{ background: #1a1a2e; color: white; padding: 24px 32px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header .time {{ opacity: 0.7; font-size: 13px; margin-top: 4px; }}
  .container {{ max-width: 960px; margin: 24px auto; padding: 0 16px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  .card .num {{ font-size: 36px; font-weight: bold; }}
  .card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .passed {{ color: #22c55e; }} .failed {{ color: #ef4444; }}
  .skipped {{ color: #f59e0b; }} .rate {{ color: #3b82f6; }}
  .section {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  .section h2 {{ margin: 0 0 16px; font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
  .failure {{ border-left: 3px solid #ef4444; padding: 12px 16px; margin-bottom: 10px; background: #fef2f2; border-radius: 0 6px 6px 0; }}
  .failure .nodeid {{ font-weight: bold; font-size: 14px; margin-bottom: 6px; }}
  .failure pre {{ margin: 0; font-size: 12px; color: #666; white-space: pre-wrap; word-break: break-all; }}
  .trend-bar {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 13px; }}
  .bar {{ height: 18px; border-radius: 3px; background: #22c55e; min-width: 2px; }}
  .bar-fail {{ background: #ef4444; }}
  .no-fail {{ color: #22c55e; padding: 12px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🧪 pytest 测试报告</h1>
  <div class="time">生成时间：{timestamp}</div>
</div>
<div class="container">
  <div class="cards">
    <div class="card"><div class="num passed">{passed}</div><div class="label">通过</div></div>
    <div class="card"><div class="num failed">{failed}</div><div class="label">失败</div></div>
    <div class="card"><div class="num skipped">{skipped}</div><div class="label">跳过</div></div>
    <div class="card"><div class="num rate">{pass_rate}%</div><div class="label">通过率</div></div>
  </div>

  <div class="section">
    <h2>⏱ 执行信息</h2>
    <p>总计：{total} 个用例 &nbsp;|&nbsp; 耗时：{duration}s</p>
  </div>

  <div class="section">
    <h2>❌ 失败用例</h2>
    {failures_html}
  </div>

  <div class="section">
    <h2>📈 历史趋势（最近10次）</h2>
    {trend_html}
  </div>
</div>
</body>
</html>"""


class Reporter:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_html(self, result: dict, trend: list) -> Path:
        failures_html = self._render_failures(result.get("failures", []))
        trend_html = self._render_trend(trend)
        html = HTML_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            passed=result.get("passed", 0),
            failed=result.get("failed", 0),
            skipped=result.get("skipped", 0),
            pass_rate=result.get("pass_rate", 0),
            total=result.get("total", 0),
            duration=result.get("duration", 0),
            failures_html=failures_html,
            trend_html=trend_html,
        )
        out = self.output_dir / "report.html"
        out.write_text(html, encoding="utf-8")
        return out

    def _render_failures(self, failures: list) -> str:
        if not failures:
            return '<div class="no-fail">✅ 无失败用例</div>'
        parts = []
        for f in failures:
            msg = f.get("message", "").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"""
            <div class="failure">
              <div class="nodeid">{f['nodeid']}</div>
              <pre>{msg}</pre>
            </div>""")
        return "".join(parts)

    def _render_trend(self, trend: list) -> str:
        if not trend:
            return "<p>暂无历史数据</p>"
        max_total = max((r.get("total", 1) for r in trend), default=1)
        parts = []
        for r in trend:
            total = r.get("total", 1) or 1
            passed = r.get("passed", 0)
            failed = r.get("failed", 0)
            pw = int(passed / max_total * 300)
            fw = int(failed / max_total * 300)
            t = r.get("timestamp", "")[:16]
            parts.append(f"""
            <div class="trend-bar">
              <span style="width:140px;font-size:12px;color:#888">{t}</span>
              <div class="bar" style="width:{pw}px" title="通过:{passed}"></div>
              <div class="bar bar-fail" style="width:{fw}px" title="失败:{failed}"></div>
              <span>{r.get('pass_rate',0)}%</span>
            </div>""")
        return "".join(parts)
