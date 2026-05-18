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


def _tg_post(method: str, **kwargs) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    with httpx.Client() as client:
        resp = client.post(url, json=kwargs, timeout=30)
    return resp.json()


def _send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> int:
    r = _tg_post("sendMessage", chat_id=chat_id, text=text, parse_mode=parse_mode)
    return r.get("result", {}).get("message_id", 0)


def _edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown") -> None:
    try:
        _tg_post("editMessageText", chat_id=chat_id, message_id=message_id,
                 text=text, parse_mode=parse_mode)
    except Exception:
        pass


def _send_video(chat_id: int, path: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    with httpx.Client() as client:
        with open(path, "rb") as f:
            client.post(url, data={"chat_id": chat_id, "caption": caption},
                        files={"video": f}, timeout=180)


def _fmt_progress(job: WorkerJob, step: str, detail: str = "") -> str:
    effects_on = [k for k, v in job.effects.__dict__.items() if isinstance(v, bool) and v]
    music_note = f"\n🎵 `{job.music_start:.0f}s–{job.music_end:.0f}s` · {job.bpm} BPM" if job.bpm else ""
    detail_note = f"\n{detail}" if detail else ""
    return (
        f"⚙️ Job `{job.id[:8]}`{music_note}\n"
        f"Эффекты: `{', '.join(effects_on)}`\n\n"
        f"{step}{detail_note}"
    )


def _process(job: WorkerJob) -> None:
    job_dir = WORK_DIR / job.id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.Client() as client:
            client.post(f"{VPS_URL}/jobs/{job.id}/claim", headers=_headers(), timeout=15)
    except httpx.RequestError as e:
        log.warning("Claim failed (continuing): %s", e)

    msg_id = _send_message(job.chat_id, _fmt_progress(job, "📥 Скачиваю клип..."))

    clips: list[Path] = []
    for i, url in enumerate(job.clip_urls, 1):
        _edit_message(job.chat_id, msg_id,
                      _fmt_progress(job, f"📥 Скачиваю клип {i}/{len(job.clip_urls)}..."))
        path = download_clip(url, job_dir / "clips", bot_token=BOT_TOKEN)
        if path:
            clips.append(path)
            log.info("Downloaded clip %d: %s", i, path.name)
        else:
            log.warning("Failed to download clip %d: %s", i, url[:60])

    if not clips:
        _update_status(job.id, "error", error_msg="No clips downloaded")
        _edit_message(job.chat_id, msg_id, f"❌ Не смог скачать клип для job `{job.id[:8]}`")
        return

    music: Path | None = None
    if job.music_file_id:
        _edit_message(job.chat_id, msg_id, _fmt_progress(job, "🎵 Скачиваю музыку..."))
        music = download_telegram_file(job.music_file_id, BOT_TOKEN, job_dir / "music")

    _update_status(job.id, "processing")
    output = RESULTS_DIR / f"{job.id}.mp4"

    effects_list = [k for k, v in job.effects.__dict__.items() if isinstance(v, bool) and v]
    _edit_message(job.chat_id, msg_id,
                  _fmt_progress(job, f"🎬 Рендерю на Snapdragon...",
                                 f"Применяю: `{', '.join(effects_list)}`"))

    render_start = time.time()

    def on_progress(secs: float) -> None:
        elapsed = int(time.time() - render_start)
        _edit_message(job.chat_id, msg_id,
                      _fmt_progress(job, "🎬 Рендерю на Snapdragon...",
                                    f"⏱ `{int(secs)}s` обработано · прошло `{elapsed}s`"))

    success = render(
        clips, job.effects, output, music,
        music_start=job.music_start,
        music_end=job.music_end,
        bpm=job.bpm,
        on_progress=on_progress,
    )

    if success and output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        elapsed = int(time.time() - render_start)
        _edit_message(job.chat_id, msg_id,
                      _fmt_progress(job, f"📤 Готово! Отправляю...",
                                    f"Размер: `{size_mb:.1f} MB` · Рендер: `{elapsed}s`"))
        _update_status(job.id, "done", result_path=str(output))
        _send_video(job.chat_id, output, f"✅ {job.request[:80]}")
        _edit_message(job.chat_id, msg_id,
                      _fmt_progress(job, f"✅ Готово за `{elapsed}s`",
                                    f"Размер: `{size_mb:.1f} MB`"))
    else:
        _update_status(job.id, "error", error_msg="FFmpeg render failed")
        _edit_message(job.chat_id, msg_id,
                      _fmt_progress(job, "❌ FFmpeg упал",
                                    "Проверь логи воркера"))


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
                    _send_message(job.chat_id, f"❌ Ошибка: `{exc}`")

        except httpx.RequestError as exc:
            log.warning("Poll failed: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
