"""SoilLayer: simple grid-based farming system.

This is a compact implementation intended to provide basic till/plant/water/harvest
behavior for the skeleton game. It keeps a grid of tiles and a sprite group of plants.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import pygame
import logging

from pygame.sprite import Group, Sprite

_logger = logging.getLogger("mystic_meadows.soil")


@dataclass
class TileState:
    tilled: bool = False
    seed_id: Optional[str] = None
    growth_stage: int = 0
    watered_today: bool = False


class Plant(Sprite):
    def __init__(self, x: int, y: int, tile_size: int, plant_type: str = "corn"):
        super().__init__()
        self.plant_type = plant_type
        self.image = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
        # simple visual: green square scaled by growth stage
        pygame.draw.rect(self.image, (34, 139, 34), self.image.get_rect())
        self.rect = self.image.get_rect(topleft=(x * tile_size, y * tile_size))
        self.z = 3
        self.growth_stage = 0
        self.max_stage = 3
        self.harvestable = False

    def advance(self):
        if self.growth_stage < self.max_stage:
            self.growth_stage += 1
            # visual scale change
            scale = 8 + self.growth_stage * 8
            surf = pygame.Surface((scale, scale), pygame.SRCALPHA)
            pygame.draw.rect(surf, (34, 139, 34), surf.get_rect())
            # center inside tile
            self.image = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
            self.image.blit(surf, ((self.rect.w - scale) // 2, (self.rect.h - scale) // 2))
            if self.growth_stage >= self.max_stage:
                self.harvestable = True


class SoilLayer:
    def __init__(self, all_sprites: Group, collision_sprites: Group, tile_size: int, grid_size: Tuple[int,int]):
        self.all_sprites = all_sprites
        self.collision_sprites = collision_sprites
        self.tile_size = tile_size
        self.grid_w, self.grid_h = grid_size
        self.grid: List[List[TileState]] = [[TileState() for _ in range(self.grid_h)] for _ in range(self.grid_w)]
        self.plant_sprites: Group = Group()
        self.raining = False

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.grid_w and 0 <= ty < self.grid_h

    def till(self, tx: int, ty: int) -> bool:
        if not self.in_bounds(tx, ty):
            return False
        tile = self.grid[tx][ty]
        if tile.tilled:
            return False
        tile.tilled = True
        _logger.debug("Tilled tile %s,%s", tx, ty)
        return True

    def plant(self, tx: int, ty: int, seed_id: str) -> bool:
        if not self.in_bounds(tx, ty):
            return False
        tile = self.grid[tx][ty]
        if not tile.tilled or tile.seed_id is not None:
            return False
        tile.seed_id = seed_id
        # create a plant sprite
        plant = Plant(tx, ty, self.tile_size, plant_type=seed_id)
        self.plant_sprites.add(plant)
        self.all_sprites.add(plant)
        _logger.debug("Planted %s at %s,%s", seed_id, tx, ty)
        return True

    def water(self, tx: int, ty: int) -> bool:
        if not self.in_bounds(tx, ty):
            return False
        tile = self.grid[tx][ty]
        tile.watered_today = True
        _logger.debug("Watered tile %s,%s", tx, ty)
        return True

    def water_all(self):
        for x in range(self.grid_w):
            for y in range(self.grid_h):
                self.grid[x][y].watered_today = True
        _logger.debug("All tiles watered (rain)")

    def remove_water(self):
        for x in range(self.grid_w):
            for y in range(self.grid_h):
                self.grid[x][y].watered_today = False

    def update_plants(self):
        # Advance growth for plants that were watered_today (or if raining)
        for plant in list(self.plant_sprites.sprites()):
            tx = plant.rect.x // self.tile_size
            ty = plant.rect.y // self.tile_size
            tile = self.grid[tx][ty]
            if tile.watered_today or self.raining:
                plant.advance()
                _logger.debug("Advanced plant at %s,%s to stage %d", tx, ty, plant.growth_stage)

    def harvest_at_rect(self, rect: pygame.Rect) -> Optional[str]:
        for plant in list(self.plant_sprites.sprites()):
            if plant.harvestable and plant.rect.colliderect(rect):
                plant_type = plant.plant_type
                plant.kill()
                # clear tile
                tx = plant.rect.x // self.tile_size
                ty = plant.rect.y // self.tile_size
                self.grid[tx][ty].seed_id = None
                self.grid[tx][ty].tilled = False
                self.grid[tx][ty].watered_today = False
                _logger.debug("Harvested %s at %s,%s", plant_type, tx, ty)
                return plant_type
        return None
