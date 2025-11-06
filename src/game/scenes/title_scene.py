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
        self._show_controls = False
        # menu modes: 'main', 'select_slot_new', 'select_slot_load', 'confirm_overwrite'
        self._mode = 'main'
        self._slot_count = 4
        self._slot_rects = {}
        self._chosen_slot = None
        # SaveSystem helper to list/load saves
        try:
            from src.game.systems.save_system import SaveSystem
            self._save_system = SaveSystem(getattr(self.context, 'data_dir', None) or '.')
        except Exception:
            self._save_system = None
        try:
            from src.game.systems import save as save_helpers
            self._save_helpers = save_helpers
        except Exception:
            self._save_helpers = None

    def on_exit(self):
        _logger.info("Exiting TitleScene")

    def handle_event(self, event):
        try:
            import pygame  # type: ignore
        except Exception:
            return

        # Allow keyboard cancellation of modal dialogs (slot select / confirm)
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                # If controls overlay is shown, hide it first
                if getattr(self, '_show_controls', False):
                    self._show_controls = False
                    return
                # If in any non-main mode, return to main menu
                if self._mode in ('select_slot_new', 'select_slot_load'):
                    self._mode = 'main'
                    self._chosen_slot = None
                    return
                if self._mode == 'confirm_overwrite':
                    # cancel overwrite back to slot select
                    self._mode = 'select_slot_new'
                    self._chosen_slot = None
                    return

        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            # If controls overlay is open, close it when clicking outside the overlay
            if getattr(self, '_show_controls', False):
                try:
                    surf = pygame.display.get_surface()
                    if surf is not None:
                        sw, sh = surf.get_size()
                        box_w, box_h = 560, 320
                        bx = sw // 2 - box_w // 2
                        by = sh // 2 - box_h // 2
                        panel_rect = pygame.Rect(bx, by, box_w, box_h)
                        if not panel_rect.collidepoint(pos):
                            self._show_controls = False
                            return
                        # if click inside panel, check if user clicked the visible Close button
                        close_rect = self._button_rects.get('close_controls')
                        if close_rect and close_rect.collidepoint(pos):
                            self._show_controls = False
                            return
                        # otherwise consume the click so it doesn't fall through to other UI
                        return
                except Exception:
                    # safest fallback: hide controls
                    self._show_controls = False
                    return
            # Mode: main menu buttons
            if self._mode == 'main':
                for name, rect in list(self._button_rects.items()):
                    if rect.collidepoint(pos):
                        if name == "start":
                            # enter slot selection for new game
                            self._mode = 'select_slot_new'
                            return
                        if name == "load":
                            # enter slot selection for load
                            self._mode = 'select_slot_load'
                            return
                        if name == "quit":
                            # signal application to stop
                            if hasattr(self.context, "running"):
                                self.context.running = False
                            return
                        if name == "controls":
                            # toggle a simple controls overlay
                            self._show_controls = not self._show_controls
                            return

            # Mode: selecting a slot for new game
            if self._mode in ('select_slot_new', 'select_slot_load'):
                clicked_on_slot = False
                # if user clicked the visible Close button inside the slot panel, cancel
                close_btn = self._button_rects.get('close_slots')
                if close_btn and close_btn.collidepoint(pos):
                    self._mode = 'main'
                    self._chosen_slot = None
                    return
                for i, rect in list(self._slot_rects.items()):
                    if rect.collidepoint(pos):
                        clicked_on_slot = True
                        slot_num = int(i)
                        # check if save exists for slot
                        has = False
                        try:
                            if self._save_helpers is not None:
                                lst = self._save_helpers.list_saves(getattr(self.context, 'data_dir', None))
                                names = [p.stem for p in lst]
                                has = f"save_slot_{slot_num}" in names
                        except Exception:
                            has = False
                        if self._mode == 'select_slot_new':
                            if has:
                                # ask to overwrite
                                self._chosen_slot = slot_num
                                self._mode = 'confirm_overwrite'
                                return
                            else:
                                # start new game using this slot
                                try:
                                    self.context.save_slot = slot_num
                                except Exception:
                                    pass
                                from src.game.scenes.game_scene import GameScene
                                gs = GameScene()
                                if hasattr(self.context, "scene_manager"):
                                    self.context.scene_manager.push(gs, context=self.context)
                                return
                        else:
                            # load existing save if present
                            if not has:
                                return
                            # perform load via SaveSystem, then start game with pending_load
                            try:
                                if self._save_system is not None:
                                    obj = self._save_system.load(slot_num)
                                    payload = obj.get('payload', obj)
                                    try:
                                        self.context.pending_load = payload
                                    except Exception:
                                        pass
                                    try:
                                        self.context.save_slot = slot_num
                                    except Exception:
                                        pass
                                    from src.game.scenes.game_scene import GameScene
                                    gs = GameScene()
                                    if hasattr(self.context, "scene_manager"):
                                        self.context.scene_manager.push(gs, context=self.context)
                            except Exception:
                                pass
                            return
                # If we clicked the panel but not on any slot (or clicked outside), treat as cancel
                if not clicked_on_slot:
                    # revert to main menu
                    self._mode = 'main'
                    self._chosen_slot = None
                    return

            # Mode: confirm overwrite (Yes/No)
            if self._mode == 'confirm_overwrite':
                # yes/no buttons stored in _button_rects under 'yes_overwrite'/'no_overwrite'
                yes = self._button_rects.get('yes_overwrite')
                no = self._button_rects.get('no_overwrite')
                if yes and yes.collidepoint(pos):
                    # confirm: set context.save_slot and start game
                    try:
                        self.context.save_slot = int(self._chosen_slot)
                    except Exception:
                        pass
                    from src.game.scenes.game_scene import GameScene
                    gs = GameScene()
                    if hasattr(self.context, "scene_manager"):
                        self.context.scene_manager.push(gs, context=self.context)
                    return
                if no and no.collidepoint(pos):
                    # cancel overwrite, go back to slot select
                    self._mode = 'select_slot_new'
                    self._chosen_slot = None
                    return


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
            load_rect = pygame.Rect((sw - btn_w) // 2, start_rect.y + btn_h + 8, btn_w, btn_h)
            controls_rect = pygame.Rect((sw - btn_w) // 2, load_rect.y + btn_h + 8, btn_w, btn_h)
            quit_rect = pygame.Rect((sw - btn_w) // 2, controls_rect.y + btn_h + 8, btn_w, btn_h)
            mouse_pos = pygame.mouse.get_pos()

            def draw_button(rect, label):
                hovering = rect.collidepoint(mouse_pos)
                color = (200, 160, 60) if hovering else (160, 120, 24)
                pygame.draw.rect(surface, color, rect, border_radius=8)
                if self._small_font:
                    lbl = self._small_font.render(label, True, (0, 0, 0))
                    lw, lh = lbl.get_size()
                    surface.blit(lbl, (rect.x + (rect.w - lw) // 2, rect.y + (rect.h - lh) // 2))

            # compute a controls and quit button below the start button without overlap
            draw_button(start_rect, "Start Game")
            draw_button(load_rect, "Load Game")
            draw_button(controls_rect, "Controls")
            draw_button(quit_rect, "Quit")

            # store for event handling
            self._button_rects["start"] = start_rect
            self._button_rects["load"] = load_rect
            self._button_rects["controls"] = controls_rect
            self._button_rects["quit"] = quit_rect

            # If we're in slot-selection mode, render the slot panel
            if self._mode in ('select_slot_new', 'select_slot_load'):
                try:
                    panel_w, panel_h = 420, 300
                    px = sw // 2 - panel_w // 2
                    py = sh // 2 - panel_h // 2
                    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                    panel.fill((8, 8, 8, 220))
                    surface.blit(panel, (px, py))
                    title = "Select Save Slot to " + ("Load" if self._mode == 'select_slot_load' else "Start New")
                    surface.blit(self._small_font.render(title, True, (240, 240, 240)), (px + 12, py + 12))

                    # gather save list info
                    existing = set()
                    if self._save_helpers is not None:
                        try:
                            lst = self._save_helpers.list_saves(getattr(self.context, 'data_dir', None))
                            names = [p.stem for p in lst]
                            for n in names:
                                if n.startswith('save_slot_'):
                                    try:
                                        idx = int(n.split('_')[-1])
                                        existing.add(idx)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    # draw slots as buttons
                    slot_w = 160
                    slot_h = 48
                    gap = 12
                    start_x = px + 12
                    start_y = py + 48
                    self._slot_rects = {}
                    for i in range(1, self._slot_count + 1):
                        row = (i - 1) // 2
                        col = (i - 1) % 2
                        rx = start_x + col * (slot_w + gap)
                        ry = start_y + row * (slot_h + gap)
                        r = pygame.Rect(rx, ry, slot_w, slot_h)
                        # label
                        label = f"Slot {i}"
                        if i in existing:
                            label += " (Saved)"
                        draw_button(r, label)
                        self._slot_rects[str(i)] = r

                    # draw a visible Close button inside the slot-selection panel (top-right)
                    try:
                        close_w, close_h = 84, 36
                        close_rect = pygame.Rect(px + panel_w - close_w - 12, py + 12, close_w, close_h)
                        pygame.draw.rect(surface, (200, 80, 60), close_rect, border_radius=6)
                        if self._small_font:
                            lbl = self._small_font.render("Close", True, (0, 0, 0))
                            lw, lh = lbl.get_size()
                            surface.blit(lbl, (close_rect.x + (close_w - lw) // 2, close_rect.y + (close_h - lh) // 2))
                        self._button_rects['close_slots'] = close_rect
                    except Exception:
                        pass

                except Exception:
                    pass

            # If confirm overwrite mode, render confirm box
            if self._mode == 'confirm_overwrite':
                try:
                    box_w, box_h = 360, 140
                    bx = sw // 2 - box_w // 2
                    by = sh // 2 - box_h // 2
                    overlay = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                    overlay.fill((20, 20, 20, 240))
                    surface.blit(overlay, (bx, by))
                    txt = f"Overwrite Slot {self._chosen_slot}?"
                    surface.blit(self._small_font.render(txt, True, (240, 240, 240)), (bx + 12, by + 12))
                    # yes/no buttons
                    yes_rect = pygame.Rect(bx + 40, by + 60, 100, 44)
                    no_rect = pygame.Rect(bx + 200, by + 60, 100, 44)
                    draw_button(yes_rect, "Yes")
                    draw_button(no_rect, "No")
                    self._button_rects['yes_overwrite'] = yes_rect
                    self._button_rects['no_overwrite'] = no_rect
                except Exception:
                    pass

            # If controls overlay toggled, draw it
            if self._show_controls:
                try:
                    box_w, box_h = 560, 320
                    bx = sw // 2 - box_w // 2
                    by = sh // 2 - box_h // 2
                    overlay = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                    overlay.fill((8, 8, 8, 220))
                    surface.blit(overlay, (bx, by))
                    lines = [
                        "Controls:",
                        "W / Arrow Up    - Move Up",
                        "S / Arrow Down  - Move Down",
                        "A / Arrow Left  - Move Left",
                        "D / Arrow Right - Move Right",
                        "Space           - Use Tool / Interact",
                        "1-5             - Hotbar slots",
                        "Mouse Wheel     - Cycle Hotbar",
                        "E / Q           - Cycle seeds/tools",
                        "Tab             - Open Shop/Menu",
                    ]
                    for i, ln in enumerate(lines):
                        lbl = self._small_font.render(ln, True, (240, 240, 240)) if self._small_font else None
                        if lbl:
                            surface.blit(lbl, (bx + 20, by + 20 + i * 28))
                    # draw a visible Close button inside the controls overlay (top-right)
                    try:
                        close_w, close_h = 84, 36
                        close_rect = pygame.Rect(bx + box_w - close_w - 12, by + 12, close_w, close_h)
                        clr = (200, 80, 60)
                        pygame.draw.rect(surface, clr, close_rect, border_radius=6)
                        if self._small_font:
                            lbl = self._small_font.render("Close", True, (0, 0, 0))
                            lw, lh = lbl.get_size()
                            surface.blit(lbl, (close_rect.x + (close_w - lw) // 2, close_rect.y + (close_h - lh) // 2))
                        # store for click handling
                        self._button_rects['close_controls'] = close_rect
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            _logger.exception("Error rendering TitleScene")
