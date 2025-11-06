"""Player sprite implementing movement and simple tool actions."""
import pygame
from typing import Optional


class Player(pygame.sprite.Sprite):
    def __init__(self, id: str = "player", x: float = 0.0, y: float = 0.0):
        super().__init__()
        self.id = id
        self.x = x
        self.y = y
        self.money = 0
        self.energy = 100
        self.inventory = {}
        self.speed = 120.0

        # visual
        self.image = pygame.Surface((32, 48), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (200, 180, 120), self.image.get_rect())
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
        self.hitbox = self.rect.copy()
        self.hitbox.inflate_ip(-8, -8)
        self.z = 4

    def update(self, dt: float, keys=None) -> None:
        dx = dy = 0.0
        if keys is not None:
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx -= 1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx += 1
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                dy -= 1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dy += 1
        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt
        self.rect.center = (int(self.x), int(self.y))
        self.hitbox.center = self.rect.center

    def use_tool_till(self, soil, tx: int, ty: int) -> bool:
        return soil.till(tx, ty)

    def use_tool_plant(self, soil, tx: int, ty: int, seed_id: str) -> bool:
        if self.inventory.get(seed_id, 0) <= 0:
            return False
        ok = soil.plant(tx, ty, seed_id)
        if ok:
            self.inventory[seed_id] = self.inventory.get(seed_id, 0) - 1
        return ok

    def use_tool_water(self, soil, tx: int, ty: int) -> bool:
        return soil.water(tx, ty)

    def try_harvest(self, soil) -> Optional[str]:
        return soil.harvest_at_rect(self.hitbox)

