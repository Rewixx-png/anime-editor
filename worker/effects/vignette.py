from .base import BaseEffect


class VignetteEffect(BaseEffect):
    def get_filter(self, intensity: float = 1.0, **kwargs) -> str:
        angle = min(1.8, max(0.5, intensity * 1.2))
        return f"vignette=angle={angle:.2f}:mode=forward"
