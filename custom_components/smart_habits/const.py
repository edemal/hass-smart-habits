"""Constants for the Smart Habits integration."""

DOMAIN = "smart_habits"

CONF_LOOKBACK_DAYS = "lookback_days"
DEFAULT_LOOKBACK_DAYS = 30
LOOKBACK_OPTIONS = ["7", "14", "30", "90"]

CONF_ANALYSIS_INTERVAL = "analysis_interval"
DEFAULT_ANALYSIS_INTERVAL = 1
ANALYSIS_INTERVAL_OPTIONS = ["1", "3", "7"]

DEFAULT_ENTITY_DOMAINS = [
    "light",
    "switch",
    "binary_sensor",
    "input_boolean",
    "person",
    "device_tracker",
]

# Pattern detection thresholds
DEFAULT_MIN_CONFIDENCE = 0.6
MIN_EVENTS_THRESHOLD = 5

# Stale automation detection threshold (MGMT-03)
STALE_AUTOMATION_DAYS = 30

# Temporal sequence detection configuration
CONF_SEQUENCE_WINDOW = "sequence_window"
DEFAULT_SEQUENCE_WINDOW = 300  # seconds (5 minutes)
SEQUENCE_WINDOW_OPTIONS = ["60", "120", "300", "600", "900"]

# Automation creation prefix for deterministic IDs (AUTO-05)
AUTOMATION_ID_PREFIX = "smart_habits_"
