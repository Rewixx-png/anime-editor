from .base import BaseEffect


class SpeedLinesEffect(BaseEffect):
    def get_filter(self, intensity: float = 0.5, **kwargs) -> str:
        sigma = max(3, int(25 * intensity))
        return f"gblur=sigma={sigma}:sigmaV=2"
