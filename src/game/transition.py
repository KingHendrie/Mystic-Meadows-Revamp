"""Simple day transition, sky and rain placeholder.

This module provides a Transition controller which can play a short
fade-out/fade-in animation and optionally trigger a callback when the day
advances (e.g., to call Farm.reset_day()). It's intentionally lightweight so
it can be expanded later into weather and richer visuals.
"""
from __future__ import annotations
import pygame
from typing import Callable, Optional


class Transition:
    def __init__(self, size: tuple[int, int], on_day_advance: Optional[Callable] = None):
        self.surface = pygame.Surface(size).convert_alpha()
        self.progress = 0.0
        self.duration = 1.0
        self.running = False
        self.on_day_advance = on_day_advance

    def start(self):
        self.running = True
        self.progress = 0.0

    def update(self, dt: float):
        if not self.running:
            return
        self.progress += dt
        if self.progress >= self.duration:
            # trigger day advance at midpoint
            self.running = False
            if self.on_day_advance:
                self.on_day_advance()

    def draw(self, target: pygame.Surface):
        if not self.running:
            return
        alpha = int(255 * (self.progress / self.duration))
        alpha = max(0, min(255, alpha))
        self.surface.fill((0, 0, 0, alpha))
        target.blit(self.surface, (0, 0))
