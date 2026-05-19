import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_TG_TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0)
_TG_CHUNK = 64 * 1024
_TG_MAX_RETRIES = 4


def download_clip(url: str, dest_dir: Path, bot_token: str = "") -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)

    if url.startswith("local:"):
        local = Path(url[6:])
        if not local.exists():
            log.error("Local clip not found: %s", local)
            return None
        return local

    if url.startswith("tg:"):
        file_id = url[3:]
        log.info("Downloading clip from Telegram: %s", file_id[:20])
        return download_telegram_file(file_id, bot_token, dest_dir)

    log.info("Downloading: %s", url)
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "--merge-output-format", "mp4",
                "-o", str(dest_dir / "%(id)s.%(ext)s"),
                "--no-playlist",
                "--retries", "3",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            log.error("yt-dlp failed (rc=%d):\n%s", result.returncode, result.stderr[-800:])
            return None
        downloaded = sorted(dest_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not downloaded:
            log.error("yt-dlp succeeded but no .mp4 found in %s", dest_dir)
            return None
        return downloaded[-1]
    except subprocess.TimeoutExpired:
        log.error("yt-dlp timed out for %s", url)
        return None
    except FileNotFoundError:
        log.error("yt-dlp not found — install it in Termux: pip install yt-dlp")
        return None


def download_telegram_file(file_id: str, bot_token: str, dest_dir: Path) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = f"https://api.telegram.org/bot{bot_token}"

    with httpx.Client(timeout=_TG_TIMEOUT) as client:
        try:
            resp = client.get(f"{base}/getFile", params={"file_id": file_id})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.error("getFile failed for %s: %s", file_id[:20], e)
            return None

        result = resp.json().get("result") or {}
        file_path = result.get("file_path")
        if not file_path:
            log.error("getFile returned no file_path: %s", resp.text[:200])
            return None
        expected_size = int(result.get("file_size") or 0)

        ext = Path(file_path).suffix or ".bin"
        safe_id = file_id[:32].replace("/", "_").replace(":", "_")
        dest = dest_dir / f"{safe_id}{ext}"
        url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

        for attempt in range(1, _TG_MAX_RETRIES + 1):
            try:
                written = 0
                with client.stream("GET", url) as data:
                    if data.status_code != 200:
                        log.warning(
                            "TG file HTTP %d (attempt %d/%d)",
                            data.status_code, attempt, _TG_MAX_RETRIES,
                        )
                        time.sleep(min(2 ** attempt, 15))
                        continue
                    with open(dest, "wb") as f:
                        for chunk in data.iter_bytes(chunk_size=_TG_CHUNK):
                            f.write(chunk)
                            written += len(chunk)
                if expected_size and written < expected_size:
                    log.warning(
                        "Short read %d/%d bytes (attempt %d/%d)",
                        written, expected_size, attempt, _TG_MAX_RETRIES,
                    )
                    time.sleep(min(2 ** attempt, 15))
                    continue
                log.info("Downloaded %s: %d bytes", dest.name, written)
                return dest
            except (httpx.RemoteProtocolError, httpx.ReadTimeout,
                    httpx.ConnectError, httpx.ReadError) as e:
                log.warning(
                    "TG download attempt %d/%d failed: %s",
                    attempt, _TG_MAX_RETRIES, e,
                )
                time.sleep(min(2 ** attempt, 15))

        log.error("TG download exhausted retries for %s", file_id[:20])
        return None
