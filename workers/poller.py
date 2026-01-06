from PyQt5.QtCore import QThread, pyqtSignal
import time
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from controllers.detector import detect_controllers
from models.controller import Controller, ControllerType, ConnectionType
from plat import get_battery_provider

logger = logging.getLogger("gamepad_manager")


class ControllerPoller(QThread):
    updated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.battery_provider = get_battery_provider()
        self.last_controllers = []
        self.battery_executor = ThreadPoolExecutor(max_workers=4)

    def run(self):
        while True:
            controllers = self.scan()
            
            # Only emit signal if controllers changed
            if self._controllers_changed(controllers):
                self.updated.emit(controllers)
                self.last_controllers = controllers
            
            time.sleep(2)

    def scan(self):
        """Detect connected controllers and get their battery info."""
        try:
            detected = detect_controllers()
            controllers = []

            # Get batteries asynchronously
            battery_futures = {}
            for device in detected:
                if self.battery_provider:
                    future = self.battery_executor.submit(
                        self.battery_provider.get_battery, device
                    )
                    battery_futures[id(device)] = (device, future)
                else:
                    # No battery provider, create controller without battery
                    controller = Controller(
                        name=device["name"],
                        ctype=self._parse_controller_type(device["type"]),
                        connection=self._detect_connection_type(device),
                        battery=None
                    )
                    controllers.append(controller)

            # Collect battery results
            for device_id, (device, future) in battery_futures.items():
                try:
                    battery = future.result(timeout=1.0)  # 1 second timeout per device
                except Exception:
                    battery = None

                controller = Controller(
                    name=device["name"],
                    ctype=self._parse_controller_type(device["type"]),
                    connection=self._detect_connection_type(device),
                    battery=battery
                )
                controllers.append(controller)

            return controllers
        except Exception as e:
            logger.error(f"Error scanning controllers: {e}", exc_info=True)
            return []

    def _controllers_changed(self, controllers):
        """Check if controller list has changed."""
        if len(controllers) != len(self.last_controllers):
            return True
        
        # Check if any controller info changed
        for new, old in zip(controllers, self.last_controllers):
            if (new.name != old.name or 
                new.type != old.type or 
                new.connection != old.connection or
                new.battery != old.battery):
                return True
        
        return False

    def _parse_controller_type(self, type_string):
        """Convert detector type string to ControllerType enum."""
        mapping = {
            "Xbox": ControllerType.XBOX,
            "PlayStation": ControllerType.PLAYSTATION,
            "Nintendo": ControllerType.NINTENDO,
        }
        return mapping.get(type_string, ControllerType.UNKNOWN)

    def _detect_connection_type(self, device):
        """Detect if controller is USB or Bluetooth based on device path."""
        path = device.get("path", "").lower()
        if "bluetooth" in path or "#bth#" in path:
            return ConnectionType.BLUETOOTH
        elif "usb" in path:
            return ConnectionType.USB
        return ConnectionType.UNKNOWN
