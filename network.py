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
    # Method 1: Windows ARP cache (fast, no admin needed)
    try:
        out = subprocess.run(["arp", "-a", ip], capture_output=True, text=True).stdout
        m = re.search(r"([\da-fA-F]{2}[:-]){5}[\da-fA-F]{2}", out)
        if m:
            return m.group(0).replace("-", ":").lower()
    except Exception:
        pass

    # Method 2: Scapy ARP request
    try:
        result = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip),
                     timeout=2, verbose=0)[0]
        if result:
            return result[0][1].hwsrc
    except Exception:
        pass

    return None


def resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


def _scan_scapy(subnet: str) -> list[dict]:
    """ARP scan using Scapy (requires Npcap + admin)."""
    result = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet),
        timeout=3, verbose=0,
    )[0]
    return [
        {
            "ip":       pkt.psrc,
            "mac":      pkt.hwsrc,
            "hostname": resolve_hostname(pkt.psrc),
        }
        for _, pkt in result
    ]


def _scan_arp_cache() -> list[dict]:
    """
    Fallback: read devices already in the Windows ARP cache.
    Works without Scapy/admin — catches any device that recently
    communicated on the network.
    """
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
    devices = []
    for line in out.splitlines():
        # Lines look like:  192.168.0.5      be-22-28-ff-b1-2e     dynamic
        m = re.match(r"\s+([\d.]+)\s+([\da-fA-F]{2}[:-]){5}[\da-fA-F]{2}", line)
        if not m:
            continue
        parts = line.split()
        ip  = parts[0]
        mac = parts[1].replace("-", ":").lower()
        # Skip multicast/broadcast entries
        if ip.startswith("224.") or ip == "255.255.255.255":
            continue
        devices.append({
            "ip":       ip,
            "mac":      mac,
            "hostname": resolve_hostname(ip),
        })
    return devices


def scan_network(subnet: str) -> list[dict]:
    """
    Scan the subnet for devices.
    Tries Scapy ARP scan first (more complete), falls back to ARP cache.
    """
    devices = []

    try:
        devices = _scan_scapy(subnet)
        print(f"[scan] Scapy found {len(devices)} device(s)")
    except Exception as e:
        print(f"[scan] Scapy failed ({e}), falling back to ARP cache")

    if not devices:
        devices = _scan_arp_cache()
        print(f"[scan] ARP cache found {len(devices)} device(s)")

    # Deduplicate by IP
    seen = set()
    unique = []
    for d in devices:
        if d["ip"] not in seen:
            seen.add(d["ip"])
            unique.append(d)

    unique.sort(key=lambda d: int(d["ip"].split(".")[-1]))
    return unique
