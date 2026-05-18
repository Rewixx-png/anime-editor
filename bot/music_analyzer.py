import base64
import json
import os
from pathlib import Path

import httpx


def analyze_music(audio_path: Path) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")

    _MIME = {
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".m4a": "audio/aac",
        ".aac": "audio/aac",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
    }
    mime = _MIME.get(audio_path.suffix.lower(), "audio/mpeg")

    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()

    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": audio_b64,
                    }
                },
                {
                    "text": (
                        "Analyze this music track for an anime AMV edit. "
                        "Find the single best energetic section (30-90 seconds) "
                        "that starts at a drop, buildup, or climax. "
                        "Return ONLY valid JSON, no explanation:\n"
                        '{"start": <float seconds>, "end": <float seconds>, '
                        '"bpm": <int>, "energy": "low|medium|high", '
                        '"drops": [<float seconds of key drop moments>]}'
                    )
                },
            ]
        }]
    }

    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    return {
        "start": float(data.get("start", 0)),
        "end": float(data.get("end", 90)),
        "bpm": int(data.get("bpm", 120)),
        "energy": data.get("energy", "high"),
        "drops": [float(d) for d in data.get("drops", [])],
    }
