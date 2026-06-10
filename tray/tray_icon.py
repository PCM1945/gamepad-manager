from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt
import sys
import logging
from models.controller import ControllerType, ConnectionType
from ui.controller_events_window import ControllerEventsWindow
from workers.input_monitor import InputMonitor

logger = logging.getLogger("gamepad_manager")


class TrayIcon(QSystemTrayIcon):
    def __init__(self, icon):
        super().__init__(icon)
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.controllers = []
        self.events_windows = {}  # Track open events windows

    def update_controllers(self, controllers):
        """Update tray menu with current controllers and their status."""
        self.controllers = controllers
        self.menu.clear()
        
        logger.debug(f"Updating tray menu with {len(controllers)} controller(s)")

        if not controllers:
            self.menu.addAction("No controllers detected")
            logger.info("No controllers detected")
        else:
            for idx, c in enumerate(controllers):
                self._add_controller_action(c, idx)
            logger.info(f"Displayed {len(controllers)} controller(s) in tray menu")

        self.menu.addSeparator()
        
        # Status line showing total controllers
        status = f"{len(controllers)} controller(s) detected"
        self.menu.addAction(status).setEnabled(False)
        
        self.menu.addSeparator()
        self.menu.addAction("Exit", lambda: sys.exit(0))

    def _add_controller_action(self, controller, controller_index):
        """Add a menu action for a single controller with formatted info."""
        # Build the label
        type_icon = self._get_type_emoji(controller.type)
        connection_icon = self._get_connection_icon(controller.connection)
        battery_percent = self._normalize_battery_percent(controller.battery)
        battery_str = self._format_battery(battery_percent)

        battery_icon = self._get_battery_icon(battery_percent)
        # Put battery info before controller name so it's visible even with long names.
        label = f"{type_icon} {battery_icon} BAT: {battery_str} | {controller.name} ({connection_icon})"

        logger.debug(
            f"Tray label battery diagnostics: name={controller.name}, "
            f"raw={controller.battery}, normalized={battery_percent}, label='{label}'"
        )

        # Make the action clickable to open events window
        action = self.menu.addAction(label)
        action.triggered.connect(lambda: self.open_events_window(controller, controller_index))
        
        return action

    def _get_type_emoji(self, controller_type):
        """Get emoji based on controller type."""
        type_map = {
            ControllerType.XBOX: "🎮",
            ControllerType.PLAYSTATION: "🎮",
            ControllerType.NINTENDO: "🎮",
            ControllerType.GAMESIR: "🎮",
            ControllerType.UNKNOWN: "❓",
        }
        return type_map.get(controller_type, "❓")

    def _get_connection_icon(self, connection_type):
        """Get connection type label."""
        conn_map = {
            ConnectionType.USB: "USB",
            ConnectionType.BLUETOOTH: "BT",
            ConnectionType.DONGLE: "Dongle",
            ConnectionType.UNKNOWN: "?",
        }
        return conn_map.get(connection_type, "?")

    def _get_battery_icon(self, battery_level):
        """Get battery icon based on level."""
        if battery_level is None:
            return "🔋"
        elif battery_level >= 75:
            return "🔋"
        elif battery_level >= 50:
            return "🔋"
        elif battery_level >= 25:
            return "🪫"
        else:
            return "🪫"

    def _format_battery(self, battery_level):
        """Format battery level for display."""
        if battery_level is None:
            return "N/A"
        return f"{battery_level}%"

    def _normalize_battery_percent(self, battery_level):
        """Normalize battery level to 0-100 when possible."""
        if battery_level is None:
            return None

        try:
            value = int(battery_level)
        except (TypeError, ValueError):
            return None

        # Backward compatibility if provider still returns XInput levels (0..3).
        if 0 <= value <= 3:
            level_map = {0: 10, 1: 33, 2: 66, 3: 100}
            return level_map.get(value)

        if 0 <= value <= 100:
            return value

        return None
    
    def open_events_window(self, controller, controller_index):
        """Open the events window for the specified controller."""
        logger.info(f"Opening events window for controller: {controller.name}")
        
        # Create a unique key for this controller
        controller_key = f"{controller.name}_{controller_index}"
        
        # Check if window already exists
        if controller_key in self.events_windows:
            window = self.events_windows[controller_key]
            if window.isVisible():
                # Window is already open, just bring it to front
                window.activateWindow()
                window.raise_()
                return
            else:
                # Window was closed, remove it
                del self.events_windows[controller_key]
        
        # Create new input monitor and events window
        input_monitor = InputMonitor(
            controller_index=controller_index,
            controller_name=controller.name,
            controller_type=controller.type.value,
        )
        events_window = ControllerEventsWindow(controller, input_monitor)
        
        # Store reference to prevent garbage collection
        self.events_windows[controller_key] = events_window
        
        # Show the window
        events_window.show()
        
        # Clean up when window is closed
        events_window.destroyed.connect(
            lambda: self.events_windows.pop(controller_key, None)
        )

