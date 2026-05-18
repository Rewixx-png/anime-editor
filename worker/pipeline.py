import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

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

log = logging.getLogger(__name__)

_TIME_RE = re.compile(r"time=(\d+):(\d+):([\d.]+)")


def _get_video_size(path: Path) -> tuple[int, int]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 0, 0


def _build_filter(effects: WorkerEffects, bpm: Optional[int] = None, video_size: tuple[int, int] = (0, 0)) -> str:
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
        parts.append(ZoomPunchEffect().get_filter(
            intensity=effects.zoom_intensity,
            video_width=video_size[0],
            video_height=video_size[1],
        ))
    if effects.speed_lines:
        parts.append(SpeedLinesEffect().get_filter(intensity=effects.speed_lines_intensity))
    if effects.vignette:
        parts.append(VignetteEffect().get_filter(intensity=effects.vignette_intensity))
    if effects.grain:
        parts.append(GrainEffect().get_filter(intensity=effects.grain_intensity, style=effects.grain_style))

    return ",".join(parts) if parts else "copy"


def _parse_seconds(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def render(
    clips: list[Path],
    effects: WorkerEffects,
    output: Path,
    music: Optional[Path] = None,
    music_start: Optional[float] = None,
    music_end: Optional[float] = None,
    bpm: Optional[int] = None,
    on_progress: Optional[Callable[[float], None]] = None,
) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    video_size = _get_video_size(clips[0]) if clips else (0, 0)
    filter_chain = _build_filter(effects, bpm=bpm, video_size=video_size)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")
        concat_file = f.name

    try:
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file]

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
                "-filter_complex", audio_filter,
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
            "-stats_period", "3",
            str(output),
        ]

        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        last_report = 0.0
        stderr_lines: list[str] = []

        for line in proc.stderr:
            stderr_lines.append(line)
            m = _TIME_RE.search(line)
            if m and on_progress:
                secs = _parse_seconds(m.group(1), m.group(2), m.group(3))
                if secs - last_report >= 5.0:
                    on_progress(secs)
                    last_report = secs

        proc.wait(timeout=600)
        if proc.returncode != 0:
            log.error("FFmpeg failed (rc=%d):\n%s", proc.returncode,
                      "".join(stderr_lines[-30:]))
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        log.error("FFmpeg timed out")
        return False
    finally:
        os.unlink(concat_file)
