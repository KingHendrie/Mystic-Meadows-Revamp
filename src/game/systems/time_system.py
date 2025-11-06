"""Basic TimeSystem: tracks in-game time and day progression and emits events.

This skeleton does not depend on an EventBus; it exposes callbacks registration.
"""
from typing import Callable, List
import logging

_logger = logging.getLogger("mystic_meadows.time")


class TimeSystem:
    def __init__(self, day_length_seconds: float = 600.0):
        self.day_length_seconds = float(day_length_seconds)
        self.time_of_day = 6.0
        self.day_number = 1
        self._day_end_listeners: List[Callable[[], None]] = []

    def update(self, dt_seconds: float) -> None:
        hours_per_second = 24.0 / max(1.0, self.day_length_seconds)
        self.time_of_day += dt_seconds * hours_per_second
        if self.time_of_day >= 24.0:
            self.time_of_day -= 24.0
            self.day_number += 1
            _logger.debug("Day ended; new day %d", self.day_number)
            for cb in list(self._day_end_listeners):
                try:
                    cb()
                except Exception:
                    _logger.exception("Error in day end listener")

    def get_time(self) -> float:
        return self.time_of_day

    def get_day(self) -> int:
        return self.day_number

    def subscribe_day_end(self, callback: Callable[[], None]) -> None:
        self._day_end_listeners.append(callback)
