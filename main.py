
import sys
import os
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from tray.tray_icon import TrayIcon
from workers.poller import ControllerPoller

# Setup logging
log_dir = os.path.expanduser("~")
log_file = os.path.join(log_dir, "gamepad_manager.log")

# Configure logger
logger = logging.getLogger("gamepad_manager")
logger.setLevel(logging.DEBUG)

# File handler - logs everything
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Console handler - only logs warnings and errors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=== Gamepad Manager Started ===")

try:
    app = QApplication(sys.argv)
    logger.info("PyQt5 Application initialized")

    # Handle icon path for both development and PyInstaller builds
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        logger.info(f"Running as frozen executable, base path: {base_path}")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Running in development mode, base path: {base_path}")

    icon_path = os.path.join(base_path, "controller.png")
    logger.info(f"Loading icon from: {icon_path}")
    tray = TrayIcon(QIcon(icon_path))
    tray.show()
    logger.info("Tray icon displayed")

    poller = ControllerPoller()
    poller.updated.connect(tray.update_controllers)
    poller.start()
    logger.info("Controller poller started")

    sys.exit(app.exec())

except Exception as e:
    logger.critical(f"Critical error: {e}", exc_info=True)
    print(f"Error: {e}")
    print(traceback.format_exc())
