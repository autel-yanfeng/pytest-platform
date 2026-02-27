"""
命令行入口
脱离 AI 和 API，直接在终端使用

用法：
  python cli.py run                        # 运行全部测试
  python cli.py run --path tests/unit      # 指定目录
  python cli.py run --markers smoke        # 按 marker 运行
  python cli.py run --test-id tests/test_math.py::test_add  # 单个测试
  python cli.py report                     # 查看最近结果
  python cli.py trend                      # 查看趋势
  python cli.py failures                   # 查看失败用例
  python cli.py stats                      # 高频失败统计
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import TestRunner, TestStorage, Reporter


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_run(args):
    runner = TestRunner()
    storage = TestStorage()
    reporter = Reporter()

    print(f"▶ 执行测试：{args.path or args.test_id or 'tests/'}")
    result = runner.run(
        path=args.path or "tests/",
        markers=args.markers,
        test_id=args.test_id,
    )

    if "error" in result:
        print(f"✗ 错误：{result['error']}")
        sys.exit(1)

    storage.save(result)
    html_path = reporter.generate_html(result, storage.get_trend())

    # 打印摘要
    status = "✅ 全部通过" if result["failed"] == 0 else "❌ 存在失败"
    print(f"\n{status}")
    print(f"  通过: {result['passed']}  失败: {result['failed']}  "
          f"跳过: {result['skipped']}  共: {result['total']}")
    print(f"  通过率: {result['pass_rate']}%  耗时: {result['duration']}s")
    print(f"  HTML 报告: {html_path}")

    if result["failures"]:
        print("\n失败用例：")
        for f in result["failures"]:
            print(f"  ✗ {f['nodeid']}")
            if f.get("message"):
                lines = f["message"].splitlines()[:5]
                for line in lines:
                    print(f"    {line}")

    return result["exit_code"]


def cmd_report(args):
    storage = TestStorage()
    data = storage.get_last()
    if not data:
        print("暂无测试记录")
        return
    print_json({k: v for k, v in data.items() if k != "failures"})


def cmd_trend(args):
    storage = TestStorage()
    trend = storage.get_trend(args.limit)
    print(f"\n最近 {len(trend)} 次测试趋势：\n")
    for r in trend:
        bar = "█" * int(r["pass_rate"] / 5)
        print(f"  {r['timestamp'][:16]}  {bar:<20} {r['pass_rate']}%  "
              f"({r['passed']}/{r['total']})")


def cmd_failures(args):
    storage = TestStorage()
    data = storage.get_last()
    if not data:
        print("暂无测试记录")
        return
    failures = data.get("failures", [])
    if not failures:
        print("✅ 最近一次测试无失败用例")
        return
    for f in failures:
        print(f"\n✗ {f['nodeid']}")
        print(f"  {f.get('message', '')[:300]}")


def cmd_stats(args):
    storage = TestStorage()
    stats = storage.get_failure_stats(args.limit)
    if not stats:
        print("暂无失败记录")
        return
    print(f"\n高频失败用例（最近 {args.limit} 次运行）：\n")
    for s in stats[:10]:
        print(f"  {s['fail_count']:>3}次  {s['nodeid']}")


def main():
    parser = argparse.ArgumentParser(description="pytest 测试平台 CLI")
    sub = parser.add_subparsers(dest="cmd")

    # run
    p_run = sub.add_parser("run", help="执行测试")
    p_run.add_argument("--path", help="测试路径")
    p_run.add_argument("--markers", "-m", help="marker 表达式")
    p_run.add_argument("--test-id", help="单个测试 nodeid")

    # report
    sub.add_parser("report", help="查看最近一次结果")

    # trend
    p_trend = sub.add_parser("trend", help="查看通过率趋势")
    p_trend.add_argument("--limit", type=int, default=10)

    # failures
    sub.add_parser("failures", help="查看最近失败用例")

    # stats
    p_stats = sub.add_parser("stats", help="高频失败统计")
    p_stats.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    dispatch = {
        "run": cmd_run,
        "report": cmd_report,
        "trend": cmd_trend,
        "failures": cmd_failures,
        "stats": cmd_stats,
    }
    exit_code = dispatch[args.cmd](args) or 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
