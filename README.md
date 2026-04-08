# netcut-clone

A GUI network manager that scans your local network and lets you cut (ARP-spoof) devices off the internet — a Python clone of NetCut.

> **For authorized/educational use only.** Only run this on networks you own or have explicit permission to test.

## Features

- Scans the LAN and lists connected devices with vendor info
- ARP-spoofs selected devices to block their internet access
- Custom device nicknames
- Dark-themed CustomTkinter GUI

## Setup

```bash
pip install -r requirements.txt
# Requires admin/root privileges for ARP spoofing
python main.py
```

## Requirements

- Python 3.10+
- Scapy (raw packet crafting)
- CustomTkinter (GUI)
- Must be run as administrator on Windows

## Stack

| File | Purpose |
|---|---|
| `main.py` | GUI application |
| `network.py` | Network scanning and MAC lookup |
| `spoofer.py` | ARP spoofing logic |
| `vendor.py` | Device vendor identification |
| `names.py` | Custom device nickname storage |
