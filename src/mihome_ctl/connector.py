"""Xiaomi official cloud connector (password-free QR login + RC4-encrypted API).

This file is a **trimmed derivative** of ``token_extractor.py`` from
PiotrMachowski/Xiaomi-cloud-tokens-extractor (MIT, see ``THIRD_PARTY_LICENSES/``):
it keeps only the QR login connector and its encrypted API calls, dropping the
upstream argparse / password login / 2FA / captcha / CLI shell.

Public interface preserved here (session caching and API calls depend on these
names, do not rename):
    attributes ``userId`` / ``_ssecurity`` / ``_serviceToken``
    methods ``login()`` / ``login_step_2()`` (may be overridden for a terminal QR)
            ``get_homes`` / ``get_dev_cnt`` / ``get_devices`` / ``get_beaconkey``
            ``get_api_url`` / ``execute_api_call_encrypted``

Upstream re-sync: diff against the two classes ``XiaomiCloudConnector`` /
``QrCodeXiaomiCloudConnector`` in token_extractor.py.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import random
import socket
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

try:
    from Crypto.Cipher import ARC4
except ModuleNotFoundError:  # pragma: no cover - depends on which crypto pkg is present
    from Cryptodome.Cipher import ARC4

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
except Exception:  # pragma: no cover - colorama optional at runtime

    class _Dummy:
        def __getattr__(self, _name: str) -> str:
            return ""

    Fore = Style = _Dummy()  # type: ignore[assignment]

_LOGGER = logging.getLogger("mihome_ctl.connector")


def _msg(value: str = "") -> None:
    print(value)


class XiaomiCloudConnector(ABC):
    """Encrypted API base (RC4-signed). The login method is implemented by subclasses."""

    def __init__(self) -> None:
        self._agent = self.generate_agent()
        self._device_id = self.generate_device_id()
        self._session = requests.session()
        self._ssecurity: str | None = None
        self.userId: int | str | None = None
        self._serviceToken: str | None = None

    @abstractmethod
    def login(self) -> bool: ...

    def get_homes(self, country: str):
        url = self.get_api_url(country) + "/v2/homeroom/gethome"
        params = {
            "data": '{"fg": true, "fetch_share": true, "fetch_share_dev": true, "limit": 300, "app_ver": 7}'
        }
        return self.execute_api_call_encrypted(url, params)

    def get_devices(self, country: str, home_id, owner_id):
        url = self.get_api_url(country) + "/v2/home/home_device_list"
        params = {
            "data": '{"home_owner": '
            + str(owner_id)
            + ',"home_id": '
            + str(home_id)
            + ',  "limit": 200,  "get_split_device": true, "support_smart_home": true}'
        }
        return self.execute_api_call_encrypted(url, params)

    def get_dev_cnt(self, country: str):
        url = self.get_api_url(country) + "/v2/user/get_device_cnt"
        params = {"data": '{ "fetch_own": true, "fetch_share": true}'}
        return self.execute_api_call_encrypted(url, params)

    def get_beaconkey(self, country: str, did: str):
        url = self.get_api_url(country) + "/v2/device/blt_get_beaconkey"
        params = {"data": '{"did":"' + did + '","pdid":1}'}
        return self.execute_api_call_encrypted(url, params)

    def execute_api_call_encrypted(self, url: str, params: dict):
        headers = {
            "Accept-Encoding": "identity",
            "User-Agent": self._agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
            "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4",
        }
        cookies = {
            "userId": str(self.userId),
            "yetAnotherServiceToken": str(self._serviceToken),
            "serviceToken": str(self._serviceToken),
            "locale": "en_GB",
            "timezone": "GMT+02:00",
            "is_daylight": "1",
            "dst_offset": "3600000",
            "channel": "MI_APP_STORE",
        }
        millis = round(time.time() * 1000)
        nonce = self.generate_nonce(millis)
        signed_nonce = self.signed_nonce(nonce)
        fields = self.generate_enc_params(url, "POST", signed_nonce, nonce, params, self._ssecurity)
        response = self._session.post(url, headers=headers, cookies=cookies, params=fields)
        if response.status_code == 200:
            decoded = self.decrypt_rc4(self.signed_nonce(fields["_nonce"]), response.text)
            return json.loads(decoded)
        return None

    @staticmethod
    def get_api_url(country: str) -> str:
        return "https://" + ("" if country == "cn" else (country + ".")) + "api.io.mi.com/app"

    def signed_nonce(self, nonce: str) -> str:
        hash_object = hashlib.sha256(base64.b64decode(self._ssecurity) + base64.b64decode(nonce))
        return base64.b64encode(hash_object.digest()).decode("utf-8")

    @staticmethod
    def generate_nonce(millis: int) -> str:
        nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder="big")
        return base64.b64encode(nonce_bytes).decode()

    @staticmethod
    def generate_agent() -> str:
        agent_id = "".join(chr(random.randint(65, 69)) for _ in range(13))
        random_text = "".join(chr(random.randint(97, 122)) for _ in range(18))
        return f"{random_text}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"

    @staticmethod
    def generate_device_id() -> str:
        return "".join(chr(random.randint(97, 122)) for _ in range(6))

    @staticmethod
    def generate_enc_signature(url: str, method: str, signed_nonce: str, params: dict) -> str:
        signature_params = [str(method).upper(), url.split("com")[1].replace("/app/", "/")]
        for k, v in params.items():
            signature_params.append(f"{k}={v}")
        signature_params.append(signed_nonce)
        signature_string = "&".join(signature_params)
        return base64.b64encode(hashlib.sha1(signature_string.encode("utf-8")).digest()).decode()

    @staticmethod
    def generate_enc_params(
        url: str, method: str, signed_nonce: str, nonce: str, params: dict, ssecurity
    ) -> dict:
        params["rc4_hash__"] = XiaomiCloudConnector.generate_enc_signature(
            url, method, signed_nonce, params
        )
        for k, v in params.items():
            params[k] = XiaomiCloudConnector.encrypt_rc4(signed_nonce, v)
        params.update(
            {
                "signature": XiaomiCloudConnector.generate_enc_signature(
                    url, method, signed_nonce, params
                ),
                "ssecurity": ssecurity,
                "_nonce": nonce,
            }
        )
        return params

    @staticmethod
    def to_json(response_text: str):
        return json.loads(response_text.replace("&&&START&&&", ""))

    @staticmethod
    def encrypt_rc4(password: str, payload: str) -> str:
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return base64.b64encode(r.encrypt(payload.encode())).decode()

    @staticmethod
    def decrypt_rc4(password: str, payload: str) -> bytes:
        r = ARC4.new(base64.b64decode(password))
        r.encrypt(bytes(1024))
        return r.encrypt(base64.b64decode(payload))


class QrCodeXiaomiCloudConnector(XiaomiCloudConnector):
    """Password-free QR login: scan the code in a browser/terminal → long-polling to exchange for a serviceToken."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        super().__init__()
        self._host = host
        self._cUserId: str | None = None
        self._pass_token: str | None = None
        self._location: str | None = None
        self._qr_image_url: str | None = None
        self._login_url: str | None = None
        self._long_polling_url: str | None = None
        self._timeout: int = 0

    def login(self) -> bool:
        if not self.login_step_1():
            _msg(f"{Fore.RED}Unable to get login message.")
            return False
        if not self.login_step_2():
            _msg(f"{Fore.RED}Unable to get login QR Image.")
            return False
        if not self.login_step_3():
            _msg(f"{Fore.RED}Unable to login.")
            return False
        if not self.login_step_4():
            _msg(f"{Fore.RED}Unable to get service token.")
            return False
        return True

    def login_step_1(self) -> bool:
        url = "https://account.xiaomi.com/longPolling/loginUrl"
        data = {
            "_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false",
            "sid": "xiaomiio",
            "serviceParam": "",
            "_locale": "en_GB",
            "_dc": str(int(time.time() * 1000)),
        }
        response = self._session.get(url, params=data)
        if response.status_code == 200:
            response_data = self.to_json(response.text)
            if "qr" in response_data:
                self._qr_image_url = response_data["qr"]
                self._login_url = response_data["loginUrl"]
                self._long_polling_url = response_data["lp"]
                self._timeout = response_data["timeout"]
                return True
        return False

    def login_step_2(self) -> bool:
        response = self._session.get(self._qr_image_url)
        if response is not None and response.status_code == 200:
            _msg(f"{Fore.BLUE}Please scan the following QR code to log in.")
            present_image_image(
                response.content,
                message_url=f"QR code URL: {Fore.BLUE}http://{self._host}:31415",
                message_file_saved="QR code image saved at: {}",
                message_manually_open_file="Please open {} and scan the QR code.",
            )
            _msg()
            _msg(f"{Fore.BLUE}Alternatively you can visit the following URL:")
            _msg(f"{Fore.BLUE}  {self._login_url}")
            _msg()
            return True
        _LOGGER.error("login_step_2 failed: HTTP %s", getattr(response, "status_code", "?"))
        return False

    def login_step_3(self) -> bool:
        url = self._long_polling_url
        start_time = time.time()
        response = None
        while True:
            try:
                response = self._session.get(url, timeout=10)
            except requests.exceptions.Timeout:
                if time.time() - start_time > self._timeout:
                    break
                continue
            except requests.exceptions.RequestException as e:
                _LOGGER.error("Long polling error: %s", e)
                break
            if response.status_code == 200:
                break
        if response is None or response.status_code != 200:
            return False
        response_data = self.to_json(response.text)
        self.userId = response_data["userId"]
        self._ssecurity = response_data["ssecurity"]
        self._cUserId = response_data["cUserId"]
        self._pass_token = response_data["passToken"]
        self._location = response_data["location"]
        return True

    def login_step_4(self) -> bool:
        if not (location := self._location):
            return False
        response = self._session.get(
            location, headers={"content-type": "application/x-www-form-urlencoded"}
        )
        if response.status_code != 200:
            return False
        self._serviceToken = response.cookies["serviceToken"]
        return True


def start_image_server(image: bytes) -> None:
    class ImgHttpHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(image)

        def log_message(self, msg, *args) -> None:  # noqa: A002 - stdlib signature
            _LOGGER.debug(msg, *args)

    httpd = HTTPServer(("", 31415), ImgHttpHandler)
    _LOGGER.debug("QR image server on %s (%s)", httpd.server_address, socket.gethostname())
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()


def present_image_image(
    image_content: bytes,
    message_url: str,
    message_file_saved: str,
    message_manually_open_file: str,
) -> None:
    """Serve the QR image via a local http server; on failure, save a temp file and try to open the image."""
    try:
        start_image_server(image_content)
        _msg(message_url)
    except Exception as e1:  # pragma: no cover - fallback path
        _LOGGER.debug("image server failed: %s", e1)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_content)
            tmp_path = tmp.name
        _msg(message_file_saved.format(tmp_path))
        try:
            from PIL import Image

            Image.open(tmp_path).show()
        except Exception as e2:
            _LOGGER.debug("PIL show failed: %s", e2)
            _msg(message_manually_open_file.format(tmp_path))
