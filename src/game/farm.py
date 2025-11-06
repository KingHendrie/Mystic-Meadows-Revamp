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
from src.game.sprites import Generic
from src.game.systems.save_system import SaveSystem
from src.game.ui.menu import Menu
from src.game.transition import Transition

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
        self.tree_sprites = Group()
        self.interaction_sprites = Group()

        # Create a player at center
        px = window_size[0] // 2
        py = window_size[1] // 2
        self.player = Player(id="player", x=px, y=py, assets_dir=self.assets_dir)
        self.all_sprites.add(self.player)

        # Menu (shop) and transition controller
        self.menu = Menu(self.player, self.toggle_shop)
        self._tab_prev = False
        self._n_prev = False

        # Transition for day advance
        self.transition = Transition(window_size, on_day_advance=self._on_day_advance)

        # Save system
        try:
            self.save_system = SaveSystem(self.data_dir)
        except Exception:
            self.save_system = None

        # Soil grid: compute grid size based on window size
        grid_w = window_size[0] // tile_size
        grid_h = window_size[1] // tile_size
        self.soil = SoilLayer(self.all_sprites, self.collision_sprites, tile_size, (grid_w, grid_h))

        # create simple ground tiles so the map is visible without TMX
        try:
            # attempt to load a ground tile from assets
            ground_path = self.assets_dir / "sprites" / "world" / "ground.png"
            if ground_path.exists():
                ground_surf = pygame.image.load(str(ground_path)).convert_alpha()
                ground_surf = pygame.transform.scale(ground_surf, (tile_size, tile_size))
            else:
                ground_surf = None
            for x in range(grid_w):
                for y in range(grid_h):
                    if ground_surf is not None:
                        surf = ground_surf
                    else:
                        surf = pygame.Surface((tile_size, tile_size))
                        surf.fill((100, 180, 90))
                    Generic((x * tile_size, y * tile_size), surf, (self.all_sprites,), z=1)
        except Exception:
            pass

        # Attach world references to player so it can call soil/interact
        try:
            self.player.attach_world(self.soil, self.collision_sprites, self.tree_sprites, self.interaction_sprites, self.toggle_shop)
        except Exception:
            pass

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
        # shop modal handling: if menu active, only update menu
        if self.menu.active:
            # allow toggle key to close via edge detection
            try:
                tab_pressed = keys[pygame.K_TAB]
            except Exception:
                tab_pressed = False
            if tab_pressed and not self._tab_prev:
                self.toggle_shop(False)
            self._tab_prev = tab_pressed
            # let menu handle input
            try:
                self.menu.update()
            except Exception:
                pass
            return

        # Edge detect day-transition key (n) and menu key (tab)
        try:
            tab_pressed = keys[pygame.K_TAB]
            n_pressed = keys[pygame.K_n]
        except Exception:
            tab_pressed = False
            n_pressed = False

        if tab_pressed and not self._tab_prev:
            self.toggle_shop(True)
        if n_pressed and not self._n_prev:
            # start transition (which will call day advance when complete)
            try:
                self.transition.start()
            except Exception:
                pass
        self._tab_prev = tab_pressed
        self._n_prev = n_pressed

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

        # update transition
        try:
            self.transition.update(dt)
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

        # draw menu overlay if active
        try:
            if self.menu.active:
                font = pygame.font.Font(None, 32)
                overlay = pygame.Surface((200, 150), pygame.SRCALPHA)
                overlay.fill((0,0,0,180))
                surface.blit(overlay, (50, 50))
                surface.blit(font.render("Shop - 1: Corn (5)", True, (255,255,255)), (60, 60))
                surface.blit(font.render("2: Tomato (7)", True, (255,255,255)), (60, 100))
        except Exception:
            pass

        # draw transition on top if running
        try:
            self.transition.draw(surface)
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

        # harvest tree apples if overlapping
        try:
            for tree in list(self.tree_sprites.sprites()):
                # each tree has an apple_sprites group
                apples = getattr(tree, "apple_sprites", None)
                if apples is None:
                    continue
                for a in list(apples.sprites()):
                    if a.rect.colliderect(self.player.hitbox):
                        # give apple to player
                        app_id = getattr(a, "item_id", "apple")
                        try:
                            self.player.player_add(app_id, 1)
                        except Exception:
                            self.player.inventory[app_id] = self.player.inventory.get(app_id, 0) + 1
                        try:
                            a.kill()
                        except Exception:
                            pass
                        if self.success:
                            try:
                                self.success.play()
                            except Exception:
                                pass
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

    def _on_day_advance(self):
        # Called by transition when day advance is requested
        try:
            self.reset_day()
        except Exception:
            pass

        # perform quick-save of essential state
        if getattr(self, "save_system", None) is not None:
            try:
                state = {
                    "day": self.day,
                    "player": {
                        "money": getattr(self.player, "money", 0),
                        "inventory": getattr(self.player, "inventory", getattr(self.player, "item_inventory", {})),
                    },
                    "plants": [
                        {"x": p.rect.x // self.tile_size, "y": p.rect.y // self.tile_size, "type": getattr(p, "plant_type", None), "growth_stage": getattr(p, "growth_stage", 0)}
                        for p in list(self.soil.plant_sprites.sprites())
                    ],
                }
                try:
                    self.save_system.auto_save(state, slot=self.day)
                except Exception:
                    # fallback to default slot 1
                    try:
                        self.save_system.auto_save(state)
                    except Exception:
                        pass
            except Exception:
                pass

    def toggle_shop(self, on: bool):
        try:
            if on:
                self.menu.open()
            else:
                self.menu.close()
        except Exception:
            pass
