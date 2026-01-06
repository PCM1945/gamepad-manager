import sys
from plat.windows import WindowsBatteryProvider
from models.controller import Controller, ControllerType, ConnectionType


def get_battery_provider():
    """Get the appropriate battery provider for the current platform."""
    if sys.platform == "win32":
        return WindowsBatteryProvider()
    if sys.platform == "darwin":
        pass  # Add macOS battery provider
    if sys.platform.startswith("linux"):
        pass
