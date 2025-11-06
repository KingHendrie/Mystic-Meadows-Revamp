"""Lightweight launcher for Mystic Meadows.

Per project guidelines this should remain small and delegate to `src.game.app`.
"""
import sys
import argparse
import logging
from pathlib import Path


def ensure_data_dirs(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "saves").mkdir(exist_ok=True)
    (data_dir / "cache").mkdir(exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mystic Meadows launcher")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--save-slot", type=int, default=1)
    parser.add_argument("--reset-cache", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    logger = logging.getLogger("mystic_meadows.launcher")
    repo_root = Path(__file__).parent
    assets_dir = repo_root / "assets"
    data_dir = repo_root / "data"

    if not assets_dir.exists():
        logger.error("Missing assets/ directory. Ensure repository is intact.")
        sys.exit(1)

    ensure_data_dirs(data_dir)

    if args.reset_cache:
        logger.info("reset-cache requested: clearing data/cache/")
        # Precise confirmation omitted in automated launcher; implement interactive confirmation in tools.
        cache_dir = data_dir / "cache"
        for p in cache_dir.iterdir() if cache_dir.exists() else []:
            try:
                if p.is_file():
                    p.unlink()
            except Exception:
                logger.debug("Failed to remove cache file %s", p)

    try:
        # Defer import; this gives clearer errors if src/ is broken
        from src.game.app import Application

        app = Application(assets_dir=assets_dir, data_dir=data_dir, debug=args.debug, save_slot=args.save_slot)
        app.run()
    except Exception as e:
        logger.exception("Failed to start application: %s", e)
        raise


if __name__ == "__main__":
    main()
