"""A minimal TitleScene for testing the application skeleton.

This scene will draw a simple title text using pygame when available.
"""
from src.game.scenes.base_scene import BaseScene
import logging

_logger = logging.getLogger("mystic_meadows.title_scene")


class TitleScene(BaseScene):
    def on_enter(self, context):
        _logger.info("Entering TitleScene")
        self.context = context
        self._font = None

        # Lazy import of pygame to avoid hard dependency during static analysis
        try:
            import pygame  # type: ignore

            # Use a default font; Application will have initialized pygame
            self._font = pygame.font.Font(None, 72)
        except Exception:
            _logger.debug("pygame not available for TitleScene rendering")
        self._small_font = None
        try:
            import pygame  # type: ignore

            self._small_font = pygame.font.Font(None, 36)
        except Exception:
            self._small_font = None
        # button rects will be computed on render
        self._button_rects = {}

    def on_exit(self):
        _logger.info("Exiting TitleScene")

    def handle_event(self, event):
        try:
            import pygame  # type: ignore
        except Exception:
            return

        # Handle mouse clicks to trigger buttons
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            for name, rect in list(self._button_rects.items()):
                if rect.collidepoint(pos):
                    if name == "start":
                        # push GameScene
                        from src.game.scenes.game_scene import GameScene

                        gs = GameScene()
                        # context is the Application instance which contains scene_manager
                        if hasattr(self.context, "scene_manager"):
                            self.context.scene_manager.push(gs, context=self.context)
                    elif name == "quit":
                        # signal application to stop
                        if hasattr(self.context, "running"):
                            self.context.running = False


    def update(self, dt: float):
        pass

    def render(self, surface):
        """Render a simple title to the provided pygame Surface.

        If pygame isn't available the call is a no-op.
        """
        if self._font is None:
            return
        try:
            import pygame  # type: ignore

            surface.fill((24, 96, 24))
            text_surf = self._font.render("Mystic Meadows", True, (255, 255, 255))
            tw, th = text_surf.get_size()
            sw, sh = surface.get_size()
            surface.blit(text_surf, ((sw - tw) // 2, (sh - th) // 2 - 80))

            # Draw buttons
            btn_w, btn_h = 240, 60
            start_rect = pygame.Rect((sw - btn_w) // 2, (sh // 2), btn_w, btn_h)
            quit_rect = pygame.Rect((sw - btn_w) // 2, (sh // 2) + btn_h + 16, btn_w, btn_h)
            mouse_pos = pygame.mouse.get_pos()

            def draw_button(rect, label):
                hovering = rect.collidepoint(mouse_pos)
                color = (200, 160, 60) if hovering else (160, 120, 24)
                pygame.draw.rect(surface, color, rect, border_radius=8)
                if self._small_font:
                    lbl = self._small_font.render(label, True, (0, 0, 0))
                    lw, lh = lbl.get_size()
                    surface.blit(lbl, (rect.x + (rect.w - lw) // 2, rect.y + (rect.h - lh) // 2))

            draw_button(start_rect, "Start Game")
            draw_button(quit_rect, "Quit")

            # store for event handling
            self._button_rects["start"] = start_rect
            self._button_rects["quit"] = quit_rect
        except Exception:
            _logger.exception("Error rendering TitleScene")
