from .base import BaseEffect


class GrainEffect(BaseEffect):
    def get_filter(self, intensity: float = 0.5, style: str = "film", **kwargs) -> str:
        strength = max(3, int(18 * intensity))

        if style == "vhs":
            return (
                f"noise=alls={strength}:allf=t+u,"
                f"drawgrid=w=0:h=2:t=1:c=black@0.15,"
                f"hue=h='2*sin(t*8)':s='1+0.1*sin(t*13)'"
            )
        if style == "heavy":
            return (
                f"noise=c0s={strength}:c0f=t+u:c1s={strength//2}:c1f=t+u,"
                f"curves=master='0/0.02 0.5/0.5 1/0.98'"
            )
        return f"noise=alls={strength}:allf=t+u"
