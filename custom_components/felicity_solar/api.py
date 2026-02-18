import logging
import re
import json
import base64
from datetime import datetime
from enum import Enum
import jwt
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


class DeviceTypeEnum(str, Enum):
    LITHIUM_BATTERY_PACK = "LITHIUM_BATTERY_PACK"
    HIGH_FREQUENCY_INVERTER = "HIGH_FREQUENCY_INVERTER"


class FelicitySolarAPI:
    LOGIN_URL = "https://shine.felicitysolar.com/login"
    API_URL_DEVICE_LIST = "https://shine-api.felicitysolar.com/device/list_device_all_type"
    API_URL_DEVICE_SNAPSHOT = "https://shine-api.felicitysolar.com/device/get_device_snapshot"
    API_URL_USER_LOGIN = "https://shine-api.felicitysolar.com/userlogin"

    def __init__(self, email: str, password: str, session: ClientSession):
        self.email = email
        self.password = password
        self.session = session

        self.bearer_token: str | None = None
        self.token_expiration: datetime | None = None
        self.devices_serial_numbers: list[str] = []

    async def initialize(self) -> None:
        if not self._is_logged_in():
            await self._login()
        await self._load_devices_serial_numbers()

    async def refresh_devices(self) -> None:
        if not self._is_logged_in():
            await self._login()
        await self._load_devices_serial_numbers()

    def get_devices_serial_numbers(self) -> list[str]:
        return self.devices_serial_numbers

    async def get_device_snapshot(self, device_sn: str) -> dict:
        if not self._is_logged_in():
            await self._login()

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
                raise ValueError(f"Failed to get device snapshot: {data}")

            device_data = data["data"]
            if "productTypeEnum" not in device_data:
                raise ValueError(f"Invalid device data: {device_data}")

            return device_data

    # --- Private Methods ---

    def _is_logged_in(self) -> bool:
        if not self.bearer_token or not self.token_expiration:
            return False
        return self.token_expiration > datetime.now()

    async def _load_devices_serial_numbers(self) -> None:
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
            devices_sn = [device["deviceSn"]
                          for device in data.get("data", {}).get("dataList", [])]
            self.devices_serial_numbers = devices_sn

    async def _login(self) -> None:
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
                raise ValueError("Token missing from login response.")

            # Remove 'Bearer_' prefix if it exists to decode
            clean_token = bearer.replace("Bearer_", "")
            try:
                decrypted_token = jwt.decode(
                    clean_token, options={"verify_signature": False})
            except Exception as e:
                raise ValueError(f"Failed to decode token: {e}")

            self.token_expiration = datetime.fromtimestamp(
                decrypted_token["exp"])
            self.bearer_token = bearer

    async def _generate_password_hash(self, password: str) -> str:
        public_key_str = await self._extract_public_key()
        key = RSA.import_key(public_key_str)
        cipher = PKCS1_v1_5.new(key)
        encrypted = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    async def _extract_public_key(self) -> str:
        _LOGGER.debug(f"Fetching main page: {self.LOGIN_URL}")
        async with self.session.get(self.LOGIN_URL) as response:
            response.raise_for_status()
            combined_text = await response.text()

        head_match = re.search(
            r"<head[^>]*>([\s\S]*?)<\/head>", combined_text, re.IGNORECASE)
        head_content = head_match.group(1) if head_match else ""

        script_src_regex = re.compile(
            r'(?:href|src)=["\']([^"\']*/index\.[^"\']*\.js)["\']', re.IGNORECASE)
        match = script_src_regex.search(head_content)
        script_urls = []

        if match:
            index_url = match.group(1)
            try:
                absolute_index_url = response.url.join(index_url)
                async with self.session.get(absolute_index_url) as index_res:
                    if index_res.status == 200:
                        index_text = await index_res.text()
                        combined_text += "\n\n" + index_text

                        login_route_regex = re.compile(
                            r'path:\s*["\']/login["\'][\s\S]*?component:\s*\(\)\s*=>[\s\S]*?\[(.*?)\]')
                        login_match = login_route_regex.search(index_text)

                        if login_match:
                            asset_regex = re.compile(
                                r'["\']([^"\']*/index\.[^"\']*\.js)["\']')
                            script_urls.extend(
                                asset_regex.findall(login_match.group(1)))
            except Exception as err:
                _LOGGER.error(f"Failed to fetch main index script: {err}")

        for src in script_urls:
            try:
                absolute_url = response.url.join(src)
                async with self.session.get(absolute_url) as script_res:
                    if script_res.status == 200:
                        combined_text += "\n\n" + await script_res.text()
            except Exception as err:
                _LOGGER.error(f"Failed to fetch script: {
                              absolute_url}, Error: {err}")

        set_public_key_regex = re.compile(
            r"setPublicKey\s*\(\s*([a-zA-Z0-9_$]+)\s*\)")
        pk_match = set_public_key_regex.search(combined_text)

        if not pk_match:
            raise ValueError("Could not find setPublicKey() call")

        var_name = pk_match.group(1)
        escaped_var_name = re.escape(var_name)

        assignment_regex = re.compile(
            escaped_var_name + r"\s*=\s*(['\"`])(.*?)\1")
        matches = assignment_regex.findall(combined_text)

        if not matches:
            raise ValueError(
                f"Could not find the string assignment for the variable '{var_name}'.")

        # Find the longest matched string
        extracted_value = max([m[1] for m in matches], key=len)

        return f"-----BEGIN PUBLIC KEY-----\n{extracted_value}\n-----END PUBLIC KEY-----"
