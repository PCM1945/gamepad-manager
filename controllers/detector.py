import hid as hidapi

# Vendor IDs for wireless game controllers and 2.4GHz receivers
WIRELESS_GAMEPAD_VENDORS = {
    0x045E: "Xbox",           # Microsoft (Xbox wireless)
    0x046D: "Logitech",       # Logitech wireless
    0x054C: "PlayStation",    # Sony
    0x057E: "Nintendo",       # Nintendo
    0x0738: "Mad Catz",       # Mad Catz wireless
    0x0E8F: "GreenAsia",      # GreenAsia wireless
    0x1532: "Razer",          # Razer wireless
    0x2563: "SteelSeries",    # SteelSeries
}

# Common 2.4GHz wireless receiver product IDs (subset of known ones)
WIRELESS_RECEIVER_PIDS = {
    # Xbox wireless receivers
    0x02EA,  # Xbox 360 Wireless Receiver
    0x02DD,  # Xbox One Wireless Adapter
    0x02FE,  # Xbox One S Wireless Adapter
    # Logitech wireless receivers
    0xC21F,  # F710 Gamepad
    0xC219,  # F510 Gamepad
    0xC21D,  # F310 Gamepad
}

# Keywords to filter OUT (non-gaming devices)
EXCLUDED_KEYWORDS = {
    'keyboard', 'mouse', 'trackpad', 'touchpad', 'sensor',
    'hid-compliant', 'device', 'headset', 'microphone',
    'usb input', 'generic usb', 'composite device'
}


def _is_gaming_controller(name, vid, pid):
    """Check if device is a gaming controller/receiver."""
    if not name:
        return False
    
    name_lower = name.lower()
    
    # Check if name contains excluded keywords
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in name_lower:
            return False
    
    # Check if vendor is a known wireless gamepad vendor
    if vid in WIRELESS_GAMEPAD_VENDORS:
        # Additional check: name should suggest it's a controller
        gaming_keywords = {'controller', 'gamepad', 'receiver', 'wireless', 'adapter', 'joystick', 'game'}
        if any(keyword in name_lower for keyword in gaming_keywords):
            return True
        # Xbox and PlayStation devices without these keywords are likely real controllers
        if vid in (0x045E, 0x054C, 0x057E):
            return True
    
    return False


def detect_controllers():
    devices = []
    for d in hidapi.enumerate():
        vid = d["vendor_id"]
        pid = d["product_id"]
        name = d.get("product_string") or "Unknown Controller"
        path = d["path"]
        
        # Convert bytes to string if necessary
        if isinstance(path, bytes):
            path = path.decode('utf-8')
        
        # Filter: only include gaming controllers and wireless receivers
        if not _is_gaming_controller(name, vid, pid):
            continue

        ctype = WIRELESS_GAMEPAD_VENDORS.get(vid, "Unknown")

        devices.append({
            "name": name,
            "vid": vid,
            "pid": pid,
            "path": path,
            "type": ctype,
        })

    return devices
