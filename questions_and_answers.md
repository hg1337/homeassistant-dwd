[![Release](https://img.shields.io/github/v/release/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/releases) [![Hassfest Workflow Status](https://img.shields.io/github/actions/workflow/status/hg1337/homeassistant-dwd/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/actions/workflows/hassfest.yml) [![License](https://img.shields.io/github/license/hg1337/homeassistant-dwd?style=for-the-badge)](https://github.com/hg1337/homeassistant-dwd/blob/main/LICENSE) [![Donation](https://img.shields.io/badge/Donation-Buy%20me%20a%20coffee-ffd557?style=for-the-badge)](https://www.buymeacoffee.com/hg1337)  
[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hg1337&repository=homeassistant-dwd&category=integration) [![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dwd)

# Deutscher Wetterdienst (DWD) Questions & Answers

Please read [README.md](./README.md) first, if you haven't already.

- [Why is the station that I would like to use not in the selection list when setting up the integration?](#why-is-the-station-that-i-would-like-to-use-not-in-the-selection-list-when-setting-up-the-integration)
- [How can I access forecast data from templates?](#how-can-i-access-forecast-data-from-templates)
- [I'm using a third party weather card that doesn't support the new forecast mechanism. Can I continue using it?](#im-using-a-third-party-weather-card-that-doesnt-support-the-new-forecast-mechanism-can-i-continue-using-it)
- [Why does the daily forecast for the current day differ from the Warnwetter app?](#why-does-the-daily-forecast-for-the-current-day-differ-from-the-warnwetter-app)
- [What is the difference to https://github.com/FL550/dwd_weather?](#what-is-the-difference-to-httpsgithubcomfl550dwd_weather)

## Why is the station that I would like to use not in the selection list when setting up the integration?

In the selection list the same stations as listed at [stations.md](./stations.md) are listed, ordered by distance from your home location configured in Home Assistant. If your station is missing, first try adding it manually by selecting "Custom..." from the list and entering the ID of the station. If this works, probably the station list is outdated and will be updated with the next release. If it doesn't work and you believe it should, please open an [issue](https://github.com/hg1337/homeassistant-dwd/issues), mentioning the station ID and name.

## How can I access forecast data from templates?

Accessing forecast data is basically done by calling the `weather.get_forecast` service, so wherever you want to access forecast data, you need to be able to call services. This is easily possible in automation actions where you can call services, but if you e.g. need it in a template condition, you need a different approach. The most universally applicable way is to create a template sensor that provides the information you need.

For more information on template sensors see https://www.home-assistant.io/integrations/template/

To create a template sensor that can call services, you need access to the config folder of Home Assistant as this is not possible with Helpers yet. How to access the config folder depends on how you have installed Home Assistant. If you are using the Home Assistant Operating System, you may e.g. use the "Studio Code Server" or "Samba share" add-on.

If your config folder doesn't contain a `templates.yaml` file yet, create an empty one and include it from the `configuration.yaml` by adding this line:

```yaml
template: !include templates.yaml
```

After doing this, go in the Developer Tools to the YAML tab and select "Check Configuration" to make sure you didn't break the configuration.

Then you can create your template sensor in the `templates.yaml` file. The following example shows a templates sensor that provides the precipitation for the next 3 hours:

```yaml
- trigger:
    - platform: time_pattern
      minutes: "*"
    - platform: homeassistant
      event: start
    - platform: event
      event_type: event_template_reloaded
  action:
    - service: weather.get_forecasts
      target:
        entity_id: weather.stuttgart_echterdingen
      data:
        type: hourly
      response_variable: forecast
  sensor:
    - name: "Precipitation next 3 hours"
      unique_id: precipitation_next_3_hours
      state: >
        {{
          forecast['weather.stuttgart_echterdingen'].forecast[0].precipitation
          + forecast['weather.stuttgart_echterdingen'].forecast[1].precipitation
          + forecast['weather.stuttgart_echterdingen'].forecast[2].precipitation
        }}
```

After making changes to your template sensors, you can reload them in the YAML tab of the Developer Tools by selecting to reload the Template Entities.

If everything went fine, you should see your new sensor in the States tab of the Developer Tools. You can now use it in any template, e.g.:

```yaml
{{ states("sensor.precipitation_next_3_hours") }}
```

Or in a [template condition](https://www.home-assistant.io/docs/scripts/conditions/#template-condition) in an automation:

```yaml
condition: template
value_template: 'states("sensor.precipitation_next_3_hours") > 10 }}'
```

## I'm using a third party weather card that doesn't support the new forecast mechanism. Can I continue using it?

More and more third party weather cards are being updated for new the forecast mechanism, but there might still be some that have not switched yet. The good news is, you can most likely continue using them by creating a template sensor. The approach is basically to call the `weather.get_forecast` service to get the hourly or daily forecast and provide the result in a state attribute.

**Before you continue: This is only a workaround. The correct way is to do the necessary changes in the third party weather cards to work with the new forecast mechanism.**

For more information on template sensors and to create them see also [How can I access forecast data from templates?](#how-can-i-access-forecast-data-from-templates) above.

You can use the following code as a starting point for your own template sensors. Change all occurrences of `stuttgart_echterdingen` to the Entity ID of your station. Also change the `name` and `unique_id` of the new sensors accordingly.

```yaml
- trigger:
    - platform: time_pattern
      minutes: "*"
    - platform: homeassistant
      event: start
    - platform: event
      event_type: event_template_reloaded
  action:
    - service: weather.get_forecasts
      target:
        entity_id: weather.stuttgart_echterdingen
      data:
        type: hourly
      response_variable: hourly_forecast
    - service: weather.get_forecasts
      target:
        entity_id: weather.stuttgart_echterdingen
      data:
        type: daily
      response_variable: daily_forecast
  sensor:
    - name: "Stuttgart-Echterdingen Hourly"
      unique_id: stuttgart_echterdingen_hourly
      state: "{{ states('weather.stuttgart_echterdingen') }}"
      attributes:
        temperature: "{{ state_attr('weather.stuttgart_echterdingen', 'temperature') }}"
        dew_point: "{{ state_attr('weather.stuttgart_echterdingen', 'dew_point') }}"
        temperature_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'temperature_unit') }}"
        humidity: "{{ state_attr('weather.stuttgart_echterdingen', 'humidity') }}"
        cloud_coverage: "{{ state_attr('weather.stuttgart_echterdingen', 'cloud_coverage') }}"
        pressure: "{{ state_attr('weather.stuttgart_echterdingen', 'pressure') }}"
        pressure_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'pressure_unit') }}"
        wind_bearing: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_bearing') }}"
        wind_gust_speed: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_gust_speed') }}"
        wind_speed: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_speed') }}"
        wind_speed_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_speed_unit') }}"
        visibility: "{{ state_attr('weather.stuttgart_echterdingen', 'visibility') }}"
        visibility_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'visibility_unit') }}"
        precipitation: "{{ state_attr('weather.stuttgart_echterdingen', 'precipitation') }}"
        precipitation_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'precipitation_unit') }}"
        forecast: "{{ hourly_forecast['weather.stuttgart_echterdingen'].forecast[:5] }}"
    - name: "Stuttgart-Echterdingen Daily"
      unique_id: stuttgart_echterdingen_daily
      state: "{{ states('weather.stuttgart_echterdingen') }}"
      attributes:
        temperature: "{{ state_attr('weather.stuttgart_echterdingen', 'temperature') }}"
        dew_point: "{{ state_attr('weather.stuttgart_echterdingen', 'dew_point') }}"
        temperature_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'temperature_unit') }}"
        humidity: "{{ state_attr('weather.stuttgart_echterdingen', 'humidity') }}"
        cloud_coverage: "{{ state_attr('weather.stuttgart_echterdingen', 'cloud_coverage') }}"
        pressure: "{{ state_attr('weather.stuttgart_echterdingen', 'pressure') }}"
        pressure_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'pressure_unit') }}"
        wind_bearing: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_bearing') }}"
        wind_gust_speed: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_gust_speed') }}"
        wind_speed: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_speed') }}"
        wind_speed_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'wind_speed_unit') }}"
        visibility: "{{ state_attr('weather.stuttgart_echterdingen', 'visibility') }}"
        visibility_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'visibility_unit') }}"
        precipitation: "{{ state_attr('weather.stuttgart_echterdingen', 'precipitation') }}"
        precipitation_unit: "{{ state_attr('weather.stuttgart_echterdingen', 'precipitation_unit') }}"
        forecast: "{{ daily_forecast['weather.stuttgart_echterdingen'].forecast[:5] }}"
```

To save resources, the template sensors above limit the forecasts to 5 items. If you need more, just change the `5` in `forecast[:5]` to a greater number. If the forecast array gets to large, you will see warnings from the Recorder in the logs that the state is too large to be stored in the history.

After making changes to your template sensors, you can reload them in the YAML tab of the Developer Tools by selecting to reload the Template Entities.

If everything went fine, you should find the two new senors in the States tab of the Developer Tools. They look pretty much like Weather entities, just that they are sensors with the "sensor" prefix instead of the "weather" prefix. Usually that doesn't disturb weather cards. They might just not show the entities in the selection list, but you can usually enter the ID manually.

## Why does the daily forecast for the current day differ from the Warnwetter app?

Currently, the daily forecast only takes the future into account which means for the current day the remaining hours including the current one. This was the most straight forward way during implementation, but it also makes sense from a user's perspective, that a *forecast* only shows what's coming up and not what already happened.

For example, if it rained the whole morning and the sun is going to shine the whole afternoon, and it's already afternoon, it's more useful to see the sun icon and not the rain oder mixed icon to know what's coming up.

If this is an issue in your scenario, please open an [issue](https://github.com/hg1337/homeassistant-dwd/issues) so we can discuss this.

## What is the difference to https://github.com/FL550/dwd_weather?

The reason that both exist is mainly because the other one didn’t exist yet when this one was started, so they were more or less developed in parallel. This one was just added to HACS much much later, and it was running privately at home for some time, before it was even put on GitHub. So none of the two is a clone or fork of the other.

That‘s why when you look at the two integrations, they are quite different in their approach. For example, this one from the beginning on focused much on real measurements while the other one only uses forecast data on purpose. However, while this one supports „only“ on the official Weather Entity, the other one provides additional sensors. There are many other differences, best you compare and decide for yourself, which one better fits your needs.

Because of the differences, it would be a huge effort to unify the two, and the outcome would probably rather be a third one.
