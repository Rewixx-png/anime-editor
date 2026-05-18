import json
import os

import anthropic

from shared.models import EditJob, EditStyle, EffectConfig

_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_STYLE_EFFECTS: dict[EditStyle, EffectConfig] = {
    EditStyle.AGGRESSIVE: EffectConfig(
        shake=True, shake_intensity=0.5,
        motion_blur=True, blur_strength=0.6,
        color_grade=True, color_style="dark",
        chromatic=True, chromatic_offset=3,
        glitch=True, glitch_intensity=0.25,
        zoom_punch=True, zoom_intensity=1.12,
        time_remap=True,
        vignette=True, vignette_intensity=0.7,
        grain=True, grain_intensity=0.25, grain_style="film",
    ),
    EditStyle.SMOOTH: EffectConfig(
        motion_blur=True, blur_strength=0.5,
        color_grade=True, color_style="warm",
        zoom_punch=True, zoom_intensity=1.06,
        interpolate=True, interpolate_fps=60,
        vignette=True, vignette_intensity=0.5,
        grain=True, grain_intensity=0.15, grain_style="film",
    ),
    EditStyle.DARK: EffectConfig(
        shake=True, shake_intensity=0.3,
        motion_blur=True, blur_strength=0.7,
        color_grade=True, color_style="dark",
        chromatic=True, chromatic_offset=2,
        glitch=True, glitch_intensity=0.15,
        time_remap=True,
        vignette=True, vignette_intensity=0.9,
        grain=True, grain_intensity=0.45, grain_style="heavy",
    ),
    EditStyle.LOFI: EffectConfig(
        color_grade=True, color_style="warm",
        vignette=True, vignette_intensity=0.6,
        grain=True, grain_intensity=0.5, grain_style="vhs",
    ),
}

_SYSTEM = """Parse anime edit requests into JSON only.
Return: {
  "character": string|null,
  "style": "aggressive"|"smooth"|"dark"|"lofi",
  "overrides": {
    "time_remap": bool,
    "interpolate": bool,
    "interpolate_fps": int,
    "vignette": bool,
    "grain": bool,
    "grain_style": "film"|"vhs"|"heavy",
    "speed_lines": bool
  }
}
"overrides" is optional — only include keys the user explicitly requested.
Examples:
"aggressive edit kurumi" → {"character": "Kurumi Tokisaki", "style": "aggressive"}
"smooth 60fps rem edit" → {"character": "Rem", "style": "smooth", "overrides": {"interpolate": true, "interpolate_fps": 60}}
"lofi vhs grain edit" → {"character": null, "style": "lofi", "overrides": {"grain": true, "grain_style": "vhs"}}
"dark timeremap speed lines" → {"character": null, "style": "dark", "overrides": {"time_remap": true, "speed_lines": true}}"""


def parse_request(text: str, chat_id: int) -> EditJob:
    resp = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )

    try:
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        data = {"character": None, "style": "aggressive"}

    style = EditStyle(data.get("style", "aggressive"))
    effects = _STYLE_EFFECTS[style].model_copy(deep=True)

    for key, val in data.get("overrides", {}).items():
        if hasattr(effects, key):
            setattr(effects, key, val)

    return EditJob(
        chat_id=chat_id,
        request=text,
        character=data.get("character"),
        style=style,
        effects=effects,
    )
