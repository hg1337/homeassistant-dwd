# Takes station information from the following URLs and creates the stations.json file: 
# - https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication
# - https://opendata.dwd.de/weather/weather_reports/poi/
# - https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/
# As the station list doesn't change frequently, we don't download everything online in the dwd component.
# See also https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg

import json
import os
import re
import urllib.request
import codecs
import datetime
from html.parser import HTMLParser

SOURCE_STATIONSLEXIKON = 0
SOURCE_MOSMIX_STATIONSKATALOG = 1

NAME_RE = re.compile("[A-ZÄÖÜ]{2,}")

def beautify_name(name: str) -> str:
    return NAME_RE.sub(lambda x: x.group()[0] + x.group()[1:].lower(), name)

if __name__ == "__main__":

    measurement_href_pattern = re.compile(r"^(.*[^_])_*-BEOB\.csv$")
    forecast_href_pattern = re.compile(r"^(.+)/$")
    mosmix_stationskatalog_pattern = re.compile(r"^([^ ]+)[ ]+([^ ]+)[ ]+(.+[^ ])[ ]+(-?[0-9]+\.[0-9]+)[ ]+(-?[0-9]+\.[0-9]+)[ ]+(-?[0-9]+?)$")

    class HtmlStationListParser(HTMLParser):

        def __init__(self, href_pattern: re.Pattern) -> None:
            self._href_pattern = href_pattern
            self.result = set()
            super().__init__()

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                for attr in attrs:
                    if attr[0] == "href":
                        match = self._href_pattern.match(attr[1])
                        if match:
                            self.result.add(match.groups()[0])

    class HtmlStationslexikonParser(HTMLParser):
        def __init__(self) -> None:
            self.result = {}
            self._current_row = None
            self._current_content = None
            super().__init__()

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self._current_row = []

        def handle_endtag(self, tag):
            if tag == "tr":
                if len(self._current_row) >= 11:
                    name = self._current_row[0]
                    feature = self._current_row[2]
                    station_id = self._current_row[3]
                    latitude = self._current_row[4]
                    longitude = self._current_row[5]
                    altitude = self._current_row[6]
                    start = self._current_row[9]
                    end = self._current_row[10]
                    if name and feature and station_id and latitude and longitude and altitude and start and end:
                        startdate = datetime.datetime.strptime(start, r"%d.%m.%Y").date()
                        enddate = datetime.datetime.strptime(end, r"%d.%m.%Y").date()
                        if startdate < datetime.date.today() + datetime.timedelta(days=7) and enddate > datetime.date.today() - datetime.timedelta(days=7) and feature in ["SY", "TU"]:
                            self.result[station_id] = (name, latitude, longitude, altitude)
                self._current_content = None
                self._current_row = None
            elif tag == "td":
                self._current_row.append(self._current_content)
                self._current_content = None

        def handle_data(self, data):
            if self._current_row is not None:
                self._current_content = data.strip()

    result = []

    measurement_stations = None
    forecast_stations = None
    stationslexikon_stations = None

    url = "https://rcc.dwd.de/DE/leistungen/klimadatendeutschland/statliste/statlex_html.html?view=nasPublication"
    print(f"Loading and parsing Stationslexikon from {url}...", end="", flush=True)
    with urllib.request.urlopen(url) as response:
        stationslexikon_parser = HtmlStationslexikonParser()
        stationslexikon_parser.feed(codecs.decode(response.read(), 'iso-8859-1'))
        stationslexikon_stations = stationslexikon_parser.result
    print(f"done.")
    print(f"Found useful information about {len(stationslexikon_stations)} stations.")

    url = "https://opendata.dwd.de/weather/weather_reports/poi/"
    print(f"Checking which stations provide measurement data at {url}...", end="", flush=True)
    with urllib.request.urlopen(url) as response:
        measurement_parser = HtmlStationListParser(measurement_href_pattern)
        measurement_parser.feed(codecs.decode(response.read(), 'iso-8859-1'))
        measurement_stations = measurement_parser.result
    print(f"done.")
    print(f"Found {len(measurement_stations)} stations.")

    url = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/"
    print(f"Checking which stations provide forecast data at {url}...", end="", flush=True)
    with urllib.request.urlopen(url) as response:
        forecast_parser = HtmlStationListParser(forecast_href_pattern)
        forecast_parser.feed(codecs.decode(response.read(), 'iso-8859-1'))
        forecast_stations = forecast_parser.result
    print(f"done.")
    print(f"Found {len(forecast_stations)} stations.")

    url = "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication"
    print(f"Getting MISMIX Stationskatalog from {url} and combining all information...", end="", flush=True)
    with urllib.request.urlopen(url) as response:
        for line in response:
            line = codecs.decode(line, 'iso-8859-1')
            match = mosmix_stationskatalog_pattern.match(line)
            if match:
                station_id = match.groups()[0]
                station_measurement = (station_id in measurement_stations)
                station_forecast = (station_id in forecast_stations)
                if station_measurement or station_forecast:
                    data_from_stationslexikon = stationslexikon_stations.get(station_id, None)
                    if data_from_stationslexikon is None:
                        station_name = beautify_name(match.groups()[2])
                        station_latitude = float(match.groups()[3])
                        station_longitude = float(match.groups()[4])
                        station_altitude = float(match.groups()[5])
                        station_source = SOURCE_MOSMIX_STATIONSKATALOG
                    else:
                        station_name = data_from_stationslexikon[0]
                        station_latitude = float(data_from_stationslexikon[1])
                        station_longitude = float(data_from_stationslexikon[2])
                        station_altitude = float(data_from_stationslexikon[3])
                        station_source = SOURCE_STATIONSLEXIKON
                    result.append({"id": station_id, "name": station_name, "latitude": station_latitude, "longitude": station_longitude, "altitude": station_altitude, "measurement": station_measurement, "forecast": station_forecast, "source": station_source})
    print(f"done.")
    print(f"Result contains {len(result)} stations providing measurement or forcast data.")

    print(f"Sorting list by station name...", end="", flush=True)
    result = list(sorted(result, key=lambda x: x["name"].casefold()))
    print(f"done.")

    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "custom_components", "dwd", "stations.json")
    print(f"Writing stations to {filename}...", end="", flush=True)
    with open(filename, "wt", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False)
    print(f"done.")

    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "stations.md")
    print(f"Writing stations to {filename}...", end="", flush=True)
    with open(filename, "wt", encoding="utf-8") as file:
        file.write("[![Release](https://img.shields.io/github/v/release/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/releases) [![Hassfest Workflow Status](https://img.shields.io/github/actions/workflow/status/hg1337/homeassistant-dwd/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/actions/workflows/hassfest.yml) [![License](https://img.shields.io/github/license/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/blob/main/LICENSE) [![Donation](https://img.shields.io/badge/Donation-Buy%20me%20a%20coffee-ffd557?style=for-the-badge)](https://www.buymeacoffee.com/hg1337)  \n")
        file.write("[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration) [![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)\n")
        file.write("\n")
        file.write("# Deutscher Wetterdienst Stations\n")
        file.write("\n")
        file.write("Please read [README.md](./README.md) first, if you haven't already.\n")
        file.write("\n")
        file.write("The following table lists the stations of Deutscher Wetterdienst that provide\n")
        file.write("measurement or forecast data and can probably be used by this Home Assistant\n")
        file.write(f"integration. It contains a total of {len(result)} stations and was automatically\n")
        file.write("generated by\n")
        file.write("[tools/generate_stations/generate_stations.py](./tools/generate_stations/generate_stations.py)\n")
        file.write("using information provided by Deutscher Wetterdienst.\n")
        file.write("\n")
        file.write(f"{sum(1 for _ in filter(lambda x: x['source'] == SOURCE_STATIONSLEXIKON, result))} stations were found in the\n")
        file.write("[Stationslexikon](https://rcc.dwd.de/DE/leistungen/klimadatendeutschland/stationsliste.html)\n")
        file.write(f"and additional {sum(1 for _ in filter(lambda x: x['source'] == SOURCE_MOSMIX_STATIONSKATALOG, result))} stations were found in the\n")
        file.write("[MOSMIX Stationskatalog](https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg)\n")
        file.write(f"that were not listed in the Stationslexikon. The Stationslexikon is preferred\n")
        file.write("because it contains more precise geo coordinates and nicer names.\n")
        file.write("\n")
        file.write(f"{sum(1 for _ in filter(lambda x: x['measurement'], result))} of these stations provide [measurement data](https://opendata.dwd.de/weather/weather_reports/poi/),\n")
        file.write(f"{sum(1 for _ in filter(lambda x: x['forecast'], result))} provide [forecast data](https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/)\n")
        file.write(f"and {sum(1 for _ in filter(lambda x: x['measurement'] and x['forecast'], result))} provide both.\n")
        file.write("\n")
        file.write("Although this list is generated from original data from Deutscher Wetterdienst,\n")
        file.write("this is no offical list and it is not updated automatically. There might also be\n")
        file.write("stations that are not in this list that work as well. So when in doubt, please\n")
        file.write("check the original lists above and try their ID.\n")
        file.write("\n")
        file.write("ID       | Name                        | Latitude    | Longitude   | Altitude | Limitations         | Source                \n")
        file.write("---------|-----------------------------|-------------|-------------|----------|---------------------|-----------------------\n")
        for station in result:
            file.write(station["id"].ljust(9))
            file.write("| ")
            file.write(station["name"].ljust(28))
            file.write("| ")
            file.write(str(station["latitude"]).ljust(12))
            file.write("| ")
            file.write(str(station["longitude"]).ljust(12))
            file.write("| ")
            file.write(str(station["altitude"]).ljust(9))
            file.write("| ")
            if not station["measurement"]:
                file.write("no measurement data ")
            elif not station["forecast"]:
                file.write("no forecast data    ")
            else:
                file.write("                    ")
            file.write("| ");
            if station["source"] == SOURCE_STATIONSLEXIKON:
                file.write("Stationslexikon")
            elif station["source"] == SOURCE_MOSMIX_STATIONSKATALOG:
                file.write("MOSMIX Stationskatalog")
            else:
                file.write("                        ")
            file.write("\n")
    print(f"done.")
