"""
Master 存储层
职责：持久化来自所有 Worker 上报的测试结果
支持按 worker、project、branch 多维度查询
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class MasterStorage:
    def __init__(self, db_path: str = "master/data/results.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id     TEXT    NOT NULL UNIQUE,   -- worker 生成的唯一 ID
                worker_id  TEXT    NOT NULL,
                project    TEXT    DEFAULT '',
                branch     TEXT    DEFAULT '',
                timestamp  TEXT    NOT NULL,
                passed     INTEGER DEFAULT 0,
                failed     INTEGER DEFAULT 0,
                error      INTEGER DEFAULT 0,
                skipped    INTEGER DEFAULT 0,
                total      INTEGER DEFAULT 0,
                duration   REAL    DEFAULT 0,
                pass_rate  REAL    DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS failures (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id   TEXT NOT NULL,
                nodeid   TEXT NOT NULL,
                duration REAL DEFAULT 0,
                message  TEXT DEFAULT '',
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_runs_worker  ON runs(worker_id);
            CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project);
            CREATE INDEX IF NOT EXISTS idx_runs_ts      ON runs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_failures_run ON failures(run_id);
        """)
        self.conn.commit()

    def save_run(self, payload: dict) -> str:
        """保存 Worker 上报的一次测试结果"""
        run_id = payload["run_id"]
        self.conn.execute("""
            INSERT OR REPLACE INTO runs
              (run_id, worker_id, project, branch, timestamp,
               passed, failed, error, skipped, total, duration, pass_rate)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_id,
            payload.get("worker_id", "unknown"),
            payload.get("project", ""),
            payload.get("branch", ""),
            payload.get("timestamp", datetime.now().isoformat(timespec="seconds")),
            payload.get("passed", 0),
            payload.get("failed", 0),
            payload.get("error", 0),
            payload.get("skipped", 0),
            payload.get("total", 0),
            payload.get("duration", 0),
            payload.get("pass_rate", 0),
        ))
        # 写入失败明细
        for f in payload.get("failures", []):
            self.conn.execute("""
                INSERT INTO failures (run_id, nodeid, duration, message)
                VALUES (?,?,?,?)
            """, (run_id, f.get("nodeid", ""), f.get("duration", 0), f.get("message", "")))
        self.conn.commit()
        return run_id

    def get_runs(self, worker_id: str = None, project: str = None,
                 branch: str = None, limit: int = 50) -> list[dict]:
        where, params = [], []
        if worker_id:
            where.append("worker_id=?"); params.append(worker_id)
        if project:
            where.append("project=?"); params.append(project)
        if branch:
            where.append("branch=?"); params.append(branch)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM runs {clause} ORDER BY id DESC LIMIT ?", params
        ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["failures"] = [
            dict(r) for r in self.conn.execute(
                "SELECT nodeid, duration, message FROM failures WHERE run_id=?", (run_id,)
            ).fetchall()
        ]
        return data

    def get_trend(self, project: str = None, limit: int = 10) -> list[dict]:
        where = "WHERE project=?" if project else ""
        params = ([project] if project else []) + [limit]
        rows = self.conn.execute(
            f"SELECT timestamp, passed, failed, total, pass_rate, worker_id "
            f"FROM runs {where} ORDER BY id DESC LIMIT ?", params
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_workers(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT worker_id,
                   COUNT(*) as run_count,
                   MAX(timestamp) as last_seen,
                   AVG(pass_rate) as avg_pass_rate
            FROM runs GROUP BY worker_id ORDER BY last_seen DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_failure_stats(self, project: str = None, limit: int = 100) -> list[dict]:
        where = "WHERE r.project=?" if project else ""
        params = ([project] if project else []) + [limit]
        rows = self.conn.execute(f"""
            SELECT f.nodeid, COUNT(*) as fail_count
            FROM failures f JOIN runs r ON f.run_id = r.run_id
            {where}
            GROUP BY f.nodeid ORDER BY fail_count DESC LIMIT ?
        """, params).fetchall()
        return [dict(r) for r in rows]
