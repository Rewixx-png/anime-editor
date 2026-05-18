import logging
import math
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


def _get_video_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        val = r.stdout.strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def _write_concat(
    f,
    clips: list[Path],
    bpm: Optional[float],
    music_duration: float,
) -> None:
    f.write("ffconcat version 1.0\n\n")

    if bpm and music_duration > 2.0:
        beat = 60.0 / max(60.0, bpm)
        cut_interval = beat * 2
        n_cuts = math.ceil(music_duration / cut_interval)
        src_durations = [_get_video_duration(c) for c in clips]
        log.info("Beat edit: %d cuts @ %.3fs each, total %.1fs", n_cuts, cut_interval, music_duration)

        for i in range(n_cuts):
            src_idx = i % len(clips)
            src = clips[src_idx]
            src_dur = src_durations[src_idx]
            if src_dur < 0.1:
                continue
            start = (i / n_cuts) * max(0.0, src_dur - cut_interval)
            end = min(src_dur, start + cut_interval)
            if end - start < 0.05:
                continue
            f.write(f"file '{src.absolute()}'\n")
            f.write(f"inpoint {start:.3f}\n")
            f.write(f"outpoint {end:.3f}\n\n")
    else:
        write_clips = clips
        if music_duration > 2.0:
            total = sum(_get_video_duration(c) for c in clips)
            if 0 < total < music_duration:
                loops = math.ceil(music_duration / total)
                write_clips = clips * loops
                log.info("Looping clips x%d to fill %.1fs", loops, music_duration)
        for clip in write_clips:
            f.write(f"file '{clip.absolute()}'\n")


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

    music_duration = 0.0
    if music_start is not None and music_end is not None:
        music_duration = music_end - music_start
    elif music_end is not None:
        music_duration = music_end

    video_size = _get_video_size(clips[0]) if clips else (0, 0)
    filter_chain = _build_filter(effects, bpm=bpm, video_size=video_size)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        _write_concat(f, clips, float(bpm) if bpm else None, music_duration)
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
