"""
REST API 层
脱离 AI 独立使用：CI/CD、前端、脚本均可调用
启动：uvicorn api.server:app --reload --port 8080
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core import TestRunner, TestStorage, Reporter

app = FastAPI(
    title="pytest Test Platform API",
    description="测试平台 REST 接口，支持执行测试、查询报告、获取趋势",
    version="1.0.0",
)

runner = TestRunner()
storage = TestStorage()
reporter = Reporter()


class RunRequest(BaseModel):
    path: str = "tests/"
    markers: Optional[str] = None
    test_id: Optional[str] = None


@app.post("/run", summary="执行测试")
def run_tests(req: RunRequest):
    """触发 pytest 执行，保存结果并返回摘要"""
    result = runner.run(path=req.path, markers=req.markers, test_id=req.test_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    storage.save(result)
    reporter.generate_html(result, storage.get_trend())
    return result


@app.get("/report/last", summary="最近一次报告")
def last_report():
    data = storage.get_last()
    if not data:
        raise HTTPException(status_code=404, detail="暂无测试记录")
    return data


@app.get("/report/history", summary="历史记录")
def history(limit: int = Query(20, ge=1, le=100)):
    return storage.get_history(limit)


@app.get("/report/trend", summary="通过率趋势")
def trend(limit: int = Query(10, ge=1, le=50)):
    return storage.get_trend(limit)


@app.get("/report/failures/stats", summary="高频失败用例统计")
def failure_stats(limit: int = Query(50, ge=1, le=200)):
    return storage.get_failure_stats(limit)


@app.get("/report/html", summary="查看 HTML 报告", response_class=FileResponse)
def html_report():
    p = Path("reports/report.html")
    if not p.exists():
        raise HTTPException(status_code=404, detail="HTML 报告不存在，请先运行测试")
    return FileResponse(p, media_type="text/html")


@app.get("/health", summary="健康检查")
def health():
    return {"status": "ok"}
