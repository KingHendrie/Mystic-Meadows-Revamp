"""Convenience entrypoint for the game package.

Use `from src.game.main import run` for a simple entrypoint that constructs the
Application defined in `src.game.app`.
"""
from pathlib import Path
from typing import Optional


def run(assets_dir: Optional[Path] = None, data_dir: Optional[Path] = None, debug: bool = False, save_slot: int = 1):
    """Run the game application.

    This defers to `src.game.app.Application`.
    """
    from src.game.app import Application

    app = Application(assets_dir=assets_dir, data_dir=data_dir, debug=debug, save_slot=save_slot)
    try:
        app.run()
    finally:
        app.shutdown()


if __name__ == "__main__":
    run()
