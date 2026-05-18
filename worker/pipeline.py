import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from shared.models import EffectConfig
from worker.effects.blur import MotionBlurEffect
from worker.effects.chromatic import ChromaticEffect
from worker.effects.color import ColorEffect
from worker.effects.glitch import GlitchEffect
from worker.effects.shake import ShakeEffect
from worker.effects.zoom import ZoomPunchEffect


def _build_filter(effects: EffectConfig) -> str:
    parts: list[str] = []

    if effects.color_grade:
        parts.append(ColorEffect().get_filter(style=effects.color_style))
    if effects.chromatic:
        parts.append(ChromaticEffect().get_filter(offset=effects.chromatic_offset))
    if effects.shake:
        parts.append(ShakeEffect().get_filter(intensity=effects.shake_intensity))
    if effects.motion_blur:
        parts.append(MotionBlurEffect().get_filter(strength=effects.blur_strength))
    if effects.glitch:
        parts.append(GlitchEffect().get_filter(intensity=effects.glitch_intensity))
    if effects.zoom_punch:
        parts.append(ZoomPunchEffect().get_filter(intensity=effects.zoom_intensity))

    return ",".join(parts) if parts else "null"


def render(
    clips: list[Path],
    effects: EffectConfig,
    output: Path,
    music: Optional[Path] = None,
) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = _build_filter(effects)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")
        concat_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
        ]

        if music and music.exists():
            cmd += ["-i", str(music)]

        cmd += ["-vf", filter_chain, "-map", "0:v"]

        if music and music.exists():
            cmd += ["-map", "1:a", "-shortest"]
        else:
            cmd += ["-an"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return result.returncode == 0
    finally:
        os.unlink(concat_file)
