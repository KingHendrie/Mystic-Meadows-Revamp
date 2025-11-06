"""Debug utilities extracted from HUD._run_debug_action.

Provides a single entrypoint `handle_debug_action(hud, key)` which performs
actions that operate on the HUD's player/farm. These were moved out of the
HUD class to keep UI code thin and make the actions easier to test.
"""
from __future__ import annotations
from pathlib import Path
import pygame
import json
import logging
from datetime import datetime

_log = logging.getLogger('mystic_meadows.debug_utils')


def _get_farm(hud):
    return getattr(getattr(hud, 'player', None), 'farm', None)


def handle_debug_action(hud, key: str):
    farm = _get_farm(hud)
    try:
        if key == 'Teleport':
            _teleport(farm)
            return
        if key == 'GrowAll':
            _grow_all(farm)
            return
        if key == 'WaterAll':
            _water_all(farm)
            return
        if key == 'RemovePlants':
            _remove_plants(farm)
            return
        if key == 'SaveNow':
            _save_now(farm)
            return
        if key == 'ListSaves':
            _list_saves(farm)
            return
        if key == 'DumpSave':
            _dump_save(farm)
            return
        if key == 'ToggleCollisions':
            _toggle_collisions(farm)
            return
        if key == 'ExportScreen':
            _export_screen(farm, hud)
            return
        if key == 'ExportSoil':
            _export_soil(farm, hud)
            return
    except Exception:
        _log.exception('handle_debug_action failed for %s', key)


def _teleport(farm):
    if farm is None:
        _log.debug('Teleport: no farm')
        return
    ps = list(getattr(getattr(farm, 'soil', None), 'plant_sprites', []).sprites())
    if not ps:
        _log.debug('Teleport: no plants')
        return
    p = ps[0]
    try:
        farm.player.x = p.rect.centerx
        farm.player.y = p.rect.centery
    except Exception:
        try:
            farm.player.rect.center = p.rect.center
        except Exception:
            pass
    _log.info('Teleport: moved player to plant at %s,%s', getattr(p, 'tx', None), getattr(p, 'ty', None))


def _grow_all(farm):
    if farm is None:
        return
    for p in list(getattr(getattr(farm, 'soil', None), 'plant_sprites', []).sprites()):
        try:
            p.growth_stage = getattr(p, 'max_stage', getattr(p, 'growth_stage', 0))
            if hasattr(p, 'frames') and getattr(p, 'frames', None):
                try:
                    p.image = p.frames[min(int(p.growth_stage), len(p.frames) - 1)]
                except Exception:
                    pass
            try:
                p.reposition()
            except Exception:
                pass
            p.harvestable = True
        except Exception:
            pass
    _log.info('GrowAll: set all plants to mature')


def _water_all(farm):
    if farm is None:
        return
    try:
        farm.soil.water_all()
        _log.info('WaterAll: watered all tilled tiles')
    except Exception:
        _log.exception('WaterAll failed')


