"""Higher-level SaveSystem that wraps the lower-level transactional helpers.

Provides methods the rest of the app can call (save/load/auto_save).
"""
from __future__ import annotations

from pathlib import Path
import logging
from typing import Any, Dict

from src.game.systems import save as save_helpers

_logger = logging.getLogger("mystic_meadows.save_system")


class SaveSystem:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        save_helpers.ensure_data_dirs(self.data_dir)

    def save(self, slot: int, state: Dict[str, Any]) -> Path:
        slot_name = f"save_slot_{slot}"
        _logger.info("Saving slot=%s", slot_name)
        path = save_helpers.save_game(slot_name, state, start_search=self.data_dir.parent)
        _logger.info("Saved to %s", path)
        return path

    def load(self, slot: int) -> Dict[str, Any]:
        slot_name = f"save_slot_{slot}"
        _logger.info("Loading slot=%s", slot_name)
        obj = save_helpers.load_game(slot_name, start_search=self.data_dir.parent)
        return obj

    def auto_save(self, state: Dict[str, Any], slot: int = 1) -> Path:
        _logger.info("Auto-saving slot=%s", slot)
        return self.save(slot, state)
