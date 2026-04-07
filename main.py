import threading
import customtkinter as ctk
from tkinter import messagebox

from network import get_subnet, get_gateway_ip, get_mac, scan_network, get_local_ip
from spoofer import ARPSpoofer
from vendor import get_device_info

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#6C63FF"
RED    = "#FF5252"
GREEN  = "#4CAF50"
BG     = "#1A1A2E"
CARD   = "#2D2D3F"
CARD2  = "#252537"
TEXT   = "#FFFFFF"
SUB    = "#888888"
BORDER = "#3D3D55"


class DeviceCard(ctk.CTkFrame):
    def __init__(self, parent, device: dict, blocked: bool, on_toggle, **kw):
        super().__init__(parent, corner_radius=14, fg_color=CARD, **kw)

        emoji, label = get_device_info(device["mac"], device["hostname"])

        # ── icon ──
        ctk.CTkLabel(self, text=emoji, font=ctk.CTkFont(size=30),
                     width=52).grid(row=0, column=0, rowspan=2,
                                    padx=(16, 8), pady=16, sticky="ns")

        # ── name + meta ──
        ctk.CTkLabel(self, text=label,
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT, anchor="w").grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=(14, 0))

        ctk.CTkLabel(self, text=f"{device['ip']}   ·   {device['mac']}",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUB, anchor="w").grid(
            row=1, column=1, sticky="w", padx=(0, 8), pady=(0, 14))

        # ── status badge ──
        status_txt   = "🔴  Blocked" if blocked else "🟢  Active"
        status_color = "#FF5252" if blocked else "#4CAF50"
        ctk.CTkLabel(self, text=status_txt,
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=status_color, width=90).grid(
            row=0, column=2, padx=(0, 8), pady=(14, 0), sticky="e")

        # ── toggle button ──
        btn_text  = "Unblock" if blocked else "✂  Block"
        btn_color = "#2E7D32" if blocked else RED
        btn_hover = "#1B5E20" if blocked else "#C62828"
        ctk.CTkButton(self, text=btn_text,
                      fg_color=btn_color, hover_color=btn_hover,
                      font=ctk.CTkFont("Segoe UI", 11, "bold"),
                      width=88, height=30, corner_radius=8,
                      command=on_toggle).grid(
            row=1, column=2, padx=(0, 16), pady=(0, 14), sticky="e")

        self.columnconfigure(1, weight=1)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NetCut")
        self.geometry("580x660")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self._spoofer      = ARPSpoofer()
        self._devices:     list[dict] = []
        self._gateway_ip:  str | None = None
        self._gateway_mac: str | None = None
        self._card_widgets: list[DeviceCard] = []

        self._build()
        self._init_network()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(24, 12))

        ctk.CTkLabel(hdr, text="NetCut",
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=TEXT).pack(side="left")

        self._scan_btn = ctk.CTkButton(
            hdr, text="⟳   Scan",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color="#5550CC",
            width=110, height=38, corner_radius=10,
            command=self._start_scan,
        )
        self._scan_btn.pack(side="right")

        # Info bar
        info = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        info.pack(fill="x", padx=24, pady=(0, 16))

        gw_col = ctk.CTkFrame(info, fg_color="transparent")
        gw_col.pack(side="left", padx=20, pady=12)
        ctk.CTkLabel(gw_col, text="GATEWAY",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=SUB).pack(anchor="w")
        self._gw_label = ctk.CTkLabel(gw_col, text="Detecting…",
                                       font=ctk.CTkFont("Segoe UI", 13, "bold"),
                                       text_color=TEXT)
        self._gw_label.pack(anchor="w")

        ip_col = ctk.CTkFrame(info, fg_color="transparent")
        ip_col.pack(side="right", padx=20, pady=12)
        ctk.CTkLabel(ip_col, text="YOUR IP",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=SUB).pack(anchor="e")
        ctk.CTkLabel(ip_col, text=get_local_ip(),
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=TEXT).pack(anchor="e")

        # Section label
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(row, text="Connected Devices",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(row, text="Unblock All",
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color="transparent", hover_color=CARD,
                      text_color=SUB, width=88, height=28,
                      command=self._unblock_all).pack(side="right")

        # Scrollable device list
        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             scrollbar_button_color=CARD2,
                                             scrollbar_button_hover_color=BORDER)
        self._list.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        self._empty_lbl = ctk.CTkLabel(
            self._list,
            text="No devices found\nClick  ⟳ Scan  to discover devices on your network",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=SUB,
        )
        self._empty_lbl.pack(pady=60)

        # Status bar
        bar = ctk.CTkFrame(self, fg_color=CARD2, corner_radius=0, height=34)
        bar.pack(fill="x", side="bottom")
        self._status_lbl = ctk.CTkLabel(bar, text="Ready",
                                         font=ctk.CTkFont("Segoe UI", 10),
                                         text_color=SUB)
        self._status_lbl.pack(side="left", padx=16, pady=7)

    # ── network init ──────────────────────────────────────────────────────────

    def _init_network(self):
        def _worker():
            ip  = get_gateway_ip()
            self.after(0, lambda: self._on_gw_ip(ip))
            mac = get_mac(ip) if ip else None
            self.after(0, lambda: self._on_gw_mac(mac))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_gw_ip(self, ip: str | None):
        self._gateway_ip = ip
        self._gw_label.configure(text=ip or "Not found")
        self._status("Gateway found — resolving MAC…" if ip else
                     "Gateway not found. Are you on WiFi?")

    def _on_gw_mac(self, mac: str | None):
        self._gateway_mac = mac
        ip = self._gateway_ip or "?"
        if mac:
            self._gw_label.configure(text=f"{ip}  ({mac})")
            self._status("Ready — click Scan to discover devices")
        else:
            self._gw_label.configure(text=f"{ip}  (MAC pending…)")
            self._status("Gateway MAC not resolved yet — scan will try again")

    # ── scan ──────────────────────────────────────────────────────────────────

    def _start_scan(self):
        if not self._gateway_ip:
            messagebox.showwarning("NetCut", "Gateway not detected yet.")
            return
        self._scan_btn.configure(state="disabled", text="Scanning…")
        self._status("Scanning network…")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        own_ip  = get_local_ip()
        subnet  = get_subnet()
        devices = scan_network(subnet)

        # If gateway MAC is still missing, grab it now from scan results
        if not self._gateway_mac and self._gateway_ip:
            for d in devices:
                if d["ip"] == self._gateway_ip:
                    self._gateway_mac = d["mac"]
                    self._spoofer._iface  # touch to keep alive
                    break
            if not self._gateway_mac:
                self._gateway_mac = get_mac(self._gateway_ip)

        # Exclude self and gateway from the device list
        visible = [d for d in devices
                   if d["ip"] != own_ip and d["ip"] != self._gateway_ip]

        self.after(0, lambda: self._on_scan_done(visible))

    def _on_scan_done(self, devices: list[dict]):
        self._devices = devices
        self._scan_btn.configure(state="normal", text="⟳   Scan")
        self._rebuild_cards()
        gw_mac = self._gateway_mac or "not found"
        self._gw_label.configure(text=f"{self._gateway_ip}  ({gw_mac})")
        self._status(f"Found {len(devices)} device(s)" +
                     ("  —  gateway MAC missing, blocking may not work"
                      if not self._gateway_mac else ""))

    # ── device cards ──────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        for w in self._card_widgets:
            w.destroy()
        self._card_widgets.clear()

        if not self._devices:
            self._empty_lbl.pack(pady=60)
            return

        self._empty_lbl.pack_forget()
        for dev in self._devices:
            blocked = self._spoofer.is_blocked(dev["ip"])
            card = DeviceCard(
                self._list, dev, blocked,
                on_toggle=lambda d=dev: self._toggle(d),
            )
            card.pack(fill="x", pady=(0, 10))
            self._card_widgets.append(card)

    # ── block / unblock ───────────────────────────────────────────────────────

    def _toggle(self, dev: dict):
        if not self._gateway_ip or not self._gateway_mac:
            messagebox.showerror(
                "NetCut",
                "Gateway MAC address unknown — cannot block.\n\n"
                "Make sure you are running as Administrator and\n"
                "Npcap is installed, then scan again."
            )
            return

        if self._spoofer.is_blocked(dev["ip"]):
            self._spoofer.unblock(dev["ip"], dev["mac"],
                                   self._gateway_ip, self._gateway_mac)
            self._status(f"Unblocked {dev['ip']}")
        else:
            self._spoofer.block(dev["ip"], dev["mac"],
                                 self._gateway_ip, self._gateway_mac)
            self._status(f"Blocking {dev['ip']}…")

        self._rebuild_cards()

    def _unblock_all(self):
        self._spoofer.unblock_all(self._devices,
                                   self._gateway_ip or "",
                                   self._gateway_mac or "")
        self._rebuild_cards()
        self._status("All devices unblocked")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_lbl.configure(text=f"  {msg}")

    def on_close(self):
        self._unblock_all()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
