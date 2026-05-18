from .base import BaseEffect

_PRESETS: dict[str, str] = {
    "anime": (
        "curves=red='0/0 0.5/0.55 1/1':blue='0/0 0.5/0.62 1/1',"
        "eq=saturation=1.3:contrast=1.1"
    ),
    "dark": (
        "eq=contrast=1.4:brightness=-0.08:saturation=1.2,"
        "curves=master='0/0 0.5/0.35 1/0.85'"
    ),
    "warm": (
        "colorbalance=rs=0.1:gs=0:bs=-0.15:rm=0.05:gm=0:bm=-0.1,"
        "eq=saturation=1.1"
    ),
    "cinematic": (
        "curves=master='0/0.03 0.5/0.5 1/0.97'"
        ":red='0/0 0.5/0.55 1/1'"
        ":blue='0/0.02 0.5/0.48 1/0.95'"
    ),
}


class ColorEffect(BaseEffect):
    def get_filter(self, style: str = "anime", **kwargs) -> str:
        return _PRESETS.get(style, _PRESETS["anime"])
