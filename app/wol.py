import re
import socket

MAC_RE = re.compile(r"^([0-9a-fA-F]{2}[:-]?){5}[0-9a-fA-F]{2}$")


def clean_mac(mac: str) -> str:
    mac = (mac or "").strip()
    if not MAC_RE.match(mac):
        raise ValueError("MAC address should look like AA:BB:CC:DD:EE:FF")
    return re.sub(r"[^0-9a-fA-F]", "", mac).upper()


def pretty(mac: str) -> str:
    h = clean_mac(mac)
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def send(mac: str, broadcast: str = "") -> None:
    """Sends a Wake-on-LAN magic packet. Works from a PC, or from a container using host networking."""
    packet = b"\xff" * 6 + bytes.fromhex(clean_mac(mac)) * 16
    target = (broadcast or "").strip() or "255.255.255.255"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(packet, (target, port))
