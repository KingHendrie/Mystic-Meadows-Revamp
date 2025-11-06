"""Simple logging configuration for Mystic Meadows.

Provide a small helper to configure global logging with debug vs info levels.
"""
import logging


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)5s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt)
