"""Compatibility Player expected by Farm: constructor matches original API.

Constructor: Player(pos, groups, collision_sprites, tree_sprites, interaction_sprites, soil_layer, toggle_shop)
"""
from __future__ import annotations
import pygame
from pygame.sprite import Sprite, Group
from typing import Tuple, Callable, Optional
import logging

_logger = logging.getLogger("mystic_meadows.player")


class Player(Sprite):
    def __init__(self, pos: Tuple[int,int], groups: Tuple[Group,...], collision_sprites: Group, tree_sprites: Group, interaction_sprites: Group, soil_layer, toggle_shop: Callable[[bool], None]):
        super().__init__()
        self.x, self.y = pos
        self.image = pygame.Surface((32,48), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (200,180,120), self.image.get_rect())
        self.rect = self.image.get_rect(center=pos)
        self.hitbox = self.rect.copy()
        self.hitbox.inflate_ip(-8, -8)
        self.z = 4

        # inventories and state
        self.item_inventory = {}
        self.sleep = False
        self.status = "idle"
        self.speed = 120.0

        # references
        self.groups = groups
        for g in groups:
            g.add(self)
        self.collision_sprites = collision_sprites
        self.tree_sprites = tree_sprites
        self.interaction_sprites = interaction_sprites
        self.soil_layer = soil_layer
        self.toggle_shop = toggle_shop

    def update(self, dt: float):
        # movement handled externally by key polling in GameScene/Farm
        pass

    def move(self, dx: float, dy: float, dt: float):
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt
        self.rect.center = (int(self.x), int(self.y))
        self.hitbox.center = self.rect.center

    # Tool interface
    def till(self, tx: int, ty: int) -> bool:
        return self.soil_layer.till(tx, ty)

    def plant(self, tx: int, ty: int, seed_id: str) -> bool:
        return self.soil_layer.plant(tx, ty, seed_id)

    def water(self, tx: int, ty: int) -> bool:
        return self.soil_layer.water(tx, ty)

    def player_add(self, item_id: str, amount: int = 1):
        self.item_inventory[item_id] = self.item_inventory.get(item_id, 0) + amount
        _logger.debug("Player received %s x%d", item_id, amount)
