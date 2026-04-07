import ipaddress
import socket
import subprocess
import re

from scapy.all import ARP, Ether, srp, conf


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def get_subnet() -> str:
    ip = get_local_ip()
    return str(ipaddress.IPv4Network(f"{ip}/24", strict=False))


def get_gateway_ip() -> str | None:
    # Method 1: scapy routing table (most reliable)
    try:
        gw = conf.route.route("0.0.0.0")[2]
        if gw and gw != "0.0.0.0":
            return gw
    except Exception:
        pass

    # Method 2: route print
    try:
        out = subprocess.run(["route", "print", "0.0.0.0"],
                             capture_output=True, text=True).stdout
        m = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+([\d.]+)", out)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    # Method 3: ipconfig fallback
    try:
        out = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
        m = re.search(r"Default Gateway[^:]*:\s*([\d.]+)", out)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    return None


def get_mac(ip: str) -> str | None:
    result = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip),
                 timeout=2, verbose=0)[0]
    return result[0][1].hwsrc if result else None


def resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


def scan_network(subnet: str) -> list[dict]:
    """ARP-scan the subnet. Returns list of {ip, mac, hostname}."""
    result = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet),
        timeout=3, verbose=0,
    )[0]

    devices = []
    for _, pkt in result:
        devices.append({
            "ip":       pkt.psrc,
            "mac":      pkt.hwsrc,
            "hostname": resolve_hostname(pkt.psrc),
        })

    # Sort by last IP octet
    devices.sort(key=lambda d: int(d["ip"].split(".")[-1]))
    return devices
