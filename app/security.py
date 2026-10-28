import hashlib
import hmac
import os
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class Vault:
    """Encrypts stored API keys. The key file lives next to the database, so this protects
    against casually reading the database, not against someone who can read the whole data folder."""

    def __init__(self, data_dir):
        p = Path(data_dir) / "secret.key"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(Fernet.generate_key())
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        self.f = Fernet(p.read_bytes().strip())

    def enc(self, s: str) -> str:
        return self.f.encrypt(s.encode()).decode() if s else ""

    def dec(self, s: str) -> str:
        if not s:
            return ""
        try:
            return self.f.decrypt(s.encode()).decode()
        except InvalidToken:
            return ""


def _scrypt(pw: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    return salt.hex() + ":" + _scrypt(pw, salt).hex()


def check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(_scrypt(pw, bytes.fromhex(salt)).hex(), h)
    except Exception:
        return False


def sha(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()


class Throttle:
    """Slows down repeated wrong passwords from one address."""

    def __init__(self):
        self.f = {}

    def wait_time(self, ip) -> int:
        rec = self.f.get(ip)
        return max(0, int(rec[1] - time.time())) if rec else 0

    def fail(self, ip):
        n = self.f.get(ip, (0, 0))[0] + 1
        self.f[ip] = (n, time.time() + min(2 ** n, 300) if n >= 3 else 0)

    def ok(self, ip):
        self.f.pop(ip, None)
