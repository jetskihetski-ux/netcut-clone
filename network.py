import ipaddress
import socket
import subprocess
import threading
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
    """Read devices from Windows ARP cache (arp -a)."""
    out = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout

    # Match lines like:  192.168.0.105    a8-8f-d9-4a-58-23    dynamic
    pattern = re.compile(
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"   # IP
        r"\s+"
        r"([\da-fA-F]{2}-[\da-fA-F]{2}-[\da-fA-F]{2}"
        r"-[\da-fA-F]{2}-[\da-fA-F]{2}-[\da-fA-F]{2})"  # MAC xx-xx-xx-xx-xx-xx
        r"\s+dynamic"                               # only dynamic entries
    )

    devices = []
    for ip, mac in pattern.findall(out):
        if ip.startswith("224.") or ip.startswith("239.") or ip == "255.255.255.255":
            continue
        devices.append({
            "ip":       ip,
            "mac":      mac.replace("-", ":").lower(),
            "hostname": resolve_hostname(ip),
        })
    return devices


def ping_sweep(subnet: str) -> None:
    """
    Ping all 254 hosts in the subnet simultaneously.
    This wakes up idle devices (phones, laptops) and populates
    the Windows ARP cache so they appear in the scan.
    """
    prefix = subnet.rsplit(".", 1)[0]   # e.g. "192.168.0"
    threads = []

    def _ping(ip: str) -> None:
        subprocess.run(
            ["ping", "-n", "1", "-w", "300", ip],
            capture_output=True,
        )

    for i in range(1, 255):
        t = threading.Thread(target=_ping, args=(f"{prefix}.{i}",), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=1.5)


def _is_alive(ip: str) -> bool:
    """Returns True only if the device responds to a ping right now."""
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "500", ip],
        capture_output=True,
    )
    return result.returncode == 0


def scan_network(subnet: str, on_progress=None) -> list[dict]:
    """
    Full network scan:
      1. Ping sweep  — wakes idle devices, populates ARP cache
      2. Scapy ARP   — active ARP discovery
      3. ARP cache   — catches anything Scapy missed
      4. Verify alive — removes stale/offline entries from the list
    """
    merged: dict[str, dict] = {}

    if on_progress:
        on_progress("Pinging all devices…")
    ping_sweep(subnet)

    if on_progress:
        on_progress("Running ARP scan…")

    try:
        for d in _scan_scapy(subnet):
            merged[d["ip"]] = d
    except Exception as e:
        print(f"[scan] Scapy failed: {e}")

    for d in _scan_arp_cache():
        if d["ip"] not in merged:
            merged[d["ip"]] = d

    if on_progress:
        on_progress("Verifying devices are online…")

    # Verify each candidate in parallel — drop any that don't respond
    alive: dict[str, bool] = {}
    lock  = threading.Lock()

    def _check(ip: str) -> None:
        result = _is_alive(ip)
        with lock:
            alive[ip] = result

    threads = [threading.Thread(target=_check, args=(ip,), daemon=True)
               for ip in merged]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    online = {ip: d for ip, d in merged.items() if alive.get(ip)}
    print(f"[scan] Online: {len(online)} / {len(merged)} discovered")

    return sorted(online.values(), key=lambda d: int(d["ip"].split(".")[-1]))
