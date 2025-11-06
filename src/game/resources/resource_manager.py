"""Minimal ResourceManager: loads and caches images, fonts and sounds.

This is a thin skeleton intended for development. It provides helpful errors
if assets are missing and caches surfaces by key.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

_logger = logging.getLogger("mystic_meadows.resources")


class ResourceManager:
    def __init__(self, assets_dir: Optional[Path] = None):
        self.assets_dir = Path(assets_dir) if assets_dir is not None else Path.cwd() / "assets"
        self._images: Dict[str, Path] = {}
        self._fonts: Dict[str, Path] = {}
        # Sounds and other resources can be added similarly

    def resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.assets_dir / path
        if not p.exists():
            _logger.error("Asset not found: %s", p)
            raise FileNotFoundError(f"Asset not found: {p}")
        return p

    def load_image(self, key: str, path: str, tile_size: Optional[Tuple[int, int]] = None):
        p = self.resolve(path)
        # We don't import pygame here to keep the manager lightweight; callers can load
        # surfaces using pygame.image.load(p) or similar. We store the resolved path.
        self._images[key] = p
        return p

    def get_image_path(self, key: str) -> Path:
        return self._images[key]


_default_manager: Optional[ResourceManager] = None


def get_default_manager(assets_dir: Optional[Path] = None) -> ResourceManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ResourceManager(assets_dir)
    return _default_manager
