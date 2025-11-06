"""Simple resource helpers: import_folder and image caching.

This is a lightweight implementation used by the sprites module to
load animation frames from a folder. It returns a list of pygame.Surface
objects sorted by filename.
"""
from __future__ import annotations
from pathlib import Path
import pygame
from typing import List
import logging

_cache: dict = {}


def import_folder(folder: Path | str) -> List[pygame.Surface]:
    p = Path(folder)
    key = str(p)
    if key in _cache:
        return _cache[key]
    frames: List[pygame.Surface] = []
    if not p.exists() or not p.is_dir():
        return frames
    # sort by name for deterministic order
    files = sorted([x for x in p.iterdir() if x.suffix.lower() in ('.png', '.jpg', '.bmp')])
    for f in files:
        try:
            img = pygame.image.load(str(f)).convert_alpha()
            frames.append(img)
        except Exception:
            # skip files that fail to load
            continue
    _cache[key] = frames
    return frames
_logger = logging.getLogger("mystic_meadows.resources")


class ResourceManager:
    def __init__(self, assets_dir: Path | None = None):
        self.assets_dir = Path(assets_dir) if assets_dir is not None else Path.cwd() / "assets"
        self._images = {}
        self._fonts = {}

    def resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.assets_dir / path
        if not p.exists():
            _logger.error("Asset not found: %s", p)
            raise FileNotFoundError(f"Asset not found: {p}")
        return p

    def load_image(self, key: str, path: str):
        p = self.resolve(path)
        self._images[key] = p
        return p

    def get_image_path(self, key: str) -> Path:
        return self._images[key]


_default_manager: ResourceManager | None = None


def get_default_manager(assets_dir: Path | None = None) -> ResourceManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ResourceManager(assets_dir)
    return _default_manager
