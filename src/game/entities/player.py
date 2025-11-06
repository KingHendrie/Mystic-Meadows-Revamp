"""Player sprite implementing movement and simple tool actions."""
import pygame
from typing import Optional
from pygame.sprite import Group
from typing import Tuple, Callable
from pathlib import Path

try:
    # prefer authored settings if present
    from data.config.settings import PLAYER_TOOL_OFFSET, TILE_SIZE
except Exception:
    from src.game.config import DEFAULT_TILE_SIZE as _DEFAULT_TILE_SIZE
    TILE_SIZE = _DEFAULT_TILE_SIZE[0]
    PLAYER_TOOL_OFFSET = {
        'left': pygame.math.Vector2(-40, 20),
        'right': pygame.math.Vector2(40, 20),
        'up': pygame.math.Vector2(0, -10),
        'down': pygame.math.Vector2(0, 30)
    }


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

        # load animations if available
        try:
            self.import_assets()
            # set initial image from animations where possible
            if getattr(self, 'animations', None):
                frames = self.animations.get(self.status, None)
                if frames:
                    self.image = frames[0]
        except Exception:
            pass

        # world references (attached later by Farm)
        self.soil = None
        self.collision_sprites: Optional[Group] = None
        self.tree_sprites: Optional[Group] = None
        self.interaction_sprites: Optional[Group] = None
        self.toggle_shop: Optional[Callable[[bool], None]] = None

        # action state
        # animation status keys like 'down', 'up', 'left', 'right', plus '_idle' or '_hoe' etc.
        self.status = 'down_idle'
        self.frame_index = 0.0
        self.sleep = False

        # position & movement (compat with backup impl)
        self.pos = pygame.math.Vector2(self.rect.center)
        self.direction = pygame.math.Vector2()
        self.speed = 160

        # Timers (use seconds)
        from src.game.timer import Timer
        self.timers = {
            'tool use': Timer(0.35, callback=self._on_tool_use_done),
            'tool switch': Timer(0.2),
            'seed use': Timer(0.35, callback=self._on_seed_use_done),
            'seed switch': Timer(0.2)
        }

        # Tools and seeds
        self.tools = ['hoe', 'axe', 'water']
        self.tool_index = 0
        self.selected_tool = self.tools[self.tool_index]

        self.item_inventory = {}
        self.seed_inventory = {'corn': 0, 'tomato': 0}
        self.money = getattr(self, 'money', 0)

        self.seeds = ['corn', 'tomato']
        self.seed_index = 0
        self.selected_seed = self.seeds[self.seed_index]

        # hotbar (visual mapping) keep existing simple hotbar too
        self.hotbar = ["hoe", "water", "corn", "tomato", "harvest"]
        self.selected_slot = 0

        # world refs
        self.tree_sprites = None
        self.interaction_sprites = None

    def update(self, dt: float, keys=None) -> None:
        # follow backup-style update pipeline: input -> status -> timers -> move -> animate
        # read keys via passed keys or pygame
        self._keys = keys if keys is not None else pygame.key.get_pressed()
        try:
            self.input()
            self.get_status()
            # update timers
            for t in self.timers.values():
                try:
                    t.update(dt)
                except Exception:
                    pass
            # compute target position for tools
            self.get_target_pos()
            # movement
            self.move(dt)
            # animate
            self.animate(dt)
        except Exception:
            # fallback to safe minimal behavior
            try:
                # minimal movement handling
                if keys is not None:
                    dx = dy = 0
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
                    self.pos.x += dx * self.speed * dt
                    self.pos.y += dy * self.speed * dt
                    self.rect.center = (int(self.pos.x), int(self.pos.y))
                    self.hitbox.center = self.rect.center
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

    def perform_action(self) -> bool:
        """Perform the action bound to the currently selected hotbar slot.

        Resolves a target tile in front of the player using simple facing logic
        and calls the appropriate SoilLayer method or interactives.
        """
        # compute target tile based on facing
        try:
            tile_size = getattr(self.soil, "tile_size", None)
            if tile_size is None:
                return False
            tx = int(self.x) // tile_size
            ty = int(self.y) // tile_size
            f = getattr(self, "facing", "down")
            if f == "left":
                tx -= 1
            elif f == "right":
                tx += 1
            elif f == "up":
                ty -= 1
            elif f == "down":
                ty += 1

            slot = None
            try:
                slot = self.hotbar[self.selected_slot]
            except Exception:
                return False

            # tool semantics
            if slot == "hoe":
                return self.use_tool("hoe", tx, ty)
            if slot == "water":
                return self.use_tool("water", tx, ty)
            if slot == "harvest":
                return self.use_tool("harvest", tx, ty)

            # otherwise treat slot as a seed id (plant)
            # require at least one seed in inventory
            if isinstance(slot, str) and self.inventory.get(slot, 0) > 0:
                ok = self.soil.plant(tx, ty, slot)
                if ok:
                    self.inventory[slot] = self.inventory.get(slot, 0) - 1
                return ok
            return False
        except Exception:
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

    # --- Backup-style methods: timers, assets, input, animation, movement ---
    def _on_tool_use_done(self):
        # called when tool use timer finishes
        try:
            # perform actual tool effect now
            if self.selected_tool == 'hoe':
                # target_pos computed previously
                tx = int(self.target_pos[0]) // getattr(self.soil, 'tile_size', TILE_SIZE)
                ty = int(self.target_pos[1]) // getattr(self.soil, 'tile_size', TILE_SIZE)
                self.soil.till(tx, ty)
            elif self.selected_tool == 'water':
                tx = int(self.target_pos[0]) // getattr(self.soil, 'tile_size', TILE_SIZE)
                ty = int(self.target_pos[1]) // getattr(self.soil, 'tile_size', TILE_SIZE)
                self.soil.water(tx, ty)
            elif self.selected_tool == 'axe':
                # damage trees at target
                if self.tree_sprites is not None:
                    for tree in self.tree_sprites.sprites():
                        if tree.rect.collidepoint(self.target_pos):
                            try:
                                tree.damage()
                            except Exception:
                                pass
        except Exception:
            pass

    def _on_seed_use_done(self):
        try:
            tx = int(self.target_pos[0]) // getattr(self.soil, 'tile_size', TILE_SIZE)
            ty = int(self.target_pos[1]) // getattr(self.soil, 'tile_size', TILE_SIZE)
            if self.seed_inventory.get(self.selected_seed, 0) > 0:
                self.soil.plant(tx, ty, self.selected_seed)
                self.seed_inventory[self.selected_seed] -= 1
        except Exception:
            pass

    def import_assets(self):
        # load animation folders from assets_dir/sprites/character/<animation>
        self.animations = {k: [] for k in ['up','down','left','right','up_idle','down_idle','left_idle','right_idle','up_hoe','down_hoe','left_hoe','right_hoe','up_axe','down_axe','left_axe','right_axe','up_water','down_water','left_water','right_water']}
        try:
            if hasattr(self, 'assets_dir') and self.assets_dir is not None:
                base = Path(self.assets_dir) / 'sprites' / 'character'
                for name in list(self.animations.keys()):
                    folder = base / name
                    if folder.exists() and folder.is_dir():
                        files = sorted(folder.glob('*.png'))
                        for f in files:
                            try:
                                surf = pygame.image.load(str(f)).convert_alpha()
                                self.animations[name].append(surf)
                            except Exception:
                                pass
        except Exception:
            pass

    def animate(self, dt: float):
        try:
            frames = self.animations.get(self.status, None)
            if frames:
                self.frame_index += 6 * dt
                if self.frame_index >= len(frames):
                    self.frame_index = 0
                self.image = frames[int(self.frame_index)]
            else:
                # fallback to base image
                pass
        except Exception:
            pass

    def input(self):
        keys = self._keys if hasattr(self, '_keys') else pygame.key.get_pressed()
        # Only accept input when not using tools and not sleeping
        if not self.timers['tool use'].running and not self.sleep:
            # movement
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.direction.y = -1
                self.status = 'up'
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.direction.y = 1
                self.status = 'down'
            else:
                self.direction.y = 0

            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.direction.x = 1
                self.status = 'right'
            elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.direction.x = -1
                self.status = 'left'
            else:
                self.direction.x = 0

            # Tool use (SPACE)
            if keys[pygame.K_SPACE] and not self.timers['tool use'].running:
                self.timers['tool use'].start()
                self.direction = pygame.math.Vector2()
                self.frame_index = 0

            # Change tool (Q)
            if keys[pygame.K_q] and not self.timers['tool switch'].running:
                self.timers['tool switch'].start()
                self.tool_index = (self.tool_index + 1) % len(self.tools)
                self.selected_tool = self.tools[self.tool_index]

            # Seed use (LCTRL)
            if keys[pygame.K_LCTRL] and not self.timers['seed use'].running:
                self.timers['seed use'].start()
                self.direction = pygame.math.Vector2()
                self.frame_index = 0

            # Change seed (E)
            if keys[pygame.K_e] and not self.timers['seed switch'].running:
                self.timers['seed switch'].start()
                self.seed_index = (self.seed_index + 1) % len(self.seeds)
                self.selected_seed = self.seeds[self.seed_index]

            # Interact / sleep (RETURN)
            if keys[pygame.K_RETURN]:
                collided = []
                try:
                    if self.interaction_sprites is not None:
                        for it in self.interaction_sprites.sprites():
                            if it.rect.colliderect(self.hitbox):
                                collided.append(it)
                except Exception:
                    collided = []
                if collided:
                    name = getattr(collided[0], 'name', None)
                    if name == 'Trader' and self.toggle_shop:
                        self.toggle_shop(True)
                    else:
                        self.status = 'left_idle'
                        self.sleep = True

        # hotbar selection (1-5) and perform action (space alternative)
        try:
            for i, k in enumerate((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)):
                if keys[k]:
                    self.selected_slot = i
                    # also update selected tool/seed for convenience
                    slot = self.hotbar[i]
                    if slot in self.tools:
                        self.selected_tool = slot
                    elif slot in self.seeds:
                        self.selected_seed = slot
            # action via space/return already handled
        except Exception:
            pass

    def get_status(self):
        # Idle
        try:
            if self.direction.length() == 0:
                self.status = self.status.split('_')[0] + '_idle'
            # timers determine tool animations
            if self.timers['tool use'].running:
                self.status = self.status.split('_')[0] + '_' + self.selected_tool
            if self.timers['seed use'].running:
                self.status = self.status.split('_')[0] + '_hoe'
        except Exception:
            pass

    def get_target_pos(self):
        try:
            base = pygame.math.Vector2(self.rect.center)
            key = self.status.split('_')[0]
            offset = PLAYER_TOOL_OFFSET.get(key, pygame.math.Vector2(0, 0))
            self.target_pos = base + offset
        except Exception:
            self.target_pos = pygame.math.Vector2(self.rect.center)

    def collision(self, direction):
        try:
            for sprite in self.collision_sprites.sprites():
                if getattr(sprite, 'hitbox', None) is not None and sprite.hitbox.colliderect(self.hitbox):
                    if direction == 'horizontal':
                        if self.direction.x > 0:
                            self.hitbox.right = sprite.hitbox.left
                        if self.direction.x < 0:
                            self.hitbox.left = sprite.hitbox.right
                        self.rect.centerx = self.hitbox.centerx
                        self.pos.x = self.hitbox.centerx
                    if direction == 'vertical':
                        if self.direction.y > 0:
                            self.hitbox.bottom = sprite.hitbox.top
                        if self.direction.y < 0:
                            self.hitbox.top = sprite.hitbox.bottom
                        self.rect.centery = self.hitbox.centery
                        self.pos.y = self.hitbox.centery
        except Exception:
            pass

    def move(self, dt: float):
        try:
            if self.direction.length() > 1:
                self.direction = self.direction.normalize()

            # Horizontal
            self.pos.x += self.direction.x * self.speed * dt
            self.hitbox.centerx = round(self.pos.x)
            self.rect.centerx = self.hitbox.centerx
            self.collision('horizontal')

            # Vertical
            self.pos.y += self.direction.y * self.speed * dt
            self.hitbox.centery = round(self.pos.y)
            self.rect.centery = self.hitbox.centery
            self.collision('vertical')
        except Exception:
            pass

