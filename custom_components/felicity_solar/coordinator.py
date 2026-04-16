import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FelicitySolarAPI, DeviceTypeEnum
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    """Convert value to float, returning default if value is None or invalid."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=0):
    """Convert value to int, returning default if value is None or invalid."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


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
            _LOGGER.info("Starting data update cycle")

            # Re-auth and load devices if needed
            await self.api.initialize()

            devices_data = {}
            serial_numbers = self.api.get_devices_serial_numbers()

            if not serial_numbers:
                _LOGGER.warning("No devices found — check your Felicity Solar account or credentials")
                return devices_data

            _LOGGER.info("Fetching snapshots for %d device(s)", len(serial_numbers))

            for device_sn in serial_numbers:
                try:
                    snapshot = await self.api.get_device_snapshot(device_sn)
                    device_type = snapshot.get("productTypeEnum")

                    if device_type == DeviceTypeEnum.HIGH_FREQUENCY_INVERTER:
                        devices_data[device_sn] = {
                            "type": device_type,
                            "serialNumber": device_sn,
                            "data": {
                                "acInputVoltage": _safe_float(snapshot.get("acRInVolt")),
                                "acInputFrequency": _safe_float(snapshot.get("acRInFreq")),
                                "acInputPower": _safe_float(snapshot.get("acRInPower")),
                                "acOutputVoltage": _safe_float(snapshot.get("acROutVolt")),
                                "acOutputCurrent": _safe_float(snapshot.get("acROutCurr")),
                                "acOutputFrequency": _safe_float(snapshot.get("acROutFreq")),
                                "acTotalOutputActivePower": _safe_float(snapshot.get("acTotalOutActPower")),
                                "loadPercentage": _safe_float(snapshot.get("loadPercent")),
                                "pvVoltage": _safe_float(snapshot.get("pvVolt")),
                                "pvInputCurrent": _safe_float(snapshot.get("pvInCurr")),
                                "pvPower": _safe_float(snapshot.get("pvPower")),
                                "pvTotalPower": _safe_float(snapshot.get("pvTotalPower")),
                                "batteryVoltage": _safe_float(snapshot.get("emsVoltage")),
                                "batteryCurrent": _safe_float(snapshot.get("emsCurrent")),
                                "batteryPower": _safe_float(snapshot.get("emsPower")),
                                "batterySoc": _safe_int(snapshot.get("emsSoc")),
                                "tempMax": _safe_float(snapshot.get("tempMax")),
                                "devTempMax": _safe_float(snapshot.get("devTempMax")),
                                "energyPvToday": _safe_float(snapshot.get("ePvToday")),
                                "energyPvTotal": _safe_float(snapshot.get("ePvTotal")),
                                "energyLoadToday": _safe_float(snapshot.get("eLoadToday")),
                                "energyLoadTotal": _safe_float(snapshot.get("eLoadTotal")),
                                "totalEnergy": _safe_float(snapshot.get("totalEnergy")),
                            }
                        }
                    elif device_type == DeviceTypeEnum.LITHIUM_BATTERY_PACK:
                        devices_data[device_sn] = {
                            "type": device_type,
                            "serialNumber": device_sn,
                            "data": {
                                "voltage": _safe_float(snapshot.get("battVolt")),
                                "current": _safe_float(snapshot.get("battCurr")),
                                "soc": _safe_int(snapshot.get("battSoc")),
                                "soh": _safe_int(snapshot.get("battSoh")),
                                "ratedEnergy": _safe_float(snapshot.get("ratedEnergy")),
                                "energyUnit": str(snapshot.get("energyUnit", "")),
                                "nameplateRatedPower": str(snapshot.get("nameplateRatedPower", "")),
                            }
                        }
                    else:
                        _LOGGER.warning(
                            "Unknown device type '%s' for %s, skipping",
                            device_type, device_sn
                        )
                        continue

                    _LOGGER.debug("Data fetched successfully for %s (%s)", device_sn, device_type)

                except Exception as err:
                    _LOGGER.error("Failed to fetch snapshot for device %s: %s", device_sn, err)
                    continue

            _LOGGER.info(
                "Data update complete: %d device(s) with data out of %d",
                len(devices_data), len(serial_numbers)
            )
            return devices_data

        except Exception as err:
            _LOGGER.error("Update failed: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}")
