"""Small Timer utility used by transitions and other timed events."""
from __future__ import annotations
from typing import Optional, Callable


class Timer:
    def __init__(self, duration: float, callback: Optional[Callable] = None):
        self.duration = duration
        self.callback = callback
        self.elapsed = 0.0
        self.running = False

    def start(self):
        self.running = True
        self.elapsed = 0.0

    def stop(self):
        self.running = False

    def reset(self):
        self.elapsed = 0.0

    def update(self, dt: float):
        if not self.running:
            return
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.running = False
            if self.callback:
                try:
                    self.callback()
                except Exception:
                    pass

    def finished(self) -> bool:
        return not self.running and self.elapsed >= self.duration
