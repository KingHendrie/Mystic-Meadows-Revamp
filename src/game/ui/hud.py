"""HUD (heads-up display) for the farm scene.

This HUD draws a small translucent panel with Day and Money, a 5-slot
hotbar and a prominent icon + label for the currently selected slot.
It is defensive and tolerates missing assets or missing player fields.
"""
from __future__ import annotations
from typing import Optional
from pathlib import Path
import pygame


class HUD:
    def __init__(self, player, assets_dir: Optional[Path] = None):
        self.player = player
        self.assets_dir = Path(assets_dir) if assets_dir is not None else None
        # icon cache keyed by (name, size) -> surface
        self._icons = {}
        # debug overlay toggle (draw plant rects + counts)
        self.show_debug = False
        # debug buttons (label -> rect)
        self._debug_buttons = {}
        # transient toasts: list of dicts with keys: text,start,expire,duration,type,color
        self._toasts = []
        try:
            self.font = pygame.font.Font(None, 20)
        except Exception:
            # fallback if font creation fails
            self.font = None

    def _load_icon(self, name: str, size: tuple[int, int]) -> Optional[pygame.Surface]:
        if not name or self.assets_dir is None:
            return None
        key = (name, size)
        if key in self._icons:
            return self._icons[key]
        try:
            p = self.assets_dir / 'sprites' / 'overlay' / f"{name}.png"
            if p.exists():
                surf = pygame.image.load(str(p)).convert_alpha()
                surf = pygame.transform.smoothscale(surf, size)
                self._icons[key] = surf
                return surf
        except Exception:
            pass
        return None

    def display(self, surface: pygame.Surface) -> None:
        try:
            # read state defensively
            font = self.font or pygame.font.Font(None, 20)
            day = getattr(self.player, 'day', None) or getattr(getattr(self.player, 'farm', None), 'day', None)
            day_text = f"Day: {day}" if day is not None else "Day: ?"
            money = getattr(self.player, 'money', 0)
            money_text = f"${money}"

            # panel
            panel_w = 280
            panel_h = 84
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 140))
            surface.blit(panel, (8, 8))

            # text
            surface.blit(font.render(day_text, True, (240, 240, 240)), (16, 12))
            surface.blit(font.render(money_text, True, (240, 240, 240)), (16, 36))
            # harvested crop counts (quick glance)
            try:
                inv = getattr(self.player, 'inventory', {}) or {}
                corn_ct = inv.get('corn', 0)
                tomato_ct = inv.get('tomato', 0)
                # draw small icons if available, else colored squares
                try:
                    icon_size = (16, 16)
                    corn_icon = self._load_icon('corn', icon_size)
                except Exception:
                    corn_icon = None
                try:
                    tomato_icon = self._load_icon('tomato', icon_size)
                except Exception:
                    tomato_icon = None
                x = 150
                y = 36
                if corn_icon is not None:
                    surface.blit(corn_icon, (x, y))
                else:
                    sq = pygame.Surface((16, 16))
                    sq.fill((200, 180, 60))
                    surface.blit(sq, (x, y))
                surface.blit(font.render(str(corn_ct), True, (220, 220, 180)), (x + 20, y))
                # tomato
                tx = x + 64
                if tomato_icon is not None:
                    surface.blit(tomato_icon, (tx, y))
                else:
                    sq = pygame.Surface((16, 16))
                    sq.fill((220, 80, 80))
                    surface.blit(sq, (tx, y))
                surface.blit(font.render(str(tomato_ct), True, (220, 220, 180)), (tx + 20, y))
            except Exception:
                pass

            # hotbar geometry
            hotbar_x = 16
            hotbar_y = surface.get_height() - 64
            slot_w = 48
            slot_h = 48
            slots = 5
            selected = getattr(self.player, 'selected_slot', 0) or 0

            # draw slots
            for i in range(slots):
                rect = pygame.Rect(hotbar_x + i * (slot_w + 8), hotbar_y, slot_w, slot_h)
                pygame.draw.rect(surface, (36, 36, 36), rect)
                pygame.draw.rect(surface, (10, 10, 10), rect, 2)

                # selected highlight
                if i == selected:
                    glow = pygame.Surface((slot_w + 10, slot_h + 10), pygame.SRCALPHA)
                    glow.fill((255, 200, 50, 28))
                    surface.blit(glow, (rect.x - 5, rect.y - 5))
                    pygame.draw.rect(surface, (255, 200, 50), rect, 3)

                # draw icon if available
                try:
                    hotbar = getattr(self.player, 'hotbar', []) or []
                    if i < len(hotbar):
                        item_id = hotbar[i]
                        icon = self._load_icon(item_id, (slot_w - 8, slot_h - 8))
                        # For seeds, prefer the seed_inventory; otherwise use generic inventory
                        if hasattr(self.player, 'seeds') and item_id in getattr(self.player, 'seeds', []):
                            count = getattr(self.player, 'seed_inventory', {}).get(item_id, 0)
                        else:
                            count = getattr(self.player, 'inventory', {}).get(item_id, 0)
                        if icon is not None:
                            icon_pos = (rect.x + 4, rect.y + 4)
                            if count <= 0:
                                # dim icon by blitting a semi-transparent dark overlay
                                dim = icon.copy()
                                try:
                                    overlay = pygame.Surface(dim.get_size(), pygame.SRCALPHA)
                                    overlay.fill((0, 0, 0, 120))
                                    dim.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
                                except Exception:
                                    # fallback: just blit the original icon with reduced alpha
                                    dim.set_alpha(100)
                                surface.blit(dim, icon_pos)
                            else:
                                surface.blit(icon, icon_pos)
                        # count
                        if count:
                            surface.blit(font.render(str(count), True, (230, 230, 230)), (rect.right - 18, rect.bottom - 20))
                except Exception:
                    pass

            # draw selected large icon + label
            try:
                hotbar = getattr(self.player, 'hotbar', []) or []
                if 0 <= selected < len(hotbar):
                    slot_id = hotbar[selected]
                    icon = self._load_icon(slot_id, (56, 56))
                    icon_x = hotbar_x + selected * (slot_w + 8) + (slot_w - 56) // 2
                    icon_y = hotbar_y - 72
                    if icon is not None:
                        surface.blit(icon, (icon_x, icon_y))
                    # label pill
                    pill = pygame.Surface((100, 24), pygame.SRCALPHA)
                    pill.fill((0, 0, 0, 160))
                    lx = icon_x - 18
                    ly = icon_y + 56
                    surface.blit(pill, (lx, ly))
                    surface.blit(font.render(str(slot_id).capitalize(), True, (240, 240, 240)), (lx + 8, ly + 3))
            except Exception:
                pass

            # debug overlay: draw plant bboxes and count when enabled
            try:
                if getattr(self, 'show_debug', False) and getattr(self.player, 'farm', None) is not None:
                    farm = self.player.farm
                    try:
                        window_w, window_h = getattr(farm, 'window_size', (surface.get_width(), surface.get_height()))
                        offset_x = self.player.rect.centerx - window_w // 2
                        offset_y = self.player.rect.centery - window_h // 2
                        for p in list(getattr(getattr(farm, 'soil', None), 'plant_sprites', []).sprites()):
                            dest = p.rect.move(-offset_x, -offset_y)
                            try:
                                pygame.draw.rect(surface, (255, 0, 0), dest, 1)
                                tx = getattr(p, 'tx', None)
                                ty = getattr(p, 'ty', None)
                                if tx is None or ty is None:
                                    tx = p.rect.x // farm.tile_size
                                    ty = p.rect.y // farm.tile_size
                                label = f"{getattr(p, 'plant_type', '?')} ({tx},{ty})"
                                surface.blit(font.render(label, True, (255, 200, 200)), (dest.x, max(0, dest.y - 14)))
                            except Exception:
                                pass
                        # plant count in top-right of HUD area
                        try:
                            count = len(list(farm.soil.plant_sprites.sprites()))
                            surface.blit(font.render(f"Plants: {count}", True, (255, 255, 200)), (surface.get_width() - 140, 12))
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # draw debug utilities panel (only when show_debug True)
                    try:
                        dbg_w = 220
                        dbg_h = 36 + 36 * 8
                        dbg_x = surface.get_width() - dbg_w - 8
                        dbg_y = 60
                        panel = pygame.Surface((dbg_w, dbg_h), pygame.SRCALPHA)
                        panel.fill((8, 8, 8, 200))
                        surface.blit(panel, (dbg_x, dbg_y))
                        # list of debug buttons and labels
                        buttons = [
                            ("Teleport", "Teleport to first plant"),
                            ("GrowAll", "Force-grow all plants"),
                            ("WaterAll", "Water all tilled tiles"),
                            ("RemovePlants", "Remove all plants"),
                            ("SaveNow", "Save current slot now"),
                            ("ListSaves", "List save files (log)"),
                            ("DumpSave", "Dump current save payload (log)"),
                            ("ToggleCollisions", "Toggle collision boxes"),
                            ("ExportScreen", "Save a screenshot of current display"),
                            ("ExportSoil", "Export soil+plants state to JSON"),
                        ]
                        bx = dbg_x + 8
                        by = dbg_y + 8
                        self._debug_buttons = {}
                        for i, (key, label_text) in enumerate(buttons):
                            ry = by + i * 36
                            rect = pygame.Rect(bx, ry, dbg_w - 16, 28)
                            pygame.draw.rect(surface, (60, 60, 60), rect, border_radius=6)
                            surface.blit(font.render(label_text, True, (240, 240, 240)), (rect.x + 8, rect.y + 4))
                            self._debug_buttons[key] = rect
                    except Exception:
                        pass
            except Exception:
                pass

            # toasts (transient messages shown near top-center) with simple fade/slide
            try:
                if getattr(self, '_toasts', None):
                    now = pygame.time.get_ticks()
                    ty_base = 8
                    kept = []
                    for t in list(self._toasts):
                        try:
                            start = t.get('start', 0)
                            dur = int(t.get('duration', 1000)) or 1000
                            expire = t.get('expire', 0)
                            if expire <= now:
                                continue
                            # progress 0..1
                            prog = max(0.0, min(1.0, (now - start) / float(dur)))
                            # fade out towards end
                            alpha = int(255 * (1.0 - prog))
                            # slide up slightly as it ages
                            yoff = int((1.0 - prog) * 10)
                            text = t.get('text', '')
                            color = t.get('color', (220, 220, 220))
                            s = font.render(text, True, color)
                            sw = s.get_width()
                            sh = s.get_height()
                            sx = surface.get_width() // 2 - sw // 2
                            ty = ty_base
                            # background pill
                            pill = pygame.Surface((sw + 20, sh + 8), pygame.SRCALPHA)
                            pill.fill((0, 0, 0, 160))
                            # apply alpha to pill and text
                            try:
                                pill.set_alpha(max(40, alpha))
                            except Exception:
                                pass
                            surface.blit(pill, (sx - 10, ty - 4 - yoff))
                            try:
                                img = s.copy()
                                img.set_alpha(alpha)
                                surface.blit(img, (sx, ty - yoff))
                            except Exception:
                                surface.blit(s, (sx, ty - yoff))
                            ty_base += sh + 10
                            kept.append(t)
                        except Exception:
                            pass
                    self._toasts = kept
            except Exception:
                pass

        except Exception:
            # never crash the main loop due to HUD issues
            return

    def toast(self, text: str, duration: float = 2.0, ttype: str = 'info'):
        """Show a transient on-screen message.

        ttype: 'info'|'success'|'error' to influence color. Duration in seconds.
        """
        try:
            now = pygame.time.get_ticks()
            dur_ms = int(duration * 1000)
            expire = now + dur_ms
            color = (200, 200, 200)
            if ttype == 'success':
                color = (140, 220, 140)
            elif ttype == 'error':
                color = (240, 140, 140)
            self._toasts.append({'text': str(text), 'start': now, 'expire': expire, 'duration': dur_ms, 'type': ttype, 'color': color})
            # cap toasts to last 6 messages
            if len(self._toasts) > 6:
                self._toasts = self._toasts[-6:]
        except Exception:
            pass

    def handle_debug_event(self, event):
        """Handle click events for the debug buttons when visible."""
        try:
            import pygame
        except Exception:
            return
        if not getattr(self, 'show_debug', False):
            return
        if getattr(event, 'type', None) == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', None) == 1:
            pos = getattr(event, 'pos', None)
            if pos is None:
                return
            for key, rect in list(self._debug_buttons.items()):
                try:
                    if rect.collidepoint(pos):
                        # dispatch action
                        try:
                            self._run_debug_action(key)
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

    def _run_debug_action(self, key: str):
        # delegate to external debug utils to keep HUD class lightweight
        try:
            from src.game import debug_utils
            debug_utils.handle_debug_action(self, key)
        except Exception:
            try:
                import logging
                logging.getLogger('mystic_meadows.hud.debug').exception('Delegating debug action failed')
            except Exception:
                pass

        except Exception:
            pass
