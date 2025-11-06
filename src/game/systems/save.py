from __future__ import annotations

"""Transactional save/load helpers for Mystic Meadows.

Features:
- Discover or create the project `data/` folder.
- Ensure standard subfolders exist (saves, cache).
- Atomic save writes using a temporary file + fsync + os.replace.
- Keep a .bak of previous save on successful replace.
- Safe load with fallback to .bak if the main file is corrupted.

This module intentionally does not alter assets/ and only writes to data/.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import os
import shutil
import tempfile
import time
from typing import Any, Dict, Optional, List


class SaveError(Exception):
    pass


class LoadError(Exception):
    pass


def _find_repo_root(start: Optional[Path] = None) -> Path:
    """Find the repository root by searching upwards for a `data` directory or stop at filesystem root.

    If `start` is None the current working directory is used.
    """
    cur = (Path(start) if start is not None else Path.cwd()).resolve()
    for p in [cur] + list(cur.parents):
        if (p / "data").exists():
            return p
    # fallback to current working directory
    return cur


def get_data_dir(start_search: Optional[Path] = None) -> Path:
    """Return the path to the persistent `data/` directory.

    This will not create the directory. Use ensure_data_dirs() to create subfolders.
    """
    repo_root = _find_repo_root(start_search)
    return repo_root / "data"


def ensure_data_dirs(start_search: Optional[Path] = None) -> Path:
    """Ensure `data/` and required subfolders (saves, cache) exist and return the data dir path.

    This should be called during game startup.
    """
    data_dir = get_data_dir(start_search)
    # If data_dir doesn't exist, create it in the repo root (first-run)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "saves").mkdir(exist_ok=True)
    (data_dir / "cache").mkdir(exist_ok=True)
    (data_dir / "settings").mkdir(exist_ok=True)
    return data_dir


def _save_atomic(target_path: Path, data_bytes: bytes) -> None:
    """Write bytes to target_path atomically with fsync and replace.

    Steps:
    - Write to a temp file in the same directory.
    - Flush and fsync.
    - Rename/replace the target atomically.
    """
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    fd = None
    tmp_path = None
    try:
        # Create a secure temporary file in the same directory to allow atomic replace
        fd, tmp_path = tempfile.mkstemp(prefix=target_path.name, dir=str(target_dir))
        with os.fdopen(fd, "wb") as f:
            fd = None
            f.write(data_bytes)
            f.flush()
            os.fsync(f.fileno())
        # At this point tmp_path contains the fully written file. Replace target atomically.
        # Keep a backup of the existing file if present
        if target_path.exists():
            bak = target_path.with_suffix(target_path.suffix + ".bak")
            # Overwrite existing bak
            shutil.copy2(target_path, bak)
        os.replace(tmp_path, target_path)
    except Exception as e:
        raise SaveError(f"Atomic save failed: {e}")
    finally:
        # cleanup tmp file if it still exists
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path is not None and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _serialize_save(data: Dict[str, Any], version: int = 1) -> bytes:
    envelope = {
        "metadata": {
            "version": version,
            "timestamp": int(time.time()),
        },
        "payload": data,
    }
    return json.dumps(envelope, indent=2, ensure_ascii=False).encode("utf-8")


def save_game(slot: str, data: Dict[str, Any], start_search: Optional[Path] = None) -> Path:
    """Save `data` to `data/saves/<slot>.json` atomically and keep a .bak of the prior save.

    slot: name of save file (without extension). Example: 'save_slot_1' or 'player1'.
    Returns the Path to the saved file.
    """
    data_dir = ensure_data_dirs(start_search)
    saves_dir = data_dir / "saves"
    saves_dir.mkdir(parents=True, exist_ok=True)
    target = saves_dir / f"{slot}.json"
    payload = _serialize_save(data)
    _save_atomic(target, payload)
    return target


def load_game(slot: str, start_search: Optional[Path] = None) -> Dict[str, Any]:
    """Load a save file from `data/saves/<slot>.json`.

    If the primary save is corrupted and a .bak exists, the .bak will be loaded.
    Raises LoadError if both attempts fail.
    """
    data_dir = get_data_dir(start_search)
    target = data_dir / "saves" / f"{slot}.json"
    bak = target.with_suffix(target.suffix + ".bak")

    def _read(path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
            # Simple validation
            if not isinstance(obj, dict) or "payload" not in obj:
                raise LoadError("Invalid save file structure")
            return obj
        except Exception as e:
            raise LoadError(f"Failed to read save '{path}': {e}")

    if target.exists():
        try:
            return _read(target)
        except LoadError:
            # Try fallback
            if bak.exists():
                try:
                    return _read(bak)
                except LoadError as e:
                    raise LoadError(f"Both save and backup are invalid: {e}")
            raise
    else:
        raise LoadError(f"Save not found: {target}")


def list_saves(start_search: Optional[Path] = None) -> List[Path]:
    data_dir = get_data_dir(start_search)
    saves_dir = data_dir / "saves"
    if not saves_dir.exists():
        return []
    return sorted([p for p in saves_dir.iterdir() if p.suffix == ".json"])


def delete_save(slot: str, start_search: Optional[Path] = None) -> None:
    data_dir = get_data_dir(start_search)
    target = data_dir / "saves" / f"{slot}.json"
    bak = target.with_suffix(target.suffix + ".bak")
    for p in (target, bak):
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            raise SaveError(f"Failed to delete {p}: {e}")
