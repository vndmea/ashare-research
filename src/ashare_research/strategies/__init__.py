"""Research strategy definitions."""

from ashare_research.strategies.moving_average import moving_average_crossover_signals
from ashare_research.strategies.registry import registry

__all__ = ["moving_average_crossover_signals", "registry"]
