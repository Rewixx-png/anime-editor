from .base import BaseEffect


class VignetteEffect(BaseEffect):
    def get_filter(self, intensity: float = 1.0, **kwargs) -> str:
        angle = min(0.9, max(0.2, intensity * 0.55))
        return f"vignette=angle={angle:.2f}:mode=forward"
