"""Sprite types used by the farm scene: Generic, Water, WildFlower, Tree, Interaction, Particle."""
from __future__ import annotations
import pygame
from pygame.sprite import Sprite, Group
from typing import Tuple, Callable
from pathlib import Path
from src.game.resources.resource_manager import import_folder
import logging

_logger = logging.getLogger("mystic_meadows.sprites")


class Generic(Sprite):
    def __init__(self, pos: Tuple[int,int], surf: pygame.Surface=None, groups: Tuple[Group,...]=(), z:int=3):
        super().__init__()
        self.image = surf if surf is not None else pygame.Surface((32,32))
        if surf is None:
            self.image.fill((120,120,120))
        self.rect = self.image.get_rect(topleft=pos)
        self.z = z
        for g in groups:
            g.add(self)


class Water(Sprite):
    def __init__(self, pos: Tuple[int,int], frames: list | str | Path = None, groups: Tuple[Group,...]=(), z:int=2):
        super().__init__()
        # frames may be a list of surfaces or a path to a folder
        if isinstance(frames, (str, Path)):
            self.frames = import_folder(frames)
        else:
            self.frames = frames or []
        self.index = 0
        self.image = self.frames[0] if self.frames else pygame.Surface((32,32))
        self.rect = self.image.get_rect(topleft=pos)
        self.z = z
        for g in groups:
            g.add(self)

    def update(self, dt=0):
        if not self.frames:
            return
        # advance based on dt if frames are present (simple frame-per-update)
        self.index = (self.index + 1) % len(self.frames)
        self.image = self.frames[self.index]


class WildFlower(Generic):
    def __init__(self, pos, surf=None, groups=(), z=3):
        super().__init__(pos, surf, groups, z)


class Interaction(Sprite):
    def __init__(self, pos: Tuple[int,int], size: Tuple[int,int], name: str, groups: Tuple[Group,...]=(), z:int=3):
        super().__init__()
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(self.image, (0,0,0,0), self.image.get_rect())
        self.rect = self.image.get_rect(topleft=pos)
        self.name = name
        self.z = z
        for g in groups:
            g.add(self)


class Particle(Sprite):
    def __init__(self, pos: Tuple[int,int], surf: pygame.Surface, groups: Tuple[Group,...]=(), z:int=4, lifetime:float=0.5):
        super().__init__()
        self.image = surf.copy()
        self.rect = self.image.get_rect(topleft=pos)
        self.z = z
        self.lifetime = lifetime
        self.age = 0.0
        for g in groups:
            g.add(self)

    def update(self, dt=0):
        self.age += dt
        if self.age >= self.lifetime:
            self.kill()


class Tree(Sprite):
    def __init__(self, pos: Tuple[int,int], surf: pygame.Surface=None, groups: Tuple[Group,...]=(), name:str="Tree", player_add:Callable[[str],None]=None, z:int=3):
        super().__init__()
        self.image = surf if surf is not None else pygame.Surface((64,96), pygame.SRCALPHA)
        if surf is None:
            pygame.draw.rect(self.image, (34,139,34), self.image.get_rect())
        self.rect = self.image.get_rect(topleft=pos)
        self.z = z
        self.name = name
        self.player_add = player_add
        self.apple_sprites = Group()
        for g in groups:
            g.add(self)

    def spawn_apple(self, apple_surf: pygame.Surface):
        # Create a simple apple sprite
        from pygame.sprite import Sprite
        a = Sprite()
        a.image = apple_surf
        a.rect = a.image.get_rect(center=(self.rect.centerx, self.rect.centery - 10))
        a.z = self.z + 1
        self.apple_sprites.add(a)
        return a
