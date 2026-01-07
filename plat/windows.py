from controllers.batteryprovider import BatteryProvider
from controllers.detector import _get_xinput_api
import logging

logger = logging.getLogger("gamepad_manager")


class WindowsBatteryProvider(BatteryProvider):
    """Get battery level for controllers on Windows using XInput."""

    def __init__(self):
        self.xinput = _get_xinput_api()

    def get_battery(self, controller) -> int | None:
        """
        Get battery level using XInput for connected controllers.

        Args:
            controller: dict with 'index' key indicating XInput slot (0-3)

        Returns:
            Battery percentage (0-100) or None if not available
        """
        try:
            if not self.xinput._xinput:
                return None

            # Get the XInput index from the controller dict
            idx = controller.get("index")
            if idx is None:
                logger.debug("Controller has no XInput index, cannot get battery")
                return None

            battery_info = self.xinput.get_battery(idx)
            if battery_info:
                battery_percent = self._charge_level_to_percent(battery_info.BatteryLevel)
                logger.debug(f"XInput battery for idx {idx}: {battery_percent}%")
                return battery_percent

            return None
        except Exception as e:
            logger.error(f"Error getting battery from XInput: {e}", exc_info=True)
            return None

    def _charge_level_to_percent(self, charge_level) -> int | None:
        """Convert XInput battery level to percentage."""
        try:
            level_map = {0: 10, 1: 30, 2: 65, 3: 100}
            return level_map.get(int(charge_level), None)
        except Exception as e:
            logger.debug(f"Error converting charge level: {e}")
            return None
