import ctypes
import logging

logger = logging.getLogger("gamepad_manager")


# XInput constants
XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE = 7849
XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE = 8689
XINPUT_GAMEPAD_TRIGGER_THRESHOLD = 30

# XInput device subtypes
XINPUT_DEVSUBTYPE_GAMEPAD = 0x01
XINPUT_DEVSUBTYPE_WHEEL = 0x02
XINPUT_DEVSUBTYPE_ARCADE_STICK = 0x03
XINPUT_DEVSUBTYPE_FLIGHT_STICK = 0x04
XINPUT_DEVSUBTYPE_DANCE_PAD = 0x05
XINPUT_DEVSUBTYPE_GUITAR = 0x06
XINPUT_DEVSUBTYPE_DRUM_KIT = 0x08


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class XINPUT_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("Type", ctypes.c_ubyte),
        ("SubType", ctypes.c_ubyte),
        ("Flags", ctypes.c_ushort),
        ("Gamepad", XINPUT_GAMEPAD),
        ("Vibration", ctypes.c_ubyte * 4),
    ]


class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BatteryType", ctypes.c_ubyte),
        ("BatteryLevel", ctypes.c_ubyte),
    ]


class XInputAPI:
    """Wrapper for XInput API."""
    
    def __init__(self):
        self._xinput = None
        self._get_state_func = None
        self._get_capabilities_func = None
        self._get_battery_func = None
        self._init_xinput()
    
    def _init_xinput(self):
        """Load XInput DLL and prepare functions."""
        xinput_libs = ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll")
        for lib in xinput_libs:
            try:
                x = ctypes.WinDLL(lib)
                
                # XInputGetState
                get_state = getattr(x, "XInputGetState", None)
                if get_state:
                    get_state.argtypes = [ctypes.c_uint, ctypes.POINTER(XINPUT_STATE)]
                    get_state.restype = ctypes.c_uint
                    self._get_state_func = get_state
                
                # XInputGetCapabilities
                get_caps = getattr(x, "XInputGetCapabilities", None)
                if get_caps:
                    get_caps.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(XINPUT_CAPABILITIES)]
                    get_caps.restype = ctypes.c_uint
                    self._get_capabilities_func = get_caps
                
                # XInputGetBatteryInformation
                get_battery = getattr(x, "XInputGetBatteryInformation", None)
                if get_battery:
                    get_battery.argtypes = [ctypes.c_uint, ctypes.c_ubyte, ctypes.POINTER(XINPUT_BATTERY_INFORMATION)]
                    get_battery.restype = ctypes.c_uint
                    self._get_battery_func = get_battery
                
                if self._get_state_func and self._get_capabilities_func:
                    self._xinput = x
                    logger.info(f"Loaded {lib} for XInput")
                    return
            except Exception as e:
                logger.debug(f"Failed to load {lib}: {e}")
                continue
        
        logger.warning("Could not load any XInput DLLs. Controller detection will be unavailable.")
    
    def get_state(self, user_index):
        """Get the state of an XInput controller."""
        if not self._get_state_func:
            return None
        
        state = XINPUT_STATE()
        result = self._get_state_func(ctypes.c_uint(user_index), ctypes.byref(state))
        if result == 0:  # ERROR_SUCCESS
            return state
        return None
    
    def get_capabilities(self, user_index):
        """Get the capabilities of an XInput controller."""
        if not self._get_capabilities_func:
            return None
        
        caps = XINPUT_CAPABILITIES()
        result = self._get_capabilities_func(ctypes.c_uint(user_index), ctypes.c_uint(0), ctypes.byref(caps))
        if result == 0:  # ERROR_SUCCESS
            return caps
        return None
    
    def get_battery(self, user_index):
        """Get battery information for an XInput controller."""
        if not self._get_battery_func:
            return None
        
        battery = XINPUT_BATTERY_INFORMATION()
        # 0x00 = BATTERY_DEVTYPE_GAMEPAD
        result = self._get_battery_func(ctypes.c_uint(user_index), ctypes.c_ubyte(0x00), ctypes.byref(battery))
        if result == 0:  # ERROR_SUCCESS
            return battery
        return None


# Global XInput API instance
_xinput_api = None


def _get_xinput_api():
    """Get or create the global XInput API instance."""
    global _xinput_api
    if _xinput_api is None:
        _xinput_api = XInputAPI()
    return _xinput_api


def _get_controller_name(subtype):
    """Get controller name based on XInput subtype."""
    subtype_names = {
        XINPUT_DEVSUBTYPE_GAMEPAD: "Xbox Controller",
        XINPUT_DEVSUBTYPE_WHEEL: "Xbox Racing Wheel",
        XINPUT_DEVSUBTYPE_ARCADE_STICK: "Xbox Arcade Stick",
        XINPUT_DEVSUBTYPE_FLIGHT_STICK: "Xbox Flight Stick",
        XINPUT_DEVSUBTYPE_DANCE_PAD: "Xbox Dance Pad",
        XINPUT_DEVSUBTYPE_GUITAR: "Xbox Guitar",
        XINPUT_DEVSUBTYPE_DRUM_KIT: "Xbox Drum Kit",
    }
    return subtype_names.get(subtype, "Xbox Compatible Controller")


def detect_controllers():
    """Detect connected XInput controllers.
    
    Returns:
        List of dictionaries containing controller information.
        Each dictionary has: name, type, index, subtype
    """
    devices = []
    xinput = _get_xinput_api()
    
    if not xinput._xinput:
        logger.warning("XInput not available, cannot detect controllers")
        return devices
    
    # XInput supports up to 4 controllers (indices 0-3)
    for user_index in range(4):
        try:
            caps = xinput.get_capabilities(user_index)
            if caps:
                # Controller is connected
                name = _get_controller_name(caps.SubType)
                
                devices.append({
                    "name": name,
                    "type": "Xbox",  # XInput only supports Xbox controllers
                    "index": user_index,
                    "subtype": caps.SubType,
                })
                logger.debug(f"Found XInput controller at index {user_index}: {name}")
        except Exception as e:
            logger.debug(f"Error checking XInput slot {user_index}: {e}")
            continue
    
    return devices
