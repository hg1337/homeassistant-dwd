"""Support for DWD weather service."""
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Optional

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
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import (
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.helpers import sun
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import (
    ATTR_FORECAST_CLOUD_COVER,
    ATTR_FORECAST_CUSTOM_DWD_WW,
    ATTRIBUTION,
    CONDITION_CLOUDY_THRESHOLD,
    CONDITION_PARTLYCLOUDY_THRESHOLD,
    CONDITIONS_MAP,
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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

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
                hass.config.units.is_metric,
                FORECAST_MODE_DAILY,
                device,
            ),
            DwdWeather(
                hass,
                coordinator,
                f"{config_entry.unique_id}-hourly",
                config_entry,
                hass.config.units.is_metric,
                FORECAST_MODE_HOURLY,
                device,
            ),
        ]
    )


class DwdWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a DWD weather condition."""

    def __init__(
        self, hass, coordinator, unique_id, config, is_metric, forecast_mode, device
    ):
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._hass = hass
        self._unique_id = unique_id
        self._config = config
        self._is_metric = is_metric
        self._forecast_mode = forecast_mode
        self._device = device

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def name(self):
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
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Device info."""
        return self._device

    @property
    def condition(self):
        """Return the current condition."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_PRESENT_WEATHER, None
        )
        if str_value is None or str_value == "---":
            return None
        else:
            condition = CONDITIONS_MAP.get(int(str_value), "")
            if condition == ATTR_CONDITION_SUNNY and not sun.is_up(self._hass):
                condition = ATTR_CONDITION_CLEAR_NIGHT
            return condition

    @property
    def temperature(self):
        """Return the temperature."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_TEMPERATURE, None
        )
        if str_value is None:
            return None
        else:
            return DwdWeather._str_to_float(str_value)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_PRESSURE, None
        )
        if str_value is None:
            return None
        else:
            pressure_hpa = DwdWeather._str_to_float(str_value)
            if self._is_metric or pressure_hpa is None:
                return pressure_hpa
            else:
                return round(
                    convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 1
                )

    @property
    def humidity(self):
        """Return the humidity."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_HUMIDITY, None
        )
        if str_value is None:
            return None
        else:
            return DwdWeather._str_to_float(str_value)

    @property
    def visibility(self):
        """Return the humidity."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_VISIBILITY, None
        )
        if str_value is None:
            return None
        else:
            visibility_km = DwdWeather._str_to_float(str_value)
            if self._is_metric or visibility_km is None:
                return visibility_km
            else:
                return round(
                    convert_distance(visibility_km, LENGTH_KILOMETERS, LENGTH_MILES), 1
                )

    @property
    def wind_speed(self):
        """Return the wind speed."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_MEANWIND_SPEED, None
        )
        if str_value is None:
            return None
        else:
            speed_km_h = DwdWeather._str_to_float(str_value)
            if self._is_metric or speed_km_h is None:
                return speed_km_h
            else:
                return round(
                    convert_distance(speed_km_h, LENGTH_KILOMETERS, LENGTH_MILES), 1
                )

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        str_value = self.coordinator.data[DWD_MEASUREMENT].get(
            DWD_MEASUREMENT_MEANWIND_DIRECTION, None
        )
        if str_value is None:
            return None
        else:
            return DwdWeather._str_to_float(str_value)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""

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
        dwd_forecast_timestamp = dwd_forecast.get(DWD_FORECAST_TIMESTAMP, [])
        dwd_forecast_TTT = dwd_forecast.get("TTT", [])
        dwd_forecast_ww = dwd_forecast.get("ww", [])
        dwd_forecast_Neff = dwd_forecast.get("Neff", [])
        dwd_forecast_RR1c = dwd_forecast.get("RR1c", [])
        dwd_forecast_wwP = dwd_forecast.get("wwP", [])
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
                    hourly_item[ATTR_FORECAST_TEMP] = temperature_celcius

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
                            if self._is_metric:
                                hourly_item[
                                    ATTR_FORECAST_PRECIPITATION
                                ] = precipitation_mm
                            else:
                                hourly_item[ATTR_FORECAST_PRECIPITATION] = round(
                                    convert_distance(
                                        precipitation_mm,
                                        LENGTH_MILLIMETERS,
                                        LENGTH_INCHES,
                                    ),
                                    2,
                                )

                    # wwP is in %
                    if i < len(dwd_forecast_wwP):
                        raw_value = dwd_forecast_wwP[i]
                        if raw_value != "-":
                            hourly_item[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = int(
                                round(float(raw_value), 0)
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
                            if self._is_metric:
                                hourly_item[ATTR_FORECAST_WIND_SPEED] = int(
                                    round(wind_speed_kmh, 0)
                                )
                            else:
                                hourly_item[ATTR_FORECAST_WIND_SPEED] = int(
                                    round(
                                        convert_distance(
                                            wind_speed_kmh,
                                            LENGTH_KILOMETERS,
                                            LENGTH_MILES,
                                        ),
                                        0,
                                    )
                                )

                    hourly_list.append(hourly_item)

        if self._forecast_mode == FORECAST_MODE_DAILY:
            result = []
            if len(daily_list) > 0:
                # Always add current day:
                result.append(daily_list[0].values)
                # Only add other days of they are complete
                for i in range(1, len(daily_list)):
                    if daily_list[i].has_enough_hours:
                        result.append(daily_list[i].values)
            return result
        if self._forecast_mode == FORECAST_MODE_HOURLY:
            return hourly_list

    @staticmethod
    def _str_to_float(value: str) -> Optional[float]:
        if value == "---":
            return None
        else:
            return float(value.replace(",", "."))


class DwdWeatherDay:
    @property
    def day(self) -> date:
        return self._day

    @property
    def has_enough_hours(self) -> bool:
        # We do not insist on 24 hours,
        # 1. because the day might have 23 or 25 hours on DST changes.
        # 2. to be a bit robust in case data is missing for very few hours (although we didn't observe this yet).
        return len(self._hours) > 20

    @property
    def values(self) -> dict:

        result = {}

        result[ATTR_FORECAST_TIME] = datetime.combine(self._day, time(0, 0, 0))

        values = list(
            filter(
                lambda x: x is not None,
                map(lambda x: x.get(ATTR_FORECAST_TEMP, None), self._hours),
            )
        )
        if len(values) > 0:
            result[ATTR_FORECAST_TEMP] = max(values)
            result[ATTR_FORECAST_TEMP_LOW] = min(values)

        # Danger: The following has a slight ruonding error. You can easily see that because if you
        # sum up RR1c ("Total precipitation during the last hour consistent with significant weather"),
        # you get a different number that the sum of RRdc ("Total precipitation during the last 24 hours
        # consistent with significant weather"). Usually this seems not to be too big, e.g. a sum of
        # 1.7 mm instead of 1.6 mm. Unfortunately, we can't use RRdc either, because it's not aligned
        # to days.
        values = list(
            filter(
                lambda x: x is not None,
                map(lambda x: x.get(ATTR_FORECAST_PRECIPITATION, None), self._hours),
            )
        )
        if len(values) > 0:
            precipitation = sum(values)
            result[ATTR_FORECAST_PRECIPITATION] = round(precipitation, 2)

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

    def __init__(self, day: date, dwd_forecast: dict):
        self._day = day
        self._dwd_forecast = dwd_forecast
        self._hours = []
        self._hour_indices = []

    def add_hour(self, hour_item: dict, index: int):
        self._hours.append(hour_item)
        self._hour_indices.append(index)
