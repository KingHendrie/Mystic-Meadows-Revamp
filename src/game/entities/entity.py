"""Base Entity class used by gameplay entities."""
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Entity:
    id: str
    x: float = 0.0
    y: float = 0.0

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        pass
