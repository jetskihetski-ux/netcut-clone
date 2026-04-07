import threading
import customtkinter as ctk
from tkinter import messagebox

from network import get_subnet, get_gateway_ip, get_mac, scan_network, get_local_ip
from spoofer import ARPSpoofer
from vendor import get_device_info
import names as namestore

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG     = "#1A1A2E"
CARD   = "#2D2D3F"
CARD2  = "#252537"
ACCENT = "#6C63FF"
RED    = "#EF5350"
ORANGE = "#FF9800"
YELLOW = "#FFC107"
GREEN  = "#4CAF50"
TEXT   = "#FFFFFF"
SUB    = "#888888"
BORDER = "#3D3D55"

MODE_COLORS = {
    "normal": (CARD2,   TEXT),
    "lag":    (ORANGE,  "#111"),
    "limit":  (YELLOW,  "#111"),
    "block":  (RED,     TEXT),
}

MODE_LABELS = {
    "normal": "● Normal",
    "lag":    "⚡ Lagging",
    "limit":  "📉 Limited",
    "block":  "✂ Blocked",
}


class DeviceCard(ctk.CTkFrame):
    def __init__(self, parent, device: dict, spoofer: ARPSpoofer,
                 get_gateway, on_rename, **kw):
        super().__init__(parent, corner_radius=14, fg_color=CARD, **kw)

        self._dev         = device
        self._spoofer     = spoofer
        self._get_gateway = get_gateway
        self._on_rename   = on_rename

        emoji, vendor_label = get_device_info(device["mac"], device["hostname"])
        current_mode = spoofer.get_mode(device["ip"])

        # Best display name: custom > hostname > vendor label
        custom   = namestore.get(device["mac"])
        hostname = device.get("hostname", "")
        if custom:
            display_name = custom
            sub_name     = vendor_label
        elif hostname:
            display_name = hostname
            sub_name     = vendor_label
        else:
            display_name = vendor_label
            sub_name     = ""

        # ── top row: icon / name / status ────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))

        ctk.CTkLabel(top, text=emoji,
                     font=ctk.CTkFont(size=28), width=40).pack(side="left")

        name_col = ctk.CTkFrame(top, fg_color="transparent")
        name_col.pack(side="left", padx=10, fill="x", expand=True)

        # Device name row with rename button
        name_row = ctk.CTkFrame(name_col, fg_color="transparent")
        name_row.pack(anchor="w", fill="x")
        ctk.CTkLabel(name_row, text=display_name,
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkButton(name_row, text="✏", width=24, height=22,
                      fg_color="transparent", hover_color=BORDER,
                      text_color=SUB,
                      font=ctk.CTkFont(size=12),
                      command=lambda: on_rename(device)).pack(side="left", padx=4)

        # Sub-info: vendor + IP + MAC
        sub_parts = [p for p in [sub_name, device["ip"], device["mac"]] if p]
        ctk.CTkLabel(name_col, text="   ·   ".join(sub_parts),
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUB, anchor="w").pack(anchor="w")

        bg, fg = MODE_COLORS[current_mode]
        self._status_lbl = ctk.CTkLabel(
            top, text=MODE_LABELS[current_mode],
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            fg_color=bg, text_color=fg,
            corner_radius=8, width=96, height=28,
        )
        self._status_lbl.pack(side="right")

        # ── mode buttons ──────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(4, 0))

        modes = [("Normal", "normal"), ("⚡ Lag", "lag"),
                 ("📉 Limit", "limit"), ("✂ Block", "block")]

        for lbl, mode in modes:
            active   = current_mode == mode
            fg_color = _mode_btn_color(mode) if active else CARD2
            ctk.CTkButton(
                btn_row, text=lbl, width=0,
                font=ctk.CTkFont("Segoe UI", 11, "bold" if active else "normal"),
                fg_color=fg_color,
                hover_color=_mode_btn_color(mode),
                text_color=TEXT if mode in ("block", "normal") else "#111",
                height=30, corner_radius=8,
                command=lambda m=mode: self._set_mode(m),
            ).pack(side="left", expand=True, fill="x", padx=3)

        # ── intensity slider (hidden when Normal/Block) ───────────────────────
        self._slider_frame = ctk.CTkFrame(self, fg_color="transparent")

        ctk.CTkLabel(self._slider_frame, text="Intensity",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=SUB).pack(side="left", padx=(14, 6))

        self._slider = ctk.CTkSlider(
            self._slider_frame,
            from_=10, to=100, number_of_steps=18,
            button_color=ACCENT, progress_color=ACCENT,
            width=200,
        )
        self._slider.set(60)
        self._slider.pack(side="left")

        self._intensity_lbl = ctk.CTkLabel(
            self._slider_frame, text="60%",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=SUB, width=36,
        )
        self._intensity_lbl.pack(side="left", padx=6)
        self._slider.configure(command=self._on_slider)

        # spacer
        ctk.CTkFrame(self, fg_color="transparent", height=10).pack()

        if current_mode in ("lag", "limit"):
            self._slider_frame.pack(fill="x", pady=(2, 8))

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        gw_ip, gw_mac = self._get_gateway()
        if not gw_ip or not gw_mac:
            messagebox.showerror(
                "NetCut",
                "Gateway MAC not resolved.\nRun as Administrator and scan again.",
            )
            return

        intensity = int(self._slider.get())
        ip, mac = self._dev["ip"], self._dev["mac"]

        if mode == "normal":
            self._spoofer.remove(ip, mac, gw_ip, gw_mac)
        else:
            self._spoofer.apply(ip, mac, gw_ip, gw_mac,
                                mode=mode, intensity=intensity)

        # Update status badge
        bg, fg = MODE_COLORS[mode]
        self._status_lbl.configure(text=MODE_LABELS[mode],
                                    fg_color=bg, text_color=fg)

        # Show/hide slider
        if mode in ("lag", "limit"):
            self._slider_frame.pack(fill="x", pady=(2, 8))
        else:
            self._slider_frame.pack_forget()

    def _on_slider(self, value: float) -> None:
        pct = int(value)
        self._intensity_lbl.configure(text=f"{pct}%")
        # Live-update if already active
        mode = self._spoofer.get_mode(self._dev["ip"])
        if mode in ("lag", "limit"):
            gw_ip, gw_mac = self._get_gateway()
            if gw_ip and gw_mac:
                self._spoofer.apply(self._dev["ip"], self._dev["mac"],
                                    gw_ip, gw_mac,
                                    mode=mode, intensity=pct)


def _mode_btn_color(mode: str) -> str:
    return {
        "normal": CARD2,
        "lag":    ORANGE,
        "limit":  YELLOW,
        "block":  RED,
    }[mode]


# ── Main window ───────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NetCut")
        self.geometry("600x700")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self._spoofer      = ARPSpoofer()
        self._devices:     list[dict] = []
        self._gateway_ip:  str | None = None
        self._gateway_mac: str | None = None
        self._cards:       list      = []

        self._build()
        self._init_network()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(24, 12))
        ctk.CTkLabel(hdr, text="NetCut",
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=TEXT).pack(side="left")
        self._scan_btn = ctk.CTkButton(
            hdr, text="⟳  Scan",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color="#5550CC",
            width=110, height=38, corner_radius=10,
            command=self._start_scan,
        )
        self._scan_btn.pack(side="right")

        # Info bar
        info = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        info.pack(fill="x", padx=24, pady=(0, 16))

        gw = ctk.CTkFrame(info, fg_color="transparent")
        gw.pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(gw, text="GATEWAY",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=SUB).pack(anchor="w")
        self._gw_lbl = ctk.CTkLabel(gw, text="Detecting…",
                                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                                     text_color=TEXT)
        self._gw_lbl.pack(anchor="w")

        own = ctk.CTkFrame(info, fg_color="transparent")
        own.pack(side="right", padx=20, pady=10)
        ctk.CTkLabel(own, text="YOUR IP",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=SUB).pack(anchor="e")
        ctk.CTkLabel(own, text=get_local_ip(),
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=TEXT).pack(anchor="e")

        # Section row
        sec = ctk.CTkFrame(self, fg_color="transparent")
        sec.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(sec, text="Devices",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(sec, text="Restore All",
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color="transparent", hover_color=CARD,
                      text_color=SUB, width=88, height=28,
                      command=self._restore_all).pack(side="right")

        # Device list
        self._list = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=CARD2,
            scrollbar_button_hover_color=BORDER,
        )
        self._list.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        self._empty = ctk.CTkLabel(
            self._list,
            text="No devices found\nClick  ⟳ Scan  to discover devices",
            font=ctk.CTkFont("Segoe UI", 13), text_color=SUB,
        )
        self._empty.pack(pady=60)

        # Status bar
        bar = ctk.CTkFrame(self, fg_color=CARD2, corner_radius=0, height=34)
        bar.pack(fill="x", side="bottom")
        self._status_lbl = ctk.CTkLabel(bar, text="Ready",
                                         font=ctk.CTkFont("Segoe UI", 10),
                                         text_color=SUB)
        self._status_lbl.pack(side="left", padx=16, pady=7)

    # ── network ───────────────────────────────────────────────────────────────

    def _init_network(self):
        def _w():
            ip  = get_gateway_ip()
            self.after(0, lambda: self._on_gw_ip(ip))
            mac = get_mac(ip) if ip else None
            self.after(0, lambda: self._on_gw_mac(mac))
        threading.Thread(target=_w, daemon=True).start()

    def _on_gw_ip(self, ip):
        self._gateway_ip = ip
        self._gw_lbl.configure(text=ip or "Not found")

    def _on_gw_mac(self, mac):
        self._gateway_mac = mac
        ip = self._gateway_ip or "?"
        self._gw_lbl.configure(
            text=f"{ip}  ({mac})" if mac else f"{ip}  (MAC pending)"
        )
        self._status("Ready — click Scan")

    def _start_scan(self):
        if not self._gateway_ip:
            messagebox.showwarning("NetCut", "Gateway not detected yet.")
            return
        self._scan_btn.configure(state="disabled", text="Scanning…")
        self._status("Scanning network…")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        own  = get_local_ip()
        devs = scan_network(
            get_subnet(),
            on_progress=lambda msg: self.after(0, lambda m=msg: self._status(m)),
        )

        if not self._gateway_mac and self._gateway_ip:
            for d in devs:
                if d["ip"] == self._gateway_ip:
                    self._gateway_mac = d["mac"]
                    break
            if not self._gateway_mac:
                self._gateway_mac = get_mac(self._gateway_ip)

        visible = [d for d in devs
                   if d["ip"] != own and d["ip"] != self._gateway_ip]
        self.after(0, lambda: self._on_scan_done(visible))

    def _on_scan_done(self, devices):
        self._devices = devices
        self._scan_btn.configure(state="normal", text="⟳  Scan")
        gm = self._gateway_mac or "not found"
        self._gw_lbl.configure(text=f"{self._gateway_ip}  ({gm})")
        self._rebuild()
        self._status(f"Found {len(devices)} device(s)")

    # ── cards ─────────────────────────────────────────────────────────────────

    def _rebuild(self):
        for c in self._cards:
            c.destroy()
        self._cards.clear()

        if not self._devices:
            self._empty.pack(pady=60)
            return

        self._empty.pack_forget()
        for dev in self._devices:
            card = DeviceCard(
                self._list, dev, self._spoofer,
                get_gateway=lambda: (self._gateway_ip, self._gateway_mac),
                on_rename=self._show_rename,
            )
            card.pack(fill="x", pady=(0, 10))
            self._cards.append(card)

    def _show_rename(self, dev: dict):
        """Pop up a dialog to set a custom name for a device."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename Device")
        dialog.geometry("340x160")
        dialog.configure(fg_color=BG)
        dialog.grab_set()

        current = namestore.get(dev["mac"]) or dev.get("hostname") or ""
        ctk.CTkLabel(dialog, text=f"Name for  {dev['ip']}",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=TEXT).pack(pady=(20, 8))

        entry = ctk.CTkEntry(dialog, width=260, placeholder_text="e.g. PS5, Mum's Phone…")
        entry.insert(0, current)
        entry.pack()

        def _save():
            name = entry.get().strip()
            if name:
                namestore.set_name(dev["mac"], name)
            else:
                namestore.clear(dev["mac"])
            dialog.destroy()
            self._rebuild()

        ctk.CTkButton(dialog, text="Save", command=_save,
                      fg_color=ACCENT, width=120).pack(pady=14)

    def _restore_all(self):
        self._spoofer.remove_all(self._devices,
                                  self._gateway_ip or "",
                                  self._gateway_mac or "")
        self._rebuild()
        self._status("All devices restored")

    def _status(self, msg: str):
        self._status_lbl.configure(text=f"  {msg}")

    def on_close(self):
        self._restore_all()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
