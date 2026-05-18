import base64
import json
import logging
import os
import subprocess
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

_MIME = {
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".m4a": "audio/aac",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}


def _get_audio_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except Exception:
        return 90.0


def analyze_music(audio_path: Path) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    track_dur = _get_audio_duration(audio_path)

    def _fallback() -> dict:
        return {
            "start": 0.0,
            "end": min(90.0, track_dur),
            "bpm": 128,
            "energy": "high",
            "drops": [],
        }

    try:
        mime = _MIME.get(audio_path.suffix.lower(), "audio/mpeg")
        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()

        prompt = (
            f"This audio track is {track_dur:.1f} seconds long. "
            "Analyze it for an anime AMV edit. "
            "Find the best energetic section, at least 30 seconds long, "
            "starting at a drop, buildup, or climax. "
            "Return ONLY valid JSON:\n"
            '{"start": <seconds>, "end": <seconds>, '
            '"bpm": <int 60-220>, "energy": "low|medium|high", '
            '"drops": [<seconds of key drops>]}'
        )

        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": audio_b64}},
                    {"text": prompt},
                ]
            }]
        }

        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.1-flash-lite-preview:generateContent?key={api_key}",
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw.strip())
        start = float(data.get("start", 0))
        end = float(data.get("end", min(90.0, track_dur)))
        bpm = max(60, min(220, int(data.get("bpm", 128))))

        if end - start < 20 or start < 0 or end > track_dur + 1:
            log.warning(
                "Gemini returned invalid segment %.1f–%.1f (track=%.1fs), falling back",
                start, end, track_dur,
            )
            return _fallback()

        return {
            "start": start,
            "end": end,
            "bpm": bpm,
            "energy": data.get("energy", "high"),
            "drops": [float(d) for d in data.get("drops", [])],
        }

    except Exception as e:
        log.warning("Music analysis failed: %s — using full track", e)
        return _fallback()
