import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from shared.worker_models import WorkerEffects
from worker.effects.blur import MotionBlurEffect
from worker.effects.chromatic import ChromaticEffect
from worker.effects.color import ColorEffect
from worker.effects.glitch import GlitchEffect
from worker.effects.grain import GrainEffect
from worker.effects.interpolation import FrameInterpolationEffect
from worker.effects.shake import ShakeEffect
from worker.effects.speedlines import SpeedLinesEffect
from worker.effects.timeremap import TimeRemapEffect
from worker.effects.vignette import VignetteEffect
from worker.effects.zoom import ZoomPunchEffect


def _build_filter(effects: WorkerEffects, bpm: Optional[int] = None) -> str:
    parts: list[str] = []

    if effects.interpolate:
        parts.append(FrameInterpolationEffect().get_filter(target_fps=effects.interpolate_fps))

    if effects.time_remap:
        parts.append(TimeRemapEffect().get_filter(bpm=float(bpm or 120)))

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

    if effects.speed_lines:
        parts.append(SpeedLinesEffect().get_filter(intensity=effects.speed_lines_intensity))

    if effects.vignette:
        parts.append(VignetteEffect().get_filter(intensity=effects.vignette_intensity))

    if effects.grain:
        parts.append(GrainEffect().get_filter(intensity=effects.grain_intensity, style=effects.grain_style))

    return ",".join(parts) if parts else "null"


def render(
    clips: list[Path],
    effects: WorkerEffects,
    output: Path,
    music: Optional[Path] = None,
    music_start: Optional[float] = None,
    music_end: Optional[float] = None,
    bpm: Optional[int] = None,
) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = _build_filter(effects, bpm=bpm)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")
        concat_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
        ]

        has_music = music and music.exists()
        if has_music:
            cmd += ["-i", str(music)]

        if has_music and (music_start is not None or music_end is not None):
            start = music_start or 0.0
            audio_filter = f"[1:a]atrim=start={start:.3f}"
            if music_end is not None:
                audio_filter += f":end={music_end:.3f}"
            audio_filter += ",asetpts=PTS-STARTPTS[aout]"
            cmd += [
                "-filter_complex", f"{audio_filter}",
                "-vf", filter_chain,
                "-map", "0:v",
                "-map", "[aout]",
                "-shortest",
            ]
        else:
            cmd += ["-vf", filter_chain, "-map", "0:v"]
            if has_music:
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
