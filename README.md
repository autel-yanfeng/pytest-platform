# 🧪 pytest-platform

> **平台能力优先，AI 是调用者而非依赖项。**
>
> 脱离 AI 可独立运行完整测试流程；接入 MCP 后，AI 工具可自然语言驱动测试平台。

---

## 架构

```
┌─────────────────────────────────────────────────┐
│              测试平台（自治层）                    │
│                                                  │
│  CLI / REST API                                  │
│       ↓                                          │
│  core/runner  →  core/storage  →  core/reporter  │
│  (执行测试)       (SQLite历史)     (HTML报告)      │
│                                                  │
│  ✅ 完全独立，无 AI 依赖                           │
└──────────────────┬──────────────────────────────┘
                   │ MCP Server（标准接口层）
        ┌──────────┴──────────┐
        │                     │
   Cursor / Claude        其他 AI 工具
   自然语言驱动测试         标准 MCP 协议接入
```

---

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 方式一：CLI（最简单）

```bash
# 运行全部测试
python cli.py run

# 按 marker 运行
python cli.py run --markers smoke

# 运行单个测试
python cli.py run --test-id tests/test_example.py::TestDivide::test_divide_normal

# 查看最近结果
python cli.py report

# 查看趋势
python cli.py trend

# 查看失败用例
python cli.py failures

# 高频失败统计
python cli.py stats
```

### 方式二：REST API

```bash
# 启动 API 服务
uvicorn api.server:app --reload --port 8080

# 执行测试
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"path": "tests/", "markers": "smoke"}'

# 查看最近结果
curl http://localhost:8080/report/last

# 查看趋势
curl http://localhost:8080/report/trend

# 浏览器查看 HTML 报告
open http://localhost:8080/report/html
```

API 文档：http://localhost:8080/docs

### 方式三：Cursor AI 调用（MCP）

**配置 `.cursor/mcp.json`（已内置）：**

```json
{
  "mcpServers": {
    "test-platform": {
      "command": "python",
      "args": ["mcp/server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

重启 Cursor 后，在 Chat 中可直接说：

```
运行 smoke 标签的测试，分析失败原因
→ AI 自动调用 run_tests + get_failures，输出分析报告

最近测试趋势怎么样？
→ AI 调用 get_trend，解读变化

哪些测试最容易失败？
→ AI 调用 get_failure_stats，给出建议
```

---

## MCP 工具列表

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `run_tests` | 执行测试 | path, markers, test_id |
| `get_last_report` | 最近结果摘要 | 无 |
| `get_failures` | 失败用例+堆栈 | 无 |
| `get_trend` | 通过率趋势 | limit |
| `get_failure_stats` | 高频失败统计 | limit |

---

## 项目结构

```
pytest-platform/
├── core/
│   ├── runner.py       # pytest 执行器
│   ├── storage.py      # SQLite 历史存储
│   └── reporter.py     # HTML 报告生成
├── api/
│   └── server.py       # FastAPI REST 接口
├── mcp/
│   └── server.py       # MCP Server（AI 接口层）
├── cli.py              # 命令行入口
├── tests/
│   └── test_example.py # 示例测试
├── .cursor/
│   ├── mcp.json        # Cursor MCP 配置
│   ├── rules/must.mdc  # AI 规范
│   └── skills/         # AI 操作模板
└── requirements.txt
```

---

## 设计原则

```
平台 = 自治体
  ✅ CLI 可独立运行
  ✅ REST API 供 CI/CD 集成
  ✅ SQLite 持久化历史，无外部依赖
  ✅ HTML 报告本地生成

MCP = 标准接口
  ✅ AI 是众多调用者之一，不是依赖项
  ✅ 平台能力不因 AI 不可用而受影响
  ✅ 任何支持 MCP 协议的 AI 工具均可接入
```

---

## CI/CD 集成示例

```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    pip install -r requirements.txt
    python cli.py run
    
- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: test-report
    path: reports/report.html
```

---

## License

MIT
