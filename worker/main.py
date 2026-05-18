import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from shared.worker_models import WorkerJob, WorkerUpdate
from worker.downloader import download_clip, download_telegram_file
from worker.pipeline import render

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

VPS_URL = os.environ["VPS_API_URL"]
API_KEY = os.environ["WORKER_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
WORK_DIR = Path("data/worker")
RESULTS_DIR = Path("data/results")
POLL_INTERVAL = 5


def _headers() -> dict:
    return {"x-api-key": API_KEY}


def _send_video(chat_id: int, path: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    with httpx.Client() as client:
        with open(path, "rb") as f:
            client.post(url, data={"chat_id": chat_id, "caption": caption}, files={"video": f}, timeout=120)


def _send_message(chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    with httpx.Client() as client:
        client.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)


def _process(job: WorkerJob) -> None:
    job_dir = WORK_DIR / job.id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.Client() as client:
            client.post(f"{VPS_URL}/jobs/{job.id}/claim", headers=_headers(), timeout=15)
    except httpx.RequestError as e:
        log.warning("Claim request failed (continuing anyway): %s", e)

    log.info("Downloading %d clips for job %s", len(job.clip_urls), job.id[:8])
    clips: list[Path] = []
    for url in job.clip_urls:
        path = download_clip(url, job_dir / "clips", bot_token=BOT_TOKEN)
        if path:
            clips.append(path)

    if not clips:
        _update_status(job.id, "error", error_msg="No clips downloaded")
        _send_message(job.chat_id, f"❌ Не смог скачать клипы для job {job.id[:8]}")
        return

    music: Path | None = None
    if job.music_file_id:
        music = download_telegram_file(job.music_file_id, BOT_TOKEN, job_dir / "music")

    _update_status(job.id, "processing")
    output = RESULTS_DIR / f"{job.id}.mp4"

    log.info("Rendering job %s with %d clips (bpm=%s)", job.id[:8], len(clips), job.bpm)
    success = render(
        clips, job.effects, output, music,
        music_start=job.music_start,
        music_end=job.music_end,
        bpm=job.bpm,
    )

    if success and output.exists():
        _update_status(job.id, "done", result_path=str(output))
        _send_video(job.chat_id, output, f"✅ {job.request}")
    else:
        _update_status(job.id, "error", error_msg="FFmpeg render failed")
        _send_message(job.chat_id, f"❌ Ошибка рендера для job {job.id[:8]}")


def _update_status(
    job_id: str,
    status: str,
    result_path: str | None = None,
    error_msg: str | None = None,
) -> None:
    update = WorkerUpdate(status=status, result_path=result_path, error_msg=error_msg)
    try:
        with httpx.Client() as client:
            client.put(
                f"{VPS_URL}/jobs/{job_id}",
                json=update.to_dict(),
                headers=_headers(),
                timeout=10,
            )
    except httpx.RequestError:
        log.warning("Could not update job status for %s", job_id)


def run() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Worker started. Polling %s every %ds", VPS_URL, POLL_INTERVAL)

    while True:
        try:
            with httpx.Client() as client:
                resp = client.get(f"{VPS_URL}/jobs/pending", headers=_headers(), timeout=10)
            if resp.status_code != 200:
                log.warning("API returned %d: %s", resp.status_code, resp.text[:100])
                time.sleep(POLL_INTERVAL)
                continue
            jobs = [WorkerJob.from_dict(j) for j in resp.json()]

            for job in jobs:
                log.info("Processing job %s (%s)", job.id[:8], job.request[:40])
                try:
                    _process(job)
                except Exception as exc:
                    log.exception("Job %s failed: %s", job.id[:8], exc)
                    _update_status(job.id, "error", error_msg=str(exc))
                    _send_message(job.chat_id, f"❌ Ошибка: {exc}")

        except httpx.RequestError as exc:
            log.warning("Poll failed: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
