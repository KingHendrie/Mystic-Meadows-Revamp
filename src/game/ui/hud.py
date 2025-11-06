"""HUD (heads-up display) for the farm scene.

This module provides a minimal, robust HUD that displays day, money and a
hotbar. It is intentionally defensive: it tolerates missing assets and
missing player attributes so it can be integrated into the current skeleton
without breaking runtime.
"""
from __future__ import annotations
import pygame
from pathlib import Path
from typing import Optional


class HUD:
    def __init__(self, player, assets_dir: Optional[Path] = None):
        self.player = player
        self.assets_dir = Path(assets_dir) if assets_dir is not None else None
        # basic font
        try:
            self.font = pygame.font.Font(None, 24)
        except Exception:
            self.font = None

    def display(self, surface: pygame.Surface) -> None:
        """Draw the HUD on top of the given surface.

        Displays basic info: Day, Money and a small hotbar indicator. This is
        intentionally simple so it works when icon assets are not available.
        """
        try:
            # safe reads of player state
            day = getattr(self.player, "day", None) or getattr(self.player, "_day", None) or None
            # Farm stores day on Farm, not Player. We try to read from player then
            # fallback to a public attribute 'day' on the farm if present via player.farm
            if day is None:
                day = getattr(getattr(self.player, "farm", None), "day", None)
            if day is None:
                # leave blank
                day_text = "Day: ?"
            else:
                day_text = f"Day: {day}"

            money = getattr(self.player, "money", 0)
            money_text = f"Money: {money}"

            # render text
            font = self.font or pygame.font.Font(None, 24)
            d_surf = font.render(day_text, True, (255, 255, 255))
            m_surf = font.render(money_text, True, (255, 255, 255))
            surface.blit(d_surf, (8, 8))
            surface.blit(m_surf, (8, 32))

            # simple hotbar: draw 5 slots and highlight selected
            hotbar_x = 8
            hotbar_y = surface.get_height() - 48
            slot_w = 40
            slot_h = 40
            slots = 5
            selected = getattr(self.player, "selected_slot", 0)
            if selected is None:
                selected = 0

            for i in range(slots):
                rect = pygame.Rect(hotbar_x + i * (slot_w + 6), hotbar_y, slot_w, slot_h)
                color = (60, 60, 60)
                pygame.draw.rect(surface, color, rect)
                pygame.draw.rect(surface, (0, 0, 0), rect, 2)
                if i == selected:
                    pygame.draw.rect(surface, (255, 255, 0), rect, 3)
                # draw item count if available
                try:
                    hotbar = getattr(self.player, "hotbar", None)
                    if hotbar and i < len(hotbar):
                        item_id = hotbar[i]
                        count = self.player.inventory.get(item_id, 0)
                        if count:
                            t = font.render(str(count), True, (255, 255, 255))
                            surface.blit(t, (rect.right - 14, rect.bottom - 18))
                except Exception:
                    pass
        except Exception:
            # swallow drawing errors to avoid crashing the main loop
            return
"""Heads-up display skeleton."""
import logging

_logger = logging.getLogger("mystic_meadows.ui.hud")


class HUD:
    def __init__(self):
        self.visible = True

    def update(self, dt: float):
        pass

    def render(self, surface):
        # In a real game we'd draw text and icons here
        pass
