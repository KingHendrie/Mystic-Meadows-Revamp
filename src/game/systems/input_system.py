"""Input system: translate pygame events into high level actions.

The skeleton supports mapping basic keyboard controls; in the real game this
would post events to EventBus.
"""
from typing import Tuple
import logging

_logger = logging.getLogger("mystic_meadows.input")


class InputSystem:
    def __init__(self):
        self._pressed = set()

    def update(self, events: Tuple[object, ...]) -> None:
        # events is expected to be a tuple/list of pygame events; callers manage import
        for ev in events:
            # Basic keyboard handling could be added here
            pass

    def is_key_pressed(self, key: str) -> bool:
        return key in self._pressed
