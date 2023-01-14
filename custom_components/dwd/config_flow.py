"""Config flow to configure DWD component."""

import json
import os
from aiohttp import ClientSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector
from homeassistant.util import location as loc_util

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
    URL_FORECAST,
    URL_MEASUREMENT,
)


# Translation workaround for selectors until they are supported by Home Assistant
STRING_CUSTOM = {"en": "Custom...", "de": "Benutzerdefiniert..."}
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        errors = {}

        self._station_id = None

        if user_input is not None:

            self._station_id = user_input[CONF_STATION_ID]

            if self._station_id == "-":

                return await self.async_step_manual()

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
                    return await self.async_step_options()

        stations = await self._async_get_nearest_stations()

        station_options = [
            {
                "label": STRING_CUSTOM.get(
                    self.hass.config.language, STRING_CUSTOM["en"]
                ),
                "value": "-",
            }
        ] + list(
            map(
                lambda x: {
                    "label": f'{x["name"]} ({x["distance"]:.0f} {self.hass.config.units.length_unit})',
                    "value": x["id"],
                },
                stations,
            )
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID,
                    description={"suggested_value": station_options[1]["value"]},
                ): selector(
                    {
                        "select": {
                            "options": station_options,
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

    async def async_step_manual(self, user_input=None):
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

    async def async_step_options(self, user_input=None):
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def async_step_options_no_measurement(self, user_input=None):
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def async_step_options_no_forecast(self, user_input=None):
        """Handle the step for manual station selection."""
        return await self._async_step_options(user_input)

    async def _async_step_options(self, user_input):
        """Handle the step for manual station selection."""

        self._current_weather = None
        self._forecast = None

        if user_input is not None:
            self._current_weather = user_input[CONF_CURRENT_WEATHER]
            self._forecast = user_input[CONF_FORECAST]

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

            return sorted(stations, key=lambda x: x["distance"])

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
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._available_data = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def async_step_init_no_measurement(self, user_input=None) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def async_step_init_no_forecast(self, user_input=None) -> FlowResult:
        """Manage the options."""
        return await self._async_step_init(user_input)

    async def _async_step_init(self, user_input) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_CURRENT_WEATHER: user_input[CONF_CURRENT_WEATHER],
                    CONF_FORECAST: user_input[CONF_FORECAST],
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
):
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


async def _get_available_data(station_id: str, clientsession: ClientSession):

    result = []

    response = await clientsession.head(URL_MEASUREMENT.format(station_id=station_id))
    if response.status >= 200 and response.status <= 299:
        result.append(DWD_MEASUREMENT)

    response = await clientsession.head(URL_FORECAST.format(station_id=station_id))
    if response.status >= 200 and response.status <= 299:
        result.append(DWD_FORECAST)

    return result
