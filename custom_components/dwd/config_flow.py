"""Config flow to configure DWD component."""
from __future__ import annotations
from itertools import chain, islice

import json
import os
from typing import Any
from aiohttp import ClientSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, UnitOfLength
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_CURRENT_WEATHER,
    CONF_CURRENT_WEATHER_DEFAULT,
    CONF_CURRENT_WEATHER_FORECAST,
    CONF_CURRENT_WEATHER_HYBRID,
    CONF_CURRENT_WEATHER_MEASUREMENT,
    CONF_FORECAST,
    CONF_FORECAST_DEFAULT,
    CONF_STATION_ID,
    DOMAIN,
    DWD_FORECAST,
    DWD_MEASUREMENT,
    SOURCE_STATIONSLEXIKON,
    URL_FORECAST,
    URL_MEASUREMENT,
)


# Translation workaround for selectors until they are supported by Home Assistant
STRING_CUSTOM = {"en": "Custom...", "de": "Benutzerdefiniert..."}
STRING_NO_MEASUREMENT = {"en": "[no measurement data]", "de": "[keine Messdaten]"}
STRING_NO_FORECAST = {"en": "[no forecast data]", "de": "[keine Vorhersagedaten]"}
STRING_ALL = {
    "en": "Load all (might be slow)...",
    "de": "Alle laden (könnte langsam sein)...",
}
STRING_CURRENT_WEATHER_MEASUREMENT = {
    "en": "Measurement data only (recommended)",
    "de": "Nur Messdaten (empfohlen)",
}
STRING_CURRENT_WEATHER_HYBID = {
    "en": "Measurement data with forecast data for current hour as fallback for attributes where no measurement data is available",
    "de": "Messdaten mit Vorhersagedaten für die aktuelle Stunde für Attribute für die keine Messdaten verfügbar sind",
}
STRING_CURRENT_WEATHER_FORECAST = {
    "en": "Forecast data only (recommended only for stations that do not provide measurement data at all)",
    "de": "Nur Vorhersagedaten (nur für Stationen emfohlen, die über haupt keine Messdaten liefern)",
}


class DwdFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DWD component."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the DWD flow."""
        self._name = None
        self._station_id = None
        self._available_data = None
        self._current_weather = None
        self._forecast = None
        self._show_all = False

    def _get_translation(self, translations: dict[str, str]) -> str:
        return translations.get(self.hass.config.language, translations["en"])

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors = {}

        self._station_id = None

        if user_input is not None:

            self._station_id = user_input[CONF_STATION_ID]

            if self._station_id == "-":

                return await self.async_step_manual()

            elif self._station_id == "+":

                self._show_all = True
                return await self.async_step_user()

            else:

                await self.async_set_unique_id(self._station_id)
                self._abort_if_unique_id_configured()

                if not errors:
                    self._available_data = await _get_available_data(
                        self._station_id, async_get_clientsession(self.hass)
                    )
                    if len(self._available_data) == 0:
                        errors[CONF_STATION_ID] = "no_data"

                if not errors:
                    self._name = await DwdFlowHandler._async_get_station_name(
                        self._station_id
                    )
                    if self._name is None:
                        errors[CONF_STATION_ID] = "no_station_name"

                if not errors:
                    return await self.async_step_name()

        stations = list(await self._async_get_nearest_stations())

        station_options = chain(
            [
                {
                    "label": self._get_translation(STRING_CUSTOM),
                    "value": "-",
                }
            ],
            map(
                lambda x: {
                    # Elevation is always in m in Home Assistant
                    "label": f'{x["name"]} ({"" if x["source"] == SOURCE_STATIONSLEXIKON else "~ "}{x["distance"]:.0f} {self.hass.config.units.length_unit}, {x["altitude_delta"]:+.0f} m) {self._get_translation(STRING_NO_MEASUREMENT) if not x["measurement"] else self._get_translation(STRING_NO_FORECAST) if not x["forecast"] else ""}',
                    "value": x["id"],
                },
                stations,
            ),
        )

        if not self._show_all:
            station_options = chain(
                station_options,
                [
                    {
                        "label": self._get_translation(STRING_ALL),
                        "value": "+",
                    }
                ],
            )

        suggested_station = next(
            (
                x
                for x in stations
                if x["measurement"] and x["forecast"] and abs(x["altitude_delta"]) < 500
            ),
            None,
        )
        if (
            suggested_station is None
            or DistanceConverter.convert(
                suggested_station["distance"],
                self.hass.config.units.length_unit,
                UnitOfLength.KILOMETERS,
            )
            > 20
        ):
            suggested_station = stations[0]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID,
                    description={"suggested_value": suggested_station["id"]},
                ): selector(
                    {
                        "select": {
                            "options": list(station_options),
                            "custom_value": False,
                            "mode": "dropdown",
                        }
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors, last_step=False
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to rename the station after selecting one from the list."""

        if user_input is not None:
            self._name = user_input[CONF_NAME]
            return await self.async_step_options()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self._name): str,
            }
        )

        return self.async_show_form(step_id="name", data_schema=schema, last_step=False)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for manual station selection."""

        errors = {}

        self._name = None
        self._station_id = None

        if user_input is not None:

            self._name = user_input[CONF_NAME]
            self._station_id = user_input[CONF_STATION_ID]

            await self.async_set_unique_id(self._station_id)
            self._abort_if_unique_id_configured()

            if not errors:
                self._available_data = await _get_available_data(
                    self._station_id, async_get_clientsession(self.hass)
                )
                if len(self._available_data) == 0:
                    errors[CONF_STATION_ID] = "no_data"

            if not errors:
                return await self.async_step_options()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, description={"suggested_value": self._name}
                ): str,
                vol.Required(
                    CONF_STATION_ID, description={"suggested_value": self._station_id}
                ): str,
            }
        )

        return self.async_show_form(
            step_id="manual", data_schema=schema, errors=errors, last_step=False
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def async_step_options_no_measurement(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def async_step_options_no_forecast(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def _async_step_options(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Handle the step for manual station selection."""

        self._current_weather = None
        self._forecast = None

        if user_input is not None:
            # CONF_CURRENT_WEATHER is always set from the UI.
            self._current_weather = user_input[CONF_CURRENT_WEATHER]
            # CONF_FORECAST is not configurable in the UI if no forecast is
            # available and has to default to False in this case.
            self._forecast = user_input.get(CONF_FORECAST, False)

            return self.async_create_entry(
                title=self._name,
                data={CONF_STATION_ID: self._station_id},
                options={
                    CONF_CURRENT_WEATHER: self._current_weather,
                    CONF_FORECAST: self._forecast,
                },
            )
        else:
            self._current_weather = CONF_CURRENT_WEATHER_DEFAULT
            self._forecast = CONF_FORECAST_DEFAULT

        schema = _create_schema(
            self._available_data,
            self._current_weather,
            self._forecast,
            self.hass.config.language,
        )

        if (
            DWD_MEASUREMENT not in self._available_data
            and DWD_FORECAST in self._available_data
        ):
            return self.async_show_form(
                step_id="options_no_measurement", data_schema=schema, last_step=True
            )
        elif (
            DWD_MEASUREMENT in self._available_data
            and DWD_FORECAST not in self._available_data
        ):
            return self.async_show_form(
                step_id="options_no_forecast", data_schema=schema, last_step=True
            )
        else:
            return self.async_show_form(
                step_id="options", data_schema=schema, last_step=True
            )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return DwdOptionsFlowHandler(config_entry)

    async def _async_get_nearest_stations(self):

        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "stations.json"),
            "rt",
            encoding="utf-8",
        ) as file:
            stations = json.load(file)

            for station in stations:
                station["distance"] = self.hass.config.distance(
                    station["latitude"], station["longitude"]
                )
                # The elevation is always in m in Home Assistant same as the station altitude!
                station["altitude_delta"] = (
                    station["altitude"] - self.hass.config.elevation
                )

            sorted_startions = sorted(stations, key=lambda x: x["distance"])

            if self._show_all:
                return sorted_startions
            else:
                return islice(sorted_startions, 100)

    @staticmethod
    async def _async_get_station_name(station_id: str):

        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "stations.json"),
            "rt",
            encoding="utf-8",
        ) as file:
            stations = json.load(file)

            for station in stations:
                if station["id"] == station_id:
                    return station["name"]

            return None


class DwdOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for DWD component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._available_data = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def async_step_init_no_measurement(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def async_step_init_no_forecast(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def _async_step_init(self, user_input: dict[str, Any] | None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    # CONF_CURRENT_WEATHER is always set from the UI.
                    CONF_CURRENT_WEATHER: user_input[CONF_CURRENT_WEATHER],
                    # CONF_FORECAST is not configurable in the UI if no forecast is
                    # available and has to default to False in this case.
                    CONF_FORECAST: user_input.get(CONF_FORECAST, False),
                }
            )

        available_data = await _get_available_data(
            self.config_entry.data[CONF_STATION_ID], async_get_clientsession(self.hass)
        )

        schema = _create_schema(
            available_data,
            self.config_entry.options.get(
                CONF_CURRENT_WEATHER, CONF_CURRENT_WEATHER_DEFAULT
            ),
            self.config_entry.options.get(CONF_FORECAST, CONF_FORECAST_DEFAULT),
            self.hass.config.language,
        )

        if DWD_MEASUREMENT not in available_data and DWD_FORECAST in available_data:
            return self.async_show_form(
                step_id="init_no_measurement", data_schema=schema
            )
        elif DWD_MEASUREMENT in available_data and DWD_FORECAST not in available_data:
            return self.async_show_form(step_id="init_no_forecast", data_schema=schema)
        else:
            return self.async_show_form(step_id="init", data_schema=schema)


def _create_schema(
    available_data: list,
    suggested_current_weather: str,
    suggested_forecast: bool,
    language: str,
) -> vol.Schema:
    selector_dict = {
        "select": {
            "options": [],
            "custom_value": False,
            "mode": "list",
        }
    }

    if DWD_MEASUREMENT in available_data:
        selector_dict["select"]["options"].append(
            {
                "label": STRING_CURRENT_WEATHER_MEASUREMENT.get(
                    language, STRING_CURRENT_WEATHER_MEASUREMENT["en"]
                ),
                "value": CONF_CURRENT_WEATHER_MEASUREMENT,
            }
        )

    if DWD_MEASUREMENT in available_data and DWD_FORECAST in available_data:
        selector_dict["select"]["options"].append(
            {
                "label": STRING_CURRENT_WEATHER_HYBID.get(
                    language, STRING_CURRENT_WEATHER_HYBID["en"]
                ),
                "value": CONF_CURRENT_WEATHER_HYBRID,
            },
        )

    if DWD_FORECAST in available_data:
        selector_dict["select"]["options"].append(
            {
                "label": STRING_CURRENT_WEATHER_FORECAST.get(
                    language, STRING_CURRENT_WEATHER_FORECAST["en"]
                ),
                "value": CONF_CURRENT_WEATHER_FORECAST,
            },
        )

    # Overwrite suggested values if some data is not available
    if DWD_MEASUREMENT in available_data and not DWD_FORECAST in available_data:
        suggested_current_weather = CONF_CURRENT_WEATHER_MEASUREMENT
        suggested_forecast = None
    elif DWD_MEASUREMENT not in available_data and DWD_FORECAST in available_data:
        suggested_current_weather = CONF_CURRENT_WEATHER_FORECAST
    elif DWD_MEASUREMENT not in available_data and DWD_FORECAST not in available_data:
        suggested_current_weather = None
        suggested_forecast = None

    schema_dict = {}
    if DWD_MEASUREMENT in available_data or DWD_FORECAST in available_data:
        schema_dict[
            vol.Required(
                CONF_CURRENT_WEATHER,
                description={"suggested_value": suggested_current_weather},
            )
        ] = selector(selector_dict)
    if DWD_FORECAST in available_data:
        schema_dict[
            vol.Required(
                CONF_FORECAST,
                description={"suggested_value": suggested_forecast},
            )
        ] = bool

    return vol.Schema(schema_dict)


async def _get_available_data(
    station_id: str, clientsession: ClientSession
) -> list[str]:

    result = []

    response = await clientsession.head(URL_MEASUREMENT.format(station_id=station_id))
    if response.status >= 200 and response.status <= 299:
        result.append(DWD_MEASUREMENT)

    response = await clientsession.head(URL_FORECAST.format(station_id=station_id))
    if response.status >= 200 and response.status <= 299:
        result.append(DWD_FORECAST)

    return result
