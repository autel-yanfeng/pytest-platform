"""
Jinja2 报告渲染器（Master 内部模块）
职责：聚合存储层数据，渲染 HTML，供 API 接口直接返回
"""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class Renderer:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def render_report(
        self,
        runs: list,
        trend: list,
        failure_stats: list,
        workers: list,
        project: str = "",
    ) -> str:
        template = self.env.get_template("report.html.j2")
        last = runs[0] if runs else {}
        failures = last.get("failures", [])
        return template.render(
            title=f"{project or '全部项目'} 测试报告",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            runs=runs,
            failures=failures,
            trend=trend,
            failure_stats=failure_stats,
            workers=workers,
        )
