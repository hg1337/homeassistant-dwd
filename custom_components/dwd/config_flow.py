"""Config flow to configure DWD component."""

import json
import os
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector
from homeassistant.util import location as loc_util

from .const import CONF_STATION_ID, DOMAIN, URL_FORECAST, URL_MEASUREMENT


class DwdFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DWD component."""

    VERSION = 1

    # Not completely sure, but the pure numeric stations seem to be the "good" ones that provide measured data.
    _station_id_re = re.compile(r"^[0-9]{5}$")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        errors = {}

        station_id = None

        if user_input is not None:

            station_id = user_input[CONF_STATION_ID]

            if station_id == "-":

                return await self.async_step_manual()

            else:

                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()

                clientsession = async_get_clientsession(self.hass)

                if not errors:
                    result = await clientsession.head(
                        URL_MEASUREMENT.format(station_id=station_id)
                    )
                    if result.status < 200 or result.status > 299:
                        errors[CONF_STATION_ID] = "no_measurement"

                if not errors:
                    result = await clientsession.head(
                        URL_FORECAST.format(station_id=station_id)
                    )
                    if result.status < 200 or result.status > 299:
                        errors[CONF_STATION_ID] = "no_forecast"

                if not errors:
                    name = await DwdFlowHandler._async_get_station_name(station_id)
                    if name is None:
                        errors[CONF_STATION_ID] = "no_station_name"

                if not errors:
                    return self.async_create_entry(
                        title=name, data={CONF_STATION_ID: station_id}
                    )

        stations = await DwdFlowHandler._async_get_nearest_stations(
            self.hass.config.latitude, self.hass.config.longitude
        )

        station_options = [{"label": "Custom...", "value": "-",}] + list(
            map(
                lambda x: {
                    "label": f'{x["name"]} ({x["distance"]/1000:.0f} km)',
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

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_manual(self, user_input=None):
        """Handle the step for manual station selection."""

        errors = {}

        name = None
        station_id = None

        if user_input is not None:

            name = user_input[CONF_NAME]
            station_id = user_input[CONF_STATION_ID]

            await self.async_set_unique_id(station_id)
            self._abort_if_unique_id_configured()

            clientsession = async_get_clientsession(self.hass)

            if not errors:
                result = await clientsession.head(
                    URL_MEASUREMENT.format(station_id=station_id)
                )
                if result.status < 200 or result.status > 299:
                    errors[CONF_STATION_ID] = "no_measurement"

            if not errors:
                result = await clientsession.head(
                    URL_FORECAST.format(station_id=station_id)
                )
                if result.status < 200 or result.status > 299:
                    errors[CONF_STATION_ID] = "no_forecast"

            if not errors:
                return self.async_create_entry(
                    title=name, data={CONF_STATION_ID: station_id}
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, description={"suggested_value": name}): str,
                vol.Required(
                    CONF_STATION_ID, description={"suggested_value": station_id}
                ): str,
            }
        )

        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    @staticmethod
    async def _async_get_nearest_stations(latitude: float, longitude: float):

        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "stations.json"),
            "rt",
            encoding="utf-8",
        ) as file:
            stations = json.load(file)

            for station in stations:
                station["distance"] = loc_util.distance(
                    station["latitude"], station["longitude"], latitude, longitude
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
