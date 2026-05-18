from .base import BaseEffect


class ZoomPunchEffect(BaseEffect):
    def get_filter(self, intensity: float = 1.2, video_width: int = 0, video_height: int = 0, **kwargs) -> str:
        z = max(1.05, min(1.6, intensity))
        size = f"s={video_width}x{video_height}:" if video_width and video_height else ""
        return (
            f"zoompan="
            f"z='if(lte(mod(in,30),3),{z:.2f},1)':"
            f"d=1:"
            f"{size}"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)'"
        )
