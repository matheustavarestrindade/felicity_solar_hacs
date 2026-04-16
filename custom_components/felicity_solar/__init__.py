import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .coordinator import FelicitySolarCoordinator

_LOGGER = logging.getLogger(__name__)

# Tell HA which platforms we support (only sensors for now)
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Felicity Solar from a config entry."""
    _LOGGER.info("Setting up Felicity Solar integration for %s", entry.data.get(CONF_EMAIL, "unknown"))
    hass.data.setdefault(DOMAIN, {})

    # Extract the data saved by config_flow.py
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    update_interval = entry.data.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    _LOGGER.info("Update interval set to %d seconds", update_interval)

    # Boot up the background worker
    coordinator = FelicitySolarCoordinator(
        hass=hass,
        email=email,
        password=password,
        update_interval=update_interval
    )

    # Fetch the very first batch of data before creating the entities
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in memory so sensor.py can access it
    hass.data[DOMAIN][entry.entry_id] = coordinator

    _LOGGER.info(
        "First refresh complete, found %d device(s), forwarding setup to sensor platform",
        len(coordinator.data) if coordinator.data else 0
    )

    # Forward setup to sensor.py
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Felicity Solar integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry (e.g. if the user clicks Delete)."""
    _LOGGER.info("Unloading Felicity Solar integration for %s", entry.data.get(CONF_EMAIL, "unknown"))
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Felicity Solar integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload Felicity Solar integration")
    return unload_ok
