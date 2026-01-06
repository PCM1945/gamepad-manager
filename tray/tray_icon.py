from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt
import sys
import logging
from models.controller import ControllerType, ConnectionType

logger = logging.getLogger("gamepad_manager")


class TrayIcon(QSystemTrayIcon):
    def __init__(self, icon):
        super().__init__(icon)
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.controllers = []

    def update_controllers(self, controllers):
        """Update tray menu with current controllers and their status."""
        self.controllers = controllers
        self.menu.clear()
        
        logger.debug(f"Updating tray menu with {len(controllers)} controller(s)")

        if not controllers:
            self.menu.addAction("No controllers detected")
            logger.info("No controllers detected")
        else:
            for c in controllers:
                self._add_controller_action(c)
            logger.info(f"Displayed {len(controllers)} controller(s) in tray menu")

        self.menu.addSeparator()
        
        # Status line showing total controllers
        status = f"{len(controllers)} controller(s) detected"
        self.menu.addAction(status).setEnabled(False)
        
        self.menu.addSeparator()
        self.menu.addAction("Exit", lambda: sys.exit(0))

    def _add_controller_action(self, controller):
        """Add a menu action for a single controller with formatted info."""
        # Build the label
        type_icon = self._get_type_emoji(controller.type)
        connection_icon = self._get_connection_icon(controller.connection)
        battery_str = self._format_battery(controller.battery)

        label = f"{type_icon} {controller.name}"
        if controller.battery is not None:
            battery_icon = self._get_battery_icon(controller.battery)
            label += f" {battery_icon} {battery_str}"
        else:
            label += " 🔋 N/A"

        label += f" ({connection_icon})"

        action = self.menu.addAction(label)
        action.setEnabled(False)  # Make it non-clickable
        
        return action

    def _get_type_emoji(self, controller_type):
        """Get emoji based on controller type."""
        type_map = {
            ControllerType.XBOX: "🎮",
            ControllerType.PLAYSTATION: "🎮",
            ControllerType.NINTENDO: "🎮",
            ControllerType.UNKNOWN: "❓",
        }
        return type_map.get(controller_type, "❓")

    def _get_connection_icon(self, connection_type):
        """Get connection type label."""
        conn_map = {
            ConnectionType.USB: "USB",
            ConnectionType.BLUETOOTH: "BT",
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

