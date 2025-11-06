"""Base scene interface for game scenes."""
from typing import Any


class BaseScene:
    def on_enter(self, context: Any) -> None:  # context can be the Application or scene manager
        raise NotImplementedError()

    def on_exit(self) -> None:
        raise NotImplementedError()

    def handle_event(self, event: object) -> None:
        raise NotImplementedError()

    def update(self, dt: float) -> None:
        raise NotImplementedError()

    def render(self, surface: object) -> None:
        raise NotImplementedError()
