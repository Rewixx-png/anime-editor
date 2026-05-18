import logging
import subprocess
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def download_clip(url: str, dest_dir: Path) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)

    if url.startswith("local:"):
        local = Path(url[6:])
        if not local.exists():
            log.error("Local clip not found: %s", local)
            return None
        return local

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

    with httpx.Client() as client:
        resp = client.get(f"{base}/getFile", params={"file_id": file_id})
        if resp.status_code != 200:
            return None
        file_path = resp.json()["result"]["file_path"]
        ext = Path(file_path).suffix
        dest = dest_dir / f"music{ext}"
        data = client.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}")
        if data.status_code != 200:
            return None
        dest.write_bytes(data.content)
        return dest
