"""
异步数据采集器
职责：在 pytest hook 回调中，将数据投入队列，由后台线程异步写入存储
确保 hook 回调立即返回，不阻塞测试执行进程
"""
import json
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """单次测试运行的结构化结果"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    total: int = 0
    duration: float = 0.0
    pass_rate: float = 0.0
    failures: list = field(default_factory=list)


class AsyncCollector:
    """
    异步采集器（单例，生命周期跟随 pytest session）

    原理：
      hook 回调 → put() 投入队列（非阻塞，μs 级）
                         ↓
      后台 daemon 线程 → 消费队列 → 写 SQLite / 生成报告

    pytest 主线程完全不等待 I/O。
    """

    _instance: Optional["AsyncCollector"] = None

    def __init__(self, storage, reporter=None):
        from core.storage import TestStorage
        self._storage: TestStorage = storage
        self._reporter = reporter
        self._queue: queue.Queue = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._started = False

    # ── 生命周期 ──────────────────────────────────────────

    def start(self):
        """启动后台消费线程（pytest session 开始时调用）"""
        if self._started:
            return
        self._started = True
        self._worker = threading.Thread(
            target=self._consume,
            name="collector-worker",
            daemon=True,   # 主进程退出时自动销毁
        )
        self._worker.start()
        logger.debug("AsyncCollector: worker thread started")

    def stop(self, timeout: float = 5.0):
        """
        优雅停止（pytest session 结束时调用）
        发送哨兵值，等待队列消费完毕，最多等 timeout 秒
        """
        if not self._started:
            return
        self._queue.put(None)           # 哨兵：通知 worker 退出
        if self._worker:
            self._worker.join(timeout=timeout)
            if self._worker.is_alive():
                logger.warning("AsyncCollector: worker did not finish in time")
        logger.debug("AsyncCollector: stopped")

    # ── 生产端（hook 调用，必须极快返回）────────────────────

    def submit(self, result: RunResult):
        """非阻塞投入队列，hook 调用此方法后立即返回"""
        try:
            self._queue.put_nowait(result)
        except queue.Full:
            logger.error("AsyncCollector: queue full, result dropped")

    # ── 消费端（后台线程）────────────────────────────────────

    def _consume(self):
        """后台线程：持续消费队列，执行 I/O 操作"""
        while True:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if item is None:            # 哨兵，退出
                break

            try:
                self._persist(item)
            except Exception as e:
                logger.error(f"AsyncCollector: persist failed: {e}")
            finally:
                self._queue.task_done()

    def _persist(self, result: RunResult):
        """实际 I/O：写存储 + 生成报告"""
        data = {
            "passed": result.passed,
            "failed": result.failed,
            "error": result.error,
            "skipped": result.skipped,
            "total": result.total,
            "duration": result.duration,
            "pass_rate": result.pass_rate,
            "failures": result.failures,
        }
        self._storage.save(data)
        if self._reporter:
            trend = self._storage.get_trend()
            self._reporter.generate_html(data, trend)
        logger.info(
            f"AsyncCollector: saved run — "
            f"{result.passed}/{result.total} passed, {result.duration}s"
        )
