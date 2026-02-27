"""
Worker conftest.py
放到 Worker 节点的项目根目录，替换本地 conftest.py

差异：AsyncCollector 的 reporter 替换为 WorkerReporter（上报到 Master）
      Worker 本地不写 SQLite，不生成 HTML
"""
import os
import time
import uuid

import pytest

# 将平台路径加入 sys.path（根据实际部署调整）
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.collector import AsyncCollector, RunResult
from core.storage import TestStorage
from worker.reporter import WorkerReporter

WORKER_ID = os.environ.get("WORKER_ID", os.uname().nodename)
PROJECT   = os.environ.get("PROJECT", "")
BRANCH    = os.environ.get("BRANCH", "")

_collector: AsyncCollector | None = None


def _get_collector() -> AsyncCollector:
    global _collector
    if _collector is None:
        _collector = AsyncCollector(
            storage=TestStorage("reports/local.db"),  # 本地轻量缓存（可选）
            reporter=WorkerReporter(),                 # 上报到 Master
        )
    return _collector


def pytest_sessionstart(session):
    _get_collector().start()


def pytest_sessionfinish(session, exitstatus):
    collector = _get_collector()
    reporter_plugin = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = getattr(reporter_plugin, "stats", {}) if reporter_plugin else {}

    passed  = len(stats.get("passed",  []))
    failed  = len(stats.get("failed",  []))
    error   = len(stats.get("error",   []))
    skipped = len(stats.get("skipped", []))
    total   = passed + failed + error + skipped

    failures = [
        {
            "nodeid":   r.nodeid,
            "duration": round(getattr(r, "duration", 0), 3),
            "message":  str(getattr(r, "longrepr", ""))[:800],
        }
        for r in stats.get("failed", [])
    ]

    result = RunResult(
        passed=passed, failed=failed, error=error,
        skipped=skipped, total=total,
        duration=0.0,
        pass_rate=round(passed / max(total, 1) * 100, 1),
        failures=failures,
    )
    # 附加 Worker 元数据（注入到 dataclass 扩展字段）
    result.__dict__.update({
        "run_id":    str(uuid.uuid4()),
        "worker_id": WORKER_ID,
        "project":   PROJECT,
        "branch":    BRANCH,
    })

    collector.submit(result)
    collector.stop(timeout=10.0)   # Worker 上报网络 I/O，给多一点超时
