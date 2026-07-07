"""Research strategy definitions."""

from ashare_research.strategies.moving_average import moving_average_crossover_signals
from ashare_research.strategies.relative_strength import relative_strength_signals
from ashare_research.strategies.registry import registry

__all__ = ["moving_average_crossover_signals", "relative_strength_signals", "registry"]
