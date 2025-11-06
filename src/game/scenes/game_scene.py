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
            # honor any selected save slot or pending load provided by TitleScene via context
            try:
                if hasattr(context, 'save_slot') and getattr(context, 'save_slot', None) is not None:
                    try:
                        self.farm.save_slot = int(context.save_slot)
                    except Exception:
                        pass
                if hasattr(context, 'pending_load') and getattr(context, 'pending_load', None) is not None:
                    try:
                        self.farm.load_from_payload(context.pending_load)
                    except Exception:
                        pass
                    # clear pending_load after consume
                    try:
                        delattr = getattr(context, '__dict__', None)
                        if delattr is not None and 'pending_load' in context.__dict__:
                            del context.__dict__['pending_load']
                    except Exception:
                        try:
                            del context.pending_load
                        except Exception:
                            pass
            except Exception:
                pass
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
        # forward events to farm menu when active so it can handle clicks
        try:
            if getattr(self, 'farm', None) is not None and getattr(self.farm, 'menu', None) is not None and self.farm.menu.active:
                try:
                    self.farm.menu.handle_event(event)
                except Exception:
                    pass
        except Exception:
            pass

        # If HUD debug overlay is active, forward events to its handler so debug buttons work
        try:
            if getattr(self, 'farm', None) is not None and getattr(self.farm, 'ui', None) is not None and getattr(self.farm.ui, 'show_debug', False):
                try:
                    self.farm.ui.handle_debug_event(event)
                except Exception:
                    pass
        except Exception:
            pass

        # Show controls overlay while Tab is held: KEYDOWN/KEYUP handling
        try:
            import pygame
            if getattr(event, 'type', None) in (pygame.KEYDOWN, pygame.KEYUP) and getattr(self, 'farm', None) is not None and getattr(self.farm, 'menu', None) is not None:
                if getattr(event, 'key', None) == pygame.K_TAB:
                    # KEYDOWN -> show; KEYUP -> hide
                    try:
                        self.farm.menu.show_controls = (event.type == pygame.KEYDOWN)
                    except Exception:
                        pass
        except Exception:
            pass

        # Basic Escape handling to return to the title
        if getattr(event, "type", None) == pygame.KEYDOWN:
            if getattr(event, "key", None) == pygame.K_ESCAPE:
                # Save game state before leaving the scene
                try:
                    if getattr(self, 'farm', None) is not None:
                        try:
                            # save to the farm's configured save_slot
                            self.farm.save_game()
                        except Exception:
                            pass
                except Exception:
                    pass
                if hasattr(self.context, "scene_manager"):
                    self.context.scene_manager.pop()

        # Mouse wheel / scroll to swap hotbar slots when not in menu
        try:
            # only allow hotbar cycling when farm exists and menu is not active
            farm = getattr(self, 'farm', None)
            menu_active = bool(farm and getattr(farm, 'menu', None) and farm.menu.active)
            import time
            now = time.time()
            # initialize last wheel time if missing
            if not hasattr(self, '_last_wheel_time'):
                self._last_wheel_time = 0.0
            cooldown = 0.08

            if farm is not None and not menu_active:
                player = getattr(farm, 'player', None)
                if getattr(event, 'type', None) == pygame.MOUSEWHEEL:
                    if now - self._last_wheel_time > cooldown and player is not None:
                        if getattr(event, 'y', 0) > 0:
                            player.selected_slot = (player.selected_slot - 1) % len(player.hotbar)
                        elif getattr(event, 'y', 0) < 0:
                            player.selected_slot = (player.selected_slot + 1) % len(player.hotbar)
                        self._last_wheel_time = now
                # Some platforms deliver wheel via MOUSEBUTTONDOWN with buttons 4/5
                if getattr(event, 'type', None) == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) in (4, 5):
                    if now - self._last_wheel_time > cooldown and player is not None:
                        if event.button == 4:
                            player.selected_slot = (player.selected_slot - 1) % len(player.hotbar)
                        elif event.button == 5:
                            player.selected_slot = (player.selected_slot + 1) % len(player.hotbar)
                        self._last_wheel_time = now
        except Exception:
            pass

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
