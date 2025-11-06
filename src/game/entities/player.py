"""Player sprite implementing movement and simple tool actions."""
import pygame
from typing import Optional
from pygame.sprite import Group
from typing import Tuple, Callable
from pathlib import Path


class Player(pygame.sprite.Sprite):
    def __init__(self, id: str = "player", x: float = 0.0, y: float = 0.0, assets_dir: str | None = None):
        super().__init__()
        self.id = id
        self.x = x
        self.y = y
        # gameplay state
        self.money = 0
        self.energy = 100
        # support both names used across the codebase
        self.inventory = {}
        self.item_inventory = self.inventory
        self.speed = 120.0

        # visual: try to load an asset from assets_dir, otherwise fallback to simple block
        surf = None
        try:
            if assets_dir is not None:
                # attempt to find any character sprite under assets_dir/sprites/character
                p = Path(assets_dir) / "sprites"
                if p.exists():
                    # find first png under sprites/character
                    char_dir = p / "character"
                    if char_dir.exists():
                        files = list(char_dir.rglob("*.png"))
                        if files:
                            surf = pygame.image.load(str(files[0])).convert_alpha()
        except Exception:
            surf = None

        if surf is None:
            self.image = pygame.Surface((32, 48), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (255, 0, 255), self.image.get_rect())
        else:
            self.image = surf
        # keep an unmodified base image for flipping/animation
        try:
            self.base_image = self.image.copy()
        except Exception:
            self.base_image = self.image

        # try to find directional standalone images in assets_dir (left/right/up/down)
        self.direction_frames = {}
        try:
            if assets_dir is not None:
                char_dir = Path(assets_dir) / "sprites" / "character"
                if char_dir.exists():
                    # collect files
                    for f in char_dir.iterdir():
                        name = f.name.lower()
                        if name.endswith('.png'):
                            if 'left' in name:
                                self.direction_frames['left'] = pygame.image.load(str(f)).convert_alpha()
                            elif 'right' in name:
                                self.direction_frames['right'] = pygame.image.load(str(f)).convert_alpha()
                            elif 'up' in name:
                                self.direction_frames['up'] = pygame.image.load(str(f)).convert_alpha()
                            elif 'down' in name:
                                self.direction_frames['down'] = pygame.image.load(str(f)).convert_alpha()
        except Exception:
            pass
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
        self.hitbox = self.rect.copy()
        self.hitbox.inflate_ip(-8, -8)
        self.z = 4

        # world references (attached later by Farm)
        self.soil = None
        self.collision_sprites: Optional[Group] = None
        self.tree_sprites: Optional[Group] = None
        self.interaction_sprites: Optional[Group] = None
        self.toggle_shop: Optional[Callable[[bool], None]] = None

        # action state
        self.status = "idle"
        self.sleep = False

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
    # Attempt movement with collision resolution
        nx = self.x + dx * self.speed * dt
        ny = self.y + dy * self.speed * dt

        # Move on x and check collisions
        self.rect.centerx = int(nx)
        self.hitbox.centerx = self.rect.centerx
        collided = False
        try:
            if self.collision_sprites is not None:
                for c in self.collision_sprites.sprites():
                    if c.rect.colliderect(self.hitbox):
                        collided = True
                        break
        except Exception:
            collided = False
        if not collided:
            self.x = nx
        else:
            # revert x
            self.rect.centerx = int(self.x)
            self.hitbox.centerx = self.rect.centerx

        # Move on y and check collisions
        self.rect.centery = int(ny)
        self.hitbox.centery = self.rect.centery
        collided = False
        try:
            if self.collision_sprites is not None:
                for c in self.collision_sprites.sprites():
                    if c.rect.colliderect(self.hitbox):
                        collided = True
                        break
        except Exception:
            collided = False
        if not collided:
            self.y = ny
        else:
            # revert y
            self.rect.centery = int(self.y)
            self.hitbox.centery = self.rect.centery

        # update facing/direction for simple sprite flip or directional images
        try:
            if dx < 0:
                # facing left
                self.facing = "left"
                if 'left' in self.direction_frames:
                    self.image = self.direction_frames['left']
                else:
                    self.image = pygame.transform.flip(self.base_image, True, False)
            elif dx > 0:
                self.facing = "right"
                if 'right' in self.direction_frames:
                    self.image = self.direction_frames['right']
                else:
                    self.image = self.base_image
            else:
                # vertical facing use up/down images if available
                if dy < 0:
                    if 'up' in self.direction_frames:
                        self.image = self.direction_frames['up']
                        self.facing = 'up'
                elif dy > 0:
                    if 'down' in self.direction_frames:
                        self.image = self.direction_frames['down']
                        self.facing = 'down'
        except Exception:
            pass

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

    # New API helpers expected by farm and UI
    def attach_world(self, soil, collision_sprites: Group, tree_sprites: Group, interaction_sprites: Group, toggle_shop: Callable[[bool], None]):
        """Attach references to world systems so the player can interact."""
        self.soil = soil
        self.collision_sprites = collision_sprites
        self.tree_sprites = tree_sprites
        self.interaction_sprites = interaction_sprites
        self.toggle_shop = toggle_shop

    def use_tool(self, tool_name: str, tile_x: int, tile_y: int) -> bool:
        """Generic tool dispatcher: 'hoe'|'water'|'plant'|'harvest'"""
        if self.soil is None:
            return False
        if tool_name == "hoe":
            return self.use_tool_till(self.soil, tile_x, tile_y)
        if tool_name == "water":
            return self.use_tool_water(self.soil, tile_x, tile_y)
        if tool_name == "harvest":
            res = self.try_harvest(self.soil)
            if res:
                # give to player inventory
                self.inventory[res] = self.inventory.get(res, 0) + 1
                return True
            return False
        return False

    def interact(self):
        """Check interaction sprites (bed/trader). If bed -> toggle day via shop toggle for now."""
        try:
            if self.interaction_sprites is None:
                return None
            for it in self.interaction_sprites.sprites():
                if it.rect.colliderect(self.hitbox):
                    name = getattr(it, "name", None)
                    if name == "Trader":
                        # open shop
                        if self.toggle_shop:
                            self.toggle_shop(True)
                            return "trader"
                    if name == "Bed":
                        # signal sleep -> higher-level should start transition
                        self.sleep = True
                        return "bed"
        except Exception:
            return None
        return None

    def player_add(self, item_id: str, amount: int = 1):
        self.inventory[item_id] = self.inventory.get(item_id, 0) + amount

