# Deutscher Wetterdienst (DWD) Questions & Answers

Please read [README.md](./README.md) first, if you haven't already.

- [Why is the station that I would like to use not in the selection list when setting up the integration?](#why-is-the-station-that-i-would-like-to-use-not-in-the-selection-list-when-setting-up-the-integration)
- [Can you add sensors?](#can-you-add-sensors)
- [Do you have example templates how to access forecast data? ](#do-you-have-example-templates-how-to-access-forecast-data)
- [Why does the daily forecast for the current day differ from the Warnwetter app?](#why-does-the-daily-forecast-for-the-current-day-differ-from-the-warnwetter-app)

## Why is the station that I would like to use not in the selection list when setting up the integration?

For quality reasons, the selection list only contains stations that provide both measurement and forecast data, which are the same stations as listed at [stations.md](./stations.md). However, if you like, you can also use stations that have only measurement data or only forecast data. To do that, just select "Custom..." from the list and enter the ID of the station manually.

If you find a station that provides both measurement and forecast data and is still not listed, please open an [issue](https://github.com/hg1337/homeassistant-dwd/issues), mentioning the station ID and name.

## Can you add sensors?

This integration creates [Weather Entities](https://developers.home-assistant.io/docs/core/entity/weather/) for each weather station which basically is like a (complex) sensor and is even displayed as sensors in the UI. If you are thinking about having one sensor entity per value, this would not be the correct design for weather data and also leads to problems when it comes to forecast data which is an array of forecast objects. Everything that is possible with simple sensors should also be possible with Weather Entities. In the worst case you have to use templates, but in most places you can now directly access state attributes.

## Do you have example templates how to access forecast data?

Sure. This accesses the minimum temperature in 3 days:

```
{{ state_attr("weather.stuttgart_echterdingen_daily", "forecast")[3].get("templow") }}
```

`forecast` is an array starting at the current hour for the hourly entities and at the current day for daily entities, so for the daily entity, 0 is today, 1 is tomorrow etc. If you are unsure, you can also display the date/time:

```
{{ state_attr("weather.stuttgart_echterdingen_daily", "forecast")[3].get("datetime") }}
```

To use this in an automation, you can use a value template, e.g. in a [template condition](https://www.home-assistant.io/docs/scripts/conditions/#template-condition):

```
condition: template
value_template: '{{ state_attr("weather.stuttgart_echterdingen_daily", "forecast")[3].get("templow") > 10 }}'
```

Try it out with your entities:

[![Open your Home Assistant instance and show your template developer tools.](https://my.home-assistant.io/badges/developer_template.svg)](https://my.home-assistant.io/redirect/developer_template/)

To explore what's available, it's best to have a look at the entities themselves:

[![Open your Home Assistant instance and show your state developer tools.](https://my.home-assistant.io/badges/developer_states.svg)](https://my.home-assistant.io/redirect/developer_states/)

## Why does the daily forecast for the current day differ from the Warnwetter app?

Currently, the daily forecast only takes the future into account which means for the current day the remaining hours including the current one. This was the most straight forward way during implementation, but it also makes sense from a user's perspective, that a *forecast* only shows what's coming up and not what already happened.

For example, if it rained the whole morning and the sun is going to shine the whole afternoon, and it's already afternoon, it's more useful to see the sun icon and not the rain oder mixed icon to know what's coming up.

If this is an issue in your scenario, please open an [issue](https://github.com/hg1337/homeassistant-dwd/issues) so we can discuss this.