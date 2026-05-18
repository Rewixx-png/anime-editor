from .base import BaseEffect


class ZoomPunchEffect(BaseEffect):
    def get_filter(self, intensity: float = 1.2, **kwargs) -> str:
        z = max(1.05, min(1.6, intensity))
        return (
            f"zoompan="
            f"z='if(lte(mod(n,30),3),{z:.2f},1)':"
            f"d=1:"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)'"
        )
