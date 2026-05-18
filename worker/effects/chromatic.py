from .base import BaseEffect


class ChromaticEffect(BaseEffect):
    def get_filter(self, offset: int = 3, **kwargs) -> str:
        o = max(1, abs(offset))
        return f"rgbashift=rh={o}:rv=0:bh=-{o}:bv=0"
