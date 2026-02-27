"""
测试历史存储
职责：持久化每次运行结果，支持趋势查询
使用 SQLite，无外部依赖
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class TestStorage:
    def __init__(self, db_path: str = "reports/history.db"):
        Path(db_path).parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                passed    INTEGER DEFAULT 0,
                failed    INTEGER DEFAULT 0,
                error     INTEGER DEFAULT 0,
                skipped   INTEGER DEFAULT 0,
                total     INTEGER DEFAULT 0,
                duration  REAL    DEFAULT 0,
                pass_rate REAL    DEFAULT 0,
                failures  TEXT    DEFAULT '[]'
            )
        """)
        self.conn.commit()

    def save(self, result: dict) -> int:
        cur = self.conn.execute("""
            INSERT INTO runs
              (timestamp, passed, failed, error, skipped, total, duration, pass_rate, failures)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            result.get("passed", 0),
            result.get("failed", 0),
            result.get("error", 0),
            result.get("skipped", 0),
            result.get("total", 0),
            result.get("duration", 0),
            result.get("pass_rate", 0),
            json.dumps(result.get("failures", []), ensure_ascii=False),
        ))
        self.conn.commit()
        return cur.lastrowid

    def get_last(self) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_history(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_trend(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT timestamp, passed, failed, total, pass_rate FROM runs ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_failure_stats(self, limit: int = 50) -> list[dict]:
        """统计最近 N 次中失败频率最高的用例"""
        rows = self.conn.execute(
            "SELECT failures FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        counter: dict[str, int] = {}
        for row in rows:
            for f in json.loads(row["failures"]):
                counter[f["nodeid"]] = counter.get(f["nodeid"], 0) + 1
        return sorted(
            [{"nodeid": k, "fail_count": v} for k, v in counter.items()],
            key=lambda x: -x["fail_count"]
        )

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["failures"] = json.loads(d.get("failures") or "[]")
        return d
