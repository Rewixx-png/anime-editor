from .base import BaseEffect


class SpeedLinesEffect(BaseEffect):
    def get_filter(self, intensity: float = 0.5, **kwargs) -> str:
        blur_w = max(5, int(30 * intensity))
        blur_h = max(1, int(3 * intensity))
        opacity = min(0.6, intensity * 0.5)
        return (
            f"split[base][blur];"
            f"[blur]boxblur={blur_w}:{blur_h}[blurred];"
            f"[base][blurred]blend=all_mode=overlay:all_opacity={opacity:.2f}"
        )
