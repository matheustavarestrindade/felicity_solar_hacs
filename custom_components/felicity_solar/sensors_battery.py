from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    PERCENTAGE,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Define all the data points from your BatteryData type
BATTERY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="voltage", name="Voltage",
                            native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE),
    SensorEntityDescription(key="current", name="Current",
                            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT),
    SensorEntityDescription(key="soc", name="State of Charge",
                            native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY),
    SensorEntityDescription(key="soh", name="State of Health",
                            native_unit_of_measurement=PERCENTAGE),
)


def create_battery_sensors(coordinator, device_sn):
    return [FelicityBatterySensor(coordinator, device_sn, desc) for desc in BATTERY_DESCRIPTIONS]


class FelicityBatterySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, device_sn: str, description: SensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self.device_sn = device_sn
        self._attr_unique_id = f"{device_sn}_{description.key}"
        self._attr_device_info = {
            "identifiers": {("felicity_solar", device_sn)},
            "name": f"Felicity Battery {device_sn}",
            "manufacturer": "Felicity Solar",
            "model": "Lithium Battery Pack",
        }

    @property
    def native_value(self):
        device_data = self.coordinator.data.get(
            self.device_sn, {}).get("data", {})
        return device_data.get(self.entity_description.key)
