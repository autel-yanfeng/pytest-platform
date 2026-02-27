"""
测试执行器
职责：触发 pytest，返回结构化结果
脱离 AI 可独立运行
"""
import json
import subprocess
import sys
from pathlib import Path


class TestRunner:
    def __init__(self, report_dir: str = "reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(exist_ok=True)
        self.last_report_path = self.report_dir / "last.json"

    def run(self, path: str = "tests/", markers: str = None, test_id: str = None) -> dict:
        """
        执行测试，返回结构化结果

        Args:
            path: 测试路径，默认 tests/
            markers: pytest marker 表达式，如 "smoke" / "not slow"
            test_id: 单个测试 nodeid，如 "tests/test_math.py::test_add"
        """
        cmd = [
            sys.executable, "-m", "pytest",
            test_id or path,
            "-v", "--tb=short",
            f"--json-report",
            f"--json-report-file={self.last_report_path}",
        ]
        if markers:
            cmd += ["-m", markers]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if not self.last_report_path.exists():
            return {"error": "报告文件未生成，请确认 pytest-json-report 已安装"}

        data = json.loads(self.last_report_path.read_text(encoding="utf-8"))
        return self._normalize(data, result.returncode)

    def _normalize(self, raw: dict, exit_code: int) -> dict:
        summary = raw.get("summary", {})
        tests = raw.get("tests", [])
        failures = [
            {
                "nodeid": t["nodeid"],
                "duration": round(t.get("call", {}).get("duration", 0), 3),
                "message": t.get("call", {}).get("longrepr", "")[:800],
            }
            for t in tests if t.get("outcome") == "failed"
        ]
        total = summary.get("total", 1)
        passed = summary.get("passed", 0)
        return {
            "passed": passed,
            "failed": summary.get("failed", 0),
            "error": summary.get("error", 0),
            "skipped": summary.get("skipped", 0),
            "total": total,
            "duration": round(raw.get("duration", 0), 2),
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "exit_code": exit_code,
            "failures": failures,
        }
