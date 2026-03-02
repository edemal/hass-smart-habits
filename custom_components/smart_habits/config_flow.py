"""Config flow for the Smart Habits integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    ANALYSIS_INTERVAL_OPTIONS,
    CONF_ANALYSIS_INTERVAL,
    CONF_EXCLUDED_DOMAINS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_LOOKBACK_DAYS,
    CONF_SEQUENCE_WINDOW,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_ENTITY_DOMAINS,
    DEFAULT_EXCLUDED_DOMAINS,
    DEFAULT_EXCLUDED_INTEGRATIONS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_SEQUENCE_WINDOW,
    DOMAIN,
    LOOKBACK_OPTIONS,
    SEQUENCE_WINDOW_OPTIONS,
)


def _get_available_integrations(hass: Any) -> list[str]:
    """Return sorted list of integration names for entities in DEFAULT_ENTITY_DOMAINS."""
    registry = er.async_get(hass)
    integrations: set[str] = set()
    for entity_id in hass.states.async_entity_ids():
        domain = entity_id.split(".")[0]
        if domain in DEFAULT_ENTITY_DOMAINS:
            entry = registry.async_get(entity_id)
            if entry is not None and entry.platform:
                integrations.add(entry.platform)
    return sorted(integrations)


class SmartHabitsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for Smart Habits."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        if user_input is not None:
            return self.async_create_entry(
                title="Smart Habits",
                data={CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS])},
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOOKBACK_DAYS, default=str(DEFAULT_LOOKBACK_DAYS)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=LOOKBACK_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> SmartHabitsOptionsFlow:
        """Return the options flow handler."""
        return SmartHabitsOptionsFlow()


class SmartHabitsOptionsFlow(OptionsFlow):
    """Handle options for Smart Habits."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options init step."""
        if user_input is not None:
            # MC-02 fix: cast SelectSelector string values to int before storage
            return self.async_create_entry(
                data={
                    CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                    CONF_ANALYSIS_INTERVAL: int(user_input[CONF_ANALYSIS_INTERVAL]),
                    CONF_SEQUENCE_WINDOW: int(user_input[CONF_SEQUENCE_WINDOW]),
                    CONF_EXCLUDED_INTEGRATIONS: user_input.get(CONF_EXCLUDED_INTEGRATIONS, []),
                    CONF_EXCLUDED_DOMAINS: user_input.get(CONF_EXCLUDED_DOMAINS, []),
                }
            )

        current_lookback = str(
            self.config_entry.options.get(
                CONF_LOOKBACK_DAYS,
                self.config_entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
            )
        )
        current_interval = str(
            self.config_entry.options.get(
                CONF_ANALYSIS_INTERVAL,
                self.config_entry.data.get(
                    CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL
                ),
            )
        )
        current_window = str(
            self.config_entry.options.get(
                CONF_SEQUENCE_WINDOW,
                self.config_entry.data.get(CONF_SEQUENCE_WINDOW, DEFAULT_SEQUENCE_WINDOW),
            )
        )
        current_excluded_integrations = self.config_entry.options.get(
            CONF_EXCLUDED_INTEGRATIONS, DEFAULT_EXCLUDED_INTEGRATIONS
        )
        current_excluded_domains = self.config_entry.options.get(
            CONF_EXCLUDED_DOMAINS, DEFAULT_EXCLUDED_DOMAINS
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOOKBACK_DAYS, default=current_lookback
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=LOOKBACK_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ANALYSIS_INTERVAL, default=current_interval
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=ANALYSIS_INTERVAL_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SEQUENCE_WINDOW, default=current_window
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=SEQUENCE_WINDOW_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_EXCLUDED_INTEGRATIONS,
                    default=current_excluded_integrations,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_get_available_integrations(self.hass),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_EXCLUDED_DOMAINS,
                    default=current_excluded_domains,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(DEFAULT_ENTITY_DOMAINS),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
