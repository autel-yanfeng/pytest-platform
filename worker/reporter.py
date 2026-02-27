"""
Worker 上报器
职责：AsyncCollector 采集完数据后，异步 POST 到 Master
Worker 本地不存储、不生成报告，纯上报
"""
import logging
import os
import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)

MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8080")


class WorkerReporter:
    """
    上报到 Master 的适配器
    替换 AsyncCollector 中的 reporter 参数传入
    """

    def generate_html(self, result: dict, trend: list):
        """
        接口兼容 core/reporter.Reporter，但实际执行 POST 上报
        被 AsyncCollector._persist() 调用，运行在后台线程中
        """
        self._post(result)

    def _post(self, result: dict):
        url = f"{MASTER_URL}/results"
        data = json.dumps(result, ensure_ascii=False).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
                logger.info(f"WorkerReporter: uploaded run_id={body.get('run_id')}")
        except urllib.error.URLError as e:
            logger.error(f"WorkerReporter: upload failed → {e}")
