from .base import BaseEffect


class GlitchEffect(BaseEffect):
    def get_filter(self, intensity: float = 0.5, **kwargs) -> str:
        noise_strength = max(5, int(25 * intensity))
        shift = max(1, int(6 * intensity))
        return (
            f"noise=alls={noise_strength}:allf=t+u,"
            f"rgbshift=rh={shift}:bh=-{shift}"
        )
