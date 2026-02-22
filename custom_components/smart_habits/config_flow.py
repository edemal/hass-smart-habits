"""Config flow for the Smart Habits integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LOOKBACK_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    DOMAIN,
    LOOKBACK_OPTIONS,
)


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
        return SmartHabitsOptionsFlow(config_entry)


class SmartHabitsOptionsFlow(OptionsFlow):
    """Handle options for Smart Habits."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options init step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_lookback = str(
            self.config_entry.options.get(
                CONF_LOOKBACK_DAYS,
                self.config_entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
            )
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
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
