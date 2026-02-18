from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfFrequency,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Define all the data points from your HighFrequencyInverterData type
INVERTER_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="acInputVoltage", name="AC Input Voltage",
                            native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE),
    SensorEntityDescription(key="acInputFrequency", name="AC Input Frequency",
                            native_unit_of_measurement=UnitOfFrequency.HERTZ, device_class=SensorDeviceClass.FREQUENCY),
    SensorEntityDescription(key="acInputPower", name="AC Input Power",
                            native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER),
    SensorEntityDescription(key="acOutputVoltage", name="AC Output Voltage",
                            native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE),
    SensorEntityDescription(key="acOutputCurrent", name="AC Output Current",
                            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT),
    SensorEntityDescription(key="acTotalOutputActivePower", name="AC Total Output Power",
                            native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER),
    SensorEntityDescription(
        key="loadPercentage", name="Load Percentage", native_unit_of_measurement=PERCENTAGE),
    SensorEntityDescription(key="pvVoltage", name="PV Voltage",
                            native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE),
    SensorEntityDescription(key="pvPower", name="PV Power",
                            native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER),
    SensorEntityDescription(key="pvTotalPower", name="PV Total Power",
                            native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER),
    SensorEntityDescription(key="batterySoc", name="Battery SOC",
                            native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY),
    SensorEntityDescription(key="tempMax", name="Inverter Temp",
                            native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE),
    # Note: For energy sensors, StateClass.TOTAL_INCREASING allows it to be used in the HA Energy Dashboard
    SensorEntityDescription(key="energyPvToday", name="Energy PV Today", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                            device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING),
    SensorEntityDescription(key="totalEnergy", name="Total System Energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                            device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING),
)


def create_inverter_sensors(coordinator, device_sn):
    return [FelicityInverterSensor(coordinator, device_sn, desc) for desc in INVERTER_DESCRIPTIONS]


class FelicityInverterSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, device_sn: str, description: SensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self.device_sn = device_sn
        self._attr_unique_id = f"{device_sn}_{description.key}"
        # Links this sensor to a specific device in the Home Assistant UI
        self._attr_device_info = {
            "identifiers": {("felicity_solar", device_sn)},
            "name": f"Felicity Inverter {device_sn}",
            "manufacturer": "Felicity Solar",
            "model": "High Frequency Inverter",
        }

    @property
    def native_value(self):
        """Extract the exact key value from coordinator data."""
        device_data = self.coordinator.data.get(
            self.device_sn, {}).get("data", {})
        return device_data.get(self.entity_description.key)
