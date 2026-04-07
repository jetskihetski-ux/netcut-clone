import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import customtkinter as ctk

from network import get_subnet, get_gateway_ip, get_mac, scan_network, get_local_ip
from spoofer import ARPSpoofer
from vendor import get_device_info
import names as namestore

ctk.set_appearance_mode("dark")

BG     = "#0d0d1a"
BAR    = "#16213e"
ACCENT = "#6C63FF"
RED    = "#FF5252"
GREEN  = "#4CAF50"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NetCut")
        self.geometry("780x520")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self._spoofer      = ARPSpoofer()
        self._devices      = []
        self._gateway_ip   = None
        self._gateway_mac  = None

        self._build()
        self._init_network()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── top bar ──
        top = ctk.CTkFrame(self, fg_color=BAR, corner_radius=0, height=54)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="NetCut",
                     font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color="white").pack(side="left", padx=20)

        self._scan_btn = ctk.CTkButton(
            top, text="⟳  Scan Network",
            fg_color=ACCENT, hover_color="#5550CC",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            width=140, height=34,
            command=self._scan,
        )
        self._scan_btn.pack(side="right", padx=16, pady=10)

        self._gw_label = ctk.CTkLabel(
            top, text="Gateway: detecting...",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#666",
        )
        self._gw_label.pack(side="right", padx=4)

        # ── device table ──
        tbl = tk.Frame(self, bg=BG)
        tbl.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("N.Treeview",
                         background="#16213e",
                         foreground="white",
                         fieldbackground="#16213e",
                         rowheight=38,
                         font=("Segoe UI", 11))
        style.configure("N.Treeview.Heading",
                         background="#0d0d1a",
                         foreground="#888888",
                         font=("Segoe UI", 10, "bold"),
                         relief="flat")
        style.map("N.Treeview",
                   background=[("selected", ACCENT)],
                   foreground=[("selected", "white")])

        self.tree = ttk.Treeview(
            tbl,
            columns=("device", "ip", "mac", "status"),
            show="headings",
            style="N.Treeview",
            selectmode="browse",
        )
        self.tree.heading("device", text="Device")
        self.tree.heading("ip",     text="IP Address")
        self.tree.heading("mac",    text="MAC Address")
        self.tree.heading("status", text="Status")
        self.tree.column("device", width=240, anchor="w")
        self.tree.column("ip",     width=140, anchor="w")
        self.tree.column("mac",    width=180, anchor="w")
        self.tree.column("status", width=110, anchor="center")

        self.tree.tag_configure("online", foreground="#4CAF50")
        self.tree.tag_configure("cut",    foreground="#FF5252",
                                           background="#1e0a0a")

        sb = ttk.Scrollbar(tbl, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda _: self._toggle())
        self.tree.bind("<Button-3>", self._right_click)

        # ── bottom bar ──
        bot = ctk.CTkFrame(self, fg_color=BAR, corner_radius=0, height=54)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)

        ctk.CTkButton(bot, text="✂  CUT",
                       fg_color=RED, hover_color="#c0392b",
                       font=ctk.CTkFont("Segoe UI", 13, "bold"),
                       width=120, height=36,
                       command=self._cut).pack(side="left", padx=(14, 6), pady=9)

        ctk.CTkButton(bot, text="▶  Resume",
                       fg_color=GREEN, hover_color="#27ae60",
                       font=ctk.CTkFont("Segoe UI", 13, "bold"),
                       text_color="white",
                       width=120, height=36,
                       command=self._resume).pack(side="left", padx=6, pady=9)

        ctk.CTkButton(bot, text="Resume All",
                       fg_color="transparent", hover_color="#2d2d3f",
                       text_color="#666",
                       width=100, height=36,
                       command=self._resume_all).pack(side="left", padx=6, pady=9)

        self._status = ctk.CTkLabel(bot, text="Ready — click Scan",
                                     font=ctk.CTkFont("Segoe UI", 11),
                                     text_color="#666")
        self._status.pack(side="right", padx=16)

    # ── network init ──────────────────────────────────────────────────────────

    def _init_network(self):
        def _w():
            ip  = get_gateway_ip()
            self.after(0, lambda: self._set_gw(ip, None))
            mac = get_mac(ip) if ip else None
            self.after(0, lambda: self._set_gw(ip, mac))
        threading.Thread(target=_w, daemon=True).start()

    def _set_gw(self, ip, mac):
        self._gateway_ip  = ip
        self._gateway_mac = mac
        if ip and mac:
            self._gw_label.configure(text=f"Gateway: {ip}  ({mac})")
        elif ip:
            self._gw_label.configure(text=f"Gateway: {ip}  (resolving…)")
        else:
            self._gw_label.configure(text="Gateway: not found")

    # ── scan ──────────────────────────────────────────────────────────────────

    def _scan(self):
        if not self._gateway_ip:
            messagebox.showwarning("NetCut", "Gateway not detected.\nMake sure you are connected to WiFi.")
            return
        self._scan_btn.configure(state="disabled", text="Scanning…")
        self._set_status("Scanning…")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        own  = get_local_ip()
        devs = scan_network(
            get_subnet(),
            on_progress=lambda m: self.after(0, lambda msg=m: self._set_status(msg)),
        )

        # Grab gateway MAC from scan if still missing
        if not self._gateway_mac and self._gateway_ip:
            for d in devs:
                if d["ip"] == self._gateway_ip:
                    self._gateway_mac = d["mac"]
                    break
            if not self._gateway_mac:
                self._gateway_mac = get_mac(self._gateway_ip)
            if self._gateway_mac:
                self.after(0, lambda: self._set_gw(self._gateway_ip, self._gateway_mac))

        visible = [d for d in devs
                   if d["ip"] != own and d["ip"] != self._gateway_ip]
        self.after(0, lambda: self._on_scan_done(visible))

    def _on_scan_done(self, devices):
        self._devices = devices
        self._scan_btn.configure(state="normal", text="⟳  Scan Network")
        self._refresh_table()
        self._set_status(f"{len(devices)} device(s) found  —  double-click or select + CUT")

    # ── table ─────────────────────────────────────────────────────────────────

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for dev in self._devices:
            emoji, vendor = get_device_info(dev["mac"], dev["hostname"])
            custom   = namestore.get(dev["mac"])
            hostname = dev.get("hostname", "")
            name     = custom or hostname or vendor
            display  = f"{emoji}  {name}"

            cut  = self._spoofer.is_active(dev["ip"])
            tag  = "cut" if cut else "online"
            stat = "✂  CUT" if cut else "● Online"

            self.tree.insert("", "end", iid=dev["ip"],
                             values=(display, dev["ip"], dev["mac"], stat),
                             tags=(tag,))

    def _selected_dev(self):
        sel = self.tree.selection()
        if not sel:
            return None
        ip = sel[0]
        return next((d for d in self._devices if d["ip"] == ip), None)

    # ── cut / resume ──────────────────────────────────────────────────────────

    def _cut(self):
        dev = self._selected_dev()
        if not dev:
            messagebox.showinfo("NetCut", "Select a device first.")
            return
        if not self._gateway_ip or not self._gateway_mac:
            messagebox.showerror("NetCut",
                "Gateway MAC not resolved.\n\n"
                "Run as Administrator, then scan again.")
            return
        self._spoofer.apply(dev["ip"], dev["mac"],
                             self._gateway_ip, self._gateway_mac,
                             mode="block")
        self._refresh_table()
        self._set_status(f"Cutting {dev['ip']}…")

    def _resume(self):
        dev = self._selected_dev()
        if not dev:
            messagebox.showinfo("NetCut", "Select a device first.")
            return
        self._spoofer.remove(dev["ip"], dev["mac"],
                              self._gateway_ip or "",
                              self._gateway_mac or "")
        self._refresh_table()
        self._set_status(f"Resumed {dev['ip']}")

    def _toggle(self):
        dev = self._selected_dev()
        if not dev:
            return
        if self._spoofer.is_active(dev["ip"]):
            self._resume()
        else:
            self._cut()

    def _resume_all(self):
        self._spoofer.remove_all(self._devices,
                                  self._gateway_ip or "",
                                  self._gateway_mac or "")
        self._refresh_table()
        self._set_status("All devices resumed")

    # ── right-click rename ────────────────────────────────────────────────────

    def _right_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        dev = self._selected_dev()
        if not dev:
            return

        menu = tk.Menu(self, tearoff=0, bg="#16213e", fg="white",
                       activebackground=ACCENT, activeforeground="white")
        menu.add_command(label="✏  Rename device",
                         command=lambda: self._rename(dev))
        menu.add_separator()
        menu.add_command(label="✂  Cut",    command=self._cut)
        menu.add_command(label="▶  Resume", command=self._resume)
        menu.tk_popup(event.x_root, event.y_root)

    def _rename(self, dev):
        current = namestore.get(dev["mac"]) or dev.get("hostname", "")
        name = simpledialog.askstring(
            "Rename Device",
            f"Name for {dev['ip']}:",
            initialvalue=current,
            parent=self,
        )
        if name is not None:
            if name.strip():
                namestore.set_name(dev["mac"], name.strip())
            else:
                namestore.clear(dev["mac"])
            self._refresh_table()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status.configure(text=msg)

    def on_close(self):
        self._resume_all()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
