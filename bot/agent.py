import json
import os

import anthropic

from shared.models import EditJob, EditStyle, EffectConfig

_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_STYLE_EFFECTS: dict[EditStyle, EffectConfig] = {
    EditStyle.AGGRESSIVE: EffectConfig(
        shake=True, shake_intensity=2.0,
        motion_blur=True, blur_strength=1.5,
        color_grade=True, color_style="dark",
        chromatic=True, chromatic_offset=5,
        glitch=True, glitch_intensity=0.8,
        zoom_punch=True, zoom_intensity=1.4,
    ),
    EditStyle.SMOOTH: EffectConfig(
        motion_blur=True, blur_strength=0.8,
        color_grade=True, color_style="warm",
        zoom_punch=True, zoom_intensity=1.1,
    ),
    EditStyle.DARK: EffectConfig(
        shake=True, shake_intensity=1.0,
        motion_blur=True, blur_strength=1.0,
        color_grade=True, color_style="dark",
        chromatic=True, chromatic_offset=3,
        glitch=True, glitch_intensity=0.4,
    ),
    EditStyle.LOFI: EffectConfig(
        color_grade=True, color_style="warm",
    ),
}

_SYSTEM = """Parse anime edit requests into JSON only.
Return: {"character": string|null, "style": "aggressive"|"smooth"|"dark"|"lofi"}
Examples:
"aggressive edit kurumi" → {"character": "Kurumi Tokisaki", "style": "aggressive"}
"smooth rem edit" → {"character": "Rem", "style": "smooth"}
"dark edit" → {"character": null, "style": "dark"}"""


def parse_request(text: str, chat_id: int) -> EditJob:
    resp = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=128,
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

    return EditJob(
        chat_id=chat_id,
        request=text,
        character=data.get("character"),
        style=style,
        effects=_STYLE_EFFECTS[style].model_copy(deep=True),
    )
