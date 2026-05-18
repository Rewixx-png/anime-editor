from .base import BaseEffect


class ShakeEffect(BaseEffect):
    def get_filter(self, intensity: float = 1.0, **kwargs) -> str:
        amp = max(4, int(20 * intensity))
        half = amp // 2
        return (
            f"scale=iw+{amp}:ih+{amp}:flags=fast_bilinear,"
            f"crop=iw-{amp}:ih-{amp}"
            f":x='{half}+{half}*sin(t*10*2*PI)'"
            f":y='{half//2}+{half//2}*cos(t*7*2*PI)'"
        )
