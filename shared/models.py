from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, Field


class EditStyle(str, Enum):
    AGGRESSIVE = "aggressive"
    SMOOTH = "smooth"
    DARK = "dark"
    LOFI = "lofi"


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class EffectConfig(BaseModel):
    shake: bool = False
    shake_intensity: float = 1.0
    motion_blur: bool = False
    blur_strength: float = 1.0
    color_grade: bool = False
    color_style: str = "anime"
    chromatic: bool = False
    chromatic_offset: int = 3
    glitch: bool = False
    glitch_intensity: float = 0.5
    zoom_punch: bool = False
    zoom_intensity: float = 1.2
    time_remap: bool = False
    interpolate: bool = False
    interpolate_fps: int = 60
    vignette: bool = False
    vignette_intensity: float = 1.0
    grain: bool = False
    grain_intensity: float = 0.5
    grain_style: str = "film"
    speed_lines: bool = False
    speed_lines_intensity: float = 0.5


class EditJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    chat_id: int
    request: str
    character: Optional[str] = None
    style: EditStyle = EditStyle.AGGRESSIVE
    clip_urls: list[str] = Field(default_factory=list)
    music_file_id: Optional[str] = None
    music_start: Optional[float] = None
    music_end: Optional[float] = None
    bpm: Optional[int] = None
    drops: list[float] = Field(default_factory=list)
    effects: EffectConfig = Field(default_factory=EffectConfig)
    result_path: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobUpdate(BaseModel):
    status: JobStatus
    result_path: Optional[str] = None
    error_msg: Optional[str] = None
