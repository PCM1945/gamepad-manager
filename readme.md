# Gamepad Manager

A system tray application for monitoring wireless game controller battery levels on Windows.

## Features

- **Real-time Controller Monitoring**: Automatically detects connected controllers (Xbox, PlayStation, Nintendo, etc.)
- **Battery Status**: Shows battery levels for wireless controllers in the system tray
- **Controller Events Viewer**: Click on any controller to open a detailed events window showing:
  - Button presses and releases
  - Analog stick movements (left/right stick)
  - Trigger positions (LT/RT)
  - D-pad input
  - Real-time visual indicators for all inputs

## Project Structure

```
app/
├── main.py
├── tray/
│   ├── tray_icon.py
│   └── menu_builder.py
├── ui/
│   └── events_window.py
├── controllers/
│   ├── base.py
│   ├── xbox.py
│   ├── playstation.py
│   ├── nintendo.py
│   └── detector.py
├── platform/
│   ├── windows.py
│   ├── linux.py
│   └── macos.py
├── workers/
│   ├── poller.py
│   └── input_monitor.py
└── models/
    └── controller.py
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Usage

1. Run the application - it will appear in the system tray
2. Connected controllers will be listed in the tray menu with their battery status
3. Click on any controller to open the **Events Viewer** window
4. In the Events Viewer:
   - Click "Start Monitoring" to begin capturing controller inputs
   - View real-time button presses, stick movements, and trigger positions
   - See visual indicators for all analog inputs
   - Monitor the events log for detailed input history
   - Click "Clear Log" to reset the events display
   - Click "Stop Monitoring" when done

## Troubleshooting

### ImportError: Unable to load hidapi libraries

**Error message:**
```
ImportError: Unable to load any of the following libraries:libhidapi-hidraw.so libhidapi-hidraw.so.0 libhidapi-libusb.so libhidapi-libusb.so.0 libhidapi-iohidmanager.so libhidapi-iohidmanager.so.0 libhidapi.dylib hidapi.dll libhidapi-0.dll
```

**Solution:**

This error occurs when the `hidapi` package is not properly installed with the native Windows DLL. To fix it:

1. Uninstall conflicting packages:
```bash
pip uninstall -y hid hidapi
```

2. Reinstall `hidapi` with fresh download to ensure the Windows wheel is installed:
```bash
pip install --no-cache-dir hidapi
```

3. Verify the installation:
```bash
python -c "import hid; print('hidapi loaded successfully!')"
```

The Windows wheel (`.whl`) includes the necessary `hidapi.dll` file. Using `--no-cache-dir` ensures you download the correct version for your platform
