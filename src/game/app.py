from __future__ import annotations

"""Application bootstrap and main loop for Mystic Meadows.

This is a minimal skeleton that sets up directories, basic systems and a
placeholder run loop. It intentionally keeps game logic in scenes and systems.
"""
from pathlib import Path
import logging
import time
from typing import Optional

from src.game.logger import configure_logging
from src.game.systems.save import ensure_data_dirs
from src.game.scenes.manager import SceneManager
from src.game.scenes.title_scene import TitleScene
from src.game.systems.time_system import TimeSystem
from src.game.systems.input_system import InputSystem


_logger = logging.getLogger("mystic_meadows.app")


class Application:
    def __init__(self, assets_dir: Optional[Path] = None, data_dir: Optional[Path] = None, debug: bool = False, save_slot: int = 1):
        self.debug = debug
        configure_logging(debug)
        self.assets_dir = Path(assets_dir) if assets_dir is not None else Path.cwd() / "assets"
        self.data_dir = Path(data_dir) if data_dir is not None else Path.cwd() / "data"
        self.save_slot = save_slot
        self.running = False

        # Systems
        self.time_system = TimeSystem()
        self.input_system = InputSystem()
        self.scene_manager = SceneManager()

        _logger.info("Application initialized. assets=%s data=%s", self.assets_dir, self.data_dir)

    def _check_environment(self) -> None:
        if not self.assets_dir.exists():
            _logger.error("Missing assets/ directory: %s", self.assets_dir)
            raise FileNotFoundError("assets/ directory not found")

    def run(self) -> None:
        """Start a minimal pygame-backed main loop that renders the TitleScene.

        This provides a visible window for development. Replace with full SceneManager
        integrations and proper systems initialization in the real game.
        """
        self._check_environment()
        ensure_data_dirs(self.data_dir)

        # Try to import and initialize pygame
        try:
            import pygame  # type: ignore

            pygame.init()
            pygame.font.init()
        except Exception as e:
            _logger.exception("Failed to initialize pygame: %s", e)
            raise

        # Create window
        from src.game.config import DEFAULT_WINDOW_SIZE

        screen = pygame.display.set_mode(DEFAULT_WINDOW_SIZE)
        pygame.display.set_caption("Mystic Meadows - Skeleton")
        clock = pygame.time.Clock()

        # Push initial TitleScene
        title = TitleScene()
        self.scene_manager.push(title, context=self)

        self.running = True
        try:
            while self.running:
                dt = clock.tick(60) / 1000.0
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.running = False
                    else:
                        self.scene_manager.handle_event(ev)

                # Update systems
                self.time_system.update(dt)
                self.scene_manager.update(dt)

                # Render
                self.scene_manager.render(screen)
                pygame.display.flip()
        except Exception:
            _logger.exception("Unhandled exception in main loop")
        finally:
            try:
                pygame.quit()
            except Exception:
                pass

    def shutdown(self) -> None:
        _logger.info("Shutting down application")
