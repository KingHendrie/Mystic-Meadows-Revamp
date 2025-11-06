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
        # simple catalog: seed_id -> (price)
        self.catalog = {"corn_seed": 5, "tomato_seed": 7}

    def open(self):
        self.active = True

    def close(self):
        self.active = False

    def update(self):
        # handle simple key commands while shop active: press 1/2 to buy seeds
        try:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_1]:
                self._buy("corn_seed")
            if keys[pygame.K_2]:
                self._buy("tomato_seed")
            if keys[pygame.K_ESCAPE]:
                self.toggle_shop(False)
        except Exception:
            pass

    def _buy(self, seed_id: str):
        price = self.catalog.get(seed_id)
        if price is None:
            return
        player_money = getattr(self.player, "money", 0)
        if player_money >= price:
            # deduct
            try:
                self.player.money -= price
            except Exception:
                # if attribute doesn't exist, set it
                setattr(self.player, "money", player_money - price)
            # add to inventory (try common attribute names)
            if hasattr(self.player, "inventory"):
                inv = self.player.inventory
                inv[seed_id] = inv.get(seed_id, 0) + 1
            else:
                inv = getattr(self.player, "item_inventory", None)
                if inv is None:
                    self.player.item_inventory = {seed_id: 1}
                else:
                    inv[seed_id] = inv.get(seed_id, 0) + 1
            _logger.info("Bought %s", seed_id)
        else:
            _logger.info("Not enough money to buy %s", seed_id)
