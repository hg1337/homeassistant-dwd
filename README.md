[![Release](https://img.shields.io/github/v/release/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/releases) [![Hassfest Workflow Status](https://img.shields.io/github/actions/workflow/status/hg1337/homeassistant-dwd/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/actions/workflows/hassfest.yml) [![License](https://img.shields.io/github/license/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/blob/main/LICENSE) [![Donation](https://img.shields.io/badge/Donation-Buy%20me%20a%20coffee-ffd557?style=for-the-badge)](https://www.buymeacoffee.com/hg1337)  
[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration) [![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)

# Deutscher Wetterdienst (DWD) Integration for Home Assistant

![Screenshot Weather Forecast](./images/screenshot_weather-forecast.png)

- [Introduction](#introduction)
- [Main Features](#main-features)
- [Quick Setup](#quick-setup)
- [Questions & Answers](#questions--answers)
- [References](#references)

## Introduction
This custom component for [Home Assistant](https://www.home-assistant.io/) integrates weather data (measurements and forecasts) from the [Deutscher Wetterdienst Open Data](https://www.dwd.de/DE/leistungen/opendata/opendata.html) server into Home Assistant via weather entities.

### Legal Information

**Deutscher Wetterdienst (DWD) is not affiliated in any way with this project.**

The conditions from Deutscher Wetterdienst (DWD) for using their data and accessing their servers apply.
- https://www.dwd.de/EN/service/copyright/copyright_artikel.html
- https://opendata.dwd.de/README.txt

[stations.md](stations.md) and [custom_components/dwd/stations.json](custom_components/dwd/stations.json) are generated from data from Deutscher Wetterdienst (DWD) with the Python script at [tools/generate_stations/generate_stations.py](tools/generate_stations/generate_stations.py).

## Main Features

- Current measurement data from the weather stations from https://opendata.dwd.de/weather/weather_reports/poi/ as state attributes of a weather entity.
  - condition
  - temperature
  - dew_point
  - cloud_coverage
  - humidity
  - pressure
  - visibility
  - wind_gust_speed
  - wind_speed
  - wind_bearing
- Hourly forecast data from the weather stations from https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/ in the forecast list of a weather entity.
  - datetime
  - condition
  - temperature
  - dew_point
  - cloud_coverage
  - precipitation
  - precipitation_probability
  - pressure
  - wind_gust_speed
  - wind_speed
  - wind_bearing
- Daily forecast data calculated by the component from the hourly forecast data. This is the most tricky part. I have compared the result of this with what the official Warnwetter app displays and the results seems to be very close.
  - datetime
  - condition
  - temperature (the maximum temperature for the day)
  - templow (the minimum temperature for the day)
  - cloud_coverage (arithmetic average over the day)
  - precipitation (sum over the day)
  - pressure (arithmetic average over the day)
  - wind_gust_speed (maximum over the day)
  - wind_speed (arithmetic average over the day)
- Uses the [HTTP ETag](https://en.wikipedia.org/wiki/HTTP_ETag) mechanism to only download new data if the data has changed. This allows more frequent polling (currently about every 10 minutes) while still keeping the load low.
- Configuration via UI

![Screenshot Entity](./images/screenshot_entity.png)

## Quick Setup

This quick setup guide is based on [My Home Assistant](https://my.home-assistant.io) links and the [Home Assistant Community Store (HACS)](https://hacs.xyz). For more details and other setup methods, see [setup.md](setup.md).

As this integration is currently not part of Home Assistant Core, you have to download it first into your Home Assistant installation. To download it via HACS, click the following button to open the download page for this integration in HACS.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration)

After a restart of Home Assistant, this integration is configurable by via "Add Integration" at "Devices & Services" like any core integration. Select "Deutscher Wetterdienst" and follow the instructions.

![Screenshot Search Integration](./images/screenshot_search-integration.png)

To get there in one click, use this button:

[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)

This adds one device and three entities for the selected station. By default, only the entity that provides all forecasts in one entity is enabled. If you still need the deprecated weather entities with daily and houry forecasts separately or via the old mechanism, you can still enable them for now, but you should really switch to the new entity now. To add more stations, just repeat the "Add Integration" step.

## Questions & Answers

If you have questions, they might already be answered at [questions_and_answers.md](./questions_and_answers.md).

## References
Unfortunately, most of the following documentation is only available in German.
### General
- [Deutscher Wetterdienst Open Data.](https://www.dwd.de/DE/leistungen/opendata/opendata.html)
- [List of documents related to Deutscher Wetterdienst Open Data](https://www.dwd.de/DE/leistungen/opendata/hilfe.html?nn=16102&lsbId=625220), e.g. documents that describe the various file formats. The most relevant ones used during development of this component are listed below.
### Measurements
- [Description of the codes in the present_weather column of the weather reports.](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/csv/poi_present_weather_zuordnung_pdf.pdf)
### Forecasts
- [Explanation of the elements used in the MOSMIX forecast KML files.](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)
- [Explanation of the weather codes (ww, ww3, WPc11, WPc31, WPc61, WPcd1, WPch1 and W1W2) used in the MOSMIX forecast KML files.](https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_element_weather_xls.xlsx)
- [Binary Codes (BUFR).](https://www.dwd.de/DE/leistungen/pbfb_verlag_vub/pdf_einzelbaende/vub_2_binaer_barrierefrei.pdf) Actually, this should not be so much relevant, because everything should be covered by the previous documents, but there is some interesting overlap with the table "Aktuelles Wetter" on page 229 of this document.
- [General explanation of forecast symbols.](https://www.dwd.de/DE/fachnutzer/landwirtschaft/dokumentationen/agrowetter/VHS_Elemente_Wettersymbole.pdf) This doesn't explain the data format, but it is still quite interesting, because it shows the relations of the symbols to other data like cloud coverage and precipitation.
### Station Lists
For more information about stations see also [stations.md](stations.md).
- [General station list](https://rcc.dwd.de/DE/leistungen/klimadatendeutschland/stationsliste.html)
- [Station list with stations providing MOSMIX forecasts.](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg)
