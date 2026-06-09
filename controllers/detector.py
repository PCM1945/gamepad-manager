import hid as hidapi
import logging
from models.controller import ConnectionType

logger = logging.getLogger("gamepad_manager")

# Classe responsável por detectar os controladores conectados e obter suas informações, incluindo o nível de bateria, se disponível. Ele roda em uma thread separada para não bloquear a interface do usuário. O resultado é emitido através de um sinal para que a interface possa ser atualizada.
# O poller verifica periodicamente (a cada 2 segundos) se houve mudanças nos controladores detectados e só emite um sinal de atualização se houver alguma mudança, para evitar atualizações desnecessárias na interface. Ele também lida com possíveis erros durante a detecção e obtenção de informações dos controladores, garantindo que o aplicativo continue funcionando mesmo que haja problemas com algum dispositivo.

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
    0x3537: "GameSir",        # GameSir wireless
}

# Common 2.4GHz wireless receiver product IDs (subset of known ones)
WIRELESS_RECEIVER_PIDS = {
    # Xbox wireless receivers
    0x02EA: "Xbox 360 Wireless Receiver",  # Xbox 360 Wireless Receiver
    0x02DD: "Xbox One Wireless Adapter",  # Xbox One Wireless Adapter
    0x02FE: "Xbox One S Wireless Adapter",  # Xbox One S Wireless Adapter
    # Logitech wireless receivers
    0xC21F: "F710 Gamepad",  # F710 Gamepad
    0xC219: "F510 Gamepad",  # F510 Gamepad
    0xC21D: "F310 Gamepad",  # F310 Gamepad
    # gamesir wireless receivers
    0x1098: "GameSir T4 nova 2 lite Receiver", # GameSir T4 nova 2 lite Receiver
    0x1040: "GameSir T4 nova lite Receiver", # GameSir T4 nova lite Receiver
}

# Keywords to filter OUT (non-gaming devices)
EXCLUDED_KEYWORDS = {
    'keyboard', 'mouse', 'trackpad', 'touchpad', 'sensor',
    'hid-compliant', 'device', 'headset', 'microphone',
    'usb input', 'generic usb', 'composite device', "usb receiver", 'webcam', 'camera',
}


def _is_gaming_controller(name, vid, pid):
    """Check if device is a gaming controller/receiver."""
    if not name:
        return False

    # Known receiver VID/PID pairs should always be treated as gaming devices.
    if vid in WIRELESS_GAMEPAD_VENDORS and pid in WIRELESS_RECEIVER_PIDS:
        logger.debug(f"Device VID=0x{vid:04X}, PID=0x{pid:04X} is a known wireless receiver, including as gaming device")
        return True
    
    name_lower = name.lower()
    
    # Check if name contains excluded keywords
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in name_lower:
            return False
    
    # Check if vendor is a known wireless gamepad vendor
    if vid in WIRELESS_GAMEPAD_VENDORS:
        # Additional check: name should suggest it's a controller
        gaming_keywords = {'controller', 'gamepad',
                            'receiver', 'wireless',
                            'adapter', 'joystick',
                            'game', 'gamesir',
                            'controller (xbox 360 for windows)'}
        if any(keyword in name_lower for keyword in gaming_keywords):
            return True    
    return False

def _get_connection_type(device):
    """Detect if controller is USB, Bluetooth or dongle based on device path or product ID."""
    path = device.get("path", "")
    name = (device.get("product_string") or "").lower()
    # hidapi.enumerate() returns vendor_id/product_id keys.
    pid = device.get("product_id", device.get("pid"))
    vid = device.get("vendor_id", device.get("vid"))

    print(f"[DEBUG] _get_connection_type: name='{name}', vid=0x{vid:04X}, pid=0x{pid:04X}, path='{path}'")

    if isinstance(path, bytes):
        path = path.decode("utf-8", errors="ignore")
    path = path.lower()

    if vid in WIRELESS_GAMEPAD_VENDORS and pid in WIRELESS_RECEIVER_PIDS:
        logger.debug(f"Detected known wireless receiver: VID=0x{vid:04X}, PID=0x{pid:04X}")
        return ConnectionType.DONGLE

    # Bluetooth markers in Windows HID paths and product names.
    if "bluetooth" in path or "#bth#" in path:
        return ConnectionType.BLUETOOTH

    # Generic wireless receiver naming conventions.
    if any(k in name for k in ("receiver", "dongle", "wireless adapter", "2.4g", "2.4ghz")):
        return ConnectionType.DONGLE

    # Windows HID paths often don't include the literal word 'usb'.
    if "usb" in path or "hid#" in path or "vid_" in path:
        return ConnectionType.USB

    # If it's a known gamepad vendor and not Bluetooth, prefer Dongle over Unknown.
    if vid in WIRELESS_GAMEPAD_VENDORS:
        return ConnectionType.DONGLE

    return ConnectionType.UNKNOWN

def detect_controllers():
    devices = []
    for d in hidapi.enumerate():
        vid = d["vendor_id"]
        pid = d["product_id"]
        name = d.get("product_string") or "Unknown Controller"
        path = d["path"]
        connection = _get_connection_type(d)
        
        # Convert bytes to string if necessary
        if isinstance(path, bytes):
            path = path.decode('utf-8')
        
        # DEBUG: Print all devices
        #print(f"[DEBUG] Device: VID=0x{vid:04X}, PID=0x{pid:04X}, Name='{name}'")
        
        # Filter: only include gaming controllers and wireless receivers
        if not _is_gaming_controller(name, vid, pid):
            #logger.debug(f"  → Filtrado (não é gaming controller)")
            continue
        
        #logger.debug(f"  → ✓ Detectado!")

        ctype = WIRELESS_GAMEPAD_VENDORS.get(vid, "Unknown")

        devices.append({
            "name": name,
            "vid": vid,
            "pid": pid,
            "path": path,
            "type": ctype,
            "connection": connection
        })

    return devices
