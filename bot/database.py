import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

from shared.models import EditJob, JobStatus, JobUpdate

DB_PATH = Path("data/jobs.db")


def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_job(job: EditJob) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO jobs (id, data, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                job.id,
                job.model_dump_json(),
                job.status.value,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
            ),
        )
        conn.commit()


def get_job(job_id: str) -> Optional[EditJob]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT data FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if row:
        return EditJob.model_validate_json(row[0])
    return None


def get_pending_jobs() -> list[EditJob]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT data FROM jobs WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()
    return [EditJob.model_validate_json(r[0]) for r in rows]


def update_job(job_id: str, update: JobUpdate) -> None:
    job = get_job(job_id)
    if not job:
        return
    job.status = update.status
    if update.result_path is not None:
        job.result_path = update.result_path
    if update.error_msg is not None:
        job.error_msg = update.error_msg
    job.updated_at = datetime.utcnow()
    save_job(job)
