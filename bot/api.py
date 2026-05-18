import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header

from bot.database import get_job, get_pending_jobs, update_job
from shared.models import EditJob, JobStatus, JobUpdate

load_dotenv()

app = FastAPI()


def _auth(key: str) -> None:
    api_key = os.getenv("WORKER_API_KEY", "change-me")
    if key != api_key:
        raise HTTPException(status_code=403)


@app.get("/jobs/pending")
def list_pending(x_api_key: str = Header(...)):
    _auth(x_api_key)
    return [j.model_dump() for j in get_pending_jobs()]


@app.post("/jobs/{job_id}/claim")
def claim_job(job_id: str, x_api_key: str = Header(...)):
    _auth(x_api_key)
    job = get_job(job_id)
    if not job:
        raise HTTPException(404)
    if job.status != JobStatus.PENDING:
        raise HTTPException(409, "already claimed")
    update_job(job_id, JobUpdate(status=JobStatus.DOWNLOADING))
    return {"ok": True}


@app.put("/jobs/{job_id}")
def update(job_id: str, body: JobUpdate, x_api_key: str = Header(...)):
    _auth(x_api_key)
    if not get_job(job_id):
        raise HTTPException(404)
    update_job(job_id, body)
    return {"ok": True}


@app.get("/jobs/{job_id}")
def get_status(job_id: str, x_api_key: str = Header(...)):
    _auth(x_api_key)
    job = get_job(job_id)
    if not job:
        raise HTTPException(404)
    return job.model_dump()
