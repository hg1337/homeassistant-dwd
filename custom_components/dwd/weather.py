"""Support for DWD weather service."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Any, Optional

from homeassistant.helpers.entity import DeviceInfo
from . import DwdDataUpdateCoordinator

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt

from .const import (
    ATTR_FORECAST_CLOUD_COVER,
    ATTR_FORECAST_CUSTOM_DWD_WW,
    ATTRIBUTION,
    CONDITION_CLOUDY_THRESHOLD,
    CONDITION_PARTLYCLOUDY_THRESHOLD,
    CONDITIONS_MAP,
    CONF_CURRENT_WEATHER,
    CONF_CURRENT_WEATHER_DEFAULT,
    CONF_CURRENT_WEATHER_FORECAST,
    CONF_CURRENT_WEATHER_HYBRID,
    CONF_CURRENT_WEATHER_MEASUREMENT,
    CONF_FORECAST,
    CONF_FORECAST_DEFAULT,
    DOMAIN,
    DWD_FORECAST,
    DWD_FORECAST_TIMESTAMP,
    DWD_MEASUREMENT,
    DWD_MEASUREMENT_HUMIDITY,
    DWD_MEASUREMENT_MEANWIND_DIRECTION,
    DWD_MEASUREMENT_MEANWIND_SPEED,
    DWD_MEASUREMENT_PRESENT_WEATHER,
    DWD_MEASUREMENT_PRESSURE,
    DWD_MEASUREMENT_TEMPERATURE,
    DWD_MEASUREMENT_VISIBILITY,
    FORECAST_MODE_DAILY,
    FORECAST_MODE_HOURLY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Add a weather entity from a config_entry."""
    coordinator: DwdDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    device = {
        "identifiers": {(DOMAIN, config_entry.unique_id)},
        "name": config_entry.title,
        "manufacturer": "Deutscher Wetterdienst",
        "model": f"Station {config_entry.unique_id}",
        "entry_type": DeviceEntryType.SERVICE,
    }

    async_add_entities(
        [
            DwdWeather(
                hass,
                coordinator,
                f"{config_entry.unique_id}-daily",
                config_entry,
                FORECAST_MODE_DAILY,
                device,
            ),
            DwdWeather(
                hass,
                coordinator,
                f"{config_entry.unique_id}-hourly",
                config_entry,
                FORECAST_MODE_HOURLY,
                device,
            ),
        ]
    )


class DwdWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a DWD weather condition."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DwdDataUpdateCoordinator,
        unique_id: str,
        config: ConfigEntry,
        forecast_mode: int,
        device: DeviceInfo,
    ) -> None:
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._hass: HomeAssistant = hass
        self._unique_id: str = unique_id
        self._config: ConfigEntry = config
        self._forecast_mode: int = forecast_mode
        self._device: DeviceInfo = device
        self._conf_current_weather: str = self._config.options.get(
            CONF_CURRENT_WEATHER, CONF_CURRENT_WEATHER_DEFAULT
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""

        name = self._config.title
        name_appendix = ""

        if self._forecast_mode == FORECAST_MODE_HOURLY:
            name_appendix = " Hourly"
        if self._forecast_mode == FORECAST_MODE_DAILY:
            name_appendix = " Daily"

        if name is None:
            name = self.hass.config.location_name

        if name is None:
            name = "DWD"

        return f"{name}{name_appendix}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return self._device

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if (
            self._conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT
            or self._conf_current_weather == CONF_CURRENT_WEATHER_HYBRID
        ):
            str_value = self.coordinator.data[DWD_MEASUREMENT].get(
                DWD_MEASUREMENT_PRESENT_WEATHER, None
            )
            if str_value is None or str_value == "---":
                if self._conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT:
                    return None
                else:
                    forecast = self._get_forecast(FORECAST_MODE_HOURLY, 1)
                    if forecast is None or len(forecast) < 1:
                        return None
                    else:
                        return forecast[0].get(ATTR_FORECAST_CONDITION)
            else:
                condition = CONDITIONS_MAP.get(int(str_value), "")
                if condition == ATTR_CONDITION_SUNNY and not sun.is_up(self._hass):
                    condition = ATTR_CONDITION_CLEAR_NIGHT
                return condition
        elif self._conf_current_weather == CONF_CURRENT_WEATHER_FORECAST:
            forecast = self._get_forecast(FORECAST_MODE_HOURLY, 1)
            if forecast is None or len(forecast) < 1:
                return None
            else:
                return forecast[0].get(ATTR_FORECAST_CONDITION)
        else:
            return None

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self._get_float_measurement_with_fallback(
            DWD_MEASUREMENT_TEMPERATURE, ATTR_FORECAST_NATIVE_TEMP
        )

    @property
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self._get_float_measurement_with_fallback(
            DWD_MEASUREMENT_PRESSURE, ATTR_FORECAST_NATIVE_PRESSURE
        )

    @property
    def native_pressure_unit(self) -> str:
        return UnitOfPressure.HPA

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._get_float_measurement_without_fallback(DWD_MEASUREMENT_HUMIDITY)

    @property
    def native_visibility(self) -> float | None:
        """Return the humidity."""
        return self._get_float_measurement_without_fallback(DWD_MEASUREMENT_VISIBILITY)

    @property
    def native_visibility_unit(self) -> str:
        return UnitOfLength.KILOMETERS

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._get_float_measurement_with_fallback(
            DWD_MEASUREMENT_MEANWIND_SPEED, ATTR_FORECAST_NATIVE_WIND_SPEED
        )

    @property
    def native_wind_speed_unit(self) -> str:
        return UnitOfSpeed.KILOMETERS_PER_HOUR

    @property
    def native_precipitation_unit(self) -> str:
        return UnitOfLength.MILLIMETERS

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind direction."""
        return self._get_float_measurement_with_fallback(
            DWD_MEASUREMENT_MEANWIND_DIRECTION, ATTR_FORECAST_WIND_BEARING
        )

    def _get_float_measurement_with_fallback(
        self, dwd_measurement: str, attr_forecast: str
    ) -> float | None:
        if (
            self._conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT
            or self._conf_current_weather == CONF_CURRENT_WEATHER_HYBRID
        ):
            str_value = self.coordinator.data[DWD_MEASUREMENT].get(
                dwd_measurement, None
            )
            if str_value is None or str_value == "---":
                if self._conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT:
                    return None
                else:
                    forecast = self._get_forecast(FORECAST_MODE_HOURLY, 1)
                    if forecast is None or len(forecast) < 1:
                        return None
                    else:
                        return forecast[0].get(attr_forecast)
            else:
                return DwdWeather._str_to_float(str_value)
        elif self._conf_current_weather == CONF_CURRENT_WEATHER_FORECAST:
            forecast = self._get_forecast(FORECAST_MODE_HOURLY, 1)
            if forecast is None or len(forecast) < 1:
                return None
            else:
                return forecast[0].get(attr_forecast)
        else:
            return None

    def _get_float_measurement_without_fallback(
        self, dwd_measurement: str
    ) -> float | None:
        if (
            self._conf_current_weather == CONF_CURRENT_WEATHER_MEASUREMENT
            or self._conf_current_weather == CONF_CURRENT_WEATHER_HYBRID
        ):
            str_value = self.coordinator.data[DWD_MEASUREMENT].get(
                dwd_measurement, None
            )
            if str_value is None or str_value == "---":
                return None
            else:
                return DwdWeather._str_to_float(str_value)
        else:
            return None

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""

        if not self._config.options.get(CONF_FORECAST, CONF_FORECAST_DEFAULT):
            return None

        return self._get_forecast(self._forecast_mode)

    def _get_forecast(self, forecast_mode: int, max_hours: int = 0):

        # We build both lists in parallel and just return the needed one. Although it's a small
        # overhead, it still makes thinks easier, because there is still much in common, because to
        # calculate the days most of the hourly stuff has to be done again.
        hourly_list = []
        daily_list = []

        # For a description of all values see https://opendata.dwd.de/weather/lib/MetElementDefinition.xml
        # Unfortunately, "ww" is not documented there, but the assumption is that it's the same as for
        # "ww3", but hourly. However, "ww" is at least mentioned at
        # https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_element_weather_xls.xlsx

        dwd_forecast = self.coordinator.data[DWD_FORECAST]

        if dwd_forecast is None:
            return None

        dwd_forecast_timestamp = dwd_forecast.get(DWD_FORECAST_TIMESTAMP, [])
        dwd_forecast_TTT = dwd_forecast.get("TTT", [])
        dwd_forecast_ww = dwd_forecast.get("ww", [])
        dwd_forecast_Neff = dwd_forecast.get("Neff", [])
        dwd_forecast_RR1c = dwd_forecast.get("RR1c", [])
        dwd_forecast_wwP = dwd_forecast.get("wwP", [])
        dwd_forecast_PPPP = dwd_forecast.get("PPPP", [])
        dwd_forecast_DD = dwd_forecast.get("DD", [])
        dwd_forecast_FF = dwd_forecast.get("FF", [])

        current_day: DwdWeatherDay = None

        # Timestamp and temperature are mandatory attributes of the forcast entity,
        # see https://developers.home-assistant.io/docs/core/entity/weather/
        for i in range(min(len(dwd_forecast_timestamp), len(dwd_forecast_TTT))):
            # We have to subsctract one hour, because all forecast values are for the last hour
            # and we are interested in the timestamp at the beginning of the hour, not at the end.
            timestamp = dwd_forecast_timestamp[i] - timedelta(hours=1)

            # The forcast contains data from a few hour back. However, the earlist we want to return
            # is from the current hour (i.e. at most one hour back), because that's what other
            # Home Assistant components like UI elements expect. They use just everything we give them.
            if timestamp > datetime.now(timezone.utc) - timedelta(hours=1):
                hourly_item = {}

                hourly_item[ATTR_FORECAST_TIME] = timestamp.isoformat()

                timestamp_local = dt.as_local(timestamp)
                day = timestamp_local.date()
                if current_day is None or current_day.day != day:
                    current_day = DwdWeatherDay(day, dwd_forecast)
                    daily_list.append(current_day)
                current_day.add_hour(hourly_item, i)

                # TTT is in K
                raw_temperature_value = dwd_forecast_TTT[i]
                if raw_temperature_value != "-":
                    temperature_celcius = float(raw_temperature_value) - 273.15
                    hourly_item[ATTR_FORECAST_NATIVE_TEMP] = temperature_celcius

                    # If there is no temperature, we skip this entry, because it's a mandatory attribute!

                    # There are actually two sources for the mapping of the "ww" field. The primary description seems to be
                    # https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_element_weather_xls.xlsx
                    # However, at first I found
                    # https://www.dwd.de/DE/leistungen/pbfb_verlag_vub/pdf_einzelbaende/vub_2_binaer_barrierefrei.pdf
                    # ("Aktuelles Wetter" on page 229) and started the implementation based on that. The first link basically
                    # seems to be a subset of the second link. I still have some doubts regarding the values 0-3. There seems
                    # to be a slight difference between the two documentations, and the value does no behave exactly as descibed.
                    # For exmaple, the documentation says that 3 is for effective cloud coverage of at least 7/8 and 2 for
                    # effective cloud coverage 4.6/8 to 6/8, but I could observe 3 even for 78% which is much below 6/8.
                    # Still using it for now, the behavior at least seems to be the same as in the WarnWetter app so far.
                    if i < len(dwd_forecast_ww):
                        raw_weather_value = dwd_forecast_ww[i]
                        if raw_weather_value != "-":
                            weather_value = int(round(float(raw_weather_value), 0))
                            hourly_item[ATTR_FORECAST_CUSTOM_DWD_WW] = weather_value
                            if weather_value == 0:
                                if sun.is_up(self._hass, timestamp):
                                    hourly_item[
                                        ATTR_FORECAST_CONDITION
                                    ] = ATTR_CONDITION_SUNNY
                                else:
                                    hourly_item[
                                        ATTR_FORECAST_CONDITION
                                    ] = ATTR_CONDITION_CLEAR_NIGHT
                            elif 1 <= weather_value <= 2:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_PARTLYCLOUDY
                            elif weather_value == 3:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_CLOUDY
                            elif 4 <= weather_value <= 12:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif weather_value == 13:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING
                            elif 14 <= weather_value <= 16:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 17:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING
                            elif weather_value == 18:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY
                            elif weather_value == 19:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY_VARIANT
                            elif 20 <= weather_value <= 21:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 22:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif weather_value == 23:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY_RAINY
                            elif 24 <= weather_value <= 25:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 26:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif weather_value == 27:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_HAIL
                            elif weather_value == 28:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif weather_value == 29:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING_RAINY
                            elif 30 <= weather_value <= 39:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY
                            elif 40 <= weather_value <= 49:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif 50 <= weather_value <= 63:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif 64 <= weather_value <= 65:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 66 <= weather_value <= 67:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif 68 <= weather_value <= 69:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY_RAINY
                            elif 70 <= weather_value <= 79:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif 80 <= weather_value <= 81:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 82:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 83 <= weather_value <= 84:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY_RAINY
                            elif 85 <= weather_value <= 88:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif 89 <= weather_value <= 90:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_HAIL
                            elif 91 <= weather_value <= 99:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING_RAINY
                            elif weather_value == 100:
                                if sun.is_up(self._hass, timestamp):
                                    hourly_item[
                                        ATTR_FORECAST_CONDITION
                                    ] = ATTR_CONDITION_SUNNY
                                else:
                                    hourly_item[
                                        ATTR_FORECAST_CONDITION
                                    ] = ATTR_CONDITION_CLEAR_NIGHT
                            elif 101 <= weather_value <= 102:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_PARTLYCLOUDY
                            elif weather_value == 103:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_CLOUDY
                            elif 104 <= weather_value <= 105:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif weather_value == 110:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif weather_value == 111:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif weather_value == 112:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING
                            elif weather_value == 118:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY
                            elif weather_value == 120:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif 121 <= weather_value <= 123:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 124:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif weather_value == 125:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 126:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING_RAINY
                            elif 127 <= weather_value <= 129:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY
                            elif 130 <= weather_value <= 135:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_FOG
                            elif 140 <= weather_value <= 141:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 142:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif weather_value == 143:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 144:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 145 <= weather_value <= 146:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_HAIL
                            elif 147 <= weather_value <= 148:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif 150 <= weather_value <= 158:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif 160 <= weather_value <= 162:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 163:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 164 <= weather_value <= 165:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif weather_value == 166:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 167 <= weather_value <= 168:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY_RAINY
                            elif 170 <= weather_value <= 178:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif 180 <= weather_value <= 182:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_RAINY
                            elif 183 <= weather_value <= 184:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_POURING
                            elif 185 <= weather_value <= 187:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_SNOWY
                            elif weather_value == 189:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_HAIL
                            elif 190 <= weather_value <= 191:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING
                            elif 192 <= weather_value <= 193:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING_RAINY
                            elif weather_value == 194:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING
                            elif 195 <= weather_value <= 196:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_LIGHTNING_RAINY
                            elif weather_value == 199:
                                hourly_item[
                                    ATTR_FORECAST_CONDITION
                                ] = ATTR_CONDITION_WINDY_VARIANT

                    # Neff is in %
                    if i < len(dwd_forecast_Neff):
                        raw_cloud_cover_value = dwd_forecast_Neff[i]
                        if raw_cloud_cover_value != "-":
                            cloud_cover_value = float(raw_cloud_cover_value)
                            hourly_item[ATTR_FORECAST_CLOUD_COVER] = cloud_cover_value

                    # RR1c is in kg/m2 which is equal to mm
                    if i < len(dwd_forecast_RR1c):
                        raw_value = dwd_forecast_RR1c[i]
                        if raw_value != "-":
                            precipitation_mm = float(raw_value)
                            hourly_item[
                                ATTR_FORECAST_NATIVE_PRECIPITATION
                            ] = precipitation_mm

                    # wwP is in %
                    if i < len(dwd_forecast_wwP):
                        raw_value = dwd_forecast_wwP[i]
                        if raw_value != "-":
                            hourly_item[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = int(
                                round(float(raw_value), 0)
                            )

                    # PPPP is in Pa
                    if i < len(dwd_forecast_PPPP):
                        raw_value = dwd_forecast_PPPP[i]
                        if raw_value != "-":

                            hourly_item[ATTR_FORECAST_NATIVE_PRESSURE] = (
                                float(raw_value) * 0.01
                            )

                    # DD is in °
                    if i < len(dwd_forecast_DD):
                        raw_value = dwd_forecast_DD[i]
                        if raw_value != "-":

                            hourly_item[ATTR_FORECAST_WIND_BEARING] = float(raw_value)

                    # FF is in m/s
                    if i < len(dwd_forecast_FF):
                        raw_value = dwd_forecast_FF[i]
                        if raw_value != "-":
                            wind_speed_kmh = float(raw_value) * 3.6
                            hourly_item[ATTR_FORECAST_NATIVE_WIND_SPEED] = int(
                                round(wind_speed_kmh, 0)
                            )

                    hourly_list.append(hourly_item)

                    if max_hours > 0 and len(hourly_list) >= max_hours:
                        break

        if forecast_mode == FORECAST_MODE_DAILY:
            result = []
            if len(daily_list) > 0:
                # Always add current day:
                result.append(daily_list[0].values)
                # Only add other days of they are complete
                for i in range(1, len(daily_list)):
                    if daily_list[i].has_enough_hours:
                        result.append(daily_list[i].values)
            return result
        if forecast_mode == FORECAST_MODE_HOURLY:
            return hourly_list

    @staticmethod
    def _str_to_float(value: str) -> Optional[float]:
        if value == "---":
            return None
        else:
            return float(value.replace(",", "."))


class DwdWeatherDay:
    """Manages the weather data of a single day."""

    @property
    def day(self) -> date:
        """Returns the date of the day"""
        return self._day

    @property
    def has_enough_hours(self) -> bool:
        """Return True, if the day has data of enough hours, otherwise returns False."""
        # We do not insist on 24 hours,
        # 1. because the day might have 23 or 25 hours on DST changes.
        # 2. to be a bit robust in case data is missing for very few hours (although we didn't observe this yet).
        return len(self._hours) > 20

    @property
    def values(self) -> dict[str, Any]:
        """Returns the value of the day as a dict."""

        result = {}

        result[ATTR_FORECAST_TIME] = datetime.combine(self._day, time(0, 0, 0))

        values = list(
            filter(
                lambda x: x is not None,
                map(lambda x: x.get(ATTR_FORECAST_NATIVE_TEMP, None), self._hours),
            )
        )
        if len(values) > 0:
            result[ATTR_FORECAST_NATIVE_TEMP] = max(values)
            result[ATTR_FORECAST_NATIVE_TEMP_LOW] = min(values)

        # Danger: The following has a slight ruonding error. You can easily see that because if you
        # sum up RR1c ("Total precipitation during the last hour consistent with significant weather"),
        # you get a different number that the sum of RRdc ("Total precipitation during the last 24 hours
        # consistent with significant weather"). Usually this seems not to be too big, e.g. a sum of
        # 1.7 mm instead of 1.6 mm. Unfortunately, we can't use RRdc either, because it's not aligned
        # to days.
        values = list(
            filter(
                lambda x: x is not None,
                map(
                    lambda x: x.get(ATTR_FORECAST_NATIVE_PRECIPITATION, None),
                    self._hours,
                ),
            )
        )
        if len(values) > 0:
            precipitation = sum(values)
            result[ATTR_FORECAST_NATIVE_PRECIPITATION] = round(precipitation, 2)

        values = list(
            filter(
                lambda x: x is not None,
                map(
                    lambda x: x.get(ATTR_FORECAST_NATIVE_PRESSURE, None),
                    self._hours,
                ),
            )
        )
        if len(values) > 0:
            pressure = sum(values) / len(values)
            result[ATTR_FORECAST_NATIVE_PRESSURE] = round(pressure, 1)

        cloud_cover_sum = 0
        cloud_cover_items = 0
        cloud_cover_avg = 0
        for hour in self._hours:
            cloud_cover = hour.get(ATTR_FORECAST_CLOUD_COVER, None)
            if cloud_cover is not None:
                cloud_cover_sum += cloud_cover
                cloud_cover_items += 1

        if cloud_cover_items > 0:
            cloud_cover_avg = cloud_cover_sum / cloud_cover_items
            result[ATTR_FORECAST_CLOUD_COVER] = round(cloud_cover_avg, 0)

            condition_stats = {}
            for hour in self._hours:
                condition = hour.get(ATTR_FORECAST_CONDITION, None)
                if condition is not None:
                    condition_stats[condition] = condition_stats.get(condition, 0) + 1
            if len(condition_stats) == 1:
                for condition in condition_stats.keys():
                    result[ATTR_FORECAST_CONDITION] = condition
            elif condition_stats.get(ATTR_CONDITION_LIGHTNING_RAINY, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_LIGHTNING_RAINY
            elif condition_stats.get(ATTR_CONDITION_LIGHTNING, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_LIGHTNING
            elif condition_stats.get(ATTR_CONDITION_HAIL, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_HAIL
            elif condition_stats.get(ATTR_CONDITION_SNOWY, 0) > 0:
                if (
                    condition_stats.get(ATTR_CONDITION_SNOWY_RAINY, 0) == 0
                    and condition_stats.get(ATTR_CONDITION_RAINY, 0) == 0
                ):
                    result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_SNOWY
                else:
                    result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_SNOWY_RAINY
            elif condition_stats.get(ATTR_CONDITION_SNOWY_RAINY, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_SNOWY_RAINY
            elif condition_stats.get(ATTR_CONDITION_POURING, 0) > 1:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_POURING
            elif (
                condition_stats.get(ATTR_CONDITION_POURING, 0)
                + condition_stats.get(ATTR_CONDITION_RAINY, 0)
                > 0
            ):
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_RAINY
            elif cloud_cover_avg >= CONDITION_CLOUDY_THRESHOLD:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_CLOUDY
            elif cloud_cover_avg >= CONDITION_PARTLYCLOUDY_THRESHOLD:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_PARTLYCLOUDY
            elif condition_stats.get(ATTR_CONDITION_WINDY_VARIANT, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_WINDY_VARIANT
            elif condition_stats.get(ATTR_CONDITION_WINDY, 0) > 0:
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_WINDY
            elif (
                condition_stats.get(ATTR_CONDITION_SUNNY, 0)
                + condition_stats.get(ATTR_CONDITION_CLEAR_NIGHT, 0)
                > 0
            ):
                result[ATTR_FORECAST_CONDITION] = ATTR_CONDITION_SUNNY

        return result

    def __init__(self, day: date, dwd_forecast: dict[str, Any]) -> None:
        self._day: date = day
        self._dwd_forecast: dict[str, Any] = dwd_forecast
        self._hours: list[dict[str, Any]] = []
        self._hour_indices: list[int] = []

    def add_hour(self, hour_item: dict[str, Any], index: int) -> None:
        """Adds hour information to this day."""
        self._hours.append(hour_item)
        self._hour_indices.append(index)
