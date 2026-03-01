"""Coordinator for the Smart Habits integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_LOOKBACK_DAYS,
    CONF_SEQUENCE_WINDOW,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_SEQUENCE_WINDOW,
    DOMAIN,
    STALE_AUTOMATION_DAYS,
)
from .models import StaleAutomation
from .detectors import DailyRoutineDetector, PresencePatternDetector, TemporalSequenceDetector
from .recorder_reader import RecorderReader
from .storage import DismissedPatternsStore, AcceptedPatternsStore

_LOGGER = logging.getLogger(__name__)


class SmartHabitsCoordinator(DataUpdateCoordinator):
    """Manages data access and background analysis for the Smart Habits integration.

    Uses DataUpdateCoordinator with a configurable timedelta update_interval so HA
    re-runs analysis on the user's chosen schedule (1, 3, or 7 days). The interval
    is read from entry.options first, falling back to entry.data, then the default.
    The options update listener in __init__.py updates coordinator.update_interval
    and coordinator.lookback_days live whenever the user changes options.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        analysis_interval_days = int(
            entry.options.get(
                CONF_ANALYSIS_INTERVAL,
                entry.data.get(CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL),
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=analysis_interval_days),
        )
        self.entry = entry
        self.reader = RecorderReader(hass)
        self.lookback_days: int = int(
            entry.options.get(
                CONF_LOOKBACK_DAYS,
                entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
            )
        )
        self.min_confidence: float = DEFAULT_MIN_CONFIDENCE
        self.sequence_window: int = int(
            entry.options.get(
                CONF_SEQUENCE_WINDOW,
                entry.data.get(CONF_SEQUENCE_WINDOW, DEFAULT_SEQUENCE_WINDOW),
            )
        )
        self.dismissed_store = DismissedPatternsStore(hass)
        self.accepted_store = AcceptedPatternsStore(hass)

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Runs during async_config_entry_first_refresh. Loads dismissed patterns
        from persistent storage before the first scan so that dismissed patterns
        are filtered from the very first _async_update_data call.
        """
        await self.dismissed_store.async_load()
        await self.accepted_store.async_load()
        _LOGGER.debug("Smart Habits coordinator initialized")

    def _run_all_detectors(
        self, states: dict, lookback_days: int
    ) -> list:
        """Run all three detectors synchronously and return merged pattern list.

        Intended to be called via hass.async_add_executor_job (generic executor)
        so it does not block the event loop. Runs under GIL — safe to read
        self.min_confidence and self.sequence_window without locks (RESEARCH
        pitfall 3: read-only attributes set before executor call).

        Returns a merged list of DetectedPattern objects from all three detectors.
        """
        daily_detector = DailyRoutineDetector(min_confidence=self.min_confidence)
        daily_patterns = daily_detector.detect(states, lookback_days)

        seq_detector = TemporalSequenceDetector(
            window_seconds=self.sequence_window,
            min_confidence=self.min_confidence,
        )
        seq_patterns = seq_detector.detect(states, lookback_days)

        presence_detector = PresencePatternDetector(
            window_seconds=self.sequence_window,
            min_confidence=self.min_confidence,
        )
        presence_patterns = presence_detector.detect(states, lookback_days)

        return daily_patterns + seq_patterns + presence_patterns

    async def _async_update_data(self) -> dict:
        """Fetch state history from Recorder and run pattern detection.

        DB I/O runs inside RecorderReader via the recorder's dedicated executor.
        CPU-bound detection runs via hass.async_add_executor_job (generic executor)
        as a single _run_all_detectors call to avoid multiple round-trips through
        the executor queue (Phase 6 consolidation).
        Dismissed patterns are filtered (MGMT-02), accepted patterns are separated
        (Phase 6), and stale automations are detected from the HA state machine
        (MGMT-03, no Recorder query needed).
        """
        entity_ids = self.reader.get_analyzable_entity_ids()
        if not entity_ids:
            _LOGGER.warning("Smart Habits: no analyzable entities — skipping scan")
            stale_automations = await self._async_detect_stale_automations()
            return {"patterns": [], "accepted_patterns": [], "stale_automations": stale_automations}

        # DB I/O: uses recorder's dedicated executor (inside RecorderReader)
        states = await self.reader.async_get_states(entity_ids, self.lookback_days)

        # CPU analysis: single executor job runs all three detectors (Phase 6)
        all_patterns = await self.hass.async_add_executor_job(
            self._run_all_detectors, states, self.lookback_days
        )

        # Filter dismissed patterns (MGMT-02)
        dismissed_filtered = [
            p for p in all_patterns
            if not self.dismissed_store.is_dismissed(
                p.entity_id, p.pattern_type, p.peak_hour, p.secondary_entity_id
            )
        ]

        # Separate accepted vs active patterns (Phase 6)
        active_patterns = [
            p for p in dismissed_filtered
            if not self.accepted_store.is_accepted(
                p.entity_id, p.pattern_type, p.peak_hour, p.secondary_entity_id
            )
        ]
        accepted_patterns = [
            p for p in dismissed_filtered
            if self.accepted_store.is_accepted(
                p.entity_id, p.pattern_type, p.peak_hour, p.secondary_entity_id
            )
        ]

        # Detect stale automations from HA state machine (runs on event loop — no executor needed)
        stale_automations = await self._async_detect_stale_automations()

        _LOGGER.info(
            "Smart Habits: detected %d patterns (%d dismissed, %d accepted) from %d entities, "
            "%d stale automations",
            len(active_patterns),
            len(all_patterns) - len(dismissed_filtered),
            len(accepted_patterns),
            len(states),
            len(stale_automations),
        )
        return {"patterns": active_patterns, "accepted_patterns": accepted_patterns, "stale_automations": stale_automations}

    async def _async_detect_stale_automations(self) -> list[StaleAutomation]:
        """Detect automations that have not been triggered recently.

        Reads directly from the HA state machine (hass.states.async_all) — no
        Recorder query needed (RESEARCH pitfall 4). Automations are considered
        stale if last_triggered is None (never triggered) or older than
        STALE_AUTOMATION_DAYS days.
        """
        stale: list[StaleAutomation] = []
        cutoff = dt_util.utcnow() - timedelta(days=STALE_AUTOMATION_DAYS)

        try:
            automation_states = self.hass.states.async_all("automation")
        except TypeError:
            # Fallback for older HA versions that don't accept a domain argument
            automation_states = [
                s for s in self.hass.states.async_all()
                if s.domain == "automation"
            ]

        for state in automation_states:
            try:
                last_triggered = state.attributes.get("last_triggered")
                friendly_name = state.attributes.get("friendly_name", state.entity_id)

                if last_triggered is None:
                    # Never triggered — always stale
                    stale.append(StaleAutomation(
                        entity_id=state.entity_id,
                        friendly_name=friendly_name,
                        last_triggered=None,
                        days_since_triggered=None,
                    ))
                    continue

                # Parse last_triggered timestamp
                last_triggered_str = str(last_triggered)
                last_triggered_dt = datetime.fromisoformat(last_triggered_str)

                # Ensure timezone-aware for comparison
                if last_triggered_dt.tzinfo is None:
                    last_triggered_dt = last_triggered_dt.replace(tzinfo=timezone.utc)

                if last_triggered_dt < cutoff:
                    days_since = (dt_util.utcnow() - last_triggered_dt).days
                    stale.append(StaleAutomation(
                        entity_id=state.entity_id,
                        friendly_name=friendly_name,
                        last_triggered=last_triggered_str,
                        days_since_triggered=days_since,
                    ))

            except (ValueError, TypeError) as err:
                _LOGGER.debug(
                    "Smart Habits: could not parse last_triggered for %s: %s",
                    state.entity_id,
                    err,
                )
                continue

        return stale

    async def async_trigger_scan(self) -> None:
        """Run the analysis scan by delegating to async_refresh.

        Called via entry.async_create_background_task so HA manages cancellation
        automatically when the config entry is unloaded.
        """
        _LOGGER.info("Smart Habits: starting analysis scan")
        await self.async_refresh()
        pattern_count = len(self.data.get("patterns", []))
        _LOGGER.info("Smart Habits: scan complete — %d patterns found", pattern_count)
