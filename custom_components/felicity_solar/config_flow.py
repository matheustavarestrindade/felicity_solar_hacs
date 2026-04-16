import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .api import FelicitySolarAPI, create_felicity_client_session

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
    ),
    vol.Required(CONF_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
})


class FelicitySolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Felicity Solar."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                # Create a session with custom SSL handling for Felicity Solar
                session = create_felicity_client_session(self.hass)

                # Initialize the API to test credentials
                api = FelicitySolarAPI(email, password, session)

                # If initialize() passes without throwing an error, credentials are valid!
                await api.initialize()

                return self.async_create_entry(
                    title=email,
                    data=user_input
                )
            except Exception as err:
                _LOGGER.error(
                    f"Failed to authenticate with Felicity Solar: {err}")
                errors["base"] = "invalid_auth"

        # Show the form (with red errors if authentication failed)
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )
