from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import logging
import time
import threading

logger = logging.getLogger("gamepad_manager")

try:
    from inputs import get_gamepad, UnpluggedError, devices
    INPUTS_AVAILABLE = True
except ImportError:
    INPUTS_AVAILABLE = False
    logger.warning("inputs library not available - controller input monitoring will be disabled")


class InputMonitor(QThread):
    """Monitor controller inputs and emit events."""
    
    event_received = pyqtSignal(str)  # Emits event description
    state_updated = pyqtSignal(dict)  # Emits current input state
    
    def __init__(self, controller_index=0):
        super().__init__()
        self.controller_index = controller_index
        self.running = False
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
        if not INPUTS_AVAILABLE:
            self.event_received.emit("ERROR: inputs library not installed")
            return
        
        # Check if any gamepads are available
        try:
            if not devices.gamepads:
                self.event_received.emit("ERROR: No gamepads detected")
                logger.warning("No gamepads found")
                return
            
            self.event_received.emit(f"Found {len(devices.gamepads)} gamepad(s)")
            logger.info(f"Monitoring gamepad: {devices.gamepads}")
        except Exception as e:
            self.event_received.emit(f"ERROR: Could not detect gamepads - {e}")
            logger.error(f"Gamepad detection error: {e}")
            return
        
        try:
            self.running = True
            self.event_received.emit("Monitoring started - move controller to see events...")
            logger.info("Input monitor thread started")
            
            # Start state update timer in a separate thread
            self._start_state_updates()
            
            # Main event loop - get_gamepad() is blocking but yields events
            while self.running:
                try:
                    # This will block until an event occurs, but it's in a separate thread
                    events = get_gamepad()
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
                    # Handle controller disconnection
                    logger.error(f"OSError in gamepad reading: {e}")
                    self.event_received.emit("Controller connection lost!")
                    self.running = False
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"Error getting gamepad events: {e}")
                        time.sleep(0.1)
            
            logger.info("Input monitor thread stopped")
                        
        except Exception as e:
            logger.error(f"Error in input monitor: {e}", exc_info=True)
            self.event_received.emit(f"ERROR: {str(e)}")
    
    def _start_state_updates(self):
        """Start periodic state updates."""
        def update_loop():
            while self.running:
                self._emit_current_state()
                time.sleep(0.05)  # 20Hz update rate
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
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
        self._current_state["left_stick"] = (left_x, left_y)
        
        # Right stick (ABS_RX, ABS_RY)
        right_x = axes.get("ABS_RX", 0)
        right_y = axes.get("ABS_RY", 0)
        self._current_state["right_stick"] = (right_x, right_y)
        
        # Triggers (ABS_Z, ABS_RZ)
        self._current_state["left_trigger"] = axes.get("ABS_Z", 0)
        self._current_state["right_trigger"] = axes.get("ABS_RZ", 0)
    
    def _normalize_axis_value(self, code, value):
        """Normalize axis values to -1.0 to 1.0 range."""
        # Triggers (0-255) -> (0-1)
        if code in ["ABS_Z", "ABS_RZ"]:
            return value / 255.0
        
        # Sticks (0-65535, center at 32768) -> (-1.0 to 1.0)
        elif code in ["ABS_X", "ABS_Y", "ABS_RX", "ABS_RY"]:
            # Center at 0, normalize to -1.0 to 1.0
            normalized = (value - 32768) / 32768.0
            # Apply deadzone
            if abs(normalized) < 0.1:
                return 0.0
            return normalized
        
        # D-pad (-1, 0, 1) -> keep as is
        elif code in ["ABS_HAT0X", "ABS_HAT0Y"]:
            return float(value)
        
        return float(value)
    
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
