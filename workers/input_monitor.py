from PyQt5.QtCore import QThread, pyqtSignal
import logging
import time
import threading
import math

logger = logging.getLogger("gamepad_manager")

try:
    from inputs import UnpluggedError, devices
    INPUTS_AVAILABLE = True
except ImportError:
    INPUTS_AVAILABLE = False
    logger.warning("inputs library not available - controller input monitoring will be disabled")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None
    logger.warning("pygame library not available - fallback controller monitoring disabled")


class InputMonitor(QThread):
    """Monitor controller inputs and emit events."""

    STICK_DEADZONE = 0.15
    
    event_received = pyqtSignal(str)  # Emits event description
    state_updated = pyqtSignal(dict)  # Emits current input state
    
    def __init__(self, controller_index=0, controller_name=None, controller_type=None):
        super().__init__()
        self.controller_index = controller_index
        self.controller_name = controller_name or ""
        self.controller_type = (controller_type or "").lower()
        self.running = False
        self._axis_modes = {}  # axis code -> "signed" | "unsigned"
        self._current_state = {
            "buttons": set(),
            "left_stick": (0, 0),
            "right_stick": (0, 0),
            "left_trigger": 0,
            "right_trigger": 0,
            "axes": {}
        }
        self._state_timer = None
        
    def run(self):
        """Main monitoring loop."""
        try:
            self.running = True
            self.event_received.emit("Monitoring started - move controller to see events...")
            logger.info(
                "Input monitor thread started "
                f"index={self.controller_index} name={self.controller_name} type={self.controller_type}"
            )

            # Start state update timer in a separate thread
            self._start_state_updates()

            # Prefer inputs backend when index is available there.
            if INPUTS_AVAILABLE:
                try:
                    self.event_received.emit(f"Found {len(devices.gamepads)} gamepad(s)")
                    logger.info(f"Monitoring gamepad (inputs backend): {devices.gamepads}")
                    target_gamepad = self._get_target_gamepad()
                    if target_gamepad is not None:
                        self._run_inputs_backend()
                        return
                except Exception as e:
                    logger.warning(f"inputs backend unavailable: {e}")

            # Fallback for controllers not exposed by inputs (common with PlayStation on Windows).
            if PYGAME_AVAILABLE:
                self.event_received.emit("inputs não encontrou esse controle; usando fallback pygame...")
                self._run_pygame_backend()
                return

            self.event_received.emit("ERROR: Controle não disponível em inputs e pygame não está instalado")
            logger.error("No usable backend for controller monitoring")
            self.running = False
        except Exception as e:
            logger.error(f"Error in input monitor: {e}", exc_info=True)
            self.event_received.emit(f"ERROR: {str(e)}")
        finally:
            logger.info("Input monitor thread stopped")
    
    def _start_state_updates(self):
        """Start periodic state updates."""
        def update_loop():
            while self.running:
                self._emit_current_state()
                time.sleep(0.05)  # 20Hz update rate
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()

    def _get_target_gamepad(self):
        """Get the gamepad object that matches this monitor index."""
        gamepads = devices.gamepads
        if not gamepads or self.controller_index < 0:
            return None

        if self.controller_index >= len(gamepads):
            return None

        return gamepads[self.controller_index]

    def _run_inputs_backend(self):
        """Read events from inputs for a specific indexed gamepad."""
        while self.running:
            try:
                target_gamepad = self._get_target_gamepad()
                if target_gamepad is None:
                    self.event_received.emit("Controller disconnected!")
                    logger.warning("No gamepad available for selected index")
                    self.running = False
                    break

                # Blocking read from the selected gamepad only.
                events = target_gamepad.read()
                if not self.running:
                    break

                for event in events:
                    if not self.running:
                        break
                    self._process_event(event)

            except UnpluggedError:
                self.event_received.emit("Controller disconnected!")
                logger.warning("Controller unplugged during monitoring")
                self.running = False
                break
            except OSError as e:
                logger.error(f"OSError in gamepad reading: {e}")
                self.event_received.emit("Controller connection lost!")
                self.running = False
                break
            except Exception as e:
                if self.running:
                    logger.error(f"Error getting gamepad events: {e}")
                    time.sleep(0.1)

    def _run_pygame_backend(self):
        """Fallback backend using pygame joystick APIs."""
        pygame.init()
        pygame.joystick.init()

        joy = self._select_pygame_joystick()
        if joy is None:
            self.event_received.emit("ERROR: pygame não encontrou joysticks disponíveis")
            self.running = False
            return

        self.event_received.emit(f"Fallback ativo: {joy.get_name()}")
        logger.info(f"pygame fallback monitoring joystick: {joy.get_name()}")

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
                self.event_received.emit(f"Button {pressed} pressed")
            for released in sorted(last_buttons - current_buttons):
                self.event_received.emit(f"Button {released} released")
            last_buttons = current_buttons

            self._current_state["buttons"] = {f"B{idx}" for idx in current_buttons}
            time.sleep(0.01)

        try:
            joy.quit()
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

        # If this window is for PlayStation, prioritize PS-like device names.
        if "playstation" in self.controller_type or "sony" in self.controller_name.lower():
            for _, j, name in joysticks:
                if any(k in name for k in ("playstation", "dualshock", "dualsense", "wireless controller", "sony")):
                    return j

        # Exact index mapping when possible.
        for idx, j, _ in joysticks:
            if idx == self.controller_index:
                return j

        # Fallback by controller name similarity.
        expected = self.controller_name.lower().strip()
        if expected:
            for _, j, name in joysticks:
                if expected in name or name in expected:
                    return j

        return joysticks[0][1]
    
    def _process_event(self, event):
        """Process an input event."""
        try:
            event_type = event.ev_type
            code = event.code
            value = event.state
            
            # Button events
            if event_type == "Key":
                button_name = self._get_button_name(code)
                if value == 1:  # Button pressed
                    self._current_state["buttons"].add(button_name)
                    self.event_received.emit(f"Button {button_name} pressed")
                elif value == 0:  # Button released
                    self._current_state["buttons"].discard(button_name)
                    self.event_received.emit(f"Button {button_name} released")
            
            # Axis events (analog sticks, triggers)
            elif event_type == "Absolute":
                axis_name = self._get_axis_name(code)
                normalized_value = self._normalize_axis_value(code, value)
                
                # Store raw axis value
                self._current_state["axes"][code] = normalized_value
                
                # Update stick/trigger states
                self._update_analog_states()
                
                # Only log significant movements
                if abs(normalized_value) > 0.1 or code in ["ABS_Z", "ABS_RZ"]:  # Triggers always log
                    self.event_received.emit(f"{axis_name}: {normalized_value:.2f}")
            
            # D-pad events
            elif event_type == "Sync":
                pass  # Sync events are just markers, ignore them
                
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
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
    
    def _update_analog_states(self):
        """Update stick and trigger states from raw axis values."""
        axes = self._current_state["axes"]
        
        # Left stick (ABS_X, ABS_Y)
        left_x = axes.get("ABS_X", 0)
        left_y = axes.get("ABS_Y", 0)
        left_x, left_y = self._apply_radial_deadzone(left_x, left_y, self.STICK_DEADZONE)
        self._current_state["left_stick"] = (left_x, left_y)
        
        # Right stick (ABS_RX, ABS_RY)
        right_x = axes.get("ABS_RX", 0)
        right_y = axes.get("ABS_RY", 0)
        right_x, right_y = self._apply_radial_deadzone(right_x, right_y, self.STICK_DEADZONE)
        self._current_state["right_stick"] = (right_x, right_y)
        
        # Triggers (ABS_Z, ABS_RZ)
        self._current_state["left_trigger"] = axes.get("ABS_Z", 0)
        self._current_state["right_trigger"] = axes.get("ABS_RZ", 0)
    
    def _normalize_axis_value(self, code, value):
        """Normalize axis values to -1.0 to 1.0 range."""
        # Triggers (0-255) -> (0-1)
        if code in ["ABS_Z", "ABS_RZ"]:
            return max(0.0, min(1.0, value / 255.0))
        
        # Sticks can come as either signed (-32768..32767) or unsigned (0..65535).
        # Normalize both formats to a common -1.0..1.0 range.
        elif code in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]:
            mode = self._detect_axis_mode(code, value)

            if mode == "unsigned":
                normalized = (value - 32768.0) / 32768.0
            else:
                # Signed axis range (-32768..32767)
                if value < 0:
                    normalized = value / 32768.0
                else:
                    normalized = value / 32767.0 if value else 0.0

            return max(-1.0, min(1.0, normalized))
        
        # D-pad (-1, 0, 1) -> keep as is
        elif code in ["ABS_HAT0X", "ABS_HAT0Y"]:
            return float(value)
        
        return float(value)

    def _detect_axis_mode(self, code, value):
        """Detect if an axis is signed (-32768..32767) or unsigned (0..65535)."""
        cached_mode = self._axis_modes.get(code)
        if cached_mode:
            return cached_mode

        # Any negative value guarantees signed mode.
        if value < 0:
            self._axis_modes[code] = "signed"
            return "signed"

        # Values above signed max guarantee unsigned mode.
        if value > 32767:
            self._axis_modes[code] = "unsigned"
            return "unsigned"

        # Ambiguous values (0..32767): default to signed.
        # This avoids collapsing signed-positive half into one side.
        self._axis_modes[code] = "signed"
        return "signed"

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
    
    def _get_axis_name(self, code):
        """Get human-readable axis name."""
        axis_map = {
            "ABS_X": "Left Stick X",
            "ABS_Y": "Left Stick Y",
            "ABS_RX": "Right Stick X",
            "ABS_RY": "Right Stick Y",
            "ABS_Z": "Left Trigger",
            "ABS_RZ": "Right Trigger",
            "ABS_HAT0X": "D-pad X",
            "ABS_HAT0Y": "D-pad Y"
        }
        return axis_map.get(code, code)
    
    def _get_button_name(self, code):
        """Get human-readable button name (Xbox controller mapping)."""
        button_map = {
            "BTN_SOUTH": "A",
            "BTN_EAST": "B",
            "BTN_WEST": "X",
            "BTN_NORTH": "Y",
            "BTN_TL": "LB",
            "BTN_TR": "RB",
            "BTN_SELECT": "Back",
            "BTN_START": "Start",
            "BTN_MODE": "Xbox",
            "BTN_THUMBL": "L3",
            "BTN_THUMBR": "R3"
        }
        return button_map.get(code, code)
    
    def stop(self):
        """Stop the monitoring loop."""
        logger.info("Stopping input monitor")
        self.running = False
        # Give the thread a moment to stop
        self.wait(1000)  # Wait up to 1 second for thread to finish
