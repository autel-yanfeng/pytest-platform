"""
Master REST API
职责：JSON 数据接口 + /report/html 聚合报告（Jinja2 渲染）
HTML 由 Master 内部 Renderer 生成，MCP 直接调用此接口获取完整报告

启动：uvicorn master.api.server:app --host 0.0.0.0 --port 8080
"""
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from master.core.storage import MasterStorage
from master.core.renderer import Renderer

app = FastAPI(
    title="pytest-platform Master API",
    description="Master 数据服务：JSON 接口 + /report/html 聚合报告（Jinja2 渲染）",
    version="2.0.0",
)
storage = MasterStorage()
renderer = Renderer()


# ── 数据模型 ──────────────────────────────────────────────

class FailureItem(BaseModel):
    nodeid: str
    duration: float = 0.0
    message: str = ""


class RunPayload(BaseModel):
    run_id: str = Field(..., description="Worker 生成的唯一运行 ID（建议 uuid4）")
    worker_id: str = Field(..., description="Worker 标识，如 hostname 或容器 ID")
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
    run_id = storage.save_run(payload.model_dump())
    return {"run_id": run_id, "status": "saved"}


# ── JSON 查询接口（CI / 监控调用）────────────────────────

@app.get("/results", summary="查询运行记录列表")
def list_results(
    worker_id: Optional[str] = None,
    project: Optional[str] = None,
    branch: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    return storage.get_runs(worker_id=worker_id, project=project,
                            branch=branch, limit=limit)


@app.get("/results/{run_id}", summary="单次运行详情（含失败明细）")
def get_result(run_id: str):
    data = storage.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    return data


@app.get("/trend", summary="通过率趋势")
def trend(project: Optional[str] = None, limit: int = Query(10, ge=1, le=100)):
    return storage.get_trend(project=project, limit=limit)


@app.get("/workers", summary="Worker 列表及状态")
def workers():
    return storage.get_workers()


@app.get("/failures/stats", summary="高频失败用例统计")
def failure_stats(project: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    return storage.get_failure_stats(project=project, limit=limit)


# ── HTML 聚合报告（MCP / 浏览器调用）────────────────────

@app.get("/report/html", response_class=HTMLResponse, summary="聚合 HTML 报告（Jinja2 渲染）")
def html_report(
    project: Optional[str] = None,
    worker_id: Optional[str] = None,
    branch: Optional[str] = None,
    trend_limit: int = Query(10, ge=1, le=50),
):
    """
    聚合所有维度数据，使用 Jinja2 模板渲染完整 HTML 报告。
    MCP 直接调用此接口，无需在 MCP 层做任何渲染逻辑。
    """
    runs   = storage.get_runs(worker_id=worker_id, project=project, branch=branch, limit=1)
    # 需要失败明细，单独查详情
    if runs:
        detail = storage.get_run(runs[0]["run_id"])
        runs[0]["failures"] = detail.get("failures", []) if detail else []

    trend  = storage.get_trend(project=project, limit=trend_limit)
    stats  = storage.get_failure_stats(project=project, limit=20)
    wks    = storage.get_workers()
    html   = renderer.render_report(runs, trend, stats, wks, project=project or "")
    return HTMLResponse(content=html)


@app.get("/health", summary="健康检查")
def health():
    return {"status": "ok"}
