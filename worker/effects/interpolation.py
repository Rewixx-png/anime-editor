from .base import BaseEffect


class FrameInterpolationEffect(BaseEffect):
    def get_filter(self, target_fps: int = 60, **kwargs) -> str:
        fps = max(30, min(120, target_fps))
        return f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
