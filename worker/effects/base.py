from abc import ABC, abstractmethod


class BaseEffect(ABC):
    @abstractmethod
    def get_filter(self, **kwargs) -> str:
        pass
