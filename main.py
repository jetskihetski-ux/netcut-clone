import threading
import tkinter as tk
from tkinter import ttk, messagebox

from network import get_subnet, get_gateway_ip, get_mac, scan_network, get_local_ip
from spoofer import ARPSpoofer

# ── theme ─────────────────────────────────────────────────────────────────────
BG      = "#1E1E2E"
CARD    = "#2D2D3F"
ACCENT  = "#6C63FF"
RED     = "#FF5252"
GREEN   = "#4CAF50"
TEXT    = "#FFFFFF"
SUBTEXT = "#888888"
BORDER  = "#3D3D55"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NetCut Clone")
        self.geometry("820x560")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._spoofer   = ARPSpoofer()
        self._devices:  list[dict] = []
        self._gateway_ip:  str | None = None
        self._gateway_mac: str | None = None

        self._build_ui()
        self._init_network()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── top bar ──
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=20, pady=(20, 10))

        tk.Label(top, text="NetCut Clone", font=("Segoe UI", 18, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")

        self._scan_btn = tk.Button(
            top, text="⟳  Scan Network",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg=TEXT, activebackground="#5550CC",
            activeforeground=TEXT, bd=0, cursor="hand2",
            padx=18, pady=8, relief="flat",
            command=self._start_scan,
        )
        self._scan_btn.pack(side="right")

        # ── gateway info ──
        info = tk.Frame(self, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        info.pack(fill="x", padx=20, pady=(0, 10))

        self._gw_label  = self._info_label(info, "Gateway", "Detecting...")
        self._own_label = self._info_label(info, "Your IP",  get_local_ip())

        # ── device table ──
        table_frame = tk.Frame(self, bg=BG)
        table_frame.pack(fill="both", expand=True, padx=20)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                        background=CARD, foreground=TEXT,
                        fieldbackground=CARD, rowheight=36,
                        font=("Segoe UI", 10))
        style.configure("Custom.Treeview.Heading",
                        background=BORDER, foreground=TEXT,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Custom.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", TEXT)])

        cols = ("ip", "mac", "hostname", "status")
        self._tree = ttk.Treeview(table_frame, columns=cols,
                                  show="headings", style="Custom.Treeview")
        self._tree.heading("ip",       text="IP Address")
        self._tree.heading("mac",      text="MAC Address")
        self._tree.heading("hostname", text="Hostname")
        self._tree.heading("status",   text="Status")
        self._tree.column("ip",       width=140, anchor="w")
        self._tree.column("mac",      width=160, anchor="w")
        self._tree.column("hostname", width=240, anchor="w")
        self._tree.column("status",   width=110, anchor="center")

        self._tree.tag_configure("blocked", foreground=RED)
        self._tree.tag_configure("active",  foreground=GREEN)

        sb = ttk.Scrollbar(table_frame, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda _: self._toggle_selected())

        # ── action buttons ──
        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=20, pady=12)

        self._block_btn = tk.Button(
            actions, text="✂  Block",
            font=("Segoe UI", 11, "bold"),
            bg=RED, fg=TEXT, activebackground="#CC0000",
            activeforeground=TEXT, bd=0, cursor="hand2",
            padx=28, pady=10, relief="flat",
            command=self._block_selected,
        )
        self._block_btn.pack(side="left", padx=(0, 10))

        self._unblock_btn = tk.Button(
            actions, text="✔  Unblock",
            font=("Segoe UI", 11, "bold"),
            bg=GREEN, fg="#111", activebackground="#388E3C",
            activeforeground="#111", bd=0, cursor="hand2",
            padx=28, pady=10, relief="flat",
            command=self._unblock_selected,
        )
        self._unblock_btn.pack(side="left")

        tk.Button(
            actions, text="Unblock All",
            font=("Segoe UI", 10),
            bg=CARD, fg=SUBTEXT, activebackground=BORDER,
            activeforeground=TEXT, bd=0, cursor="hand2",
            padx=18, pady=10, relief="flat",
            command=self._unblock_all,
        ).pack(side="right")

        # ── status bar ──
        self._status = tk.Label(self, text="Ready — click Scan to discover devices",
                                font=("Segoe UI", 9), bg=BORDER, fg=SUBTEXT,
                                anchor="w", padx=12, pady=5)
        self._status.pack(fill="x", side="bottom")

    def _info_label(self, parent, title, value):
        f = tk.Frame(parent, bg=CARD)
        f.pack(side="left", padx=20, pady=10)
        tk.Label(f, text=title, font=("Segoe UI", 9),
                 bg=CARD, fg=SUBTEXT).pack(anchor="w")
        lbl = tk.Label(f, text=value, font=("Segoe UI", 11, "bold"),
                       bg=CARD, fg=TEXT)
        lbl.pack(anchor="w")
        return lbl

    # ── network init ──────────────────────────────────────────────────────────

    def _init_network(self):
        def _worker():
            gw_ip  = get_gateway_ip()
            gw_mac = get_mac(gw_ip) if gw_ip else None
            self.after(0, lambda: self._on_gateway(gw_ip, gw_mac))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_gateway(self, ip, mac):
        self._gateway_ip  = ip
        self._gateway_mac = mac
        label = f"{ip}  ({mac})" if ip and mac else "Not found"
        self._gw_label.config(text=label)
        self._set_status(f"Gateway: {label} — ready to scan")

    # ── scanning ──────────────────────────────────────────────────────────────

    def _start_scan(self):
        if not self._gateway_ip:
            messagebox.showwarning("NetCut Clone", "Gateway not detected yet. Wait a moment.")
            return
        self._scan_btn.config(state="disabled", text="Scanning...")
        self._set_status("Scanning network — this may take a few seconds...")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        subnet  = get_subnet()
        devices = scan_network(subnet)
        # exclude self and gateway
        own_ip = get_local_ip()
        devices = [d for d in devices
                   if d["ip"] != own_ip and d["ip"] != self._gateway_ip]
        self.after(0, lambda: self._on_scan_done(devices))

    def _on_scan_done(self, devices):
        self._devices = devices
        self._refresh_table()
        self._scan_btn.config(state="normal", text="⟳  Scan Network")
        self._set_status(f"Found {len(devices)} device(s) — double-click or select + Block to cut a device")

    # ── table ─────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for dev in self._devices:
            blocked = self._spoofer.is_blocked(dev["ip"])
            status  = "🔴 Blocked" if blocked else "🟢 Active"
            tag     = "blocked"    if blocked else "active"
            self._tree.insert("", "end", iid=dev["ip"],
                              values=(dev["ip"], dev["mac"],
                                      dev["hostname"], status),
                              tags=(tag,))

    def _selected_device(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("NetCut Clone", "Select a device first.")
            return None
        ip = sel[0]
        return next((d for d in self._devices if d["ip"] == ip), None)

    # ── block / unblock ───────────────────────────────────────────────────────

    def _block_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        if self._spoofer.is_blocked(dev["ip"]):
            self._set_status(f"{dev['ip']} is already blocked.")
            return
        self._spoofer.block(dev["ip"], dev["mac"],
                            self._gateway_ip, self._gateway_mac)
        self._refresh_table()
        self._set_status(f"Blocking {dev['hostname']} ({dev['ip']})...")

    def _unblock_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        self._spoofer.unblock(dev["ip"], dev["mac"],
                              self._gateway_ip, self._gateway_mac)
        self._refresh_table()
        self._set_status(f"Unblocked {dev['hostname']} ({dev['ip']})")

    def _toggle_selected(self):
        dev = self._selected_device()
        if not dev:
            return
        if self._spoofer.is_blocked(dev["ip"]):
            self._unblock_selected()
        else:
            self._block_selected()

    def _unblock_all(self):
        self._spoofer.unblock_all(self._devices,
                                  self._gateway_ip, self._gateway_mac)
        self._refresh_table()
        self._set_status("All devices unblocked.")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status.config(text=f"  {msg}")

    def on_close(self):
        self._unblock_all()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
