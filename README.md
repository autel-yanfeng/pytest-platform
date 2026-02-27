# 🧪 pytest-platform

> **Master-Worker 分布式测试平台**
> - Master：纯数据服务，只提供 JSON API，不生成页面
> - Worker：执行测试，异步上报结果
> - MCP：聚合渲染层，等效前端渲染，按需生成 HTML 报告

---

## 架构

```
┌─────────────────┐     POST /results      ┌─────────────────────────┐
│   Worker 节点    │  ──────────────────→  │     Master 服务          │
│                 │                        │                          │
│  pytest 执行    │                        │  FastAPI REST（纯 JSON）  │
│  AsyncCollector │   Worker 可以是：       │  SQLite 存储             │
│  后台线程上报    │   - 本地机器            │  多 Worker 数据汇聚       │
│                 │   - Docker 容器         │  不生成任何 HTML          │
│  WORKER_ID      │   - CI Runner           │                          │
│  PROJECT        │   - 远程服务器           └────────────┬────────────┘
│  BRANCH         │                                       │ JSON API
└─────────────────┘                                       │
                                               ┌──────────▼──────────┐
                                               │    MCP Server        │
                                               │   （聚合渲染层）       │
                                               │                      │
                                               │  查询 Master API     │
                                               │  聚合多维度数据        │
                                               │  渲染 HTML 报告       │
                                               │  返回给 AI 工具        │
                                               └─────────────────────┘
```

### 分层职责

| 层级 | 组件 | 职责 | 是否生成 HTML |
|------|------|------|:---:|
| 执行层 | Worker conftest | pytest 执行 + 异步上报 | ❌ |
| 数据层 | Master API | JSON 存取，多 Worker 汇聚 | ❌ |
| 渲染层 | MCP Server | 聚合数据，按需渲染 HTML | ✅ |

---

## 快速开始

### 1. 启动 Master 服务

```bash
pip install -r requirements.txt
uvicorn master.api.server:app --host 0.0.0.0 --port 8080
```

### 2. 配置 Worker 节点

将 `worker/conftest.py` 放到测试项目根目录，设置环境变量：

```bash
export MASTER_URL=http://your-master:8080
export WORKER_ID=ci-runner-01       # Worker 标识（默认 hostname）
export PROJECT=my-service           # 项目名
export BRANCH=main                  # 分支名

pytest tests/
# → 测试完成后自动异步上报到 Master
```

### 3. 接入 Cursor MCP

配置 `.cursor/mcp.json`（已内置）：

```json
{
  "mcpServers": {
    "pytest-platform": {
      "command": "python",
      "args": ["mcp/server.py"],
      "env": { "MASTER_URL": "http://your-master:8080" }
    }
  }
}
```

在 Cursor Chat 中使用：

```
生成 my-service 项目的测试报告
→ MCP 查询 Master，聚合数据，渲染 HTML 返回

哪些 Worker 最近在跑测试？
→ MCP 调用 get_workers，返回状态

main 分支最近10次趋势怎么样？
→ MCP 调用 get_trend(project=my-service)
```

---

## 项目结构

```
pytest-platform/
├── master/
│   ├── core/storage.py     # SQLite 存储（多 Worker 汇聚）
│   └── api/server.py       # FastAPI REST，纯 JSON，无 HTML
├── worker/
│   ├── conftest.py         # Worker pytest hooks（异步上报）
│   └── reporter.py         # POST 到 Master 的适配器
├── core/
│   ├── collector.py        # AsyncCollector（queue + daemon thread）
│   ├── runner.py           # 本地执行器（单机模式用）
│   └── storage.py          # 本地 SQLite（Worker 可选缓存）
├── mcp/
│   └── server.py           # MCP Server，聚合渲染层
├── .cursor/
│   ├── mcp.json            # Cursor MCP 配置
│   └── skills/             # AI 操作模板
└── requirements.txt
```

---

## MCP 工具列表

| 工具 | 功能 | 返回 |
|------|------|------|
| `get_report` | 聚合所有数据，渲染完整 HTML 报告 | HTML 字符串 |
| `get_summary` | 最近 N 次运行摘要 | JSON |
| `get_trend` | 通过率趋势 | JSON |
| `get_failures` | 最近一次失败明细 | JSON |
| `get_workers` | 所有 Worker 状态 | JSON |
| `get_failure_stats` | 高频失败用例排行 | JSON |

---

## Master API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/results` | Worker 上报测试结果 |
| GET  | `/results` | 查询运行列表（支持过滤） |
| GET  | `/results/{run_id}` | 单次运行详情+失败明细 |
| GET  | `/trend` | 通过率趋势 |
| GET  | `/workers` | Worker 状态汇总 |
| GET  | `/failures/stats` | 高频失败统计 |
| GET  | `/health` | 健康检查 |

完整 Swagger 文档：`http://master:8080/docs`

---

## Hook 异步采集原理

```
pytest 主线程（Worker）              后台 daemon 线程
────────────────────                 ────────────────
测试用例执行...
pytest_sessionfinish()
  构建 RunResult（内存操作）
  queue.put_nowait()  ────────────→  取出 RunResult
  ← μs 级返回                         POST /results → Master
测试进程继续收尾...                    Master 写 SQLite
stop(timeout=10s) ─────────────────→ join() 等完成
进程退出
```

---

## CI/CD 集成

```yaml
# .github/workflows/test.yml
- name: Run Tests
  env:
    MASTER_URL: ${{ secrets.MASTER_URL }}
    WORKER_ID:  ${{ runner.name }}
    PROJECT:    my-service
    BRANCH:     ${{ github.ref_name }}
  run: |
    pip install -r requirements.txt
    cp worker/conftest.py ./conftest.py
    pytest tests/
```

---

## License

MIT
