"""
pytest hooks — 异步数据采集
原则：hook 回调只做数据采集 + 队列投递，所有 I/O 在后台线程完成
      主测试进程不等待任何磁盘/数据库操作
"""
import time
import pytest
from core.collector import AsyncCollector, RunResult
from core.storage import TestStorage
from core.reporter import Reporter

# ── 全局采集器（session 级单例）────────────────────────────

_collector: AsyncCollector | None = None


def _get_collector() -> AsyncCollector:
    global _collector
    if _collector is None:
        _collector = AsyncCollector(
            storage=TestStorage(),
            reporter=Reporter(),
        )
    return _collector


# ── Session 级 hooks ──────────────────────────────────────

def pytest_sessionstart(session):
    """测试 session 开始：启动后台消费线程"""
    _get_collector().start()


def pytest_sessionfinish(session, exitstatus):
    """
    测试 session 结束：
    1. 构建 RunResult 并投入队列（非阻塞，μs 级）
    2. 调用 stop() 等待后台线程消费完毕（最多 5s）
    """
    collector = _get_collector()
    tr = session.testscollected   # 可能为 0（收集阶段失败）

    # 从 terminalreporter 获取统计（如果可用）
    reporter_plugin = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = getattr(reporter_plugin, "stats", {}) if reporter_plugin else {}

    passed  = len(stats.get("passed",  []))
    failed  = len(stats.get("failed",  []))
    error   = len(stats.get("error",   []))
    skipped = len(stats.get("skipped", []))
    total   = passed + failed + error + skipped

    # 收集失败详情
    failures = [
        {
            "nodeid": r.nodeid,
            "duration": round(getattr(r, "duration", 0), 3),
            "message": str(getattr(r, "longrepr", ""))[:800],
        }
        for r in stats.get("failed", [])
    ]

    duration = time.time() - session._setupstate._initialpathargs[0].__dict__.get(
        "_start_time", time.time()
    ) if hasattr(session, "_setupstate") else 0.0

    # 尝试从 json-report 插件获取精确 duration
    try:
        json_plugin = session.config.pluginmanager.get_plugin("json-report")
        if json_plugin and hasattr(json_plugin, "_report"):
            duration = json_plugin._report.get("duration", duration)
    except Exception:
        pass

    result = RunResult(
        passed=passed,
        failed=failed,
        error=error,
        skipped=skipped,
        total=total or tr,
        duration=round(duration, 2),
        pass_rate=round(passed / max(total, 1) * 100, 1),
        failures=failures,
    )

    # ✅ 非阻塞投入队列，hook 立即返回
    collector.submit(result)

    # 优雅停止：等后台线程把队列消费完（确保进程退出前数据落盘）
    collector.stop(timeout=5.0)
