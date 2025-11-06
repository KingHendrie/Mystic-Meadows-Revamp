"""Simple shop Menu implementation.

Menu is modal: when active, Farm calls menu.update() instead of running simulation.
This implementation provides a minimal buy/sell interface via keys for testing.
"""
from __future__ import annotations
import pygame
import logging
from typing import Callable

_logger = logging.getLogger("mystic_meadows.ui.menu")


class Menu:
    def __init__(self, player, toggle_shop: Callable[[bool], None]):
        self.player = player
        self.toggle_shop = toggle_shop
        self.active = False
        self.show_controls = False
        # simple catalog: seed_id -> price (use seed ids that match plant types)
        # Buying adds to player's seed_inventory; selling converts harvested crops from inventory
        self.catalog = {"corn": 5, "tomato": 7}
        # last drawn rect (used to map mouse clicks into the menu)
        self._last_rect = None
        # simple debounce for purchases to avoid key-repeat buying
        self._last_buy_time = {}
        # derived sell prices (fraction of buy price)
        self.sell_fraction = 0.6
        # UI rect caches for clickable buttons (populated during draw)
        self._buy_rects = {}
        self._sell_rects = {}

    def open(self):
        self.active = True

    def close(self):
        self.active = False

    def update(self):
        # Menu is modal; input is handled via events (KEYDOWN/MOUSEBUTTONDOWN) in handle_event.
        # Keep update lightweight in case the game loop calls it every frame.
        return

    def handle_event(self, event):
        """Handle mouse interactions for the menu (click Controls button)."""
        try:
            # Mouse clicks handled here (menu interactions) - Controls button removed
            # Key handling: use KEYDOWN events to avoid repeated buys when holding a key
            if getattr(event, 'type', None) == pygame.KEYDOWN:
                k = getattr(event, 'key', None)
                if k == pygame.K_1:
                    self._buy("corn")
                    return
                if k == pygame.K_2:
                    self._buy("tomato")
                    return
                if k == pygame.K_s:
                    # sell harvested crops from inventory
                    try:
                        self._sell_all()
                    except Exception:
                        pass
                    return
                if k == pygame.K_ESCAPE or k == pygame.K_TAB:
                    # close shop
                    try:
                        self.toggle_shop(False)
                    except Exception:
                        pass
                    return
            # Mouse clicks: close only when clicking outside the menu panel or the Close button.
            if getattr(event, 'type', None) == pygame.MOUSEBUTTONDOWN:
                pos = getattr(event, 'pos', None)
                # if we don't have a last drawn rect, fall back to closing
                if self._last_rect is None:
                    try:
                        self.toggle_shop(False)
                    except Exception:
                        pass
                    return
                mx, my = pos if pos is not None else (None, None)
                menu_x, menu_y, menu_w, menu_h = self._last_rect
                panel_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
                # if click outside panel, close
                if not panel_rect.collidepoint((mx, my)):
                    try:
                        self.toggle_shop(False)
                    except Exception:
                        pass
                    return
                # check buy/sell buttons first
                try:
                    for k, r in list(self._buy_rects.items()):
                        if r and r.collidepoint((mx, my)):
                            try:
                                self._buy(k)
                            except Exception:
                                pass
                            return
                except Exception:
                    pass
                try:
                    for k, r in list(self._sell_rects.items()):
                        if r and r.collidepoint((mx, my)):
                            try:
                                self._sell_item(k)
                            except Exception:
                                pass
                            return
                except Exception:
                    pass
                # if click inside panel, check close button
                close_r = getattr(self, '_close_rect', None)
                if close_r and close_r.collidepoint((mx, my)):
                    try:
                        self.toggle_shop(False)
                    except Exception:
                        pass
                    return
                # otherwise consume the click and do nothing (menu uses keys)
                return
        except Exception:
            pass

    def draw(self, surface: pygame.Surface):
        """Render the menu overlay. Farm.render will call this when active."""
        try:
            font = pygame.font.Font(None, 28)
            # panel size and center it
            panel_w, panel_h = 360, 220
            sx, sy = surface.get_size()
            menu_x = sx // 2 - panel_w // 2
            menu_y = sy // 2 - panel_h // 2
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            surface.blit(overlay, (menu_x, menu_y))
            # store the last drawn rect for click mapping
            self._last_rect = (menu_x, menu_y, panel_w, panel_h)

            surface.blit(font.render("Shop", True, (255, 255, 255)), (menu_x + 16, menu_y + 12))

            # items
            # items with buy/sell buttons and player counts
            try:
                item_x = menu_x + 16
                item_y = menu_y + 48
                btn_w, btn_h = 72, 28
                gap_y = 32
                self._buy_rects = {}
                self._sell_rects = {}
                for i, (item, price) in enumerate(self.catalog.items()):
                    y = item_y + i * gap_y
                    # label
                    surface.blit(font.render(f"{i+1}: {item.capitalize()} ({price})", True, (255, 255, 255)), (item_x, y))
                    # player count
                    try:
                        cnt = getattr(self.player, 'inventory', {}).get(item, 0)
                    except Exception:
                        cnt = 0
                    surface.blit(font.render(f"Owned: {cnt}", True, (220, 220, 180)), (item_x + 180, y))
                    # buy button (right side)
                    bx = menu_x + panel_w - btn_w - 16
                    by = y - 2
                    buy_rect = pygame.Rect(bx, by, btn_w, btn_h)
                    pygame.draw.rect(surface, (60, 160, 90), buy_rect, border_radius=6)
                    surface.blit(font.render("Buy", True, (0, 0, 0)), (bx + 18, by + 4))
                    self._buy_rects[item] = buy_rect
                    # sell button next to buy (left)
                    sxr = bx - (btn_w + 8)
                    sell_rect = pygame.Rect(sxr, by, btn_w, btn_h)
                    pygame.draw.rect(surface, (160, 120, 60), sell_rect, border_radius=6)
                    surface.blit(font.render("Sell", True, (0, 0, 0)), (sxr + 18, by + 4))
                    self._sell_rects[item] = sell_rect
                # sell-all hint (keyboard)
                surface.blit(font.render("Press S to sell all crops", True, (200, 200, 170)), (item_x, menu_y + panel_h - 48))
            except Exception:
                pass

            # If toggled, draw controls box to the right of menu (toggled via Tab hold)
            if self.show_controls:
                self.draw_controls(surface)
            # draw visible Close button (top-right of panel)
            try:
                close_w, close_h = 84, 32
                close_x = menu_x + panel_w - close_w - 12
                close_y = menu_y + 12
                self._close_rect = pygame.Rect(close_x, close_y, close_w, close_h)
                pygame.draw.rect(surface, (200, 80, 60), self._close_rect, border_radius=6)
                surface.blit(font.render("Close", True, (0, 0, 0)), (close_x + 18, close_y + 6))
            except Exception:
                self._close_rect = None
        except Exception:
            pass

    def draw_controls(self, surface: pygame.Surface):
        """Render only the controls box. This can be used when the menu is not active
        (e.g., show controls while Tab is held)."""
        try:
            font = pygame.font.Font(None, 28)
            panel_w = 360
            sx, sy = surface.get_size()
            menu_x = sx // 2 - panel_w // 2
            menu_y = sy // 2 - 220 // 2
            ctrl_w, ctrl_h = 300, 160
            ctrl_x = menu_x + panel_w + 12
            ctrl_y = menu_y
            ctrl_box = pygame.Surface((ctrl_w, ctrl_h), pygame.SRCALPHA)
            ctrl_box.fill((20, 20, 20, 230))
            surface.blit(ctrl_box, (ctrl_x, ctrl_y))
            lines = [
                "Controls:",
                "WASD / Arrow keys - Move",
                "Space - Use selected hotbar slot (tool/harvest)",
                "Left Ctrl - Use currently selected seed (plant)",
                "1-5 - Select hotbar slots",
                "Tab - Hold to view controls",
                "Enter - Interact / Sleep (press)",
                "Note: Q/E hotbar cycling removed in this build",
            ]
            for i, ln in enumerate(lines):
                surface.blit(font.render(ln, True, (220, 220, 220)), (ctrl_x + 12, ctrl_y + 12 + i * 22))
        except Exception:
            pass

    def _buy(self, seed_id: str):
        price = self.catalog.get(seed_id)
        if price is None:
            return
        import time
        now = time.time()
        last = self._last_buy_time.get(seed_id, 0.0)
        # Require at least 0.25s between purchases of the same item to avoid key-repeat
        if now - last < 0.25:
            return
        player_money = getattr(self.player, "money", 0)
        if player_money >= price:
            # deduct
            try:
                self.player.money -= price
            except Exception:
                # if attribute doesn't exist, set it
                setattr(self.player, "money", player_money - price)
            # add to seed_inventory if present, otherwise fall back to generic inventory
            try:
                if hasattr(self.player, 'seed_inventory'):
                    self.player.seed_inventory[seed_id] = self.player.seed_inventory.get(seed_id, 0) + 1
                else:
                    # legacy fallback
                    if hasattr(self.player, "inventory"):
                        inv = self.player.inventory
                        inv[seed_id] = inv.get(seed_id, 0) + 1
                    else:
                        inv = getattr(self.player, "item_inventory", None)
                        if inv is None:
                            self.player.item_inventory = {seed_id: 1}
                        else:
                            inv[seed_id] = inv.get(seed_id, 0) + 1
            except Exception:
                pass
            _logger.info("Bought %s", seed_id)
            # toast via HUD if available
            try:
                ui = getattr(getattr(self.player, 'farm', None), 'ui', None)
                if ui is not None:
                    ui.toast(f"Bought {seed_id}", 2.0)
            except Exception:
                pass
            self._last_buy_time[seed_id] = now
        else:
            _logger.info("Not enough money to buy %s", seed_id)

    def _sell_all(self):
        """Sell all harvested crops from player's inventory at sell prices."""
        if getattr(self.player, 'inventory', None) is None:
            _logger.info('Sell: no inventory available')
            return
        total = 0
        sold = {}
        for crop, buy_price in list(self.catalog.items()):
            # crops are stored in player's inventory under the same crop id
            qty = self.player.inventory.get(crop, 0)
            if qty <= 0:
                continue
            sell_price = int(buy_price * self.sell_fraction)
            gain = sell_price * qty
            total += gain
            sold[crop] = (qty, sell_price, gain)
            # remove from inventory
            try:
                self.player.inventory[crop] = max(0, self.player.inventory.get(crop, 0) - qty)
            except Exception:
                pass
        if total > 0:
            try:
                self.player.money = getattr(self.player, 'money', 0) + total
            except Exception:
                try:
                    setattr(self.player, 'money', getattr(self.player, 'money', 0) + total)
                except Exception:
                    pass
            _logger.info('Sold crops: %s -> +$%s', sold, total)
            try:
                ui = getattr(getattr(self.player, 'farm', None), 'ui', None)
                if ui is not None:
                    ui.toast(f"Sold crops +${total}", 2.5)
            except Exception:
                pass
        else:
            _logger.info('Sell: no crops to sell')
            try:
                ui = getattr(getattr(self.player, 'farm', None), 'ui', None)
                if ui is not None:
                    ui.toast('No crops to sell', 1.8)
            except Exception:
                pass

    def _sell_item(self, crop: str):
        """Sell all quantity of a specific crop from player's inventory."""
        if getattr(self.player, 'inventory', None) is None:
            return
        qty = self.player.inventory.get(crop, 0)
        if qty <= 0:
            try:
                ui = getattr(getattr(self.player, 'farm', None), 'ui', None)
                if ui is not None:
                    ui.toast(f'No {crop} to sell', 1.6, 'info')
            except Exception:
                pass
            return
        price = self.catalog.get(crop, 0)
        sell_price = int(price * self.sell_fraction)
        gain = sell_price * qty
        try:
            self.player.inventory[crop] = max(0, self.player.inventory.get(crop, 0) - qty)
        except Exception:
            pass
        try:
            self.player.money = getattr(self.player, 'money', 0) + gain
        except Exception:
            try:
                setattr(self.player, 'money', getattr(self.player, 'money', 0) + gain)
            except Exception:
                pass
        _logger.info('Sold %s x%s -> +$%s', crop, qty, gain)
        try:
            ui = getattr(getattr(self.player, 'farm', None), 'ui', None)
            if ui is not None:
                ui.toast(f'Sold {crop} x{qty} +${gain}', 2.4, 'success')
        except Exception:
            pass
