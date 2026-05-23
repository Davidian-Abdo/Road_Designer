"""Road Designer V 1.0 — BET-grade road design from terrain CSV + axe file."""

from .config import (
    DesignConfig,
    TypicalSection,
    CartoucheInfo,
    REFT_CAT_1,
    REFT_CAT_2,
    REFT_CAT_3,
)
from .road_design import RoadDesign, build_design

__version__ = "1.0.0"
__all__ = [
    "DesignConfig",
    "TypicalSection",
    "CartoucheInfo",
    "REFT_CAT_1",
    "REFT_CAT_2",
    "REFT_CAT_3",
    "RoadDesign",
    "build_design",
]
