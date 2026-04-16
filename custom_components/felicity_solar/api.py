import logging
import re
import json
import base64
import os
import asyncio
import ssl
from urllib.parse import urljoin
from datetime import datetime
from enum import Enum
import jwt
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import aiohttp

_LOGGER = logging.getLogger(__name__)


def create_felicity_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips verification for Felicity Solar servers.

    The Felicity Solar API servers (shine.felicitysolar.com, shine-api.felicitysolar.com)
    serve their leaf certificate without the intermediate CA, which causes
    SSLCertVerificationError on most clients. We disable cert verification
    only for requests to these hosts.
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    _LOGGER.info("Created custom SSL context (certificate verification disabled for Felicity Solar hosts)")
    return ssl_context


def create_felicity_client_session(hass=None) -> aiohttp.ClientSession:
    """Create an aiohttp ClientSession with custom SSL handling for Felicity Solar."""
    connector = aiohttp.TCPConnector(ssl=create_felicity_ssl_context())
    return aiohttp.ClientSession(connector=connector)


class DeviceTypeEnum(str, Enum):
    LITHIUM_BATTERY_PACK = "LITHIUM_BATTERY_PACK"
    HIGH_FREQUENCY_INVERTER = "HIGH_FREQUENCY_INVERTER"


class FelicitySolarAPI:
    JSON_FILE_PATH = "data/felicitySolarToken.json"
    LOGIN_URL = "https://shine.felicitysolar.com/login"
    API_URL_DEVICE_LIST = "https://shine-api.felicitysolar.com/device/list_device_all_type"
    API_URL_DEVICE_SNAPSHOT = "https://shine-api.felicitysolar.com/device/get_device_snapshot"
    API_URL_USER_LOGIN = "https://shine-api.felicitysolar.com/userlogin"

    def __init__(self, email: str, password: str, session: aiohttp.ClientSession):
        self.email = email
        self.password = password
        self.session = session

        self.bearer_token: str | None = None
        self.token_expiration: datetime | None = None
        self.devices_serial_numbers: list[str] = []

    async def initialize(self) -> None:
        _LOGGER.info("Initializing Felicity Solar API for %s", self.email)
        await self._load_from_file()

        if not self._is_logged_in():
            if self.bearer_token and self.token_expiration:
                _LOGGER.warning(
                    "Token expired at %s, re-authenticating",
                    self.token_expiration.strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                _LOGGER.info("No valid token found, authenticating with Felicity Solar")
            await self._login()
        else:
            _LOGGER.info(
                "Token is valid, expires at %s",
                self.token_expiration.strftime("%Y-%m-%d %H:%M:%S")
            )

        await self._load_devices_serial_numbers()
        _LOGGER.info(
            "Initialization complete, found %d device(s): %s",
            len(self.devices_serial_numbers),
            self.devices_serial_numbers
        )

    async def refresh_devices(self) -> None:
        _LOGGER.info("Refreshing device list for %s", self.email)
        if not self._is_logged_in():
            _LOGGER.info("Token expired or missing, re-authenticating for device refresh")
            await self._login()
        await self._load_devices_serial_numbers()
        _LOGGER.info("Device refresh complete, %d device(s) found", len(self.devices_serial_numbers))

    def get_devices_serial_numbers(self) -> list[str]:
        return self.devices_serial_numbers

    async def get_device_snapshot(self, device_sn: str) -> dict:
        if not self._is_logged_in():
            _LOGGER.warning("Token expired before snapshot request for %s, re-authenticating", device_sn)
            await self._login()

        _LOGGER.debug("Fetching snapshot for device %s", device_sn)
        today_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": self.bearer_token,
            "content-type": "application/json",
        }
        payload = {
            "deviceSn": device_sn,
            "deviceType": "BP",
            "dateStr": today_date_str
        }

        async with self.session.post(self.API_URL_DEVICE_SNAPSHOT, headers=headers, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

            if "data" not in data:
                _LOGGER.error("Snapshot response missing 'data' field for %s: %s", device_sn, data)
                raise ValueError(f"Failed to get device snapshot: {data}")

            device_data = data["data"]
            if "productTypeEnum" not in device_data:
                _LOGGER.error("Snapshot response missing 'productTypeEnum' for %s: %s", device_sn, device_data)
                raise ValueError(f"Invalid device data: {device_data}")

            _LOGGER.info(
                "Snapshot received for %s (type=%s)",
                device_sn, device_data.get("productTypeEnum", "unknown")
            )
            return device_data

    # --- Private Methods ---

    def _is_logged_in(self) -> bool:
        if not self.bearer_token or not self.token_expiration:
            _LOGGER.debug("Not logged in: no token or expiration stored")
            return False
        now = datetime.now()
        if self.token_expiration <= now:
            _LOGGER.debug(
                "Token expired: expiration=%s, now=%s",
                self.token_expiration.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S")
            )
            return False
        return True

    def _read_token_file_sync(self):
        if not os.path.exists(self.JSON_FILE_PATH):
            return None
        try:
            with open(self.JSON_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_token_file_sync(self, data):
        os.makedirs(os.path.dirname(self.JSON_FILE_PATH) or ".", exist_ok=True)
        with open(self.JSON_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)

    async def _load_from_file(self) -> None:
        data = await asyncio.to_thread(self._read_token_file_sync)
        if not data:
            _LOGGER.info("No token file found at %s", self.JSON_FILE_PATH)
            return

        found = next(
            (item for item in data if item["email"] == self.email), None)
        if not found:
            _LOGGER.info("No saved token found for %s in token file", self.email)
            return

        self.bearer_token = found["bearer"]
        _LOGGER.info("Loaded bearer token from file for %s", self.email)

    async def _save_to_file(self) -> None:
        if not self.bearer_token or not self.token_expiration:
            return

        data = await asyncio.to_thread(self._read_token_file_sync) or []

        found = next(
            (item for item in data if item["email"] == self.email), None)
        exp_timestamp = int(self.token_expiration.timestamp() * 1000)

        if found and found.get("exp", 0) > int(datetime.now().timestamp() * 1000):
            _LOGGER.debug("Token file already up-to-date for %s", self.email)
            return
        elif found:
            found["bearer"] = self.bearer_token
            found["exp"] = exp_timestamp
            _LOGGER.info("Updated existing token in file for %s", self.email)
        else:
            new_entry = {
                "email": self.email,
                "bearer": self.bearer_token,
                "exp": exp_timestamp
            }
            data.append(new_entry)
            _LOGGER.info("Saved new token to file for %s", self.email)

        await asyncio.to_thread(self._write_token_file_sync, data)

    async def _load_devices_serial_numbers(self) -> None:
        _LOGGER.debug("Fetching device list from API")
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": self.bearer_token,
            "content-type": "application/json",
        }
        payload = {
            "pageNum": 1,
            "pageSize": 10,
            "deviceSn": "",
            "status": "",
            "sampleFlag": "",
            "oscFlag": ""
        }

        async with self.session.post(self.API_URL_DEVICE_LIST, headers=headers, json=payload) as response:
            response.raise_for_status()
            data = await response.json()
            data_list = data.get("data", {}).get("dataList", [])
            devices_sn = [device["deviceSn"] for device in data_list]
            _LOGGER.info(
                "Device list loaded: %d device(s) found — %s",
                len(devices_sn), devices_sn
            )
            self.devices_serial_numbers = devices_sn

    async def _login(self) -> None:
        _LOGGER.info("Logging in to Felicity Solar as %s", self.email)
        password_hash = await self._generate_password_hash(self.password)
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }
        payload = {
            "userName": self.email,
            "password": password_hash,
            "version": "1.0"
        }

        async with self.session.post(self.API_URL_USER_LOGIN, headers=headers, json=payload) as response:
            response.raise_for_status()
            data = await response.json()
            bearer = data.get("data", {}).get("token")

            if not bearer:
                _LOGGER.error("Login failed — no token in response: %s", data)
                raise ValueError("Token missing from login response.")

            clean_token = bearer.replace("Bearer_", "")
            try:
                decrypted_token = jwt.decode(
                    clean_token, options={"verify_signature": False})
            except Exception as e:
                _LOGGER.error("Failed to decode JWT token: %s", e)
                raise ValueError(f"Failed to decode token: {e}")

            self.token_expiration = datetime.fromtimestamp(
                decrypted_token["exp"])
            self.bearer_token = bearer
            _LOGGER.info(
                "Login successful for %s, token expires at %s",
                self.email,
                self.token_expiration.strftime("%Y-%m-%d %H:%M:%S")
            )
            await self._save_to_file()

    async def _generate_password_hash(self, password: str) -> str:
        public_key_str = await self._extract_public_key()
        key = RSA.import_key(public_key_str)
        cipher = PKCS1_v1_5.new(key)
        encrypted = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    async def _extract_public_key(self) -> str:
        _LOGGER.info("Extracting RSA public key from Felicity Solar login page")
        async with self.session.get(self.LOGIN_URL) as response:
            response.raise_for_status()
            combined_text = await response.text()

        _LOGGER.debug("Parsing login page HTML for JS bundle URLs")

        head_match = re.search(
            r"<head[^>]*>([\s\S]*?)<\/head>", combined_text, re.IGNORECASE)
        head_content = head_match.group(1) if head_match else ""

        script_src_regex = re.compile(
            r'(?:href|src)=["\']([^"\']*/index\.[^"\']*\.js)["\']', re.IGNORECASE)
        match = script_src_regex.search(head_content)
        script_urls = []

        if match:
            index_url = match.group(1)
            _LOGGER.info("Found main JS bundle: %s", index_url)
            try:
                absolute_index_url = urljoin(self.LOGIN_URL, index_url)
                async with self.session.get(absolute_index_url) as index_res:
                    if index_res.status == 200:
                        index_text = await index_res.text()
                        combined_text += "\n\n" + index_text
                        _LOGGER.debug("Main JS bundle fetched (%d bytes), searching for login route", len(index_text))

                        login_route_regex = re.compile(
                            r'path:\s*["\']/login["\'][\s\S]*?component:\s*\(\)\s*=>[\s\S]*?\[(.*?)\]')
                        login_match = login_route_regex.search(index_text)

                        if login_match:
                            asset_regex = re.compile(
                                r'["\']([^"\']*/index\.[^"\']*\.js)["\']')
                            script_urls.extend(
                                asset_regex.findall(login_match.group(1)))
                            _LOGGER.info("Found %d login-related JS bundle(s): %s", len(script_urls), script_urls)
                        else:
                            _LOGGER.warning("Login route pattern not found in main JS bundle")
            except Exception as err:
                _LOGGER.error(f"Failed to fetch main index script: {err}")

        _LOGGER.info("Fetching %d login JS bundle(s) to find public key", len(script_urls))
        for src in script_urls:
            absolute_url = urljoin(self.LOGIN_URL, src)
            try:
                async with self.session.get(absolute_url) as script_res:
                    if script_res.status == 200:
                        script_text = await script_res.text()
                        combined_text += "\n\n" + script_text
                        _LOGGER.debug("Fetched %s (%d bytes)", src, len(script_text))
            except Exception as err:
                _LOGGER.error("Failed to fetch script %s: %s", absolute_url, err)

        _LOGGER.debug("Searching for setPublicKey() in combined JS text")
        set_public_key_regex = re.compile(
            r"setPublicKey\s*\(\s*([a-zA-Z0-9_$]+)\s*\)")
        pk_match = set_public_key_regex.search(combined_text)

        if not pk_match:
            _LOGGER.error("Could not find setPublicKey() call in any JS bundle — the Felicity Solar website may have changed")
            raise ValueError("Could not find setPublicKey() call")

        var_name = pk_match.group(1)
        _LOGGER.debug("Found setPublicKey(%s), searching for its value assignment", var_name)
        escaped_var_name = re.escape(var_name)

        assignment_regex = re.compile(
            escaped_var_name + r"\s*=\s*(['\"`])(.*?)\1")
        matches = assignment_regex.findall(combined_text)

        if not matches:
            _LOGGER.error(
                "Could not find string assignment for variable '%s' — the Felicity Solar website may have changed", var_name
            )
            raise ValueError(
                f"Could not find the string assignment for the variable '{var_name}'.")

        # Find the longest matched string
        extracted_value = max([m[1] for m in matches], key=len)
        _LOGGER.info("RSA public key successfully extracted (%d chars)", len(extracted_value))

        return f"-----BEGIN PUBLIC KEY-----\n{extracted_value}\n-----END PUBLIC KEY-----"
