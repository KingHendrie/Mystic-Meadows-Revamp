"""Primary gameplay scene that integrates the Farm world manager.

This scene delegates update/render to `src.game.farm.Farm` which provides the
core simulation (player, soil, sprites, camera and simple audio).
"""
from src.game.scenes.base_scene import BaseScene
import logging

_logger = logging.getLogger("mystic_meadows.game_scene")


class GameScene(BaseScene):
    def on_enter(self, context):
        _logger.info("Entering GameScene")
        self.context = context
        try:
            from src.game.farm import Farm

            # Create farm using application paths
            assets_dir = getattr(context, "assets_dir", None)
            data_dir = getattr(context, "data_dir", None)
            window_size = getattr(context, "window_size", None)
            if window_size is None:
                self.farm = Farm(assets_dir, data_dir)
            else:
                self.farm = Farm(assets_dir, data_dir, window_size=window_size)
        except Exception:
            _logger.exception("Failed to initialize Farm; creating minimal fallback")
            from src.game.farm import Farm

            self.farm = Farm(getattr(context, "assets_dir", None), getattr(context, "data_dir", None))

    def on_exit(self):
        _logger.info("Exiting GameScene")

    def handle_event(self, event):
        # Basic Escape handling to return to the title
        try:
            import pygame  # type: ignore
        except Exception:
            return

        if getattr(event, "type", None) == pygame.KEYDOWN:
            if getattr(event, "key", None) == pygame.K_ESCAPE:
                if hasattr(self.context, "scene_manager"):
                    self.context.scene_manager.pop()

    def update(self, dt: float):
        try:
            import pygame  # type: ignore
            keys = pygame.key.get_pressed()
        except Exception:
            keys = None
        self.farm.update(dt, keys)
        self.farm.plant_collision()

    def render(self, surface):
        self.farm.render(surface)
