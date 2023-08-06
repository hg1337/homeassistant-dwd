"""The DWD component."""
from __future__ import annotations

import codecs
from datetime import datetime, timezone
from io import BytesIO
import logging
import zipfile
from aiohttp import ClientSession

from defusedxml import ElementTree
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    DWD_FORECAST_TIMESTAMP,
    DWD_MEASUREMENT,
    DWD_MEASUREMENT_DATETIME,
    MEASUREMENTS_MAX_AGE,
    UPDATE_INTERVAL,
    URL_FORECAST,
    URL_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = config_validation.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured DWD."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up DWD as config entry."""

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    coordinator = DwdDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, Platform.WEATHER)
    )

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, Platform.WEATHER)
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True


class DwdDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching DWD data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global DWD data updater."""

        self._config_entry: ConfigEntry = config_entry
        self._clientsession: ClientSession = async_get_clientsession(hass)

        self._last_measurement: dict | None = None
        self._last_forecast: dict | None = None
        self._last_measurement_etag: str | None = None
        self._last_forecast_etag: str | None = None

        _LOGGER.debug(
            "Checking for new data for %s (%s) every %s",
            self._config_entry.title,
            self._config_entry.data.get(CONF_STATION_ID, None),
            UPDATE_INTERVAL,
        )

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict:
        """Fetch data from DWD."""

        try:
            conf_current_weather = self._config_entry.options.get(
                CONF_CURRENT_WEATHER, CONF_CURRENT_WEATHER_DEFAULT
            )
            conf_forecast = self._config_entry.options.get(
                CONF_FORECAST, CONF_FORECAST_DEFAULT
            )

            if (
                conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT
                or conf_current_weather == CONF_CURRENT_WEATHER_HYBRID
            ):
                # Fetch measurement, if new data is available (using ETag header).

                url = URL_MEASUREMENT.format(
                    station_id=self._config_entry.data[CONF_STATION_ID]
                )
                headers = {}
                if self._last_measurement_etag is not None:
                    headers["If-None-Match"] = self._last_measurement_etag
                response = await self._clientsession.get(url, headers=headers)

                if response.status == 304:
                    _LOGGER.debug("No new data from %s", url)

                elif 200 <= response.status <= 299:
                    measurement = {}
                    measurement_etag = response.headers.get("ETag", None)

                    data = response.content

                    # Read column names:
                    line = codecs.decode(await data.readline()).strip()
                    column_names = line.split(";")
                    # Skip 2 additional descriptive header rows
                    await data.readline()
                    await data.readline()
                    # Read actual measurement values into target dictionary
                    # Some stations set some values only every few hours, so we go a few rows
                    # down (up to MEASUREMENTS_MAX_AGE) to collect all values.
                    raw_line = await data.readline()
                    age = 0
                    while age < MEASUREMENTS_MAX_AGE and raw_line:
                        line = codecs.decode(raw_line).strip()
                        fields = line.split(";")
                        measurement.setdefault(
                            DWD_MEASUREMENT_DATETIME,
                            datetime.strptime(
                                f"{fields[0]} {fields[1]}", r"%d.%m.%y %H:%M"
                            ).replace(tzinfo=timezone.utc),
                        )
                        for i in range(2, min(len(column_names), len(fields))):
                            if fields[i] and fields[i] != "---":
                                measurement.setdefault(column_names[i], fields[i])
                        raw_line = await data.readline()
                        age += 1

                    self._last_measurement = measurement
                    self._last_measurement_etag = measurement_etag
                    _LOGGER.debug(
                        "Measurement successfully fetched from %s. ETag: %s",
                        url,
                        self._last_measurement_etag,
                    )

                else:
                    raise UpdateFailed(
                        f"Unexpected status code {response.status} from {url}."
                    )

            else:
                _LOGGER.debug(
                    "Not fetching measurement data because current_weather is %s",
                    conf_current_weather,
                )

            if (
                conf_current_weather == CONF_CURRENT_WEATHER_HYBRID
                or conf_current_weather == CONF_CURRENT_WEATHER_FORECAST
                or conf_forecast
            ):
                # Fetch forecast, if new data is available (using ETag header).

                url = URL_FORECAST.format(
                    station_id=self._config_entry.data[CONF_STATION_ID]
                )
                headers = {}
                if self._last_forecast_etag is not None:
                    headers["If-None-Match"] = self._last_forecast_etag
                response = await self._clientsession.get(url, headers=headers)

                if response.status == 304:
                    _LOGGER.debug("No new data from %s", url)

                elif 200 <= response.status <= 299:
                    forecast = {}
                    forecast_etag = response.headers.get("ETag", None)

                    data = await response.read()

                    with zipfile.ZipFile(BytesIO(data)) as dwd_zip_file:
                        for kml_file_name in dwd_zip_file.namelist():
                            if kml_file_name.endswith(".kml"):
                                with dwd_zip_file.open(kml_file_name) as kml_file:
                                    # For a description of all elements see https://opendata.dwd.de/weather/lib/MetElementDefinition.xml
                                    elementTree = ElementTree.parse(kml_file)
                                    timestamps = list(
                                        map(
                                            lambda x: datetime.strptime(
                                                x.text, "%Y-%m-%dT%H:%M:%S.%f%z"
                                            ),
                                            elementTree.findall(
                                                "./kml:Document/kml:ExtendedData/dwd:ProductDefinition/dwd:ForecastTimeSteps/dwd:TimeStep",
                                                {
                                                    "kml": "http://www.opengis.net/kml/2.2",
                                                    "dwd": "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd",
                                                },
                                            ),
                                        )
                                    )
                                    forecast[DWD_FORECAST_TIMESTAMP] = timestamps
                                    forecastElements = elementTree.findall(
                                        "./kml:Document/kml:Placemark/kml:ExtendedData/dwd:Forecast",
                                        {
                                            "kml": "http://www.opengis.net/kml/2.2",
                                            "dwd": "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd",
                                        },
                                    )
                                    for forecastElement in forecastElements:
                                        name = forecastElement.attrib[
                                            r"{https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd}elementName"
                                        ]
                                        values = forecastElement.find(
                                            "dwd:value",
                                            {
                                                "kml": "http://www.opengis.net/kml/2.2",
                                                "dwd": "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd",
                                            },
                                        ).text.split()
                                        forecast[name] = values

                                # There should only be on KML file in the KMZ archive so we don't handle multiple.
                                # Don't even know what this would mean. ;) Anyway, would complicate things a bit.
                                break

                    self._last_forecast = forecast
                    self._last_forecast_etag = forecast_etag
                    _LOGGER.debug(
                        "Forecast successfully fetched from %s. ETag: %s",
                        url,
                        self._last_forecast_etag,
                    )

                else:
                    raise UpdateFailed(
                        f"Unexpected status code {response.status} from {url}."
                    )
            else:
                _LOGGER.debug(
                    "Not fetching forecast data because current_weather is %s and forecast is %s",
                    conf_current_weather,
                    conf_forecast,
                )

            return {
                DWD_MEASUREMENT: self._last_measurement,
                DWD_FORECAST: self._last_forecast,
            }

        except Exception as err:
            raise UpdateFailed(err) from err
