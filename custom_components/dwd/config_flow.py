"""Config flow to configure DWD component."""

import json
import os
import re
import sys

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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

        else:

            (name, station_id) = await DwdFlowHandler._async_get_nearest_station(
                self.hass.config.latitude, self.hass.config.longitude
            )

            if name is None:
                name = self.hass.config.location_name

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=name): str,
                vol.Required(CONF_STATION_ID, default=station_id): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    async def _async_get_nearest_station(latitude: float, longitude: float):

        result_station_name = None
        result_station_id = None

        result_distance = sys.float_info.max

        with open(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "stations.json"),
            "rt",
            encoding="utf-8",
        ) as file:
            stations = json.load(file)
            for station in stations:
                station_id = station["id"]
                station_name = station["name"]
                station_latitude = station["latitude"]
                station_longitude = station["longitude"]
                distance = loc_util.distance(
                    station_latitude, station_longitude, latitude, longitude
                )
                if distance < result_distance:
                    result_station_id = station_id
                    result_station_name = station_name
                    result_distance = distance

        return (result_station_name, result_station_id)
