from PyQt5.QtCore import QThread, pyqtSignal
import logging
import time
import threading
import math

logger = logging.getLogger("gamepad_manager")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None
    logger.warning("pygame library not available - controller input monitoring disabled")


class InputMonitor(QThread):
    """Monitor controller inputs and emit events."""

    STICK_DEADZONE = 0.15
    _pygame_guard = threading.Lock()
    _pygame_users = 0
    _claimed_joystick_indices = set()
    BUTTON_MAPS = {
        "xbox": {
            0: "A",
            1: "B",
            2: "X",
            3: "Y",
            4: "LB",
            5: "RB",
            6: "Back",
            7: "Start",
            8: "L3",
            9: "R3",
            10: "Xbox",
        },
        "playstation": {
            0: "Cross",
            1: "Circle",
            2: "Square",
            3: "Triangle",
            4: "L1",
            5: "R1",
            6: "Share",
            7: "Options",
            8: "L3",
            9: "R3",
            10: "PS",
            11: "Touchpad",
        },
        "nintendo": {
            0: "B",
            1: "A",
            2: "Y",
            3: "X",
            4: "L",
            5: "R",
            6: "Minus",
            7: "Plus",
            8: "L3",
            9: "R3",
            10: "Home",
            11: "Capture",
        },
    }
    
    event_received = pyqtSignal(str)  # Emits event description
    state_updated = pyqtSignal(dict)  # Emits current input state
    
    def __init__(self, controller_index=0, controller_name=None, controller_type=None):
        super().__init__()
        self.controller_index = controller_index
        self.controller_name = controller_name or ""
        self.controller_type = (controller_type or "").lower()
        self.running = False
        self._current_state = {
            "buttons": set(),
            "left_stick": (0, 0),
            "right_stick": (0, 0),
            "left_trigger": 0,
            "right_trigger": 0,
        }
        self._active_joystick = None
        self._active_joystick_index = None
        
    def run(self):
        """Main monitoring loop."""
        if not PYGAME_AVAILABLE:
            self.event_received.emit("ERROR: pygame-ce/pygame not installed")
            return

        try:
            self.running = True
            self.event_received.emit("Monitoring started - move controller to see events...")
            logger.info(
                "Input monitor thread started "
                f"index={self.controller_index} name={self.controller_name} type={self.controller_type}"
            )

            # Start state update timer in a separate thread
            self._start_state_updates()
            self._run_pygame_backend()
        except Exception as e:
            logger.error(f"Error in input monitor: {e}", exc_info=True)
            self.event_received.emit(f"ERROR: {str(e)}")
        finally:
            self._release_joystick()
            logger.info("Input monitor thread stopped")
    
    def _start_state_updates(self):
        """Start periodic state updates."""
        def update_loop():
            while self.running:
                self._emit_current_state()
                time.sleep(0.05)  # 20Hz update rate
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()

    def _run_pygame_backend(self):
        """Controller monitoring using pygame joystick APIs."""
        self._acquire_pygame()

        joy = self._select_pygame_joystick()
        if joy is None:
            self.event_received.emit("ERROR: pygame nao encontrou joysticks disponiveis")
            self.running = False
            return

        self._active_joystick = joy
        self.event_received.emit(f"Found {pygame.joystick.get_count()} joystick(s)")
        self.event_received.emit(f"Monitoring via pygame: {joy.get_name()}")
        logger.info(f"Monitoring joystick via pygame: {joy.get_name()}")

        last_axes = {}
        last_buttons = set()

        while self.running:
            pygame.event.pump()

            axes_count = joy.get_numaxes()
            buttons_count = joy.get_numbuttons()

            # Common layout for SDL PlayStation mappings.
            left_x = joy.get_axis(0) if axes_count > 0 else 0.0
            left_y = joy.get_axis(1) if axes_count > 1 else 0.0
            right_x = joy.get_axis(2) if axes_count > 2 else 0.0
            right_y = joy.get_axis(3) if axes_count > 3 else 0.0

            # pygame/SDL reports Y positive-down; normalize to cartesian positive-up.
            left_y = -left_y
            right_y = -right_y

            # Triggers are usually axis 4/5 in SDL for DS4/DS5.
            lt_raw = joy.get_axis(4) if axes_count > 4 else -1.0
            rt_raw = joy.get_axis(5) if axes_count > 5 else -1.0
            left_trigger = max(0.0, min(1.0, (lt_raw + 1.0) / 2.0))
            right_trigger = max(0.0, min(1.0, (rt_raw + 1.0) / 2.0))

            left_x, left_y = self._apply_radial_deadzone(left_x, left_y, self.STICK_DEADZONE)
            right_x, right_y = self._apply_radial_deadzone(right_x, right_y, self.STICK_DEADZONE)

            self._current_state["left_stick"] = (left_x, left_y)
            self._current_state["right_stick"] = (right_x, right_y)
            self._current_state["left_trigger"] = left_trigger
            self._current_state["right_trigger"] = right_trigger

            axis_snapshot = {
                "LX": left_x,
                "LY": left_y,
                "RX": right_x,
                "RY": right_y,
                "LT": left_trigger,
                "RT": right_trigger,
            }

            for key, value in axis_snapshot.items():
                prev = last_axes.get(key)
                if prev is None or abs(prev - value) > 0.08:
                    if key in ("LT", "RT") or abs(value) > 0.1:
                        self.event_received.emit(f"{key}: {value:.2f}")
                    last_axes[key] = value

            current_buttons = {idx for idx in range(buttons_count) if joy.get_button(idx)}
            for pressed in sorted(current_buttons - last_buttons):
                self.event_received.emit(f"Button {self._button_name(pressed)} pressed")
            for released in sorted(last_buttons - current_buttons):
                self.event_received.emit(f"Button {self._button_name(released)} released")
            last_buttons = current_buttons

            self._current_state["buttons"] = {self._button_name(idx) for idx in current_buttons}
            time.sleep(0.01)

    def _button_name(self, button_index):
        """Map pygame button index to a platform-specific display name."""
        ctype = self.controller_type
        if "playstation" in ctype:
            mapping = self.BUTTON_MAPS["playstation"]
        elif "nintendo" in ctype:
            mapping = self.BUTTON_MAPS["nintendo"]
        elif "xbox" in ctype:
            mapping = self.BUTTON_MAPS["xbox"]
        else:
            # Controllers with Xbox-like layouts (e.g. many generic pads) look
            # better with Xbox labels than numeric IDs.
            mapping = self.BUTTON_MAPS["xbox"]

        return mapping.get(button_index, f"B{button_index}")

    def _acquire_pygame(self):
        """Initialize pygame once for all monitor threads."""
        with self._pygame_guard:
            if self._pygame_users == 0:
                pygame.init()
                pygame.joystick.init()
            self.__class__._pygame_users += 1

    def _release_joystick(self):
        """Release joystick and shutdown pygame when the last monitor stops."""
        if self._active_joystick is not None:
            try:
                self._active_joystick.quit()
            except Exception:
                pass
            self._active_joystick = None

        with self._pygame_guard:
            if self._active_joystick_index is not None:
                self._claimed_joystick_indices.discard(self._active_joystick_index)
                self._active_joystick_index = None
            if self._pygame_users > 0:
                self.__class__._pygame_users -= 1
            if self._pygame_users == 0 and PYGAME_AVAILABLE:
                try:
                    pygame.joystick.quit()
                    pygame.quit()
                except Exception:
                    pass

    def _select_pygame_joystick(self):
        """Pick the best matching pygame joystick for this monitor."""
        count = pygame.joystick.get_count()
        if count <= 0:
            return None

        joysticks = []
        for idx in range(count):
            j = pygame.joystick.Joystick(idx)
            j.init()
            joysticks.append((idx, j, (j.get_name() or "").lower()))

        def claim_if_available(idx, joystick_obj):
            with self._pygame_guard:
                if idx in self._claimed_joystick_indices:
                    return None
                self._claimed_joystick_indices.add(idx)
                self._active_joystick_index = idx
                return joystick_obj

        def type_matches(name_lower):
            if "playstation" in self.controller_type:
                if any(k in name_lower for k in ("ps4", "ps5", "playstation", "dualshock", "dualsense", "sony")):
                    return True
                # DS4/DS5 often appears as exactly "Wireless Controller" on Windows.
                return "wireless controller" in name_lower and not any(
                    k in name_lower for k in ("xbox", "nintendo", "switch")
                )
            if "nintendo" in self.controller_type:
                return any(k in name_lower for k in ("nintendo", "switch", "joy-con", "pro controller"))
            if "xbox" in self.controller_type:
                return any(k in name_lower for k in ("xbox", "x-box", "360 for windows"))
            return False

        # For PlayStation/Nintendo, type matching is more reliable than tray index.
        if any(k in self.controller_type for k in ("playstation", "nintendo")):
            for idx, j, name in joysticks:
                if type_matches(name):
                    claimed = claim_if_available(idx, j)
                    if claimed is not None:
                        logger.info(f"Joystick selected by type: idx={idx} name={j.get_name()} type={self.controller_type}")
                        return claimed

        # 1) Match by controller name first. This is the most stable signal
        # when tray ordering and pygame ordering diverge.
        expected = self.controller_name.lower().strip()
        if expected:
            for idx, j, name in joysticks:
                if expected in name or name in expected:
                    claimed = claim_if_available(idx, j)
                    if claimed is not None:
                        logger.info(f"Joystick selected by name: idx={idx} name={j.get_name()}")
                        return claimed

        # 2) Exact index mapping when name matching did not resolve.
        for idx, j, _ in joysticks:
            if idx == self.controller_index:
                claimed = claim_if_available(idx, j)
                if claimed is not None:
                    logger.info(f"Joystick selected by index: idx={idx} name={j.get_name()}")
                    return claimed

        # 3) For PlayStation windows, then prefer PS-like names.
        if "playstation" in self.controller_type or "sony" in self.controller_name.lower():
            for idx, j, name in joysticks:
                if any(k in name for k in ("playstation", "dualshock", "dualsense", "sony", "ps4", "ps5")) or (
                    "wireless controller" in name and not any(k in name for k in ("xbox", "nintendo", "switch"))
                ):
                    claimed = claim_if_available(idx, j)
                    if claimed is not None:
                        logger.info(f"Joystick selected by PS fallback: idx={idx} name={j.get_name()}")
                        return claimed

        # 4) First non-claimed joystick.
        for idx, j, _ in joysticks:
            claimed = claim_if_available(idx, j)
            if claimed is not None:
                logger.info(f"Joystick selected by first-free: idx={idx} name={j.get_name()}")
                return claimed

        # 5) If everything is claimed, keep the previous behavior as last resort.
        idx, j, _ = joysticks[0]
        self._active_joystick_index = idx
        return j
    
    def _emit_current_state(self):
        """Emit current state to UI."""
        try:
            state = {
                "buttons": list(self._current_state["buttons"]),
                "left_stick": self._current_state["left_stick"],
                "right_stick": self._current_state["right_stick"],
                "left_trigger": self._current_state["left_trigger"],
                "right_trigger": self._current_state["right_trigger"]
            }
            self.state_updated.emit(state)
        except Exception as e:
            logger.error(f"Error emitting state: {e}")
    
    def _apply_radial_deadzone(self, x, y, deadzone):
        """Apply radial deadzone while preserving stick angle and full output range."""
        magnitude = math.sqrt((x * x) + (y * y))
        if magnitude <= deadzone:
            return 0.0, 0.0

        # Re-scale the remaining range so movement still reaches full scale at the edge.
        scaled_magnitude = (magnitude - deadzone) / (1.0 - deadzone)
        scaled_magnitude = max(0.0, min(1.0, scaled_magnitude))

        factor = scaled_magnitude / magnitude
        return x * factor, y * factor
    
    def stop(self):
        """Stop the monitoring loop."""
        logger.info("Stopping input monitor")
        self.running = False
        # Give the thread a moment to stop
        self.wait(1000)  # Wait up to 1 second for thread to finish
