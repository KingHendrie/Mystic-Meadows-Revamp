"""Filesystem utility helpers."""
from pathlib import Path
import json


def ensure_dir_exists(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_json(path: Path, data: dict) -> None:
    # Small wrapper that writes JSON atomically. For complex needs reuse systems.save._save_atomic
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
    tmp.replace(path)
