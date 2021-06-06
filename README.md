# Deutscher Wetterdienst (DWD) Integration for Home Assistant

## Disclaimer
Deutscher Wetterdienst (DWD) is not affiliated in any way with this project.

## Introduction
This custom component for [Home Assistant](https://www.home-assistant.io/) integrates weather data from the [Deutscher Wetterdienst Open Data](https://www.dwd.de/DE/leistungen/opendata/opendata.html) server into Home Assistant via weather entities.

## Main Features
- Current measurement data from the weather stations from https://opendata.dwd.de/weather/weather_reports/poi/ as state attributes of a weather entity.
  - temperature
  - humidity
  - pressure
  - wind_bearing
  - wind_speed
  - visibility
- Hourly forecast data from the weather stations from https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/ in the forecast list of a weather entity.
  - datetime
  - temperature
  - condition
  - cloud_cover
  - precipitation
  - precipitation_probability
  - wind_bearing
  - wind_speed
- Daily forecast data calculated by the component from the hourly forecast data. This is the most tricky part. I have compared the result of this with what the official Warnwetter app displays and the results seems to be very close.
  - datetime
  - temperature
  - templow
  - precipitation
  - cloud_cover
  - condition
- Uses the [HTTP ETag](https://en.wikipedia.org/wiki/HTTP_ETag) mechanism to only download new data if the data has changed. This allows more frequent polling (currently about every 10 minutes) while still keeping the load low.
- Configuration via UI

## Installation and Configuration

If you have access to your config folder of Home Assistant (e.g. if you have the Samba share add-on install in Supervisor), the installation is quite easy:

1. Create a folder named "custom_components" within the config folder, if it doesn't already exist.
2. Optional: If you have Python installed and if you like, you may run [tools/generate_stations/generate_stations.py](tools/generate_stations/generate_stations.py) to update the station list. However, it shouldn't change too often, that's why it is "pre-compiled".
3. Copy the whole dwd folder of this repository into the custom_components folder. I.e. your structure should in the end be /config/custom_components/dwd.
4. Restart Home Assistant. If you see a warning "You are using a custom integration dwd which has not been tested by Home Assistant." (and no errors of course) in the log, everything went well.

To add the actual weather entities, just add a new instance of the "Deutscher Wetterdienst" integration in the Home Assistant configuration menu:

1. Open "Configuration" from the main menu.
2. Open "Integrations" from the main menu.
3. Select "Add Integration"
4. Search for "Deutscher Wetterdienst" and open it.
5. Read the instructions, change the name and station ID if needed, and select "Submit".

After that, you should have 2 new weather entities, one with hourly forecast and one with daily forceast. Both have the same measurement data. You may repeast these steps if you want to add more stations.

Additionally, I can really recommend the custom weather card at https://github.com/bramkragten/weather-card, I started using that a long time ago, because it allows more customizations.

## Limitations and Known Issues
- This component has no icon in the integrations list yet, because there is no brand image in the brands repository (https://github.com/home-assistant/brands) yet.
- This component only creates weather entities, no sensors. The main reason is that I didn't need it. ;) However, I also believe that this is actually the correct design, because all data is available via the weather entity. Additionally adding sensors with the same data to me seems like a workaround for limitations that are actually somewhere else.
- I have been running the component at home for a long time already it it seems to be quite stable, at least for the weather station that I am using. There is only one real bug I currently know of: In very rare situations, the condition for the daily forecast isn't calculated, and I didn't have the chance to figure out the exact conditions for that yet.
- While this integration should follow the Home Assistant guidelines in most aspects, it doesn't in one aspect: It fetches the data directly from Deutscher Wetterdienst Open Data server instead of outsoucing the corresponding logic to a 3rd party component. This is probably also the main show-stopper for integrating this component directly into Home Assistant. Although I am a big fan of reuse and I understand the motivation, here is why I still haven't done it (yet):
  - I didn't know about this point when I started, otherwise I maybe would have started differently. As it's now more or less finished, I'm not in the mood of a complete refactoring. ;)
  - Most of the code deals with Home Assistant specific logic like integrating with the DataUpdateCoordinator of Home Assistant or mapping the data to values and structures Home Assistant expects (especially regarding the "condition" state attribute), which cannot be part of a generic component outside Home Assistant.
  - Even the part where we calculate the daily forecast from the hourly forecast is actually Home Assistant specific, because it works on the Home Assissant specific representation, not the source values from DWD. So if this is moved somewhere to be reused, it should rather be moved to some shared logic within Home Assistant, not to an external DWD library. 
  - What's really left that could be part of a separate component is only fetching the data itself, which are only simple HTTP Requests. The scheduling of the updates should however again be part of the Home Assistant component, because it needs close integration with the DataUpdateCoordinator.
- Because of the previous point, this component is not integrated as a native component yet. As I'm not using HACS myself, it's also not available via HACS. The only installation method is as described above.

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
