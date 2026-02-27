"""
Master REST API
职责：纯数据服务，只返回 JSON，不生成任何 HTML 页面
HTML 渲染由 MCP 层负责（前端渲染模式）

启动：uvicorn master.api.server:app --host 0.0.0.0 --port 8080
"""
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from master.core.storage import MasterStorage

app = FastAPI(
    title="pytest-platform Master API",
    description="Master 数据服务，纯 JSON 接口，不提供 HTML 页面",
    version="2.0.0",
)
storage = MasterStorage()


# ── 数据模型 ──────────────────────────────────────────────

class FailureItem(BaseModel):
    nodeid: str
    duration: float = 0.0
    message: str = ""


class RunPayload(BaseModel):
    run_id: str = Field(..., description="Worker 生成的唯一运行 ID（建议 uuid4）")
    worker_id: str = Field(..., description="Worker 标识，如 hostname 或 容器 ID")
    project: str = ""
    branch: str = ""
    timestamp: Optional[str] = None
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    total: int = 0
    duration: float = 0.0
    pass_rate: float = 0.0
    failures: list[FailureItem] = []


# ── 上报接口（Worker 调用）────────────────────────────────

@app.post("/results", status_code=201, summary="Worker 上报测试结果")
def submit_result(payload: RunPayload):
    """
    Worker 在测试完成后调用此接口上报结构化结果。
    AsyncCollector 后台线程执行此 POST，不阻塞 pytest 主进程。
    """
    run_id = storage.save_run(payload.model_dump())
    return {"run_id": run_id, "status": "saved"}


# ── 查询接口（MCP / CI / 监控调用）──────────────────────

@app.get("/results", summary="查询运行记录列表")
def list_results(
    worker_id: Optional[str] = None,
    project: Optional[str] = None,
    branch: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    return storage.get_runs(worker_id=worker_id, project=project,
                            branch=branch, limit=limit)


@app.get("/results/{run_id}", summary="查询单次运行详情（含失败明细）")
def get_result(run_id: str):
    data = storage.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    return data


@app.get("/trend", summary="通过率趋势")
def trend(
    project: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
):
    return storage.get_trend(project=project, limit=limit)


@app.get("/workers", summary="Worker 列表及状态")
def workers():
    return storage.get_workers()


@app.get("/failures/stats", summary="高频失败用例统计")
def failure_stats(
    project: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    return storage.get_failure_stats(project=project, limit=limit)


@app.get("/health", summary="健康检查")
def health():
    return {"status": "ok"}
