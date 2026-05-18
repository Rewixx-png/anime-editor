from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkerEffects:
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

    @classmethod
    def from_dict(cls, d: dict) -> "WorkerEffects":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


@dataclass
class WorkerJob:
    id: str
    chat_id: int
    request: str
    style: str
    clip_urls: list
    effects: WorkerEffects
    music_file_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "WorkerJob":
        return cls(
            id=d["id"],
            chat_id=d["chat_id"],
            request=d["request"],
            style=d.get("style", "aggressive"),
            clip_urls=d.get("clip_urls", []),
            effects=WorkerEffects.from_dict(d.get("effects", {})),
            music_file_id=d.get("music_file_id"),
        )


@dataclass
class WorkerUpdate:
    status: str
    result_path: Optional[str] = None
    error_msg: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}
