from .base import BaseEffect


class MotionBlurEffect(BaseEffect):
    def get_filter(self, strength: float = 1.0, **kwargs) -> str:
        opacity = min(0.85, max(0.15, strength * 0.35))
        return f"tblend=all_mode=average:all_opacity={opacity:.2f}"
