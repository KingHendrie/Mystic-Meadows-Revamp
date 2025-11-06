"""Heads-up display skeleton."""
import logging

_logger = logging.getLogger("mystic_meadows.ui.hud")


class HUD:
    def __init__(self):
        self.visible = True

    def update(self, dt: float):
        pass

    def render(self, surface):
        # In a real game we'd draw text and icons here
        pass
