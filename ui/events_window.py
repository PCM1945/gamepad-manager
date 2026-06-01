from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTextEdit, QPushButton, QGroupBox, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
import logging

logger = logging.getLogger("gamepad_manager")


class ControllerEventsWindow(QWidget):
    """Window to display real-time controller input events."""
    
    def __init__(self, controller, input_monitor):
        super().__init__()
        self.controller = controller
        self.input_monitor = input_monitor
        self.is_monitoring = False
        
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle(f"Controller Events - {self.controller.name}")
        self.setGeometry(100, 100, 700, 600)
        
        # Main layout
        layout = QVBoxLayout()
        
        # Controller info section
        info_group = self._create_info_section()
        layout.addWidget(info_group)
        
        # Input status section
        status_group = self._create_status_section()
        layout.addWidget(status_group)
        
        # Events log section
        events_group = self._create_events_section()
        layout.addWidget(events_group, stretch=1)
        
        # Control buttons
        buttons_layout = self._create_buttons()
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def _create_info_section(self):
        """Create controller information section."""
        group = QGroupBox("Controller Information")
        layout = QVBoxLayout()
        
        # Controller details
        info_text = f"Name: {self.controller.name}\n"
        info_text += f"Type: {self.controller.type.value}\n"
        info_text += f"Connection: {self.controller.connection.value}\n"
        
        if self.controller.battery is not None:
            info_text += f"Battery: {self.controller.battery}%"
        else:
            info_text += "Battery: N/A"
        
        info_label = QLabel(info_text)
        info_label.setFont(QFont("Consolas", 10))
        layout.addWidget(info_label)
        
        group.setLayout(layout)
        return group
    
    def _create_status_section(self):
        """Create input status section with visual indicators."""
        group = QGroupBox("Input Status")
        layout = QVBoxLayout()
        
        # Buttons status
        self.buttons_label = QLabel("Buttons: None")
        self.buttons_label.setFont(QFont("Consolas", 9))
        layout.addWidget(self.buttons_label)
        
        # Left stick
        left_stick_layout = QHBoxLayout()
        left_stick_layout.addWidget(QLabel("Left Stick:"))
        self.left_stick_x = QProgressBar()
        self.left_stick_x.setRange(-100, 100)
        self.left_stick_x.setValue(0)
        self.left_stick_x.setFormat("X: %v")
        left_stick_layout.addWidget(self.left_stick_x)
        
        self.left_stick_y = QProgressBar()
        self.left_stick_y.setRange(-100, 100)
        self.left_stick_y.setValue(0)
        self.left_stick_y.setFormat("Y: %v")
        left_stick_layout.addWidget(self.left_stick_y)
        layout.addLayout(left_stick_layout)
        
        # Right stick
        right_stick_layout = QHBoxLayout()
        right_stick_layout.addWidget(QLabel("Right Stick:"))
        self.right_stick_x = QProgressBar()
        self.right_stick_x.setRange(-100, 100)
        self.right_stick_x.setValue(0)
        self.right_stick_x.setFormat("X: %v")
        right_stick_layout.addWidget(self.right_stick_x)
        
        self.right_stick_y = QProgressBar()
        self.right_stick_y.setRange(-100, 100)
        self.right_stick_y.setValue(0)
        self.right_stick_y.setFormat("Y: %v")
        right_stick_layout.addWidget(self.right_stick_y)
        layout.addLayout(right_stick_layout)
        
        # Triggers
        triggers_layout = QHBoxLayout()
        triggers_layout.addWidget(QLabel("Triggers:"))
        self.left_trigger = QProgressBar()
        self.left_trigger.setRange(0, 100)
        self.left_trigger.setValue(0)
        self.left_trigger.setFormat("LT: %v")
        triggers_layout.addWidget(self.left_trigger)
        
        self.right_trigger = QProgressBar()
        self.right_trigger.setRange(0, 100)
        self.right_trigger.setValue(0)
        self.right_trigger.setFormat("RT: %v")
        triggers_layout.addWidget(self.right_trigger)
        layout.addLayout(triggers_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_events_section(self):
        """Create events log section."""
        group = QGroupBox("Events Log")
        layout = QVBoxLayout()
        
        self.events_text = QTextEdit()
        self.events_text.setReadOnly(True)
        self.events_text.setFont(QFont("Consolas", 9))
        self.events_text.setPlaceholderText("Events will appear here when monitoring starts...")
        layout.addWidget(self.events_text)
        
        group.setLayout(layout)
        return group
    
    def _create_buttons(self):
        """Create control buttons."""
        layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.clicked.connect(self.toggle_monitoring)
        layout.addWidget(self.start_btn)
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return layout
    
    def setup_connections(self):
        """Setup signal connections with the input monitor."""
        self.input_monitor.event_received.connect(self.on_input_event)
        self.input_monitor.state_updated.connect(self.on_state_update)
    
    def toggle_monitoring(self):
        """Toggle input monitoring on/off."""
        if not self.is_monitoring:
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """Start monitoring controller inputs."""
        logger.info(f"Starting input monitoring for {self.controller.name}")
        self.input_monitor.start()
        self.is_monitoring = True
        self.start_btn.setText("Stop Monitoring")
        self.log_event("=== Monitoring Started ===")
    
    def stop_monitoring(self):
        """Stop monitoring controller inputs."""
        logger.info(f"Stopping input monitoring for {self.controller.name}")
        self.input_monitor.stop()
        self.is_monitoring = False
        self.start_btn.setText("Start Monitoring")
        self.log_event("=== Monitoring Stopped ===")
    
    @pyqtSlot(str)
    def on_input_event(self, event_text):
        """Handle incoming input event."""
        self.log_event(event_text)
    
    @pyqtSlot(dict)
    def on_state_update(self, state):
        """Update visual indicators with current input state."""
        # Update buttons
        if "buttons" in state and state["buttons"]:
            buttons_str = ", ".join(state["buttons"])
            self.buttons_label.setText(f"Buttons: {buttons_str}")
        else:
            self.buttons_label.setText("Buttons: None")
        
        # Update left stick
        if "left_stick" in state:
            x, y = state["left_stick"]
            self.left_stick_x.setValue(int(x * 100))
            self.left_stick_y.setValue(int(y * 100))
        
        # Update right stick
        if "right_stick" in state:
            x, y = state["right_stick"]
            self.right_stick_x.setValue(int(x * 100))
            self.right_stick_y.setValue(int(y * 100))
        
        # Update triggers
        if "left_trigger" in state:
            self.left_trigger.setValue(int(state["left_trigger"] * 100))
        
        if "right_trigger" in state:
            self.right_trigger.setValue(int(state["right_trigger"] * 100))
    
    def log_event(self, text):
        """Add event to the log."""
        self.events_text.append(text)
        # Auto-scroll to bottom
        self.events_text.verticalScrollBar().setValue(
            self.events_text.verticalScrollBar().maximum()
        )
    
    def clear_log(self):
        """Clear the events log."""
        self.events_text.clear()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_monitoring:
            self.stop_monitoring()
        event.accept()
