import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import DeviceTypeEnum
from .sensors_inverter import create_inverter_sensors
from .sensors_battery import create_battery_sensors

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform dynamically based on discovered devices."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # coordinator.data is the dictionary mapped by device serial number we built in _async_update_data
    if coordinator.data:
        for device_sn, device_info in coordinator.data.items():
            device_type = device_info.get("type")

            if device_type == DeviceTypeEnum.HIGH_FREQUENCY_INVERTER:
                sensor_list = create_inverter_sensors(coordinator, device_sn)
                entities.extend(sensor_list)
                _LOGGER.info(
                    "Created %d inverter sensor(s) for %s",
                    len(sensor_list), device_sn
                )

            elif device_type == DeviceTypeEnum.LITHIUM_BATTERY_PACK:
                sensor_list = create_battery_sensors(coordinator, device_sn)
                entities.extend(sensor_list)
                _LOGGER.info(
                    "Created %d battery sensor(s) for %s",
                    len(sensor_list), device_sn
                )
    else:
        _LOGGER.warning("No coordinator data available — no sensor entities will be created")

    if entities:
        _LOGGER.info("Adding %d total sensor entities to Home Assistant", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No sensor entities created — no devices discovered or data unavailable")
