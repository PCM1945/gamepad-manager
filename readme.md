# Gamepad Manager

A system tray application for monitoring wireless game controller battery levels on Windows.

## Project Structure

```
app/
├── main.py
├── tray/
│   ├── tray_icon.py
│   └── menu_builder.py
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
│   └── poller.py
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
