"""Minimal data loader: reads JSON definition files from data/ or assets/.

This is a small helper to demonstrate the structure — expand with dataclasses
and proper validation in the real project.
"""
from pathlib import Path
import json
import logging

_logger = logging.getLogger("mystic_meadows.data.loader")


def load_json(path: Path, fallback: Path = None):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    if fallback is not None and fallback.exists():
        _logger.info("Using fallback for %s", path)
        with fallback.open("r", encoding="utf-8") as f:
            return json.load(f)
    _logger.warning("Definition not found: %s", path)
    return None
