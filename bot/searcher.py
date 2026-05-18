import json
import subprocess
from typing import Optional


def search_clips(character: str, style: str, count: int = 5) -> list[str]:
    queries = [
        f"{character} twixtor 4k",
        f"{character} anime edit clips",
    ]
    urls: list[str] = []
    for query in queries:
        try:
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "-j", f"ytsearch{count}:{query}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                try:
                    info = json.loads(line)
                    url = info.get("url") or (
                        f"https://youtube.com/watch?v={info['id']}"
                        if "id" in info
                        else None
                    )
                    if url:
                        urls.append(url)
                except (json.JSONDecodeError, KeyError):
                    continue
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    seen: set[str] = set()
    deduped = [u for u in urls if not (u in seen or seen.add(u))]
    return deduped[:count]


def get_video_info(url: str) -> Optional[dict]:
    try:
        result = subprocess.run(
            ["yt-dlp", "-j", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None
