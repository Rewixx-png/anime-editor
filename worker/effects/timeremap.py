from .base import BaseEffect


class TimeRemapEffect(BaseEffect):
    def get_filter(self, bpm: float = 120.0, intensity: float = 1.0, **kwargs) -> str:
        beat = 60.0 / max(60.0, bpm)
        depth = min(0.45, intensity * 0.35)
        return f"setpts='PTS*(1.0+{depth:.3f}*sin(6.28318*T/{beat:.4f}))'"

