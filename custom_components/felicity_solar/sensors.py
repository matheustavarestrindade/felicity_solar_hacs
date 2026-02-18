from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import DeviceTypeEnum
from .sensors_inverter import create_inverter_sensors
from .sensors_battery import create_battery_sensors


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the sensor platform dynamically based on discovered devices."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # coordinator.data is the dictionary mapped by device serial number we built in _async_update_data
    for device_sn, device_info in coordinator.data.items():
        device_type = device_info.get("type")

        if device_type == DeviceTypeEnum.HIGH_FREQUENCY_INVERTER:
            entities.extend(create_inverter_sensors(coordinator, device_sn))

        elif device_type == DeviceTypeEnum.LITHIUM_BATTERY_PACK:
            entities.extend(create_battery_sensors(coordinator, device_sn))

    if entities:
        async_add_entities(entities)
