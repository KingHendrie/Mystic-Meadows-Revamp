"""Farm world manager for the skeleton game.

This keeps sprite groups, camera drawing and integrates `SoilLayer` and `Player`.
It uses a simple grid rather than a full TMX parser to avoid extra dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple
import pygame
import logging

from pygame.sprite import Group, Sprite

from src.game.config import DEFAULT_TILE_SIZE, DEFAULT_WINDOW_SIZE
from src.game.soil import SoilLayer
from src.game.entities.player import Player

_logger = logging.getLogger("mystic_meadows.farm")


class CameraGroup(Group):
    def __init__(self, window_size: Tuple[int, int], *sprites):
        super().__init__(*sprites)
        self.window_w, self.window_h = window_size

    def custom_draw(self, player: Player, surface: pygame.Surface):
        # center player
        offset_x = player.rect.centerx - self.window_w // 2
        offset_y = player.rect.centery - self.window_h // 2

        # draw background
        surface.fill((50, 180, 70))

        # draw all sprites sorted by z then by rect.centery
        sprites = sorted(self.sprites(), key=lambda s: (getattr(s, "z", 3), s.rect.centery))
        for s in sprites:
            dest = s.rect.move(-offset_x, -offset_y)
            surface.blit(s.image, dest)


class Farm:
    def __init__(self, assets_dir: Path, data_dir: Path, window_size=DEFAULT_WINDOW_SIZE, tile_size=DEFAULT_TILE_SIZE[0]):
        self.assets_dir = Path(assets_dir)
        self.data_dir = Path(data_dir)
        self.tile_size = tile_size
        self.window_size = window_size

        # Sprites and groups
        self.all_sprites = CameraGroup(window_size)
        self.collision_sprites = Group()

        # Create a player at center
        px = window_size[0] // 2
        py = window_size[1] // 2
        self.player = Player(id="player", x=px, y=py)
        self.all_sprites.add(self.player)

        # Soil grid: compute grid size based on window size
        grid_w = window_size[0] // tile_size
        grid_h = window_size[1] // tile_size
        self.soil = SoilLayer(self.all_sprites, self.collision_sprites, tile_size, (grid_w, grid_h))

        # HUD state
        self.day = 1
        self.running = True

        # audio
        try:
            pygame.mixer.init()
            success_path = self.assets_dir / "audio" / "success.wav"
            music_path = self.assets_dir / "audio" / "music.mp3"
            if success_path.exists():
                self.success = pygame.mixer.Sound(str(success_path))
                self.success.set_volume(0.3)
            else:
                self.success = None
            if music_path.exists():
                pygame.mixer.music.load(str(music_path))
                pygame.mixer.music.set_volume(0.2)
                pygame.mixer.music.play(-1)
        except Exception:
            _logger.debug("Audio unavailable or failed to initialize")

    def update(self, dt: float, keys):
        # Update player and other sprites. Some sprites accept dt/keys, others don't.
        # Ensure the player is updated with dt and keys.
        try:
            self.player.update(dt, keys)
        except TypeError:
            # fallback to no-arg update
            try:
                self.player.update()
            except Exception:
                pass

        # Update other sprites safely
        for spr in list(self.all_sprites.sprites()):
            if spr is self.player:
                continue
            # Try different update signatures
            try:
                spr.update(dt, keys)
            except TypeError:
                try:
                    spr.update(dt)
                except TypeError:
                    try:
                        spr.update()
                    except Exception:
                        pass

    def render(self, surface: pygame.Surface):
        self.all_sprites.custom_draw(self.player, surface)
        # simple HUD
        try:
            font = pygame.font.Font(None, 24)
            txt = font.render(f"Day: {self.day}  Money: {self.player.money}", True, (255,255,255))
            surface.blit(txt, (8,8))
        except Exception:
            pass

    def plant_collision(self):
        # harvest if player overlaps a harvestable plant
        harvested = self.soil.harvest_at_rect(self.player.hitbox)
        if harvested:
            self.player.inventory[harvested] = self.player.inventory.get(harvested, 0) + 1
            if self.success:
                try:
                    self.success.play()
                except Exception:
                    pass

    def reset_day(self):
        # Called at end of day
        self.soil.update_plants()
        self.soil.remove_water()
        import random

        self.soil.raining = random.choice([False, False, True])
        if self.soil.raining:
            self.soil.water_all()
        self.day += 1
