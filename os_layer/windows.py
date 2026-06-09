from controllers.batteryprovider import BatteryProvider
import logging
import ctypes

logger = logging.getLogger("gamepad_manager")


class WindowsBatteryProvider(BatteryProvider):
    """Get battery level for controllers on Windows using XInput (ctypes)."""

    def __init__(self):
        self._xinput = None
        self._init_xinput()

    def _init_xinput(self):
        """Load an XInput DLL and prepare `XInputGetBatteryInformation`."""
        xinput_libs = ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll")
        for lib in xinput_libs:
            try:
                x = ctypes.WinDLL(lib)

                class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
                    _fields_ = [("BatteryType", ctypes.c_ubyte), ("BatteryLevel", ctypes.c_ubyte)]

                func = getattr(x, "XInputGetBatteryInformation", None)
                if not func:
                    continue
                func.argtypes = [ctypes.c_uint, ctypes.c_ubyte, ctypes.POINTER(XINPUT_BATTERY_INFORMATION)]
                func.restype = ctypes.c_uint
                self._xinput = (x, XINPUT_BATTERY_INFORMATION, func)
                logger.info(f"Loaded {lib} for XInput")
                return
            except Exception:
                continue

        logger.warning("Could not load any XInput DLLs. Battery status will be unavailable.")

    def get_battery(self, controller) -> int | None:
        """
        Get battery level using XInput for connected controllers.

        Args:
            controller: dict (optional `index` key to target specific XInput slot)

        Returns:
            Battery percentage (0-100) or None if not available
        """
        try:
            if not self._xinput:
                logger.debug("Battery diagnostics: XInput unavailable (no DLL loaded)")
                return None

            _, XINPUT_BATTERY_INFORMATION, func = self._xinput

            # If caller provided an `index` (0-3), try it first.
            preferred = controller.get("index") if isinstance(controller, dict) else None
            indices = [preferred] if preferred is not None else []
            indices += [i for i in range(4) if i not in indices]
            logger.debug(
                "Battery diagnostics: querying XInput "
                f"controller={controller.get('name') if isinstance(controller, dict) else controller} "
                f"preferred_idx={preferred} scan_order={indices}"
            )

            for idx in indices:
                try:
                    info = XINPUT_BATTERY_INFORMATION()
                    logger.debug(f"Checking XInput battery for idx {idx}")
                    # devType 0x00 = BATTERY_DEVTYPE_GAMEPAD
                    res = func(ctypes.c_uint(idx), ctypes.c_ubyte(0x00), ctypes.byref(info))
                    # 0 == ERROR_SUCCESS
                    if res == 0:
                        logger.debug(
                            f"XInput battery info for idx {idx}: "
                            f"Type={info.BatteryType}, Level={info.BatteryLevel}"
                        )

                        battery_type = int(info.BatteryType)
                        battery_level = int(info.BatteryLevel)

                        # 0x00=DISCONNECTED, 0xFF=UNKNOWN
                        if battery_type in (0x00, 0xFF):
                            logger.debug(
                                f"Battery diagnostics: idx {idx} skipped (type={battery_type}, level={battery_level})"
                            )
                            continue

                        # 0x01=WIRED has no battery to report.
                        if battery_type == 0x01:
                            logger.debug(
                                f"Battery diagnostics: idx {idx} wired controller (no battery telemetry)"
                            )
                            # Do not return here. Another XInput slot may still be the
                            # wireless controller we are trying to resolve.
                            continue

                        battery_percent = self._charge_level_to_percent(battery_level)
                        if battery_percent is not None:
                            logger.debug(
                                f"Battery diagnostics: idx {idx} mapped level={battery_level} -> {battery_percent}%"
                            )
                            return battery_percent
                        logger.debug(
                            f"Battery diagnostics: idx {idx} unrecognized level={battery_level}"
                        )
                    else:
                        logger.debug(f"Battery diagnostics: idx {idx} XInput call returned error={res}")
                except Exception as e:
                    logger.debug(f"XInput battery check failed for idx {idx}: {e}")
                    continue

            logger.debug("Battery diagnostics: no battery data from any XInput slot")
            return None
        except Exception as e:
            logger.error(f"Error getting battery from XInput: {e}", exc_info=True)
            return None

    def _charge_level_to_percent(self, charge_level) -> int | None:
        """Convert XInput battery level to percentage."""
        try:
            level_map = {0: 10, 1: 33, 2: 66, 3: 100}
            return level_map.get(int(charge_level), None)
        except Exception as e:
            logger.debug(f"Error converting charge level: {e}")
            return None
