"""The DWD component."""
from datetime import datetime
from io import BytesIO
from defusedxml import ElementTree
import pytz
import logging
import zipfile
import codecs
from random import randrange
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_STATION_ID,
    DOMAIN,
    DWD_FORECAST,
    DWD_FORECAST_TIMESTAMP,
    DWD_MEASUREMENT,
    DWD_MEASUREMENT_DATETIME,
    MEASUREMENTS_MAX_AGE,
    UPDATE_INTERVAL,
    URL_MEASUREMENT,
    URL_FORECAST,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured DWD."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, config_entry):
    """Set up DWD as config entry."""

    coordinator = DwdDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True


class DwdDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Met data."""

    def __init__(self, hass, config_entry):
        """Initialize global Met data updater."""

        self._config_entry = config_entry
        self._clientsession = async_get_clientsession(hass)

        self._last_measurement = None
        self._last_forecast = None
        self._last_measurement_etag = None
        self._last_forecast_etag = None

        _LOGGER.debug(
            "Checking for new data for %s (%s) every %s",
            self._config_entry.title,
            self._config_entry.data.get(CONF_STATION_ID, None),
            UPDATE_INTERVAL,
        )

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self):
        """Fetch data from DWD."""

        try:

            # Fetch measurement, if new data is available (using ETag header).

            url = URL_MEASUREMENT.format(
                station_id=self._config_entry.data[CONF_STATION_ID]
            )
            headers = {}
            if self._last_measurement_etag is not None:
                headers["If-None-Match"] = self._last_measurement_etag
            response = await self._clientsession.get(url, headers=headers)

            if response.status == 304:
                _LOGGER.debug("No new data from %s.", url)

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
                        pytz.utc.localize(
                            datetime.strptime(
                                f"{fields[0]} {fields[1]}", r"%d.%m.%y %H:%M"
                            )
                        ),
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

            # Fetch forecast, if new data is available (using ETag header).

            url = URL_FORECAST.format(
                station_id=self._config_entry.data[CONF_STATION_ID]
            )
            headers = {}
            if self._last_forecast_etag is not None:
                headers["If-None-Match"] = self._last_forecast_etag
            response = await self._clientsession.get(url, headers=headers)

            if response.status == 304:
                _LOGGER.debug("No new data from %s.", url)

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
                                        lambda x: pytz.utc.localize(
                                            datetime.strptime(
                                                x.text, r"%Y-%m-%dT%H:%M:%S.%fZ"
                                            )
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

            return {
                DWD_MEASUREMENT: self._last_measurement,
                DWD_FORECAST: self._last_forecast,
            }

        except Exception as err:
            raise UpdateFailed(err) from err