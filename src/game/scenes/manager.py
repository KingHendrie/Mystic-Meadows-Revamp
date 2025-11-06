"""Simple SceneManager to push/pop scenes and forward events/updates/renders."""
from typing import Any, Optional


class SceneManager:
    def __init__(self):
        self._stack = []

    def push(self, scene, context: Any = None) -> None:
        scene.on_enter(context)
        self._stack.append(scene)

    def pop(self) -> None:
        if not self._stack:
            return
        scene = self._stack.pop()
        scene.on_exit()

    def current(self) -> Optional[object]:
        return self._stack[-1] if self._stack else None

    def handle_event(self, event: object) -> None:
        cur = self.current()
        if cur:
            cur.handle_event(event)

    def update(self, dt: float) -> None:
        cur = self.current()
        if cur:
            cur.update(dt)

    def render(self, surface) -> None:
        cur = self.current()
        if cur:
            cur.render(surface)
