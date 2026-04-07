import requests

# OUI (first 3 MAC bytes) -> (company, emoji, device label)
OUI_MAP = {
    # Sony / PlayStation
    "a8:8f:d9": ("Sony",      "🎮", "PlayStation"),
    "00:04:1f": ("Sony",      "🎮", "PlayStation"),
    "00:13:a9": ("Sony",      "🎮", "PlayStation"),
    "00:15:c1": ("Sony",      "🎮", "PlayStation"),
    "00:1d:0d": ("Sony",      "🎮", "PlayStation"),
    "00:1f:a7": ("Sony",      "🎮", "PlayStation"),
    "00:24:8d": ("Sony",      "🎮", "PlayStation"),
    "28:37:37": ("Sony",      "🎮", "PlayStation"),
    "70:66:55": ("Sony",      "🎮", "PlayStation"),
    "ac:9b:0a": ("Sony",      "🎮", "PlayStation"),
    # Microsoft / Xbox
    "28:18:78": ("Microsoft", "🎮", "Xbox"),
    "7c:1e:52": ("Microsoft", "🎮", "Xbox"),
    "98:5f:d3": ("Microsoft", "🎮", "Xbox"),
    "00:17:fa": ("Microsoft", "🎮", "Xbox"),
    "00:50:f2": ("Microsoft", "💻", "Windows PC"),
    # Apple
    "00:17:f2": ("Apple",     "💻", "MacBook"),
    "00:1b:63": ("Apple",     "📱", "iPhone"),
    "00:1c:b3": ("Apple",     "📱", "iPhone"),
    "00:23:12": ("Apple",     "📱", "iPhone"),
    "00:26:b9": ("Apple",     "📱", "iPhone"),
    "00:26:bb": ("Apple",     "📱", "iPhone"),
    "3c:07:54": ("Apple",     "📱", "iPhone"),
    "60:fb:42": ("Apple",     "💻", "MacBook"),
    "78:7b:8a": ("Apple",     "📱", "iPhone"),
    "a4:5e:60": ("Apple",     "📱", "iPhone"),
    "f0:d1:a9": ("Apple",     "📱", "iPhone"),
    # Samsung
    "00:07:ab": ("Samsung",   "📱", "Samsung Phone"),
    "00:15:99": ("Samsung",   "📱", "Samsung Phone"),
    "00:16:32": ("Samsung",   "📺", "Samsung TV"),
    "2c:54:cf": ("Samsung",   "📱", "Samsung Phone"),
    "78:52:1a": ("Samsung",   "📱", "Samsung Phone"),
    "8c:77:12": ("Samsung",   "📺", "Samsung TV"),
    "bc:20:a4": ("Samsung",   "📱", "Samsung Phone"),
    "e4:7c:f9": ("Samsung",   "📱", "Samsung Phone"),
    # Nintendo
    "00:1a:e9": ("Nintendo",  "🎮", "Nintendo Switch"),
    "98:b6:e9": ("Nintendo",  "🎮", "Nintendo Switch"),
    "00:17:ab": ("Nintendo",  "🎮", "Nintendo"),
    "00:19:fd": ("Nintendo",  "🎮", "Nintendo"),
    "00:22:d7": ("Nintendo",  "🎮", "Nintendo"),
    "00:24:44": ("Nintendo",  "🎮", "Nintendo"),
    # Amazon
    "40:b4:cd": ("Amazon",    "📦", "Amazon Device"),
    "68:37:e9": ("Amazon",    "📺", "Fire TV"),
    "74:c2:46": ("Amazon",    "🔊", "Echo"),
    "fc:a6:67": ("Amazon",    "🔊", "Echo"),
    # LG
    "00:1e:75": ("LG",        "📺", "LG TV"),
    "a8:23:fe": ("LG",        "📺", "LG TV"),
    "cc:2d:8c": ("LG",        "📺", "LG TV"),
    # TP-Link
    "14:cc:20": ("TP-Link",   "📡", "TP-Link"),
    "50:c7:bf": ("TP-Link",   "📡", "TP-Link"),
    "ec:08:6b": ("TP-Link",   "📡", "TP-Link"),
    # Raspberry Pi
    "b8:27:eb": ("Raspberry Pi", "🖥️", "Raspberry Pi"),
    "dc:a6:32": ("Raspberry Pi", "🖥️", "Raspberry Pi"),
    # Google
    "54:60:09": ("Google",    "🔊", "Google Home"),
    "f4:f5:d8": ("Google",    "📱", "Google Device"),
    # Intel (common in laptops)
    "8c:8d:28": ("Intel",     "💻", "Laptop"),
    # Realtek (common in PCs)
    "00:e0:4c": ("Realtek",   "💻", "Windows PC"),
}

_cache: dict[str, str] = {}


def _api_lookup(mac: str) -> str | None:
    try:
        r = requests.get(f"https://api.macvendors.com/{mac}", timeout=3)
        return r.text.strip() if r.status_code == 200 else None
    except Exception:
        return None


def _vendor_to_info(vendor: str) -> tuple[str, str]:
    v = vendor.lower()
    if "sony"       in v: return "🎮", "PlayStation"
    if "apple"      in v: return "📱", "Apple Device"
    if "samsung"    in v: return "📱", "Samsung Device"
    if "microsoft"  in v: return "💻", "Windows PC"
    if "nintendo"   in v: return "🎮", "Nintendo"
    if "amazon"     in v: return "📦", "Amazon Device"
    if "tp-link"    in v: return "📡", "TP-Link"
    if "intel"      in v: return "💻", "Laptop"
    if "realtek"    in v: return "💻", "PC"
    if "lg electron" in v: return "📺", "LG TV"
    if "raspberry"  in v: return "🖥️", "Raspberry Pi"
    if "google"     in v: return "🔊", "Google Device"
    return "🖥️", vendor


def get_device_info(mac: str, hostname: str = "") -> tuple[str, str]:
    """Return (emoji, display_name) for a device MAC address."""
    oui = mac[:8].lower()

    # 1. Local OUI table
    if oui in OUI_MAP:
        _, emoji, label = OUI_MAP[oui]
        return emoji, label

    # 2. API lookup (cached)
    if mac not in _cache:
        _cache[mac] = _api_lookup(mac) or ""
    if _cache[mac]:
        return _vendor_to_info(_cache[mac])

    # 3. Hostname hints
    if hostname and hostname not in (mac, ""):
        h = hostname.lower()
        if any(x in h for x in ("iphone", "ipad")):     return "📱", hostname
        if any(x in h for x in ("android", "phone")):   return "📱", hostname
        if any(x in h for x in ("ps4", "ps5")):         return "🎮", hostname
        if "xbox"    in h:                               return "🎮", hostname
        if any(x in h for x in ("tv", "roku", "firetv")): return "📺", hostname
        if any(x in h for x in ("laptop", "macbook", "pc", "desktop")): return "💻", hostname
        return "🖥️", hostname

    return "🖥️", "Unknown Device"
