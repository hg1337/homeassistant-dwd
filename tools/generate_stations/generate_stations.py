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

if __name__ == "__main__":

    measurement_href_pattern = re.compile(r"^(.+)-BEOB\.csv$")
    forecast_href_pattern = re.compile(r"^(.+)/$")

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
            if len(line) >= 76:
                station_id = line[12:17].strip()
                if station_id != "id" and station_id != "=====" and station_id in measurement_stations and station_id in forecast_stations:
                    data_from_stationslexikon = stationslexikon_stations.get(station_id, None)
                    if data_from_stationslexikon is None:
                        station_name = line[23:44].strip()
                        station_latitude = float(line[44:50])
                        station_longitude = float(line[51:58])
                        station_altitude = float(line[59:64])
                    else:
                        station_name = data_from_stationslexikon[0]
                        station_latitude = float(data_from_stationslexikon[1])
                        station_longitude = float(data_from_stationslexikon[2])
                        station_altitude = float(data_from_stationslexikon[3])
                    result.append({"id": station_id, "name": station_name, "latitude": station_latitude, "longitude": station_longitude, "altitude": station_altitude})
    print(f"done.")
    print(f"Result contains {len(result)} stations providing measurement and forcast data.")

    print(f"Sorting list by station name...", end="", flush=True)
    result = sorted(result, key=lambda x: x["name"])
    print(f"done.")

    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "dwd", "stations.json")
    print(f"Writing stations to {filename}...", end="", flush=True)
    with open(filename, "wt", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False)
    print(f"done.")

    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "stations.md")
    print(f"Writing stations to {filename}...", end="", flush=True)
    with open(filename, "wt", encoding="utf-8") as file:
        file.write("# Deutscher Wetterdienst Stations\n")
        file.write("\n")
        file.write("The following table lists the stations of Deutscher Wetterdienst that provide\n")
        file.write("measurement and forecast data and can probably be used by this Home Assistant\n")
        file.write("integration. This list was automatically generated by\n")
        file.write("tools/generate_stations/generate_stations.py using information provided by\n")
        file.write("Deutscher Wetterdienst at\n")
        file.write("https://rcc.dwd.de/DE/leistungen/klimadatendeutschland/stationsliste.html and\n")
        file.write("https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg\n")
        file.write("filtered by stations that provide data via\n")
        file.write("https://opendata.dwd.de/weather/weather_reports/poi/ and\n")
        file.write("https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/\n")
        file.write("which is used by this Home Assistant integration.\n")
        file.write("\n")
        file.write("Although this list is generated by original data from Deutscher Wetterdienst,\n")
        file.write("this is no offical list and it is not updated automatically. There might also\n")
        file.write("stations that are not in this list that work as well. So when in doubt, please\n")
        file.write("check the original lists above and try their ID. Deutscher Wetterdienst has\n")
        file.write("thousands of stations and below is only a subset.\n")
        file.write("\n")
        file.write("ID       | Name                        | Latitude    | Longitude   | Altitude \n")
        file.write("---------|-----------------------------|-------------|-------------|----------\n")
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
            file.write("\n")
    print(f"done.")
