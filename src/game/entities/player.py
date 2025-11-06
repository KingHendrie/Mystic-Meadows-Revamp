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
        # private x/y storage; external code sets player.x/player.y and
        # the properties below keep rect/pos/hitbox synchronized
        self._x = x
        self._y = y
        # keep assets_dir for loading animations/sounds
        self.assets_dir = assets_dir
        # gameplay state (defaults aligned with backup implementation)
        self.money = 200
        self.energy = 100
        # support both names used across the codebase
        self.inventory = {'wood': 0, 'apple': 0, 'corn': 0, 'tomato': 0}
        self.item_inventory = self.inventory
        self.speed = 120.0

        # visual: try to load an asset from assets_dir, otherwise fallback to simple block
        surf = None
        try:
            if assets_dir is not None:
                p = Path(assets_dir) / "sprites"
                if p.exists():
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

        # rect and hitbox
        self.rect = self.image.get_rect(center=(int(self._x), int(self._y)))
        self.hitbox = self.rect.copy()
        try:
            # backup used a large negative inflate to shrink the hitbox; keep same values
            self.hitbox.inflate_ip(-126, -70)
        except Exception:
            # fallback: small shrink if original inflate would be invalid for small sprites
            self.hitbox.inflate_ip(-8, -8)
        self.z = 4
        # use project layer mapping for player render order when available
        try:
            from data.config.settings import LAYERS
            self.z = LAYERS.get('main', 7)
        except Exception:
            pass

        # load animations if available
        try:
            self.import_assets()
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
        self.status = 'down_idle'
        self.frame_index = 0.0
        self.sleep = False
        # previous-key edge detections
        self._return_prev = False
        # track space key edge for interaction vs tool usage
        self._space_prev = False
        # facing used by some helper APIs (perform_action)
        self.facing = 'down'

        # position & movement (compat with backup impl)
        self.pos = pygame.math.Vector2(self.rect.center)
        self.direction = pygame.math.Vector2()
        self.speed = 160

        # Timers (use seconds)
        from src.game.timer import Timer
        self.timers = {
            'tool use': Timer(0.35),
            'tool switch': Timer(0.2),
            'seed use': Timer(0.35),
            'seed switch': Timer(0.2)
        }

        # Tools and seeds
        self.tools = ['hoe', 'axe', 'water']
        self.tool_index = 0
        self.selected_tool = self.tools[self.tool_index]

        # inventory and seeds - start with small starter seeds like the backup
        self.item_inventory = self.inventory
        self.seed_inventory = {'corn': 5, 'tomato': 5}

        self.seeds = ['corn', 'tomato']
        self.seed_index = 0
        self.selected_seed = self.seeds[self.seed_index]

        # hotbar (visual mapping) keep existing simple hotbar too
        # include axe so players can use it from the hotbar
        self.hotbar = ["hoe", "axe", "water", "corn", "tomato"]
        # selected hotbar slot (use property below to keep tool/seed in sync)
        self._selected_slot = 0

        # world refs
        self.tree_sprites = None
        self.interaction_sprites = None
        # optional sounds (non-fatal if missing)
        try:
            if self.assets_dir is not None:
                p = Path(self.assets_dir) / 'audio' / 'water.mp3'
                if p.exists():
                    # use module-level pygame imported at top
                    self.watering = pygame.mixer.Sound(str(p))
                    self.watering.set_volume(0.2)
                else:
                    self.watering = None
        except Exception:
            self.watering = None

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

    # x/y properties keep visual rect/pos in sync when external code sets them
    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value: float):
        try:
            self._x = value
            # update rect and hitbox centers and pos
            if getattr(self, 'rect', None) is not None:
                self.rect.centerx = int(value)
            if getattr(self, 'hitbox', None) is not None:
                self.hitbox.centerx = self.rect.centerx
            if getattr(self, 'pos', None) is not None:
                self.pos.x = self.hitbox.centerx
        except Exception:
            pass

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value: float):
        try:
            self._y = value
            if getattr(self, 'rect', None) is not None:
                self.rect.centery = int(value)
            if getattr(self, 'hitbox', None) is not None:
                self.hitbox.centery = self.rect.centery
            if getattr(self, 'pos', None) is not None:
                self.pos.y = self.hitbox.centery
        except Exception:
            pass

    # selected_slot property keeps hotbar selection synchronized with tool/seed
    @property
    def selected_slot(self):
        return getattr(self, '_selected_slot', 0)

    @selected_slot.setter
    def selected_slot(self, value):
        try:
            value = int(value)
        except Exception:
            value = 0
        hotbar_len = len(getattr(self, 'hotbar', [])) or 1
        self._selected_slot = value % hotbar_len
        # sync selected tool/seed when slot changes
        try:
            slot = self.hotbar[self._selected_slot]
            if slot in getattr(self, 'tools', []):
                self.selected_tool = slot
            elif slot in getattr(self, 'seeds', []):
                self.selected_seed = slot
        except Exception:
            pass

    def use_tool_till(self, soil, tx: int, ty: int) -> bool:
        return soil.till(tx, ty)

    def use_tool_axe(self, soil, tx: int, ty: int) -> bool:
        """Use the axe at tile coords: damage any tree whose rect contains the tile center.
        Returns True if any tree was damaged."""
        try:
            # convert tile coords to world center point
            tile_size = getattr(soil, 'tile_size', TILE_SIZE)
            px = tx * tile_size + tile_size // 2
            py = ty * tile_size + tile_size // 2
            if self.tree_sprites is None:
                return False
            any_hit = False
            for tree in list(self.tree_sprites.sprites()):
                try:
                    if tree.rect.collidepoint((px, py)):
                        try:
                            tree.damage()
                        except Exception:
                            pass
                        any_hit = True
                except Exception:
                    pass
            return any_hit
        except Exception:
            return False

    def use_tool_plant(self, soil, tx: int, ty: int, seed_id: str) -> bool:
        # Use seed_inventory for seeds (consistent with seed use paths)
        seed_count = getattr(self, 'seed_inventory', {}).get(seed_id, None)
        if seed_count is None:
            # fallback to generic inventory for legacy items
            seed_count = self.inventory.get(seed_id, 0)
            if seed_count <= 0:
                return False
            ok = soil.plant(tx, ty, seed_id)
            if ok:
                self.inventory[seed_id] = self.inventory.get(seed_id, 0) - 1
            return ok

        # seed_inventory path
        if seed_count <= 0:
            return False
        ok = soil.plant(tx, ty, seed_id)
        if ok:
            try:
                self.seed_inventory[seed_id] = max(0, self.seed_inventory.get(seed_id, 0) - 1)
            except Exception:
                pass
        return ok

    def use_tool_water(self, soil, tx: int, ty: int) -> bool:
        # water a small area (3x3) centered on tx,ty to match typical watering can behaviour
        try:
            watered = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx = tx + dx
                    ny = ty + dy
                    try:
                        if soil.water(nx, ny):
                            watered = True
                    except Exception:
                        pass
            return watered
        except Exception:
            return False

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
        if tool_name == "axe":
            return self.use_tool_axe(self.soil, tile_x, tile_y)
        if tool_name == "harvest":
            res = self.try_harvest(self.soil)
            if res:
                # give to player inventory
                self.inventory[res] = self.inventory.get(res, 0) + 1
                # toast via HUD if available
                try:
                    ui = getattr(getattr(self, 'farm', None), 'ui', None)
                    if ui is not None:
                        ui.toast(f"Harvested {res}", 2.0)
                except Exception:
                    pass
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
            # use current rect center so actions follow the player's visual position
            tx = int(self.rect.centerx) // tile_size
            ty = int(self.rect.centery) // tile_size
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
            if isinstance(slot, str):
                # prefer seed_inventory for seed counts
                seed_count = getattr(self, 'seed_inventory', {}).get(slot, None)
                if seed_count is None:
                    seed_count = self.inventory.get(slot, 0)
                    if seed_count <= 0:
                        return False
                    ok = self.soil.plant(tx, ty, slot)
                    if ok:
                        self.inventory[slot] = self.inventory.get(slot, 0) - 1
                    return ok
                else:
                    if seed_count <= 0:
                        return False
                    ok = self.soil.plant(tx, ty, slot)
                    if ok:
                        try:
                            self.seed_inventory[slot] = max(0, self.seed_inventory.get(slot, 0) - 1)
                        except Exception:
                            pass
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
                        # clear movement so the player doesn't slide during the sleep transition
                        try:
                            self.direction = pygame.math.Vector2()
                        except Exception:
                            pass
                        self.sleep = True
                        return "bed"
        except Exception:
            return None
        return None

    def player_add(self, item_id: str, amount: int = 1):
        self.inventory[item_id] = self.inventory.get(item_id, 0) + amount

    # --- Backup-style methods: timers, assets, input, animation, movement ---
    def _on_tool_use_done(self, slot: str | None = None, target_pos=None):
        # called when tool use timer finishes. Use the captured slot and target_pos
        try:
            tool = slot or getattr(self, 'selected_tool', None)
            tp = target_pos or getattr(self, 'target_pos', None)
            if tp is None:
                return
            tx = int(tp[0]) // getattr(self.soil, 'tile_size', TILE_SIZE)
            ty = int(tp[1]) // getattr(self.soil, 'tile_size', TILE_SIZE)

            # Debug: report tool use and computed tile coords
            try:
                print(f"_on_tool_use_done: tool={tool}, target_pos={tp}, tile=({tx},{ty})")
            except Exception:
                pass

            if tool == 'hoe':
                # try to use SoilLayer.get_hit if present (backup compatibility), else till
                try:
                    if hasattr(self.soil, 'get_hit'):
                        res = self.soil.get_hit(tp)
                        try:
                            print(f"soil.get_hit returned: {res}")
                        except Exception:
                            pass
                        if not res:
                            # fallback to till by tile coords
                            res2 = self.soil.till(tx, ty)
                            try:
                                print(f"soil.till fallback returned: {res2} for tile {tx},{ty}")
                            except Exception:
                                pass
                    else:
                        res2 = self.soil.till(tx, ty)
                        try:
                            print(f"soil.till returned: {res2} for tile {tx},{ty}")
                        except Exception:
                            pass
                except Exception:
                    try:
                        self.soil.till(tx, ty)
                    except Exception:
                        pass
            elif tool == 'water':
                try:
                    self.soil.water(tx, ty)
                    try:
                        if getattr(self, 'watering', None) is not None:
                            self.watering.play()
                    except Exception:
                        pass
                except Exception:
                    pass
            elif tool == 'axe':
                # damage trees at target_pos
                if self.tree_sprites is not None:
                    for tree in self.tree_sprites.sprites():
                        if tree.rect.collidepoint(tp):
                            try:
                                tree.damage()
                            except Exception:
                                pass
            # clear any placement preview now that the action completed
            try:
                if getattr(self, 'soil', None) is not None:
                    try:
                        self.soil.clear_preview()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_seed_use_done(self, seed: str | None = None, target_pos=None):
        try:
            s = seed or getattr(self, 'selected_seed', None)
            tp = target_pos or getattr(self, 'target_pos', None)
            if tp is None or s is None:
                return
            tx = int(tp[0]) // getattr(self.soil, 'tile_size', TILE_SIZE)
            ty = int(tp[1]) // getattr(self.soil, 'tile_size', TILE_SIZE)
            if self.seed_inventory.get(s, 0) > 0:
                try:
                    ok = self.soil.plant(tx, ty, s)
                    if ok:
                        try:
                            self.seed_inventory[s] = max(0, self.seed_inventory.get(s, 0) - 1)
                        except Exception:
                            pass
                except Exception:
                    pass
            # clear preview after planting
            try:
                if getattr(self, 'soil', None) is not None:
                    try:
                        self.soil.clear_preview()
                    except Exception:
                        pass
            except Exception:
                pass
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
        try:
            space_pressed = bool(keys[pygame.K_SPACE])
        except Exception:
            space_pressed = False
        # Only accept input when not using tools and not sleeping/transitioning
        # If the farm transition is running (day/night sleep animation), treat the player
        # as not accepting input so they cannot move until transition completes.
        try:
            transition_running = bool(getattr(self, 'farm', None) and getattr(self.farm, 'transition', None) and getattr(self.farm.transition, 'running', False))
        except Exception:
            transition_running = False
        if not self.timers['tool use'].running and not self.sleep and not transition_running:
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

            # Action key (SPACE): start tool or seed use depending on selected hotbar slot
            # If the player pressed SPACE this frame and is standing on an interaction
            # trigger (Bed/Trader), prefer the interaction instead of using the tool.
            if space_pressed and not getattr(self, '_space_prev', False):
                try:
                    if self.interaction_sprites is not None:
                        for it in self.interaction_sprites.sprites():
                            if it.rect.colliderect(self.hitbox):
                                res = self.interact()
                                if res == 'trader':
                                    try:
                                        if self.toggle_shop:
                                            self.toggle_shop(True)
                                    except Exception:
                                        pass
                                    # consume this space press (edge) and skip tool handling
                                    self._space_prev = True
                                    return
                                if res == 'bed':
                                    try:
                                        self.status = 'left_idle'
                                    except Exception:
                                        pass
                                    self._space_prev = True
                                    return
                except Exception:
                    pass
            if keys[pygame.K_SPACE]:
                try:
                    slot = self.hotbar[self.selected_slot]
                except Exception:
                    slot = None
                # if slot corresponds to a seed, start seed use timer
                if slot in getattr(self, 'seeds', []):
                    # don't start if player has no seeds for this slot
                    seed_count = getattr(self, 'seed_inventory', {}).get(slot, None)
                    if seed_count is None:
                        seed_count = self.inventory.get(slot, 0)
                    if seed_count <= 0:
                        # nothing to plant
                        return
                    if not self.timers['seed use'].running:
                        # compute & capture current target_pos so callback uses the correct values
                        try:
                            self.get_target_pos()
                        except Exception:
                            pass
                        tp = tuple(getattr(self, 'target_pos', (self.rect.centerx, self.rect.centery)))
                        # show a placement preview immediately (tile coords)
                        try:
                            if getattr(self, 'soil', None) is not None:
                                tile_size = getattr(self.soil, 'tile_size', TILE_SIZE)
                                tx = int(tp[0]) // tile_size
                                ty = int(tp[1]) // tile_size
                                try:
                                    self.soil.clear_preview()
                                except Exception:
                                    pass
                                try:
                                    self.soil.preview_tile(tx, ty)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        self.timers['seed use'].callback = (lambda s=slot, tpos=tp: self._on_seed_use_done(s, tpos))
                        self.timers['seed use'].start()
                        self.direction = pygame.math.Vector2()
                        self.frame_index = 0
                else:
                    # treat as tool/harvest
                    if not self.timers['tool use'].running:
                        try:
                            self.get_target_pos()
                        except Exception:
                            pass
                        tp = tuple(getattr(self, 'target_pos', (self.rect.centerx, self.rect.centery)))
                        # show a placement preview immediately (tile coords)
                        try:
                            if getattr(self, 'soil', None) is not None:
                                tile_size = getattr(self.soil, 'tile_size', TILE_SIZE)
                                tx = int(tp[0]) // tile_size
                                ty = int(tp[1]) // tile_size
                                try:
                                    self.soil.clear_preview()
                                except Exception:
                                    pass
                                try:
                                    self.soil.preview_tile(tx, ty)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # capture slot and target position at start
                        self.timers['tool use'].callback = (lambda s=slot, tpos=tp: self._on_tool_use_done(s, tpos))
                        self.timers['tool use'].start()
                        self.direction = pygame.math.Vector2()
                        self.frame_index = 0

            # Seed use (LCTRL)
            if keys[pygame.K_LCTRL] and not self.timers['seed use'].running:
                try:
                    self.get_target_pos()
                except Exception:
                    pass
                tp = tuple(getattr(self, 'target_pos', (self.rect.centerx, self.rect.centery)))
                # use currently selected_seed at the time LCTRL was pressed
                seed = getattr(self, 'selected_seed', None)
                # ensure we have at least one seed
                seed_count = getattr(self, 'seed_inventory', {}).get(seed, None)
                if seed_count is None:
                    seed_count = self.inventory.get(seed, 0)
                if seed is None or seed_count <= 0:
                    # nothing to plant
                    return
                # show placement preview for LCTRL planting
                try:
                    if getattr(self, 'soil', None) is not None:
                        tile_size = getattr(self.soil, 'tile_size', TILE_SIZE)
                        tx = int(tp[0]) // tile_size
                        ty = int(tp[1]) // tile_size
                        try:
                            self.soil.clear_preview()
                        except Exception:
                            pass
                        try:
                            self.soil.preview_tile(tx, ty)
                        except Exception:
                            pass
                except Exception:
                    pass
                self.timers['seed use'].callback = (lambda s=seed, tpos=tp: self._on_seed_use_done(s, tpos))
                self.timers['seed use'].start()
                self.direction = pygame.math.Vector2()
                self.frame_index = 0
            # NOTE: removed Q/E cycling. Hotbar selection is the single source of truth.

            # Interact / sleep (RETURN)
            # Interact / sleep (RETURN) - edge detect so a single press triggers
            try:
                return_pressed = bool(keys[pygame.K_RETURN])
            except Exception:
                return_pressed = False
            if return_pressed and not getattr(self, '_return_prev', False):
                # on keydown, attempt interaction via invisible Interaction sprites
                try:
                    res = self.interact()
                    try:
                        print(f"Player.interact() -> {res}")
                    except Exception:
                        pass
                    if res == 'trader':
                        # Farm.toggle_shop will handle proximity in farm; call toggle directly
                        try:
                            if self.toggle_shop:
                                self.toggle_shop(True)
                        except Exception:
                            pass
                    elif res == 'bed':
                        # set sleep; Farm will start transition when it sees player.sleep
                        try:
                            self.status = 'left_idle'
                        except Exception:
                            pass
                except Exception:
                    pass
            # update prev key state
            try:
                self._return_prev = return_pressed
            except Exception:
                pass
            try:
                self._space_prev = space_pressed
            except Exception:
                pass

        # hotbar selection (1-5) and perform action (space alternative)
        try:
            for i, k in enumerate((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)):
                if keys[k]:
                    # set selected slot (property will keep tool/seed synced)
                    self.selected_slot = i
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
            # keep facing in sync with status base (up/down/left/right)
            self.facing = self.status.split('_')[0]
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
                # prefer a sprite.hitbox when available, otherwise use sprite.rect
                other_box = getattr(sprite, 'hitbox', None) or getattr(sprite, 'rect', None)
                if other_box is None:
                    continue
                if other_box.colliderect(self.hitbox):
                    if direction == 'horizontal':
                        if self.direction.x > 0:
                            # moving right -> place player's right to other's left
                            self.hitbox.right = other_box.left
                        if self.direction.x < 0:
                            self.hitbox.left = other_box.right
                        self.rect.centerx = self.hitbox.centerx
                        self.pos.x = self.hitbox.centerx
                    if direction == 'vertical':
                        if self.direction.y > 0:
                            self.hitbox.bottom = other_box.top
                        if self.direction.y < 0:
                            self.hitbox.top = other_box.bottom
                        self.rect.centery = self.hitbox.centery
                        self.pos.y = self.hitbox.centery
        except Exception:
            pass

    def move(self, dt: float):
        try:
            # Do not move while sleeping or while the day-transition is running
            try:
                if getattr(self, 'sleep', False):
                    return
            except Exception:
                pass
            try:
                if getattr(self, 'farm', None) and getattr(self.farm, 'transition', None) and getattr(self.farm.transition, 'running', False):
                    return
            except Exception:
                pass

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

