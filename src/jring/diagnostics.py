import hashlib
import secrets


class Redactor:
    def __init__(self, salt: bytes | None = None):
        self._salt = salt or secrets.token_bytes(32)

    def address(self, address: str) -> str:
        digest = hashlib.sha256(self._salt + address.lower().encode("ascii")).hexdigest()[:10]
        return f"device-{digest}"
