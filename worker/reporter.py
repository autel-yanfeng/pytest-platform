"""
Worker 上报器
职责：AsyncCollector 采集完数据后，异步 POST 到 Master
包含重试、超时、HTTP 状态码、JSON 解析等完整错误处理
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

MASTER_URL  = os.environ.get("MASTER_URL", "http://localhost:8080")
MAX_RETRIES = int(os.environ.get("WORKER_UPLOAD_RETRIES", "3"))
TIMEOUT     = int(os.environ.get("WORKER_UPLOAD_TIMEOUT", "10"))
RETRY_DELAY = float(os.environ.get("WORKER_UPLOAD_RETRY_DELAY", "2.0"))


class UploadError(Exception):
    """上报失败（已重试耗尽）"""


class WorkerReporter:
    """
    上报到 Master 的适配器，接入 AsyncCollector._persist() 调用链
    运行在后台线程，错误不会影响主测试进程
    """

    def generate_html(self, result: dict, trend: list):
        """兼容 core/reporter.Reporter 接口，实际执行 POST 上报"""
        self._upload_with_retry(result)

    # ── 内部实现 ─────────────────────────────────────────

    def _upload_with_retry(self, result: dict):
        last_error: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                run_id = self._post(result)
                logger.info(
                    f"WorkerReporter: uploaded ok "
                    f"run_id={run_id} attempt={attempt}/{MAX_RETRIES}"
                )
                return  # 成功，退出
            except UploadError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"WorkerReporter: upload failed (attempt {attempt}/{MAX_RETRIES}), "
                        f"retry in {RETRY_DELAY}s — {e}"
                    )
                    time.sleep(RETRY_DELAY)

        logger.error(
            f"WorkerReporter: all {MAX_RETRIES} attempts failed, "
            f"result lost — {last_error}"
        )

    def _post(self, result: dict) -> str:
        """
        执行单次 POST，返回 run_id。
        所有异常统一转换为 UploadError，让 retry 逻辑统一处理。
        """
        url = f"{MASTER_URL}/results"
        try:
            body = json.dumps(result, ensure_ascii=False).encode()
        except (TypeError, ValueError) as e:
            raise UploadError(f"序列化失败: {e}") from e

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                status = resp.status
                raw = resp.read()
        except urllib.error.HTTPError as e:
            # HTTP 非 2xx（如 422 参数错误、500 服务端错误）
            raw_body = e.read().decode(errors="replace")[:200]
            raise UploadError(f"HTTP {e.code}: {raw_body}") from e
        except urllib.error.URLError as e:
            # 网络不可达、DNS 失败、连接拒绝
            raise UploadError(f"网络错误: {e.reason}") from e
        except TimeoutError as e:
            raise UploadError(f"请求超时 ({TIMEOUT}s)") from e
        except OSError as e:
            # socket 级别错误
            raise UploadError(f"Socket 错误: {e}") from e

        # 解析响应 JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise UploadError(f"响应非 JSON (status={status}): {raw[:100]}") from e

        if status not in (200, 201):
            raise UploadError(f"非预期状态码 {status}: {data}")

        run_id = data.get("run_id", "unknown")
        return run_id
