"""Configuration defaults and constants for the game.

Keep this file light — use constants and a small Config dataclass if needed.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


DEFAULT_TILE_SIZE: Tuple[int, int] = (48, 48)
DEFAULT_WINDOW_SIZE: Tuple[int, int] = (960, 640)
DEFAULT_DAY_LENGTH_SECONDS: int = 600  # 10 minutes per in-game day by default


@dataclass
class Config:
    assets_dir: Path
    data_dir: Path
    window_size: Tuple[int, int] = DEFAULT_WINDOW_SIZE
    tile_size: Tuple[int, int] = DEFAULT_TILE_SIZE
    day_length_seconds: int = DEFAULT_DAY_LENGTH_SECONDS
