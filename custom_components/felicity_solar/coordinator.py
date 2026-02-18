import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FelicitySolarAPI, DeviceTypeEnum
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FelicitySolarCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from Felicity Solar."""

    def __init__(self, hass: HomeAssistant, email: str, password: str, update_interval: int):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.api = FelicitySolarAPI(
            email=email,
            password=password,
            session=async_get_clientsession(hass)
        )

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from API for all devices."""
        try:
            # Re-auth and load devices if needed
            await self.api.initialize()

            devices_data = {}

            for device_sn in self.api.get_devices_serial_numbers():
                try:
                    snapshot = await self.api.get_device_snapshot(device_sn)
                    device_type = snapshot.get("productTypeEnum")

                    if device_type == DeviceTypeEnum.HIGH_FREQUENCY_INVERTER:
                        devices_data[device_sn] = {
                            "type": device_type,
                            "serialNumber": device_sn,
                            "data": {
                                "acInputVoltage": float(snapshot.get("acRInVolt", 0)),
                                "acInputFrequency": float(snapshot.get("acRInFreq", 0)),
                                "acInputPower": float(snapshot.get("acRInPower", 0)),
                                "acOutputVoltage": float(snapshot.get("acROutVolt", 0)),
                                "acOutputCurrent": float(snapshot.get("acROutCurr", 0)),
                                "acOutputFrequency": float(snapshot.get("acROutFreq", 0)),
                                "acTotalOutputActivePower": float(snapshot.get("acTotalOutActPower", 0)),
                                "loadPercentage": float(snapshot.get("loadPercent", 0)),
                                "pvVoltage": float(snapshot.get("pvVolt", 0)),
                                "pvInputCurrent": float(snapshot.get("pvInCurr", 0)),
                                "pvPower": float(snapshot.get("pvPower", 0)),
                                "pvTotalPower": float(snapshot.get("pvTotalPower", 0)),
                                "batteryVoltage": float(snapshot.get("emsVoltage", 0)),
                                "batteryCurrent": float(snapshot.get("emsCurrent", 0)),
                                "batteryPower": float(snapshot.get("emsPower", 0)),
                                "batterySoc": int(snapshot.get("emsSoc", 0)),
                                "tempMax": float(snapshot.get("tempMax", 0)),
                                "devTempMax": float(snapshot.get("devTempMax", 0)),
                                "energyPvToday": float(snapshot.get("ePvToday", 0)),
                                "energyPvTotal": float(snapshot.get("ePvTotal", 0)),
                                "energyLoadToday": float(snapshot.get("eLoadToday", 0)),
                                "energyLoadTotal": float(snapshot.get("eLoadTotal", 0)),
                                "totalEnergy": float(snapshot.get("totalEnergy", 0)),
                            }
                        }
                    elif device_type == DeviceTypeEnum.LITHIUM_BATTERY_PACK:
                        devices_data[device_sn] = {
                            "type": device_type,
                            "serialNumber": device_sn,
                            "data": {
                                "voltage": float(snapshot.get("battVolt", 0)),
                                "current": float(snapshot.get("battCurr", 0)),
                                "soc": int(snapshot.get("battSoc", 0)),
                                "soh": int(snapshot.get("battSoh", 0)),
                                "ratedEnergy": float(snapshot.get("ratedEnergy", 0)),
                                "energyUnit": str(snapshot.get("energyUnit", "")),
                                "nameplateRatedPower": str(snapshot.get("nameplateRatedPower", "")),
                            }
                        }
                except Exception as err:
                    _LOGGER.error(f"Failed to fetch snapshot for device {
                                  device_sn}: {err}")
                    continue

            return devices_data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
