"""Backward-compatibility shim. Import from detectors/ instead."""
from .detectors.daily_routine import DailyRoutineDetector  # noqa: F401
from .detectors._utils import ACTIVE_STATES, SKIP_STATES  # noqa: F401
