# Deutscher Wetterdienst (DWD) Setup

Please read [README.md](./README.md) first, if you haven't already.

- [Download](#download)
    - [Donwload via HACS](#download-via-hacs)
    - [Manual Download](#manual-download)
- [Configuration](#configuration)

## Download

As this integration is currently not part of Home Assistant Core, you have to download it first into your Home Assistant installation. The recommended way is via the [Home Assistant Community Store (HACS)](https://hacs.xyz), because it makes updates easier, but of course you can also do it manually, if you don't want to use HACS.

### Download via HACS

The easiest way is by clicking on the following button. It will directly open the download page for this integration in HACS.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration)

If you don't want to use the My Home Assistant button or if it doesn't work in your setup, follow these steps:

1. Open "HACS" from the Home Assistant main menu.
2. Select "Integrations".
3. Add this repository as a custom repository. (It might be available as a default repository soon. Then this step can be skipped.) To do this, click on the 3 dots and select "Custom repositories". Use this information:
    - Repository: https://github.com/hg1337/homeassistant-dwd
    - Category: Integration
4. Select "Explore & Dowload Repositories".
5. Search for "Deutscher Wetterdienst (by hg1337)" and select it.  
![Screenshot Add Repository](./images/screenshot_hacs_add-repository.png)  
There is another integration named "Deutscher Wetterdienst" available, that's not this one. However, feel free to try out both. ;)

Select "Download" and follow the instructions. To use the newly downloaded integration, you have to restart Home Assistant

### Manual Download

For manual download, you need access to the config folder of Home Assistant. This depends on how you have installed Home Assistant. If you are using the Home Assistant Operating System, you may e.g. use the "Samba share" or the "Terminal & SSH" add-on.

[![Open your Home Assistant instance and show the Supervisor add-on store.](https://my.home-assistant.io/badges/supervisor_store.svg)](https://my.home-assistant.io/redirect/supervisor_store/)

These steps are based on the "Samba share" add-on, but other methods are quite similar.

1. Create a folder named "custom_components" within the config folder, if it doesn't already exist.
2. Optional: If you have Python installed and if you like, you may run [tools/generate_stations/generate_stations.py](tools/generate_stations/generate_stations.py) to update the station list. However, it shouldn't change too often, that's why it is "pre-compiled".
3. Copy the whole custom_components/dwd folder of this repository into the custom_components folder. I.e. your structure should in the end be /config/custom_components/dwd.  
![Screenshot Installation Folder](./images/screenshot_installation-folder.png)
4. Restart Home Assistant. If you see a warning "You are using a custom integration dwd which has not been tested by Home Assistant." (and no errors of course) in the log, everything went well.

## Configuration

To add the actual weather device and entities, just add a new instance of the "Deutscher Wetterdienst" integration:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)

If you don't want to use the My Home Assistant button or if it doesn't work in your setup, follow these steps:

1. Open "Settings" from the Home Assistant main menu.
2. Select "Devices & Services".
3. Select "Add Integration".
4. Search for "Deutscher Wetterdienst" and select it.  
![Screenshot Search Integration](./images/screenshot_search-integration.png)
5. Follow the instructions, select a different station or enter a custom one if needed, e.g if you want to use a station that doesn't provide measurement data as only stations that provide measurement as well as forecast data are offered for direct selection.

After that, you should have one new device and two new weather entities for the selected station, one entity with hourly forecast and one entity with daily forceast. Both have the same measurement data. You may repeat these steps if you want to add more stations.

![Screenshot Entities](./images/screenshot_entities.png)

You may use these entities with any component that supports weather entities, e.g. the standard Weather Forecast Card:

![Screenshot Entities](./images/screenshot_weather-forecast-card-configuration.png)

I can really recommend the custom weather card at https://github.com/bramkragten/weather-card, I started using that a long time ago, because it allows more customizations than the standard weather forecast card:

![Screenshot Weather Card](./images/screenshot_bramkragten-weather-card.png)
