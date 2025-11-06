"""Simple publish/subscribe in-process event bus.

This is intentionally tiny: subscribe by event_type (string) and receive
callables with a single positional argument (the event object).
"""
from typing import Callable, Dict, List, Any
import logging

_logger = logging.getLogger("mystic_meadows.event_bus")


class EventBus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        self._subs.setdefault(event_type, []).append(callback)
        _logger.debug("Subscribed %s to %s", callback, event_type)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        listeners = self._subs.get(event_type)
        if listeners and callback in listeners:
            listeners.remove(callback)

    def post(self, event_type: str, event: Any = None) -> None:
        for cb in list(self._subs.get(event_type, [])):
            try:
                cb(event)
            except Exception:
                _logger.exception("Error dispatching event %s to %s", event_type, cb)
