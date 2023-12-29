[![Release](https://img.shields.io/github/v/release/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/releases) [![Hassfest Workflow Status](https://img.shields.io/github/actions/workflow/status/hg1337/homeassistant-dwd/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/actions/workflows/hassfest.yml) [![License](https://img.shields.io/github/license/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/blob/main/LICENSE) [![Donation](https://img.shields.io/badge/Donation-Buy%20me%20a%20coffee-ffd557?style=for-the-badge)](https://www.buymeacoffee.com/hg1337)  
[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration) [![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)

# Migration to New Weather Entity and Forecasts

This page is for people running this integration already. If you are new, please start at [README.md](./README.md).

With release 2023.8, Home Assistant has switched to a new mechanism how weather forecasts are provided. Before that, weather forecasts were provided via a state attribute of the weather entities, and the weather entities for each station needed to be duplicated to provide both hourly and daily forecasts.

Since Home Assistant 2023.8, all forecasts are provdided by a single entity (per station) and are retrieved by the [weather.get_forecasts service](https://www.home-assistant.io/integrations/weather/#service-weatherget_forecasts).

Currently, this integration provides both mechnisms in parallel via three different entities, the old ones with the `_daily` and `_hourly` suffix (disabled by default for new stations), and the new one without suffix, see screenshot below. But as the old mechism is deprecated by Home Assistant, it will eventually go away, [probably around Home Assistant 2024.3](https://developers.home-assistant.io/blog/2023/08/07/weather_entity_forecast_types/). So you should migrate to the new entities and the new mechanism now.

![Screenshot Entities](./images/screenshot_entities.png)

If you only use the built-in Weather Forecard Card from Home Assistant, the migration is usually as easy as removing the `_daily` or `_hourly` suffix from the Entity ID in the configuration of the Weather Forecast Card and selecting the desired forecast type (daily or hourly).

![Screenshot Weather Forecast Card Configuration](./images/screenshot_weather-forecast-card-configuration.png)

You should also disable the daily and hourly entities afterwards to make sure you don't use them any more.

[![Open your Home Assistant instance and show your entities.](https://my.home-assistant.io/badges/entities.svg)](https://my.home-assistant.io/redirect/entities/)

If you use the forecasts from the state attribute in a template sensor or automation, or if you are using a third party weather card that has not been adapted yet, there is a bit more work to do. For that, you may find these resources helpful:

- [Examples](https://www.home-assistant.io/integrations/weather/#examples) in the Home Assistant documentation.
- [Questions & Answers](./questions_and_answers.md) for this integration which also include a complete example for a template sensor that can be used as a drop-in replacement for third party weather cards that have not be adapted yet.