def _remove_plants(farm):
    if farm is None:
        return
    try:
        for p in list(getattr(getattr(farm, 'soil', None), 'plant_sprites', []).sprites()):
            try:
                tx = getattr(p, 'tx', int(p.rect.x) // farm.tile_size)
                ty = getattr(p, 'ty', int(p.rect.y) // farm.tile_size)
                if farm.soil.in_bounds(tx, ty):
                    cell = farm.soil.grid[ty][tx]
                    try:
                        if 'P' in cell:
                            cell.remove('P')
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                p.kill()
            except Exception:
                pass
        _log.info('RemovePlants: removed all plants')
    except Exception:
        _log.exception('RemovePlants failed')


def _save_now(farm):
    if farm is None:
        return
    try:
        path = farm.save_game()
        _log.info('SaveNow: saved to %s', path)
    except Exception:
        _log.exception('SaveNow failed')


def _list_saves(farm):
    if farm is None or getattr(farm, 'save_system', None) is None:
        _log.info('ListSaves: no save system')
        return
    try:
        lst = farm.save_system.list_saves(getattr(farm, 'data_dir', None))
        names = [p.stem for p in lst]
        _log.info('ListSaves: %s', names)
    except Exception:
        _log.exception('ListSaves failed')


def _dump_save(farm):
    if farm is None or getattr(farm, 'save_system', None) is None:
        _log.info('DumpSave: no save system')
        return
    try:
        cur = getattr(farm, 'save_slot', 1)
        obj = farm.save_system.load(cur)
        payload = obj.get('payload', obj)
        _log.info('DumpSave slot=%s: %s', cur, str(payload)[:1000])
    except Exception:
        _log.exception('DumpSave failed')


def _toggle_collisions(farm):
    if farm is None:
        return
    try:
        cur = getattr(farm, '_debug_draw_collisions', False)
        setattr(farm, '_debug_draw_collisions', not cur)
        _log.info('ToggleCollisions: now %s', not cur)
    except Exception:
        _log.exception('ToggleCollisions failed')


def _export_screen(farm, hud=None):
    try:
        # prefer using farm.window_size so output matches in-game view
        if farm is None:
            _log.info('ExportScreen: no farm available')
            return
        win_w, win_h = getattr(farm, 'window_size', None) or (pygame.display.get_surface().get_width(), pygame.display.get_surface().get_height())
        now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        base = getattr(farm, 'data_dir', None) or Path('.')
        # group screenshots by current date for easier browsing
        date_dir = datetime.utcnow().strftime('%Y-%m-%d')
        outdir = Path(base) / 'screenshots' / date_dir
        outdir.mkdir(parents=True, exist_ok=True)
        slot = getattr(farm, 'save_slot', 'noslot')

        saved = []

        # 1) farm rendered view (no UI)
        try:
            surf_world = pygame.Surface((win_w, win_h)).convert_alpha()
            surf_world.fill((0, 0, 0, 0))
            try:
                farm.all_sprites.custom_draw(farm.player, surf_world)
            except Exception:
                # fallback: draw onto a plain surface by blitting display if available
                try:
                    ds = pygame.display.get_surface()
                    if ds is not None:
                        surf_world.blit(ds, (0, 0))
                except Exception:
                    pass
            fname = outdir / f"screenshot_farm_{slot}_{now}.png"
            try:
                pygame.image.save(surf_world, str(fname))
                saved.append(fname)
            except Exception:
                _log.exception('ExportScreen: failed to save farm view')
        except Exception:
            _log.exception('ExportScreen: farm view failed')

        # 2) color map (tile-level visualization)
        try:
            soil = getattr(farm, 'soil', None)
            if soil is not None:
                ts = getattr(soil, 'tile_size', getattr(farm, 'tile_size', 16))
                grid = getattr(soil, 'grid', [])
                w = len(grid[0]) if grid else (win_w // ts)
                h = len(grid) if grid else (win_h // ts)
                surf_color = pygame.Surface((win_w, win_h))
                surf_color.fill((0, 0, 0))
                # color mapping
                for y in range(h):
                    for x in range(w):
                        try:
                            cell = grid[y][x] if y < len(grid) and x < len(grid[y]) else []
                            # choose color
                            if 'P' in cell:
                                col = (200, 180, 60)  # plant
                            elif 'W' in cell:
                                col = (80, 140, 220)  # watered
                            elif 'F' in cell or 'X' in cell:
                                col = (140, 100, 60)  # tilled
                            else:
                                col = (100, 180, 90)  # grass
                            rect = pygame.Rect(x * ts, y * ts, ts, ts)
                            pygame.draw.rect(surf_color, col, rect)
                        except Exception:
                            pass
                fname = outdir / f"screenshot_color_{slot}_{now}.png"
                try:
                    pygame.image.save(surf_color, str(fname))
                    saved.append(fname)
                except Exception:
                    _log.exception('ExportScreen: failed to save color map')
        except Exception:
            _log.exception('ExportScreen: color map failed')

        # 3) collision map (rects)
        try:
            surf_col = pygame.Surface((win_w, win_h)).convert_alpha()
            surf_col.fill((0, 0, 0, 0))
            try:
                for c in list(getattr(farm, 'collision_sprites', []).sprites()):
                    try:
                        dest = c.rect.move((win_w//2 - farm.player.rect.centerx, win_h//2 - farm.player.rect.centery))
                        pygame.draw.rect(surf_col, (255, 80, 0), dest, 1)
                    except Exception:
                        pass
            except Exception:
                pass
            fname = outdir / f"screenshot_collisions_{slot}_{now}.png"
            try:
                pygame.image.save(surf_col, str(fname))
                saved.append(fname)
            except Exception:
                _log.exception('ExportScreen: failed to save collisions map')
        except Exception:
            _log.exception('ExportScreen: collisions map failed')

        # 4) plant map (plant positions)
        try:
            surf_plants = pygame.Surface((win_w, win_h)).convert_alpha()
            surf_plants.fill((0, 0, 0, 0))
            try:
                for p in list(getattr(getattr(farm, 'soil', None), 'plant_sprites', []).sprites()):
                    try:
                        dest = p.rect.move((win_w//2 - farm.player.rect.centerx, win_h//2 - farm.player.rect.centery))
                        pygame.draw.rect(surf_plants, (240, 200, 80), dest)
                    except Exception:
                        pass
            except Exception:
                pass
            fname = outdir / f"screenshot_plants_{slot}_{now}.png"
            try:
                pygame.image.save(surf_plants, str(fname))
                saved.append(fname)
            except Exception:
                _log.exception('ExportScreen: failed to save plants map')
        except Exception:
            _log.exception('ExportScreen: plants map failed')

        # 5) HUD overlay only
        try:
            if hud is not None:
                surf_hud = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
                try:
                    hud.display(surf_hud)
                except Exception:
                    pass
                fname = outdir / f"screenshot_hud_{slot}_{now}.png"
                try:
                    pygame.image.save(surf_hud, str(fname))
                    saved.append(fname)
                except Exception:
                    _log.exception('ExportScreen: failed to save hud map')
        except Exception:
            _log.exception('ExportScreen: hud map failed')

        # friendly toast summarizing results
        try:
            if hud is not None:
                if saved:
                    hud.toast(f"Exported {len(saved)} images to {outdir}", duration=3.5, ttype='success')
                else:
                    hud.toast('ExportScreen: nothing was saved', duration=3.0, ttype='error')
        except Exception:
            pass

        for p in saved:
            _log.info('ExportScreen: saved %s', str(p))
    except Exception:
        _log.exception('ExportScreen top-level error')


def _export_soil(farm, hud=None):
    try:
        if farm is None or getattr(farm, 'soil', None) is None:
            _log.info('ExportSoil: no farm/soil available')
            return
        soil = farm.soil
        export = {}
        try:
            export['grid'] = [[list(cell) for cell in row] for row in getattr(soil, 'grid', [])]
        except Exception:
            export['grid'] = None
        try:
            plants = []
            for p in list(getattr(soil, 'plant_sprites', []).sprites()):
                try:
                    plants.append({
                        'type': getattr(p, 'plant_type', None),
                        'tx': getattr(p, 'tx', None),
                        'ty': getattr(p, 'ty', None),
                        'growth_stage': getattr(p, 'growth_stage', None),
                        'harvestable': getattr(p, 'harvestable', None),
                    })
                except Exception:
                    pass
            export['plants'] = plants
        except Exception:
            export['plants'] = None
        base = getattr(farm, 'data_dir', None) or Path('.')
        outdir = Path(base) / 'exports'
        outdir.mkdir(parents=True, exist_ok=True)
        now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        slot = getattr(farm, 'save_slot', 'noslot')
        fname = outdir / f"soil_export_{slot}_{now}.json"
        try:
            with open(fname, 'w', encoding='utf-8') as fh:
                json.dump(export, fh, indent=2)
            _log.info('ExportSoil: saved %s', str(fname))
            try:
                if hud is not None:
                    hud.toast(f"Exported soil: {fname.name}", duration=3.0, ttype='success')
            except Exception:
                pass
        except Exception:
            _log.exception('ExportSoil: failed to write')
    except Exception:
        _log.exception('ExportSoil top-level error')
