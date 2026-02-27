"""
Worker conftest.py
放到 Worker 节点的项目根目录

差异：AsyncCollector 的 reporter 替换为 WorkerReporter（上报到 Master）
      Worker 本地不写 SQLite，不生成 HTML
"""
import logging
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.collector import AsyncCollector, RunResult
from core.storage import TestStorage
from worker.reporter import WorkerReporter

logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", os.uname().nodename)
PROJECT   = os.environ.get("PROJECT", "")
BRANCH    = os.environ.get("BRANCH", "")

_collector: AsyncCollector | None = None
_session_start: float = 0.0


def _get_collector() -> AsyncCollector:
    global _collector
    if _collector is None:
        _collector = AsyncCollector(
            storage=TestStorage("reports/local.db"),
            reporter=WorkerReporter(),
        )
    return _collector


def pytest_sessionstart(session):
    global _session_start
    _session_start = time.monotonic()
    _get_collector().start()


def pytest_sessionfinish(session, exitstatus):
    duration = round(time.monotonic() - _session_start, 2)
    collector = _get_collector()

    # 从 terminalreporter 获取统计
    tr_plugin = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = getattr(tr_plugin, "stats", {}) if tr_plugin else {}

    passed  = len(stats.get("passed",  []))
    failed  = len(stats.get("failed",  []))
    error   = len(stats.get("error",   []))
    skipped = len(stats.get("skipped", []))
    total   = passed + failed + error + skipped

    failures = []
    for r in stats.get("failed", []):
        try:
            failures.append({
                "nodeid":   r.nodeid,
                "duration": round(getattr(r, "duration", 0) or 0, 3),
                "message":  str(getattr(r, "longrepr", "") or "")[:800],
            })
        except Exception as e:
            logger.warning(f"conftest: 采集失败详情时出错: {e}")

    result = RunResult(
        passed=passed,
        failed=failed,
        error=error,
        skipped=skipped,
        total=total,
        duration=duration,
        pass_rate=round(passed / max(total, 1) * 100, 1),
        failures=failures,
    )
    result.__dict__.update({
        "run_id":    str(uuid.uuid4()),
        "worker_id": WORKER_ID,
        "project":   PROJECT,
        "branch":    BRANCH,
    })

    collector.submit(result)
    collector.stop(timeout=15.0)
