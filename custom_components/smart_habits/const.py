"""Constants for the Smart Habits integration."""

DOMAIN = "smart_habits"

CONF_LOOKBACK_DAYS = "lookback_days"
DEFAULT_LOOKBACK_DAYS = 30
LOOKBACK_OPTIONS = ["7", "14", "30", "90"]

DEFAULT_ENTITY_DOMAINS = [
    "light",
    "switch",
    "binary_sensor",
    "input_boolean",
    "person",
    "device_tracker",
]
