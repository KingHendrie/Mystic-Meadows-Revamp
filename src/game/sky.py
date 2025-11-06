"""Sky and Rain visuals.

This is a lightweight implementation that provides a day/night tint overlay
and a simple rain flag. It's intentionally minimal so it can be iterated on
later with actual timed sky transitions and particle systems.
"""
from __future__ import annotations
import pygame
from typing import Tuple


class Sky:
    def __init__(self, window_size: Tuple[int, int]):
        self.width, self.height = window_size
        # overlay surface used to tint the scene for dawn/dusk/night
        self.overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        # simple state: 0.0 (day) .. 1.0 (night)
        self.time_of_day = 0.0
        self.speed = 0.0  # if >0, advances automatically
        self.target = 0.0

    def set_time(self, t: float):
        self.time_of_day = max(0.0, min(1.0, t))

    def update(self, dt: float):
        if self.speed and self.time_of_day != self.target:
            # move towards target slowly
            if self.time_of_day < self.target:
                self.time_of_day = min(self.target, self.time_of_day + dt * self.speed)
            else:
                self.time_of_day = max(self.target, self.time_of_day - dt * self.speed)

    def set_night(self):
        self.target = 1.0

    def set_day(self):
        self.target = 0.0

    def display(self, surface: pygame.Surface) -> None:
        """Draw a translucent overlay representing current time of day.

        time_of_day 0 -> no overlay; 1 -> dark overlay.
        """
        try:
            # compute alpha from time_of_day
            alpha = int(self.time_of_day * 180)
            self.overlay.fill((10, 20, 60, alpha))
            surface.blit(self.overlay, (0, 0))
        except Exception:
            return


class Rain:
    def __init__(self):
        self.active = False
        self.droplets = []

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def update(self, dt: float):
        # placeholder: no heavy particle system here
        pass
